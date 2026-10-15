# Stack-analysis continuation — 2026-10-14

The **1,784-byte figure is withdrawn as a worker-stack ceiling**. It was a
heuristic graph result with unknown callbacks and cut cycles. This review found
additional modeling errors, so it cannot establish any margin within the
2,048-byte allocation. No overflow is demonstrated either. Stack and USB
lifecycle gates remain open; the lifecycle candidate remains DO_NOT_FLASH.

## Instruction findings

1. `c014a0cc` calls the save helper `c016e020` using A3 as the continuation
   register. `c016e020..e032` pushes 56 bytes and branches back through A3
   **without popping those bytes**. They remain live while the wrapper calls
   `c0144580` at `c014a0f8`. The later `c014a114 -> c016e000` restores them
   and returns through the saved B3. A call-tree maximum over these two sibling
   calls does not account for the live helper frame. The revised tool flags
   this pattern rather than assigning a finite total.
2. The old generic resolution supplied all six task-hook targets to every
   indirect site. This creates unsupported edges while missing the actual
   formatter, diagnostic, idle and other targets. Observations now apply to
   individual instruction addresses and remain explicit assumptions.
3. Suppressing every A3 branch as a return hid callbacks. A register loaded
   from a stack slot somewhere earlier in a function is also insufficient
   return evidence: another load or call can change it before the branch.
   The revised inventory leaves non-B3 transfers unresolved unless mapped.
   This intentionally includes some real return aliases for later review.
4. The catalog merges the wait wrapper with nearby entries. Explicit boundaries
   at `c014a120`, `c014a160`, `c014a170` prevent those routines' calls and
   pushes being charged to the wait wrapper. `c016b940` is also a separate
   entry: its prologue begins at that address, independently of `c016b7c0`.
   Other uncatalogued entries remain blockers. The inventory refuses to scan
   their bodies, or a last catalog entry without an end, through adjacent code
   or data. Catalogued extents still need semantic validation.

## Callback progress

Static words below were read from `build/fw/map/main.elf`; arguments were
checked against `main.dis`, including branch delay instructions.

| Branch site | Evidence | Observed target(s) | Remaining condition |
|---|---|---|---|
| `c0150bf8` | `c0150ba0/ba4` construct `c0180d1c`; `c0150bb8` loads B7 | `c0161540` | Runtime writer completeness |
| `c013ce6c` | `c013cda4/cdac` construct `c0181a48`; `c013cdb0` loads A5 in the delay sequence of `c013cda8 -> c013ce68` | `c015aa20` | Runtime writer completeness; formatting-path context |
| `c016b992` | `c016e0c0` stores incoming A4 to `c0183aec` | `c016e200`, `c016e060`, `c01654a0` | All registration callers/aliases and initialization ordering |
| `c0162c70` | Record field [2] at `c0180630` and `c0180648` | Both zero | Record immutability and image identity |
| `c015df2c` | Record field [3] at the same two records | `c0160660`, `c01690c0` | Record immutability and image identity |

The three registration arguments for `c0183aec` are:

- `c0168c70/78` construct `c016e200`, retained in A11 and passed in A4 to
  `c016e0c0` at `c0168ca8/cac`.
- `c016b0e8/ec` construct `c016e060`, retained in A10 and passed in A4 at
  `c016b114/118`.
- `c016c3d8/3e0` construct `c01654a0`, retained in B10 and passed in A4 at
  `c016c3f8/3fc`.

This recovers targets; it does not prove an exhaustive runtime set or bound
their stack usage. The previous note's classification of `c013ce6c` as a
task-hook-table call is superseded: it is in the format-processing path with
a callback slot at `c0181a48`.

The `c0166b28/38` A11 transfers remain caller-sensitive: `c0166aa4` copies
incoming A6 to A11. For example, wrappers `c016d940` and `c016da00` set A6
to `c0163fc0` and `c016e7e0` respectively in their tail-branch delay sequences;
`c016e780` instead passes A6=0. Assigning all of these targets at every call
requires a conservative, context-aware analysis, not a global callback list.
`c015a8fc` still loads a zero-in-image slot at `c01819ec`; its runtime reachability
and writers have not been proved.

## Reproducible inventory

`tools/stack_depth.py` is import-safe and accepts fixture disassembly/catalog
paths. Its JSON contains per-function SP-decrement inventories, edges, explicit
site assumptions, unresolved entries/transfers, live-helper findings, cycles,
and SHA-256 hashes for the analyzer and input files. Callback observations are
in `stack_callbacks.json`; the CLI rejects them for a different disassembly
hash. The observed ELF hash is recorded as provenance. Passing `--elf FILE`
also requires that the callback, extent and transfer records match that
file's SHA-256; it does not prove the disassembly was derived from it or
that runtime writers are exhaustive.

Every report has `status=NOT_A_STACK_PROOF` and `stack_bound_bytes=null`.
`accounted_frame_bytes` is only a graph subtotal for a graph without blockers
or cycles; it still is not a runtime bound. All four current roots return null.
Each root is evaluated independently, avoiding cross-root memoization hiding
findings. Unknown extents and unmodeled control flow can cause false positives
and missing edges; counts are triage findings, not distinct proven callbacks.

```powershell
.venv/Scripts/python.exe tools/stack_depth.py --resolve --report build/controller/stack_inventory_2026-10-14.json c014a0cc c014a094 c014a1c8 c016a9c0
```

Add `--details` for individual findings. Current inventory:

The analyzer also accepts `--extents FILE` and `--transfers FILE` for reviewed
function ranges and return/continuation sites. It verifies the disassembly hash
and every quoted instruction anchor before use, retains annotations as explicit
assumptions, and keeps annotated stack-switch sites as blockers. These inputs
improve graph accuracy; they do not establish a runtime stack bound.

| Root | Functions | Blocker records | DFS cycle records | Site assumptions |
|---|---:|---:|---:|---:|
| `c014a0cc` | 100 | 62 | 8 | 14 |
| `c014a094` | 98 | 59 | 8 | 13 |
| `c014a1c8` | 98 | 59 | 11 | 13 |
| `c016a9c0` | 6 | 6 | 0 | 0 |

## Next evidence

### Lead integration and commit review

Reviewed commits `7e5cd86` and `3a16797`, then integrated the previously
untracked [kernel extents](KERNEL_EXTENTS_2026-10-14.md),
[execution-context evidence](STACK_CONTEXT_2026-10-14.md), their JSON inputs,
and the [USB lifecycle continuation](USB_LIFECYCLE_CONTINUATION_2026-10-14.md).
All quoted extent/transfer anchors match the pinned disassembly. The ELF
and catalog identities were checked separately. The notes' semantic
interpretations remain explicit review assumptions.

Commit review found that explicit B15 writes, including the task stack load
at `c016aecc`, could previously leave a finite graph subtotal if other blockers
were removed. The analyzer now emits `UNMODELED_SP_WRITE` for stack-pointer
loads, register moves, alignment and unrecognized arithmetic. Constant ADD
decrements are also counted. This is not general SP dataflow: memory updates,
loop counts, predicates and delay packets still need semantic analysis.

The physical command-switch owner `c01520f4..c0152240` now spans its internal
catalog fragments. This removes the fake `c0152154` callee and includes calls
to the USB command handlers. The switch dispatch remains unresolved and the
scan includes all physical case bodies without caller-specific pruning.
Consequently more downstream blockers appear; the earlier six-entry USB-send
inventory was incomplete. A separate return-stub extent resolves `c016e940`.

```powershell
.venv/Scripts/python.exe tools/stack_depth.py --resolve --elf build/fw/map/main.elf --extents docs/helpers/stack_extents.json --transfers docs/helpers/stack_context_sites.json --report build/controller/stack_review_2026-10-14.json c014a0cc c014a094 c014a1c8 c016a9c0
```

| Root | Functions | Blocker records | DFS cycle records | Assumptions |
|---|---:|---:|---:|---:|
| `c014a0cc` | 69 | 15 | 0 | 42 |
| `c014a094` | 66 | 11 | 0 | 38 |
| `c014a1c8` | 39 | 7 | 0 | 27 |
| `c016a9c0` | 130 | 58 | 0 | 48 |

All four still have null graph subtotals and null stack bounds. Counts include
overlapping findings, such as the stack load and its later context transfer.
The earlier cycle involving `c0150b20`, `c0164380`, and `c0161200` was
another catalog merge: the `c01644f0` call belongs to the independent routine
starting at `c01644c0`. Reviewed physical ranges remove this cycle and the
unrelated callback-wrapper edge in `c0166780`. Zero cycles in this incomplete
graph does not prove recursion or reentrant scheduling absent. The physical
extent of `c015dc20` is now known; its callbacks are still unresolved when
that wrapper is analyzed independently. The scaled `SUBAW` adjustment at
`c01387f4` remains an explicit SP-modeling blocker.

Seventeen regressions added since the pickup cover explicit SP writes,
constant adjustments, scanning a switch owner across catalog fragments,
anchored extent boundaries, unresolved-record anchors and optional ELF
identity rejection. Full suite: **148 tests and two subtests pass**.
The exact seven-hook candidate verifier and all six updater
stage operations also pass; candidate hashes remain those in the lifecycle
build record. No firmware or device state changed. DO_NOT_FLASH remains.

Evidence validation now checks every declared `unresolved` record as well as
extent/transfer records. Every reviewed extent must quote its own entry and
decoded exclusive-end boundary; a plausible numeric end alone is rejected.
This catches truncated or unanchored ranges but cannot validate the reviewer's
control-flow interpretation.

The USB follow-up identifies the exact poll/queue/recycling behavior in
[USB_ABORT_OWNERSHIP_2026-10-14.md](USB_ABORT_OWNERSHIP_2026-10-14.md).
Successful queue-pending observation still needs association with the
requested endpoint; expiry, Hwi coexistence and reset completion remain open.

### Remaining instruction work

First establish instruction-backed extents for the reachable library entries
and continuation helpers. Then model live save-helper frames and distinguish
actual return aliases from callbacks using control flow and delay sequences.
Resolve runtime registration/diagnostic targets and prove whether scheduler
cycles can grow the worker stack, or whether context switching/guards bound
them. Audit worker drain and event-post paths as well as wait/lock roots.
Interrupt and reset-caller stacks require separate context analysis.

Increasing the worker allocation alone does not close unknown recursion,
ownership or timing gates. A watermark diagnostic can provide measured
evidence after its own access and execution path has been reviewed.
