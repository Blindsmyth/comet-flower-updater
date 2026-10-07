#!/usr/bin/env python3
"""Decode the CF MEMPRB tone code from a recording.

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
SYNC, BIT, WORDS = 6615, 882, 12
NAMES = ["magic", "code (this function)", "table (const_blob)", "state (instance[2])",
         "knob table (instance[1])", "audio buffer (ctx[1])", "stack local",
         "instance pointer", "cycles: 128 table reads, first call",
         "cycles: 128 table reads, now", "cycles: 128 stack reads", "check (XOR)"]


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
                frames.append((k * win / SR, w, w[0] == 0xCF00A55A and chk == w[11]))
            k = j + (WORDS * 32 * BIT) // win
        else:
            k += 1
    return frames


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
    print("%d frames found, %d decode cleanly" % (len(frames), len(good)))
    for t, w, ok in frames:
        print("\nframe at %.2f s: %s" % (t, "OK" if ok else "BAD (magic/check mismatch)"))
        if not ok:
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
