# Brief for Gemini 3.8 Flash (agy): CF WattL, a cheaper Hiwatt core

You are making an existing guitar-amp model for a Zoom G1X Four pedal (TI C6745
DSP, float, ~375 MHz, 16-sample blocks at 44.1 kHz) **cheaper to run while
sounding the same**. A test bench and a PASS/FAIL scorer are set up. Read every
step. Earlier helpers went wrong by guessing, by editing files they were told
not to touch, and by losing work to quota limits.

## 0. First action
Create `docs/helpers/HIWATT_LITE_RESULT_2026-10-23.md` with the headings
`## Status`, `## Baseline cost`, `## Changes tried`, `## Scores`, `## Cost`,
`## Problems`. After every test run, append the scorer's last 3 lines, the cost
estimate and the date/time, then commit THAT FILE ONLY (rules in
`docs/helpers/SAVE_PROTOCOL.md`; read it, including "Token economy"):
```
git add docs/helpers/HIWATT_LITE_RESULT_2026-10-23.md
git commit -m "HIWATT_LITE: <one-line finding>" -m "Co-Authored-By: Gemini 3.8 Flash <noreply@google.com>"
```
Never commit any other file. Never push. Claude reviews and commits the code.

## 1. Why
The owner's 5-effect patch (CFM Pre, CF Delay, CF Watt, CF Rotary, CF Delay)
peaks at 107 % CPU. CF Watt costs a median 23.4k cycles per block on the pedal,
the second-biggest slot. The goal is more slots per patch later, so every
effect has to get leaner. Owner rule: **the cheapest version that sounds the
same wins.**

## 2. The files
- `effects/common/hiwatt_lite.h`: **your file.** Right now it is a verbatim copy
  of the shipped core `effects/common/hiwatt_amp.h` (same API: `HwState`,
  `HwCoeffs`, `hw_coeffs()`, `hw_block()`). Keep that API and its meaning
  (the kernel `effects/common/hiwatt_kernel.h` calls it unchanged). Read its
  header comment first: it describes the chain
  (input DC guard -> V1 tube -> V1 network -> V2 tube -> tone stack + master ->
  V3a tube -> NFB loop with back half, PI, EL34 power stage with sag, residual
  -> downsample -> Fane cab).
- You may create new headers `effects/common/hiwatt_lite_*.h` and helper scripts
  `tools/gen_hiwatt_lite*.py` (for example to fit tables or filters), and
  scratch files under `build/hiwatt_lite/` only.
- `effects/hiwattl/manifest.json`: you may change ONLY `"state_bytes"`
  (= `sizeof(HwState)` of the kernel state + 16, multiple of 4, max 392; check
  the kernel's state struct in `hiwatt_kernel.h`).
- **Do not edit anything else**: not `hiwatt_amp.h`, `hiwatt_kernel.h`,
  `hiwatt_netgen.h`, the tests, the scorer, other effects, or anything outside
  this repository. Shared headers that `hiwatt_lite.h` includes
  (`hiwatt_netgen.h`, `hiwatt_cab.h`, `hw_blob.h`, `os_hbiir.h`, ...) are used by
  shipped effects: if you need a changed copy, copy it to a new
  `hiwatt_lite_*.h` file and change the copy.
- **Never touch the pedal**: no MIDI, no `tools/cf_probe.py`, `tools/ua_*.py`,
  no updater `.exe` files.

## 3. The test loop (repository root; PowerShell shown, bash in brackets)
```
cmd /c "tests\host\build_hiwatt_lite.bat"            [cmd //c "tests\\host\\build_hiwatt_lite.bat"]
.venv\Scripts\python.exe tests\host\hiwatt_lite_score.py
```
The first line compiles `hiwatt_lite.h` into the PC bench at 2x and renders 36
tests (4 knob settings x 110/440/1760 Hz x 3 levels) to `build/host/hwl/L_*`.
The reference renders (`ref_*`, 16x desktop circuit) and the shipped core
(`G_*`) are already there: **never delete or regenerate them.** The scorer
compares your output with the shipped core and with the reference (rules in its
docstring) and ends with `ACCURACY: PASS` or `FAIL`. The unchanged copy passes
with STRETCH 0.00. **Every change must keep `ACCURACY: PASS`.**

## 4. Build for the pedal and measure cost
```
& "C:\Program Files\Git\bin\bash.exe" tools/build_g1.sh hiwattl "CF WattL" "CF/WATT"
.venv\Scripts\python.exe tools/c6x_cycles.py C:/Users/z/zoomlab/stomphacks/effects/hiwattl/build/hiwattl.asm
```
The build must end with `slot memory: ... ok` (the code + data must fit 40,960
bytes per slot; watch the free number). `hiwattl.asm` is the compiled kernel
(the build keeps it because of `-k`). `c6x_cycles.py` prints the cycles of each
code block; software-pipelined loops show PROLOG / KERNEL / EPILOG: one loop
costs about `(trips - 1) * KERNEL + PROLOG + EPILOG`. At 2x a block has
`HW_NB = 32` oversampled samples (16 at base rate for the cab and the
resamplers' outer side). Map each loop to its source loop (the `.asm` has
source-line comments) and sum **cycles per 16-sample block** in steady state
(knobs not moving: the kernel caches `hw_coeffs`).

**Step 1 (before changing anything): compute the baseline** of the unchanged
copy this way and write the table (loop, source line, trips, cycles) in
`## Baseline cost`. Static counts are trustworthy only for loops with no
data-dependent branches; the shipped core still has some (the ADAA fix-up
paths), so note where the static number is a lower bound.

**Goal: steady-state static cost at most 50 % of your baseline, stretch 40 %,
with `ACCURACY: PASS`.** Same method for both numbers, so the ratio is what
counts. The pedal measurement comes later (the owner runs it).

## 5. Pedal rules (the build rejects, or the pedal misbehaves)
- **No libm at run time** (no sinf, tanhf, expf, logf, powf, sqrtf). Use the
  inline helpers already used here (`sd_expf`, `ts_rcp`, ...) or polynomials or
  small `static const float` tables. Tables < 8 KB in total (16 KB fast data cache).
- **No division** on per-sample paths (`ts_rcp`). **No `switch`.** **No calls**
  to non-inline functions (helpers `TS_INLINE`).
- **No data-dependent `if` in per-sample loops**: use `fminf/fmaxf`-style
  selects or tables; fixed loop counts. This also makes the static count true.
- Keep the stage-major structure (each stage over the whole block with its
  state in locals) so the compiler can software-pipeline; only a real feedback
  loop has to run sample by sample.
- `hw_block` must stay safe for silence, full-scale input and every knob
  setting (no NaN, no blow-up): the scorer flags NaN.

## 6. Where the cost is (from `docs/DR103_REDESIGN_2026-10-15.md`, at 4x;
2x is roughly half per part) and ideas to try, cheapest first
- **NFB loop** (`hw_nfb_block`, serial, ~258 cycles per sample): the biggest
  part. Ideas: move every linear piece that does not need the nonlinear
  residual out of the serial loop (block passes before/after); cheaper tube and
  EL34 transfer functions (polynomial or table instead of exp-based curves);
  fewer state variables in the linear networks (lower-order fits that keep the
  response within the scorer's limits).
- **Preamp tubes** (3 stages, ADAA fast pass + fix-up list): try plain
  waveshaping without ADAA on stages where the alias rule still passes at 2x;
  a cheaper transfer function; remove the fix-up branch.
- **Networks per sample** (V1 network, tone stack): try lower-order or
  merged filter forms (for example a biquad cascade fitted to the network
  response for the knob values, derived in `hw_coeffs`, which only runs when a
  knob moves).
- **Resampling / DC guard / cab / glue**: smaller items; the cab runs at base
  rate already.
Measure each idea alone (score + cost) and record it in `## Changes tried`, keep
what passes and saves cycles, revert what does not. Do not spend the run on one
idea that will not pass.

## 7. Finish
- `ACCURACY: PASS` and the final cost table in the report, with the saving vs
  baseline in percent.
- Build for the pedal ends `ok`; give the free bytes.
- Run `.venv\Scripts\python.exe -m pytest tests -q -x --ignore=tests/host`
  and report the result (known unrelated failure:
  `tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx`).
- `## Status`: DONE or STOPPED, and one paragraph: what changed in the sound
  model, in plain words, and what you would try next.
