# CF Mistress DSP Core Results

## Status
Baseline test run completed with placeholder pass-through. 81/81 failed as expected. Proceeding to implement full DSP core in `effects/common/mistress_g1.h`.

## Scores
Baseline placeholder:
```
worst INTERP -11.8 dB (limit -55.0); worst LOOSE -4.3 dB (limit -30.0); worst DEFAULT -2.8 dB (limit -40.0)
STRETCH: worst pluck/chirp residual -4.3 dB (lower is better)
ACCURACY: FAIL (81 of 81 tests)
```
Date: 2026-10-17 10:12 PDT

## Cost
Placeholder run: N/A.

## Design
EHX Electric Mistress V2 flanger model running directly at 44.1 kHz:
- Pre-BBD 80 Hz coupling-cap HPF (feeds dry and wet paths).
- LFO phase accumulator (start phase 0, deterministic).
- Two-segment exponential-triangle LFO shape (`mistressLfoShape`), or static delay in Matrix mode.
- Pre-BBD anti-alias LPF cascade (12 kHz 1st-order TPT + 12 kHz Q 0.7071 RBJ biquad).
- Feedback sum through 18V op-amp ADAA tanh clip.
- BBD delay: 0.64 to 6.4 ms range, 4-point (cubic) Lagrange 3rd-order fractional interpolation.
- CTI one-pole low-pass (sweeps 8 kHz to 2.5 kHz based on delay).
- Post-BBD 5 Hz DC-block HPF + reconstruction LPF cascade (8 kHz 1st-order TPT + 8 kHz Q 0.7071 biquad + 8.5 kHz Q 0.5 biquad).
- Dry/wet mix (50/50 at mix=1).

Memory: Fixed-size circular buffer in state struct (e.g. 512 samples, mask 0x1ff, power of 2).

Pedal constraints:
- No libm at runtime (no expf, sinf, cosf, tanf, tanhf, logf).
- No division on hot path (use reciprocal approximations or precomputed / coefficients updated per block).
- All helper functions TS_INLINE.
- No switch statements.

## Problems
None yet.
