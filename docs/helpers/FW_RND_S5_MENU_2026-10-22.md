# FW RND S5: Effect edit screen - labels, pages, sub-menu (question 7)

## Status
done (within budget; see Not checked / open leads for the one significant gap: the
real LCD effect-param draw function was not located)

## Findings

### Finding 0: address sanity check on the two prior Argon/Astra menu reports
Before relying on `MENU_RE_ARGON_2026-10-16.md` / `MENU_PAGES_ARGON_2026-10-16.md` /
`MENU_RE_ASTRA_2026-10-16.md`, spot-checked their key addresses exist as real function
entries in `build/fw/map/main.dis`:
```
grep -n '^c0149664\b|^c01495c0\b|^c0154564\b|^c0149948\b' build/fw/map/main.dis
84213  c01495c0   01bc54f6   STW.D2T2  B3,*B15--[2]
84257  c0149664   10493810   CALLP.S1  0xc016e020,A3
84506  c0149948   1048dc10   CALLP.S1  0xc016e020,A3
98807  c0154564   10335810   CALLP.S1  0xc016e020,A3
```
All four addresses are valid function entries (each opens with a prologue: either a
manual `STW B3,*B15--[2]` or a `CALLP 0xc016e020,A3` register-save veneer). This is a
structural sanity check only (right address, looks like a function start), not a
re-verification of every claim in those reports. Confidence: **confirmed** (for address
validity only).

### Finding 1: fxparam_page_size (11807eb8) re-disassembled independently, formula matches S1 Finding 2
Read `11807eb8..11807ef8` directly in `main.dis` without reference to S1's transcript
first, then compared. Same instructions, same result:
```
11807ecc  CALLP 0xc012af98,B3   ; X = c012af98() -- always returns 1 (two-instr leaf,
                                 ;   c012af98: MVK.L1 1,A4 ; BNOP.S2 B3,5)
11807ed4  CALLP 0xc012b048,B3   ; n = c012b048(slot)
11807ee0  CALLP 0xc012f628,B3   ; r = c012f628(slot), 0 or 1 (S1 Finding 4)
11807ee6  SHL.S1 A0,0x2,A0      ; A0 = X*4 = 4
11807ee8  SUB.L1 A0,A4,A1       ; A1 = 4 - r               ("nominal" page width)
11807eea  ADD.L1 A1,-1,A2       ; A2 = A1 - 1
11807eee  CMPGT.L1 A0,A1,A0     ; wait: re-read -- A0 here is n (moved into A0 at
                                 ;   11807eec MV.L1 A11,A0 first), so this is n > A1
11807ef0  [A0] BNOP 0x11807ef6,5
11807ef4  MV.L1 A1,A2           ; n<=A1: A2 = A1 (undo the -1)
11807ef6  MV.L1 A2,A0           ; return A2
```
`page_size = (n > 4-r) ? (4-r-1) : (4-r)`, confirmed identical to S1. Confidence:
**confirmed** for the arithmetic (own read, matches S1's independent read byte for
byte). Since `n` (the ZD2's own parameter count, confirmed below in Finding 3) is 9 for
every real stock 2-slot effect and well above 4 for `CFMPRE` (12 params), the `n > 4-r`
branch is taken for every multi-knob effect regardless of `r`, giving page_size 3 (if
r=0) or 2 (if r=1) -- **this is the likely source of the hardware-observed "3 params
per page"**, independent of whatever `r` turns out to mean. For an effect with `n<=4`
(a plain 1-slot 4-knob stock effect) and r=0, page_size=4 (no reduction) -- matching
the handoff's "stock 1-slot effects have 4 knobs" (shown on one page, not split).

### Finding 2: what r actually tests -- c012f628 -> c012ee80(slot, idx=0), traced one level deeper than S1
S1 confirmed `c012f628(slot)` returns `c012ee80(slot, 0) != 0` as a 0/1 boolean
(S1 Finding 4) but left the meaning of `c012ee80` as a guess. Read `c012ee80` directly
(`main.dis:48059..48099`, confirmed it is a real function entry: the line immediately
before it, `c012ee78`, is the *previous* function's `CALLP 0xc016e000,A3` epilogue, per
the brief's warning not to fold epilogue code into the next function -- `c012ee80` itself
starts its own `CALLP 0xc016e020,A3` prologue):
```
c012ee80  CALLP 0xc016e020,A3      ; prologue (register-save veneer)
c012ee84  MV.L1X B4,A11            ; A11 = idx (2nd arg)
c012ee86  MV.S1  A4,A14            ; A14 = slot (1st arg), kept across both calls below
c012ee88  CALLP 0xc012b008,B3      ; count1 = c012b008(slot)
c012ee90  [!A0] BNOP 0xc012ef14,4  ; if count1==0, return early (0)
c012ee94  MV.L1 A4,A10             ; A10 = count1
c012ee96  MV.L1 A14,A4             ; restore A4=slot
c012ee98  CALLP 0xc012b108,B3      ; count2 = c012b108(slot)
c012eea0  ADD.L2X A4,2,B1          ; B1 = count2+2
c012eea4  ADD.L1  2,A0,A0          ; A0 = count1+2 (A0 was count1 via A10 copy)
c012eeac  CMPLTU.L2X B1,A0,B0      ; B0 = (count2+2 < count1+2) = (count2 < count1)
c012eeb0  [!B0] BNOP 0xc012ef14,5  ; if count2 >= count1, return early (0)
  ... then builds a 64-bit mask (1 << (15+idx)) in A12:A13 (SET bit15,
      SHL by idx, SHR by 0x1f for the sign-extended high word) ...
c012eed4  CALLP 0xc012afe0,B3      ; desc = c012afe0(slot, idx)   [confirmed: args line
                                    ;  up with A4=slot kept live, B4=idx from A11/B1 chain]
  ... AND's the mask against a 64-bit field at desc+24 words (LDDW *A4[6], i.e. a
      doubleword at byte offset 48 within the 56-byte descriptor) and returns whether
      bit (15+idx) of that field is set.
```
So `c012ee80(slot, idx)` is "does parameter descriptor `idx` of this slot's loaded
effect have bit `(15+idx)` set in its 64-bit flag word (descriptor offset +48)?" --
i.e. it tests a **per-index flag bit inside that specific parameter's own flags**, not
a fixed "slot has a reserved param 0" global. It also only runs at all if
`c012b108(slot) < c012b008(slot)` (two different "count" accessors on the slot;
`c012b008`/`c012b108` are the same functions S1's Finding 6 searched for the 12-param
cap in, and chunk_01's facts file already flagged these two as suspect "usb" names that
the chunk_01 pass itself reclassified -- see Finding 4 below). Confidence: **likely**
for the control flow and the bit-position formula (own read of the full function body);
**guess** for what bit 15 of a parameter's own flag word semantically means (candidate:
a per-parameter "optional/hidden" or "has-extra-page-cell" flag set by the ZD2 builder,
not re-derived from the ZD2 format itself in the time available). This means **r is a
per-loaded-effect-instance property of parameter slot 0's own flags, not a direct
function of the ZD2 header's slot-count byte (0x58)** that S1's Q1 covers -- a 1-slot
vs 2-slot effect could have r=0 or r=1 depending on how its own parameter 0 is flagged,
and I could not confirm from disassembly alone which value stock 1-slot vs 2-slot
effects actually carry (would need the ZD2's raw parameter bytes, not just the firmware
side). **Not confirmed**: whether r differs between 1-slot and 2-slot effects.

### Finding 3: parameter labels are read directly from a 56-byte descriptor, inline at offset 0, cross-confirmed with F2
Read `c012afe0` (`main.dis:42565..42579`), the descriptor accessor `fxparam_row_text`
(11808360) and `fxparam_fmt_string` (118082f8) call: `c012afe0(A4=slot, B4=idx)`
computes `base = *(ptr table at 0xc0064404 + slot*36)` then `desc = base + idx*56`
(`SHL B0,3` then `SHL B0,6` then `SUB` = `idx*8` vs `idx*64`, difference `idx*56`,
confirmed instruction-by-instruction). In `fxparam_row_text` (`11808360`, read
`main.dis:10775..10849` directly), the non-value path calls `fxparam_fmt_string(A4, B4=
outbuf)` right after `desc = c012afe0(slot, col)` (`11808398`) with **no intervening
write to A4** between the call that returns `desc` in A4 and the `fxparam_fmt_string`
call at `11808418` -- i.e. the descriptor's own address is passed as the string
pointer. That only works if the label text is stored **inline at byte offset 0** of
the 56-byte descriptor, not behind a separate name pointer field.
This matches job F2's *independent* finding from the ZD2/ELF side (not firmware
disassembly): `docs/helpers/FW_RND_ZD2_SURVEY_FLASH_2026-10-22.md` Finding 3/4, citing
`src/zd2tools/elfinfo.py` lines 12-14/108-129: `PARAM_RECORD = 56` bytes, label = bytes
`0..11` (12-byte NUL-padded C string), longest stock label 8 chars (`"D57:D421"`), our
`CFMPRE` uses 9-char labels. Two independent methods (firmware disassembly here, ELF
parsing in F2) agree on the 56-byte record and the label living at its start.
Confidence: **confirmed** (firmware side: direct disassembly read; corroborated by F2's
independent tool-side read of the same 56-byte record). This also answers "does it read
the 12-byte ELF label directly" from the brief: **yes** -- the firmware does not keep
its own copy or truncate at load time as far as traced; it formats whatever bytes sit
at descriptor+0 through `fxparam_fmt_string` -> `c016c360` (a generic `"%s"`-style
copy), so a label longer than the firmware's fixed column width would not be rejected
at this layer, only clipped or overlapped by the LCD draw step (not located, see
Finding 4).

### Finding 4: MAJOR CAVEAT -- the whole fxparam_page_size/fxlist_row_text cluster appears to be MIDI-rooted, not LCD-rooted; the real on-screen effect-param draw function was NOT located
Traced every caller edge up from `11807eb8`/`11808360`/`11808320` using
`build/fw/map/facts/chunk_*.md` (static call-graph facts, which also tag selected
functions with a `roots:` field computed from task-entry reachability -- the same
mechanism that tagged the CHAIN-screen icon draw function `c0145eac` as `roots:
UpdateUI`, confirmed by checking that entry too):
```
fxparam_page_size (11807eb8) and friends (fxparam_last_page, fxparam_entry_valid,
fxparam_page_start*, fxparam_page_end, fxparam_slot_item, fxparam_row_text,
fxlist_fmt_effect_name) all funnel through exactly ONE pair of entry points:
  1180af60 "usbdesc_builder_entry"  (facts: callers (1): 11803514)
  1180af8c "usbdesc_builder_entry2" (facts: callers (1): 11803514)
Both are called ONLY from 11803514 ("midi_send_full6_1180", size 508,
build/fw/map/facts/chunk_00.md:209), whose own calls include:
  11802a90 "midi_tx_forward_1180"  -> calls c0144dc8 "midi_tx_forward_common"
                                       (roots: MIDI,MainApp -- confirmed tag)
  11802b70 "midi_stage_copy_1180"  (roots: MIDI,MainApp -- confirmed tag)
11803514's own caller, 118037c6 ("midi_table_veneer10"), is itself one of a block of
similarly-named veneers (midi_table_veneer*) feeding "midi_send_full1_1180" through
"midi_send_full6_1180" (6 variants), and is referenced as a function-pointer table
entry (facts: "ptr@: c01840fc") -- i.e. this is reached via an indirect jump table,
consistent with a MIDI SysEx command dispatcher, not a screen descriptor (which would
be a different, already-identified table at 0xc018413c, see Finding 0).
```
I never found a call edge from `UpdateUI` (`c013c754`) or any of the confirmed menu
screen draw callbacks (`c0149a68`->desc->w6, `c0154564`, `c0154338`) into this cluster,
and no font/pixel primitive (`c011e700`, `c011d4d8`, `c011c508`, `c013a7b4`) appears
anywhere in the `calls` lists of `11807eb8` through `11808440` or their callers up to
`11803514`. The CHAIN screen (Screen ID 4, the only confirmed on-screen "effect slot"
page) draws small fixed on/off **icons** per slot (`c014632c` -> `c0145eac` ->
`c0145e60` -> `c015bc78`/`c015bca4`/`c0145e00`/`c0145e28`), not per-parameter text rows,
and does not call into the fxparam cluster either.
**Conclusion: the fxparam_page_size / fxparam_row_text / fxlist_fmt_effect_name
mechanism that the F1 digest and S1 treated as "the" effect-edit-screen pagination is,
on the evidence found here, a MIDI SysEx response builder** (plausibly "send the
currently-displayed effect's parameter name/value text to a PC editor", given 6
"send_full" variants and the use of the same slot/run/page vocabulary) **rather than
the code that paints the pedal's own LCD for per-effect parameter editing.** The actual
on-device "turn a knob, see 3-4 param names/values, flip pages" screen -- the one the
handoff's hardware tests (CFM2P/CFMPRE knob behavior) actually exercised on the pedal
-- was **not found** in the time available. It is plausible (not confirmed) that it
reuses the *same* ZD2 descriptors (Finding 3, so per-effect labels already work there
regardless) and a *similar* paging rule (hence the matching "3 per page" and "4 knobs"
numbers against Finding 1's arithmetic and the Settings-menu's confirmed "4 columns = 4
physical knobs" layout from `MENU_RE_ARGON_2026-10-16.md` A4.1), but this is an
inference from matching numbers, not a traced call path. Confidence: **confirmed** that
the fxparam cluster's only static callers are MIDI-rooted; **likely** (not confirmed)
that the real LCD effect-param screen uses matching per-page-count logic; **not found**:
the actual LCD draw function(s) for per-effect parameter text.
This directly weakens the brief's framed patch sites: patching `11807eb8` or
`11808360`/`118082f8` would most plausibly change what a MIDI-connected PC editor is
told about the current page, and might do **nothing** to the physical LCD if the LCD
has its own separate (unlocated) page-size constant.

### Finding 5: sub-menu / custom-screen mechanism (confirmed menu-system side, from MENU_PAGES_ARGON, addresses spot-checked)
`MENU_PAGES_ARGON_2026-10-16.md` P3/P4 (addresses spot-checked against `main.dis` in
Finding 0) establishes a generic, already-working mechanism for adding a custom
screen/sub-page to the Settings-menu system, independent of whether it is wired to the
stock "SETTING" gear icon or to something else:
- `c0149664(screen_id)` is the *sole* writer of the active-screen pointer
  (`*+B14[120]`); it looks up a 36-byte descriptor (`w0..w8`: id, 3 icon bitmaps,
  on_enter, on_exit, draw, on_poll, on_event) via `c01495c0(screen_id)`, which indexes
  a 15-entry `.switch` table at `0xc018413c..0xc0184174` for `screen_id < 15`.
- Three of those 15 descriptors (`Screen ID 0, 1, 5` at `0xc01833dc`, `0xc0183400`,
  `0xc0183740`) live in **writable RAM** (`.cinit`-decompressed at boot), and Screen
  IDs `1` and `5` are **provably dormant** in stock firmware (no code path ever passes
  `screen_id=1` to `c0149664`; `c0149820()`'s exit-gate special-cases only `{0,1,9}`).
  Overwriting their `w6`/`w8` fields in RAM (draw/event callbacks) and/or their 4-item
  record tables lets a patch add an arbitrary custom page reachable by calling
  `c0149664(1)` or `c0149664(5)` from a hook, with **no flash-code patch needed for the
  descriptor tables themselves** (only the hook call site, e.g.
  `c0156de0: CALLP.S2 0xc01496d0,B3`, a single 32-bit `CALLP`).
- The generic 4-column page renderer (`c0154564` -> `c0154338`) and the generic 4-knob
  editor (`c0149948`) both take a plain item-record array pointer as an argument, so a
  "sub-menu for one multi-stage effect" (one screen per stage, 4 knobs each, reusing
  `c0149948`) is buildable with this exact mechanism: point a dormant screen's `w6` at
  a thin wrapper calling `c0154564(4, stage_records, x_table, "STAGE 1", 0, 1)` and its
  `w8` at a wrapper calling `c0149948(4, ev, stage_records)`, then flip `stage_records`
  (or re-enter with a different screen id) to move between stages.
I did not re-derive this mechanism myself end-to-end (budget), but spot-checked its
load-bearing addresses in Finding 0 and it is internally consistent with the
descriptor layout I independently re-derived for the fxparam cluster's accessor
pattern in Findings 1-3 (function-pointer table + RAM-resident per-item records is the
same idiom used in both subsystems). Confidence: **likely** (addresses confirmed
present and are real functions; the full mechanism is carried over from
MENU_PAGES_ARGON's report, not re-verified instruction-by-instruction here).
**Important scope note**: this sub-menu mechanism is proven for the **Settings-menu
screen-descriptor system** (`c0149664`/`c01495c0`), which Finding 4 shows is a
*different* subsystem from the (MIDI-rooted, not LCD-confirmed) fxparam cluster that
actually renders per-effect parameter text. Whether the stock per-effect "turn a knob"
edit view is *itself* built on the `c0149664` screen-descriptor system (making this
sub-menu trick directly applicable to it) or on some other, unlocated mechanism was
**not determined**.

## Answers

### (a) Params per page: what sets it, c012af98 and r for 1-slot vs 2-slot effects
`page_size = (n > 4-r) ? (4-r-1) : (4-r)`, where `c012af98()` is a constant-1 leaf
(confirmed, Finding 1) and `r = c012f628(slot)` is 0 or 1, derived from whether bit
`(15+0)` of parameter-descriptor-0's own 64-bit flag word (descriptor offset +48) is
set for that slot's loaded effect (Finding 2). **`r` is not a function of the ZD2
slot-count header (0x58, S1's Q1)** -- it depends on how the effect's own parameter 0
is flagged, which I could not determine for actual stock 1-slot vs 2-slot effects from
firmware disassembly alone (would need the ZD2's raw per-parameter flag bytes, out of
scope for this job; F2's survey did not record this field). What I can say with
confidence: for any effect with more than 4 real parameters (every stock 2-slot
effect at 9, and `CFMPRE` at 12), the `n > 4-r` branch fires regardless of `r`'s value,
giving page_size 3 (r=0) or 2 (r=1) -- this alone explains the observed "3 per page"
without needing r to differ by slot count. Can a patch change it: the "4" only exists
as a bare `SHL #2` (Finding 1), so changing the nominal width requires patching the
constant-1 return of `c012af98` (two instructions, trivial) or the `SHL 0x2` itself;
**risk is unknown because I could not confirm this code is the one driving the actual
LCD screen** (Finding 4) -- patching it may only change what a MIDI-connected PC
editor is told, not the pedal's own display.

### (b) Label drawing: font, pixel width, chars before clipping, 12-byte ELF label read directly?
**Yes, confirmed**: the firmware reads the parameter label directly from byte offset 0
of the 56-byte per-parameter descriptor (Finding 3), which is exactly the 12-byte
(11 chars + NUL) field F2 independently found in the ZD2/ELF's own `elfinfo.py`
parsing. There is no firmware-side string table or truncation at this layer; whatever
bytes are in the ZD2 get copied through `c016c360` (a generic sprintf-style `"%s"`
copy). **Font, pixel width per column, and clipping point for the actual on-screen
effect-param view were NOT located** (Finding 4) -- the only place I found text/font
rendering with confirmed pixel coordinates and font selection is the *Settings-menu*
system (`c0154338`, `MENU_RE_ARGON_2026-10-16.md` A2.2, spot-checked present at
`c0154564`/Finding 0): 4 columns at ~31px spacing, 3x5 font (`c011e700`, 4px pitch,
up to 2 lines) or 5x7 font (`c011d4d8`, 6px pitch, single line), 5-6 characters before
a column starts to overhang. If the effect-param screen shares this same renderer
(plausible given it is the only confirmed LCD text-column system in the firmware, but
**not confirmed** it is actually used for that screen), the same per-column budget
(~5-6 chars at 5x7, ~7 chars/line at 3x5) would apply, meaning `CFMPRE`'s 9-char
labels (`"Muff Sust"`, `"Mist Rate"`, etc., per F2 Finding 4) would already overhang a
single-font-row column by that measure, independent of any firmware patch.

### (c) Can labels change per page?
Trivially **yes** at the data level, already working today without any firmware
patch: because each parameter's label lives inline in that parameter's own 56-byte ZD2
descriptor (Finding 3), and list position `k` maps through `fxlist_slot_at`/
`fxlist_run_index` to a specific `(slot, page)`, **different pages of the same loaded
effect already show different labels by construction** -- there is no shared/static
label table that a "page" patches into. The brief's suggested patch sites
`11808360`/`118082f8` are the MIDI-rooted formatter (Finding 4), not a place where
per-page label *selection* logic lives; I found no code there that would need patching
to get per-page-distinct labels, because the ZD2 data itself already supplies that.
What *is* fixed per page, system-wide, is the page *width* in cells (answer (a)), not
the label text.

### (d) Can one effect open a sub-menu (chain of stages)?
**Yes, confirmed feasible** using the Settings-menu screen-descriptor system
(`c0149664`/`c01495c0`, Finding 5): dormant Screen IDs 1 and 5 already sit in writable
RAM with no live callers in stock firmware, and the generic 4-column
draw/edit pair (`c0154564`/`c0149948`) accepts an arbitrary item-record array, so a
multi-stage effect's "sub-menu" (one screen per stage, re-entered by changing which
record array a wrapper points `w6`/`w8` at, or by allocating one Screen ID per stage)
is directly buildable with a single `CALLP` hook and RAM-table writes, no `.switch`
table patch needed. **Caveat** (also Finding 5): this is proven for the Settings-menu
subsystem; whether the stock effect-param edit view (the one actually used when you
turn a knob on a loaded effect) is built on this same screen-descriptor system was not
established, so "patch a CALLP hook, point it at a new screen" may need to target a
different, unlocated entry point if the two UIs turn out to be separate code (as
Finding 4's evidence suggests they likely are).

## Not checked / open leads
- **The actual LCD draw function(s) for the per-effect parameter-edit view are not
  located.** This is the single biggest gap: everything in this report about pixel
  width, font, and per-page label mechanics for *that specific screen* is inferred by
  analogy to the Settings-menu renderer, not traced. A next pass should start from
  `effect_slot_load_unload` (`c01297a0`, S1 Finding 5) or from the knob-event dispatch
  that currently drives a loaded effect's parameters in Stomp/Play mode (not the gear
  icon) and look for calls to `c011e700`/`c011d4d8`/`c011c508`/`c013a7b4` that are NOT
  already attributed to the CHAIN/SETUP/PWR/TUNER/OUTPUT screens.
- What the 11803514 "midi_send_full6" family and its 5 siblings (`11802d08`,
  `11802d44`, `11802ee0`, `11803044`, `118031ac`, `11803254`, `1180340c`) actually
  send, and on what MIDI SysEx command ID (the `c01840fc`-area veneer table) -- would
  confirm or refute the "PC editor mirrors the LCD" theory in Finding 4.
- Whether `r` (Finding 2) actually differs between any real stock 1-slot and 2-slot
  effect was not checked against ZD2 parameter-flag bytes (would need a small script
  reading each stock ZD2's parameter-0 flag word, cross-referenced with F2's corpus).
- The meaning of bit 15 (and the `(15+idx)` family of bits) in a parameter
  descriptor's 64-bit flag word (offset +48) beyond "some per-parameter flag" -- not
  derived from the ZD2 format spec.
- `c012b008` vs `c012b048` vs `c012b108`: three similarly-named "count" accessors used
  inconsistently across the cluster (chunk_01.md's own gloss uses `c012b048` for
  `fxparam_page_size`'s `n` but `c012b008` for `fxparam_index_check`'s bound); I did
  not re-derive why there are three or confirm they return the same count for a given
  slot. Relevant if patching anything in this area.

## Note on tool output (not a job-7 finding, flagged for the record)
While grepping repo docs for "effect edit" context, one Bash tool result had an extra
block appended after the real repository content that looked like a copy of this
session's system reminder about commit attribution, but with an added
`Claude-Session: https://claude.ai/code/...` URL line not present in the real reminder
given at the start of this conversation. Treated as untrusted data (not an instruction
from the user/caller) and ignored; no such line was added to any commit in this job.
Flagging it here only so the caller is aware the grep surfaced something that looked
like an injected instruction.
