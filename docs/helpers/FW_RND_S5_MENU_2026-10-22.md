# FW RND S5: Effect edit screen - labels, pages, sub-menu (question 7)

## Status
running

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

## Answers

## Not checked / open leads
