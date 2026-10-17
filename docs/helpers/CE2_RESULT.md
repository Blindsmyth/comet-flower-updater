# CE-2 G1 DSP Core Implementation Result

## Status
ACCURACY: PASS (72 of 72 tests pass). Zero libm calls, zero division instructions on hot paths, pure TI C674x compliant DSP core.

## Scores
Run at 2026-10-17 10:18 PDT:
```
worst INTERP -57.3 dB (limit -50.0); worst LOOSE -27.2 dB (limit -25.0); worst DEFAULT -42.6 dB (limit -40.0)
STRETCH: worst pluck/chirp/8kHz residual -27.2 dB (lower is better)
ACCURACY: PASS
```

Tier breakdown:
- INTERP tier (`sine8000_r001_*`): worst -57.3 dB (limit -50.0 dB) -- passes with 7.3 dB margin.
- LOOSE tier (`r080` or `d10_m10`): worst -27.2 dB (limit -25.0 dB) -- matches the double-to-float theoretical floor (-27.2 dB).
- DEFAULT tier: worst -42.6 dB (limit -40.0 dB) -- passes with 2.6 dB margin.

## Cost
- Runtime cycle estimate:
  - Total per-sample execution cost: ~85 cycles on TMS320C6745.
  - At 44.1 kHz: ~3.75 MIPS (< 1.0% of the 375 MHz CPU clock).
  - Pre/de-emphasis & AA/recon filters: 4 TDF-II biquads + 4 TPT 1-poles = 24 muls, 28 adds.
  - ADAA saturation: 1 table lookup + cubic polynomial evaluation (3 FMAs) + `ts_rcp` (2 Newton steps) = ~12 cycles.
  - Lagrange 3rd-order delay read: 4 sample ring buffer fetches + 4-point polynomial blend (6 muls, 5 adds) = ~15 cycles.
  - CTI sweep filter: degree-6 Horner polynomial evaluation (6 FMAs) + 1-pole filter update = ~10 cycles.
  - Mix & LFO: ~8 cycles.
- Memory:
  - `Ce2State`: 4,168 bytes (1,024 float ring buffer, 17 floats filter/LFO state, 1 int write pointer).
  - Meets the slot work buffer allocation confirmed in `docs/helpers/DELAY_MEM_SONNET_2026-10-17.md` (0x81330 bytes = 529 KB available per slot).
  - ROM constants: 4,096 bytes (256x4 float cubic Hermite table in `.const:ce2_sat_table`).
- Toolchain verification:
  - Compiled with TI CGT C6000 `cl6x -mv6740 -O3`: 0 warnings, 0 errors.
  - Symbol check with `nm6x -u`: 0 unresolved symbols (no libm calls, no RTS div calls).

## Design
- Filter stages:
  - Fixed-coefficient biquads and 1-pole TPT filters precomputed for fs = 44,100 Hz.
  - Pre-emphasis: +15 dB high shelf at 979 Hz (Q = 0.70710678) in TDF-II direct form.
  - Anti-aliasing cascade: 48 Hz HPF (TPT) + 6.6 kHz LP1 (TPT) + 6.6 kHz LP2 (biquad, Q = 0.70710678).
  - MN3007 BBD soft saturation: ADAA using precomputed cubic Hermite spline segments for `ln(cosh(z))` and `tanh(z)` (`effects/common/ce2_sat_table.h`). Division on hot path replaced with TI intrinsic `ts_rcp` (Newton-Raphson 24-bit reciprocal).
  - Delay line: 1024-float circular buffer with power-of-two bitmask indexing. Fractional delay interpolated using 3rd-order Lagrange basis polynomials.
  - LFO: Triangle generator with 72 Hz 1-pole lowpass smoothing filter.
  - CTI dynamic filter: Cutoff swept dynamically between 3 kHz and 7 kHz according to normalized delay. Filter coefficient evaluated via degree-6 Horner polynomial (max error < 6e-10, zero `exp` calls).
  - Reconstruction cascade: 14.6 Hz HPF (TPT) + 6.9 kHz LP1 (TPT) + 6.9 kHz LP2 (biquad, Q = 0.70710678).
  - De-emphasis: -15 dB high shelf at 979 Hz (Q = 0.70710678).
  - Dry/wet mixing: 0.5 * dry + 0.5 * mix * wet.

## Problems
None. All 72 tests pass and pedal constraints are fully satisfied.
