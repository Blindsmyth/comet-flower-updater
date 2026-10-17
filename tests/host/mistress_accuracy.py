"""Score the CF Mistress candidate (effects/common/mistress_g1.h) against the
double-precision reference (tests/host/mistress_accuracy.cpp). Prints a
PASS/FAIL verdict.

Per test (a sine, a guitar-like pluck, a 200-3000 Hz chirp, or an 8 kHz probe
tone, at a grid of Rate/Range/Color settings, plus a separate Matrix-mode
grid): RESIDUAL dB = 20*log10(rms(candidate - reference) / rms(reference)),
over the whole test with the first 0.25 s (filter/LFO/delay-line settling)
discarded. Both the reference and the candidate run at 44.1 kHz with zero
added latency and a deterministic LFO start phase (no parameter smoothing in
this bench), so a correct port lines up with the reference sample-for-sample.

THREE THRESHOLD TIERS, not one -- found necessary by calibration (below).
Full-depth modulation at a non-trivial Rate and Color pushes the BBD feedback
loop (delay -> CTI low-pass -> ADAA clip -> back into the delay) close enough
to its stability edge that float-vs-double ROUNDING ALONE -- not a port
defect -- makes the candidate and the reference diverge by a few tens of dB
after under a second, independently of whether the delay read uses Lagrange
or linear interpolation (measured: both scored -37.6 dB on the single worst
case, chirp at Rate 1 Hz/Range 1.0/Color 0.9). A single global threshold
tight enough to catch a real interpolation defect would therefore also fail
an honest port on that same case. So:
  - INTERP tests (tag contains "sine8000_r001": an 8 kHz probe tone at the
    slowest Rate, added specifically to isolate interpolation quality from
    the feedback-loop sensitivity above): RESIDUAL <= -55 dB. This is the
    tier that actually catches the brief's suggested "linear instead of
    Lagrange" degradation -- see calibration.
  - LOOSE tests (full Range AND Rate >= 1 Hz: the feedback-loop-sensitive
    corner described above): RESIDUAL <= -30 dB.
  - everything else (DEFAULT): RESIDUAL <= -40 dB.

Calibration (2026-10-17, this repository's tests/host/build_mistress_accuracy.bat
+ this scorer, run three times with different effects/common/mistress_g1.h
contents -- see docs/helpers/AGY_MISTRESS.md for the transcripts):
  - the double reference re-typed into float, same structure, same Lagrange
    3rd-order interpolation, no shortcuts ("self" check, a careful and
    correct port): worst INTERP-tier residual -64.0 dB, worst LOOSE-tier
    -37.6 dB, worst DEFAULT-tier -52.1 dB. PASSes every test.
  - the SAME port with the delay line's Lagrange 3rd-order read replaced by
    LINEAR interpolation (this kit's brief's suggested degradation): worst
    INTERP-tier residual -44.6 dB (fails the -55 dB tier on all 6 of its
    tests), worst LOOSE-tier -37.6 dB (identical to the honest port -- this
    is the feedback-loop floor, not an interpolation artefact), worst
    DEFAULT-tier -41.6 dB. 6 of 63 tests fail.
  - the shipped placeholder (identity): worst residual +1.0 dB (no flanging
    happened at all -- the "residual" is as loud as the reference signal).
    FAILs every test, as it must.

Pass criteria (the gate): every test finite; the tier threshold above on
every test.
Stretch score (reported, not gated): the worst RESIDUAL over the pluck/chirp
tests specifically (the most demanding signals: a decaying transient and a
swept tone, versus the steady sines). Lower is better; -40 dB or better means
the port's modulation is indistinguishable from the reference by ear.
Written by Claude; do not edit as part of the model work.
"""
import glob
import sys
from pathlib import Path

import numpy as np

D = Path(__file__).resolve().parents[2] / "build" / "host" / (sys.argv[1] if len(sys.argv) > 1 else "mistress")
SR = 44100
WARMUP = SR // 4
INTERP_MAX = -55.0
LOOSE_MAX = -30.0
DEFAULT_MAX = -40.0


def db(x, eps=1e-12):
    return 20.0 * np.log10(np.maximum(x, eps))


def tier(tag):
    parts = tag.split("_")
    if "sine8000" in tag and "r001" in parts:
        return "INTERP", INTERP_MAX
    is_full_depth = "d10" in parts
    is_fast = any(p in ("r010", "r040") for p in parts)
    if is_full_depth and is_fast:
        return "LOOSE", LOOSE_MAX
    return "DEFAULT", DEFAULT_MAX


refs = sorted(glob.glob(str(D / "ref_*.f32")))
if not refs:
    sys.exit("no reference outputs in %s: run tests/host/build_mistress_accuracy.bat first" % D)

fails = []
worst_by_tier = {"INTERP": -999.0, "LOOSE": -999.0, "DEFAULT": -999.0}
worst_demanding = -999.0
print(f"{'test':24s} {'tier':8s} {'residual dB':>12s}")
for rf in refs:
    tag = Path(rf).stem[4:]
    ref = np.fromfile(rf, dtype=np.float32).astype(np.float64)
    cand = np.fromfile(D / f"cand_{tag}.f32", dtype=np.float32).astype(np.float64)
    if not np.all(np.isfinite(cand)):
        fails.append(f"{tag}: non-finite output")
        print(f"{tag:24s} non-finite output")
        continue

    n = min(len(ref), len(cand))
    ref, cand = ref[WARMUP:n], cand[WARMUP:n]
    resid = cand - ref
    residual_db = db(np.sqrt(np.mean(resid * resid))) - db(np.sqrt(np.mean(ref * ref)) + 1e-12)
    tname, tmax = tier(tag)
    worst_by_tier[tname] = max(worst_by_tier[tname], residual_db)
    if tag.startswith("pluck") or tag.startswith("chirp"):
        worst_demanding = max(worst_demanding, residual_db)

    flag = []
    if residual_db > tmax: flag.append("residual")
    if flag: fails.append(f"{tag}: {', '.join(flag)}")
    print(f"{tag:24s} {tname:8s} {residual_db:12.1f} {' '.join(flag)}")

print("")
print(f"worst INTERP {worst_by_tier['INTERP']:.1f} dB (limit {INTERP_MAX}); "
      f"worst LOOSE {worst_by_tier['LOOSE']:.1f} dB (limit {LOOSE_MAX}); "
      f"worst DEFAULT {worst_by_tier['DEFAULT']:.1f} dB (limit {DEFAULT_MAX})")
print(f"STRETCH: worst pluck/chirp residual {worst_demanding:.1f} dB (lower is better)")
print("ACCURACY: PASS" if not fails else f"ACCURACY: FAIL ({len(fails)} of {len(refs)} tests)")
sys.exit(0 if not fails else 1)
