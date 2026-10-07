# Brief for Gemini (Antigravity): write the CF Muff DSP core

You are writing a real DSP effect for a Zoom G1X Four guitar pedal (TI C6745
DSP, float, ~375 MHz). Everything you need is set up; your job is ONE file
of C code that passes an automatic test. Read every step. Earlier helpers
went wrong by guessing, by editing files they were told not to touch, and
by losing work to quota limits.

## 0. First action
Create `docs/helpers/MUFF_RESULT.md` with the headings
`## Status`, `## Scores`, `## Cost`, `## Design`, `## Problems`, and update it
after every test run (paste the scorer's last 3 lines and the date/time).
If you are cut off, this file is what survives.

## 1. The task
Implement the '74 Violet Ram's Head Big Muff in `effects/common/muff_g1.h`,
replacing the placeholder bodies, keeping the CONTRACT at the top of that
file exactly.

The model is Comet Flower's own mobile core, which the bench uses as its
reference (at 32x/64x) and as its yardstick (at 4x):
`C:/Users/z/Documents/exhboost/VirtualPedalBoardEngine/Source/MobileDsp/FuzzMobileCore.h`
(read it first; it is short), with
`../ADAAWaveshaper.h` class `WaveshaperFunctions::DiodeCapFeedbackStage`
(the clip stage: `build()` tabulates the solution offline, `process()` and
`lookup()` are the per-sample work), `../ToneStackMath.h` (`muffTone`), and
`../MuffCircuit.h` (all component constants). Read, do not edit, anything in
that folder. `tests/host/muff_ref.h` shows exactly what the reference runs.

What the port must do:
- the same chain as `FuzzMobileCore::stage()`: input HP 4 Hz -> Miller LP
  1.2 kHz -> x stage1Gain -> asymmetric rails -> clip1HP (corner depends on
  Sustain) -> x drive -> clip stage 1 -> clip2HP 94 Hz -> x stage3Gain ->
  clip stage 2 -> tone biquad -> recovery HP 4 Hz -> x 4.5 x volume,
  at 4x oversampling (`effects/common/os_hbiir.h` half-band stages; the CF
  RAT core `effects/common/rat_g1.h` shows how to chain them).
- The clip stages' tables depend on the oversampled rate (176.4 kHz): they
  must be generated OFFLINE at that rate with the exact `build()` math and
  shipped as data. **256 cells per stage is known to pass the gate** (the
  bench's feasibility check). Each cell is v, w, V (3 floats; drop the pad).
- Coefficients that need tan/pow/the tone-network maths (the Sustain-
  dependent clip1HP corner, the tone biquad's 5 coefficients) become
  precomputed tables over the knob (e.g. 256 points), interpolated in
  `muff_coeffs`, exactly like `rat_coeffs` does.
- The rails (2 tanh(v/2) for v >= 0, 7 tanh(v/7) below) need a table or a
  polynomial: no libm at run time.

### How tables are shipped (do it exactly like CF RAT)
Write a generator (Python in `tools/gen_muff_blob.py`, or C++ compiled with
`/I` to the VirtualPedalBoardEngine Source folder so it uses the real
`build()` maths) that writes BOTH:
- `effects/muffx/blob.bin` (float32 little-endian, all tables back to back),
- `effects/common/muff_blob.h` with
  `#if defined(__TI_COMPILER_VERSION__)  extern const float muff_blob[];`
  `#else  static const float muff_blob[N] = {...};  #endif` and `#define`
  offsets into it, exactly as `tools/gen_rat_blob.py` /
  `effects/common/rat_blob.h` do (print floats with `%.9e` so 0 is `0.0e+00f`).
Then add to `effects/muffx/manifest.json`:
`"const_blob": { "symbol": "muff_blob", "words": N, "init": "blob.bin" },`
**Do NOT use `#pragma DATA_SECTION`** or put tables in `.text`: the
const_blob path is the one proven on the pedal. Keep the blob <= 12 KB.

## 2. The test loop (run from the repository root)
These are bash commands. In PowerShell use
`cmd /c "tests\host\build_muff_accuracy.bat muff --skip-ref"` and
`& "C:\Program Files\Git\bin\bash.exe" tools/build_g1.sh muffx "CF Muff" "CF/MUFF"`.
```
cmd //c "tests\\host\\build_muff_accuracy.bat muff --skip-ref"
.venv/Scripts/python.exe tests/host/muff_accuracy.py muff
```
The first line compiles your header into the PC bench and renders 54 tests
(the reference files already exist; `--skip-ref` keeps them, never delete
`build/host/muff/ref*`, `ref64*` or `mob*`). The second prints per-test numbers and ends with
`ACCURACY: PASS` or `FAIL`. Read the scorer's docstring for the criteria.
**Your goal: `ACCURACY: PASS` (at least as accurate as Comet Flower's
mobile Muff on every test), then as many STRETCH tests as you can within the
cost budget.** A faithful 4x port with 256-cell tables is known to pass.
The bench takes ~75 s with the references; with --skip-ref only your model
is rebuilt.

## 3. Pedal rules (the build rejects or the pedal misbehaves otherwise)
- Code runs on the pedal: **no libm at run time, in either function**
  (no sinf, tanf, powf, expf, logf, sqrtf). Use the inline helpers in
  `effects/common/ts808_core.h` (`ts_rcp`, `ts_exp_pos`, `ts_onepole_g`,
  `ts_clamp`) and `ts808_sd.h` (`sd_expf`), or polynomial approximations,
  or precomputed `static const float` tables in your header.
- **No division** on hot paths (use `ts_rcp`). **No `switch`.** **No calls**
  to non-inline functions; mark helpers `TS_INLINE`.
- **No data-dependent `if` in the per-sample path**: use `ts_clamp` /
  `fminf`-style selects (rail limiter and clamps included). Fixed
  loop counts only.
- Oversampling building blocks: `effects/common/os_hbiir.h` (polyphase IIR
  half-band 2x stages, used by the shipped Hiwatt). Good example of a
  complete pedal core: `effects/common/ts808_exact.h`.
- No Newton iterations at run time: the clip stages read their tables.
- Memory: `sizeof(MuffState)` plus 16 bytes must fit 388 bytes. After you
  change `MuffState`, set `"state_bytes"` in `effects/muffx/manifest.json` to
  `sizeof(MuffState) + 16`, rounded up to a multiple of 4. `state_bytes` and
  the `const_blob` line are the ONLY things you may change in that manifest.

## 4. Build for the pedal and measure cost
```
bash tools/build_g1.sh muffx "CF Muff" "CF/MUFF"
# kernel assembly (the build folder's MUFFX.asm is only the scaffold):
T=build/agy4/cc; rm -rf $T; mkdir -p $T
cp effects/muffx/muffx.c effects/common/*.h /c/Users/z/zoomlab/stomphacks/effects/muffx/build/sh_params.h $T/
CG=/c/Users/z/ti/ti-cgt-c6000_8.5.0.LTS
(cd $T && $CG/bin/cl6x --c99 --opt_level=2 --silicon_version=6740 --abi=eabi --mem_model:const=data --mem_model:data=far_aggregates -k -I$CG/include -c muffx.c)
.venv/Scripts/python.exe tools/c6x_cycles.py $T/muffx.asm
```
For a software-pipelined loop ("PIPED LOOP PROLOG/KERNEL/EPILOG"), the
kernel block runs (trips - stages + 1) times; counting it for every trip
overstates the cost (an upper bound is fine, say which you used).
The build must end with "CF Muff ready". `c6x_cycles.py` prints cycles per
code block; multiply each loop's block by its trip count (16 samples per
block, times your oversampling factor) and add them up. **Budget: 15,000
cycles per 16-sample block, hard limit 20,000.** Write the arithmetic in
MUFF_RESULT.md `## Cost`. Also note `.text` size from
`/c/Users/z/zoomlab/stomphacks/effects/muffx/build/REPORT.md` (keep it
under 18 KB).

## 5. What you may edit
- `effects/common/muff_g1.h` (your code), plus `effects/common/muff_blob.h`
  and other new headers named `effects/common/muff_*.h`;
- `tools/gen_muff_blob.py` (or a C++ generator under `tools/`), and the
  `effects/muffx/blob.bin` it writes;
- `"state_bytes"` and the `const_blob` line in `effects/muffx/manifest.json`;
- `docs/helpers/MUFF_RESULT.md`;
- scratch files under `build/agy4/` ONLY (never in the repository root).
Nothing else. In particular do NOT edit `tests/host/muff_accuracy.cpp`,
`tests/host/muff_accuracy.py`, `tests/host/muff_ref.h`,
`build_muff_accuracy.bat`, `effects/muffx/muffx.c`, or any other effect.
Changing the test to pass is a failure of the task.

## 6. Hard rules
- **Never touch the pedal**: no MIDI ports; do not run `tools/pedal_g1.py`,
  `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  `make_fs_restore_updater.py`, `make_g1_image.py`, or any `.exe` other than
  the compilers the commands above call.
- No git commits or pushes; Claude reviews and commits.
- Finish with a summary: PASS or FAIL, STRETCH number, cycles per block,
  state bytes, .text size, and what you would try next.
