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
