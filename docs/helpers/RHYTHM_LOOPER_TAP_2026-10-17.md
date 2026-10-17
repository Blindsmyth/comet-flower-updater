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
