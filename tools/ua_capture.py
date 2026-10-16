"""Record the pedal's USB audio input directly and check it.

    python tools/ua_capture.py [--seconds 10] [--out take.wav]   record, then analyse
    python tools/ua_capture.py --wav take.wav                    analyse an existing take
    python tools/ua_capture.py --list                            list input devices

Recording uses WASAPI exclusive mode (no Windows mixer, so no dither, resampling or
"enhancements" touch the samples), 44.1 kHz stereo 16-bit, from the first input whose
name contains "Comet Flower" (--device to choose another). If exclusive mode is refused it
falls back to shared mode and says so: shared-mode takes carry +-1 dither.

Analysis:
- Pattern takes (the diagnostic build, make_usb_audio_fw.py --tap-pattern: left = frame
  counter, right = 1002 Hz sine indexed by the counter): every frame is checked against
  what the pedal sent. Reports gaps (frames lost, and how many), repeats or backward
  jumps, padding (all-zero frames), and corrupt frames (right channel does not match
  the counter), with their spacing.
- Any other take (guitar through the normal tap build): level, clipping, all-zero runs,
  and sample-to-sample jumps far above the signal's own slope (clicks), with spacing.
"""
import argparse
import collections
import sys
import wave
from pathlib import Path

import numpy as np

FS = 44100
SINE = np.round(16384 * np.sin(2 * np.pi * (np.arange(44) + 0.5) / 44)).astype(np.int16)


def record(seconds, device=None, exclusive=True):
    import sounddevice as sd
    if device is None:
        for i, d in enumerate(sd.query_devices()):
            api = sd.query_hostapis(d["hostapi"])["name"]
            if "Comet Flower" in d["name"] and d["max_input_channels"] >= 2 and "WASAPI" in api:
                device = i
                break
        else:
            sys.exit("no WASAPI input named 'Comet Flower' (try --list)")
    extra = sd.WasapiSettings(exclusive=True) if exclusive else None
    import time
    t0 = time.monotonic()
    try:
        data = sd.rec(int(seconds * FS), samplerate=FS, channels=2, dtype="int16",
                      device=device, extra_settings=extra, blocking=True)
        mode = "exclusive" if exclusive else "shared"
    except sd.PortAudioError as e:
        if not exclusive:
            raise
        print("exclusive mode refused (%s); recording shared (expect +-1 dither)" % e)
        data = sd.rec(int(seconds * FS), samplerate=FS, channels=2, dtype="int16",
                      device=device, blocking=True)
        mode = "shared"
    wall = time.monotonic() - t0
    print("%d frames took %.1f s of wall time (%.0f frames/s arrived)" % (len(data), wall, len(data) / wall))
    return data, mode


def load_wav(path):
    with wave.open(str(path)) as w:
        if w.getnchannels() != 2 or w.getsampwidth() != 2:
            sys.exit("need a 16-bit stereo wav")
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2)


def save_wav(path, data):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes(np.ascontiguousarray(data, dtype="<i2").tobytes())


def is_pattern(data):
    """True when most frames carry the counter + matching sine."""
    if len(data) < 100:
        return False
    return np.mean(data[:, 1] == SINE[_unwrap(data) % 44]) > 0.5


def _unwrap(data):
    """Full frame count from the 16-bit left counter. The sine phase follows the full
    count (65536 % 44 != 0), so it is needed to check the right channel after a wrap.
    Padding frames are skipped when counting wraps."""
    l = data[:, 0].astype(np.uint16).astype(np.int64)
    real = ~((data[:, 0] == 0) & (data[:, 1] == 0))
    idx = np.where(real)[0]
    wraps = np.zeros(len(l), np.int64)
    if len(idx) > 1:
        back = np.diff(l[idx]) < -32768
        w = np.concatenate([[0], np.cumsum(back)])
        wraps[idx] = w
        wraps = np.maximum.accumulate(wraps)
    full = l + 65536 * wraps
    # Wraps before the take shift the sine phase by 20 per wrap (65536 % 44), period 11:
    # pick the starting wrap count that matches the right channel best.
    best = max(range(11), key=lambda k: np.sum(data[:, 1] == SINE[(full + 65536 * k) % 44]))
    return full + 65536 * best


def _spacing(idx):
    if len(idx) < 2:
        return ""
    g = np.diff(idx)
    return "spacing frames: min %d, median %d, max %d" % (g.min(), np.median(g), g.max())


def analyse_pattern(data):
    """Classify every frame of a pattern take. Returns (report lines, events)."""
    l = data[:, 0].astype(np.uint16).astype(np.int64)
    r = data[:, 1]
    zero = (data[:, 0] == 0) & (data[:, 1] == 0)        # the sine is never 0: padding
    good_r = r == SINE[_unwrap(data) % 44]
    corrupt = ~zero & ~good_r
    valid = np.where(~zero & good_r)[0]
    events = []                                          # (frame index, kind, size)
    for a, b in zip(valid[:-1], valid[1:]):
        step = (l[b] - l[a]) % 65536
        between = b - a - 1                              # padding/corrupt frames in between
        lost = step - 1                                  # counter values not received in order
        if lost in (0, between):
            continue          # in order: filler was inserted (lost 0) or stood in for frames 1:1
        if step == 0 or step > 32768:
            events.append((int(b), "repeat/back", int(65536 - step + 1 if step else 1)))  # frames replayed
        else:
            events.append((int(b), "gap", int(lost)))
    zruns = _runs(zero)
    cruns = _runs(corrupt)
    n = len(data)
    lines = ["pattern take: %d frames (%.2f s)" % (n, n / FS),
             "in-order valid frames: %d (%.3f %%)" % (len(valid), 100.0 * len(valid) / max(n, 1)),
             "padding (all-zero) runs: %d, frames %d %s" % (len(zruns), sum(z[1] for z in zruns),
                                                           _spacing([z[0] for z in zruns])),
             "corrupt runs (right channel does not match counter): %d, frames %d %s" % (
                 len(cruns), sum(c[1] for c in cruns), _spacing([c[0] for c in cruns]))]
    gaps = [e for e in events if e[1] == "gap"]
    reps = [e for e in events if e[1] != "gap"]
    lines.append("gaps (frames lost): %d, lost %d %s" % (len(gaps), sum(g[2] for g in gaps),
                                                        _spacing([g[0] for g in gaps])))
    if gaps:
        sizes = np.bincount([g[2] for g in gaps])
        lines.append("  gap sizes: " + ", ".join("%d x%d" % (s, c) for s, c in enumerate(sizes) if c))
    lines.append("repeats/backward jumps: %d %s" % (len(reps), _spacing([e[0] for e in reps])))
    if len(reps):
        sizes = np.bincount([e[2] for e in reps])
        lines.append("  repeat sizes: " + ", ".join("%d x%d" % (s, c) for s, c in enumerate(sizes) if c))
    lines += diag_report(data, corrupt)
    if cruns and not any(l.startswith("pedal diag") for l in lines):
        i = cruns[0][0]
        lines.append("  first corrupt frame %d: L %04x R %04x (expected R %04x); neighbours %s" % (
            i, int(data[i, 0]) & 0xffff, int(data[i, 1]) & 0xffff, int(SINE[_unwrap(data)[i] % 44]) & 0xffff,
            [(int(x) & 0xffff, int(y) & 0xffff) for x, y in data[max(i - 2, 0):i + 3]]))
    if len(valid) > 1:
        # Counter span over the take (unwrapped from the in-order steps).
        steps = (np.diff(l[valid]) % 65536)
        sent = int(np.sum(np.where(steps > 32768, 0, steps)))
        lines.append("frames the pedal generated / frames received: %.5f (1.0 = nothing lost)"
                     % ((sent + 1) / (valid[-1] - valid[0] + 1)))
    first = sorted(events + [(z[0], "padding", z[1]) for z in zruns] +
                   [(c[0], "corrupt", c[1]) for c in cruns])[:15]
    if first:
        lines.append("first events (frame, kind, size): %s" % first)
    return lines, events


DIAG_NAMES = ["packets loaded", "SOFs skipped (TxPktRdy still set)", "TXCSR UnderRun seen",
              "USB frames with no tick", "ring fill", "tap overruns", "tap underruns", "TXCSR"]


def diag_report(data, mismatch):
    """Pedal-side counters carried in the first frame of each packet (pattern build with
    in-band diag, usb_audio_tap.c). Returns [] when the take has none."""
    idx = np.where(mismatch)[0]
    if len(idx) < 16:
        return []
    r = data[idx, 1].astype(np.uint16).astype(np.int64)
    tag, val = r >> 13, r & 0x1fff
    # Real diag frames start each received packet: 44 or 45 frames apart within a run
    # of received packets (lost packets only lengthen some spacings).
    if np.mean(np.isin(np.diff(idx), (44, 45))) < 0.3:
        return []
    out = ["pedal diag: %d packet-start frames received; packet length (frames between): %s" % (
        len(idx), dict(sorted(collections.Counter(np.diff(idx).tolist()).most_common(6))))]
    t0 = np.where(tag == 0)[0]
    if len(t0) > 1:
        loaded = (int(val[t0[-1]]) - int(val[t0[0]])) % 8192 * 8
        got = t0[-1] - t0[0]
        out.append("  packets loaded by the pedal %d, received %d, lost on the way %d (%.2f %%)" % (
            loaded, got, loaded - got, 100.0 * (loaded - got) / max(loaded, 1)))
    for k in (1, 2, 3, 5, 6):
        sel = np.where(tag == k)[0]
        if len(sel) > 1:
            out.append("  %s: +%d during the take (last %d)" % (
                DIAG_NAMES[k], (int(val[sel[-1]]) - int(val[sel[0]])) % 8192, int(val[sel[-1]])))
    sel = np.where(tag == 4)[0]
    if len(sel):
        f = val[sel]
        out.append("  ring fill at SOF: min %d, median %d, max %d" % (f.min(), np.median(f), f.max()))
    sel = np.where(tag == 7)[0]
    if len(sel):
        out.append("  TXCSR at SOF: %s" % ", ".join("%04x x%d" % (v, c) for v, c in
                                                     collections.Counter(val[sel].tolist()).most_common(6)))
    return out


def _runs(mask):
    out, start = [], None
    for i, v in enumerate(np.append(mask, False)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            out.append((start, i - start))
            start = None
    return out


def analyse_audio(data):
    x = data.astype(np.float64)
    lines = ["audio take: %d frames (%.2f s)" % (len(x), len(x) / FS)]
    for ch, name in ((0, "L"), (1, "R")):
        s = x[:, ch]
        rms = s.std()
        lines.append("%s: rms %.0f (%.1f dBFS), peak %d, clipped frames %d" % (
            name, rms, 20 * np.log10(max(rms, 1e-9) / 32768), int(abs(s).max()),
            int(np.sum(abs(s) >= 32767))))
    zero = np.all(data == 0, axis=1)
    zr = [z for z in _runs(zero) if z[1] >= 8]
    lines.append("all-zero runs of 8+ frames: %d %s" % (len(zr), _spacing([z[0] for z in zr])))
    s = x[:, 0]
    d2 = np.abs(np.diff(s, 2))
    thr = 8 * np.median(d2) + 50
    clicks = np.where(d2 > thr)[0]
    if len(clicks):
        clicks = clicks[np.append(True, np.diff(clicks) > 4)]
    lines.append("clicks (2nd difference > %.0f): %d %s" % (thr, len(clicks), _spacing(clicks)))
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=float, default=10)
    ap.add_argument("--out", help="wav to write (default: build/ua_takes/take_<time>.wav)")
    ap.add_argument("--wav", help="analyse this wav instead of recording")
    ap.add_argument("--device", type=int)
    ap.add_argument("--shared", action="store_true", help="record in shared mode")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list:
        import sounddevice as sd
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"]:
                print(i, sd.query_hostapis(d["hostapi"])["name"], "|", d["name"])
        return
    if a.wav:
        data = load_wav(a.wav)
    else:
        data, mode = record(a.seconds, a.device, not a.shared)
        if a.out:
            out = Path(a.out)
        else:
            import time
            out = Path(__file__).resolve().parents[1] / "build" / "ua_takes" / (
                "take_%s.wav" % time.strftime("%Y%m%d_%H%M%S"))
        out.parent.mkdir(parents=True, exist_ok=True)
        save_wav(out, data)
        print("recorded %s (%s mode)" % (out, mode))
    lines = analyse_pattern(data)[0] if is_pattern(data) else analyse_audio(data)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
