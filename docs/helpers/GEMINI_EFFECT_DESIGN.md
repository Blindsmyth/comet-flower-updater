# Design brief for Gemini: new effects that cannot brick and do not waste memory (2026-10-10)

Written by Claude when its quota ran out. You (Gemini/agy) may do the offline
half of effect work from this file. You never touch the pedal; the owner does
all hardware steps. Read with it: `docs/DSP_RULES.md` (proven rules),
`recon/14_effect_memory.md` (memory map), `docs/helpers/AGY_RAT.md` (the
test-gated kit pattern that works for you), `docs/helpers/SAVE_PROTOCOL.md`.

Your known weakness (see GEMINI_NEXT.md): plausible claims where evidence is
missing. Here that means: every number below that you rely on must be
measured or quoted, never assumed. "Unknown" is a valid answer.

## 1. What a bad effect can and cannot do

| Failure | Cause | Damage | Guard |
|---|---|---|---|
| Noise / glitch / frozen screen | Over 96k cycles per block | none, power cycle fixes | cost budget (§3) |
| Neighbour slot or firmware corrupted | State, stack or table overrun | crash, possibly bad save | bounds rules (§4) |
| Pedal will not boot | Interrupted or oversized **install** (directory full) | needs FS restore | owner installs only via update-mode image; you build nothing installable |
| Loud / stuck output | NaN, inf or runaway feedback in state | ears, speakers | output clamp, state flush (§4) |

So brick risk lives in the install path and in memory overruns, not in the
maths. Your work stays safe if you obey §6 and stop at the gates in §5.

## 2. The memory you actually have (per effect, per slot)

From recon/14 (confirmed on the pedal for slot addresses) and DSP_RULES §3.

| Region | Size | Where | Use it for | Status |
|---|---|---|---|---|
| Slot image heap | 40 KiB (0xa000), fixed, no spill | cached SDRAM | `.text` + `.const` + zero-fill PT_LOAD + loader overhead | enforced by `tools/check_slot_mem.py` |
| Instance state | **392 B** budget | L1D RAM (fast) | all mutable state | 392 is proven safe; the slot stride is 672 B but use above 392 is NOT proven for our effects |
| Coefficient buffer | 840 B | L1D RAM | small hot tables, filled at init | stock NYC copies 568 B defaults there; unproven for DIY, probe first |
| Stack | 1536 B max frame | L2 RAM | locals | overflow corrupts firmware |
| Audio bus | 2 x 16 floats | L1D RAM | in place | do not hold pointers across calls |
| Work buffers (0x81330 B each) | descriptor exists | SDRAM | long delay lines? | **ownership unproven. Do not use.** |

Consequences (design from these, do not argue with them):
1. **No long memory.** Delay, reverb, long IR convolution do not fit and have
   no proven buffer. If an effect needs more than the table above, stop and
   write the need into your result file. Do not invent an allocator.
2. **No mutable globals or mutable `static` locals.** Non-loadable `.bss` is
   not allocated by the loader (recon/14 §1). All mutable data lives in the
   state struct. Tables are `static const`.
3. Entry fields [5]..[8] are callbacks, not memory requests (recon/14 §3).
   Never write a size there.
4. The 16 KB L1D cache is shared by all five slots and is refilled between
   blocks (19-25 % of kernel cost, measured on RATT and 808T). So **hot
   working set per effect: aim at 3 KB or less of tables read per block**,
   and read tables in order. A 27 KB table that is read sparsely is cheap
   in RAM and expensive in cache; prefer one small table plus interpolation.
5. `.text` + `.const` must fit 40 KiB together with overhead. `.text` 18 KB
   and const 27 KB cannot both be at their maxima. Check with
   `tools/check_slot_mem.py`; leave at least 1 KiB spare (T808 has 0.5 KiB
   and is the floor, not the target).

## 3. CPU budget (design target for sharing a patch)

- Pedal gives about 96k cycles per 16-sample block in total; the screen
  freezes near 96-102k. Five effects must fit together, so **an effect
  that wants to be shareable should measure about 12k or less**; stock
  drives cost 9-15k (recon/11).
- Measured reality: kernels cost what the static count says when the loop is
  branch free, then add roughly 20-25 % cache refill, and about 7k per
  effect of framework work. A 15k kernel (RAT) measured about 24k on the
  pedal. Budget with that multiplier: **static kernel target 9k for sharing,
  15k solo-friendly, 20k hard stop** (the AGY_RAT numbers).
- Cheapest version that sounds the same wins (owner, 2026-10-06). Prove
  "sounds the same" with the host bench (aliasing, response vs reference),
  never by assertion.
- Allowed tricks, in order of preference: lower oversampling where the host
  bench still passes; polynomial or small-table nonlinearity; fixed-point-free
  float code; merging filters; skipping oversampling on linear stages.
  Not allowed: data-dependent branches or `while` in the sample loop, libm,
  division, `switch`, calls to non-inline functions.

## 4. Safety rules for the code (each one is checkable)

- **Bounds:** every table index goes through a clamp before the load. Table
  length is a compile-time constant; add a `_Static_assert` or equivalent on
  `sizeof(State) + 16 <= 392`.
- **Stack:** no recursion, VLAs, `alloca`, or local arrays above 256 B.
  `build_g1.sh` reports the frame; keep it far under 1536 B.
- **Output:** final sample `ts_clamp`ed to about +-1.0 (or the host-bench
  headroom you can justify). Never emit NaN.
- **State:** flush denormals (add and subtract a tiny constant, or clamp small
  values to zero); clamp any feedback state; reset state in init to a known
  value, never leave it zero-uninitialised assumptions.
- **Parameters:** map every knob through a clamp. Knob ranges come from
  `manifest.json`; do not read outside them.
- **Slot picture:** ELF image 0 must be drawn or the slot shows blank/BYPASS
  (proven). Copy the picture handling from the nearest shipped effect.
- **Only the files your task names.** No firmware patches, no loader
  changes, no `stomphacks` edits, no edits to `res5` or boot code.

## 5. Gates (an effect moves only when the previous gate passes)

| Gate | What | Who | Evidence you write |
|---|---|---|---|
| G0 | Design sheet (§7) filled in, memory and cost estimates with arithmetic | Gemini | `docs/helpers/<name>_DESIGN.md` |
| G1 | Host bench vs reference: PASS and STRETCH numbers (kit in AGY_RAT style) | Gemini | scorer's last 3 lines pasted |
| G2 | `tools/build_g1.sh` ends "ready"; `check_slot_mem.py` OK; state <= 392; stack OK | Gemini | build output pasted |
| G3 | Static cycles via `tools/c6x_cycles.py`, arithmetic written, loops branch-free | Gemini | numbers in the design sheet |
| G4 | Claude or Codex reviews G1-G3 and the diff | reviewer | review note |
| G5 | Update-mode image built, owner installs, AUTO SAVE off, effect alone in an empty patch, passes audio | **owner** | owner report |
| G6 | Cost test with Probe 10, then sharing test, then real `dspload` | **owner** | owner report |
| G7 | Only now: save patches containing it | owner | - |

You stop after G3 and report. Do not build update images, do not run any of
the pedal tools named in AGY_RAT §6.

## 6. Hard "do not" list

Same as AGY_RAT §6, plus: no `git push`; no commits of build artefacts
(`build/` is scratch); never mark a design "safe" or "shippable", only
"passes G1..G3"; never lower a bench threshold or edit a scorer to get a
PASS; never use MIDI install/replace/uninstall (it bricked the pedal).

## 7. Design sheet template (copy to `docs/helpers/<name>_DESIGN.md`)

```
# <effect> design sheet
Source/reference: <file and function in juce_source or exhboost; quote line ranges>
Signal chain: <stage list with the nonlinear stages marked>
Oversampling: <factor per stage, why, host-bench evidence>
State bytes: <field by field, total + 16, must be <= 392>
Tables: <name, entries, bytes, hot bytes per block>
.text estimate: <KB, basis>   .const: <KB>   slot total: <KB of 40>
Stack frame: <bytes>
Cycles/block: <loop by loop: cycles x trips = total; branch-free? yes/no>
Needs more memory than the table in section 2? <no / what exactly>
Unknowns: <list; each with how to measure it>
Gate status: G0 [ ] G1 [ ] G2 [ ] G3 [ ]
```

## 8. First offline task for Gemini (no pedal, no new DSP yet)

**E0. Candidate feasibility sheet.** Survey the owner's JUCE pedalboard
(`juce_source/` here and `C:/Users/z/Documents/exhboost/VirtualPedalBoardEngine/Source/`;
read-only) and write `docs/helpers/EFFECT_CANDIDATES.md`: one row per effect
or amp, with columns: nonlinear stages, filter count, needs delay memory?
(yes means out of scope today), table needs, estimated state bytes,
estimated cycle class (A: <=9k, B: <=15k, C: more), and a
quote of the source lines you based it on. Do not pick a winner and do not
write DSP: the owner picks (the amp, Tweed 5E3, is undecided). Mark every
estimate `guess` unless you counted it from code you quote.
Commit only that file.
