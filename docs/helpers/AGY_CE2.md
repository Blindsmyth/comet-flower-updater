# Brief for Gemini (Antigravity): write the CF CE-2 DSP core

You are writing a real DSP effect for a Zoom G1X Four guitar pedal (TI C6745
DSP, float, ~375 MHz). Everything you need is set up; your job is ONE file
of C code that passes an automatic test. Read every step. Earlier helpers on
other kits went wrong by guessing, by editing files they were told not to
touch, and by losing work to quota limits.

## 0. First action
Create `docs/helpers/CE2_RESULT.md` with the headings
`## Status`, `## Scores`, `## Cost`, `## Design`, `## Problems`, and update it
after every test run (paste the scorer's last 5 lines and the date/time).
If you are cut off, this file is what survives.

## 1. The task
Implement the Boss CE-2 chorus in `effects/common/ce2_g1.h`, replacing the
placeholder bodies, keeping the CONTRACT at the top of that file exactly
(type names, function names, arguments, meaning -- the fields INSIDE the
structs are yours to design).

The model to match is the reference chain in `tests/host/ce2_accuracy.cpp`,
function `reference()`. That chain IS the specification: pre-emphasis +15 dB
high shelf (979 Hz, Q 0.707) -> anti-alias HPF (48 Hz) + LPF cascade (6.6 kHz
1st order + 6.6 kHz Q 0.707) -> MN3007 BBD soft saturation (ADAA
tanh(0.7x)/0.7) -> BBD delay (Lagrange 3rd-order fractional read, center
12.8 ms, +-5 ms * Depth, triangle LFO smoothed by a 72 Hz one-pole) -> CTI
one-pole low-pass (cutoff sweeps with delay time against FIXED 7.8/17.8 ms
reference bounds -- the desktop hardcodes those two numbers regardless of
Depth, do not re-derive them) -> reconstruction HPF (14.6 Hz) + LPF cascade
(6.9 kHz 1st order + 6.9 kHz Q 0.707) -> de-emphasis (exact inverse shelf)
-> 50/50 dry/wet mix (wet scaled by Mix). ALL OF THIS RUNS AT 44.1 kHz
DIRECTLY: unlike the CF Mistress kit, the desktop CE-2 plugin never
oversamples either (`ChorusProcessor.h` has no `juce::dsp::Oversampling`
member), so there is no rate choice to make here -- match the reference at
the pedal's own rate.

The original desktop code is
`C:/Users/z/Documents/exhboost/VirtualPedalBoardEngine/Source/ChorusProcessor.{h,cpp}`
(knob names/ranges in `PluginProcessor.cpp`'s "Chorus" block: Rate 0.1-8.0
APVTS units mapped linearly to an actual LFO frequency of 0.1-3.5 Hz, Depth
0-1, Mix 0-1; `ChorusMobileProcessor.h` + its `MobileDsp/ChorusMobileCore.h`
show a second, independently-written restatement of the same circuit that
is also mono-in (it is worth cross-checking yourself against if anything in
the desktop file is unclear, but DO NOT port its simplifications -- see
section 4): read it for understanding, do not edit anything in that folder.
The desktop is stereo with a 90-degree LFO phase offset between channels;
the G1 is mono, so only channel 0's phase (0, the default reset value)
applies -- same resolution the CF Mistress kit's brief uses.

## 2. The test loop (run from the repository root)
These are bash commands. In PowerShell use
`cmd /c "tests\host\build_ce2_accuracy.bat ce2 --skip-ref"`.
```
cmd //c "tests\\host\\build_ce2_accuracy.bat ce2 --skip-ref"
.venv/Scripts/python.exe tests/host/ce2_accuracy.py ce2
```
The first line compiles your header into the PC bench and renders 72 tests
(sine, an 8 kHz probe tone, pluck, and chirp, each at a grid of Rate/Depth/
Mix); `--skip-ref` keeps the existing reference files, never delete
`build/host/ce2/ref*`. The second prints per-test numbers and ends with
`ACCURACY: PASS` or `FAIL`.

**Read the scorer's docstring before you argue with a FAIL.** It gates on
THREE thresholds (-50 dB, -25 dB, or -40 dB) depending on the test, for the
same reason the CF Mistress kit's scorer does: at the fastest Rate combined
with deep modulation, a HONEST float port still diverges from the double
reference by a legitimate float-vs-double floor (measured -27.2 dB, same for
a correct Lagrange port and a degraded linear-interpolation port -- this is
NOT an interpolation defect, it is the comb filter's response changing fast
enough that tiny timing differences become real amplitude differences). The
tier that actually matters for your interpolation code is "INTERP" (the
`sine8000_r001_*` tests, an 8 kHz probe at the slowest Rate): a careful
Lagrange 3rd-order port measures -57.3 dB there; the SAME port with linear
interpolation instead measures only -44.8 dB on its worst case and fails
that tier on 3 of its 6 tests. **Your goal: `ACCURACY: PASS`, then the
lowest STRETCH number (worst pluck/chirp/8kHz residual) you can get.**

## 3. Pedal rules (the build rejects or the pedal misbehaves otherwise)
- Code runs on the pedal: **no libm at run time** (no sinf, cosf, tanf,
  expf, log1pf, tanhf, sqrtf). Use `effects/common/ts808_core.h`'s helpers
  (`ts_onepole_g` for the TPT one-pole filters, `ts_rcp`, `ts_exp_pos`) and
  your own polynomial/table for `tanh`, `log(cosh())` (the BBD saturation),
  and the RBJ biquad coefficients' `sin`/`cos`/`sqrt` (the pre/de-emphasis
  shelves and the two 2nd-order low-passes). `effects/common/rat_g1.h` and
  `effects/common/ts808_exact.h` are worked examples of both kinds of
  replacement.
- **No division** on hot paths (`ts_rcp`). **No `switch`.** **No calls** to
  non-inline functions; mark helpers `TS_INLINE`. **Fixed loop counts only.**
- **Memory -- same open question the CF Mistress kit raises, worse here.**
  A correct implementation needs a fractional-delay ring buffer covering
  >= 17.8 ms at 44.1 kHz: about 785 samples, ~3.1 KB as `float[]`. That is
  well over the 392-byte per-instance state budget in `docs/DSP_RULES.md`
  section 3. See `docs/helpers/AGY_MISTRESS.md` section 3 and
  `docs/helpers/DELAY_MEM_BRIEF_2026-10-17.md` /
  `DELAY_MEM_SONNET_2026-10-17.md` for the unresolved investigation into
  where a CF effect gets a bigger read/write buffer on the pedal. This kit
  does not include an `effects/ce2/` pedal wrapper (no manifest.json, no
  kernel .c) -- only the shared header and its PC bench -- so you do NOT
  need to solve the on-pedal buffer question to pass this bench.

## 4. Do not copy the mobile core's simplifications
`ChorusMobileProcessor.h`'s `MobileDsp::ChorusMobileCore` is a real, shipped,
cheaper restatement of this same pedal, and reading it will teach you useful
things (how to structure a mono-in/stereo-out BBD chorus cheaply). But it is
a DIFFERENT, intentionally leaner line -- it is not what this bench grades
you against. The reference you must match is `reference()` in
`tests/host/ce2_accuracy.cpp`, which restates the DESKTOP `ChorusProcessor.cpp`
chain (the biquad shelf pair, the 3-stage AA/reconstruction filter cascades,
the Lagrange-3 BBD delay). If the mobile core differs from the desktop
anywhere (check before assuming it matches), follow the desktop/the bench,
not the mobile core.

## 5. What you may edit
- `effects/common/ce2_g1.h` (your code), plus new headers you create named
  `effects/common/ce2_*.h`;
- `docs/helpers/CE2_RESULT.md`;
- scratch files under `build/scratch/sonnet_kits/`.
Nothing else. In particular do NOT edit `tests/host/ce2_accuracy.cpp`,
`tests/host/ce2_accuracy.py`, `build_ce2_accuracy.bat`, or any other
effect's files. Changing the test to pass is a failure of the task.

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
Run 2026-10-17, `effects/common/ce2_g1.h` as shipped (pass-through):
```
test                 tier      residual dB
chirp_r001_d03_m05   DEFAULT           0.1 residual
chirp_r001_d03_m10   DEFAULT           0.1 residual
...
sine8000_r080_d10_m05 LOOSE             0.0 residual
sine8000_r080_d10_m10 LOOSE             0.0 residual

worst INTERP 0.0 dB (limit -50.0); worst LOOSE 2.2 dB (limit -25.0); worst DEFAULT 10.0 dB (limit -40.0)
STRETCH: worst pluck/chirp/8kHz residual 10.0 dB (lower is better)
ACCURACY: FAIL (72 of 72 tests)
```
Every single test fails: pass-through does no chorusing at all, so the
reference's dry+wet mix (even at the gentlest Mix) diverges from raw
passthrough on every test.
