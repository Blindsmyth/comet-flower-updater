# Brief 4, 2026-10-22 (jobs F6, F7, Gemini 3.8 Flash)

Rules as `docs/helpers/FW_RND_BRIEF2_2026-10-22.md` (build jobs: edit only the
files your job names plus your report; build with `bash tools/build_g1.sh`;
never touch updater images or the pedal; SAVE_PROTOCOL; never push; utf-8).
Run `.venv/Scripts/python.exe -m pytest tests -q` at the end; one failure
`test_slot_heap_calculation_ratx` is known and unrelated.

## F6 - CFMPRE labels cut to 5 characters
Report `docs/helpers/FW_RND_F6_CFMPRE5_FLASH_2026-10-22.md`. Edit only
`effects/cfm_pre/manifest.json`, `effects/cfm_pre/cfm_pre.c`, the report.
Why: the effect screen draws labels centred in 31 px columns with a fixed
6 px font (`docs/FW_RND_ANSWERS_2026-10-22.md` Q7), so 5 chars fit and 6+
overlap the neighbours. Change ONLY the labels (same order, max, default,
explanation) to exactly these, then the `SH_PARAM_*` names in cfm_pre.c to
the newly generated ones (read the generated sh_params.h):
  1 `DSens` 2 `DOut` 3 `DynOn` | 4 `MSust` 5 `MTone` 6 `MVol` |
  7 `FRate` 8 `FRang` 9 `FColr` | 10 `MufOn` 11 `FMtx` 12 `Level`
(D = DynaComp, M = Muff, F = Flanger/Mistress.) Also add one sentence to each
param's explanation? NO: leave explanations unchanged. Build (icon label
`CFM Pre`), check_slot_mem passes, header 0x58 still 2; script-check that
only names changed (compare with `git show HEAD:effects/cfm_pre/manifest.json`).

## F7 - CF Delay "Tail" switch
Report `docs/helpers/FW_RND_F7_DELAYTAIL_FLASH_2026-10-22.md`. Edit only
`effects/delayx/delayx.c`, `effects/delayx/manifest.json`,
`tests/host/delayx_kernel_test.cpp`, the report.
Why: the firmware likely keeps calling a bypassed effect with coef[0]
(`fade`) = 0 (S9 in the answers doc); a delay can then let its repeats ring
out after it is switched off. Add a 4th param `Tail` (max 1, default 1,
explanation "1: repeats ring out after the effect is switched off").
Behaviour: Tail 0 = exactly today's code path (bit-identical output; prove it
in the host test against the old kernel or a recorded reference). Tail 1 =
the signal FED INTO the delay line is scaled by `fade` (so new input stops
entering when OFF) while the wet repeats are always output at full level on
top of the dry signal: out = dry + wet, with no fade on the wet. Read
`effects/common/delay_g1.h` (`delay_block`, `delay_coeffs`) to see how dry
and wet are mixed today; if dry and wet are not separable without editing
delay_g1.h, STOP and report how you would do it (do not edit effects/common).
Host test additions: with Tail 1, feed a burst then set fade 0: repeats keep
decaying (energy after 1 s > 0, after 30 s near 0 with Regen < 100), no NaN;
with fade 0 from the start nothing enters the line (output == input).
Build (icon label `CF DLY`), check_slot_mem passes, report cycles change
(`build/DLYX.LOOPS.md`, REPORT.md) and the new EDTB note: param 4 is a 12-bit
field (fine). Note: saved patches with CF Delay get Tail from their stored
value (likely 0 = old behaviour).
