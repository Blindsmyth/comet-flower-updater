"""Record the pedal's 8-channel USB input (the --tap8 build) and say what each channel carries.

    python tools/ua_capture8.py [--seconds 20] [--out take.wav]
    python tools/ua_capture8.py --wav take.wav

Channel labels come from tools/ua_channels.json (the one place to edit when the map changes).
Each recording also writes one mono WAV per channel named after its signal
(take8_<time>_03_Guitar_DI.wav, ...) and take8_<time>.channels.json with the map.
Per channel: rms / peak in dBFS, clipped samples, the share of the take that is silent
(digital zero), and the strongest correlation with another channel, so a take with the
drum machine or the looper running shows which bus carries it. WASAPI exclusive mode,
like tools/ua_capture.py; never writes to the pedal.
"""
import argparse
import sys
import time
import wave
from pathlib import Path

import json
import re

import numpy as np

FS = 44100
MAP_FILE = Path(__file__).with_name("ua_channels.json")
CHMAP = json.loads(MAP_FILE.read_text())
NAMES = [c["label"] for c in CHMAP["channels"]]


def slug(label):
    return re.sub(r"[^A-Za-z0-9]+", "_", label).strip("_")


def save_labelled(out, data):
    """Next to the multichannel take: one mono WAV per channel named after its signal, and a
    JSON sidecar with the channel map, so every take stays labelled outside this tool."""
    stem = out.with_suffix("")
    files = []
    for ch in range(data.shape[1]):
        label = NAMES[ch] if ch < len(NAMES) else "ch%d" % (ch + 1)
        f = Path("%s_%02d_%s.wav" % (stem, ch + 1, slug(label)))
        save(f, data[:, ch:ch + 1])
        files.append(f.name)
    side = stem.with_suffix(".channels.json")
    side.write_text(json.dumps({"take": out.name, "firmware": CHMAP.get("firmware"),
                                "channels": CHMAP["channels"][:data.shape[1]], "files": files}, indent=2))
    return files, side


def record(seconds, nch, device=None):
    import sounddevice as sd
    if device is None:
        for i, d in enumerate(sd.query_devices()):
            api = sd.query_hostapis(d["hostapi"])["name"]
            if "Comet Flower" in d["name"] and d["max_input_channels"] >= nch and "WASAPI" in api:
                device = i
                break
        else:
            sys.exit("no WASAPI input named 'Comet Flower' with %d channels (is the 8ch build on the pedal?)" % nch)
    t0 = time.monotonic()
    data = sd.rec(int(seconds * FS), samplerate=FS, channels=nch, dtype="int16", device=device,
                  extra_settings=sd.WasapiSettings(exclusive=True), blocking=True)
    wall = time.monotonic() - t0
    print("%d frames x %d ch took %.1f s of wall time (%.0f frames/s)" % (len(data), nch, wall, len(data) / wall))
    return data


def save(path, data):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(data.shape[1])
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes(np.ascontiguousarray(data, dtype="<i2").tobytes())


def load(path):
    with wave.open(str(path)) as w:
        n = w.getnchannels()
        return np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, n)


def db(x):
    return 20 * np.log10(max(x, 1e-9) / 32768.0)


def report(data):
    x = data.astype(np.float64)
    n = x.shape[1]
    rms = np.sqrt((x ** 2).mean(axis=0))
    lines = ["%d frames (%.2f s), %d channels" % (len(x), len(x) / FS, n)]
    active = rms > 4
    corr = np.zeros((n, n))
    if active.sum() > 1:
        xs = x[:, active] - x[:, active].mean(axis=0)
        c = np.corrcoef(xs.T)
        corr[np.ix_(active, active)] = c
    for ch in range(n):
        col = data[:, ch]
        peak = int(np.abs(col.astype(np.int32)).max())
        zero = float(np.mean(col == 0))
        clip = int(np.sum((col == 32767) | (col == -32768)))
        best = ""
        if active[ch]:
            others = [(abs(corr[ch, k]), k) for k in range(n) if k != ch and active[k]]
            if others:
                v, k = max(others)
                best = "most like ch%d %s (|r| %.2f)" % (k + 1, NAMES[k] if k < len(NAMES) else "", v)
        name = NAMES[ch] if ch < len(NAMES) else ""
        lines.append("ch%d %-11s rms %6.1f dBFS  peak %6.1f dBFS  zero %5.1f %%  clipped %d  %s" % (
            ch + 1, name, db(rms[ch]), db(peak), 100 * zero, clip, best if active[ch] else "(silent)"))
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=float, default=20)
    ap.add_argument("--channels", type=int, default=8)
    ap.add_argument("--out")
    ap.add_argument("--wav")
    ap.add_argument("--device", type=int)
    ap.add_argument("--no-split", action="store_true", help="do not write the per-channel labelled WAVs")
    ap.add_argument("--split", action="store_true", help="with --wav: write labelled per-channel WAVs for it")
    a = ap.parse_args()
    if a.wav:
        data = load(a.wav)
        if a.split:
            files, side = save_labelled(Path(a.wav), data)
            print("labelled: %s ... (%d files), map %s" % (files[0], len(files), side.name))
    else:
        data = record(a.seconds, a.channels, a.device)
        out = Path(a.out) if a.out else Path(__file__).resolve().parents[1] / "build" / "ua_takes" / (
            "take8_%s.wav" % time.strftime("%Y%m%d_%H%M%S"))
        out.parent.mkdir(parents=True, exist_ok=True)
        save(out, data)
        print("recorded", out)
        if not a.no_split:
            files, side = save_labelled(out, data)
            print("labelled: %s ... (%d files), map %s" % (files[0], len(files), side.name))
    print("\n".join(report(data)))


if __name__ == "__main__":
    main()
