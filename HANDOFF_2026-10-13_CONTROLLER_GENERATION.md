# Handoff — controller generation candidate — 2026-10-13

## Current status

The reset generation fix is implemented, compiled and packaged offline. **DO_NOT_FLASH: physical hardware testing and flashing remain unapproved.** No updater was launched or pedal touched.

Continue the offline stack and lifecycle/context audits, then propose an owner-run test with exact artifact hashes. The broader priority remains processed pedal audio to the computer over USB alongside MIDI; see HANDOFF_2026-10-13_ASTRA.md for USB audio context.

## Implementation

- firmware/controller/controller.c adds generation and observed_generation. The sixth CALLP hook at c014a048 replaces the unlock inside stock reset c014a018 with controller_reset_unlock. It increments generation under B14[89], releases the original lock, then wakes the MIDI worker. It preserves the release result and stock mode behavior.
- The worker holds B14[89] through generation observation, at most four complete CC appends, and sent-state commits. A generation change discards obsolete button edges and invalidates sent-state for desired-state replay. A complete batch requests another wake; a full ring leaves values pending.
- tools/make_controller_fw.py validates six hooks, including both analog channels. tools/make_fs_restore_updater.py uses that hook list.
- tools/controller_transport_model.py and tests/test_controller_transport_model.py add reset-only observation and three policy regressions. These tests do not execute TI firmware.

## Exact artifacts

| Artifact | SHA-256 |
|---|---|
| build/fw/res1_controller_generation_candidate.bin | a7e4a13719d77af0c0d456c3dd5d5e9d7ee22fa0e3d1004664936127bfbe7593 |
| build/controller/DO_NOT_FLASH_controller_generation_candidate.exe | ac7030c6707343608ae3f20f31f2db88e383602bfedd0adde60649d31aeea12c |

TI C6000 8.5.0.LTS, C6740, EABI, C99, O2. Payload: 2,976 bytes at c01a0000..c01a0b9f, inside 16 KiB reservation. Firmware: 496,400 bytes. Base: build/fw/res1_cfupd.bin, preserving artwork/text. Presets and effects inputs: build/fw/cfupd_res85.bin and build/fw/cfupd_res88.bin.

| Call site | Linked target |
|---|---|
| c0134e14 | controller_start, c01a0654 |
| c0134df0 | controller_dispatch, c01a0b40 |
| c015ffd0 and c01600b0 | controller_analog, c01a0980 |
| c0149d4c | controller_worker_wait, c01a0144 |
| c014a048 | controller_reset_unlock, c01a070c |

The older worker candidate files were preserved and remain stale. Old executable SHA-256: 91b9894e30946bd6205a1dab699e5900f1b9834ae6c513fad60c7fae4ff7644a. Old loose firmware: f1478153ed179d167a799ba4f94aedd3a1a4550f20ab771cfc38bc84b9d4c021. Old embedded firmware: 0ecddd890ed7925471a00a749a11ccc3b8eda9c2b646ef1795bcaa81bcfc89e2. Do not confuse these with the generation candidate.

## Verification already completed

The implementation turn recorded **91 tests passed, 2 subtests passed**. All six updater stages pass. Resource 0x81 equals the new firmware byte for byte; the AIS payload equals the linked ELF allocation. All other BIN resources match the old candidate. Each hook reaches its exact ELF symbol with non-target bits preserved. Restoring any single hook to stock is rejected. Six patched fetch packets were independently assembled and decoded with TI dis6x.

The exact stage table has erase/write pairs for presets at 0x28000, effects FS at 0x102000, and main firmware at 0x33000. Full resource write sizes were also bounded inside permitted regions. Boot/update and settings regions are excluded.

Full record: docs/CONTROLLER_GENERATION_CANDIDATE_2026-10-13.md.
Build verifier: build/controller/verify_generation.py.
Source/resource hashes: build/controller/generation_manifest.json.
TI packet listings: build/controller/generation_packet_audit/.
Build artifacts are ignored by Git; preserve them or recreate them when moving checkouts. This handoff did not rerun tests.

## Remaining gates and next work

1. Prove task stack allocation and worst-case headroom. Worker frame remains 72 bytes; known partial wait depth is 312 bytes (72 + 56 + 184), before deeper callees and preemption. Reset wrapper adds a 24-byte frame and another call path. The 0x800 word at c0180520 near worker entry c0149d40 is only a lead. Trace descriptor consumption and task creation; include deeper kernel calls, ISR nesting, and any separate interrupt stack. Do not infer spare capacity by subtracting 312 from an unverified descriptor word.
2. Finish lifecycle and callback-context coverage. The fix covers event 8 and c014a058(0) through c014a018. It does not prove every lifecycle transition or computed/aliased ring write passes the hook. Audit readiness writers, reset callees, event producer contexts, lock initialization/destruction, downstream packet ownership, and transitive callbacks. Review the four-CC lock duration and wake legality in every reset caller context.
3. Review source together with compiled instructions. Model tests establish policy only. Rebuild and verify a new exact identity after any source change.
4. Only after those gates close, present hashes and a bounded input/reconnect/reset test plan for owner approval. Flashing has not been authorized.

Audit entry points: docs/helpers/WORKER_ABI_AUDIT_2026-10-13.md, docs/helpers/USB_LIFECYCLE_AUDIT_2026-10-13.md, docs/helpers/ASTRA_WORKER_REVIEW_2026-10-13.md, and build/fw/map/main.dis.

## Working tree

HEAD at handoff: 726a026 — docs: controller worker ABI, timeout units, and USB lifecycle audit.
Implementation is uncommitted. Preserve modified files:

- firmware/controller/controller.c
- tools/make_controller_fw.py
- tools/make_fs_restore_updater.py
- tools/controller_transport_model.py
- tests/test_controller_transport_model.py
- docs/CONTROLLER_WORKER_CANDIDATE_2026-10-12.md
- docs/helpers/USB_LIFECYCLE_AUDIT_2026-10-13.md

New documentation: docs/CONTROLLER_GENERATION_CANDIDATE_2026-10-13.md and this handoff. .agents/ and bridge/ were already untracked; preserve them. Recheck status before editing. The older Astra handoff's working-tree description predates this one.

## Reproduction

Run from C:/Users/z/Documents/zoom project:

```powershell
.venv/Scripts/python.exe tools/make_controller_fw.py --base build/fw/res1_cfupd.bin --out build/fw/res1_controller_generation_candidate.bin
.venv/Scripts/python.exe tools/make_fs_restore_updater.py 'C:/Users/z/Downloads/G1X FOUR_v2.00_Win_E/ZOOM G1X FOUR System v2.00 Updater.exe' build/controller/DO_NOT_FLASH_controller_generation_candidate.exe --controller-fw build/fw/res1_controller_generation_candidate.bin --presets build/fw/cfupd_res85.bin --image build/fw/cfupd_res88.bin
.venv/Scripts/python.exe tools/check_updater_stages.py build/controller/DO_NOT_FLASH_controller_generation_candidate.exe
.venv/Scripts/python.exe build/controller/verify_generation.py
.venv/Scripts/python.exe -m pytest -q
```

Receive-only monitor for an already-running earlier image: .venv/Scripts/python.exe tools/cf_midi_monitor.py. It does not install or validate this candidate.
