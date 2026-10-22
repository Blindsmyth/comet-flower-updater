# CF Delay "Tail" Switch (Job F7)

## Status
running

## Findings

### Analysis of Delay Core and Dry/Wet Separability
- **Claim**: In `effects/common/delay_g1.h`, the delay core mixes dry and wet in both `delay_process()` and `delay_block()` via `out = in * k->dry + tap * k->wet`. The `DelayCoeffs` struct contains public float fields `target`, `fb`, `wet`, and `dry`. The dry and wet components are cleanly separable from the caller (`effects/delayx/delayx.c`) WITHOUT editing `effects/common/delay_g1.h`:
  1. Passing an input scaled by `fade` (`in_scaled[i] = fade * eff[i]`) feeds scaled audio into the delay line write node (`w[i] = in[i] + dl_tone_step(&lp, outL[i]) * fb`), so new input stops entering when `fade == 0` (bypassed).
  2. Setting `k.dry = 0.0f` causes `delay_block()` to compute `outL[i] = in_scaled[i] * 0.0f + tapL * k->wet = tapL * k->wet` and `outR[i] = tapR * k->wet`, returning pure wet repeats.
  3. In `delayx.c`, the output is formed by summing the dry input signal with the pure wet repeats (`out = dry + wet`), with no fade applied to the wet repeats when `Tail == 1`.
  4. For `Tail == 0`, today's existing code path (`k.dry = 1.0f - m`, `delay_block(eff)`, crossfade `da + fade * (wl - da)`) is preserved verbatim for exact bit-identical output.
- **Evidence**:
  - `effects/common/delay_g1.h` lines 50-63 (`DelayCoeffs` definition and `delay_coeffs()`), lines 150-166 (`delay_process()`), lines 176-232 (`delay_block()`). In both functions, `k->dry` is only used in the final output mix and does not affect the feedback or delay line state.
  - `effects/delayx/delayx.c` lines 35-94 (calling layout, coefficient extraction, and block processing).
- **Confidence**: Confirmed.

## Answers

- **Can a firmware patch change it?**:
  No firmware patch is necessary. As discovered in S9 (`docs/FW_RND_ANSWERS_2026-10-22.md` lines 225-234), the firmware continues to call bypassed effect kernels every block with `coef[0]` (`fade`) = 0. The kernel itself governs the dry/wet mix and can continue rendering delay repeats after `fade` reaches 0.
- **Patch site + plan + risk**:
  N/A. Handled purely in user-space effect code within `effects/delayx/`.

## Not checked / open leads
- Pending edits to `effects/delayx/manifest.json`, `effects/delayx/delayx.c`, and `tests/host/delayx_kernel_test.cpp`.
- Pending verification via host tests and `tools/build_g1.sh delayx "CF DLY"`.
