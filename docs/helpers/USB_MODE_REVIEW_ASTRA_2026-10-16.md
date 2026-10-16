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

**Verdict: bug (confirmed call-graph fact; likely in practice — priority
direction and reachability reasoned, not hardware-tested).**

`usb_set` (firmware/controller/controller_menu.c:112-120) reads
`USB_READY`/`USB_STATE` once, then — still inside the same MainApp
event-dispatch call, holding no lock — runs `USB_CLOSE()` (c016ab58),
`SLEEP_MS(500)`, `USB_OPEN()` (c016ab8c): the exact same two global,
non-reentrant stock entry points the cable handler calls on a physical
detach/attach (confirmed: `1180a824 CALLP 0x1180b180`→c016ab58 and
`1180a874 CALLP 0x1180b150`→c016ab8c, traced directly in main.dis). Neither
c016ab58 nor c016ab8c take or check any mutex: the background report already
established "No locking is present in these small wrappers" for the registry
mutator, and that the one thing that looks like a lock (B14[96]) is a stub
(`c014a4d0 MVK 1,A4; c014a4d2 BNOP B3,5`). I re-read c0122260 (Hwi create,
inside the open chain) directly and confirmed it is explicitly **not**
idempotent/reentrant: it tests a single shared handle at B14[131] with a
plain load-test-store, no interrupt disable or semaphore around the
check-then-act.

The cable handler that can call these same two entry points lives in
`SwitchNrmlSpdRead`, a separate task the background report places at
priority 9, versus MainApp (which runs `usb_set`) at priority 3. TI
SYS/BIOS-family schedulers use higher-number-equals-higher-priority with
preemption, so (likely, not textually confirmed in this codebase) the switch
task can preempt MainApp at any instruction boundary, including mid-way
through `usb_set`'s close/sleep/open sequence or during the 500 ms
`Task_sleep` itself (which exists precisely to let other tasks run).

Concrete failure scenario: a user opens the COMET FLOWER page and turns the
USB knob while the cable is unplugged or replugged at nearly the same
moment (or the cable glitches during the 500 ms detached window `usb_set`
itself creates). MainApp is inside `usb_set`'s close/sleep/open when the
switch task's cable handler independently calls c016ab58 or c016ab8c for the
same physical event. Two tasks then race on the same unlocked shared state —
the worker/MIDI/controller handles at B14[94..96], the Hwi handle at
B14[131], the registry at c011aa28, the MIDI ring c0117b28 — with no mutual
exclusion. c0122260's own refusal path (confirmed above, R2) shows the stock
code is written assuming single-threaded, serialized calls: a second
concurrent open/close is not rejected safely, it silently takes a different,
partially-skipped path (same mechanism as the R2 skip branch). Worst case is
a corrupted worker/Hwi/registry state requiring a power cycle — a materially
worse outcome than the existing stock cable-detach race, since this is a new,
self-inflicted 500+ ms window of exposure that stock code never created.

This matches a risk the background report already flagged in general terms
("new lifecycle serialization against switch-task cable changes ... the
stock lock stub is insufficient") but `usb_set` as shipped does not implement
any such serialization — it only checks `USB_READY`/`USB_STATE` once,
unguarded, before starting the sequence. No offline test can catch this: it
depends on real cable-event timing.

Suggested fix: do not call c016ab58/c016ab8c from `usb_set` without first
taking a lock the cable handler also respects (e.g. a flag the switch task's
dispatch checks before acting, or disabling/deferring that task's cable
notifications for the duration), not just the stub B14[96]; at minimum,
re-check `USB_STATE` immediately before `USB_OPEN()` too, and abort the
software-replug sequence (leaving the device however the cable handler left
it) if state changed underneath it.

Secondary, unresolved sub-point (explicitly unproved): the cable handler also
calls `1180b160`→c0155290 and `1180b170`→c01295ec and reads `11805eb4` on a
physical transition; `usb_set`'s software replug calls neither. c0155290 is
also called from the boot path (`c016c148 CALLP 0xc0155290`), so it is not
obviously MIDI/audio-critical, but I did not trace its body or c01295ec's
within this review's budget, so whether skipping them matters is left
unproved rather than asserted either way.

## R4. Malformed-image rejection

**Verdict: bug. Confidence: confirmed** (read directly, tools/make_fs_restore_updater.py
and tools/make_usb_audio_fw.py).

`strip_usb_audio(old_fw, new_fw)` (make_fs_restore_updater.py:140-186) is
only used to build `checked`, which is passed to `validate_controller_fw`
for validation. It is **not** what gets written to the updater: at
line 363, `grown = new_fw` — the original, un-stripped bytes, including
whatever is in the USB-audio AIS section — and `grown` is what
`grow_resource(data, FW_RES, grown)` (line 397, using `grow_resource` at
line 245-273, which writes `payload` i.e. `grown` verbatim into the PE
resource) actually embeds in the output updater. So for a `--test-controller-fw`
build with a USB-audio layer, the bytes that get shipped are never the bytes
`validate_controller_fw` examined.

`strip_usb_audio` itself only checks, for each of the small, fixed list of
patch words in `ua.PATCHES` (the 7 descriptor-builder call sites, the
usbmidi_open call, the map-thunk overwrite, the two SOF-hook MVK/MVKH
halves): that the word's *encoding* is a well-formed, in-place-only change
(same opcode/unit/parallel bits, only the displacement or 16-bit immediate
field differs) and that the *target address* it decodes to lands inside the
just-identified trailing AIS section (`base <= target < base+size`). It then
unconditionally overwrites those words back to their pristine stock values
(`struct.pack_into("<I", view, o, old)`) and discards the whole trailing
section before handing `checked` to `validate_controller_fw`. At no point
does either function hash, diff, or otherwise inspect the *contents* of the
USB-audio section itself against any known-good build (e.g. the output of
`make_usb_audio_fw.py`'s own `build()`, which does rebuild from source via
the TI toolchain and does check its own output byte-for-byte). `--controller-fw`
takes an arbitrary file path from the command line; nothing requires it to
have actually been produced by `make_usb_audio_fw.py`.

Concrete failure scenario: hand-craft (or take a buggy build of) a
`controller_fw` image that is byte-identical to a legitimate controller +
USB-audio build except that the bytes at the symbol targets `ua_usbmidi_open`,
`usb_audio_descriptor_veneer`, `ua_map_thunk`, or `usb_audio_sof_tick` inside
the trailing section hold different code — e.g. code that omits the
`ua_mode.active` gate entirely, or anything else, as long as the seven
BUILDER_CALLS/usbmidi_open/map-thunk/SOF-hook words are still well-formed
retargets landing inside that section's address range (which is easy:
copy them unchanged from a real build). `strip_usb_audio` will restore the
same handful of call-site words to stock, `validate_controller_fw` will pass
the resulting `checked` (its per-byte loop at lines 230-233 only inspects
bytes before `close`, which this attack never touches), and
`make_fs_restore_updater.py` will then embed the **original, unverified**
`new_fw` — section contents and all — into the output updater, printing
"TEST build with diag/UI hooks (owner-run test only)" with no indication
anything is wrong. The packager's validation is a structural/format check
on a reconstructed copy, not a content check on what is actually shipped.

Suggested fix: either (a) have the caller flash/write `checked` plus the
re-attached, hash-pinned section (i.e. validate the exact bytes that will be
shipped, not a derived reconstruction), or (b) have `strip_usb_audio`/
`validate_controller_fw` additionally verify the stripped section's bytes
against a freshly-built reference (e.g. accept a `--expect-usb-audio-sha256`
or rebuild via `make_usb_audio_fw.build()` and compare), so a malformed or
tampered USB-audio payload is rejected rather than silently embedded.

Minor, secondary robustness note (not itself a "passes validation" bug):
`off, op, args = cmds[-2]` (line 152) and the equivalent in
`validate_controller_fw` will raise an unhandled `IndexError` rather than a
`ValueError` if `new_fw`'s AIS command list has fewer than 2 entries; this
is only caught by `except ValueError` in `main()`, so a sufficiently
malformed (not just malicious) `--controller-fw` file crashes the packager
with a raw traceback instead of the usual clean error message. No image
passes in that case either way, so this is a diagnostics gap, not an
acceptance bug.
