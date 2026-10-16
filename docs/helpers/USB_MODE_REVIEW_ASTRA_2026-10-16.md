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

**Verdict: ok for the latch invariant itself (confirmed); unproved for one
upstream stock conditional that can skip the open chain entirely** (pre-
existing stock control flow, not part of this patch set).

Single-call-site proof (main.dis, `grep -n "0xc0152410"` / `"CALLP.*c0145124"`
etc.): `c0152410` (stock usbmidi_open) has exactly one caller in the whole
firmware, c0145158 — so there is no way to reach the stock open without going
through the patched site. The chain above it is also single-caller end to
end: c0145124 only from c01597b0; c0159758 only from c016ab78; c016ab70 only
from c016ab98; and c016ab8c (the full-open entry) is called from exactly two
places — `c016c150 CALLP 0xc016ab8c` on the boot path, and, on the
cable-attach path, `1180a874 CALLP 0x1180b150` where the veneer at 1180b150
(`MVK 0xab8c,B31; MVKH 0xc0160000,B31; B B31`) resolves to the same
0xc016ab8c. c016ab8c's own body (`c016ab94 CALLP c015b114,B3; c016ab98 CALLP
c016ab70,B3`) calls both unconditionally with no test in between, matching
the background report. So whenever MIDI/audio actually get (re-)opened, it is
always through the one patched call site, and `ua_mode.active` cannot be
latched from a different request value than the one used by that same open's
registrations (it is written nowhere else: grep of ua_glue.c confirms
`ua_mode.active` is assigned only inside `ua_usbmidi_open`).

Residual, unproved point found while tracing this: `c016ab70` itself is not
an unconditional pass-through to c0159758 — `c016ab72 MV.L1 A4,A0; c016ab74
[!A0] BNOP 0xc016ab80,5` skips the call to c0159758 (hence skips c0145158 and
our registration) whenever its A4 argument is 0, and falls through regardless
to `c016ab80 CALLP c015af18,B3` (connect/SOFTCONN) either way. That argument
is c015b114's return value threaded straight through c016ab8c
(`c0138a78`→`c0122260`, "refuses if the Hwi handle B14[131] already exists,
otherwise creates one and returns 0" — confirmed by reading c0122260 directly:
`c0122264 LDW *+B14[131],B0; c0122268 [!B0] BNOP c0122274,5` takes the create
path when no handle exists and returns 0 on success; the existing-handle path
falls through to `c0122270 MVK 0xffff8acd,A4` without branching). B14[131] has
exactly two writers in all of main.dis (c01222b4 inside c0122260, and c01200e0
inside the close path c01200c0), so it is 0 only before the very first
successful open since the last close/boot. I could not fully resolve, within
this review's budget, whether/how the two actual callers of c016ab8c (boot,
cable-attach) interleave relative to this flag in practice — i.e. whether the
very first open after boot ever reaches the "fresh handle, skip MIDI open,
connect anyway" branch while a connection is externally visible. If it does,
that connection's descriptor response (ua_mode.active, still at its prior
value, since ua_usbmidi_open never ran to refresh it) and its registrations
(not rebuilt, left exactly as they were) are in fact **still mutually
consistent** with each other for that connection — just possibly stale
relative to the current `ua_mode.request` — because nothing else writes
`ua_mode.active` or clears the registry in that branch. So this does not
break the specific invariant R2 asks about, but it means "c0145158 runs on
every path that later connects" is not literally true; it is "every path that
(re)builds the registry also re-latches active before connecting," which is
the weaker, still-sufficient property. Marking this unproved rather than ok
because I have not traced far enough to rule out a request/connect ordering
where the host could query descriptors inside that narrow skip-MIDI window.

## R3. Software replug

Pending.

## R4. Malformed-image rejection

Pending.
