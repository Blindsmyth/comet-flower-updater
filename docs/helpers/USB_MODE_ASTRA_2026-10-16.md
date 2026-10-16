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
