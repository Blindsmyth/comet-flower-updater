# Handoff — offline validation phase — 2026-10-13

## Current continuation: lifecycle candidate

The following original checkpoint is superseded by
[the lifecycle candidate record](docs/CONTROLLER_LIFECYCLE_CANDIDATE_2026-10-13.md).
Current firmware removes producer/reset event posts, polls at 10 Clock ticks,
and hooks worker creation to force replay after stock teardown/reinitialization.
Both lifecycle hooks compile as tail branches with no added stack frame.
The suite now passes **109 tests and 2 subtests**, and all seven hooks and updater
resources/stages pass verification. Exact hashes and reproduction commands are
in that record; use the named `lifecycle_controller.elf`, not an older ELF.

Hardware remains deferred: finish worst-case kernel/hook stack paths and USB
ownership/timing evidence. The interrupt-stack reservation is traced to 12 KiB;
this is allocation evidence, not a measured margin. No device was accessed.

## Original validation checkpoint (historical)

## Phase status

Implementation is saved in `c72f789` (`fix: replay controller state after MIDI
ring resets`). Offline artifact verification is reproducible from tracked tooling.
**DO_NOT_FLASH: the stack and lifecycle/context gates remain open.** No updater
was launched and no hardware was accessed. USB audio integration has not started;
the combined processed USB audio plus MIDI goal and sequence in
`HANDOFF_2026-10-13_ASTRA.md` still apply.

## Completed this phase

- Reran the suite: **106 tests passed, 2 subtests passed**. Fifteen new verifier
  tests reject changed resources, altered stage rows (including trailing rows),
  oversized firmware and incomplete preset/effects region inputs.
- Recompiled the current controller source with the existing TI toolchain into
  `build/fw/res1_controller_generation_rebuild.bin`. Its firmware hash is
  identical to the existing candidate. The rebuilt ELF hash also matches.
- Ran `tools/verify_controller_candidate.py` against the official updater,
  rebuilt ELF, candidate firmware/updater, presets and effects. All six hooks,
  payload allocation, embedded resources, full eight-row stage table and write
  bounds pass. Restoring any single hook to stock is rejected.
- All six stages pass the separate `tools/check_updater_stages.py` checker.
- Independently assembled and decoded all six patched fetch packets with TI
  tools in `build/controller/phase_validation_packets/`; each hook reaches the
  recorded linked symbol.
- Traced stack request/allocation, sentinel fill, task context switching and
  interrupt stack switching. Corrected the partial note's stock worker frame
  from 72 bytes to **8**. Details: `docs/helpers/STACK_AUDIT_2026-10-13.md`.
- Linked one indirect event-8 producer through callback registration and
  audited the packetizer-reset leaf subtree and teardown order. Details:
  `docs/helpers/USB_LIFECYCLE_AUDIT_2026-10-13.md`.

## Artifact identity

| Artifact | SHA-256 |
|---|---|
| `build/fw/res1_controller_generation_candidate.bin` | `a7e4a13719d77af0c0d456c3dd5d5e9d7ee22fa0e3d1004664936127bfbe7593` |
| `build/controller/DO_NOT_FLASH_controller_generation_candidate.exe` | `ac7030c6707343608ae3f20f31f2db88e383602bfedd0adde60649d31aeea12c` |
| `build/controller/controller.elf` | `f8d927776c9ca7d01e1915876421ee215b268fe800f44fc981a4d1fdc752bf0e` |

The firmware payload remains 2,976 bytes at `c01a0000`. The prior generation
candidate identity has not changed. Never select the older `worker_candidate`
updater by mistake. Build files remain ignored by Git. Preserve them or recreate
them using the original owner-supplied updater and existing preset/effects inputs.
No proprietary binaries are committed.

Machine-readable validation record: `build/controller/phase_validation_manifest.json`.
Its source hashes identify current files; the separate rebuild comparison is the
evidence linking the current firmware source to this artifact.

## Next work, in order

1. **Finish stack bounds.** The requested worker stack is 2048 bytes and the
   image enables `0xBE` fill. Known wait frames total 320 bytes including the
   stock worker. The located full interrupt path uses another 352 bytes plus
   alignment before switching stacks. Neither subtotal bounds deeper kernel
   calls, vector entry, scheduler work or all preemption paths. Trace those
   paths and the reset caller separately; establish interrupt-stack capacity.
   Do not equate `2048 - 672` with verified spare space.
2. **Finish USB lifecycle/context coverage.** Trace the event-8 producer's
   callers (`c0151f30` callback site, discriminator 132), all event 2/3/5 paths,
   the transitive effects of `c01522d8 -> c01520f4`, readiness aliases and
   downstream packet ownership. Audit reset post legality and the four-CC lock
   duration in every reachable context. Normal teardown deletes the worker,
   event, then lock but continues after deletion failures; prove external
   serialization before claiming handle lifetime safety.
3. **Rebuild if source changes.** Repackage a new candidate and record a new
   exact identity. Run both the full candidate verifier and stage checker.
4. **Prepare owner-run hardware test only after the offline gates close.**
   Present exact hashes and a bounded sequence: stock-mode baseline, controller
   entry, one control at a time with channel/CC/value logging, knob/expression
   sweeps, mixed-input load, reconnect replay and recovery checks. Physical labels
   remain unverified. Test reset-only behavior only through an established trigger;
   do not invent a host command for event 8. Flash approval is a separate step.
5. After a successful MIDI hardware milestone, integrate silence-only USB audio
   using `recon/20_usb_audio_proto.md` section 2.6, then proceed to processed audio
   tap and coexistence measurements as described in the Astra handoff.

## Verification commands

Run from `C:/Users/z/Documents/zoom project`. These commands are offline.

```powershell
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe tools/check_updater_stages.py build/controller/DO_NOT_FLASH_controller_generation_candidate.exe
.venv/Scripts/python.exe tools/verify_controller_candidate.py --firmware build/fw/res1_controller_generation_candidate.bin --updater build/controller/DO_NOT_FLASH_controller_generation_candidate.exe --elf build/controller/controller.elf --reference-updater 'C:/Users/z/Downloads/G1X FOUR_v2.00_Win_E/ZOOM G1X FOUR System v2.00 Updater.exe' --presets build/fw/cfupd_res85.bin --effects build/fw/cfupd_res88.bin --manifest build/controller/phase_validation_manifest.json --packet-audit build/controller/phase_validation_packets
```

The tracked verifier supersedes dependence on the ignored
`build/controller/verify_generation.py`. Its `--packet-audit` option generates
listings; inspect their decoded targets as well as the verifier's own target
checks. Full rebuild/package commands remain in
`docs/CONTROLLER_GENERATION_CANDIDATE_2026-10-13.md`.

## Workspace preservation

The pre-existing untracked `.agents/` and `bridge/` directories are preserved and
excluded from the validation commits. Recheck Git status on resume. The older
implementation handoff's working-tree description is historical.
