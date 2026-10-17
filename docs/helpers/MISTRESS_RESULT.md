# CF Mistress DSP Core Results

## Status
Initial implementation of `mistress_g1.h`. 77 of 81 tests pass!
All Matrix tests pass (-135 to -140 dB).
All Sine 440 tests pass (-41 to -96 dB).
All Sine 8000 tests pass, with worst INTERP at -64.0 dB (matches calibration benchmark exactly).
All Pluck tests pass (-38 to -97 dB).
Only 4 chirp tests with high feedback (f=0.9) and high rates (r=1.0, 4.0) missed the threshold. Investigating feedback loop sensitivity / float accuracy differences.

## Scores
Run 1:
```
worst INTERP -64.0 dB (limit -55.0); worst LOOSE -24.7 dB (limit -30.0); worst DEFAULT -36.1 dB (limit -40.0)
STRETCH: worst pluck/chirp residual -24.7 dB (lower is better)
ACCURACY: FAIL (4 of 81 tests)
```
Date: 2026-10-17 10:18 PDT

Baseline placeholder:
```
worst INTERP -11.8 dB (limit -55.0); worst LOOSE -4.3 dB (limit -30.0); worst DEFAULT -2.8 dB (limit -40.0)
STRETCH: worst pluck/chirp residual -4.3 dB (lower is better)
ACCURACY: FAIL (81 of 81 tests)
```

## Cost
TBD.

## Design
EHX Electric Mistress V2 flanger model running directly at 44.1 kHz:
- Pre-BBD 80 Hz coupling-cap HPF (TPT)
- LFO phase accumulator + two-segment exponential-triangle shape / Matrix static delay
- Pre-BBD anti-alias cascade: 12 kHz 1st-order TPT + 12 kHz Q=0.7071 biquad
- Feedback ADAA tanh clip (with mean_tanh for small steps, ln_cosh for large steps)
- 512-sample power-of-two circular buffer with 4-point Lagrange 3rd-order fractional delay read
- CTI one-pole low-pass filter
- Post-BBD 5 Hz DC-block HPF + reconstruction cascade (8 kHz 1st-order + 8 kHz Q=0.7071 biquad + 8.5 kHz Q=0.5 biquad)
- 50/50 dry/wet mix

## Problems
4 chirp tests with feedback = 0.9 (high feedback loop sensitivity) failed:
`chirp_r010_d03_f09` (-36.8 dB vs -40.0 limit)
`chirp_r010_d10_f09` (-26.0 dB vs -30.0 limit)
`chirp_r040_d03_f09` (-36.1 dB vs -40.0 limit)
`chirp_r040_d10_f09` (-24.7 dB vs -30.0 limit)
Investigating ADAA and filter differences on the high feedback path.
