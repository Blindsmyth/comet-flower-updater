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
- Any other take (guitar through the normal tap build): level, clipping, the leading
  priming run, and stream defects found by linear prediction (lost / repeated frames,
  inserted zero runs, sample jumps), "N defects in M min". Below QUIET_RMS (a few LSB of
  noise) the defect check is skipped: noise cannot be predicted, so it would flag noise.
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
              "USB frames with no tick", "ring fill", "ticks in an unchanged frame",
              "tap overruns/underruns", "TXCSR"]
# Variants build after run 9 (variants build 74f779cb used: 0 double+on, 1 single+on,
# 2 double+off, 3 single+off).
VARIANTS = ["double buffer, ISOUpdate off", "single buffer, ISOUpdate off",
            "double buffer, ISOUpdate on", "single buffer, ISOUpdate on"]


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
    fields = {1: (val, 8192), 2: (val, 8192), 3: (val & 0x7ff, 2048), 5: (val, 8192),
              6: (val >> 7, 64)}
    for k, (v, mod) in fields.items():
        sel = np.where(tag == k)[0]
        if len(sel) > 1:
            name = "tap overruns" if k == 6 else DIAG_NAMES[k]
            out.append("  %s: +%d during the take (last %d)" % (
                name, (int(v[sel[-1]]) - int(v[sel[0]])) % mod, int(v[sel[-1]])))
    sel = np.where(tag == 6)[0]
    if len(sel) > 1:
        u = val[sel] & 0x7f
        out.append("  tap underruns: +%d during the take" % ((int(u[-1]) - int(u[0])) % 128))
    out += variant_report(tag, val)
    sel = np.where(tag == 4)[0]
    if len(sel):
        f = val[sel]
        out.append("  ring fill at SOF: min %d, median %d, max %d" % (f.min(), np.median(f), f.max()))
    sel = np.where(tag == 7)[0]
    if len(sel):
        out.append("  TXCSR at SOF: %s" % ", ".join("%04x x%d" % (v, c) for v, c in
                                                     collections.Counter(val[sel].tolist()).most_common(6)))
    return out


def variant_report(tag, val):
    """Packets loaded vs received for each FIFO set-up variant (tag 3 bits 11..12)."""
    t3 = np.where(tag == 3)[0]
    if len(t3) == 0 or not np.any(val[t3] >> 11):
        return []
    var = np.full(len(tag), -1)
    var[t3] = val[t3] >> 11
    for i in range(1, len(var)):                 # carry the latest variant forward
        if var[i] < 0:
            var[i] = var[i - 1]
    t0 = np.where(tag == 0)[0]
    loaded, got = collections.Counter(), collections.Counter()
    for a, b in zip(t0[:-1], t0[1:]):
        seg = var[a:b + 1]
        if seg[0] < 0 or np.any(seg != seg[0]):
            continue                             # spans a variant change
        n = (int(val[b]) - int(val[a])) % 8192 * 8
        if n > 400:
            continue                             # long silence; skip
        loaded[int(seg[0])] += n
        got[int(seg[0])] += b - a
    out = ["  per FIFO set-up variant (packets loaded / received / lost):"]
    for k in range(4):
        if loaded[k]:
            out.append("    %d %-30s %6d / %6d / %5.1f %%" % (
                k, VARIANTS[k], loaded[k], got[k], 100.0 * (loaded[k] - got[k]) / loaded[k]))
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


def _fast_median_mad(x):
    n = len(x)
    mid = n >> 1
    med = float(np.partition(x, mid)[mid])
    ad = np.abs(x - med)
    mad = float(np.partition(ad, mid)[mid])
    return med, mad * 1.4826


def _find_priming(data, chunk=4096):
    n = len(data)
    i = 0
    while i < n:
        sub = data[i:min(n, i + chunk)]
        nz = np.where((sub[:, 0] != 0) | (sub[:, 1] != 0))[0]
        if len(nz) > 0:
            prim = i + int(nz[0])
            return prim if prim >= 4 else 0
        i += chunk
    return n


def _channel_level(data, ch, chunk=262144):
    n = len(data)
    if n == 0:
        return 0.0, 0, 0
    sum_s = 0.0
    sum_s2 = 0.0
    peak = 0
    clipped = 0
    for i in range(0, n, chunk):
        s = data[i:min(n, i + chunk), ch].astype(np.float64)
        sum_s += float(np.sum(s))
        sum_s2 += float(np.dot(s, s))
        ab = np.abs(s)
        pk = int(ab.max())
        if pk > peak:
            peak = pk
        clipped += int(np.sum(ab >= 32767))
    mean = sum_s / n
    var = max(0.0, (sum_s2 / n) - mean * mean)
    return float(np.sqrt(var)), peak, clipped


def _local_scale(r, win=512, step=32):
    from numpy.lib.stride_tricks import sliding_window_view
    n = len(r)
    if n < win:
        med, mad = _fast_median_mad(r)
        return np.full(n, max(mad, 0.7))
    pad = win // 2
    padded = np.pad(np.abs(r), pad, mode="reflect")
    windows = sliding_window_view(padded, win)[::step]
    meds = np.partition(windows, win // 2, axis=1)[:, win // 2] * 1.4826
    grid = np.arange(len(meds)) * step
    loc_sc = np.interp(np.arange(n), grid, meds)
    return np.maximum(loc_sc, 0.7)


def detect_glitches(data, order=28, block=4096):
    """Detect USB audio stream defects in a stereo int16 array in bounded O(block) memory.
    Returns (priming_frames, events) where each event is (frame_idx, kind, size) and
    kind is one of: 'lost', 'repeat', 'zero', 'jump'.
    """
    from numpy.lib.stride_tricks import sliding_window_view
    n = len(data)
    if n <= order * 2 + 4:
        return 0, []
    priming = _find_priming(data)
    m_len = n - priming - 1
    if m_len <= order * 2 + 4:
        return priming, []

    events = []
    skip_until = 0
    reg_idx = np.arange(order)

    for b_start in range(order, m_len, block):
        b_end = min(m_len, b_start + block)
        if b_end - b_start <= order:
            break

        i0 = priming + b_start - order
        i1 = min(n, priming + b_end + order + 1)
        sub = data[i0:i1]
        sub0 = sub[:, 0].astype(np.float64)
        if np.array_equal(sub[:, 0], sub[:, 1]):
            s_blk = sub0
        else:
            s_blk = 0.6 * sub0 + 0.4 * sub[:, 1].astype(np.float64)
        blk = np.diff(s_blk)

        w = sliding_window_view(blk, order + 1)
        X_f = w[:, :-1]
        y_f = w[:, -1]
        X_b = w[:, 1:]
        y_b = w[:, 0]

        gram_f = X_f.T @ X_f
        gram_f[reg_idx, reg_idx] += 1e-6
        coef_f = np.linalg.solve(gram_f, X_f.T @ y_f)
        r_f = y_f - X_f @ coef_f

        gram_b = X_b.T @ X_b
        gram_b[reg_idx, reg_idx] += 1e-6
        coef_b = np.linalg.solve(gram_b, X_b.T @ y_b)
        r_b = y_b - X_b @ coef_b

        sc_f = _local_scale(r_f)
        sc_b = _local_scale(r_b)

        zf = np.abs(r_f) / sc_f
        zb = np.abs(r_b) / sc_b

        blk_rms = float(np.std(s_blk))

        # In active audio (blk_rms > 3.0), any zero run >= 4 frames where previous sample was active (> 10 LSB) is a stream defect
        if blk_rms > 3.0:
            z_mask = (sub[order:, 0] == 0) & (sub[order:, 1] == 0)
            for z_start, z_len in _runs(z_mask):
                if z_len >= 4 and z_start > 0 and (abs(int(sub[order + z_start - 1, 0])) > 10 or abs(int(sub[order + z_start - 1, 1])) > 10):
                    p_z = b_start + z_start
                    if p_z >= skip_until:
                        zf_pos = priming + p_z
                        full_z = 0
                        while zf_pos + full_z < n and data[zf_pos + full_z, 0] == 0 and data[zf_pos + full_z, 1] == 0:
                            full_z += 1
                        events.append((zf_pos, "zero", full_z))
                        skip_until = p_z + full_z + order + 2

        # In +-1 LSB silence (0.3 < blk_rms <= 3.0), linear prediction residuals on
        # zero-runs or repeated slices are <= 2 LSB, so scan directly for >= 16-frame
        # all-zero runs or exact slice repeats.
        if 0.3 < blk_rms <= 3.0 and float(np.std(blk)) > 0.7:
            z_mask = (sub[order:, 0] == 0) & (sub[order:, 1] == 0)
            for z_start, z_len in _runs(z_mask):
                if z_len >= 16 and z_start > 0:
                    p_z = b_start + z_start
                    if p_z >= skip_until:
                        zf_pos = priming + p_z
                        full_z = 0
                        while zf_pos + full_z < n and data[zf_pos + full_z, 0] == 0 and data[zf_pos + full_z, 1] == 0:
                            full_z += 1
                        events.append((zf_pos, "zero", full_z))
                        skip_until = p_z + full_z + order + 2
            cur_sub = sub[order:]
            for L in (1, 8, 16, 20, 24, 32, 44, 45):
                if priming + b_start >= L and len(cur_sub) > 16:
                    prev_sub = data[priming + b_start - L:i1 - L]
                    eq = (cur_sub[:, 0] == prev_sub[:, 0]) & (cur_sub[:, 1] == prev_sub[:, 1])
                    nz = (cur_sub[:, 0] != 0) | (cur_sub[:, 1] != 0)
                    for r_start, r_len in _runs(eq):
                        if r_len >= 16 and np.any(nz[r_start:r_start + r_len]):
                            p_r = b_start + r_start
                            if p_r >= skip_until:
                                rf_pos = priming + p_r
                                full_r = 0
                                while rf_pos + full_r < n and data[rf_pos + full_r, 0] == data[rf_pos - L + full_r, 0] and data[rf_pos + full_r, 1] == data[rf_pos - L + full_r, 1]:
                                    full_r += 1
                                events.append((rf_pos, "repeat", full_r))
                                skip_until = p_r + full_r + order + 2

        if np.max(zf) < 6.0 or np.max(zb) < 6.0:
            continue

        m_start = max(order + 6, order)
        m_end = min(len(r_b) - 8, b_end - b_start + order)
        if m_end <= m_start:
            continue
        m_arr = np.arange(m_start, m_end)
        kf_arr = m_arr - order
        raw_cands = m_arr[(zf[kf_arr] >= 6.0) | (zb[m_arr] >= 6.0)]

        passed = []
        for m in raw_cands:
            kf = m - order
            zf_pk = max(zf[kf - 1 : kf + 3])
            zb_pk = max(zb[m - 1 : m + 3])
            if min(zf_pk, zb_pk) < 9.5:
                continue

            zf_pre = max(zf[kf - 5 : kf - 1])
            zb_post = max(zb[m + 3 : m + 7])
            sc_f_val = zf_pk / max(1.0, zf_pre)
            sc_b_val = zb_pk / max(1.0, zb_post)
            score = min(sc_f_val, sc_b_val)
            if score >= 6.0:
                passed.append(m)

        if not passed:
            continue

        # Group adjacent candidate frames within 4 samples into clusters
        clusters = []
        cur_clust = [passed[0]]
        for m in passed[1:]:
            if m <= cur_clust[-1] + 4:
                cur_clust.append(m)
            else:
                clusters.append(cur_clust)
                cur_clust = [m]
        clusters.append(cur_clust)

        for clust in clusters:
            best_m = max(clust, key=lambda m: zf[m - order] + zb[m])
            kf = best_m - order
            p = b_start + kf + 1
            if p < skip_until:
                continue

            g_frame = priming + p
            loc_start = max(priming, g_frame - 128)
            loc_end = min(n, g_frame + 128)
            loc_sub = data[loc_start:loc_end]
            if np.array_equal(loc_sub[:, 0], loc_sub[:, 1]):
                s_loc = loc_sub[:, 0].astype(np.float64)
            else:
                s_loc = 0.6 * loc_sub[:, 0].astype(np.float64) + 0.4 * loc_sub[:, 1].astype(np.float64)
            lp = g_frame - loc_start

            # 1. Check for inserted zero frame(s) starting in [g_frame-2 .. g_frame+2]
            zero_found = None
            if blk_rms > 3.0:
                for dz in range(-2, 3):
                    zf_f = g_frame + dz
                    lp_z = lp + dz
                    if priming < zf_f < n and 1 <= lp_z < len(s_loc):
                        if data[zf_f, 0] == 0 and data[zf_f, 1] == 0 and (data[zf_f - 1, 0] != 0 or data[zf_f - 1, 1] != 0):
                            zlen = 0
                            while zf_f + zlen < n and data[zf_f + zlen, 0] == 0 and data[zf_f + zlen, 1] == 0:
                                zlen += 1
                            if zlen >= 4 or abs(s_loc[lp_z - 1]) > 6.0:
                                zero_found = (zf_f, "zero", zlen, (zf_f - priming) + zlen + order + 2)
                                break
            if zero_found is not None:
                events.append(zero_found[:3])
                skip_until = zero_found[3]
                continue

            # 2. Check for repeated frame(s) starting in [g_frame-2 .. g_frame+2]
            rep_found = None
            if blk_rms > 3.0:
                for drp in range(-2, 3):
                    rp = lp + drp
                    if 2 <= rp < len(s_loc) - 2:
                        for L in range(2, min(96, rp)):
                            if s_loc[rp] == s_loc[rp - L] and s_loc[rp + 1] == s_loc[rp - L + 1]:
                                while rp > L and s_loc[rp - 1] == s_loc[rp - 1 - L]:
                                    rp -= 1
                                rf_f = loc_start + rp
                                mlen = 0
                                while rf_f + mlen < n and data[rf_f + mlen, 0] == data[rf_f - L + mlen, 0] and data[rf_f + mlen, 1] == data[rf_f - L + mlen, 1]:
                                    mlen += 1
                                if mlen >= 2:
                                    rep_found = (rf_f, "repeat", mlen, (rf_f - priming) + mlen + order + 2)
                                    break
                    if rep_found is not None:
                        break
                if rep_found is None:
                    for drp in (0, -1, 1, 2, -2):
                        rp = lp + drp
                        if 2 <= rp < len(s_loc) - 1 and s_loc[rp] == s_loc[rp - 1]:
                            prev_step = abs(s_loc[rp - 1] - s_loc[rp - 2])
                            next_step = abs(s_loc[rp + 1] - s_loc[rp])
                            if prev_step > max(2.5 * sc_f[kf], 10.0) and prev_step < 4.0 * max(next_step, 1.0):
                                rf_f = loc_start + rp
                                hlen = 0
                                while rf_f + hlen < n and data[rf_f + hlen, 0] == data[rf_f - 1, 0] and data[rf_f + hlen, 1] == data[rf_f - 1, 1]:
                                    hlen += 1
                                rep_found = (rf_f, "repeat", hlen, (rf_f - priming) + hlen + order + 2)
                                break
            if rep_found is not None:
                events.append(rep_found[:3])
                skip_until = rep_found[3]
                continue

            # 3. Distinguish 'jump' vs 'lost'
            is_jump = False
            best_g_frame = g_frame
            if blk_rms <= 3.0:
                is_jump = True
            elif 2 <= lp < len(s_loc) - 2:
                for dj in (0, -1, 1):
                    cur_lp = lp + dj
                    if 2 <= cur_lp < len(s_loc) - 2:
                        slope_before = s_loc[cur_lp - 1] - s_loc[cur_lp - 2]
                        slope_after = s_loc[cur_lp + 2] - s_loc[cur_lp + 1]
                        interp_err_1 = abs((s_loc[cur_lp + 1] - s_loc[cur_lp - 1]) - (slope_before + slope_after))
                        step_err = max(abs(s_loc[cur_lp] - s_loc[cur_lp - 1] - slope_before), abs(s_loc[cur_lp + 1] - s_loc[cur_lp] - slope_after))
                        jump_mag = abs(s_loc[cur_lp] - 0.5 * (s_loc[cur_lp - 1] + s_loc[cur_lp + 1]))
                        delta1 = (s_loc[cur_lp] - s_loc[cur_lp - 1]) - slope_before
                        delta2 = (s_loc[cur_lp + 1] - s_loc[cur_lp]) - slope_after
                        if delta1 * delta2 < 0 and jump_mag > max(2.0 * sc_f[kf], 10.0) and step_err > 3.0 * max(interp_err_1, sc_f[kf] * 2.0):
                            is_jump = True
                            best_g_frame = loc_start + cur_lp
                            break

            kind = "jump" if is_jump else "lost"
            events.append((best_g_frame, kind, 1))
            skip_until = p + order + 4

    return priming, events


EVENT_TYPES = (
    ("lost", "lost frames"),
    ("repeat", "repeated frames"),
    ("zero", "inserted zero runs"),
    ("jump", "sample jumps"),
)


QUIET_RMS = 50   # LSB, about -56 dBFS: below this the defect check is not meaningful


def analyse_audio(data):
    n = len(data)
    lines = ["audio take: %d frames (%.2f s)" % (n, n / FS)]
    for ch, name in ((0, "L"), (1, "R")):
        rms, peak, clipped = _channel_level(data, ch)
        lines.append("%s: rms %.0f (%.1f dBFS), peak %d, clipped frames %d" % (
            name, rms, 20 * np.log10(max(rms, 1e-9) / 32768), peak, clipped))
    loudest = max(_channel_level(data, ch)[0] for ch in (0, 1))
    if loudest < QUIET_RMS:
        # A few LSB of noise has no structure to predict: the detector would
        # flag noise as repeats and losses (2026-10-16 tap2 takes at rms 4).
        lines.append("defect check skipped: signal too quiet (rms %.0f < %d LSB); "
                     "plug in or play the guitar" % (loudest, QUIET_RMS))
        return lines
    priming, events = detect_glitches(data)
    lines.append("leading zero (priming) frames: %d" % priming)
    for kind, label in EVENT_TYPES:
        pos = [e[0] for e in events if e[1] == kind]
        sp = (" " + _spacing(pos)) if len(pos) > 1 else ""
        lines.append("%s: %d, positions %s%s" % (label, len(pos), pos[:10], sp))
    mins = n / (FS * 60.0)
    min_str = "%d" % round(mins) if mins >= 1.0 and abs(mins - round(mins)) < 1e-2 else "%.2f" % mins
    lines.append("%d defects in %s min" % (len(events), min_str))
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
