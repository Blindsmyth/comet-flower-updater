# CF Delay "Tail" Switch (Job F7)

## Status
done

## Findings

### 1. Analysis of Delay Core and Dry/Wet Separability
- **Claim**: In `effects/common/delay_g1.h`, the delay core mixes dry and wet in both `delay_process()` and `delay_block()` via `out = in * k->dry + tap * k->wet`. The `DelayCoeffs` struct contains public float fields `target`, `fb`, `wet`, and `dry`. The dry and wet components are cleanly separable from the caller (`effects/delayx/delayx.c`) WITHOUT editing `effects/common/delay_g1.h`:
  1. Passing an input scaled by `fade` (`in_scaled[i] = eff[i] * fade`) feeds scaled audio into the delay line write node (`w[i] = in[i] + dl_tone_step(&lp, outL[i]) * fb`), so new input stops entering when `fade == 0` (bypassed).
  2. Setting `k.dry = 0.0f` causes `delay_block()` to compute `outL[i] = in_scaled[i] * 0.0f + tapL * k->wet = tapL * k->wet` and `outR[i] = tapR * k->wet`, returning pure wet repeats.
  3. In `delayx.c`, the output is formed by summing the dry input signal with the pure wet repeats (`out = dry + wet`), with no fade applied to the wet repeats when `Tail == 1`.
  4. For `Tail == 0`, today's existing code path (`k.dry = 1.0f - m`, `delay_block(eff)`, crossfade `da + fade * (wl - da)`) is preserved verbatim for exact bit-identical output.
- **Evidence**:
  - `effects/common/delay_g1.h` lines 50-63 (`DelayCoeffs` definition and `delay_coeffs()`), lines 150-166 (`delay_process()`), lines 176-232 (`delay_block()`). In both functions, `k->dry` is only used in the final output mix and does not affect the feedback or delay line state.
  - `effects/delayx/delayx.c` lines 35-128.
- **Confidence**: Confirmed.

### 2. Manifest and Parameter Generation
- **Claim**: Added 4th parameter `Tail` (max 1, default 1, explanation `"1: repeats ring out after the effect is switched off"`) to `effects/delayx/manifest.json`. Stomphacks parameter mapping assigns `Tail` to coefficient slot `[7]` (`SH_PARAM_TAIL 7`).
- **Evidence**:
  - `effects/delayx/manifest.json` lines 18-23.
  - Generated `sh_params.h`: `#define SH_PARAM_TAIL 7 /* 'Tail' knob 0..1 -> coeff 0..1, default 1 */`, `#define SH_NUM_PARAMS 4`.
  - `build/DLYX.REPORT.md` parameter table: entry 5, `Tail`, range `0..1`, default `1`, coeff slot `[7]`, direct handler.
- **Confidence**: Confirmed.

### 3. Kernel Tail Implementation
- **Claim**: `effects/delayx/delayx.c` branches on `ktail < 0.5f`:
  - `Tail == 0`: Executes the original code path verbatim (`delay_block` with unmodified `k` and `eff`, crossfading `a = da + fade * (wl - da)`).
  - `Tail == 1`: Scales the input into a local array `in_scaled[i] = eff[i] * fade`, sets `k.dry = 0.0f` to obtain pure wet repeats from `delay_block`, and mixes dry and wet via `dry_a = da * (1.0f - fade * mix)`, `dry_b = db * (1.0f - fade) + da * fade * (1.0f - mix)`, `a = dry_a + wl`, `b = dry_b + wr`.
  - When `fade == 1.0f`, both Tail 0 and Tail 1 produce bit-identical results.
  - When `fade == 0.0f` from the start, Tail 1 produces exact pass-through (`output == input`).
  - When `fade` transitions to `0.0f` after audio has entered, the repeats decay naturally according to feedback, with no fade applied to the wet signal.
- **Evidence**:
  - `effects/delayx/delayx.c` lines 79-127.
- **Confidence**: Confirmed.

### 4. Host Test Verification
- **Claim**: Extended `tests/host/delayx_kernel_test.cpp` to verify all requirements:
  - Added `coef[SH_PARAM_TAIL] = 1.5f` out-of-range guard check (mutes correctly).
  - Added Test 5: Verified Tail 0 is 100% bit-identical (`std::memcmp`) to the old kernel reference across 88,200 samples with varying fade, dynamic inputs, and impulse tests.
  - Added Test 6: Verified Tail 1 with `fade == 0.0f` from the start yields `output == input` (exact bit-identical pass-through).
  - Added Test 7: Verified Tail 1 with a 100 ms burst followed by `fade == 0.0f`:
    - Energy after 1 s is 37.857076 (> 0, repeats ring out).
    - Energy after 30 s is 0.0000000000 (< 1e-6, decayed to zero).
    - All samples across 32 seconds remain finite (no NaN, no Inf).
- **Evidence**:
  - Execution of `tests/host/build_delayx_kernel_test.bat`: all 17 checks passed.
- **Confidence**: Confirmed.

### 5. Build, Slot Memory, and Cycles Report
- **Claim**: Built with `bash tools/build_g1.sh delayx "CF DLY"`. `check_slot_mem.py` passes with 23,016 bytes of headroom. Static cycle cost changes by only +16 cycles per block for Tail 1.
- **Evidence**:
  - `tools/check_slot_mem.py`: `slot memory: build/DLYX.ZD2 uses 17944 of 40960 bytes (23016 free) ok`.
  - `build/DLYX.REPORT.md`: container ID `0x08000f8b`, 4-param PRME/PRMJ, CRC `0xd4a2ccae`, `.text` 12,352 B, dspload 20.00 raw (7.4%).
  - `build/DLYX.LOOPS.md`: 20 loops (10 in Tail 0 branch, 10 in Tail 1 branch), 2 not pipelined (the fallback `delay_process` path for delay times < 17 samples).
  - Cycle impact:
    - Tail 0 path: 0 cycle change (identical code).
    - Tail 1 path: +16 cycles for the `in_scaled` loop (trip 8, ii 2, unroll 2x). Output mix loop has trip 16, ii 6 (identical to Tail 0 output loop).
- **Confidence**: Confirmed.

### 6. EDTB Note and Patch Compatibility
- **Claim**: Parameter 4 (0-based index 3, `Tail`) occupies a 12-bit field in the Zoom G1 Four patch `EDTB` parameter table. Since `Tail` has max = 1 (values 0 or 1), it fits well within the 12-bit field (0..4095).
- **Saved Patches Note**: Existing saved patches that contain CF Delay have only the first 3 parameter words populated in their `EDTB` record; the 4th parameter word is stored as 0 (default zero-fill in unused slot parameters). Consequently, existing patches loaded on the pedal will read `Tail = 0` (preserving legacy behaviour where repeats fade on bypass). Newly created or edited patches with CF Delay will default to `Tail = 1` as specified in the manifest.
- **Evidence**:
  - `docs/helpers/PATCH_STORE_ARGON_2026-10-17.md` line 130 (EDTB bitfield unpack `0xc017f648`).
  - `docs/helpers/FW_RND_BRIEF4_2026-10-22.md` lines 44-46.
- **Confidence**: Confirmed.

### 7. Pytest Suite Execution
- **Claim**: `.venv/Scripts/python.exe -m pytest tests -q` ran with 339 passed, 146 subtests passed, and exactly 1 failure: `test_slot_heap_calculation_ratx`.
- **Evidence**:
  - Pytest run output: `FAILED tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx`, 1 failed, 339 passed, 146 subtests passed in 69.01s.
  - Matches `FW_RND_BRIEF4_2026-10-22.md` lines 6-7 ("one failure test_slot_heap_calculation_ratx is known and unrelated").
- **Confidence**: Confirmed.

## Answers

- **Can a firmware patch change it?**:
  No firmware patch is necessary. The firmware calls bypassed effect kernels continuously with `coef[0] == 0.0f`. Delay tails are implemented entirely within the effect kernel.
- **Patch site + plan + risk**:
  N/A. Implemented cleanly in `effects/delayx/`.

## Not checked / open leads
- On-hardware pedal verification of tail behavior when switching patches or toggling bypass via the physical footswitch (deferred to bench testing as pedal access is prohibited during static analysis).
