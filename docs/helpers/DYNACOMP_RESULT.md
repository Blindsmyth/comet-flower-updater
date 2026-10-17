# Dyna Comp Result Log

## Status
Direct float implementation passes all 72 tests (ACCURACY: PASS). Optimization and pedal rules compliance (eliminating libm and divisions on hot paths) in progress.

## Scores
2026-10-17 10:15 PDT
```
worst residual -38.2 dB (limit -40.0, -30.0 on GENTLE/a005 tests); worst GR trajectory 0.05 dB (limit 0.3)
STRETCH: worst pluck/step residual -56.9 dB (lower is better)
ACCURACY: PASS
```

Earlier baseline (placeholder):
```
worst residual 16.1 dB (limit -40.0, -30.0 on GENTLE/a005 tests); worst GR trajectory 28.11 dB (limit 0.3)
STRETCH: worst pluck/step residual 12.1 dB (lower is better)
ACCURACY: FAIL (72 of 72 tests)
```

## Cost
`sizeof(DynaCompState)` = 32 bytes (8 floats: v1_pre, v2_pre, v1_de, v2_de, s_hp, adaa_x1, adaa_ad1, envelope).
`sizeof(DynaCompCoeffs)` = 16 bytes (4 floats: threshold, thresholdDb, autoMakeup, outTrim).
Total per-instance state: 48 bytes (well under the 392-byte limit).

## Design
Current implementation:
- Pre-emphasis shelf: DF2T biquad with precomputed float32 constants at 44.1 kHz.
- Envelope detector: attack 5 ms, release 300 ms, pure exponential decay.
- Gain computer: CompressorMath 8:1 soft knee (6 dB) with reference-level-preserving makeup.
- ADAA saturator: tanh(x/1.2) * 1.2 with lnCosh antiderivative.
- De-emphasis shelf: DF2T biquad with precomputed float32 constants at 44.1 kHz.
- Output HPF: 80 Hz TPT one-pole with precomputed float32 constant.
- Output trim: linear scaling.

## Problems
Next step: Replace runtime libm calls (`log10f`, `expf`, `log1pf`, `tanhf`, `powf`) and division in `dynacomp_process` with TI C674x-compliant inline math (`ts_rcp`, polynomial / range-reduced math) while maintaining `ACCURACY: PASS`.
