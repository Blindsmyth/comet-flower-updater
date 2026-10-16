# USB mode — Codex Astra — 2026-10-16

## Summary
Work in progress; offline disassembly analysis only.

## U1. Ordering at boot

## U2. Software disconnect / reconnect

## U3. Full re-open functions, contexts, and synchronization

## Unproved points
### Finding 1 — connect wrapper includes teardown (U2/U3)
**Confidence: confirmed** for call graph; lifecycle safety is not yet established.
`c015af18 STW B3,*B15--[2]`; `c015af20 CALLP c0138720` is the public
connect wrapper, not the POWER write itself. `c0138722 CALLP c013826c`
first shuts down the previous instance. Shutdown starts `c0138274 CALLP
c011ff28`, then handles task/synchronization objects in B14[94..96]:
`c0138298 CALLP c014a160`, `c01382a4 CALLP c014a2b0`,
`c01382d0 CALLP c014a344`, `c01382e0 CALLP c014a340`.
Creation uses `c0138730 CALLP c014a4d0`, `c013876c CALLP c014a4d4`,
`c01387ac CALLP c014a400`, storing handles in B14[96], [95], [94].
The explicit stop wrapper is `c015af10 CALLP c013826c` (entry c015af0c).
These wrappers need task-context lifecycle serialization; they cannot be
assumed to be a harmless SOFTCONN toggle from Hwi.
### Finding 2 — actual POWER writes and shutdown work (U2)
**Confidence: confirmed.** POWER is 0x01e00401. Connect: `c0120e18 LDBU
*A4[0],A0; c0120e1a SET A0,6,6,A0; c0120e20 STB A0,*A4[0]`.
Disconnect: `c011ff34 LDBU *A4[0],A1; c011ff4a CLR A1,6,6,A1;
c011ff4c STB A1,*A4[0]`. Stop also writes zero / 0x4000 through
0x01e01800 / 0x01e01808 with 32-byte strides (`c011ff68 STW
A0,*B4++[8]`; `c011ff6c STW B0,*A4++[8]`), masks wrapper interrupts
(`c011ff8a STW A0,*A4[0]`, address 0x01e00034), and calls interrupt
control `c011ff8c CALLP c014a2a0` with A4=7. Connect enables interrupts
(`c0120de8 CALLP c014a278`, A4=7), iterates endpoint setup
`c0120df0 CALLP c0120888; c0120e00 CALLP c01201e0`, then sets SOFTCONN.
Thus stock disconnect does more than remove the pull-up. DMA descriptor
ownership reclamation is not proved by these register writes alone.
### Finding 3 — normal boot ordering and task priorities (U1)
**Confidence: confirmed** for the traced normal-boot control flow and task
records; **likely** that no untraced indirect task-priority mutation bypasses it.
The important boundary is NOT entry versus return of stock c015d428:
`c0134e14 CALLP c015d428` returns BEFORE `c0134e18 CALLP c0134db8`;
`c0134dc0 CALLP c01341e4` then performs the later application initialization.
That later initialization calls switch setup (`c0134200 CALLP c01570a4`)
and initial USB detection (`c0134354 CALLP c016c120`). Initial detection
uses `c016c140 CALLP c016ec60` (veneer to GPIO78 reader 1180950c), and
on its zero branch `c016c150 CALLP c016ab8c` starts USB in **MainApp**.
Thus controller_start's current source order, STOCK_STARTUP then two
READ_SWITCHES calls then mode assignment, is still before this USB open.
This corrects the tempting but incorrect inference that all application
initialization occurs inside c015d428.

Decoded static task objects in build/codex3/init_c0181b28.bin:
MainApp object c0181b28 has priority +8 = 3, entry +40 = c0134e10;
SwitchNrmlSpdRead object c0181c90 has priority +8 = -1 (inactive), entry
+40 = 118076c0. B14 base c0184e00 is established by `c0169a38 MVK
0x4e00,B14; c0169a3c MVKH 0xc0180000,B14`; c0185070 (B14[156])
contains c0181c90. Switch setup enables priority **9**:
`c0157138 CALLP c01529c0; c0157140 LDW *+B14[156],A4;
c0157144 MVK 9,B4` (parallel call argument packet).
Later GPIO78 changes are handled in that switch task by 1180a7ec:
`1180a874 CALLP 1180b150`, veneer `1180b150 MVK 0xab8c,B31;
1180b154 MVKH 0xc0160000,B31; 1180b158 B B31` -> c016ab8c.
Its initialization gate is `1180a800 LDBU *A5[0],A0; 1180a804 [!A0]
BNOP 1180a890`, A5=118134a0, set by `c016c172 STB A0,*A4[0]`.

Both paths converge: `c016ab94 CALLP c015b114` (endpoint-layer init),
`c016ab98 CALLP c016ab70`; `c016ab78 CALLP c0159758`;
`c01597b0 CALLP c0145124`; `c0145158 CALLP c0152410`;
then `c016ab80 CALLP c015af18`. Open and SOFTCONN run synchronously
in the initiating task: MainApp priority 3 initially, switch task priority 9
on its transition path, NOT in the new USB worker. The created worker is
c0138310, priority **30**, descriptor c01800bc: `.word c0138310` at
c01800c4, `.word 0x1e` at c01800c8, name pointer c01817d0 at c01800d4.
`c01387ac CALLP c014a400` creates it; `c014a438 LDW *A4[3],A0`
loads priority into Task params before `c014a46c CALLP c0165920`;
`c01387d0 CALLP c014a170` starts it, then `c01387e8 CALLP c0120dd0`
sets SOFTCONN in the caller. Worker receives at `c0138318 CALLP
c014a214` using B14[95]. Static MainApp/switch objects are C-initialized,
not created by this USB task factory.

Answer: c0134e14 (including the current latch before its return) precedes
c0145158 on the traced normal paths. No move is required for these paths.
A defensive common pre-open latch could run once at entry to c016ab8c,
before c016ab94, with already initialized GPIO; or immediately before
c0145158 if only registration needs guarding. These are **likely design
options**, not claims of a verified new patch. Do not re-sample on every
cable reconnection: latch once per power-up, initialize FX by default, and
preserve later explicit settings-page choices. Earlier raw GPIO reads
before platform initialization are not certified here.
