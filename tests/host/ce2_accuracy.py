"""Score the CF CE-2 candidate (effects/common/ce2_g1.h) against the double-
precision reference (tests/host/ce2_accuracy.cpp). Prints a PASS/FAIL
verdict.

Per test (a sine, an 8 kHz probe tone, a guitar-like pluck, or a 200-3000 Hz
chirp, at a grid of Rate/Depth/Mix): RESIDUAL dB =
20*log10(rms(candidate - reference) / rms(reference)), over the whole test
with the first 0.25 s (filter/LFO/delay-line settling) discarded. Both the
reference and the candidate run at 44.1 kHz with zero added latency and a
deterministic LFO start phase (no parameter smoothing in this bench), so a
correct port lines up with the reference sample-for-sample.

THREE THRESHOLD TIERS, not one -- found necessary by calibration (below),
the same lesson the CF Mistress kit (also a Lagrange-interpolated BBD line)
already learned: the CE-2 has no feedback path (it is a straight write/
modulate/read chorus, unlike the Mistress's feedback loop), but at the
fastest Rate (the knob's top end, 3.5 Hz) combined with deep modulation, a
HONEST float port still diverges from the double reference by several tens
of dB purely from float-vs-double rounding, because a fast, deep sweep makes
the instantaneous comb-filter response change quickly enough that a tiny
timing difference becomes a real amplitude difference. This is NOT an
interpolation defect (an honest Lagrange port and a degraded linear-
interpolation port score almost identically there -- measured -27.2 dB vs
-27.1 dB on the worst case). So:
  - INTERP tests (tag contains "sine8000_r001": an 8 kHz probe tone at the
    slowest Rate, added specifically to isolate interpolation quality from
    the fast-sweep sensitivity above): RESIDUAL <= -50 dB. This is the tier
    that actually catches a linear-vs-Lagrange defect -- see calibration.
  - LOOSE tests (Rate at the knob's fastest setting, OR full Depth AND full
    Mix together: the fast-sweep-sensitive corner described above):
    RESIDUAL <= -25 dB.
  - everything else (DEFAULT): RESIDUAL <= -40 dB.

Calibration (2026-10-17, this repository's tests/host/build_ce2_accuracy.bat
+ this scorer, run three times with different effects/common/ce2_g1.h
contents -- see docs/helpers/AGY_CE2.md for the transcripts):
  - the double reference re-typed into float, same structure, same Lagrange
    3rd-order interpolation, no shortcuts ("self" check, a careful and
    correct port): worst INTERP-tier residual -57.3 dB, worst LOOSE-tier
    -27.2 dB, worst DEFAULT-tier (every other test) well clear of -40 dB.
    PASSes every test.
  - the SAME port with the delay line's Lagrange 3rd-order read replaced by
    LINEAR interpolation (the same degradation the CF Mistress kit uses,
    equally applicable here): worst INTERP-tier residual -44.8 dB (fails the
    -50 dB tier on most of its 6 tests), worst LOOSE-tier -27.1 dB (near-
    identical to the honest port -- confirms this tier is the fast-sweep
    floor, not an interpolation artefact).
  - the shipped placeholder (identity): worst residual +10.0 dB (no chorus
    happened at all). FAILs every test, as it must.

Pass criteria (the gate): every test finite; the tier threshold above on
every test.
Stretch score (reported, not gated): the worst RESIDUAL over the pluck/chirp
tests and the 8 kHz probe tone specifically (the signals most sensitive to
delay-interpolation and filter-coefficient accuracy). Lower is better; -45 dB
or better means the port's modulation is indistinguishable from the
reference by ear.
Written by Claude; do not edit as part of the model work.
"""
import glob
import sys
from pathlib import Path

import numpy as np

D = Path(__file__).resolve().parents[2] / "build" / "host" / (sys.argv[1] if len(sys.argv) > 1 else "ce2")
SR = 44100
WARMUP = SR // 4
INTERP_MAX = -50.0
LOOSE_MAX = -25.0
DEFAULT_MAX = -40.0


def db(x, eps=1e-12):
    return 20.0 * np.log10(np.maximum(x, eps))


def tier(tag):
    parts = tag.split("_")
    if "sine8000" in tag and "r001" in parts:
        return "INTERP", INTERP_MAX
    if "r080" in parts or ("d10" in parts and "m10" in parts):
        return "LOOSE", LOOSE_MAX
    return "DEFAULT", DEFAULT_MAX


refs = sorted(glob.glob(str(D / "ref_*.f32")))
if not refs:
    sys.exit("no reference outputs in %s: run tests/host/build_ce2_accuracy.bat first" % D)

fails = []
worst_by_tier = {"INTERP": -999.0, "LOOSE": -999.0, "DEFAULT": -999.0}
worst_demanding = -999.0
print(f"{'test':20s} {'tier':8s} {'residual dB':>12s}")
for rf in refs:
    tag = Path(rf).stem[4:]
    ref = np.fromfile(rf, dtype=np.float32).astype(np.float64)
    cand = np.fromfile(D / f"cand_{tag}.f32", dtype=np.float32).astype(np.float64)
    if not np.all(np.isfinite(cand)):
        fails.append(f"{tag}: non-finite output")
        print(f"{tag:20s} non-finite output")
        continue

    n = min(len(ref), len(cand))
    ref, cand = ref[WARMUP:n], cand[WARMUP:n]
    resid = cand - ref
    residual_db = db(np.sqrt(np.mean(resid * resid))) - db(np.sqrt(np.mean(ref * ref)) + 1e-12)
    tname, tmax = tier(tag)
    worst_by_tier[tname] = max(worst_by_tier[tname], residual_db)
    if tag.startswith("pluck") or tag.startswith("chirp") or tag.startswith("sine8000"):
        worst_demanding = max(worst_demanding, residual_db)

    flag = []
    if residual_db > tmax: flag.append("residual")
    if flag: fails.append(f"{tag}: {', '.join(flag)}")
    print(f"{tag:20s} {tname:8s} {residual_db:12.1f} {' '.join(flag)}")

print("")
print(f"worst INTERP {worst_by_tier['INTERP']:.1f} dB (limit {INTERP_MAX}); "
      f"worst LOOSE {worst_by_tier['LOOSE']:.1f} dB (limit {LOOSE_MAX}); "
      f"worst DEFAULT {worst_by_tier['DEFAULT']:.1f} dB (limit {DEFAULT_MAX})")
print(f"STRETCH: worst pluck/chirp/8kHz residual {worst_demanding:.1f} dB (lower is better)")
print("ACCURACY: PASS" if not fails else f"ACCURACY: FAIL ({len(fails)} of {len(refs)} tests)")
sys.exit(0 if not fails else 1)
