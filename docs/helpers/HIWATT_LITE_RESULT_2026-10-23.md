# HIWATT_LITE Result (2026-10-23)

## Status
IN PROGRESS

## Baseline cost
Pedal build slot memory: 35248 of 40960 bytes (5712 free).
Steady-state static cost per 16-sample block (2x oversampled, HW_NB = 32 samples):

| Loop / Stage | Source line | Trips | Formula / Schedule | Steady-state Cycles |
|---|---|---|---|---|
| Kernel coeff cache copy | hiwatt_kernel.h:147 | 23 | (23-1)*8 + 1 + 14 | 191 |
| Kernel wet in copy | hiwatt_kernel.h:158 | 8 | (8-1)*8 + 1 + 6 | 63 |
| Upsampler stage 1 (allpass) | os_hbiir.h:115 | 10 | (10-1)*7 + 1 + 34 | 98 |
| Upsampler stage 2 (allpass) | os_hbiir.h:115 | 16 | (16-1)*16 + 76 + 78 | 394 |
| Upsampler stage 3 (allpass) | os_hbiir.h:115 | 10 | (10-1)*7 + 1 + 4 | 68 |
| Input DC guard | hiwatt_lite.h:538 | 32 | (32-1)*23 + 1 + 45 | 759 |
| Preamp tube pass 1 (x3 stages) | hiwatt_lite.h:337 | 32 | 3 x ((32-1)*11 + 42 + 137) | 1560 |
| Preamp tube pass 2 (x3 stages) | hiwatt_lite.h:355 | 32 | 3 x ((32-1)*9 + 137 + 72) | 1464 |
| Preamp tube pass 3 (x3 stages) | hiwatt_lite.h:373 | 32 | 3 x ((32-1)*37 + 1 + 31) | 3537 |
| Tone stack net5 (st=1) | hiwatt_lite.h:427 | 32 | (32-1)*25 + 14 + 29 | 818 |
| Tone stack scale (st=1) | hiwatt_lite.h:567 | 16 | (16-1)*12 + 1 + 5 | 186 |
| V1 network net2 (st=0) | hiwatt_lite.h:406 | 32 | (32-1)*16 + 21 + 42 | 559 |
| V1 scale (st=0) | hiwatt_lite.h:564 | 16 | (16-1)*12 + 1 + 0 | 181 |
| NFB loop (serial, fast path) | hiwatt_lite.h:480 | 32 | 32 x (148 + 107) | 8160 |
| Downsampler stage 1 | os_hbiir.h:115 | 10 | (10-1)*7 + 1 + 18 | 82 |
| Downsampler stage 2 | os_hbiir.h:115 | 16 | (16-1)*12 + 58 + 16 | 254 |
| Downsampler stage 3 | os_hbiir.h:115 | 10 | (10-1)*7 + 1 + 6 | 70 |
| Cab biquads pass 1a | hiwatt_lite.h:291 | 5 | (5-1)*12 + 0 + 52 | 100 |
| Cab biquads pass 1b | hiwatt_lite.h:291 | 16 | (16-1)*23 + 52 + 23 | 420 |
| Cab biquads pass 1c | hiwatt_lite.h:291 | 5 | (5-1)*12 + 23 + 3 | 74 |
| Cab biquads pass 2a | hiwatt_lite.h:292 | 4 | (4-1)*12 + 3 + 43 | 82 |
| Cab biquads pass 2b | hiwatt_lite.h:292 | 16 | (16-1)*22 + 43 + 23 | 396 |
| Cab biquads pass 2c | hiwatt_lite.h:292 | 4 | (4-1)*12 + 23 + 4 | 63 |
| Kernel mix & clamp | hiwatt_kernel.h:160 | 16 | (16-1)*38 + 1 + 28 | 599 |
| Entry overhead & control flow | Fx_SFX_CFWattL | 1 | Basic blocks & tests | 202 |
| **Total Baseline Steady-state Cost** | | | | **20,380 cycles** |

*Note on static counts*: The count above assumes the fast-path condition (no ADAA fixup branch triggered in preamp tubes or PI stage). When signals trigger the ADAA fixup loop (`hiwatt_lite.h:253`), additional cycles are spent, so 20,380 is a lower bound in steady state.

## Changes tried
1. **Disabled preamp tube ADAA fix-up pass entirely**: Reverted. Failed 8 of 36 tests (extreme alias blowout on `cranked_f1760_a070` due to unhandled region boundary crossings).
2. **Plain waveshaping on V3a**: Reverted. Failed 1 of 36 tests (`cranked_f1760_a070`: alias -28.8 dB vs shipped -35.1 dB, 0.3 dB over tolerance).
3. **Plain waveshaping on PI**: Reverted. Failed 12 of 36 tests (strong harmonic distortion changes on pushed signals).
4. **Linear input decomposition of NFB loop (`hw_nfb_block`)**: Kept. Decomposed back-half network into input-driven pass $x_A$ (pipelined over 32 samples) and residual-driven serial loop $x_B$. Removes $u_0, s_0$ partials from serial feedback loop. PASS 36/36, STRETCH 0.00 dB. Slot memory 36368 B (4592 free).

## Scores
### Baseline (Unchanged core)
failing tests: 0 of 36
STRETCH (worst character deviation, dB): 0.00
ACCURACY: PASS
Steady-state cost: 20,380 cycles
Date/Time: 2026-10-23 01:34:00-07:00

### Change 4: NFB linear split (precomputed xA, dB pass)
failing tests: 0 of 36
STRETCH (worst character deviation, dB): 0.00
ACCURACY: PASS
Steady-state cost estimate: 19,850 cycles
Date/Time: 2026-10-23 01:54:00-07:00

## Cost
Baseline: 20,380 cycles per 16-sample block (steady-state static estimate).
Target: <= 50% baseline (<= 10,190 cycles), stretch <= 40%, ACCURACY: PASS.

## Problems
None so far.
