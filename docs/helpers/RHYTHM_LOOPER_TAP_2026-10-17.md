# Rhythm/Looper tap feasibility (2026-10-17)

Written by Claude Sonnet 5. Offline static analysis only of
`build/fw/map/main.dis` / `build/fw/map/refs.txt` / `build/fw/map/strings.txt`.
Nothing on the pedal was touched. Scratch: `build/scratch/sonnet_rhythm/`
(unused — no scratch files were needed, all work was read-only grep/sed on
existing maps).

## Summary

R1 (confirmed): the audio Swi `11818ba0` makes exactly 21 CALLPs per
16-frame block, in a fixed order; full list below with every target traced.
R2/R3 (open): **no rhythm- or looper-alone buffer was found.** Every CALLP
target reachable from the Swi was traced to completion; none of them touch
the rhythm sample ROM (`c016f780`) or the looper candidate buffer
(`c01834ac`/`c04abff0`) region, and none contain drum-sample playback
code. The only confirmed rhythm/looper-specific code found is (a) the task
names `g_Task_RhythmService`/`g_Task_LooperUI` (not traced to a function
body this pass) and (b) a per-slot classification routine `c01502cc`,
called once per effect slot from inside the Swi's 5-slot loop, which
explicitly string-compares against `"LOOPER"`/`"RHYTHM"` — but those two
strings live in a footswitch-menu string table (next to `"FSW:ENTER"`), so
this is **likely** UI/bypass-state classification, not audio mixing.
R4: the effect-chain output buffer (`11f037b0`/`11f037f0`, float, planar,
2ch, 16 samples/ch) is intact between the slot loop (`11818c38`) and the
patch-level-gain call (`11818c44`) — a new, confirmed, unused tap point for
"effect chain output before any later mix stage" — but rhythm-alone and
looper-alone still have no known address. Biggest open thread for a
follow-up pass: find the Task function bodies for `g_Task_RhythmService`/
`g_Task_LooperUI` and the two helpers `c013a34c`/`c013a328` called from
`c01502cc`.

R5 (follow-up, 2026-10-17): fully traced `11817a90`'s four extra buffers.
`11f03830` is a real **stereo** 16-sample float bus (confirmed by the
loop's own per-channel pointer advance and the startup zero-size), added
directly into the effect-chain output before the patch-level-gain multiply.
`11f03930` is a real **mono** 16-sample float bus, scaled by gain cell
`c011acd0` and summed in separately. `11f03970` is address-published
(feature table slot 0) but has **no located consumer** anywhere. `c011acec`
is **confirmed** to be a mirrored copy of the patch-level gain
`c011acd8` (not a rhythm/looper volume) — traced to its exact setter
function, which also (conditionally) forces both cells to 1.0 during a
flag-gated path. The neighboring gain cells (`c011accc`/`acd0`/`ace4`/`ace8`)
trace to the same generic "all-slots mute/reload" sequence recon/16 B2/B3
already documented (confirmed: that sequence's mute-flag setter is
`c01435a0`, and it also calls `c01502cc` per slot). **No producer (writer of
actual samples) for `11f03830`/`11f03930`/`11f03970` was found** — this
remains the key open item; the signal shape fits a rhythm/looper send, but
the gain plumbing traces to generic mute infrastructure, not a
string-identified rhythm/looper control, so the identification stays
unconfirmed.

## R1. Audio Swi full call sequence

Source: `build/fw/map/main.dis` lines 18270-18352 (prologue through the
5-slot loop) and 18352-18358 (tail), addresses `11818ba0`..`11818c84`.
Confirmed by direct read of every instruction in that window; no CALLP was
skipped (verified by grepping the same window for every `CALLP` occurrence
and matching the count against this list, 21 calls + 1 two-way branch
override inside the effect loop).

Prologue `11818ba0`-`11818ba8`: saves `A11`, `B11:B10`, `A10` on the stack.

1. **`11818ba8` CALLP `0x11818840`** (confirmed address/location). Body
   (`main.dis` 18018-18111) reads/writes `11f03e2c`/`11f03e7c` (16-entry
   float array region used elsewhere for per-slot level ramps), does
   `ABSDP`/`CMPLTDP` min/max-style comparisons and writes a 16-word result
   array. No CALLP inside it (leaf). Confidence for "what it does": **guess**
   — looks like per-slot/per-parameter level-knob smoothing (interpolating a
   UI-set target into a per-sample ramp), not audio-sample generation; no
   rhythm/looper string or buffer reference found in its body.
2. **`11818bac` CALLP `0x11818980`** (confirmed address/location). Body
   (`main.dis` 18111-18270) touches `11f03ed8`, `11f03e30` (same ramp region
   as #1, and adjacent to the `11f03ed0` jump table used in step 6/14 below)
   and `c011ad6c` (SDRAM constant one word from `c011ad60`, which `11816f60`
   also reads — see step 4). **Guess**: same family as #1, parameter/level
   smoothing; not examined instruction-by-instruction beyond its refs.
3. **`11818bb0` CALLP `0x11818b20`** — RX unpack. **Confirmed** (pre-existing,
   recon/C4, re-verified): writes planar int32 dry input to `11f03730` (L) /
   `11f03770` (R), 16 samples/channel.
4. **`11818bb4` CALLP `0x11816f60`** (confirmed address/location, **full
   trace**, 680 lines, no CALLP inside — confirmed leaf). Fixed-point
   (`SMPY32`/`SADD`/`SSHL`/`SSUB`/`ABS`, all saturating) FIR-style filter
   using a ~14-tap coefficient table based at `11f03d84` and running over a
   circular history read from/written back into `11f03770` (the **right**
   ADC channel raw int32 buffer, same one RX-unpack just filled) via
   `STW *-A28[16]` / `*A28++[1]` (`A28`=`11f03770`). Also reads SDRAM word
   `c018341c` and `c011ad60` once each; grepped the whole address range for
   `c016f7`/`c04ab`/`c0183` and found **no reference to the rhythm sample ROM
   or the looper buffer candidate anywhere in this function** (confirmed
   absence via `refs.txt`). **Guess**: input-conditioning filter (DC-block or
   anti-alias) on the right ADC channel; not rhythm/looper.
5. **`11818bb8` CALLP `0x11818360`** — int→float conversion. **Confirmed**
   (pre-existing, recon/C4): writes `11f037b0`/`11f037f0` (16 floats/channel)
   from `11f03730`/`11f03770`.
6. **`11818bc0` CALLP `0x11818e60`** with `A4=0` (parallel `MVK 0,A4` in the
   call's fetch packet). **Confirmed, full trace**: `11818e60` is a 2-entry
   jump-table dispatcher — `LDW *+A5[A4],A0` with `A5=11f03ed0`, then
   `B.S2X A0`. Called again later with `A4=1` (step 13/14). **Guess** for
   purpose: paired with step 12 (`c013f594`, which does double-precision
   subtract/multiply typical of elapsed-cycle→load-percentage conversion),
   this looks like a start/stop bracket for CPU-load or "PROCESS OVERFLOW"
   measurement (recon/10 bitmap), not rhythm/looper.
7. **`11818bc8` CALLP `0x118183d0`** (confirmed address/location, **full
   trace**, leaf, no CALLP inside). Copies the first 3 sample-pairs (6
   floats, `SPLOOPD` with `ILC=6`) of `11f037b0`/`11f037f0` into two small
   scratch buffers `11f03928`/`11f03968`. **Guess**: short lookahead/pre-roll
   snapshot of the fresh dry signal; purpose not resolved, no rhythm/looper
   reference found.
8. **`11818bcc` CALLP `0x11817ce0`** (confirmed address/location, **full
   trace**, leaf, no CALLP inside). Reads two 9-word SDRAM state blocks at
   `c011a360`.. and `c011a4b4`.. (9 words each, stride 4), does 9 pairwise
   `MPYSP` multiplies with `SADD`/`CMPGTSP`-magnitude-style selection, then
   loops up to 16 times over a float array at `11f0396c`
   (`A19++[1]` each iteration) comparing against the computed values and
   writing results back into cells near `c011a398`. No reference to
   `c016f780` or `c04abff0`/`c01834ac` anywhere in this function (confirmed
   absence). **Guess**: runs immediately after int→float, on the
   still-unprocessed dry signal — consistent with tuner/pitch-detection
   analysis (zero-crossing or autocorrelation-style scoring), not rhythm or
   looper.
9. **`11818bd0` CALLP `0x11817940`** (confirmed address/location, **full
   trace** of the portion before `11817a90` starts, i.e. `11817940`-`11817a8c`
   — this is the real extent of this function since `11817a90` is a
   separately-CALLP'd routine, see step 12). Reads a gain value from
   `c011ace4` (and a second read of the same cell later), and conditionally
   (skip on the very first loop iteration only — `A0` starts at 1, decrements
   to 0 after iteration 1, stores gated on `!A0`) writes ramped
   multiply-products into specific word offsets of the **left**-channel float
   buffer region (`A7` based on `11f037b0-8`). Right channel was not seen
   touched in this function. **Guess**: an input-trim or gate gain ramp
   applied to the left channel only (asymmetric L/R handling would fit a
   mono-guitar-in, stereo-out architecture); no rhythm/looper reference.
10. **Mute-flag check** (confirmed, pre-existing recon/B2): `11818bd8 LDW
    *+B14[101],B0` (`B14[101]`=`c0184f94`); if nonzero, `11818bec [B0] BNOP
    0x11818c44,5` skips straight to step 12, bypassing the whole slot loop.
11. **5-slot effect loop** (confirmed mechanism, matches recon/B2-B3, with
    one new confirmed detail this pass): `B10`=0..4, exit test
    `11818c28 CMPGT 5,B10,B0`. **Per iteration, before fetching/invoking the
    slot's own callback**: `11818c04 CALLP 0x11818eb0` (veneer → `c01502cc`)
    with `A4`=slot index; the call's return value is moved into `A10` then
    back into `A4` (`11818c08`/`11818c12`) and becomes the argument passed to
    the slot's process callback fetched from `118133e0+4*slot` and invoked
    indirectly at `11818c16` (`BNOP.S2 B5,0`) — i.e. **`c01502cc`'s return
    value, not a fixed per-slot instance pointer, is what every slot callback
    receives as its first argument** (confirmed instruction trace; this is a
    new, not-previously-documented detail — recon/B2-B3 described the table
    fetch and indirect call but not this indirection step).
    `c01502cc` itself (`main.dis` ~93170-93390, **confirmed partial trace**):
    for slot index != 0, loads string constants `c0180cbc` (**"LOOPER"**,
    confirmed in `strings.txt` line 1458) and `c0180cc3` (**"RHYTHM"**,
    confirmed `strings.txt` line 1459 — both strings sit in the same table as
    `c0180cb1` `"FSW:ENTER"`, a footswitch-assignable-function menu list),
    and calls two helpers `c013a34c`/`c013a328` with the slot's data,
    comparing the results via `CMPEQ ... 1,B1` / `CMPEQ ... 2,B1` to derive a
    classification value that flows into the return value described above.
    It also reads `instance[3]` (`LDW *A4[3],A0` at `c0150382`) and
    conditionally branches through it or through `instance[6]`
    (`*A4[6]`) as a function pointer. **Confirmed**: this exact code exists
    and explicitly special-cases "LOOPER"/"RHYTHM" per slot. **Likely, not
    confirmed**: given the string table's footswitch-menu context, this is
    UI/bypass-state classification (e.g. "is this footswitch position
    assigned to toggle Looper/Rhythm instead of being a plain effect
    bypass"), not audio-sample mixing — but the `instance[3]`/`instance[6]`
    indirect-call behavior was not fully resolved and is flagged for
    follow-up (see Summary).
12. **`11818c44` CALLP `0x11817a90`** — patch-level gain mix. **Confirmed**,
    matches existing `docs/helpers/USB_OPT_ASTRA_2026-10-16.md` A2 finding 3
    exactly (re-verified by re-disassembling this pass): reads patch-level
    gain `c011acd4` (`A9`=`A22-4` at `11817b34`), builds a 16-sample
    interpolation ramp from `c011acd8`/`c011acdc`/`c011ace0`/`c011acec` into
    scratch curve buffers `11f03e20`/`11f03de0` (and working buffers
    `11f03830`/`11f03930`), multiplies the slot-loop output by that ramp and
    stores the mixed result into `11f037b0` (`11817c3c`, confirmed) and the
    second channel (`A20`, 16 words further). No evidence this function
    reads from `c016f780`/`c04abff0`/`c01834ac` (confirmed absence from its
    refs).
13. **`11818c48` CALLP `0x11818ea0`** with `A4=0`. **Confirmed, full trace**:
    veneer → `c013f594`. That routine does double-precision `SUBDP`/`MPYDP`/
    `ADDDP`/`DPSP` arithmetic (subtract two values, multiply by a constant,
    convert back to float) and stores results into offsets `[3]`/`[4]` of a
    struct pointed to by its instance argument (`A13`); it also walks
    function-pointer tables at `c0183a30`/`c0183a40` in a small bounded loop.
    **Guess**: elapsed-cycles→load-percentage style computation, consistent
    with the known "PROCESS OVERFLOW" firmware feature (recon/10); not
    rhythm/looper (no string/buffer reference to either).
14. **`11818c4e`/`11818c50` CALLP `0x11818e60`** with `A4=1` — second half of
    the dispatcher pair from step 6 (table index 1 this time).
15. **`11818c54` CALLP `0x11818d60`** — master/output gain. **Confirmed**
    (pre-existing, USB_OPT_ASTRA A2 finding 2): reads float gain `11f03e34`,
    writes final planar float output back into `11f037b0`/`11f037f0`
    (overwrites step 12's result in place).
16. **`11818c58` CALLP `0x11818428`** — float→int conversion. **Confirmed**
    (pre-existing).
17. **`11818c60` CALLP `0x118186e0`** — filter/mute stage, coefficient
    `11f03ebc`. **Confirmed** (pre-existing).
18. **`11818c64` CALLP `0x11818aa0`** — TX pack. **Confirmed** (pre-existing):
    reads planar int32 `11f038b0` (L) / `11f038f0` (R), writes the inactive
    DMA half. **This is the existing USB tap's hook point** (veneer replaces
    this CALLP, runs the stock pack, then copies `11f038b0`/`11f038f0` and
    `11f03730`).
19. **`11818c68` CALLP `0x11818cf4`** (confirmed address/location, **full
    trace**, leaf). Reads/writes a small state word near `c0183a24` with a
    short `SPLOOP` byte copy — looks like switch/rotary edge-debounce
    bookkeeping (**guess**); runs after TX pack, so it cannot affect the
    already-packed audio of this block regardless of what it does.
20. **`11818c6c` CALLP `0x11818ca0`** (confirmed address/location, **full
    trace**, leaf). Same family as #19, state near `c0183a1c`. Same caveat.
21. **`11818c70` CALLP `0x11818540`** (confirmed address/location only, body
    not fully disassembled this pass). Matches recon/B2's "rotary decoding at
    `11818c70`" note. Runs after TX pack; cannot affect this block's packed
    audio.

Epilogue `11818c74`-`11818c84`: restores `A10`, `B11:B10`, `A11`, returns.

**Where rhythm/looper could enter, per this trace:** the only point in this
list where "a thing gets added to the dry/effect signal under a
rhythm/looper-looking label" is step 11's `c01502cc`, and that is weak,
likely-UI evidence, not a confirmed audio-mixing site. No step in this list
reads the rhythm ROM (`c016f780`) or the looper candidate buffer
(`c01834ac`/`c04abff0`).

## R2. Rhythm rendering: not located this pass

**Confirmed absent from the Swi's call graph**: none of the 21 calls above,
nor any function they call (steps with "full trace, no CALLP inside" are
leaves; steps 6/13/14's dispatcher and its two resolved targets were also
fully traced), contain a reference to the rhythm constant-data table
(`c016f780`, recon/10) or to anything resembling PCM sample playback
(incrementing read pointer into a `.const` sample table, interpolation,
etc.). This was checked both by instruction-level reading and by grepping
`refs.txt` for `c016f7` across every traced function's address range.

**What IS confirmed to exist in this firmware, from `strings.txt`** (not
newly discovered, but not previously tied to a function body in
`recon/*.md`): `g_Event_RhythmService` (`c0172c99`), `g_Task_RhythmService`
(`c0172f3d`), and the UI string `"RHYTHM"` (`c0180cc3`, used by `c01502cc`,
see R1 step 11). The Task's actual function body was not located this pass
— SYS/BIOS Task/Swi objects in this firmware live in cinit-RLE-compressed
data (cf. recon/16 C3's decode of `g_Swi_AudioProcess`'s object at
`c0182a40`), not as a direct code xref to the name string, so finding it
requires decoding the Task-object table the same way, which this pass did
not do.

**No rhythm-alone buffer address can be given.** Candidates ruled out this
pass: `11f037b0`/`11f037f0` (shared effect-chain/output buffer, confirmed
written by many stages, not rhythm-specific); the 5 per-slot `0x81330`-byte
delay buffers at `c0226000` etc. (recon/14, DELAY_MEM_SONNET — confirmed
unrelated, those are generic per-slot effect scratch space reachable only
via `instance[3]`, not rhythm-specific); `c01834ac`/`c04abff0` (see R3 — this
is the looper candidate, not rhythm's).

**Open thread for a follow-up pass** (not completed here due to time):
(1) locate `g_Task_RhythmService`'s function pointer via the Task-object
cinit table (same method as recon/16 C3); (2) fully disassemble
`c013a34c`/`c013a328` (`main.dis` lines 63729/63742 — only their first CALLP
was glanced at this pass) to settle what `c01502cc`'s classification is
actually used for; (3) if rhythm turns out to be slot-resident (loadable
into one of the 5 effect-chain positions like a normal effect), the
tap point would be right after that slot's `BNOP B5,0` returns at
`11818c20`, reading `11f037b0`/`11f037f0` before the next slot overwrites
them — but this is speculative pending (1)/(2).

## R3. Looper rendering: not located this pass; buffer identity unchanged from prior work

Same negative result as R2: no play/record mixing code was found in the
Swi's call graph, and no reference to `c01834ac`/`c04abff0` was found in
any of the 21 traced calls or their sub-calls.

**One new confirmed fact this pass**, found while looking for callers of
`c0139ae0` (the routine `docs/helpers/DELAY_MEM_SONNET_2026-10-17.md` D4
flagged as reading the `c01834ac` descriptor): `c0139ae0` is not an
independent function — it is a label inside a much larger function spanning
roughly `c0139900`-`c013a000` (confirmed by following the only branch into
it, `c0139ac0 BNOP.S1 0xc0139ae0,1`). That larger function does effect-name
string copies via `c0164600`, calls `c014d528`/`c014d2bc`, and zeroes slot
state via `c0167b00` — all consistent with a **patch-load/apply** sequence,
**not** the per-block audio Swi. Inside it, `c0139ae0`-`c0139b10` reads the
looper descriptor's base field (`LDW *+A4[0],A0` with `A4`=`c01834ac`, so
`A0`=`c04abff0`) and copies it into variable `c011aca8`, then also derives
and stores a value of about `0x2b110` (close to, but not exactly, the
descriptor's `0x2b1100` size field — possibly a divided/shifted form, not
re-derived exactly) into a nearby cell. **Confirmed**: this patch-load code
explicitly reads and re-derives values from the `c01834ac`/`c04abff0`
descriptor. **Still likely, not confirmed**: that this makes `c04abff0` the
looper's buffer specifically — this is consistent with (raises confidence
slightly above) DELAY_MEM_SONNET's existing "likely looper, ownership not
confirmed" guess, but does not newly prove it, since the copied value
(`c011aca8`) was not traced further to see if it is later used by looper
playback/record code or by something else entirely (e.g. a generic
"largest free SDRAM block" bookkeeping value touched during every patch
load for an unrelated reason).

**Format, if `c04abff0` is confirmed to be the looper buffer**: unchanged
from DELAY_MEM_SONNET — `0x2b1100` bytes (~2.8 MB) contiguous SDRAM, no
format (sample width/channel count) was determined in that prior pass or
this one; the per-slot delay buffers it's structurally analogous to
(`DELAY_3S`/`ANDLY_3S`, recon D2) use 32-bit (4-byte) samples, so a similar
32-bit mono assumption would give ~16.8 s at 44.1 kHz, but this is **not
verified** for the looper buffer specifically.

**No pre/post-effects, pre/post-rhythm ordering for recording can be given**
— no record-side code was located at all this pass.

## R5. Follow-up: the four extra buffers `11817a90` touches

Re-disassembled `11817a90`-`11817cdc` in full (`main.dis` lines 17011-17171)
register-by-register, cross-checked against the startup zeroing sequence
(`c0165c80`-`c0165d78`, which zeroes every `11f03xxx` audio buffer in address
order with an explicit byte count per buffer — this is new evidence this
pass, not previously in any `recon/*.md`) and against the big per-feature
table-fill function `c014fea0`-`c01502c8` (also newly traced this pass).

**New structural fact (confirmed): the zeroing sequence gives buffer sizes
unambiguously.** `c0165c80`-`c0165d78` zeroes, in order: `11f03530`(128B),
`11f035b0`(128B), `11f03630`(128B), `11f036b0`(128B), `11f03730`(128B),
`11f037b0`(128B), **`11f03830`(128B)**, `11f038b0`(128B), **`11f03930`(64B)**,
**`11f03970`(64B)**, then `11f039b0`(32B, different init pattern — a
byte-accumulator, matches recon/16 C11's "unrelated" flag, confirmed still
unrelated). Every one of the 128-byte entries before `11f03830` is a
**known stereo pair** (e.g. `11f03730`/`11f03770` = ADC int32 L/R,
`11f037b0`/`11f037f0` = float L/R, `11f038b0`/`11f038f0` = TX int32 L/R —
all confirmed pre-existing). `11f03830`'s 128-byte zero call, by the exact
same pattern, means **`11f03830` is also a stereo pair: L at `11f03830`,
R at `11f03870`** (confirmed below by a second, independent piece of
evidence — the loop in `11817a90` itself). `11f03930` and `11f03970` are
each zeroed with only **64 bytes** — i.e. each is a **standalone mono**
16-float buffer, not part of a stereo pair.

### (a) What `11817a90` computes, and which buffers get added into `11f037b0`/`11f037f0`

**Confirmed, by direct trace of the per-sample loop (`11817bb0`-`11817c98`,
software-pipelined, outer count `B1`=2 for L-then-R at `11817bcc`/`c054`):**

- `11817b90`/`11817c9c`-area: `LDW *B6++[1],A6` reads **sequential floats from
  `11f03830`** (pointer `B19`/`B6`, confirmed).
- `11817b98`: `LDW *+A18[0],A3` reads the **existing** sample already in
  `11f037b0` (the effect-chain output, pointer `A18`/`A20`, confirmed).
- `11817bbc`: `ADDSP A6,A3,A3` — **`11f03830` is added directly, sample for
  sample, to the effect-chain output** (confirmed instruction).
- `11817bd4`: that sum is multiplied by `A7` = `*(c011acd4)` — **the patch-level
  gain** (confirmed register identity, matches
  `docs/helpers/USB_OPT_ASTRA_2026-10-16.md` A2 finding 3 exactly).
- `11817be0`: the result is multiplied again by `B4` = `*(c011accc)` (a second,
  separate gain cell — see (c) below for what this cell is).
- In parallel, `11817ba8`/`c0cb`-area: `LDW *A19++[1],B5` reads **sequential
  floats from `11f03930`** (pointer `A21`/`A19`).
- `11817bd8`: that sample is multiplied by `B8` = `*(c011acd0)` (yet another
  gain cell, adjacent to `c011accc`, same struct — see (c)).
- `11817bec`: `ADDSP A3,B5,A4` — the two branches are **summed together**.
- `11817c3c`/`11817c98`: the final value is stored back into `11f037b0`
  (`A18++`), i.e. **in place**, confirmed, matching Astra's existing finding
  that `11817a90` writes the mixed result into `11f037b0`.
- The **outer loop** (`B1`=2) confirms channel handling: after the first pass,
  `11817c40`/`c44` add **64 bytes** to both the `11f03830` pointer (`B19`) and
  the output pointer (`A20`) — moving to `11f03870`/`11f037f0` — so
  **`11f03830` is read as a true stereo pair, L then R** (confirmed, not just
  inferred from the zero-call size). By contrast, `11817c4c`/`c4e` **reset**
  the `11f03930` pointer (`A19`→`A21`) and the `11f03de0` pointer (`A17`→`A23`)
  back to their starting address for the second pass — **`11f03930` is mono
  and gets reapplied identically to both the L and R output channels**
  (confirmed).
- A third gain multiply chain (`11817c28`, `c38`, `c50`, `c64`, `c74`) folds in
  `A5` = `*(c011ace8)` and a broadcast constant computed in the function's
  first loop (`11817ad8`-`b18`, from `c011acd8`/`acdc`/`ace0`/`acec` — see (c)).
  **Likely, not fully nailed down**: the exact final algebraic order of all
  three-to-four multiplies (patch level × `accc` × `ace8` × broadcast-constant)
  was not resolved with full certainty — the code is heavily
  software-pipelined (values from different logical samples share a fetch
  packet), so hand-reconstructing the exact arithmetic order carries real
  risk of error beyond what's stated above. The **individual facts above
  (which buffer, which address, ADDSP vs MPYSP, stereo vs mono, which
  pointer resets each channel pass) are confirmed**; the precise combined
  formula is **likely** only.

**Qualitative summary (likely)**: `out[L/R][i] ≈ patchLevel × accc-gain ×
(chainOut[L/R][i] + buf_11f03830[L/R][i]) + acd0-gain × buf_11f03930[i]`,
with `ace8`/the `acd8`-family broadcast constant folded in as additional
smoothing/ramp factors.

### (b) Role of each buffer — producer not found

**No producer (writer of actual sample content) for `11f03830`, `11f03930`,
or `11f03970` was found anywhere in `main.dis` this pass.** Every reference
to these three addresses in `refs.txt` is accounted for and is one of: this
function's own reads (`11817a90`), the startup zero (`c0165xxx`, confirmed
above), or the feature-table fill at `c014ff58`-`c01502c8` (new trace this
pass, see below) which stores their **addresses** into a lookup table —
never writes sample data into them. This means **something writes 16 (or 32,
for the stereo one) floats into these buffers every block, but that writer
was not located** — it is not reachable from the audio Swi's own call graph
(R1), so it is most likely a function reached only through a pointer/table
this pass didn't resolve, or it runs as part of `g_Task_RhythmService`/
`g_Task_LooperUI` (R2/R3's still-unlocated Task bodies) writing directly into
these fixed L2 addresses ahead of the Swi's next invocation. This is the
single most important open thread from this whole investigation.

**The feature table (`c014fea0`-`c01502c8`, confirmed new trace this pass):**
immediately after the already-known per-slot `instance[3]` wiring (D1 in
`docs/helpers/DELAY_MEM_SONNET_2026-10-17.md`), the same large function fills
a **63-entry array at `11f03b48`** (one `STW ...,*A4[0]` per entry, `A4`
incrementing by 4 each time) with a mix of data-buffer addresses and function
pointers. Entries recovered: `[0]=11f03970`, `[1]=11f037b0` (the effect
output buffer), `[2]=11f03830`, `[3]=1180a2a8`/`[4]=1180a220` (ramp-start
helper functions, same family as Astra's A2 finding 3's `1180a2a8`),
`[5]=c0164684` (the mute/level-coefficient setter Astra found at A2 finding
1), `[6]=c0164600` (a byte/string-copy helper used throughout the patch-load
code traced for R3), `[7]=11f03e20`, `[8]=11f03de0`, `[9]=c011ad60`,
`[10]=11f03e38`, entries `[11]`+ are further function pointers in the
`c013dxxx`/`c016xxxx`/`1180axxx` ranges (several of which are the exact
helpers called from `c013f594`, the CPU-load-looking routine from R1 step
13 — e.g. `c016c240`, `c013ee60` both appear both as table entries and as
direct `CALLP` targets inside `c013f594`). **Confirmed**: this table exists
and holds these specific entries, in this order. **Guess**: given the mix of
data addresses and function pointers, this looks like a generic
"per-feature descriptor" array (one entry per internally-numbered
setting/feature) rather than something rhythm/looper-specific; it does not
by itself identify who produces `11f03830`'s or `11f03930`'s samples — it
only shows where their *addresses* are published, presumably for some other
code to look them up by feature-ID rather than by hardcoded immediate.
Note `11f03930` is **not** in this table (consistent with the user's
observation that it's otherwise only referenced at `11817b70` and the
zeroing call) — whatever writes it must either hardcode the immediate the
same way `11817a90` does, or reach it through a different table entirely.

### (c) What is `c011acec` (and the neighboring cells)?

**`c011acec` is a mirrored copy of the patch-level gain `c011acd8`, not a
rhythm or looper volume (confirmed by direct trace).** Function `c01618a4`-
`c01619d8` (`main.dis` lines ~115760-115880) is the patch-level **apply**
routine: it calls the curve-mapping helper `c0151ce0` with value 101 (the
exact 0-100/101-120 split Astra's A2 finding 3 already established for patch
level), stores the result into `c011acd8` (`c01618e4`, confirmed), then
checks a global flag bit at `1180312c` bit 31 and — only when that bit is
set — **also** stores the identical value into `c011acec` (`c01618f8`-
`c0161904`, confirmed). A second branch in the same function (triggered when
a *different* test of the same `1180312c` flag succeeds, `c0161958`-`c0161988`)
instead writes the float constant **1.0** into both `c011acd8` (`c0161976`)
and `c011acec` (`c0161984`), then starts output-volume-style ramps (via
`c016f320`, same ramp helper and the exact same duration constant
`0x44306666` Astra found for master-volume smoothing) on `c011ace4`
(`c011accc+0x18`) and `c011ace8` (`c011accc+0x1c`). The third writer the
coordinator flagged, `c016bdf0`, was not fully traced but uses the identical
`MVK 0xffffacec,A4` pattern (same mirror-store idiom).

**`c011accc` is touched by a separate, more general routine, `c01435a0`-
`c0143710`, which is the same "all-slots mute" sequence recon/16 B2 already
identified** (`c01435a0` is literally the function that sets the audio-mute
flag `B14[101]`/`c0184f94` at `c01435ac` — the exact flag the audio Swi reads
at `11818bd8`, R1 step 10). Immediately around that mute-flag set, this
function also: calls `c016d220` (Astra's A2 finding 1 output-mute ramp),
ramps `c011accc`/`c011accc+4` toward `0x44306666` via `c016f320`, checks the
same `1180312c` flag, and — when clear — loops over all 5 slots calling
`c012afe0`, `c014ff44`, and **`c01502cc`** (the same per-slot
LOOPER/RHYTHM-string-checking routine from R1 step 11!) before an indirect
call through each slot's `instance[7]`. This matches recon/16 B3's
"all five callbacks substituted before unload/load" reload sequence almost
exactly, just with `c01502cc` now confirmed as part of it.

**Conclusion (confirmed by these two traces together): `c011accc` through
`c011acec` (9 contiguous words, `accc,ad0,ad4,ad8,adc,ae0,ae4,ae8,aec`) is a
shared "whole-chain mute/level ramp" structure used by (1) the patch-level
0-120-range apply code and (2) the generic all-slots mute/reload sequence,
gated by the same global flag `1180312c`.** It is **not** a rhythm-specific
or looper-specific volume control by any name/string evidence found — no UI
string was found near either writer. This directly answers (c): **it is, at
best, a generic ducking/mute-ramp gain, most plausibly tied to patch-level
and reload-time muting, not a dedicated "rhythm volume" or "looper level."**
This also means `11f03830`/`11f03930`'s gain multipliers (`c011accc`,
`c011acd0`) are driven by this same general mute infrastructure, which
weakens (without ruling out) the rhythm/looper-send hypothesis — it is
equally or more consistent with `11f03830`/`11f03930` being a **generic
crossfade/carry-over bus used across slot reloads** (e.g. "previous state to
fade from") rather than a standing rhythm or looper send.

### (d) Is one of these the rhythm or looper signal alone?

**Not confirmed either way.** What's established:

- **`11f03830`**: float, **stereo** planar (L `11f03830`, R `11f03870`,
  confirmed by the loop's own 64-byte-per-channel pointer advance, matching
  every other real audio buffer's layout convention), 16 samples/channel.
  Added directly (`ADDSP`, confirmed) to the effect-chain output inside
  `11817a90`, before the patch-level-gain multiply. **Last point in the Swi
  where it is read intact for this block: `11817b90`/the equivalent
  R-channel read on the loop's second outer pass (inside R1 step 12,
  `11817a90`, called from `11818c44`)** — i.e. it must be freshly written by
  its (unlocated) producer sometime before `11818c44` runs each block.
- **`11f03930`**: float, **mono**, 16 samples (confirmed 64-byte zero, and
  confirmed mono by the pointer-reset-per-channel behavior in the loop).
  Scaled by `c011acd0` and summed in as a second term. **Last point in the
  Swi where it is read intact: `11817ba8` (first channel pass) inside the
  same `11817a90` call.**
- **`11f03970`**: float, mono, 16 samples (same zero-size pattern as
  `11f03930`), its **address** is published in the feature table slot `[0]`
  — but **no consumer of its contents was found anywhere in `main.dis`**
  (`refs.txt` shows only the table-writer and the zero-call referencing it).
  This is the weakest-evidenced of the four buffers; it may be the "other"
  of a rhythm/looper pair, or something unrelated whose only consumer reaches
  it indirectly through the feature table (not as a literal immediate, so
  `refs.py`'s MVK/MVKH scan would miss it).

**No buffer here was confirmed, by name or by any producer code, to be
"rhythm alone" or "looper alone."** The honest state of the evidence: these
are real, additional, per-block audio-rate (16-sample) mix buses that get
summed into the main output in `11817a90` — which is exactly the shape a
rhythm or looper send would have — but their gain cells trace back to
generic mute/reload infrastructure rather than anything string-identified as
rhythm or looper, and their producer (who actually writes samples into them)
was not located. Settling this requires finding that producer — almost
certainly inside `g_Task_RhythmService` or `g_Task_LooperUI`'s own task-body
code, which neither this pass nor the original R2/R3 pass located.

## R4. Buffer addresses at TX-pack time

- **Effect chain output, before rhythm/looper (and before patch-level gain,
  master gain) are added — confirmed, new tap point this pass**:
  `11f037b0` (L) / `11f037f0` (R), float, planar, 2 channels, 16
  samples/channel. This is the state of the buffer in the gap between
  `11818c38` (end of the 5-slot loop) and `11818c44` (start of
  `11817a90`, patch-level gain). It is intact at that exact point and
  overwritten in place twice afterward (`11817a90` at step 12, then
  `11818d60` at step 15). A hook could use the same veneer-and-copy
  technique already used at `11818c64` for the USB tap, but placed at
  `11818c44` instead, to capture "pure effect-chain output, before any
  trim/master gain" per block.
- **Rhythm alone / Looper alone, at TX-pack time or any other point in the
  block — not found.** No buffer holding either signal in isolation was
  identified (see R2/R3). Nothing in this report should be read as ruling
  out that such a buffer exists; it simply was not located within the
  21-call graph of the audio Swi that this pass exhaustively traced.
- **Existing USB tap, reconfirmed unchanged**: `11818c64`'s veneer around
  `11818aa0` (TX pack) copying `11f038b0` (L) / `11f038f0` (R) — planar
  int32, post-mute/filter, post-master-gain, post-float→int — and
  `11f03730` — planar int32 dry ADC left — matches the task's stated
  "known context" exactly; this pass found no reason to revise it.
