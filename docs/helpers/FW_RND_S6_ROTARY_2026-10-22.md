# S6 - CF Rotary: simple mono rotary replacing RA200X

## Status
done (build, check_slot_mem, host test all pass; not measured on the pedal --
no pedal access, per the hard rules)

## Design
`effects/rotx/rotx.c`, `effects/rotx/manifest.json`. Mono in, channel A only
(`ctx[1]`), same signal duplicated to channel B (`eff[i + SH_CH_B_OFFSET]`),
matching what CE2X (`effects/ce2x/ce2x.c`) and DLYX (`effects/delayx/delayx.c`)
both do: they read channel A only and write their one result to both channels,
with a per-channel bypass crossfade (`fade`) against whatever was already on
each channel. Same pattern followed here exactly (same `(-8,8)` clamp too).

Signal path: a fixed 1-pole TPT crossover at ~800 Hz (`ROT_XOVER_G`,
precomputed constant, not computed at runtime) splits input `x` into drum
(lowpass `y`) and horn (`x - y`) bands; `horn + drum == x` identically for a
true 1-pole split. Each band is pushed into its own small circular line in
the work buffer, from the *same* write pointer. The horn line is read back
with a linear-interpolated, LFO-modulated (Doppler) offset, around a fixed
baseline of 64 samples, and amplitude-modulated by the same LFO. The drum
line is read back at that *same* 64-sample baseline, but held fixed (no
Doppler, no interpolation needed since the baseline is an exact integer),
and amplitude-modulated by its own (slower) LFO. Reading both bands from the
same past index reconstructs `x` exactly when the Doppler swing is 0 (Depth
0): it is the *matched* baseline delay on both paths, not merely the 1-pole
split, that keeps Mix 100 / Depth 0 at unity gain -- see "bug found and
fixed" below, where an *unmatched* delay broke this. Both LFOs are a
triangle wave from a phase accumulator, shaped by the parabolic cubic
`tri*(1.5 - 0.5*tri*tri)` instead of calling `sinf` (no libm anywhere).

Horn/drum rotation rates glide to the Speed target once per 16-sample block,
each at its own fixed step size derived from the (smoothed) Ramp knob: horn
0.8..6.7 Hz (brief-specified), drum 0.6..5.5 Hz (a bit slower, per brief);
drum's per-block step is smaller at both the fast (Ramp=0) and slow (Ramp=100)
ends, so its spin-up/down is slower *and* takes longer to finish, matching a
larger rotor's inertia. The step constants (`ROT_STEP_*`) are reasonable
chosen numbers within the two brief-given rate points, not derived from a
measured real Leslie motor spec -- see "Not met / open leads".

Params (4, all <= 8 chars, max <= 255): `Speed` (max 1, default 0), `Depth`
(max 100, default 70), `Ramp` (max 100, default 50), `Mix` (max 100, default
80). Depth, Ramp and Mix are smoothed per block with the same `KNOB_SMOOTH =
0.1f` one-pole as CE2X/DLYX use for their knobs. Speed is not smoothed as a
value; its "smoothing" *is* the horn/drum frequency ramp itself, which is
the point of the Ramp control, not a redundant second stage.

### Bug found and fixed by the host test: unmatched baseline delay
First version pushed only the horn band into a delay line and read the drum
band *directly, undelayed*, with the horn's Doppler read centered on a 64-
sample baseline. At Depth 0 (no Doppler swing) this still summed
`horn(n-64) + drum(n)` -- two different time instants of a signal that only
sums to `x` when both bands are read at the *same* instant, so it is not `x`
-- at 440 Hz a 64-sample (1.45 ms) relative delay between the bands is a
~230 degree relative phase shift, giving partial cancellation. The host
test's level check caught this directly: -4.49 dB instead of 0 dB (see
`tests/host/rotx_test.cpp` check 3). Fix: give the drum band its own line,
pushed from the same write pointer, read at the *same* fixed baseline the
horn's Doppler swings around; now both bands are always read from the same
past write index when Depth is 0, so they still sum to `x` (just delayed by
64 samples, which does not change a steady-state level measurement). Re-run
after the fix: 0.00 dB. This cost 32 B of `.audio`, which is why
`kernel_section` moved to `"text"` (next section).

## State
`KernelState` (9 floats, 36 B: crossover filter state, 2 LFO phases, 2 LFO
rates, 3 smoothed knobs, primed flag) lives in the declared per-instance
state; manifest declares `"state_bytes": 40` (`sizeof(KernelState) <=
SH_STATE_BYTES` enforced by a `typedef char ..._state_fits[...]` compile
check, same idiom as ce2x.c/delayx.c). 40 B is far under the 392 B rule.

The two delay lines (`RotLine`: `buf_h[128]` + `buf_d[128]` + a `uint32_t`
write pointer = 1,028 B, <= 2.9 ms each at 44.1 kHz) live in the slot's work
buffer via `instance[3] -> {base, end, size}`, same mechanism and same guard
check as CE2X's `work_state()`/DLYX's `work_state()` (8-byte alignment,
non-null base, `end - base == size`, `size >= sizeof(RotLine)`);
`work_line()` in rotx.c is that same check against `RotLine`. If the buffer
is absent, too small, or the state guard word is wrong, or any coefficient
is out of its declared [0,1] range, the kernel mutes both channels to
silence -- the exact fallback CE2X and DLYX already use when *their* guard
checks fail; this is not a new convention, it is the existing one. Whether
the loader actually grants a work buffer to a brand-new effect id
(`06000f8a`, `g1_slots` 1) is **not verified** (no pedal access, hard rule)
-- same open risk CE2X/DLYX themselves carry ("TEST: cost not yet measured
on the pedal" in their own manifests); ROTX's manifest description carries
the same caveat.

## Build / checks
`bash tools/build_g1.sh rotx "CF ROT" "CF/ROT"` succeeds:
- `build/ROTX.ZD2` produced, `tools/check_slot_mem.py` passes: **3,720 of
  40,960 slot bytes used (37,240 free)**.
- Manifest sets `"kernel_section": "text"` (needed once the second delay
  line pushed the kernel to 1,504 B, over the default `.audio` section's
  1,472 B ceiling -- see the bug-fix note above) but leaves `allow_stack`
  at its default (`false`), i.e. still the strictest SAFE-DSP leaf path,
  just with the bigger code budget. stomphacks' own build-time assertion
  (`tools/zd2_make_effect.py`) disassembles the compiled kernel and
  asserts it contains **no `B15` (stack pointer) reference at all** and no
  callee-saved register use when `allow_stack` is false; the build printed
  `kernel: ~1924 B in .text (upper size bound); SAFE-DSP ok (leaf, no
  stack, no callee-saved regs)` -- that line is itself the proof of a
  **0-byte stack frame** (stronger than the brief's "< 256 B" target, and
  verified by the build's own disassembly check, not an estimate). 1,924 B
  is well under the 18 KB `.text` budget (CE2X/DLYX themselves need
  `allow_stack: true` for their bigger per-block local arrays; ROTX does
  not need that relaxation).
- No `switch` (none written), no division at runtime (the one `/` in the
  source, `1.0f/SH_SAMPLE_RATE`, is a compile-time constant fold, same idiom
  as `ce2_coeffs`'s `1.0f/44100.0f`), no libm call, no function calls in the
  audio function (`calls = [l for l in kernel if "CALL" in l]` asserted empty
  by the same build-time verifier).

## Cycles / loop report
`tools/c6x_loop_report.py --compile effects/rotx` (`build/ROTX.LOOPS.md`):

| loop (source line) | trips | result |
|---|---|---|
| rotx.c:149 (guard-fail mute loop) | 16 | pipelined |
| rotx.c:159 (one-time work-buffer zero-init, 1028 B / 4 = 257 words) | 257 | pipelined |
| rotx.c:199 (the main per-sample loop) | 16 (fixed; `MUST_ITERATE(16,16)`) | **not pipelined: "Loop contains control code"** |

All three loops have a **fixed, compile-time-constant trip count** -- "not
pipelined" is a scheduling outcome, not an unbounded-trip-count problem; the
C source bound (`i < SH_FRAMES`, `SH_FRAMES == 16`) does not change.

Why the main loop isn't pipelined: it does the crossover, both LFOs, both
delay-line reads and the final clamp/mix all in **one** per-sample pass, so
it carries several of the same branchy idioms CE2X/DLYX themselves use (the
LFO-phase wrap `p -= (p>=1)?1:0`, exactly `ce2_phase_step`'s idiom; the output
range clamp `if (!(wet>-8 && wet<8)) wet=0`, exactly ce2x.c/delayx.c's idiom).
CE2X/DLYX avoid the pipelining penalty by splitting each stage into its own
small loop over 16 pre-stored samples (`ce2_block`'s stage-major design,
`docs/C6745_DESIGN.md`) -- but that needs several 16-float local arrays
(CE2X's `ce2_block` locals alone are 6 arrays, 384+ B), which needs
`allow_stack: true` and a bigger frame. I kept the single-pass, zero-local-
array version instead, because the brief's frame target for this job (< 256
B, aim for 0) is stricter than CE2X/DLYX's own precedent, and the measured
result (0 B, build-verified) meets it exactly; the trade-off is a less
certain static cycle estimate (below) and no software pipelining. This is a
real design trade-off, not an oversight; both paths are open to revisit if
the owner would rather have CE2X-style pipelining than a verified-zero frame.

Static cycle estimate (`tools/c6x_cycles.py` on the kept `-mw` asm,
`build/rotx_kernel.asm`): summed **every** block on **both** arms of every
conditional in the per-sample-loop region (rotx.c:199, blocks `$C$L22`..
`$C$L35+`) as a safe upper bound -- about **161 cycles/sample** that way (an
over-count, since not every arm runs every sample) -- times 16 samples =
**~2,576 cycles**, plus the one-time-per-block setup/guard code before the
loop (~189 cycles, blocks before `$C$L22`, excluding the rare 257-trip cold-
init path) plus the loop exit (~4 cycles): **~2,769 cycles per 16-sample
block, static, upper-bound**. This is comfortably under the brief's 5,000-
cycle budget (about 45% headroom) even as a deliberately pessimistic sum, but
per `docs/DSP_RULES.md` ("static cycle counts are trustworthy only for
branch-free loops") this number is **not a branch-free guarantee** the way a
CE2X-style pipelined loop's would be -- it is a hand-summed upper bound over
a hand-read control-flow graph, not a tool-verified total. Treat it as
"likely well under budget," not as a certified count; the pedal measurement
step (DSP_RULES order of work, step 5) is the real proof, as it is for every
effect in this codebase, including CE2X/DLYX themselves.

## dspload
kcycles ~2.77k rounded up to 3.0k for margin; `dspload = 7 + 3*kcycles =
16.0`, declared in the manifest and confirmed by the build: `container INFO
dspload set to 16.00 raw = 5.9% of the 270 budget`.

## Host test
`tests/host/rotx_test.cpp` + `tests/host/build_rotx_test.bat`, pattern of
`tests/host/delayx_kernel_test.cpp` (compiles the real `effects/rotx/rotx.c`
as a 32-bit host binary, extern "C" include, with the pedal's
instance/ctx calling layout -- not the ce2x/delayx *_block_test.cpp
core-equivalence pattern, since ROTX has no separate "core" header/bench
reference to compare against; the brief's own checklist for S6 matches the
kernel-level harness: finite output, ramp-reaches-target, a level check).

Run: `tests/host/build_rotx_test.bat` -> `all passed`:
```
CF Rotary kernel host test (state 36 B, work buffer need 1028 B)
  finite output: silence/full-scale sine/noise, all 16 param corners, 10 s each ok
  (after 6 s at Ramp=100: freq_h 6.700 Hz (target 6.7), freq_d 5.500 Hz (target 5.5))
  horn speed ramp reaches its target (Ramp=100, 6 s)             ok
  drum speed ramp reaches its target (Ramp=100, 6 s)             ok
  (Mix 100 / Depth 0: in RMS 0.56563, out RMS 0.56563, -0.00 dB)
  output level within 3 dB of input at Mix 100, Depth 0          ok
  bad state guard mutes                                          ok
  out-of-range coefficient mutes                                 ok
  no work buffer mutes                                           ok
all passed
```
Checks covered: (1) finite output (no NaN/Inf) for silence, full-scale sine
and noise, at all 16 Speed/Depth/Ramp/Mix corners, 10 s each (480 s of
simulated audio total); (2) the Speed ramp reaches its target at the
slowest glide setting (Ramp=100) within 6 s (worst case chosen, drum's
~4.4 s glide, is covered with margin); (3) output level within 3 dB of
input at Mix 100 / Depth 0 (measured 0.00 dB after the bug fix above); (4)
the three guard paths (bad state guard, out-of-range coefficient, missing
work buffer) all mute to silence, matching CE2X/DLYX's own convention.

## pytest
`.venv/Scripts/python.exe -m pytest tests -q`: **1 failed, 333 passed, 146
subtests passed**. The one failure is pre-existing and unrelated to this job:

```
FAILED tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx
  assert used == 18176
  E assert 18464 == 18176
```

`tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx` checks
`build/RATX.ZD2` (the CF RAT effect, `effects/ratx/`) against a hardcoded
byte count; its `build/RATX.ZD2` now measures 18,464 B instead of the
18,176 the test expects. Nothing in this job touched `effects/ratx/`,
`build/RATX.ZD2`, or that test file -- not investigated or fixed, per the
brief ("do not fix unrelated failures; list them"). No test under
`tests/host/rotx_*` or referencing `effects/rotx` failed or was collected
with errors.

## Not met / open leads
- Static cycle number is a hand-summed CFG upper bound, not a tool-certified
  branch-free count (see Cycles section) -- confidence: likely, not confirmed.
- Work-buffer availability for a new effect id is unverified (no pedal
  access); if the loader does not grant `instance[3]` to ROTX, the effect
  fails closed to silence rather than crashing (same fallback as CE2X/DLYX),
  but it would then make no sound at all until that is confirmed/fixed.
- Horn/drum ramp step constants (`ROT_STEP_*`) are reasonable chosen numbers
  within the two brief-given rate points (0.8/6.7 Hz horn, 0.6/5.5 Hz drum),
  not derived from a measured real Leslie motor spec.
- Not measured on the pedal (no pedal access, per the hard rules): cost,
  audio pass, and the work-buffer question above all still need the real
  on-pedal step per `docs/DSP_RULES.md` order of work; dspload (16) and the
  cycle estimate are both pre-measurement numbers, same caveat CE2X/DLYX
  themselves carry.
- Did not attempt to restructure the main loop into CE2X/DLYX's stage-major
  multi-array form to get full software pipelining, because that would need
  `allow_stack: true` and several 16-float arrays, conflicting with this
  job's explicit < 256 B (target 0) frame requirement; see Cycles section.
