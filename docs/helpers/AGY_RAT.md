# Brief for Gemini (Antigravity): write the CF RAT DSP core

You are writing a real DSP effect for a Zoom G1X Four guitar pedal (TI C6745
DSP, float, ~375 MHz). Everything you need is set up; your job is ONE file
of C code that passes an automatic test. Read every step. Earlier helpers
went wrong by guessing, by editing files they were told not to touch, and
by losing work to quota limits.

## 0. First action
Create `docs/helpers/RAT_RESULT.md` with the headings
`## Status`, `## Scores`, `## Cost`, `## Design`, `## Problems`, and update it
after every test run (paste the scorer's last 3 lines and the date/time).
If you are cut off, this file is what survives.

## 1. The task
Implement the ProCo RAT in `effects/common/rat_g1.h`, replacing the
placeholder bodies, keeping the CONTRACT at the top of that file exactly
(type names, function names, arguments, meaning).
The model to match is the reference chain in `tests/host/rat_accuracy.cpp`,
function `reference()`. That chain IS the specification:
input high-pass 10 Hz -> gain stage with the two RC legs (1539 Hz, 60.5 Hz,
Rf from the Distortion knob) -> 100 pF feedback-cap low-pass on the boost ->
LM308 slew limit 0.3 V/us -> op-amp bandwidth low-pass (2nd-order SVF) ->
rail clamp +-4 V -> 1N914 shunt diode pair (Rs 68 ohm) -> Filter (tone)
low-pass (2nd-order SVF) -> x 1.67 -> x vol.
The original desktop code is
`C:/Users/z/Documents/exhboost/VirtualPedalBoardEngine/Source/RatProcessor.cpp`
(and the diode table in `ADAAWaveshaper.h`, class `DiodeFeedbackClipper`):
read it for understanding, do not edit anything in that folder.

## 2. The test loop (run from the repository root)
These are bash commands. In PowerShell use
`cmd /c "tests\hostuild_rat_accuracy.bat rat --skip-ref"` and
`& "C:\Program Files\Gitinash.exe" tools/build_g1.sh ratx "CF RAT" "CF/RAT"`.
```
cmd //c "tests\\host\\build_rat_accuracy.bat rat --skip-ref"
.venv/Scripts/python.exe tests/host/rat_accuracy.py rat
```
The first line compiles your header into the PC bench and renders 54 tests
(the reference files already exist; `--skip-ref` keeps them, never delete
`build/host/rat/ref*`). The second prints per-test numbers and ends with
`ACCURACY: PASS` or `FAIL`. Read the scorer's docstring for the criteria.
**Your goal: `ACCURACY: PASS`, then the lowest STRETCH number you can get
within the cost budget.** A plain, careful 8x-oversampled implementation
of the chain is known to pass; 4x is known to fail.

## 3. Pedal rules (the build rejects or the pedal misbehaves otherwise)
- Code runs on the pedal: **no libm at run time, in either function**
  (no sinf, tanf, powf, expf, logf, sqrtf). Use the inline helpers in
  `effects/common/ts808_core.h` (`ts_rcp`, `ts_exp_pos`, `ts_onepole_g`,
  `ts_clamp`) and `ts808_sd.h` (`sd_expf`), or polynomial approximations,
  or precomputed `static const float` tables in your header.
- **No division** on hot paths (use `ts_rcp`). **No `switch`.** **No calls**
  to non-inline functions; mark helpers `TS_INLINE`.
- **No data-dependent `if` in the per-sample path**: use `ts_clamp` /
  `fminf`-style selects (the slew limiter and rail clamp included). Fixed
  loop counts only.
- Oversampling building blocks: `effects/common/os_hbiir.h` (polyphase IIR
  half-band 2x stages, used by the shipped Hiwatt). Good example of a
  complete pedal core: `effects/common/ts808_exact.h`.
- Diode pair: no Newton iterations at run time. Use a lookup table over
  the shunt solution (as the desktop does), or a fitted closed form.
  Keep tables small (< 8 KB total): the DSP's fast data cache is 16 KB.
- Memory: `sizeof(RatState)` plus 16 bytes must fit 392 bytes. After you
  change `RatState`, set `"state_bytes"` in `effects/ratx/manifest.json` to
  `sizeof(RatState) + 16`, rounded up to a multiple of 4. That number is
  the ONLY thing you may change in that manifest.

## 4. Build for the pedal and measure cost
```
bash tools/build_g1.sh ratx "CF RAT" "CF/RAT"
.venv/Scripts/python.exe tools/c6x_cycles.py /c/Users/z/zoomlab/stomphacks/effects/ratx/build/RATX.asm
```
The build must end with "CF RAT ready". `c6x_cycles.py` prints cycles per
code block; multiply each loop's block by its trip count (16 samples per
block, times your oversampling factor) and add them up. **Budget: 15,000
cycles per 16-sample block, hard limit 20,000.** Write the arithmetic in
RAT_RESULT.md `## Cost`. Also note `.text` size from
`/c/Users/z/zoomlab/stomphacks/effects/ratx/build/REPORT.md` (keep it
under 18 KB).

## 5. What you may edit
- `effects/common/rat_g1.h` (your code), plus new headers you create named
  `effects/common/rat_*.h`;
- the `"state_bytes"` value in `effects/ratx/manifest.json`;
- `docs/helpers/RAT_RESULT.md`;
- scratch files under `build/agy3/`.
Nothing else. In particular do NOT edit `tests/host/rat_accuracy.cpp`,
`tests/host/rat_accuracy.py`, `build_rat_accuracy.bat`,
`effects/ratx/ratx.c`, or any other effect. Changing the test to pass is
a failure of the task.

## 6. Hard rules
- **Never touch the pedal**: no MIDI ports; do not run `tools/pedal_g1.py`,
  `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  `make_fs_restore_updater.py`, `make_g1_image.py`, or any `.exe` other than
  the compilers the commands above call.
- No git commits or pushes; Claude reviews and commits.
- Finish with a summary: PASS or FAIL, STRETCH number, cycles per block,
  state bytes, .text size, and what you would try next.
