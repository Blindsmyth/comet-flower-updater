# S1 - Effect list filter, slot-count byte, param limits

## Status
done (stopped near the ~2h budget; see Not checked / open leads for what remains)

## Findings

### Finding 1: Process Overflow (dspload sum) check, CONFIRMED at c0141ac8..c0141b60
This is the "patch admission" gate from `docs/DSP_RULES.md` ("Process Overflow rule"),
independently re-traced here at the instruction level (not just trusted from the doc).
It is a **different mechanism from the effect-list filter** (Q1) -- it sums a float
`dspload` bookkeeping value, not the integer header-0x58 slot count.

```
c0141ad8  MVK.L1   1,A0            ; loop i=0 bit mask seed
c0141ae0  SHL.S1   A0,A1,A0        ; A0 = 1<<i
c0141ae4  AND.L1   A1,A0,A0        ; test active-slot bitmask bit i
c0141ae6  [!A0] BNOP 0xc0141b32,5  ; slot i inactive -> add 0.0 to sum
c0141ae8  CALLP.S2 0xc012edcc,B3   ; slot active -> fetch/apply this slot's value
...
c0141b14  ADDSP.L2X B0,A4,B0       ; sum += this slot's declared dspload (float)
...
c0141b44  ADD.L1   1,A10,A10       ; i++
c0141b48  CMPGT.L1 5,A10,A0        ; loop while i<5
c0141b4c  [A0] BNOP 0xc0141ad8,5
c0141b50  LDW.D2T2 *B15[1],B0      ; B0 = accumulated sum
c0141b54  MVKH.S2  0x43660000,B4   ; B4 = 230.0f  <-- matches DSP_RULES.md exactly
c0141b60  CMPLTSP.S2 B0,B4,B4      ; B4 = (sum < 230.0) ? 1 : 0
c0141b68  XOR.L1X  1,B4,A4         ; A4 = NOT(sum<230) = overflow flag
```
Confidence: **confirmed** (read in full, c0141aa8..c0141b70, main.dis). Caller:
`c0141ac8` (named `effect_slot_list_update` in recon/map/chunk_09.md) is itself called
from 11806120, 11806450 (`midi_usb_orchestrator_1180`) and recursively at c0141b74/c0141bc4
(a bitmask-clear retry loop that calls this overflow check once per candidate active-slot
bitmask -- consistent with "which bit can I clear to fit under 230" logic, not yet traced).
Patch-site note: changing the 230.0f constant is a one-word MVKH edit at c0141b54; this
does not touch the Q1/Q3 mechanisms below.

### Finding 2: fxparam_page_size (0x11807eb8), page-size formula CONFIRMED by direct read
Re-disassembled independently (recon/map/chunk_01.md already described this function as
"guess"; the trace below is new, from main.dis, and upgrades it to confirmed instruction
semantics, though the real-world meaning of one input (`r`) stays a guess):

```
11807ecc  CALLP 0xc012af98,B3   ; X = rts_const_return_1() -- see Finding 3, X==1 always
11807ed4  CALLP 0xc012b048,B3   ; n = param count for this list entry's effect slot
11807ee0  CALLP 0xc012f628,B3   ; r = c012f628(slot) -- see Finding 4, r in {0,1}
11807ee4  MV.L1 A10,A0          ; A0 = X
11807ee6  SHL.S1 A0,0x2,A0      ; A0 = X*4   <-- the "4" is a bare SHL-by-2, no MVK 4 or
                                ;     named constant anywhere in this function
11807ee8  SUB.L1 A0,A4,A1       ; A1 = 4*X - r   (base page size, "A1")
11807eea  ADD.L1 A1,-1,A2       ; A2 = A1-1          (kept if n > A1)
11807eec  MV.L1 A11,A0          ; A0 = n
11807eee  CMPGT.L1 A0,A1,A0     ; A0 = (n > A1)
11807ef0  [A0] BNOP 0x11807ef6,5
11807ef4  MV.L1 A1,A2           ; (not taken: n<=A1) A2 = A1   -- overwrites the -1 version
11807ef6  MV.L1 A2,A0           ; return value = A2
```
So `page_size = (n > 4*X - r) ? (4*X - r - 1) : (4*X - r)`, with X==1 confirmed (Finding 3).
For the common case of a multi-knob effect (n > 4, the usual case for any effect with more
than a handful of params) and r==0 (Finding 4's typical case), this evaluates to **3**,
matching the handoff's observed "3-params-per-page" layout. For r==1 it would instead be 2.
Confidence: **confirmed** for the arithmetic/branch structure (read in full,
11807eb8..11807ef8); **likely** (not confirmed) that this is *the* mechanism behind the
3-per-page UI layout, since the higher-level screen-draw caller that turns this count into
drawn rows was not traced. The literal "4" exists only as an `SHL #2` shift, not as a
named/visible immediate -- there is no single `MVK 4` instruction to point to as "the" 4.

### Finding 3: c012af98 = rts_const_return_1, CONFIRMED
```
c012af98  MVK.L1  1,A4     ; A4 = 1
c012af9a  BNOP.S2 B3,5     ; return
```
Two-instruction leaf, always returns the constant 1. Confirmed (full read). This settles
X==1 in Finding 2's formula.

### Finding 4: c012f628, CONFIRMED disassembly -- a 1-pass existence check disguised as a loop
```
c012f628  MV.L1  A4,A13          ; A13 = slot (arg)
c012f630  CALLP  0xc012af98,B3   ; returns 1 -> loop count
c012f638  MVK.L1 0,A11           ; A11 = 0 (accumulator)
c012f640  MV.L1X B0,A12          ; A12 = 1 (loop count, from X)
c012f648  CALLP  0xc012ee80,B3   ; B4=index(0), A4=slot -> returns a flag
c012f652  [!A0] BNOP 0xc012f658,5 ; skip increment if flag==0
c012f654  ADD.L1 1,A11,A11        ; else A11++ (count becomes 1)
c012f658  SUB.L1 A12,0x1,A0       ; loop-count-- ; loop while nonzero (runs exactly once)
c012f66e  EXTU.S1 A0,24,24,A4     ; return A11 as a 0/1 byte
```
So `c012f628(slot)` returns 1 iff `c012ee80(slot, index=0)` is nonzero, else 0 -- i.e. it
is a boolean "does param-descriptor-entry-0 of this effect satisfy some flag?" test, not a
real count. Confidence: **confirmed** for the mechanics (full read, c012f628..c012f674);
**guess** for what the `c012ee80(slot,0)` flag actually means (not traced further; could be
"effect has a reserved param 0" e.g. a bypass/mode control that eats one of the 4 page
slots, which would explain the 4-vs-3 split cleanly, but this is not verified).

### Finding 5: candidate site for the header-0x58 ">4" rejection, LIKELY but NOT fully confirmed
In `effect_slot_load_unload` (c01297a0, A4=slot index, B4=load/unload flag -- the function
recon/14 and recon/18_round3.md already identify as the per-slot ZD2 load path), right
after the ZDLF "INFO" tag match loop (c0129894..c01298ac, confirmed against recon/14's
cited c017f598="ZDLF" signature) and a "target capability bit 2 must be set" check
(c01298f4..c0129900, matching recon/03's "bit 0x2 in every one" finding):
```
c0129904  LDBU.D2T2 *+B15[128],B0   ; B0 = a byte from the parsed-header local copy
c0129908  CMPLTU.L2 0x4,B0,B0       ; B0 = (4 < B0), i.e. B0_value > 4
c012990c  [B0] BNOP 0xc0129b40,5    ; if value>4, branch away (shared with the bit-2 check)
```
The threshold **4** sits exactly between the hardware-observed accepted value (CFM2P,
header 0x58 = 2) and the rejected value (CFM5P, header 0x58 = 5) from the handoff. This is
a real, confirmed comparison-and-branch in the loader's header-validation block; what is
**not** confirmed is that the byte at local offset B15[128] is literally file offset 0x58
(the copy's field-to-local-offset mapping was not traced byte-for-byte -- the "INFO" magic
match loop copies into B15+8 progressively, so B15+128 would be relative offset 120 from
that base, not 0x58=88; the discrepancy means either extra fields are consumed before the
raw struct copy proper, or this is a different field entirely that happens to also cap at 4).
Caveat that weakens the "this hides it from the pick-list" reading: the branch target
c0129b40 does NOT render a "missing effect"/error message -- it leads into code that writes
per-slot status words and then calls the string renderer with addresses that resolve (via
`build/fw/map/strings.txt`) to **"BYPASS"**/`"BPS"` (c017f5a7/c017f5ae), i.e. the same tag
strings recon/14 already found guarding the ZDLF container's BYPASS/BPS sub-chunks. This is
as consistent with "fall through to checking the BYPASS/BPS chunk tag next" (normal ZDLF
chunk-tag dispatch) as with "reject this header and mark the slot bypassed" -- the two
readings were not distinguished. Confidence: **likely** that a firmware-side cap near 4
exists in this header-validation block; **guess** that this specific branch is the Q1
"why is CFM5P excluded from the add-effect list" mechanism, and **not found**: the actual
browse/pick-list-building function that enumerates candidate effects for a slot (distinct
from this load-time validator) was not located in the time available.

### Finding 6: the 12-param maximum -- NOT FOUND as a firmware-enforced constant
Searched the per-slot parameter/knob dispatch cluster (chunk_06 c0132430..c0133398,
chunk_09 c013eeec..c0142300: `slot_knobcount_ui_update` c0132980, `knob_probe_loop_7`
c013f78c, `slot_knob_index_clamp_and_dispatch` c013f6d0) and the generic indexed-table
accessors (c012afe0/c012b008/c012b048) for a literal 12-entry array bound or `MVK 12`
comparison tied to param count; none found. `docs/CF_MASTER_PROBE_2026-10-19.md` already
states "Stock effects have at most 9 knobs (zd2 audit: 11 table entries). 12 is the
stomphacks maximum" -- i.e. the "12" in the handoff/brief looks like a **build-tool
(stomphacks) convention**, not a number this firmware itself compares against anywhere
found. `slot_knob_index_clamp_and_dispatch` (c013f6d0, called from
`slot_knobcount_ui_update`) does loop a fixed **4** times over two 4-entry function-pointer
tables (0xc0183a30, 0xc0183a40 -- confirmed by direct read, `MVK.L1 4,A0` at 11807... no,
at c013f6e8) regardless of the effect's real param count, which is consistent with "4
physical/on-screen widget slots" rather than any param-count ceiling. Confidence:
**confirmed** that no 12-bound exists in the functions checked; **not checked**: the Dll
entry-struct's declared-descriptor-array capacity (whether the 56-byte-descriptor array at
c012afe0 is a fixed-size field in the loaded ELF structure vs. sized from file content) --
this would be the place a true firmware-side array-capacity cap could still hide, and was
not traced in the time available.

## Answers

### Question 1: effect list filter / why header 5 is hidden, header 2 is offered
- **Where the header slot-count is read and checked:** the strongest candidate found is
  `effect_slot_load_unload` (c01297a0), in its ZDLF/INFO header-validation block
  (c0129904..c012990c, Finding 5): a byte from the parsed header is compared `>4` and, if
  so, branches away from the normal accept path. This threshold sits exactly between the
  hardware-observed accepted value (2) and rejected value (5). **Likely**, not confirmed:
  the byte's provenance as literal file-offset 0x58 was not proven, and the branch target
  renders ZD2's own "BYPASS"/"BPS" tag strings rather than an obvious error message, so it
  may instead be ordinary ZDLF chunk-tag dispatch rather than a reject-this-effect path.
- **Is the limit the header value, the patch slot count, or something else?** Not settled.
  No separate "how many free slots remain from here to slot 5" arithmetic was found feeding
  into a List candidate filter; the one numeric cap found (c0129904's >4 test) is a flat
  per-header ceiling, independent of where in the patch the slot sits.
- **Can it be raised (to 5, or beyond)?** Unknown/not confirmed. *If* Finding 5's check is
  really the gate, raising the `CMPLTU 0x4` immediate at c0129908 to `CMPLTU 0x5` (one
  halfword) is a one-instruction patch candidate -- but given the confidence level, this
  should be tried on a throwaway updater and observed, not trusted from static analysis
  alone. Risk: if B15[128] is actually a different field (not slot-count), this patch could
  silently change unrelated validation (e.g. the BYPASS/BPS dispatch path) instead of what
  is wanted.
- **The actual "pick an effect to add to this slot" browse-list builder was not located.**
  Candidates ruled out: `fx_cat_edit_*` (c0148b80 family) is a generic settings-value-edit
  dispatcher (24-entry category table for numeric/field edits across many unrelated
  screens, e.g. rhythm tempo, patch name), not an effect picker. `patchlist_screen_build`
  (c012a8bc) and its FLST_SEQ.ZT2 readers build the **patch** browser (50 patches), not the
  per-slot **effect** browser. The real effect-picker screen (if distinct from
  `effect_slot_load_unload` reused in a "probe" mode) was not found in the time available.

### Question 3: 12-param maximum and 3-params-per-page layout
- **3-per-page:** `fxparam_page_size` (0x11807eb8, Finding 2) computes
  `page_size = (n > 4*X - r) ? (4*X - r - 1) : (4*X - r)`, X confirmed ==1 (Finding 3). For
  the ordinary case (r==0, n>4) this is **3**, matching the observed layout. The literal
  "4" is a bare `SHL #2` (times-4), not a named constant; there is no single instruction to
  point to as "the 4" beyond that shift. **Confirmed** arithmetic; **likely** that this
  specific function drives the on-screen 3-per-page behavior (the screen-draw call site
  that consumes its return value was not traced).
- **Can the page layout be changed?** If Finding 2 is really the driving function, the
  patch site is the `SHL A0,0x2,A0` at (recorded address) 11807ee6 in L2 code -- changing
  the shift amount changes the multiplier (e.g. `0x2`->`0x3` for 8 slots/page instead of 4).
  Risk: unknown downstream assumptions about page width (fixed-size UI row-draw tables,
  physical widget count) could break; not verified against the actual screen-draw code.
- **12-param maximum: not found as a firmware constant.** (Finding 6). The repo's own
  `docs/CF_MASTER_PROBE_2026-10-19.md` already attributes "12" to the **stomphacks build
  tool**, not to a measured firmware limit ("Stock effects have at most 9 knobs ... 12 is
  the stomphacks maximum"). No loop bound, array size, or MVK/CMP against 12 was found tied
  to per-effect param count in the functions checked (slot_knobcount_ui_update family,
  slot_knob_index_clamp_and_dispatch, the generic table accessors c012afe0/b008/b048). The
  one fixed-4 loop found (c013f6d0, two 4-entry function-pointer tables at 0xc0183a30/a40)
  is a UI-widget-count constant, not a param-count ceiling. Whether the ELF Dll entry
  struct's descriptor-array field has its own fixed capacity (vs. being sized from the
  loaded file) was not checked -- see Not checked below. **Can it be changed?** No firmware
  patch site identified; if 12 truly comes only from the stomphacks build tool, the limit
  (if any) is in that tool's own python/ELF-emission code, not in this firmware image.

## Not checked / open leads
- The real effect-picker ("add effect to slot") browse-list function: not located. This is
  the highest-value remaining lead for Q1 -- whichever screen draws the scrollable list of
  candidate effects for an empty/replaceable slot must call *something* per-candidate; that
  call site was not found in the time budget. Suggested next step: search for the UI screen
  reached from the slot's "edit"/footswitch-hold gesture (distinct from `fx_cat_edit_*`),
  or instrument `effect_slot_load_unload`'s callers to see if any is reached while merely
  scrolling (not confirming) a candidate.
- Byte-exact provenance of `B15[128]` in `effect_slot_load_unload` back to ZD2 file offset
  0x58: not traced. The "INFO" tag-match loop copies into `B15+8` progressively; mapping
  that to local offset 128 (implying ~120 bytes of struct before the checked field, vs. the
  documented file offset 0x58=88) was not reconciled. This is the key gap keeping Finding 5
  at "likely" instead of "confirmed".
- `c012ee80` (called by both c012f628/Finding 4 and the page-start/entry-valid functions in
  chunk_01) was not disassembled; it looks like the actual per-param-descriptor flag test
  underlying several of the param-paging functions and would likely resolve Finding 4's
  "guess" if read.
- Whether the Dll entry struct's 56-byte-descriptor array (c012afe0) has a firmware-declared
  fixed capacity (a real candidate location for a true "12" cap) vs. being sized purely from
  the loaded ELF/ZD2 file content: not checked.
- `effect_slot_list_update`'s caller-side retry loop (c0141b74..c0141bc4, which re-calls the
  Process Overflow check c0141ac8 while clearing bits of a slot-bitmask) was seen but not
  fully traced; it looks like "find which slot to drop to get under 230," tangential to Q1/Q3
  but noted here in case it is useful to S2/S3/S4's slot-loop work.
- Stopped at roughly the 2-hour budget; did not reach a firmware-level re-verification of the
  `docs/CF_MASTER_PROBE_2026-10-19.md` "11 table entries" structural-capacity claim for
  param descriptors, nor cross-checked F2's (parallel job) ZD2-file-side survey, which may
  independently confirm or refute the header-offset mapping question above once it lands.
