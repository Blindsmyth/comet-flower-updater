# USB mode review — Claude Sonnet review — 2026-10-16

Offline correctness review. Findings record instruction/source evidence, verdict, and confidence. Unproved claims remain explicitly unproved.

## R1. Inactive-mode stock behavior

**Verdict: ok. Confidence: confirmed** for the four patched sites checked
(descriptor veneer, map thunk, SOF hook, ua_usbmidi_open).

- Descriptor veneer (`build/usb_audio/usb_audio.dis`, `usb_audio_descriptor_veneer`
  at c01a85e0): `c01a85e8 LDW.D1T1 *+A0[0],A0` is immediately followed, with
  **no explicit NOP4**, by `c01a85ec [!A0] B.S1 stock_descriptor_builder`. The
  fetch packet c01a85e0..c01a85fc ends with `.fphead p, l, W, BU, nobr, nosat,
  0010000b` — the `p` flag marks this a protected-load fetch packet, so
  hardware inserts the load-to-use delay itself; the missing NOP4 is correct,
  matching the context note on protected-load packets. When `ua_mode`==0
  (A0==0) this branches straight to the stock builder with A4/B4/A6/caller B3
  untouched, exactly per source. The second gate (`c01a85f4 CMPLTU`) also
  falls to the stock builder for every A4 outside {1,2}, so STRING(3),
  qualifier(6) and other-speed(7) descriptor requests are untouched too.
- Map thunk (`ua_map_thunk` at c01a8860): same pattern —
  `c01a8870 LDW.D1T1 *+A1[0],A1` directly followed by
  `c01a8874 [A1] B.S1 ua_map_on`, fetch packet c01a8860..c01a887c ends with
  `.fphead p, l, W, BU, nobr, nosat, 0000000b` (protected). When `ua_mode`==0
  (A1==0) it falls through to `c01a8880 [!A0] B.S1 stock_map_reject` /
  `c01a8888 B.S1 stock_map_continue` — the exact two-way branch that was at
  the overwritten site c015c674 (`[!A0] BNOP c015c6ac,5` then fall through to
  c015c678), reproduced from the same A0 the stock packet computed, with B3
  restored to c015c768. Byte-for-byte equivalent fallback confirmed.
- SOF hook (`c016f770`/`c016f774`, retargeted from the stock veneer target
  `0x11818e80` to `usb_audio_sof_tick`): checked what the *replaced* stock
  target actually does — `11818e80: BNOP.S2 B3,5`, i.e. the stock SOF-hook
  slot is an empty stub (immediate return, no stock side effect at all).
  Unlike the other two sites this retarget is unconditional (no runtime
  `ua_mode` gate), but since the stock target was already a no-op there is no
  stock behavior to preserve. `usb_audio_sof_tick`'s own inactive path only
  fires when `usb_audio_state.stream_enabled`==0
  (firmware/usb_audio_proto/usb_audio.c:174-177): it increments the private
  `.ua_state` counter `missed_sof` and returns — no stock register or memory
  is touched. `stream_enabled` can only become nonzero via
  `usb_audio_set_alt`, itself only reachable through `ua_if3_request`, itself
  only registered when `ua_mode.active`!=0 at open time — so with the layer
  inactive this path is permanently a no-op. Confirmed no observable
  deviation from stock.
- `ua_usbmidi_open` (c01a8500, `build/usb_audio/usb_audio.dis`): with
  `ua_mode.request`==0, the compiled code computes `active=0` and stores it
  *in the delay slots of the branch to* `STOCK_USBMIDI_OPEN`
  (`c01a852c STW A3,*+A10[0]` is parallel-packed with `c01a8530 ADDKPC
  $C$RL4,B3,0`, both inside the 6-cycle delay window of the `c01a8514 B.S2X
  A6` call to 0xc0152410) — i.e. the active flag is latched strictly before
  the stock open code executes, then the function falls straight to
  `return r;` (registration guarded by `r==0 && ua_mode.active`, both false
  here) with the same return value the stock direct call would have
  produced. Only overhead is a few extra instructions in the caller
  (negligible timing, no behavioral change).

## R2. Connection mode latch

Pending.

## R3. Software replug

Pending.

## R4. Malformed-image rejection

Pending.
