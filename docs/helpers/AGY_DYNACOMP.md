# Brief for Gemini (Antigravity): write the CF Dyna Comp DSP core

You are writing a real DSP effect for a Zoom G1X Four guitar pedal (TI C6745
DSP, float, ~375 MHz). Everything you need is set up; your job is ONE file
of C code that passes an automatic test. Read every step. Earlier helpers on
other kits went wrong by guessing, by editing files they were told not to
touch, and by losing work to quota limits.

## 0. First action
Create `docs/helpers/DYNACOMP_RESULT.md` with the headings
`## Status`, `## Scores`, `## Cost`, `## Design`, `## Problems`, and update it
after every test run (paste the scorer's last 6 lines and the date/time).
If you are cut off, this file is what survives.

## 1. The task
Implement the MXR Dyna Comp in `effects/common/dynacomp_g1.h`, replacing the
placeholder bodies, keeping the CONTRACT at the top of that file exactly
(type names, function names, arguments, meaning -- the fields INSIDE the
structs are yours to design).

The model to match is the reference chain in `tests/host/dynacomp_accuracy.cpp`,
function `reference()`. That chain IS the specification: CA3080
pre-emphasis high shelf (+3.5 dB above 2 kHz, Q 0.707) -> peak-detect envelope
(attack 5 ms, release 300 ms, pure exponential decay toward zero, mono peak
since the G1 is mono) -> an 8:1 gain law with a 6 dB soft knee and makeup
gain defined as "what a -12 dBFS signal actually loses" (not a function of
the knob -- see CompressorMath in the reference) -> ADAA tanh(x/1.2) OTA
output clip -> C5 de-emphasis (the EXACT inverse shelf, corner/1.5, gain
1/1.5) -> 80 Hz output high-pass -> output trim. No oversampling: the
desktop plugin never oversamples this pedal and neither should you.

The original desktop code is
`C:/Users/z/Documents/exhboost/VirtualPedalBoardEngine/Source/DynaCompProcessor.cpp`
(knob names and ranges in `PluginProcessor.cpp`'s "DynaComp" block;
`CompressorMath.h` for the shared gain law; `DynaCompMobileProcessor.h` +
`MobileDsp/DynaCompMobileCore.h` for a second, independently-written
restatement of the same circuit worth cross-checking yourself against if
anything in the desktop file is unclear): read it for understanding, do not
edit anything in that folder.

⚠ Knob naming: the hardware MXR Dyna Comp silkscreens its two knobs
"OUTPUT" and "SENSITIVITY". Comet Flower's source calls the second one
"Sustain" (parameter id `dynaCompSustain`) -- same control, different label.
Use `sustain` in code to match the source; call it what you like in any
UI-facing text.

## 2. The test loop (run from the repository root)
These are bash commands. In PowerShell use
`cmd /c "tests\host\build_dynacomp_accuracy.bat dynacomp --skip-ref"`.
```
cmd //c "tests\\host\\build_dynacomp_accuracy.bat dynacomp --skip-ref"
.venv/Scripts/python.exe tests/host/dynacomp_accuracy.py dynacomp
```
The first line compiles your header into the PC bench and renders 72 tests
(24 sines, 12 guitar-like plucks, 6 loud/quiet/loud steps, each at Sustain
0/5/10 and Output -6/+12 dB; the reference and input files already exist,
`--skip-ref` keeps them, never delete `build/host/dynacomp/ref*` or `in*`).
The second prints per-test numbers and ends with `ACCURACY: PASS` or `FAIL`.
Read the scorer's docstring for the exact criteria; in short: a residual
(candidate-minus-reference, relative to the reference) below -40 dB on
every test except the quietest (-30 dB there), and a gain-reduction-
trajectory error below 0.3 dB on every test.

**Your goal: `ACCURACY: PASS`, then the lowest STRETCH number
(worst pluck/step residual) you can get within the cost budget.** A careful,
direct float translation of the reference -- same structure, same constants,
no shortcuts -- is known to pass with worst residual -37.5 dB and worst GR
trajectory 0.06 dB (measured on this exact bench 2026-10-17). Coarsening the
peak detector to update every other sample (half rate, sample-and-hold) is
known to fail hard: worst residual -7.0 dB, worst GR trajectory 9.70 dB, 12
of 72 tests fail. Don't do that; run the detector every sample.

## 3. Pedal rules (the build rejects or the pedal misbehaves otherwise)
- Code runs on the pedal: **no libm at run time** (no sinf, tanf, powf,
  expf, logf, log1pf, sqrtf, tanhf). Use the inline helpers in
  `effects/common/ts808_core.h` (`ts_rcp`, `ts_exp_pos`, `ts_onepole_g`,
  `ts_clamp`) and `ts808_sd.h`, or polynomial approximations, or precomputed
  `static const float` tables in your header. The shelf/high-pass
  coefficients, the pow()-based dB<->linear conversions and the ADAA's
  log(cosh) all need libm-free replacements -- `ts_onepole_g` already gives
  you tan(w)/(1+tan(w)) without a call; you will need your own polynomial or
  table for `log(cosh(x))` and for `10^(x/20)`. Good examples of both kinds
  of replacement: `effects/common/ts808_core.h` (the whole file) and
  `effects/common/rat_g1.h` (the diode LUT, `rat_blob.h`).
- **No division** on hot paths (use `ts_rcp`). **No `switch`.** **No calls**
  to non-inline functions; mark helpers `TS_INLINE`.
- **Fixed loop counts only.** `DSP_RULES.md` section 3 also says "no
  data-dependent `if` per sample" -- but a compressor's envelope follower
  genuinely needs a different update rule above vs. below the current
  envelope (attack vs. release), and the existing RAT core (`rat_g1.h`,
  function `rat_core_stage`) uses exactly this kind of ternary for its slew
  limiter via `ts_clamp`, which is itself written with `?:`, not `if`.
  **Open question we did not resolve**: is a single ternary expression
  (`envelope = (peak > envelope) ? attack_update : release_update;`) an
  acceptable "select" in the DSP_RULES sense, or does it need to be
  restructured as a branchless blend? Our best reading is that ternaries
  like `ts_clamp`'s are fine and `if`/`switch` BLOCKS are what the rule
  targets, but we did not verify this against a real build + cycle count.
  If you hit trouble here, write what you tried in DYNACOMP_RESULT.md
  `## Problems` rather than guessing silently.
- Memory: this kit does not include an `effects/<name>/` pedal wrapper
  (manifest.json, kernel .c) -- only the shared header and its PC bench.
  Keep `sizeof(DynaCompState) + sizeof(DynaCompCoeffs)` well under the
  392-byte per-instance state budget in `docs/DSP_RULES.md` section 3; a
  correct implementation needs on the order of 10-15 floats total, nowhere
  close to that limit.

## 4. Reference provenance (read before you doubt a number)
The 2nd-order filter coefficients in `tests/host/dynacomp_accuracy.cpp`
(the high-shelf pair) use the public RBJ Audio EQ Cookbook / JUCE
`IIR::Coefficients::makeHighShelf` formula, written from well-established
public knowledge of that formula -- this machine has no checked-out
`JUCE/modules` to read the literal source against (searched; not found), so
this is flagged as an assumption rather than a verified match to the live
JUCE build. It affects only how closely THIS reference matches the desktop
plugin, not your bench: you are graded against `reference()` in
`dynacomp_accuracy.cpp`, full stop, however that function was derived.
First-order filters (the 80 Hz output HPF) use the TPT one-pole form
already established as exactly equivalent to JUCE's first-order filters by
the CF RAT bench (`rat_accuracy.cpp`'s `HP1` struct comment).

## 5. What you may edit
- `effects/common/dynacomp_g1.h` (your code), plus new headers you create
  named `effects/common/dynacomp_*.h`;
- `docs/helpers/DYNACOMP_RESULT.md`;
- scratch files under `build/scratch/sonnet_kits/`.
Nothing else. In particular do NOT edit `tests/host/dynacomp_accuracy.cpp`,
`tests/host/dynacomp_accuracy.py`, `build_dynacomp_accuracy.bat`, or any
other effect's files. Changing the test to pass is a failure of the task.

## 6. Hard rules
- **Never touch the pedal**: no MIDI ports; do not run `tools/pedal_g1.py`,
  `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  `make_fs_restore_updater.py`, `make_g1_image.py`, or any `.exe` other than
  the compiler the commands above call. This kit has no pedal build step
  (no `effects/dynacomp/manifest.json` exists) -- the PC bench in section 2
  is the whole loop. Do not create a pedal wrapper or run `tools/build_g1.sh`
  for this kit unless you are explicitly asked to.
- No git commits or pushes; Claude reviews and commits.
- Finish with a summary: PASS or FAIL, STRETCH number, and what you would
  try next.

## 7. Starting point: the placeholder's FAIL output
Run 2026-10-17, `effects/common/dynacomp_g1.h` as shipped (pass-through):
```
test                          residual dB  GR traj dB
pluck_f220_s00_o054                   1.8        6.95 residual GR
pluck_f220_s00_o072                  -2.5       11.77 residual GR
pluck_f220_s05_o054                   3.3       10.52 residual GR
pluck_f220_s10_o072                  -1.6       27.62 residual GR
sine_f110_a005_s00_o054               4.9        8.28 residual GR
sine_f110_a090_s05_o054              16.0       17.45 residual GR
step_s05_o054                        12.1       14.44 residual GR
step_s10_o072                        -5.5       26.35 residual GR
...
worst residual 16.1 dB (limit -40.0, -30.0 on GENTLE/a005 tests); worst GR trajectory 28.11 dB (limit 0.3)
STRETCH: worst pluck/step residual 12.1 dB (lower is better)
ACCURACY: FAIL (72 of 72 tests)
```
Every single test fails, as expected: pass-through applies no gain
reduction at all, so the "residual" is as loud as the signal itself.
