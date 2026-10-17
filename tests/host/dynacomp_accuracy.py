"""Score the CF Dyna Comp candidate (effects/common/dynacomp_g1.h) against the
double-precision reference (tests/host/dynacomp_accuracy.cpp). Prints a
PASS/FAIL verdict.

Per test (a sine, a guitar-like pluck, or a loud/quiet/loud step, at a few
Sustain/Output settings): two error measures.

  1. RESIDUAL dB: 20*log10(rms(candidate - reference) / rms(reference)),
     over the signal with the first 0.25 s (filter/envelope settling)
     discarded. This is the whole-signal fidelity number -- it is sensitive
     to EVERYTHING (gain, tone shaping, clip shape, envelope timing) because
     for a zero-latency, non-oversampled effect the two signals line up
     sample-for-sample.
  2. GR TRAJECTORY dB: short-time RMS of the output over short-time RMS of
     the input (10 ms windows, 5 ms hop) gives an "effective gain" curve in
     dB over time. The candidate's and the reference's curves are compared
     and the worst absolute difference (over windows where the input is not
     near-silent) is reported. This isolates the envelope follower/gain-law
     TIMING from the tone-shaping that RESIDUAL also picks up -- a port that
     gets the filters right but the ballistics wrong shows up here even if
     RESIDUAL looks only moderately bad (steady tones hide ballistics
     errors; pluck/step tests do not).

GENTLE tests (the quietest sine, amplitude 0.05, tag contains "a005") get a
looser RESIDUAL bound than every other test. At that level and Sustain 0/5 the
compressor is below its knee almost the whole time (gain reduction ~= 1), so
"residual" is really measuring single-precision floor noise in the pre/de-
emphasis shelf pair and the 80 Hz output high-pass at a quiet, low-frequency
(110 Hz, close to that 80 Hz corner) tone -- not an audible defect. A genuine,
careful float port measures -37.5 dB there (see calibration below); a flat
-40 dB gate would fail that honest port on a case the ear cannot tell apart
from the reference, so GENTLE tests use -30 dB and every other test uses -40.

Calibration (2026-10-17, this repository's tests/host/build_dynacomp_accuracy.bat
+ this scorer, run three times with different effects/common/dynacomp_g1.h
contents -- see docs/helpers/AGY_DYNACOMP.md for the transcripts):
  - the double reference re-typed into float, same structure, same constants,
    no shortcuts ("self" check, a careful and correct port): worst RESIDUAL
    -37.5 dB (a GENTLE test; worst HARD-test residual -56.6 dB), worst GR
    TRAJECTORY 0.06 dB. Comfortably inside the gate below on every test.
  - the same port with the peak detector coarsened to update every OTHER
    sample (sample-and-hold, i.e. half the effective detector rate -- the
    "2x coarser detector" degradation this kit's brief calls for): worst
    RESIDUAL -7.0 dB (pluck, Sustain 10), worst GR TRAJECTORY 9.70 dB. 16 of
    72 tests fail outright (every pluck/step test with Sustain 5 or 10, where
    gain reduction is actually happening) -- clearly worse than the honest
    port, clearly caught by the gate below.
  - the shipped placeholder (identity): worst RESIDUAL +16.1 dB (the
    "residual" is LOUDER than the reference signal -- no compression, no
    tone shaping, nothing happened at all), worst GR TRAJECTORY 28.1 dB.
    FAILs all 72 of 72 tests, as it must.

Pass criteria (the gate), chosen to sit clearly above the honest-port numbers
and clearly below the degraded-detector run:
  every test: finite output;
  RESIDUAL <= -30 dB on GENTLE tests (amplitude 0.05), <= -40 dB on every
    other test;
  GR TRAJECTORY <= 0.3 dB on every test.
Stretch score (reported, not gated): the worst RESIDUAL over the pluck/step
tests specifically (the ones that exercise the envelope ballistics hardest).
Lower is better; -50 dB or better means the port's dynamics are
indistinguishable from the reference by ear.
Written by Claude; do not edit as part of the model work.
"""
import glob
import sys
from pathlib import Path

import numpy as np

D = Path(__file__).resolve().parents[2] / "build" / "host" / (sys.argv[1] if len(sys.argv) > 1 else "dynacomp")
SR = 44100
WARMUP = SR // 4
RESIDUAL_MAX_HARD = -40.0
RESIDUAL_MAX_GENTLE = -30.0
GR_MAX = 0.3
WIN, HOP = 441, 220   # 10 ms / 5 ms
IN_FLOOR = 1.0e-4


def st_rms(x, win=WIN, hop=HOP):
    n = max(0, (len(x) - win) // hop + 1)
    if n <= 0:
        return np.zeros(0)
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    frames = x[idx]
    return np.sqrt(np.mean(frames * frames, axis=1))


def db(x, eps=1e-12):
    return 20.0 * np.log10(np.maximum(x, eps))


refs = sorted(glob.glob(str(D / "ref_*.f32")))
if not refs:
    sys.exit("no reference outputs in %s: run tests/host/build_dynacomp_accuracy.bat first" % D)

fails = []
worst_residual, worst_gr, worst_pluck_residual = -999.0, 0.0, -999.0
print(f"{'test':28s} {'residual dB':>12s} {'GR traj dB':>11s}")
for rf in refs:
    tag = Path(rf).stem[4:]
    ref = np.fromfile(rf, dtype=np.float32).astype(np.float64)
    inp = np.fromfile(D / f"in_{tag}.f32", dtype=np.float32).astype(np.float64)
    cand = np.fromfile(D / f"cand_{tag}.f32", dtype=np.float32).astype(np.float64)
    if not np.all(np.isfinite(cand)):
        fails.append(f"{tag}: non-finite output")
        print(f"{tag:28s} non-finite output")
        continue

    n = min(len(ref), len(cand), len(inp))
    ref, inp, cand = ref[WARMUP:n], inp[WARMUP:n], cand[WARMUP:n]

    resid = cand - ref
    residual_db = db(np.sqrt(np.mean(resid * resid))) - db(np.sqrt(np.mean(ref * ref)) + 1e-12)
    worst_residual = max(worst_residual, residual_db)
    if tag.startswith("pluck") or tag.startswith("step"):
        worst_pluck_residual = max(worst_pluck_residual, residual_db)
    gentle = "a005" in tag
    residual_max = RESIDUAL_MAX_GENTLE if gentle else RESIDUAL_MAX_HARD

    rms_in, rms_ref, rms_cand = st_rms(inp), st_rms(ref), st_rms(cand)
    m = min(len(rms_in), len(rms_ref), len(rms_cand))
    valid = rms_in[:m] > IN_FLOOR
    gr_ref = db(rms_ref[:m]) - db(rms_in[:m])
    gr_cand = db(rms_cand[:m]) - db(rms_in[:m])
    gr_err = np.abs(gr_cand[valid] - gr_ref[valid]) if valid.any() else np.array([0.0])
    gr_db = float(gr_err.max()) if gr_err.size else 0.0
    worst_gr = max(worst_gr, gr_db)

    flag = []
    if residual_db > residual_max: flag.append("residual")
    if gr_db > GR_MAX: flag.append("GR")
    if flag: fails.append(f"{tag}: {', '.join(flag)}")
    print(f"{tag:28s} {residual_db:12.1f} {gr_db:11.2f} {' '.join(flag)}")

print("")
print(f"worst residual {worst_residual:.1f} dB (limit {RESIDUAL_MAX_HARD}, {RESIDUAL_MAX_GENTLE} on GENTLE/a005 tests); worst GR trajectory {worst_gr:.2f} dB (limit {GR_MAX})")
print(f"STRETCH: worst pluck/step residual {worst_pluck_residual:.1f} dB (lower is better)")
print("ACCURACY: PASS" if not fails else f"ACCURACY: FAIL ({len(fails)} of {len(refs)} tests)")
sys.exit(0 if not fails else 1)
