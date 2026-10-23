# FW RND S11: slot-fit rule for header 0x58 = 3/4 (PROCESS OVERFLOW)

## Status
done (ran out of promising leads inside c01297a0 before finding the true
trigger; see Not checked)

## Findings

### Finding 1: c013b8c0's exact arithmetic (confirmed, straight-line, no delay-slot ambiguity)
`c013b8c0` (chunk_08 calls it `midi_assign_slot_check_available`, 2 args A4/B4) computes,
reading `build/fw/map/main.dis` c013b8c0..c013b8f8 top to bottom:
```
c013b8c4  A11 = B4                              ; save arg1
c013b8c8  B4  = 0x11811598                       ; fixed table base
c013b8d0  CALLP c013b690,B3   (A4=arg0, B4=table) ; X = c013b690(arg0, table)
c013b8d4  A10 = A4 + 1                            ; A10 = X + 1
c013b8d8  CALLP c012b260,B3   (A4=A11=arg1)        ; Y = c012b260(arg1)
c013b8e2  CALLP c013b798,B3   (no visible args)     ; Z = c013b798()
c013b8e6  A0 = A4 - A10        = Z - (X+1)
c013b8ea  A0 = A0 + A11(=Y)    = Z - (X+1) + Y
c013b8ec  A0 = CMPLTU(7, A0)   ; A0=1 iff A0_sum >u 7
c013b8f4/f6  A0 = A0 ? -1 : 0
c013b8f8  return A0
```
So: `result = (c013b798() - (c013b690(arg0,0x11811598) + 1) + c012b260(arg1)) >u 7 ? -1 : 0`.
This matches the brief's lead exactly. **Confidence: confirmed** (plain sequential
arithmetic, no branch-delay reordering involved in this part of the function).

### Finding 2: c013b8c0's two callers, and what -1 actually does downstream (confirmed)
Two call sites, both already in `recon/map/chunk_08.md`, re-verified by direct read:
- `c013ba34` (`midi_assign_apply_dispatch`, single caller `slot_param_type_dispatch`
  c0133254): `CALLP c013b8c0; CMPEQ -1,A4,A0; [A0] CALLP c013b904(A6=0) else CALLP
  c013b904(A6=1)`. So -1 selects the `A6=0` ("new") argument to
  `midi_assign_apply_record`, 0 selects `A6=1` ("existing"). This reads like a
  find-or-create flag, not an accept/reject flag.
- `c013ba64` (`midi_assign_table_entry_check`, called from `midi_slot_param_dispatch`
  c0132b78 at c0132d44): after the call, `c0132d4a CMPGT.L1 0,A4,A0` (true iff A4 is
  negative, i.e. -1); the taken path (confirmed via c0132d50) calls `c01400a0` with
  `B4=1` -- `c01400a0` is `status_bit_set_18e4` (chunk_09, confirmed), a generic
  bit-setter that sets bit `A1` (here, whatever index c0132b78 passes) of the global
  halfword at `0x1181_18e4` to 1. So -1 here sets a per-index flag bit at 0x1181_18e4,
  which is a plausible "something is wrong with this slot" flag, but I did not find who
  *reads* 0x1181_18e4 to decide whether to show an error, so the link to the on-screen
  "PROCESS OVERFLOW!! CHANGE EFFECT" text is NOT shown by this trace.
**Confidence: confirmed** for the two call sites and the immediate use of the return
value; **not found** for any code that reads 0x1181_18e4 and renders an error screen.

### Finding 3: controlled ZD2 diff rules out the already-confirmed dspload gate as the cause (confirmed)
`build/fw_rnd/F3/verify.py` (from an earlier job, re-run this session) parses
`build/CFM2P.ZD2` / `CFM3P.ZD2` / `CFM4P.ZD2` / `CFM5P.ZD2` and diffs their headers:
```
| file      | 0x58 | id         | dspload |
| CFM2P.ZD2 |  2   | 0x07000f8d | 10.00   |
| CFM3P.ZD2 |  3   | 0x07000f8e | 10.00   |
| CFM4P.ZD2 |  4   | 0x07000f8f | 10.00   |
| CFM5P.ZD2 |  5   | 0x07000f8c | 10.00   |
```
Byte-diff CFM2P vs CFM3P/CFM4P: only the CRC32 (0x08-0x0b), slot-count byte (0x58),
effect id (0x60) and name (0x68) differ -- `dspload` is identical (10.00) in all four,
far below the confirmed Process-Overflow dspload-sum threshold of 230.0f
(`docs/DSP_RULES.md`, c0141ad8..c0141b60). CFM2P places fine; CFM3P/CFM4P overflow on
an otherwise-empty patch (`docs/FW_RND_BENCH_2026-10-22.md` section 2, step 2: "put CF
M3 in slot 1 of an empty patch"). **This rules out the dspload-sum gate as the cause**:
the trigger is specific to header 0x58 (and/or the new effect id), not to declared CPU
load. **Confidence: confirmed** (direct byte comparison + the already-confirmed,
independently-documented dspload gate address/threshold).

### Finding 4: the real "place/switch effect in slot" function does not call c013b8c0's chain at all (confirmed, weakens the brief's lead)
`effect_slot_switch_reload` (`c013f9f0`, chunk_09: "switches the active effect slot" --
this is the function the LCD "pick an effect for this slot" action drives, per
recon/16_audio_hw.md B2/B3) was read for its complete call list
(`build/fw/map/main.dis` c013f9f0..c013fab0, every CALLP instruction):
```
c0140258, c013f6d0, c014ab0c, c0150b20, c016f4d0, c016f4c0, c014ff44, c016f660,
c013f858, rts_memset(c0167b00), c0151598, c013f78c, c0129698, c012fb9c
```
None of these is `c0133398`/`c0133254`/`c013ba34`/`c013ba64`/`c013b8c0`. The chain ends
at `c012fb9c` (`midi_apply_or_fallback`, chunk_05, confirmed), which calls
`c01297a0` (`effect_slot_load_unload`, the ZD2 loader) directly. **The whole
`c0133254`/`midi_assign_*`/`c013b8c0` cluster is reached only from MIDI CC/note-assign
code paths** (`c012fd28`, `c012ff14`, `c0134568`, `c0132b78`=`midi_slot_param_dispatch`,
etc. -- all MIDI-side per `recon/map/chunk_05.md`/`chunk_06.md`), not from the LCD
effect-picker's actual slot-switch routine. **This directly contradicts the hardware-results
doc's "(Claude, partial)" hypothesis** that c013b8c0's -1 "is what the UI reports as a
process overflow" for header 3/4 placed via the LCD menu: the LCD path never reaches
c013b8c0. **Confidence: confirmed** that c013f9f0 does not call that chain (full CALLP
list read); **likely** that this means the chain is irrelevant to the LCD PROCESS
OVERFLOW symptom (can't rule out a second, indirect path with 100% certainty without
tracing c012fb9c and c01297a0 end to end, which was not completed -- see Not checked).

### Finding 5: inside c01297a0, the header byte is read at least 3 times, but the uses found so far look like catalog bookkeeping, not a per-placement reject (likely)
Beyond the already-confirmed listing ceiling (`c0129904..c012990c`, `docs/helpers/
FW_RND_S1_LIST_PARAMS_2026-10-22.md` Finding 5: reject if header>4, but the reject
target c0129b40 falls into ordinary BYPASS/BPS tag-string code, not an error path), the
same local header-byte copy (`*+B15[128]`) is read twice more further down the same
function:
```
c0129a6c  LDBU.D2T2 *+B15[128],B6      ; same header byte, into B6 (use not located)
c0129ab4  LDBU.D2T1 *+B15[128],A0
c0129ab8  MVK.S1 0x4528,A4
c0129ac0  MVKH.S1 0xc0060000,A4        ; A4 = 0xc0064528  (matches the brief's cited
                                       ;  catalog address exactly)
c0129ac6  STB.D1T1 A0,*A5[A4]          ; store header byte at 0xc0064528 + A5 (A5=A14,
                                       ;  a running index threaded through this whole
                                       ;  block -- looks like "catalog slot i")
```
Immediately around it, the same A5-indexed pattern writes other header-derived bytes/
words into sibling arrays at `0xc0064500`, `0xc0064508`, `0xc0064518`, `0xc0064520`,
`0xc00644d0`, `0xc00644e8`. This reads as a **one-time catalog-registration pass**
(copying each ZD2's header fields into flash-resident parallel arrays indexed by
catalog position, consumed later by `c012b260`'s id-keyed search), most plausibly run
once per file at boot/file-system-scan time, not as part of handling one specific
"place this effect in this slot" user action. **Confidence: likely** for "this is
catalog registration, not a per-placement check"; **not found**: proof of when this
code path actually runs (boot-time scan vs. on-demand), and what B6 (c0129a6c) is used
for.

### Finding 6: no other header-tied numeric gate exists anywhere in c01297a0 (confirmed, negative result)
Scanned every `CMPLTU`/`CMPGTU`/`CMPGT`/`CMPLT` instruction in the full body of
`c01297a0` (c01297a0..c0129db4, confirmed end address via its epilogue `CALLP
0xc016e000` at `c0129db4`, matching chunk_04's "1560B" size): only 4 compares exist in
the whole function -- `c01298e6` (an unrelated `A1,A0` compare feeding the ZDLF-tag
check at c0129900), the already-confirmed `c0129908 CMPLTU 0x4,B0,B0` (the >4 ceiling),
and two `CMPGTU 0x11,B1,B0` (0x11=17, at `c012984c` and `c0129a44`, both look like an
unrelated chunk-tag/index range check, not slot-count). **There is no second,
header-value-scaled comparison inside the loader that could explain "3/4 specifically
overflow, 1/2 don't"**; whatever causes the observed PROCESS OVERFLOW is either outside
`c01297a0` entirely (in `c012fb9c`'s caller-selected success/failure path, in
`c012ed70`=`midi_apply_value_cascade_a` which `c012fb9c` tries first, or in a renderer
that reacts to a side effect such as the catalog bytes Finding 5 found being written to
0xc0064500-series addresses), or it is a non-comparison effect (e.g. a value computed
from the header byte that corrupts/overruns something elsewhere, rather than an explicit
threshold test). **Confidence: confirmed** (exhaustive compare-instruction scan of the
whole function); the actual trigger remains **not found**.

## Answers

### c013b690 and c013b798: what they return, in what units
- `c013b798()` (chunk_08 "midi_assign_freelist_count_fixed"): confirmed to call
  `c013b764` against the fixed table `0x11811598`, which walks a 56-byte scratch buffer
  (`0xc00be5c8`, rebuilt by `c013b6c8` from the table) for up to 14 entries and returns a
  loop-iteration counter in A2. **Likely** a count of valid/used entries in that table,
  but the exact stop condition (a `CMPGTU` on successive entries, chunk_08: "until a stop
  condition") was not resolved to a clean "count of occupied rows" semantic within budget
  -- **guess** for the precise unit.
- `c013b690(idx, table)` (chunk_08 "midi_assign_slot_find_free"): confirmed to scan a
  4-word (16-bit) window of the bitmap at `table+840` via `c013b660`, and on a hit reads
  a value from the matched 84-byte record (`table + idx*84`) in a region whose exact
  provenance (a direct field read vs. `c012b260`'s return) could not be disambiguated
  from the delay-slot-packed instruction sequence at c013b6b2..c013b6ba -- **likely**
  returns something like "the record's own stored index, minus 1", **guess** for whether
  this is truly a "free slot index" in the sense the brief's lead assumed.

### The full formula (confirmed arithmetic, semantics only likely/guess)
`result = (c013b798() - (c013b690(arg0, 0x11811598) + 1) + c012b260(arg1)) >u 7 ? -1 : 0`
(Finding 1). What `7` represents and why a patch with N effects would push 2 effects
through and fail 3/4 was **not resolved**: I could not find a clean reading of Z
("count") and X ("free+1") that reproduces the hardware-observed behaviour (CFM2P OK,
CFM3P/CFM4P overflow, tested by the owner **on an empty patch, slot 1**, per
`docs/FW_RND_BENCH_2026-10-22.md` step 2 -- meaning this is not simply "patch is nearly
full"). Combined with Finding 4 (the LCD slot-switch path never reaches this function at
all), my overall assessment is that **this formula is very likely unrelated to the
observed PROCESS OVERFLOW bug** -- it is MIDI CC/note-assignment table bookkeeping
(chunk_08's naming), reached only from MIDI-side callers (`c012fd28`, `c012ff14`,
`c0132b78`=`midi_slot_param_dispatch`), not from the LCD's effect-picker
(`c013f9f0`=`effect_slot_switch_reload`).

### Who calls c013b8c0, and does -1 show PROCESS OVERFLOW?
Two callers, both MIDI-side (Finding 2): `c013ba34` (uses -1/0 to pick a "new"/"existing"
argument for a record-apply call -- reads like a find-or-create flag, not a reject) and
`c013ba64`/`c0132b78` (sets a bit at global `0x1181_18e4` on -1, via the generic
bit-setter `c01400a0`). **No code was found that reads `0x1181_18e4` or displays an error
screen from either path.** Given Finding 4, I do **not** believe -1 from `c013b8c0` is
what produces "PROCESS OVERFLOW!! CHANGE EFFECT" for CF M3/CF M4 on the LCD. Confidence:
**likely** (not proven absent, since I did not trace every reader of 0x1181_18e4).

### What does the "7" mean?
**Not resolved.** Given the formula's likely irrelevance to the actual bug (Finding 4),
and that I could not pin down the units of `c013b690`/`c013b798` with confidence
(above), I am not willing to guess what capacity or count "7" bounds. Flagging as open
rather than filling the gap with a plausible-sounding number.

### Can a firmware patch change the real PROCESS OVERFLOW-for-header-3/4 behaviour?
**Not answerable yet** -- the triggering code was not located. The one candidate
single-instruction patch that *is* confirmed and well-understood is `c0129908`'s
`CMPLTU 0x4` (raise to loosen the *listing* ceiling to allow header 5+), which is
unrelated to this bug (`docs/helpers/FW_RND_S1_LIST_PARAMS_2026-10-22.md` Finding 5) and
already a known, separate lever.

## Not checked / open leads
- `c012ed70` (`midi_apply_value_cascade_a`), tried first by `c012fb9c` before falling
  back to `c01297a0` directly -- not read at all this session. If it behaves
  differently for header 3/4 vs 1/2, this is now the single most promising unexplored
  function on the actual LCD placement path.
- The renderer/message-ID path for "PROCESS OVERFLOW!! CHANGE EFFECT" itself: the string
  is not present as plain ASCII in `build/fw/map/strings.txt` (only stack-overflow
  messages matched "overflow"), so it is very likely drawn from a numeric message-ID
  table, not a literal C string -- that table/renderer was not located.
- Finding 5's catalog-write block (0xc0064500-series arrays, 0xc00644d0/e8): whether it
  runs once per file at boot/filesystem-scan, or again each time a slot is loaded/
  switched, was not determined. If it runs per-switch and a fixed-size catalog array is
  overrun by newly-added custom effects (CFM3P/CFM4P happen to be the two highest-id
  custom files among this probe set), that would be a capacity-overrun bug with no
  relation to the header value's *meaning* -- only incidentally correlated with it in
  this specific 4-file probe set. Not ruled in or out.
- `c013b690`'s true "free slot" semantics and `c013b798`'s true "count" semantics
  (which record set they actually describe) were not nailed down byte-for-byte; see
  Answers above.
- Did not trace every caller/reader of the global halfword `0x1181_18e4` (Finding 2).
