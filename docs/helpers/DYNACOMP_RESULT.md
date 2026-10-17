# Dyna Comp Result Log

## Status
Baseline test run with pass-through placeholder. Fails as expected (72/72 tests).

## Scores
2026-10-17 10:11 PDT
```
worst residual 16.1 dB (limit -40.0, -30.0 on GENTLE/a005 tests); worst GR trajectory 28.11 dB (limit 0.3)
STRETCH: worst pluck/step residual 12.1 dB (lower is better)
ACCURACY: FAIL (72 of 72 tests)
```

## Cost
Baseline placeholder: identity pass-through. DSP core implementation in progress.

## Design
Target specification:
- Reference model: Comet Flower DynaCompProcessor in tests/host/dynacomp_accuracy.cpp
- Pre-emphasis shelf: 2000 Hz, Q=0.70710678, gain=1.5 (+3.52 dB), Biquad DF2T
- Peak detector: attack tau=5 ms (alpha = exp(-1/(0.005*44100))), release tau=300 ms (alpha = exp(-1/(0.300*44100)))
- Compression math:
  - s = clamp(sustain, 0, 10)/10
  - threshold = 0.80 * (1-s)^2 + 0.005
  - thresholdDb = 20 * log10(threshold)
  - ratio = 8.0, kneeDb = 6.0
  - autoMakeupDb = -gainReductionDb(-12.0 - thresholdDb, 8.0, 6.0)
  - gainReductionDb(overDb, ratio, kneeDb) with slope = (1/ratio - 1) = -0.875
  - gainFor envelope
- ADAA tanh(x/1.2) * 1.2
  - Fn(x) = 1.2 * lnCosh(x/1.2)
  - if |x - x1| > 1e-5: (ad0 - ad1)/(x - x1) else tanh((x+x1)/(2*1.2))
- De-emphasis shelf: 2000 Hz, Q=0.70710678, gain = 1.0/1.5 (-3.52 dB)
- High-pass filter: 80 Hz, TPT one-pole (HP1)
- Output trim: 10^(outputDb / 20)

## Problems
None so far. Ready to implement the float DSP core in effects/common/dynacomp_g1.h.
