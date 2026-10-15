# Review 2: second independent review of the USB audio candidate (2026-10-15)

> Headline: TBD

Scope per `docs/helpers/BRIEF_REVIEW2_USB_AUDIO.md`. Reviewed against
`build/fw/map/main.dis` (stock) and a fresh rebuild of
`build/usb_audio/usb_audio.dis` (candidate). Correctness only; no file under
review edited; no hardware/pedal/.exe touched.

## 1. Descriptor veneer delegation (`firmware/usb_audio_proto/usb_audio_hooks.asm`)

**OK, confirmed.** Predicate test, delay slots, and the "don't-care" return
value all check out.

Predicate (`c0135014`-style retarget, now pointing at the veneer):
```
SUB   .L1   A4,1,A0        ; A0 = A4-1 (unsigned)
CMPLTU .L1  1,A0,A0        ; A0 = (A0 >u 1) ? 1 : 0   i.e. A0=1 iff A4 !in {1,2}
[A0] B .S1  stock_descriptor_builder
NOP 5
```
Truth table: `A0=1` (A4 ∉ {1,2}) → branch taken, tail-branches to stock.
`A0=0` (A4 ∈ {1,2}) → not taken, falls into the veneer's own build path.
This is byte-for-byte the same test stock itself runs at `c0160ee2/ee4`
(`ADD A7,-1,A0` / `CMPLTU 1,A0,A0`) — confirmed by direct comparison of both
sequences; same threshold, same unsigned compare, same `A4-1` base.

Delay slots / nothing written before the branch: only `A0` (scratch) is
written by SUB/CMPLTU before the predicated branch; A4,B4,A6,B3,SP are all
untouched on the taken path. The `NOP 5` fills the branch's delay slots
regardless of whether it is taken (correct either way: if taken, the 5 NOPs
occupy the slots before redirecting to stock; if not taken, they're just 5
dead cycles before falling into the save/call sequence). Confirmed OK.

Return value for A4 ∈ {1,2}: the veneer unconditionally sets `A4=0` after
writing `&desc_ptrs` through `*A6[0]`. Traced stock's own return convention
at the shared finisher `c0161040..1058`: `STW A0,*+A5[0]` (array base out),
then `CMPLT 14,B0,B0` where B0 is the just-built fragment count; count<=14
(the DEVICE path, count=14 per `c0160ffa`) yields `A4=0`, count=15 (the
device-qualifier/other-speed path, irrelevant here since those types never
reach the veneer) yields a nonzero pointer value. **But it does not matter**:
checked all 7 real call sites in `main.dis` (`c0135014/5168/5258/5568/
5694/57e4`, `c0152514`) and in every one, the instruction(s) immediately
after the `CALLP` either reload A4 from the stack or overwrite it with the
saved original request type (`MV A10,A4`) before the next decision point —
none of them ever branch on the callee's returned A4. The channel that
actually matters is the out-pointer write through `*A6[0]`
(`desc_ptrs`/stock array base, read back by the caller via
`LDW *B15[1],A4` → `LDW *A4[0],A0`), and that is correctly replicated.
Confidence: confirmed (direct trace of all 7 sites).

Also independently re-confirmed (per brief's "compare against the stock test
at c0160ee2..ee6"): yes, matches.

## 2. `ua_map_thunk` (`firmware/usb_audio/ua_thunks.asm`)

**OK, confirmed** on all four sub-questions (entry state, return target,
clobber set, single-caller claim). Independently re-derived from
`main.dis`, not taken on faith from review 1 or the source comments.

Stock `c015c66c` body (full function, `c015c66c`..`c015c6b2`):
```
c015c66c  MV.L1 A4,A0 || MV.S1 A6,A4 || MV.L2 B4,B0
c015c672  CMPEQ.L1 6,A0,A0
c015c674 [!A0] BNOP .. c015c6ac,5      <- gate; overwritten by the patch
c015c678.. (writes IF0/IF1/EP3/EP0x84/record_vector, A0<-0)
c015c6a8  BNOP .. c015c6b0,5
c015c6ac  MVK 0xffff8a5c,A0            (reject value)
c015c6b0  MV A0,A4
c015c6b2  BNOP B3,5                     <- function's real return
```
Entry state at the gate: A0 = (pre-swap A4 == 6), A4 = slot (from caller's
A6), B0 = record (from caller's B4) — matches the asm file's comment and
the thunk's own `[!A0] B ua_map_reject` / fall-through structure exactly.
Truth table: `[!A0]` (A0==0, i.e. original selector != 6) → reject;
`A0!=0` (selector==6) → proceed to the map writes. Same predicate sense
candidate and stock.

Single caller — re-verified independently (brief specifically asked to
re-check this, not just trust review 1):
```
$ grep -n "c015c66c" main.dis | grep -v '^c015c66c'
c015c760  CALLP.S2 0xc015c66c,B3     <- only textual reference
$ grep -c "ffffc66c" main.dis   -> 0   (no MVKL/MVKH-built function-pointer constant)
$ grep -n "c015c768" main.dis | grep -v '^c015c768'   -> (no hits: nothing else branches to the
                                                           continuation either)
```
Confirmed: exactly one caller, no jump-table/constant alias, and no other
branch target lands on the claimed continuation `c015c768`. Confidence:
confirmed.

Return-to-`c015c768` rationale: the patch's own `CALLP.S2 ua_map_thunk`
(written over the gate, mid-function) necessarily clobbers B3 with a
return address *inside* `c015c66c`, not the outer caller's real
continuation — hence the thunk must hardcode `B3 = 0xc015c768` itself
(`MVKL`/`MVKH`) rather than inherit B3. Verified this is the only
correct target: `c015c760`'s own CALLP delay-slot bundle sets up A4/A6/B4
as the callee's inputs, and `c015c768` (`ADD.L2 B1,1,B1`) is the real
post-return loop-continuation code (reads the call's A4 result via
`CMPEQ.L1 0,A4,A0` right after).

Clobber set — the thunk touches only A0/A4/A5 (+B3 for its own
reconstructed return address), a strict *subset* of stock's own
{A0,A4,A5,B0,B4}: stock additionally burns B4 as a scratch temp
(`MVK 68,B4; ADD B4,A5,B4`) to reach the EP 0x84 address, which the thunk
instead reaches via a plain immediate offset, needing no B4 scratch. Traced
the caller's loop (`c015c750`..`c015c798`) to confirm B4 is never read
between one call's return (`c015c768`) and the next iteration's own fresh
`MV.L2X A0,B4` (c015c766) — so stock's B4 clobber was never observable
anyway; the thunk being stricter is strictly safe, not just coincidentally
OK.

Slot-0 / slot-1/2 map writes — **strides computed, not eyeballed**:
- `record_vector` write: `STW B0,*A5[A4]` at base `0xc011aa18`, same in
  both stock and thunk (A4=slot is the index; word-scaled, slot·4).
- IF0/IF1: thunk's `*A5[0]`/`*A5[1]` off base `0xc011aac0` = `0xc011aac0`,
  `0xc011aac4`. Stock's `STDW A5:A4,*0xc011aac0[0]` (double-word store at
  index 0) writes the same two addresses (base+0, base+4) in one
  instruction — same two target words, confirmed equal.
- EP3/EP 0x84: thunk's base `0xc011aa4c`; `*A5[0]` = `0xc011aa4c` (EP3
  OUT); `*A5[17]` = `0xc011aa4c + 17*4` = `0xc011aa4c + 68` =
  **`0xc011aa90`**. Stock computes the same second address explicitly via
  `MVK.S2 68,B4; ADD.L2X B4,A5,B4` → `0xc011aa4c+68=0xc011aa90`. Computed
  both ways, same result: confirmed, not eyeballed.
- Slot 1/2 (new, stock never exercises these): base `0xc011aac0`
  (`interface_map`), `*A5[2]` = `0xc011aac0+2*4` = `0xc011aac8` (IF2),
  `*A5[3]` = `0xc011aac0+3*4` = `0xc011aacc` (IF3). Matches design doc's
  table.

Success/reject return value: thunk's `MVK 0,A4` (success) and
`MVKL/MVKH 0xffff8a5c,A4` (reject) reproduce stock's `A0=0`→`A4=0` and
`MVK 0xffff8a5c,A0`→`A4` exactly (stock's single-instruction MVK sign-
extends `0x8a5c` to `0xffff8a5c` directly; the thunk's two-instruction
MVKL/MVKH form is less efficient but numerically identical). Confirmed OK.

One structural point (carried over from review 1, independently re-derived
here, still **RISK not BUG**): the patch replaces a conditional `[!A0]
BNOP` with an unconditional `CALLP`, relying on CALLP's own bundled delay
slot not disturbing A0/A4/B0 (confirmed true at `c015c760`'s bundle) and on
the thunk re-doing the `[!A0]` test itself. Sound as implemented.

## 3. IF3 SETUP callback (`usb_audio.c` / `ua_glue.c`)

(pending)

## 4. Anything else found

(pending)

## Summary of verdicts

| # | item | verdict |
|---|---|---|
| 1 | descriptor veneer delegation | TBD |
| 2 | `ua_map_thunk` | TBD |
| 3 | IF3 SETUP callback | TBD |
| 4 | other | TBD |
