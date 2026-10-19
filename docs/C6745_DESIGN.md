# Designing CF effects for the C6745

Owner decision (2026-10-18): CF effects are designed around this DSP from the start, not ported from the circuit
model and squeezed afterwards. The circuit (or the reference code) defines the sound; this page defines the
shape of the code that makes it. First test: CF Master, one effect over all 5 slots running more than 5 effects
inside it. Safety and install rules stay in `docs/DSP_RULES.md`.

Facts marked *(TI)* are from TI's C674x documentation (CPU and instruction set guide SPRUFE8, C6745 datasheet)
and still need to be checked against those documents; the rest is measured on this pedal or read from its
firmware.

## 1. The chip

| What | Value | Source |
|---|---|---|
| DSP | TMS320C6745, C674x core, 375 MHz grade | board photos, recon/07 |
| Clock | SYSCLK1 364.8 MHz (19.2 MHz x 19) | AIS PLL header + CF ClkT, docs/CYCLE_BUDGET_2026-10-15.md |
| Block | 16 frames x 2 ch float32, in place, 44.1 kHz: **132,354 cycles** | same |
| Proven safe slot work | ~80k cycles per block; empty patch already 21 % CPU | bench 2026-10-18 |
| Patch admission | sum of declared `dspload` < 230.0; dspload = 7 + 3 x kcycles | DSP_RULES §4 |
| Units | 8 per cycle: .L1 .S1 .M1 .D1 / .L2 .S2 .M2 .D2 | *(TI)* |
| Float | MPYSP on .M (2 per cycle); ADDSP/SUBSP on .L and .S (up to 4 per cycle); 4-cycle latency each | *(TI)* |
| No hardware for | division (RCPSP ~8-bit seed + Newton steps), float SIMD | *(TI)*; DSP_RULES §3 |
| Has | RSQRSP seed, fixed-point SIMD of the C64x+ (ADD2, MPY2, DOTP2...) for 16-bit stages | *(TI)* |
| SPLOOP buffer | 14 execute packets: a loop body that fits pipelines with no code-fetch cost | *(TI)* |
| Effect code + const | the slot's 40 KiB in SDRAM, cached (MAR192) | recon/14 |
| State, coefficients, audio | L1D RAM (fast, no cache miss) | recon/14 |
| Caches | L1D cache (16 KB per recon/14) and L1P shared by all 5 slots and the firmware | recon/14 |

## 2. What limits our loops today (baseline 2026-10-18)

`tools/c6x_loop_report.py` (run by `tools/build_g1.sh`, output `build/<FILE>.LOOPS.md`) reads the compiler's
software-pipeline notes. "dep bound" = length in cycles of the feedback chain through one iteration;
"res bound" = cycles the units need for one iteration. If dep > res, the units are idle most of the time.

| Effect | Main sample loop | dep / res bound | Result |
|---|---|---|---|
| CF Muff | muff_g1.h:229 (4 trips) | 116 / 37 | **not pipelined**: feedback chain 3x the work (reworked 2026-10-19, §3b) |
| CF RAT | rat_g1.h:182 (8 trips) | 31 / 16 | pipelined at ii 31, half the units idle |
| CF 808 | ts808_exact.h:180 (8 trips) | 57 / 18 | pipelined at ii 61, two thirds idle |
| CF Watt 2x | hiwatt_amp.h 286/287/371/392, hiwatt_kernel.h:152 | 22/13, 16/6, 22/19, 24/8 | pipelined, all feedback-bound; hiwatt_amp.h:248 not pipelined (control code) |
| CF Dyna | dynacx.c:57 | - | **not pipelined**: control code (reworked 2026-10-19, �3d) |
| CF Mistrss | mistrx.c:83 | - | **not pipelined**: too many instructions (> 250) |
| CF CE2 | ce2x.c:81 | - | **not pipelined**: too many instructions (> 250) |
| CF Delay | delayx.c:78 | - | **not pipelined**: control code |

Stock Zoom drives run their sample loops as SPLOOPs at ii 10-14 (recon/11). Every CF effect has headroom
before any change to the model itself.

## 3. Design rules

1. **The feedback chain is the limit, not the unit count.** A recurrence (IIR state, diode solver, envelope)
   costs about 4 cycles per dependent float op, however few ops there are. Fill each loop with independent
   work so the units stay busy:
   - run several independent filters in the same loop instead of one loop each;
   - skew a cascade by a sample (stage k works on sample n-k), so the stages do not wait on each other;
   - one whole-block pass per stage, so a stage's 16 (or 32 at 2x) samples pipeline against each other wherever
     the stage has no feedback;
   - shorten the chain itself: precompute products outside the recurrence, use a transposed or
     state-variable form where it shortens the path, and replace iterative solvers with a fixed-count or
     table-seeded solve.
2. **Sample loops are branch-free and fixed-length.** No `if` on data, no early exits: use `fminf`/`fmaxf`,
   selects and table lookups. Fixed trip counts with `#pragma MUST_ITERATE(16,16,16)` (or 32 at 2x). All
   buffer pointers `restrict`. The aim of a loop: the report says "pipelined", ideally "Loop will be splooped".
3. **Keep loop bodies small.** Above 250 instructions the compiler gives up (Mistrss, CE2). Split a big body
   into passes over a block buffer in L1D state instead.
4. **Per block, not per sample:** knob mapping, coefficient calculation and smoothing run once per block. Spread
   expensive recalculations (CF Watt's coefficient derivation) over several blocks while a knob moves.
5. **Oversample only around nonlinear parts,** and share one up/down pair between neighbouring nonlinear stages
   (in CF Master: Muff and Watt inside one 2x region).
6. **Mono inside.** The guitar is mono: process one channel and copy to the second at the end, except for
   stages that really are stereo (chorus, delay spread).
7. **Memory:** hot coefficients and state live in the L1D state/coefficient buffers; tables read every sample
   should be small (a few KB) because the SDRAM cache is shared by five slots and the firmware.
8. **No division, no libm, no calls, no `switch`** in the kernel (DSP_RULES §3).
9. **Measure.** Build report first (each sample loop pipelined, dep close to res), then the pedal bench
   (`tools/ua_bench.py`, updater 17); the bench has the final word. Accuracy against the reference stays as
   strict as before (tests/host).

## 3b. Lessons from the CF Muff rework (2026-10-19)

- **State behind a pointer becomes a memory chain.** Muff's per-oversample state lived in `MuffState *st`;
  the compiler could not prove that stores to it miss the blob tables, so every oversample waited for the
  previous one's stores (dep bound 116, not pipelined). Load each state value into its own **scalar local**
  before the loop and store it back after.
- **A local struct copy is not enough:** `MuffState l = *st` stayed in memory, and neighbouring fields were
  loaded/stored as one 64-bit word, which tied two independent filters into one chain. Scalars only.
- **Write the arithmetic once:** helpers take each state value by pointer (`float *s`); the per-sample path
  passes struct fields, the block path passes locals. The two paths stay bit-identical
  (`tests/host/muff_block_test.cpp` checks output and state).
- **32 registers per side:** two clip solvers with their constants in one loop needed ~37-43 and found no
  schedule; one loop per solver pipelines. Fusing them would need fewer live constants first.
- **Masks instead of clamps on the chain:** a table index `(int)t & 0xFF` (table with one spare cell) replaces
  compare + select and stays in range for any input, NaN included; choose "extrapolate" on the same `t`.
- **`restrict` on the audio bus pointer** (`float *restrict eff = ctx[1]`): without it the final mix loop
  carried a false 24-cycle chain plus a run-time alias check.

Result: every Muff loop pipelined; the two clip chains 42 and 47 cycles per oversample (from one 116-cycle
loop that did not pipeline); static estimate ~9.8k cycles per block against 14.5k measured before (pedal
measurement pending); output within 92 dB of the previous version, accuracy bench unchanged.

## 3c. CF Watt (2026-10-19)

- Already chip-shaped (block passes, state in locals, tree sums, branch-free fast pass + fix-up list). Cheap
  wins taken: the coefficient-cache copy used `volatile` (6 cycles a word, ~560 per block -> ~90 with
  `restrict`), and the bus loops had the false alias chain (~540 -> ~100). About 0.9k cycles per block.
- **The NFB loop is the floor:** power stage -> feedback -> phase inverter, one sample late, so every sample
  waits for the previous one. Fast path ~257 cycles per sample (asm blocks), ~8.2k per block at 2x; the chain
  holds two tanh evaluations and the ADAA series in series (~200 cycles). Earlier variants that break the
  chain (residual 2-4 samples late, NFB at 1x) failed the accuracy bench.
- The preamp tube pass sits at ii 27 against a resource bound of 17: 25 registers live for the whole loop
  (constants). Worth ~1k per block if the tube code is reshaped; not done yet.
- **For CF Master:** the NFB loop leaves most units idle for ~200 cycles per sample. Independent work run in
  the same loop costs almost nothing: the parallel Alembic/RA-200 path (it does not depend on the Hiwatt path)
  or the delay are candidates. This is the main reason one CF Master kernel can beat separate effects.

## 3d. CF Dyna (2026-10-19)

Bit-identical to the previous version (host null test: 0 of 1.6 M samples differ). Six passes, all pipelined:
envelope + pre-emphasis (two recurrences, ii 16), gain computer (ii 41), ADAA antiderivative / midpoint tanh /
mix (27, 18, 6), de-emphasis + high-pass (16). Static ~2.6k cycles per block against 7.8k measured.
- A `cond ? expensive() : 1.0f` became a branch (control code): compute it always, then select.
- Two exp evaluations in one ADAA body found no schedule; the pure parts got their own passes.
- `restrict` on the block function's parameters removed a run-time alias check and a 35-cycle false chain.

## 4. Workflow for a stage

1. Host reference: the current CF effect or the owner's JUCE code (tests/host).
2. Write the stage in C to the rules above.
3. `tools/build_g1.sh` -> read `build/<FILE>.LOOPS.md`. Not pipelined, or dep far above res: restructure
   (rule 1) before tuning anything else. Hand linear assembly only where a loop still falls clearly short.
4. Host accuracy check; then the pedal bench and a listening check.
