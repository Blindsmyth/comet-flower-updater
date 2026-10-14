# Controller lifecycle candidate — 2026-10-13

**DO_NOT_FLASH. Offline candidate; no updater/device operation.** This supersedes
the generation candidate for continued review. Hardware-test readiness has not
been established.

## Issues fixed

The generation candidate posted the MIDI event from MainApp, AD and the reset
callback. Stock teardown deletes the worker, then the event, then the ring lock.
Loading a nonzero event handle before a post is insufficient to protect it from
deletion during preemption. There was also a separate replay gap: reinitialization
clears the entire transmit object with `memset` at `c0149f34`, bypassing the
generation hook inside `c014a018`. A new worker could therefore retain the old
controller sent-state even though its transport had been cleared. These are
offline interleavings, not observed hardware failures.

The revised firmware:

- Removes event posts from button/knob publication, AD publication and reset.
  Producers now write controller-owned state only and never load a MIDI kernel
  handle. A reset publishes its generation while holding the original ring lock
  and tail-calls the original release.
- Polls every **10 Clock ticks** while in controller mode. First-input latency
  is therefore up to a polling interval plus scheduler/transport delay. The
  absolute tick duration and CPU cost require further verification; the old
  documentation's assumed 1 ms tick is not a measured fact for this image.
- Keeps the bounded four-CC batch. A complete batch self-posts using the event
  supplied to this worker, so initial replay can continue without waiting for
  a fresh poll. The worker is deleted before its event by normal stock teardown.
- Adds a seventh hook at `c0149fa8`, before stock task creation. It sets
  `tx.connected=0` before creating the replacement MIDI worker. Its first ready
  pass then discards stale edges and replays current desired values, even if
  task/event/lock addresses are reused.

The new creation hook relies on the stock init guard at `c0149f00..9f24`, which
rejects initialization if any worker, event or lock handle remains. The ring is
cleared before handles are created; lock/event creation precedes worker creation.
Normal worker deletion cannot be a self-delete here: the traced teardown callers
are the USB setup/init and switch-speed paths, not the MIDI worker. The failed
self-delete path leaves its handle nonzero, which also blocks reinitialization.
This evidence supports the new pre-create invalidation point; it is not a global
proof of every stock failure path.

## Exact artifact identity

| Artifact | SHA-256 |
|---|---|
| `build/fw/res1_controller_lifecycle_candidate.bin` | `9634c77c5f7687ac68df8606542f35235f9645c51ce35f8dd092d6f75f54239b` |
| `build/controller/DO_NOT_FLASH_controller_lifecycle_candidate.exe` | `ed5212ecca25def0432b1cdea7e81674f3df052dc4bbe7c7642fbb63651e90bc` |
| `build/controller/lifecycle_controller.elf` | `208ebbe38d80c65ed40ccffcc2bbedf23a9b0f16beb948fb5dfa207ddd784791` |

The firmware is 496,240 bytes. The linked payload is 2,816 bytes at
`c01a0000..c01a0aff`, within the existing 16 KiB reservation. Base artwork,
presets and the 38-file effects image are preserved from the preceding inputs.
Build metadata and source/resource hashes: `build/controller/lifecycle_manifest.json`.

| Call site | Linked target |
|---|---|
| `c0134e14` | `controller_start`, `c01a0684` |
| `c0134df0` | `controller_dispatch`, `c01a0aa0` |
| `c015ffd0`, `c01600b0` | `controller_analog`, `c01a0920` |
| `c0149d4c` | `controller_worker_wait`, `c01a0144` |
| `c014a048` | `controller_reset_unlock`, `c01a0734` |
| `c0149fa8` | `controller_worker_create`, `c01a0654` |

## Compiled behavior reviewed

- `controller_worker_create`, `c01a0654..680`: no SP adjustment, B3 unchanged,
  A4 descriptor preserved. It branches to `c014a400`; its delay sequence stores
  zero to `tx.connected` at `c01a067c` only in controller mode, before the
  target starts. The target returns directly to the original caller.
- `controller_reset_unlock`, `c01a0734..764`: no SP adjustment or nested CALLP,
  B3 and A4 lock argument preserved. It increments/stores the generation before
  the tail branch completes into `c014a1c8`. The original release result returns
  directly to the stock caller. The removed post is absent in both modes.
- The worker retains its 72-byte actual SP decrement. MainApp/AD controller
  publication has no event-post call; analog stock mode retains its original
  `c014aef4` tail path. Self-post remains outside the ring lock in the worker.
- All seven patched fetch packets were independently assembled and decoded
  using TI tools under `build/controller/lifecycle_packets/`.

## Verification and remaining gates

**109 tests passed, 2 subtests passed.** Three additional policy regressions
cover a reset with no notification, worker recreation without a generation
change, and input/full-ring recovery without kernel notifications. They do not
execute TI code. The full candidate verifier checks ELF/payload identity, seven
exact targets, rejection of any missing hook, unchanged other resources, all
eight stage-table rows and full resource write bounds. The separate stage checker
passes all six operations.

Stack allocation and interrupt-stack placement are now traced, and the two
lifecycle hook tail paths add no frame. **The complete worst-case worker stack
bound is still open.** In particular, the catalog combines/splits some kernel
functions incorrectly; `c015a020` and `c015de40` are real hidden entries, and
`c0162be0` is a task-ready operation with hook callbacks, not a simple diagnostic
logger. Bounds inferred only from catalog extents would be invalid. Continue
through the hook records at `c0180630` and kernel diagnostic paths before
claiming spare capacity. See `helpers/STACK_AUDIT_2026-10-13.md`.

The normal reset/reinitialization observation gaps and added producer event
lifetime race are addressed. Remaining USB evidence concerns transitive
downstream ownership/progress, all readiness aliases, and timing under actual
traffic. The four-CC lock interval and faster polling have no measured audio/USB
CPU budget. Do not turn passing model/packaging checks into hardware approval.

## Reproduce offline

```powershell
.venv/Scripts/python.exe tools/make_controller_fw.py --base build/fw/res1_cfupd.bin --out build/fw/res1_controller_lifecycle_candidate.bin
Copy-Item -LiteralPath build/controller/controller.elf -Destination build/controller/lifecycle_controller.elf
.venv/Scripts/python.exe tools/make_fs_restore_updater.py 'C:/Users/z/Downloads/G1X FOUR_v2.00_Win_E/ZOOM G1X FOUR System v2.00 Updater.exe' build/controller/DO_NOT_FLASH_controller_lifecycle_candidate.exe --controller-fw build/fw/res1_controller_lifecycle_candidate.bin --presets build/fw/cfupd_res85.bin --image build/fw/cfupd_res88.bin
.venv/Scripts/python.exe tools/verify_controller_candidate.py --firmware build/fw/res1_controller_lifecycle_candidate.bin --updater build/controller/DO_NOT_FLASH_controller_lifecycle_candidate.exe --elf build/controller/lifecycle_controller.elf --reference-updater 'C:/Users/z/Downloads/G1X FOUR_v2.00_Win_E/ZOOM G1X FOUR System v2.00 Updater.exe' --presets build/fw/cfupd_res85.bin --effects build/fw/cfupd_res88.bin --manifest build/controller/lifecycle_manifest.json --packet-audit build/controller/lifecycle_packets
.venv/Scripts/python.exe tools/check_updater_stages.py build/controller/DO_NOT_FLASH_controller_lifecycle_candidate.exe
.venv/Scripts/python.exe -m pytest -q
```

Older candidate `.exe`/firmware files are preserved. The builder's generic
`controller.elf/.asm/.dis/.map` outputs now describe this candidate; named
`lifecycle_controller.*` copies are retained. The current seven-hook verifier
intentionally rejects older six-hook candidates. To reproduce their historical
records, use the source/tool versions at their recorded commits.
