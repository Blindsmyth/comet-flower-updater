#!/usr/bin/env python3
"""Decode the CF diagnostics' tone code (CF MEMPRB, CF RATT, CF 808T, CF ClkT) from a recording.

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
        print("  mean TSCL delta between calls: %.0f counts (not yet a proven full-block budget)" % period)
        print("  -> equivalent %.1f MHz if TSCL runs continuously between 16-frame calls; kernel cold / delta = %.1f%%"
              % (period * 44100 / 16 / 1e6, 100.0 * cold / period))


FRAME_BLOCKS = 21582          # one tone-code frame = 345312 samples = 21582 blocks
OSC_HZ, BLOCK_S = 19.2e6, 16 / 44100.0


def clock_report(w):
    """CF ClkT frame (effects/clkt/clkt.c) -> dict of derived numbers."""
    n = max(w[2], 1)
    tscl, tim = w[3] / n, w[4] / n
    div = lambda b: (b & 0x1f) + 1 if b & 0x80 else 1
    prediv, postdiv, plldiv1 = div(w[6] & 0xff), div(w[6] >> 8 & 0xff), div(w[6] >> 16 & 0xff)
    pllctl = w[6] >> 24
    pll_on = bool(pllctl & 1)
    sysclk1 = OSC_HZ * ((w[5] & 0x1f) + 1) / prediv / postdiv / plldiv1 if pll_on else OSC_HZ / plldiv1
    budget = sysclk1 * BLOCK_S
    load = w[8] / FRAME_BLOCKS
    return {
        "deltas": w[2], "tscl_per_block": tscl, "tim_per_block": tim,
        "tim_expected": OSC_HZ * BLOCK_S, "tscl_hz_vs_osc": tscl / tim * OSC_HZ if tim else 0.0,
        "pllm": w[5], "pll_enabled": pll_on, "sysclk1_hz": sysclk1, "budget_cycles": budget,
        "pdccmd": w[7], "gempd": bool(w[7] >> 16 & 1), "load_iters": w[10],
        "load_cycles": load, "load_cycles_per_iter": load / w[10] if w[10] else 0.0,
        "tim_wrap": w[9], "busy_fraction": tscl / budget if budget else 0.0,
    }


def show_clock(w):
    r = clock_report(w)
    print("  clock diagnostic 'CLKT': %d block deltas in this frame" % r["deltas"])
    print("  TIM12 (19.2 MHz osc) per block: %.1f (expected %.1f)" % (r["tim_per_block"], r["tim_expected"]))
    print("  TSCL per block: %.0f  -> %.1f MHz of TSCL per oscillator second"
          % (r["tscl_per_block"], r["tscl_hz_vs_osc"] / 1e6))
    print("  PLLC0: PLLM %d, PLL %s -> SYSCLK1 %.1f MHz, %.0f cycles per block"
          % (r["pllm"], "on" if r["pll_enabled"] else "BYPASSED", r["sysclk1_hz"] / 1e6, r["budget_cycles"]))
    print("  PDCCMD 0x%08x (GEMPD %d)  TIM12 wrap %s" % (r["pdccmd"], r["gempd"],
                                                        r["tim_wrap"] or "2^32"))
    if r["load_iters"]:
        print("  load: %d iterations, %.0f TSCL cycles (%.2f per iteration)"
              % (r["load_iters"], r["load_cycles"], r["load_cycles_per_iter"]))
    print("  TSCL per block / SYSCLK1 budget = %.1f%%. Compare two Load settings: if TSCL per"
          % (100 * r["busy_fraction"]))
    print("  block rises by the load cycles, TSCL stops in IDLE and this is the busy share.")


CFM_WB0, CFM_WB_STEP = 0xC0226000, 0x81330      # slot work buffers (recon/14)
CFM_CODE0, CFM_CODE_STEP = 0xC01F4000, 0xA000    # slot code/const regions (recon/14)
TIM_PER_BLOCK = 19.2e6 * 16 / 44100              # 6966


def slot_of(a, base, step):
    k, r = divmod(a - base, step)
    return k if a >= base and 0 <= k < 5 else None


def cfm_report(w):
    """CF M5 / CF M2 probe page (effects/common/cfm_probe.h) -> dict."""
    if w[1] == 0x43464D30:                       # 'CFM0'
        blocks = w[3] / TIM_PER_BLOCK
        return {"page": 0, "calls": w[2], "blocks": blocks,
                "calls_per_block": w[2] / blocks if blocks else 0.0,
                "other_instance_calls": w[4], "instance": w[5], "coef": w[6], "state": w[7],
                "work_base": w[8], "work_size": w[9], "code": w[10],
                "work_slot": slot_of(w[8], CFM_WB0, CFM_WB_STEP),
                "code_slot": slot_of(w[10], CFM_CODE0, CFM_CODE_STEP)}
    knobs = [w[4 + k // 4] >> (24 - 8 * (k % 4)) & 0xFF for k in range(12)]
    return {"page": 1, "changed": [k for k in range(5) if w[2] >> k & 1],
            "zero": [k for k in range(5) if w[3] >> k & 1], "knobs": knobs, "sums": w[7:11]}


def show_cfm(w):
    r = cfm_report(w)
    if r["page"] == 0:
        print("  CF Master probe, page 0: %d calls over %.0f blocks = %.2f calls per block"
              % (r["calls"], r["blocks"], r["calls_per_block"]))
        print("  calls with a different instance than the first: %d" % r["other_instance_calls"])
        print("  instance 0x%08x  %s" % (r["instance"], region(r["instance"])))
        print("  coef     0x%08x  %s" % (r["coef"], region(r["coef"])))
        print("  state    0x%08x  %s" % (r["state"], region(r["state"])))
        print("  work buffer 0x%08x, %d bytes -> slot %s" % (r["work_base"], r["work_size"], r["work_slot"]))
        print("  code     0x%08x -> slot region %s" % (r["code"], r["code_slot"]))
    else:
        print("  CF Master probe, page 1: work buffers changed since the last page 1: %s"
              % (r["changed"] or "none"))
        print("  work buffers whose first 4 KB are all zero: %s" % (r["zero"] or "none"))
        print("  knobs 1-12 (x100): %s" % " ".join(str(v) for v in r["knobs"]))


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
        if w[0] == 0xCF0071ED and w[1] in (0x43464D30, 0x43464D31):
            show_cfm(w)
            continue
        if w[0] == 0xCF0071ED and w[1] == 0x434c4b54:
            show_clock(w)
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
