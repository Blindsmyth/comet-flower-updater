# Brief for Gemini (Antigravity): write the CF Mistress DSP core

You are writing a real DSP effect for a Zoom G1X Four guitar pedal (TI C6745
DSP, float, ~375 MHz). Everything you need is set up; your job is ONE file
of C code that passes an automatic test. Read every step. Earlier helpers on
other kits went wrong by guessing, by editing files they were told not to
touch, and by losing work to quota limits.

## 0. First action
Create `docs/helpers/MISTRESS_RESULT.md` with the headings
`## Status`, `## Scores`, `## Cost`, `## Design`, `## Problems`, and update it
after every test run (paste the scorer's last 5 lines and the date/time).
If you are cut off, this file is what survives.

## 1. The task
Implement the EHX Electric Mistress V2 flanger in `effects/common/mistress_g1.h`,
replacing the placeholder bodies, keeping the CONTRACT at the top of that
file exactly (type names, function names, arguments, meaning -- the fields
INSIDE the structs are yours to design).

The model to match is the reference chain in `tests/host/mistress_accuracy.cpp`,
function `reference()`. That chain IS the specification: 80 Hz coupling-cap
HPF (feeds dry and wet) -> LFO phase accumulator (deterministic start phase
0) -> two-segment exponential-triangle LFO shape (`mistressLfoShape`), OR in
Matrix mode a static delay set directly by Range -> pre-BBD anti-alias LPF
cascade (12 kHz 1st order + 12 kHz Q 0.707) -> feedback sum through an 18V
op-amp ADAA tanh clip -> BBD delay, 0.64-6.4 ms, read with Lagrange 3rd-order
fractional interpolation -> CTI one-pole low-pass (cutoff sweeps 8 kHz at
short delay to 2.5 kHz at long) -> 5 Hz DC-block HPF + reconstruction LPF
cascade (8 kHz 1st order + 8 kHz Q 0.707 + 8.5 kHz Q 0.5) -> dry/wet mix
(50/50 at Mix=1). ALL OF THIS RUNS AT 44.1 kHz DIRECTLY -- no internal
oversampling in the reference (see section 4).

The original desktop code is
`C:/Users/z/Documents/exhboost/VirtualPedalBoardEngine/Source/FlangerProcessor.{h,cpp}`
(knob names/ranges in `PluginProcessor.cpp`'s "Flanger" block: Rate 0.01-10 Hz
direct, Range/depth 0-1, Color/feedback 0-0.95, Matrix bool, Mix 0-1): read it
for understanding, do not edit anything in that folder. The desktop runs this
same chain at 4x (176.4 kHz) through a JUCE FIR oversampler purely for extra
alias headroom on the ADAA feedback clip -- that detail is NOT part of this
kit's spec; see section 4.

## 2. The test loop (run from the repository root)
These are bash commands. In PowerShell use
`cmd /c "tests\host\build_mistress_accuracy.bat mistress --skip-ref"`.
```
cmd //c "tests\\host\\build_mistress_accuracy.bat mistress --skip-ref"
.venv/Scripts/python.exe tests/host/mistress_accuracy.py mistress
```
The first line compiles your header into the PC bench and renders 81 tests
(sine, pluck, chirp, and an 8 kHz probe tone, each at a grid of Rate/Range/
Color, plus a Matrix-mode grid); `--skip-ref` keeps the existing reference
files, never delete `build/host/mistress/ref*`. The second prints per-test
numbers and ends with `ACCURACY: PASS` or `FAIL`.

**Read the scorer's docstring before you argue with a FAIL.** It gates on
THREE different thresholds depending on the test (-55 dB, -30 dB, or -40 dB)
because a full-depth, fast-ish, high-feedback setting pushes the BBD feedback
loop close enough to its stability edge that float-vs-double rounding alone
-- not a defect -- makes any correct port diverge from the reference by
tens of dB there; the scorer already accounts for this (the "LOOSE" tier).
The tier that actually matters for your interpolation code is "INTERP"
(the `sine8000_r001_*` tests): a careful Lagrange 3rd-order port measures
-64 dB there; the SAME port with linear interpolation instead measures only
-44.6 dB and fails that tier outright. **Your goal: `ACCURACY: PASS`, then
the lowest STRETCH number (worst pluck/chirp residual) you can get.**

## 3. Pedal rules (the build rejects or the pedal misbehaves otherwise)
- Code runs on the pedal: **no libm at run time** (no sinf, cosf, tanf,
  expf, log1pf, tanhf). Use `effects/common/ts808_core.h`'s helpers
  (`ts_onepole_g` for the TPT one-pole filters' tan-based coefficient,
  `ts_rcp`, `ts_exp_pos`) and your own polynomial/table for `tanh` and
  `log(cosh())` in the feedback-path ADAA, and for the RBJ biquad
  coefficients' `sin`/`cos`. `effects/common/rat_g1.h` and
  `effects/common/ts808_exact.h` are worked examples of both kinds of
  replacement.
- **No division** on hot paths (`ts_rcp`). **No `switch`.** **No calls** to
  non-inline functions; mark helpers `TS_INLINE`. **Fixed loop counts only.**
- **Memory -- this is the open question we did not resolve.** A correct
  implementation needs a fractional-delay ring buffer covering >= 6.4 ms at
  44.1 kHz: about 290 samples, ~1.2 KB as `float[]`. That is well over the
  392-byte per-instance state budget in `docs/DSP_RULES.md` section 3, which
  stock G1 drives (and this project's own RAT/Hiwatt/T808 kits) fit inside
  without a separate buffer. `docs/DSP_RULES.md` section 3 notes a large
  per-slot work buffer (`entry[5]..[8]` are callbacks; recon/14 mentions a
  fixed 0x81330-byte region) but says "no verified extra per-effect
  allocation service... design and test any separate allocation explicitly."
  `docs/helpers/DELAY_MEM_BRIEF_2026-10-17.md` and
  `DELAY_MEM_SONNET_2026-10-17.md` are an ACTIVE, UNRESOLVED investigation
  into exactly this question for a different effect (CF Delay). This kit
  does not include an `effects/mistress/` pedal wrapper (no manifest.json,
  no kernel .c) -- only the shared header and its PC bench -- so you do NOT
  need to solve the on-pedal buffer question to pass this bench. If you are
  asked to wire this into a real pedal build later, read those two files
  first and write what you learn into `MISTRESS_RESULT.md` rather than
  guessing at a buffer location.

## 4. Why the reference runs at 44.1 kHz, not the desktop's 4x
The desktop plugin oversamples this chain 4x through a JUCE FIR-equiripple
filter, purely to suppress aliasing from the feedback-path ADAA clip before
it reaches the BBD delay. Every formula inside the chain (LFO phase
increment, delay-in-samples, CTI cutoff, filter cutoffs) is written in terms
of "the rate this runs at" and is equally well-defined at 44.1 kHz directly.
Rendering the reference at the desktop's 4x rate would force your candidate
to reproduce the JUCE FIR oversampler's exact group delay to avoid comparing
misaligned samples -- extra work the pedal gains nothing from. So the
reference in `mistress_accuracy.cpp` runs the whole chain at 44.1 kHz, and
your `mistress_process()` must match it there, sample for sample, zero added
latency. If you choose to internally oversample anyway (say, for extra
alias suppression on the feedback clip), it must stay sample-synchronous
with the input/output, or the scorer's direct sample comparison will
penalize the resulting shift even if your DSP is otherwise correct.

## 5. What you may edit
- `effects/common/mistress_g1.h` (your code), plus new headers you create
  named `effects/common/mistress_*.h`;
- `docs/helpers/MISTRESS_RESULT.md`;
- scratch files under `build/scratch/sonnet_kits/`.
Nothing else. In particular do NOT edit `tests/host/mistress_accuracy.cpp`,
`tests/host/mistress_accuracy.py`, `build_mistress_accuracy.bat`, or any
other effect's files. Changing the test to pass is a failure of the task.

## 6. Hard rules
- **Never touch the pedal**: no MIDI ports; do not run `tools/pedal_g1.py`,
  `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  `make_fs_restore_updater.py`, `make_g1_image.py`, or any `.exe` other than
  the compiler the commands above call. This kit has no pedal build step --
  the PC bench in section 2 is the whole loop. Do not create a pedal wrapper
  or run `tools/build_g1.sh` for this kit unless explicitly asked to.
- No git commits or pushes; Claude reviews and commits.
- Finish with a summary: PASS or FAIL, STRETCH number, and what you would
  try next.

## 7. Starting point: the placeholder's FAIL output
Run 2026-10-17, `effects/common/mistress_g1.h` as shipped (pass-through):
```
test                     tier      residual dB
chirp_r001_d03_f00       DEFAULT          -9.8 residual
chirp_r010_d03_f00       DEFAULT          -8.8 residual
...
sine8000_r001_d03_f00    INTERP          -11.9 residual
sine8000_r010_d10_f09    LOOSE           -11.9 residual
...
worst INTERP -11.8 dB (limit -55.0); worst LOOSE -4.3 dB (limit -30.0); worst DEFAULT -2.8 dB (limit -40.0)
STRETCH: worst pluck/chirp residual -4.3 dB (lower is better)
ACCURACY: FAIL (81 of 81 tests)
```
Every single test fails: pass-through does no flanging at all, so the
reference's dry+wet mix (even at 40% wet) diverges from raw passthrough on
every test.
