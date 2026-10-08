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

## 3. Bounded producer/consumer design (C/asm in build/sonnet4a/)
