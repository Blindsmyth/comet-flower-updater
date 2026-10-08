# Bounded MIDI transmit for controller mode (Helper A, Sonnet, round 4)

Brief: docs/helpers/ROUND4.md Helper A. Report protocol:
docs/helpers/SAVE_PROTOCOL.md. Scratch: build/sonnet4a/.

## 1. Periodic/task hook point for a drain step

### Recommendation: redirect c0134dc4's CALLP target (confirmed site; task-context, runs every MainApp loop pass)

MainApp's loop body is `c0134db8..c0134e0c`, confirmed by direct read of
`build/fw/map/main.dis`. Every path through one iteration converges back to
one call site:
```text
c0134dc0 CALLP.S2 0xc01341e4,B3
c0134dc4 CALLP.S2 0xc01537f4,B3   ; housekeeping, runs every pass
c0134dc8 MVK.L1   0,A0
c0134dcc STW.D1T2 A0,*+B14[124]
c0134dd0 CALLP.S2 0xc015350c,B3   ; blocking queue receive, timeout -1
...
c0134de4 LDW.D2T2 *B15[1],B0      ; event id
c0134de6 MVK.S2   42,B1
c0134dea CMPEQ.L2 B0,B1,B0
c0134dec [ B0] BNOP.S1 0xc0134dc4,5   ; sentinel 42 (idle) -> back to dc4
...
c0134df6 [ A0] BNOP.S1 0xc0134e06,5
c0134e04        BNOP.S1 0xc0134dc4,5   ; dispatcher path A -> back to dc4
c0134e0c        BNOP.S1 0xc0134dc4,5   ; dispatcher path B -> back to dc4
```
All three fall-through/branch paths after an event (sentinel-42 idle,
dispatcher A `c0134acc`, dispatcher B `c0134d04`) land back on `c0134dc4`,
so the call to housekeeping `c01537f4` executes once per loop pass
unconditionally, including idle passes. This matches recon/18 1.6's
"controller-mode resume executes housekeeping c01537f4 before
`c0134dcc STW 0,*B14[124]`" and recon/15's "Preserve queue housekeeping
c01537f4". Confidence: confirmed (direct control-flow read).

`c01537f4` takes no arguments and returns nothing (`c01537f4 STW B3,*B15--[2]`
prologue reads no incoming register before its first call; body only
touches globals). It can be redirected exactly like the existing
`controller_start`/`controller_analog` hooks: a plain C function with the
same `void(void)` signature, calling stock `c01537f4` and then a new
`controller_drain()`, installed by changing the word at `c0134dc4+... ` (the
CALLP operand) the same way the existing controller build redirects
`c0134e14`, `c0134df0`, `c015ffd0` (firmware/controller/controller.c header
comment). No asm trampoline is needed (unlike the dispatch hook, which
needed one only because it must consume the event pointer and jump back
mid-loop; this call site already returns to its caller normally).
Confidence: confirmed call-site ABI (no args/return), likely sufficient as
a plain CALLP redirect (same pattern already proven for 3 other hooks).

This is **MainApp task context** (same task family as `controller_event`,
different from the AD task that runs `controller_analog`), so a drain
function here can safely touch the knob/button state that `controller_event`
also writes (same task, no cross-task race) with no lock.

### Caveat: not a true fixed-period tick (what is missing)

The queue receive at `c0134dd0 CALLP 0xc015350c,B3` (-> `c01534c4`) uses
timeout `B4=-1` (recon/15), i.e. an unbounded wait on mailbox handle
`B14[162]`. MainApp's loop therefore advances only when *something* posts to
that mailbox, not on a guaranteed period. Several independent producers do
post to it (switch-scan task at `11807754`/`11807938`/`11807a84`, a repeat
handler near `1180a844`/`1180b008`, recon/15), so in practice the loop should
run often whenever the pedal is being played, but no fixed worst-case gap
between passes is proven here. Status: a hard real-time bound on drain
latency is **not established**; only "runs on every MainApp event,
including idle/sentinel passes" is confirmed. A SYS/BIOS `Clock`-driven
periodic alternative was considered (true fixed period, Hwi/Swi context) but
rejected for this design: no `Clock_create`/`Task_create` call site or
config-table ABI was found in the traced disassembly to safely construct a
brand-new BIOS object post-link (the one static task-descriptor table found,
`c01800bc`, is link-time BIOS configuration for the existing USB worker
task, not an extensible runtime API), and the ring's single-byte append
itself is reused by a Task-context worker (recon/17 A3) in a way that is not
proven safe to re-enter from Hwi/Swi context. Status: done (recommendation
given; fixed-period alternative explicitly ruled out, not just unexplored).

## 2. Ring free-space test and lock-free peek

### Finding: the free-space test and the single-byte append are pure arithmetic, no CALLP at all (confirmed)

Direct read of `build/fw/map/main.dis` at `c0149d74..c0149dac`:
```text
c0149d74 MV.L2    B4,B2          ; B2 = byte to append (arg)
c0149d76 LDW.D1T2 *A4[0],B0      ; B0 = ring->read_index  (c0117b28+0)
c0149d78 LDW.D1T1 *A4[1],A1      ; A1 = ring->write_index (c0117b28+4)
c0149d80 ADD.L2X  A1,1,B1
c0149d84 SET.S1   A0,10,10,A0    ; A0 = 0x400 (1024): wrap modulus
c0149d86 CMPLT.L1 A1,A0,A0
c0149d8e CMPEQ.L2 B1,B0,B0       ; candidate next-write == read -> full
c0149da4 ADD.L1   A4,A1,A5
c0149da6 STB.D1T2 B2,*A5[8]      ; data byte at ring+8+write_index
c0149da8 STW.D1T2 B1,*A4[1]      ; commit new write_index
c0149dac BNOP.S1  B3,5           ; return
```
No `CALLP` instruction appears anywhere from `c0149d74` to `c0149dac` (I
scanned the full window; the only other `CALLP` nearby, at `c0149dc4`, is
inside a *different*, caller function — the bulk-copy loop at `c0149db0`
that repeatedly invokes this same single-byte routine). So the free-space
test and the actual index/byte update that recon/17 A3 already describes
("full returns ffff63be; bulk append returns its accepted prefix count")
require **no semaphore and no wait** at the ISA level. Confidence:
confirmed (exhaustive read of the instruction range, not just the two
addresses named in the brief).

Entry parameters, read directly from the prologue: `A4` = ring object
pointer (`c0117b28`), `B4` = byte value. This confirms recon/17 A3's field
layout (read index +0, write index +4, data +8) from the producer side as
well as the consumer side already shown there.

### Finding: every externally-reachable entry point wraps this in a blocking wait; no non-blocking variant found (confirmed call sites; absence of a bypass is likely, not exhaustively proven)

The only two ways into the append logic that this audit or recon/17 found
both take an unbounded-timeout lock first:
```text
c01274d4 CALLP.S2 0xc0150b20,B3   ; outer lock, B14[161], timeout -1 (c01274e0)
c0149df0 CALLP.S2 0xc014a094,B3 || LDW *+B14[89],A4   ; inner lock, B14[89]
```
(addresses and roles per recon/17 A3 / recon/18 1.6, both already confirmed
there; re-verified present in `main.dis` at those addresses). No
zero-timeout or "try" variant of either acquire call was found anywhere in
the traced call graph. So: **a caller can check free space without any
lock** (above), but **cannot reach the real stock append without going
through one of these two blocking acquisitions** — there is no proven
non-blocking path through the stock API itself. What is missing: an
exhaustive search of every other `CALLP` target in the firmware for a
hypothetical third, non-blocking entry point was not done (would require
scanning the whole 1.3 MB image for callers of the ring object address,
beyond this budget); absence here is "not found", not "proven absent".

### Design consequence adopted for item 3

Because the pure append (`c0149d74`) takes no lock by itself, the new
drain step calls the ring object's raw indices **read-only** to *decide*
whether to attempt a send (never mutates them directly — mutating them
from a second, unaudited producer would race the stock worker, which also
holds `B14[89]` while draining, recon/17 A3). The actual byte transmission
still goes through the stock `c01274cc` (hence through both blocking
locks) when, and only when, the peek says there is room. This is a
deliberate, disclosed compromise: it is **not** a proven non-blocking send
(see item 3's `send_cc` comment), only a bounded-in-practice one, because
no non-blocking stock entry point exists to call instead. Status: done.

## 3. Bounded producer/consumer design (C/asm in build/sonnet4a/)

Files: `build/sonnet4a/controller_drain.c`, `build/sonnet4a/controller_drain.cmd`.
Compiled and linked for `c01a4000` (16 KiB window) with the exact `cl6x`
flags from `tools/make_controller_fw.py`'s `build_payload()`
(`--silicon_version=6740 --abi=eabi --c99 --opt_level=2
--mem_model:data=far --mem_model:const=data`), own `lnk6x`, own `dis6x` to
`build/sonnet4a/controller_drain.dis`. Status: compiles and links clean
(only the two benign warnings `make_controller_fw.py`'s own build also
emits: no `libc.a`, no `_c_int00` -- re-verified by building the real
`controller.c`/`controller.cmd` the same way as a control). Confidence:
confirmed (built artifact, not a design sketch).

Build note for whoever links this in: `controller.cmd` needed no
`--retain`, but because this module has more than one data object the
linker, run alone with `--ram_model` and no entry point, dropped every
section ("no input section is linked in") until I added
`--retain="*(.text)"` and `--retain="*(.drain_state)"` to
`controller_drain.cmd` -- same mechanism as `controller.cmd`'s existing
`--retain="*(.ctl_state)"`/`*(.text:dispatch)"`, just covering a whole
section instead of one symbol. If this module is merged into
`controller.cmd` instead of linked standalone, that existing file's
retains plus the reachability from the three already-hooked entry points
should make a separate retain for this module unnecessary -- not verified
here since I did not edit `firmware/controller/controller.cmd`.

### Design

Producer hooks publish latest-value+dirty state with **no locks, no
waits** (brief requirement), split by which task actually produces them:

- Knobs (CC40-43) and buttons: produced by `controller_event()` in the
  MainApp task. The chosen drain hook (item 1) also runs in the MainApp
  task, so these need no lock at all -- same-task, not reentrant.
  `drain_publish_knob()` sets a value byte and a dirty bit.
  `drain_publish_button()` pushes into a bounded 16-slot ring
  (`btn_q`, power-of-two length, wrap via `& BTN_QMASK`, never `%`). Policy
  for a full queue: **drop the new edge**, not an old one -- keeps
  press/release ordering for whatever is already queued, at the cost of
  losing the newest edge under sustained overflow. Buttons are not
  coalesced into a latest-value slot, per recon/17 A3's explicit rule.
- Expression (CC11): produced by `controller_analog()` in the **AD task**
  (recon/18 1.6), genuinely concurrent with the MainApp-task drain. Only
  this field uses `volatile` single-byte reads/writes
  (`drain_publish_expr`, consumed as snapshot-then-clear in
  `controller_drain`). The snapshot-then-clear order can drop at most one
  superseded sample if the AD task writes a newer value in the narrow
  window between the drain's read and its clear; that is the same
  "overwrite obsolete unsent motion" coalescing the brief explicitly
  allows for continuous controls, so it is accepted, not closed.

Consumer (`controller_drain()`, called from `controller_housekeeping_hook`,
item 1's hook target) sends at most `MAX_PER_DRAIN` (4) CCs per MainApp
loop pass: drains queued button edges first (FIFO order), then any dirty
knobs, then expression if a slot remains, **each gated by
`ring_free_estimate() >= 3`** before calling `send_cc()`, and returns
immediately (without sending) the first time there isn't room, retaining
whatever is left dirty/queued for the next pass.

```c
static int ring_free_estimate(void)         /* item 2's lock-free peek */
{
    u32 read_idx  = RING_OBJ[0];
    u32 write_idx = RING_OBJ[1];
    u32 used = (write_idx - read_idx) & RING_MASK;  /* RING_MASK = 0x3FF */
    return (int)(RING_MASK - used);
}
```
Verified in `controller_drain.dis` to compile to mask/subtract only, no
divide-library call:
```text
c01a4098 MVK.S2  0x7b28,B4   ; &ring_obj (c0117b28)
c01a40a4 LDW.D2T2 *B4[0],B5  ; read_idx
c01a40a8 LDW.D2T2 *+B4[0],B4 ; write_idx (B4 += 4 first)
c01a40ac MVK.S1  0x03ff,A3  ; RING_MASK
c01a40b4 SUB.L2  B4,B5,B4
c01a40b8 EXTU.S2 B4,22,22,B4 ; & 0x3FF, no division
c01a40c2 SUB.L1X A3,B4,A4   ; RING_MASK - used
```
Confidence: confirmed (disassembly of the actual build, matches the hand
read of the stock test in item 2).

### The one call that can still block (disclosed per the brief)

`send_cc()` still reaches the real stock send:
```text
c01a40c4 send_cc:
c01a40c4 MVK.S1  0x74cc,A5
c01a40c8 MVKH.S1 0xc0120000,A5   ; A5 = 0xc01274cc
c01a40cc STW.D2T2 B3,*B15--[4]
c01a40d0 B.S2X   A5               ; tail-call into stock MIDI_SEND
```
This is a deliberate choice (item 2): going through `c01274cc` means the
stock worker-wake/callback behavior inside `c0149de4` happens automatically
(the appended byte(s) are not just stored, the worker is actually woken),
which a raw bypass of `c0149d74` would have to reimplement and was not
attempted here. The cost is that `c01274cc` still acquires `B14[161]`
(timeout -1) and `B14[89]` (timeout unknown, likely -1) before touching the
ring -- **this is the one call in the whole design that is not provably
non-blocking.** The `ring_free_estimate()` gate only avoids making this
call when there is visibly no room; it does not bound how long the call
takes once there is. No stock non-blocking/zero-timeout entry point was
found to replace it with (item 2). Confidence: confirmed (disassembly);
the blocking risk itself is inherited from recon/17 A3 / recon/18 1.6,
confirmed there.

No asm was needed: `controller_housekeeping_hook` and every other function
compiled from plain C, and the disassembly confirms it (grep for `CALLP`
and `B14\[` across `controller_drain.dis` both return nothing -- the whole
module uses absolute branches it builds itself, never the stock far-data
page register or a stock lock-acquire routine, except via the one tail-call
into `c01274cc` above).

### What is missing (not invented, stated)

- No fixed-period bound on drain latency (item 1).
- No proof that `send_cc`'s call into `c01274cc` is bounded-time, only that
  it should usually be short (item 2 / this section).
- Whether any stock code path other than this design's own `send_cc`
  still produces into the same MIDI ring while controller mode is active
  was not re-checked here; if one does, the single-producer assumption
  behind treating `ring_free_estimate()`'s peek as safe to act on (without
  itself taking a lock) would need revisiting. This design never writes
  the ring directly, only peeks it read-only and then goes through the
  real stock send, so a second producer would race the stock locks against
  each other as before, not against this peek -- but it was not proven
  that no second producer exists.
- `ctl_mode`, `knob_dirty`, `knob_value`, `btn_q`, `expr_dirty`,
  `expr_value` here are standalone copies for the compile check; wiring
  `controller_event`/`controller_analog`/`ctl_state.mode` in
  `firmware/controller/controller.c` to call `drain_publish_*`/
  `drain_set_mode` instead of calling `cc()`/`MIDI_SEND` directly, and
  merging this module's `.cmd` into the real build, is integration work
  left to the owner (brief: "do not edit firmware/... code goes in your
  scratch folder and Claude integrates it").

Status: done.

## Review and integration by Claude (2026-10-08)

Integrated into `firmware/controller/controller.c` with two corrections:

1. **Ring arithmetic.** The ring has 1025 positions (indices 0..1024, wrap after 1024, full when next write == read; recon/17 A3, c0149d84 forms 1024 as the last index). Masking with 0x3ff miscounts near the wrap. `ring_free()` now computes used = w >= r ? w - r : w + 1025 - r, and free = 1024 - used.
2. **Expression stall.** MainApp's receive (c015350c -> c01534c4 -> c0166680 on mailbox B14[162]) waits with timeout -1. The AD task posts no MainApp event for analog changes, so with a drain-only design an expression change would wait for the next button or knob event. The fix: when the expression value becomes pending, controller_analog posts one event 42 with timeout 0 via c0166780(*(c0185088), &msg, 0), the same non-waiting post stock uses at 1180a840 (event 43, `MVK.L1 0,A6`). A received 42 goes c0153554 -> c01535ce (41/42) -> c01536a4, which zeroes two event words and returns. The MainApp loop then skips the handlers at c0134dec and runs housekeeping (c0134dc4), where the drain sends the value. B14 = c0184e00 (c0169a38/c0169a3c), so B14[162] is at c0185088.

Fourth hook: c0134dc4 `CALLP c01537f4` (file 0x28d40, word 103d4692) -> controller_housekeeping, which calls c01537f4 and then, in controller mode, the drain. The payload is 1504 bytes. The disassembly shows no B14 use and no runtime-library calls. The message copy uses STDW to B15+8, which is 8-byte aligned. The test updater is rebuilt (SHA-256 c6317cac…).
