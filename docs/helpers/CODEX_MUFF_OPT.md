# Brief for Codex: make the CF Muff fit the pedal (size and cycles)

## 0. First action
Append a section `## Codex optimisation (date)` to `docs/helpers/MUFF_RESULT.md`
and update it after every measurement (bench verdict lines, .text size, cycle
arithmetic). Your usage cap can end the run at any time; that file survives.

## 1. Context (read first)
- `docs/helpers/MUFF_RESULT.md`: state of the work and Claude's review.
- `effects/common/muff_g1.h`: the CF Muff core (Gemini's port of Comet
  Flower's FuzzMobileCore, '74 Violet Ram's Head). Accuracy is excellent:
  bench PASS and every stretch target met. Keep it that way.
- `docs/helpers/AGY_MUFF.md` sections 2-4: the bench, the pedal rules
  (no libm, no division on hot paths, no switch, no calls, no data-dependent
  branches in the per-sample path) and how to build and count cycles.
- `effects/common/rat_g1.h`: another core, which loops over its oversampled
  samples (small code).
- `recon/14_effect_memory.md`, top boxes: measured on the pedal, a kernel's
  cache refill costs 19-25% on top of its static count, so smaller code also
  runs faster.

## 2. Goals, in order
1. **Build for the pedal.** `.text` is 22,368 B, cap 17,632 B
   (`bash tools/build_g1.sh muffx "CF Muff" "CF/MUFF"` must end with
   "CF Muff ready"). The four oversampled samples are processed as four
   inlined copies of `muff_stage`; a loop will shrink it.
2. **Cycles: <= 15,000 per 16-sample block (hard limit 20,000)**, static
   count, now ~29k. The cost is a serial dependency chain: each clip stage's
   rhs needs its previous output (table load + float latencies), ~400 cycles
   per stage call. Ideas, yours to judge:
   - software-pipeline ACROSS the two clip stages: run stage 1 of sample
     n+1 alongside stage 2 of sample n (they are independent), and the
     linear filters of the next sample alongside the nonlinear chain;
   - process the 64 oversampled samples of a block in a structure the
     compiler can schedule (restrict pointers, `#pragma MUST_ITERATE`,
     local copies of state in registers for the whole block);
   - fewer selects in `muff_clip_lookup` (e.g. clamp the index and blend the
     extrapolation only when needed, without branches);
   - cheaper but bench-passing pieces (e.g. the ADAA quotient, the rails).
3. Accuracy must stay `ACCURACY: PASS`; report the STRETCH count too.

## 3. Measure every change
```
cmd //c "tests\\host\\build_muff_accuracy.bat muff --skip-ref"
.venv/Scripts/python.exe tests/host/muff_accuracy.py muff
bash tools/build_g1.sh muffx "CF Muff" "CF/MUFF"
T=build/codex4/cc; rm -rf $T; mkdir -p $T
cp effects/muffx/muffx.c effects/common/*.h /c/Users/z/zoomlab/stomphacks/effects/muffx/build/sh_params.h $T/
CG=/c/Users/z/ti/ti-cgt-c6000_8.5.0.LTS
(cd $T && $CG/bin/cl6x --c99 --opt_level=2 --silicon_version=6740 --abi=eabi --mem_model:const=data --mem_model:data=far_aggregates -k -I$CG/include -c muffx.c)
.venv/Scripts/python.exe tools/c6x_cycles.py $T/muffx.asm
```
(PowerShell: `cmd /c "tests\host\build_muff_accuracy.bat muff --skip-ref"`.)
For a software-pipelined loop the KERNEL block runs (trips - stages + 1)
times; state your arithmetic. Never delete `build/host/muff/ref*`, `ref64*`
or `mob*`.

## 4. What you may edit
- `effects/common/muff_g1.h`, new `effects/common/muff_*.h`;
- `tools/gen_muff_blob.cpp` and its outputs `effects/common/muff_blob.h`,
  `effects/muffx/blob.bin` (keep the const_blob method; no DATA_SECTION);
- `"state_bytes"` and the `const_blob` line of `effects/muffx/manifest.json`
  (`sizeof(MuffState) + 16` must stay <= 388);
- `docs/helpers/MUFF_RESULT.md`; scratch under `build/codex4/` only.
Do NOT edit the bench (`tests/host/muff_*`, `build_muff_accuracy.bat`),
`effects/muffx/muffx.c`, or anything else. Changing the test to pass is a
failure.

## 5. Hard rules
- **Never touch the pedal**: no MIDI ports; do not run `tools/pedal_g1.py`,
  `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`, `make_g1_image.py`,
  `make_fs_restore_updater.py`, or any `.exe` other than the compilers and
  the bench executable the commands above build.
- No git commits or pushes; Claude reviews and commits.
- Finish with: bench verdict + STRETCH, .text size, cycles/block with the
  arithmetic, state bytes, and what you would try next.
