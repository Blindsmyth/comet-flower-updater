#!/usr/bin/env python3
"""Decode the CF diagnostics' tone code (CF MEMPRB, CF RATT, CF 808T) from a recording.

  python tools/decode_memprobe.py <recording.wav> [channel]

channel: 0 = left, 1 = right (default 1: the VPE takes carry the pedal on the
right channel of *_dry.wav). Finds each 3 kHz sync tone, reads the 12 x 32
bits after it (1 kHz = 0, 2 kHz = 1, 20 ms each; Goertzel over the middle
of each bit), checks the magic word and the XOR check word, and prints every
frame that decodes cleanly, with what each address range means on the C6745.
"""
import struct
import sys

import numpy as np

SR = 44100
SYNC, BIT, WORDS = 6624, 882, 12   # 6615 in the first MEMPRB build
NAMES = ["magic", "code (this function)", "table (const_blob)", "state (instance[2])",
         "knob table (instance[1])", "audio buffer (ctx[1])", "stack local",
         "instance pointer", "cycles: 128 table reads, first call",
         "cycles: 128 table reads, now", "cycles: 128 stack reads", "check (XOR)"]


MAGICS = (0xCF00A55A, 0xCF0071ED)


def show_timing(w):
    tag = w[1].to_bytes(4, "big").decode("ascii", "replace").strip()
    n = max(w[2], 1)
    cold, warm = w[3] / n, w[6] / n
    print("  timing diagnostic '%s': %d blocks in this frame" % (tag, w[2]))
    mm = lambda *v: ("  min %8d  max %8d" % v) if any(v) else ""
    print("  cold pass (cache as the firmware left it): mean %8.0f%s cycles/block" % (cold, mm(w[4], w[5])))
    print("  warm pass (code and data just used):       mean %8.0f%s" % (warm, ("  min %8d" % w[7]) if w[7] else ""))
    print("  refill cost (cold - warm): %.0f cycles/block (%.0f%% of the cold pass)"
          % (cold - warm, 100.0 * (cold - warm) / max(cold, 1)))
    print("  code address 0x%08x  %s" % (w[8], region(w[8])))
    if w[10]:
        period = w[9] / w[10]
        print("  block period: %.0f cycles = the whole DSP budget per 16-sample block" % period)
        print("  -> DSP clock %.1f MHz (period x 44100 / 16); this kernel cold = %.1f%% of the block"
              % (period * 44100 / 16 / 1e6, 100.0 * cold / period))


def read_wav(path):
    d = open(path, "rb").read()
    i, fmt, data = 12, None, None
    while i < len(d):
        cid, n = d[i:i + 4], struct.unpack_from("<I", d, i + 4)[0]
        if cid == b"fmt ":
            fmt = struct.unpack_from("<HHIIHH", d, i + 8)
        elif cid == b"data":
            data = d[i + 8:i + 8 + n]
            break
        i += 8 + n + (n & 1)
    tag, ch, sr, _, _, bits = fmt
    dt = {(3, 32): "<f4", (1, 16): "<i2", (1, 32): "<i4"}[(tag if tag != 0xFFFE else 1, bits)]
    x = np.frombuffer(data[:len(data) - len(data) % (ch * bits // 8)], dt).reshape(-1, ch)
    return x.astype(float), sr


def power(seg, f):
    n = np.arange(len(seg))
    return abs(np.dot(seg, np.exp(-2j * np.pi * f * n / SR))) ** 2


def region(a):
    if 0x11800000 <= a < 0x11840000 or 0x00800000 <= a < 0x00840000:
        return "on-chip L2 RAM (fast)"
    if 0x11F00000 <= a < 0x11F08000 or 0x00F00000 <= a < 0x00F08000:
        return "on-chip L1D RAM (fastest)"
    if 0xC0000000 <= a < 0xC0800000:
        return "external SDRAM (slow; cached only if its MAR bit is set)"
    return "?"


def decode(x):
    # locate sync tones: 3 kHz energy over 10 ms windows
    win = 441
    nwin = len(x) // win
    r3 = np.array([power(x[k * win:(k + 1) * win], 3000) for k in range(nwin)])
    r1 = np.array([power(x[k * win:(k + 1) * win], 1000) + power(x[k * win:(k + 1) * win], 2000)
                   for k in range(nwin)])
    is3 = (r3 > 4 * r1) & (r3 > 0.05 * r3.max())   # 3 kHz dominant and loud
    frames, k = [], 0
    while k < nwin:
        if is3[k]:
            j = k
            while j < nwin and is3[j]:
                j += 1
            # refine the sync end to the sample: last 3 kHz window end
            end = j * win
            # search +-1 window for the best bit alignment
            best = None
            for off in range(-win, win + 1, 21):
                start = end + off
                if start < 0 or start + WORDS * 32 * BIT > len(x):
                    continue
                bits, margin = [], 0.0
                for b in range(WORDS * 32):
                    seg = x[start + b * BIT + BIT // 5:start + (b + 1) * BIT - BIT // 5]
                    p1, p2 = power(seg, 1000), power(seg, 2000)
                    bits.append(1 if p2 > p1 else 0)
                    margin += abs(np.log10((p2 + 1e-20) / (p1 + 1e-20)))
                if best is None or margin > best[0]:
                    best = (margin, bits)
                if off == -win:  # coarse only
                    pass
            if best:
                bits = best[1]
                w = [int("".join(map(str, bits[i * 32:(i + 1) * 32])), 2) for i in range(WORDS)]
                chk = 0
                for v in w[:11]:
                    chk ^= v
                frames.append((k * win / SR, w, w[0] in MAGICS and chk == w[11]))
            k = j + (WORDS * 32 * BIT) // win
        else:
            k += 1
    return frames


def stitch(x, frames_found):
    """No complete frame: join the end of one frame (before a sync) with the
    start of the next (after it). Addresses repeat, so the frame's own check
    word validates the join. Needs one sync with >= 2.3 s of tone each side."""
    win = 441
    nwin = len(x) // win
    r3 = np.array([power(x[k * win:(k + 1) * win], 3000) for k in range(nwin)])
    r1 = np.array([power(x[k * win:(k + 1) * win], 1000) + power(x[k * win:(k + 1) * win], 2000)
                   for k in range(nwin)])
    on = np.where((r3 > 4 * r1) & (r3 > 0.05 * r3.max()))[0]
    if len(on) == 0:
        return None
    s0 = on[0] * win
    total = WORDS * 32
    loud = np.where((r1 + r3) > 0.01 * (r1 + r3).max())[0]   # where the tone is
    t_first, t_last = loud[0] * win, (loud[-1] + 1) * win
    after = min(total, (t_last - (s0 + SYNC)) // BIT - 1)
    before = min(total, (s0 - t_first) // BIT - 1)
    if after + before < total:
        return None

    def bits_at(start, n):
        out, marg = [], []
        for b in range(n):
            seg = x[start + b * BIT + BIT // 5:start + (b + 1) * BIT - BIT // 5]
            p1, p2 = power(seg, 1000), power(seg, 2000)
            out.append(1 if p2 > p1 else 0)
            marg.append(abs(np.log10((p2 + 1e-20) / (p1 + 1e-20))))
        return out, np.median(marg)

    def best(base_fn, n):
        cands = [bits_at(base_fn(off), n) + (off,) for off in range(-win, win + 1, 20)
                 if base_fn(off) >= 0 and base_fn(off) + n * BIT <= len(x)]
        return max(cands, key=lambda c: c[1])[0]

    b_after = best(lambda off: s0 + SYNC + off, after)
    b_before = best(lambda off: s0 + off - before * BIT, before)
    full = b_after[:total - before] + b_before
    w = [int("".join(map(str, full[i * 32:(i + 1) * 32])), 2) for i in range(WORDS)]
    chk = 0
    for v in w[:11]:
        chk ^= v
    return (s0 / SR, w, w[0] in MAGICS and chk == w[11])


def main(a):
    if not a:
        sys.exit(__doc__)
    x, sr = read_wav(a[0])
    if sr != SR:
        sys.exit("expected 44.1 kHz, got %d" % sr)
    ch = int(a[1]) if len(a) > 1 else 1
    sig = x[:, min(ch, x.shape[1] - 1)]
    frames = decode(sig)
    good = [f for f in frames if f[2]]
    if not good:
        st = stitch(sig, frames)
        if st:
            print("no complete frame; stitched the frames either side of the sync at %.2f s" % st[0])
            frames = [st]
            good = [st] if st[2] else []
    print("%d frames found, %d decode cleanly" % (len(frames), len(good)))
    for t, w, ok in frames:
        print("\nframe at %.2f s: %s" % (t, "OK" if ok else "BAD (magic/check mismatch)"))
        if not ok:
            continue
        if w[0] == 0xCF0071ED:
            show_timing(w)
            continue
        for i, v in enumerate(w):
            extra = ""
            if 1 <= i <= 7:
                extra = "  " + region(v)
            elif 8 <= i <= 10:
                extra = "  (%.1f cycles per read)" % (v / 128.0)
            print("  %2d %-36s 0x%08x %s" % (i, NAMES[i], v, extra))


if __name__ == "__main__":
    main(sys.argv[1:])
