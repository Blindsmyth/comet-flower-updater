# S6 - CF Rotary: simple mono rotary replacing RA200X

## Status
running (kernel + manifest built and passing; host test next)

## Design
`effects/rotx/rotx.c`, `effects/rotx/manifest.json`. Mono in, channel A only
(`ctx[1]`), same signal duplicated to channel B (`eff[i + SH_CH_B_OFFSET]`),
matching what CE2X (`effects/ce2x/ce2x.c`) and DLYX (`effects/delayx/delayx.c`)
both do: they read channel A only and write their one result to both channels,
with a per-channel bypass crossfade (`fade`) against whatever was already on
each channel. Same pattern followed here exactly (same `(-8,8)` clamp too).

Signal path: a fixed 1-pole TPT crossover at ~800 Hz (`ROT_XOVER_G`,
precomputed constant, not computed at runtime) splits input `x` into drum
(lowpass `y`) and horn (`x - y`) bands; since `horn + drum == x` identically
for a true 1-pole split, Depth 0 recombines to the dry signal exactly (no
coloration), which is what keeps Mix 100 / Depth 0 at unity gain. Horn band:
pushed into a small circular delay line, read back with a linear-interpolated,
LFO-modulated offset (Doppler) and amplitude-modulated by the same LFO. Drum
band: amplitude modulation only, independent (slower) LFO. Both LFOs are a
triangle wave from a phase accumulator, shaped by the parabolic cubic
`tri*(1.5 - 0.5*tri*tri)` instead of calling `sinf` (no libm anywhere).

Horn/drum rotation rates glide to the Speed target once per 16-sample block,
each at its own fixed step size derived from the (smoothed) Ramp knob: horn
0.8..6.7 Hz (brief-specified), drum 0.6..5.5 Hz (a bit slower, per brief);
drum's per-block step is smaller at both the fast (Ramp=0) and slow (Ramp=100)
ends, so its spin-up/down is slower *and* takes longer to finish, matching a
larger rotor's inertia. See `## Not met / open leads` for the exact step
constants chosen (not derived from a real Leslie motor spec, just reasonable
numbers within brief's two named points).

Params (4, all <= 8 chars, max <= 255): `Speed` (max 1, default 0), `Depth`
(max 100, default 70), `Ramp` (max 100, default 50), `Mix` (max 100, default
80). Depth, Ramp and Mix are smoothed per block with the same `KNOB_SMOOTH =
0.1f` one-pole as CE2X/DLYX use for their knobs. Speed is not smoothed as a
value; its "smoothing" *is* the horn/drum frequency ramp itself, which is
the point of the Ramp control, not a redundant second stage.

## State
`KernelState` (9 floats, 36 B: crossover filter state, 2 LFO phases, 2 LFO
rates, 3 smoothed knobs, primed flag) lives in the declared per-instance
state; manifest declares `"state_bytes": 40` (`sizeof(KernelState) <=
SH_STATE_BYTES` enforced by a `typedef char ..._state_fits[...]` compile
check, same idiom as ce2x.c/delayx.c). 40 B is far under the 392 B rule.

The short Doppler delay line (`RotLine`: 128 floats + a `uint32_t` write
pointer = 516 B, <= 2.9 ms at 44.1 kHz) lives in the slot's work buffer via
`instance[3] -> {base, end, size}`, same mechanism and same guard check as
CE2X's `work_state()`/DLYX's `work_state()` (8-byte alignment, non-null base,
`end - base == size`, `size >= sizeof(RotLine)`); `work_line()` in rotx.c is
that same check against `RotLine`. If the buffer is absent, too small, or the
state guard word is wrong, or any coefficient is out of its declared [0,1]
range, the kernel mutes both channels to silence -- the exact fallback CE2X
and DLYX already use when *their* guard checks fail; this is not a new
convention, it is the existing one. Whether the loader actually grants a work
buffer to a brand-new effect id (`06000f8a`, `g1_slots` 1) is **not verified**
(no pedal access, hard rule) -- same open risk CE2X/DLYX themselves carry
("TEST: cost not yet measured on the pedal" in their own manifests); ROTX's
manifest description carries the same caveat.

## Build / checks
`bash tools/build_g1.sh rotx "CF ROT" "CF/ROT"` succeeds:
- `build/ROTX.ZD2` produced, `tools/check_slot_mem.py` passes: **3,720 of
  40,960 slot bytes used (37,240 free)**.
- `.text` 736 B (well under the 18 KB budget).
- Manifest uses the *default* `kernel_section` ("audio", 1,472 B budget) and
  default `allow_stack` (false) -- i.e. the strictest SAFE-DSP leaf path, not
  CE2X/DLYX's `"text"` + `allow_stack: true`. stomphacks' own build-time
  assertion (`tools/zd2_make_effect.py`) disassembles the compiled kernel and
  asserts it contains **no `B15` (stack pointer) reference at all** and no
  callee-saved register use when `allow_stack` is false/omitted; the build
  printed `kernel: ~1472 B at 0x7800; SAFE-DSP ok (leaf, no stack, no
  callee-saved regs)` -- that line is itself the proof of a **0-byte stack
  frame** (stronger than the brief's "< 256 B" target), confirmed by the
  build's own verifier, not just an estimate.
- Caveat: the kernel fills the `.audio` section to **exactly** 1,472 of 1,472
  B (no headroom at all in the audio-section code budget; confirmed from the
  disassembly: entry `0x7800` to end `0x7dc0` = 0x5c0 = 1472 B exactly). Any
  future change to this kernel will need `"kernel_section": "text"` (18 KB
  budget) to get room; it does not today.
- No `switch` (none written), no division at runtime (the one `/` in the
  source, `1.0f/SH_SAMPLE_RATE`, is a compile-time constant fold, same idiom
  as `ce2_coeffs`'s `1.0f/44100.0f`), no libm call, no function calls in the
  audio function (`calls = [l for l in kernel if "CALL" in l]` asserted empty
  by the same build-time verifier).

## Cycles / loop report
`tools/c6x_loop_report.py --compile effects/rotx` (`build/ROTX.LOOPS.md`):

| loop (source line) | trips | result |
|---|---|---|
| rotx.c:131 (guard-fail mute loop) | 16 | pipelined |
| rotx.c:141 (one-time work-buffer zero-init, 516 B / 4) | 129 | pipelined |
| rotx.c:180 (the main per-sample loop) | 16 (fixed; `MUST_ITERATE(16,16)`) | **not pipelined: "Loop contains control code"** |

All three loops have a **fixed, compile-time-constant trip count** -- "not
pipelined" is a scheduling outcome, not an unbounded-trip-count problem; the
C source bound (`i < SH_FRAMES`, `SH_FRAMES == 16`) does not change.

Why the main loop isn't pipelined: it does the crossover, both LFOs, the
Doppler read and the final clamp/mix all in **one** per-sample pass, so it
carries several of the same branchy idioms CE2X/DLYX themselves use (the
LFO-phase wrap `p -= (p>=1)?1:0`, exactly `ce2_phase_step`'s idiom; the output
range clamp `if (!(wet>-8 && wet<8)) wet=0`, exactly ce2x.c/delayx.c's idiom).
CE2X/DLYX avoid the pipelining penalty by splitting each stage into its own
small loop over 16 pre-stored samples (`ce2_block`'s stage-major design,
`docs/C6745_DESIGN.md`) -- but that needs several 16-float local arrays
(CE2X's `ce2_block` locals alone are 6 arrays = 384+ B), which needs
`allow_stack: true` and a bigger frame. I kept the single-pass, zero-local-
array version instead, because the brief's frame target for this job (< 256
B, aim for 0) is stricter than CE2X/DLYX's own precedent, and the measured
result (0 B, build-verified) meets it exactly; the trade-off is a less
certain static cycle estimate (see next section) and no software pipelining.
This is a real design trade-off, not an oversight; both paths are open to
revisit if the owner would rather have CE2X-style pipelining than a
verified-zero frame.

Static cycle estimate (`tools/c6x_cycles.py` on the kept `-mw` asm,
`build/rotx_kernel.asm`): summed **every** block on **both** arms of every
conditional in the per-sample-loop region (rotx.c:180, blocks `$C$L22`..
`$C$L35+`) as a safe upper bound -- about **158 cycles/sample** that way (an
over-count, since not every arm runs every sample) -- times 16 samples =
**~2,528 cycles**, plus the one-time-per-block setup/guard code before the
loop (~187 cycles, blocks before `$C$L22`, excluding the rare 129-trip cold-
init path) plus the loop exit (~3 cycles): **~2,718 cycles per 16-sample
block, static, upper-bound**. This is comfortably under the brief's 5,000-
cycle budget (about 46% headroom) even as a deliberately pessimistic sum, but
per `docs/DSP_RULES.md` ("static cycle counts are trustworthy only for
branch-free loops") this number is **not a branch-free guarantee** the way a
CE2X-style pipelined loop's would be -- it is a hand-summed upper bound over
a hand-read control-flow graph, not a tool-verified total. Treat it as
"likely well under budget," not as a certified count; the pedal measurement
step (DSP_RULES order of work, step 5) is the real proof, as it is for every
effect in this codebase, including CE2X/DLYX themselves.

## dspload
kcycles ~2.7-2.8k rounded up to 3.0k for margin; `dspload = 7 + 3*kcycles =
16.0`, declared in the manifest and confirmed by the build: `container INFO
dspload set to 16.00 raw = 5.9% of the 270 budget`.

## Host test
(filled in below)

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
- `.audio` section is at its exact 1,472 B ceiling: zero headroom for any
  future edit without moving to `kernel_section: "text"`.
- Not measured on the pedal (no pedal access, per the hard rules): cost,
  audio pass, and the work-buffer question above all still need the real
  on-pedal step per `docs/DSP_RULES.md` order of work.
