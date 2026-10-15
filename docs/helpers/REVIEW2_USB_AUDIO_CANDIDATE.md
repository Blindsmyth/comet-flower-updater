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

(pending)

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
