# Static worker-stack bound - 2026-10-13

**Superseded:** [the 2026-10-14 continuation](STACK_CONTINUATION_2026-10-14.md)
withdraws the 1,784-byte ceiling after reviewing callback resolution, live
save-helper frames and catalog extents. This note preserves the historical
calculation, not a current bound. The updated tool reports no finite ceiling.

**DO_NOT_FLASH. Offline analysis only; no device or updater touched.** Tool:
`tools/stack_depth.py` (recursive walker over `build/fw/map/main.dis`).
`tools/stack_paths.py` lists per-root prologue spills and outgoing branches.

## Method

- Frame of a function = sum of all SP decrements (`STW/STDW/STH/STB *B15--[n]`,
  `SUB B15,k`, `ADDK -k,B15`). Mutually exclusive paths are summed, so this
  over-approximates. Spill scaling was cross-checked against the known 72-byte
  controller worker frame.
- Function extents come from `subsystems.tsv` plus the nine hidden entries
  (`c015a020`, `c015de40`, ...), not catalog extents alone.
- Tail branches out of a function are charged the caller's full frame.
- A register branch whose register was reloaded from the stack or copied from
  `B3` in the same function is treated as a return.
- Remaining register branches are data-driven callbacks. With `--resolve` they
  gain the six handler pointers from the task-hook records
  (`c0180630..c0180660` and `c018172c`): `c0160660`, `c016e960`, `c0163460`,
  `c01690c0`, `c015cf20`, `c016eaa0`. A sweep of *every* code pointer in the
  config block was tried and rejected: it pulls in application callbacks and
  produces no useful bound.

## Result (conservative, conditional)

| Component | Bytes |
|---|---|
| Wait frames above the kernel call, incl. stock worker (previous audit) | 320 |
| Deepest kernel path from `c014a0cc` (`--resolve`) | 1104 |
| Interrupt context charged on the task stack (previous audit) | 352 |
| Alignment allowance | 8 |
| **Total** | **1784** |

Requested stack: 2048, so the computed margin is **264 bytes (~13%)**.

Other roots from the same run: lock pend `c014a094` 848, lock post `c014a1c8` 168
(reset path, excludes the hook callee), `c016a9c0` 944.

## Why this is not a proof

- 22 distinct indirect sites remain after resolution (listed by running
  `stack_depth.py --resolve c014a0cc`); some are real callbacks outside the six
  hook handlers (for example `c0144784`, `c0150bf8`, `c015a8fc`, `c0166b28`).
  Their targets are not known to be in the resolved set.
- Cycles were reported through `c015cf20`/`c0150b20`/`c015a7a0` and are cut,
  not bounded. The callbacks may recurse through the scheduler.
- The walker assumes the interrupt cost is the 352 B measured earlier and that
  nested interrupts are not charged more than once.
- No `0xBE` watermark has been measured on hardware.

## Gate status

Stack gate: **still open**, but with a concrete computed ceiling and a list of
sites to close. Next steps: resolve the 22 indirect sites by name; measure the
watermark in an owner-run test using a reviewed diagnostic path.

```powershell
.venv/Scripts/python.exe tools/stack_depth.py --resolve c014a0cc c014a094 c014a1c8 c016a9c0
```
