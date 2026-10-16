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
