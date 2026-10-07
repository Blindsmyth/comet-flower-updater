"""Score the CF RAT candidate (effects/common/rat_g1.h) against the 32x
reference (tests/host/rat_accuracy.cpp). Prints a PASS/FAIL verdict.

Per test (sine f0, amplitude, Distortion, Filter): harmonic amplitudes of the
candidate vs the band-limited reference, and the candidate's alias energy
(in-band energy that is not a harmonic, relative to the harmonic energy).

The reference is rendered at 32x and 64x. A test is CONVERGED when the two
agree (every harmonic within 30 dB of H1 within 0.25 dB); only then is it a
trustworthy target.

Pass criteria (the gate):
  every test: finite output;
  converged gentle tests: H1 within 0.5 dB of the reference, every harmonic
    within 30 dB of H1 within 1.5 dB;
  converged hard tests: H1 within 1.5 dB, harmonics within 3 dB;
  unconverged tests (deep slew limiting): H1 within 3 dB of the 64x reference;
  gentle tests (Distortion <= 5 and input <= 0.25 V): alias <= -45 dB
    (target -55 dB).
Stretch score (reported, not gated): the worst alias over the "hard" tests
(Distortion 10, or 0.7 V input). A straightforward chain at 8x scores about
+22 dB there (alias louder than the signal at 3.7 kHz, Distortion 10),
because the hard slew limiter's corners alias and the 473 Hz op-amp
low-pass keeps the low aliases while removing the harmonics. Lower is better;
-40 dB would be excellent.
Written by Claude; do not edit as part of the model work.
"""
import glob
import sys
from pathlib import Path

import numpy as np

D = Path(__file__).resolve().parents[2] / "build" / "host" / (sys.argv[1] if len(sys.argv) > 1 else "rat")
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


refs = sorted(glob.glob(str(D / "ref_*.f32")))
if not refs:
    sys.exit("no reference outputs in %s: run tests/host/build_rat_accuracy.bat first" % D)
fails, worst_h, worst_h1, worst_alias, nconv, worst_hard = [], 0.0, 0.0, -999.0, 0, -999.0
print(f"{'test':22s} {'conv':>4s} {'H1 dB':>7s} {'maxH dB':>8s} {'alias dB':>9s}")
for rf in refs:
    tag = Path(rf).stem[4:]
    f0 = float(tag.split("_")[0][1:])
    hr, _ = analyse(decimate_ref(np.fromfile(rf, dtype=np.float32).astype(np.float64), 32), f0)
    h64, _ = analyse(decimate_ref(np.fromfile(D / f"ref64_{tag}.f32", dtype=np.float32).astype(np.float64), 64), f0)
    conv = np.abs(herr(hr, h64)).max() <= CONV_TOL
    nconv += conv
    cand = np.fromfile(D / f"cand_{tag}.f32", dtype=np.float32).astype(np.float64)
    if not np.all(np.isfinite(cand)):
        fails.append(f"{tag}: non-finite output")
        print(f"{tag:22s} non-finite output")
        continue
    hc, al = analyse(cand, f0)
    flag = []
    parts = tag.split("_")
    gentle = int(parts[2][1:]) <= 5 and int(parts[1][1:]) <= 25
    t1, th = (H1_TOL, H_TOL) if gentle else (HARD_H1_TOL, HARD_H_TOL)
    if conv:
        d = herr(hc, hr)
        h1, mh = d[0], np.abs(d).max()
        worst_h1, worst_h = max(worst_h1, abs(h1)), max(worst_h, mh)
        if abs(h1) > t1: flag.append("H1")
        if mh > th: flag.append("harm")
    else:
        h1 = herr(hc, h64)[0]
        mh = float("nan")
        if abs(h1) > LOOSE_H1: flag.append("H1(loose)")
    if gentle:
        worst_alias = max(worst_alias, al)
        if al > ALIAS_MAX: flag.append("alias")
    else:
        worst_hard = max(worst_hard, al)
    if flag: fails.append(f"{tag}: {', '.join(flag)}")
    print(f"{tag:22s} {'yes' if conv else 'no':>4s} {h1:7.2f} {mh:8.2f} {al:9.1f} {' '.join(flag)}")

print("")
print(f"{nconv} of {len(refs)} tests converged (strict); worst on those: H1 {worst_h1:.2f} dB, "
      f"harmonics {worst_h:.2f} dB (limits gentle {H1_TOL}/{H_TOL}, hard {HARD_H1_TOL}/{HARD_H_TOL}); "
      f"worst gentle-test alias {worst_alias:.1f} dB (limit {ALIAS_MAX}, target {ALIAS_TARGET})")
print(f"STRETCH: worst hard-test alias {worst_hard:.1f} dB (naive 8x chain: about +22; lower is better)")
print("ACCURACY: PASS" if not fails else f"ACCURACY: FAIL ({len(fails)} of {len(refs)} tests)")
sys.exit(0 if not fails else 1)
