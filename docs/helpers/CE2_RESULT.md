# CE-2 G1 DSP Core Implementation Result

## Status
Baseline test run completed with placeholder ce2_g1.h. All 72 tests FAIL as expected.

## Scores
Run at 2026-10-17 10:11 PDT:
```
worst INTERP 0.0 dB (limit -50.0); worst LOOSE 2.2 dB (limit -25.0); worst DEFAULT 10.0 dB (limit -40.0)
STRETCH: worst pluck/chirp/8kHz residual 10.0 dB (lower is better)
ACCURACY: FAIL (72 of 72 tests)
```

## Cost
To be profiled / analyzed against TI C674x constraints.

## Design
Specification: Reference chain from `tests/host/ce2_accuracy.cpp`:
- Pre-emphasis: High shelf +15 dB (979 Hz, Q 0.70710678)
- Anti-aliasing filter: HPF (48 Hz, 1-pole TPT) + LPF (6.6 kHz 1st-order TPT) + LPF (6.6 kHz biquad, Q 0.70710678)
- Non-linear saturation: MN3007 BBD soft saturation using ADAA tanh(0.7 * x) / 0.7
- BBD Delay Line: Ring buffer with 3rd-order Lagrange fractional interpolation, center 12.8 ms, +- 5 ms * Depth, triangle LFO smoothed by 72 Hz one-pole (fs = 44100 Hz)
- Clock-tracking filter (CTI): One-pole lowpass swept between 3000 Hz and 7000 Hz according to normalized delay against fixed bounds [7.8, 17.8] ms
- Reconstruction filter: HPF (14.6 Hz 1-pole TPT) + LPF (6.9 kHz 1st-order TPT) + LPF (6.9 kHz biquad, Q 0.70710678)
- De-emphasis: High shelf -15 dB (979 Hz, Q 0.70710678)
- Output mixing: 0.5 * dry + 0.5 * mix * wet

Pedal compliance:
- No libm at runtime (no sin, cos, tan, exp, log, tanh, sqrt). Fast polynomial/lookup approximations or precalculated constants.
- No divide on hot path (use ts_rcp or precomputed constants).
- No switch, fixed loop counts, inline helpers.
- Ring buffer embedded in Ce2State.

## Problems
None yet.
