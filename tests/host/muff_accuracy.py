"""Score the CF Muff candidate (effects/common/muff_g1.h) against the 32x
reference (tests/host/muff_accuracy.cpp, model tests/host/muff_ref.h).
Prints a PASS/FAIL verdict.

    python tests/host/muff_accuracy.py [folder] [cand|mob]

`mob` scores Comet Flower's own shipping mobile core (4x, 2048-cell tables)
instead of the candidate: the fairness check that the gate is reachable.

Per test (sine f0, amplitude, Sustain, Tone): harmonic amplitudes of the
candidate vs the band-limited reference, and the candidate's alias energy
(in-band energy that is not a harmonic, relative to the harmonic energy).

The reference is rendered at 32x and 64x (double-precision linear filters,
65536-cell clip tables); all 54 tests converge. Comet Flower's own shipping
mobile core (mob_*: 4x, 2048 cells) measured against it: H1 within 0.07 dB,
harmonics within 3.34 dB, alias -37.6 dB at worst (3.7 kHz input).

Pass criteria (the gate) for the candidate, per test:
  finite output; H1 within max(0.5, mobile + 0.5) dB of the reference;
  worst harmonic (within 30 dB of H1) within mobile + 0.5 dB;
  alias at most max(mobile + 3, -60) dB (-60 dB = Comet Flower's audibility
  line: below it, matching the mobile core's even lower alias is not required).
i.e. at least as accurate as Comet Flower's mobile Muff, everywhere.
Stretch (reported): harmonics within 1.5 dB and alias <= -50 dB on every test.
Written by Claude (from the CF RAT scorer); do not edit as part of the model work.
"""
import glob
import sys
from pathlib import Path

import numpy as np

D = Path(__file__).resolve().parents[2] / "build" / "host" / (sys.argv[1] if len(sys.argv) > 1 else "muff")
MODEL = sys.argv[2] if len(sys.argv) > 2 else "cand"
SR = 44100
H1_TOL, H_TOL, H_RANGE_DB, ALIAS_MAX, ALIAS_TARGET = 0.5, 1.5, 30.0, -45.0, -55.0
HARD_H1_TOL, HARD_H_TOL = 1.5, 3.0
CONV_TOL, LOOSE_H1 = 0.25, 3.0


def herr(ha, hb):
    n = min(len(ha), len(hb))
    sig = hb[:n] > hb[0] * 10 ** (-H_RANGE_DB / 10)
    return 10 * np.log10(np.maximum(ha[:n][sig], 1e-30) / hb[:n][sig])


def decimate_ref(x, os=32):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / (SR * os))
    X[f > 20000] = 0
    return np.fft.irfft(X, len(x))[::os]


def analyse(y, f0):
    y = y[SR // 4:]
    w = np.blackman(len(y))
    s = np.abs(np.fft.rfft(y * w)) ** 2
    f = np.fft.rfftfreq(len(y), 1 / SR)
    harm, mask = [], (f < 20)
    for k in range(1, int(20000 // f0) + 1):
        m = np.abs(f - k * f0) < 12
        harm.append(s[m].sum())
        mask |= m
    band = f < 20000
    alias = s[band & ~mask].sum() / max(sum(harm), 1e-30)
    return np.array(harm), 10 * np.log10(alias + 1e-30)


def metrics(path, hr):
    y = np.fromfile(path, dtype=np.float32).astype(np.float64)
    if not np.all(np.isfinite(y)):
        return None
    hc, al = analyse(y, f0)
    d = herr(hc, hr)
    return abs(d[0]), np.abs(d).max(), al


refs = sorted(glob.glob(str(D / "ref_*.f32")))
if not refs:
    sys.exit("no reference outputs in %s: run tests/host/build_muff_accuracy.bat first" % D)
fails, stretch_fail, beat = [], 0, 0
wh1 = wh = 0.0
wal = -999.0
print(f"{'test':22s} {'H1 dB':>6s} {'maxH':>6s} {'alias':>7s}   {'mobile: H1':>10s} {'maxH':>6s} {'alias':>7s}")
for rf in refs:
    tag = Path(rf).stem[4:]
    f0 = float(tag.split("_")[0][1:])
    hr, _ = analyse(decimate_ref(np.fromfile(rf, dtype=np.float32).astype(np.float64), 32), f0)
    mob = metrics(D / f"mob_{tag}.f32", hr)
    cand = metrics(D / f"{MODEL}_{tag}.f32", hr)
    if cand is None:
        fails.append(f"{tag}: non-finite output")
        print(f"{tag:22s} non-finite output")
        continue
    h1, mh, al = cand
    wh1, wh, wal = max(wh1, h1), max(wh, mh), max(wal, al)
    flag = []
    if MODEL != "mob":
        if h1 > max(0.5, mob[0] + 0.5): flag.append("H1")
        if mh > mob[1] + 0.5: flag.append("harm")
        if al > max(mob[2] + 3.0, -60.0): flag.append("alias")
        if mh < mob[1] and al < mob[2]: beat += 1
    if mh > 1.5 or al > -50.0: stretch_fail += 1
    if flag: fails.append(f"{tag}: {', '.join(flag)}")
    print(f"{tag:22s} {h1:6.2f} {mh:6.2f} {al:7.1f}   {mob[0]:10.2f} {mob[1]:6.2f} {mob[2]:7.1f}  {' '.join(flag)}")

print("")
print(f"worst: H1 {wh1:.2f} dB, harmonics {wh:.2f} dB, alias {wal:.1f} dB "
      f"(mobile core: 0.07 / 3.34 / -37.6)")
if MODEL != "mob":
    print(f"better than the mobile core (harmonics AND alias) on {beat} of {len(refs)} tests")
print(f"STRETCH: {len(refs) - stretch_fail} of {len(refs)} tests within 1.5 dB harmonics and -50 dB alias")
if MODEL == "mob":
    print("(scored the mobile core itself: no gate)")
    sys.exit(0)
print("ACCURACY: PASS" if not fails else f"ACCURACY: FAIL ({len(fails)} of {len(refs)} tests)")
sys.exit(0 if not fails else 1)
