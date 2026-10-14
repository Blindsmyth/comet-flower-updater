# Controller generation candidate — 2026-10-13

Superseded for further review by the
[lifecycle candidate](CONTROLLER_LIFECYCLE_CANDIDATE_2026-10-13.md). This is a
historical six-hook build record; its commands require the historical source and
tool versions. The current verifier requires seven hooks.

**DO_NOT_FLASH. Offline candidate only; no hardware approval or device actions.**
This supersedes the October 12 candidate for further review. Its old executable
and loose firmware were preserved under their existing names.

## Change and scope

The sixth hook redirects the 32-bit CALLP at `c014a048` (AIS offset `0x3dfc4`)
from `c014a1c8` to `controller_reset_unlock`. This is the unlock boundary
inside stock reset `c014a018`, after its ring/packetizer reset. In controller
mode it increments a 32-bit generation while still holding B14[89], calls the
original unlock, then posts worker bit 0. It preserves the unlock return.
Mode off calls the original unlock without generation changes or event posts.

The worker takes B14[89] after its event wait. Under that lock, a generation
mismatch or newly observed connection discards queued transient edges and
invalidates sent-state, then replays current desired values. It retains the
lock through a bounded batch of at most four CCs and their sent-state commits.
A reset cannot interleave between acceptance and commit through this lock.
A reset after release increments the generation and wakes another replay.
The worker posts another wake after a full four-message batch, so replay does
not depend solely on 100-tick polling. A full ring leaves values pending.
This requests prompt replay; it does not promise synchronous host delivery.

This covers the audited reset-only event 8 and `c014a058(0)` paths through
`c014a018`. It does not prove every lifecycle transition or aliased ring write
passes this boundary. Readiness writers are still not all serialized by this
lock. Lock-handle destruction, downstream ownership, and full callback context
remain the limitations documented in the USB lifecycle audit. The longer
four-CC lock interval and added reset wake need scheduling/timing review.
Generation comparison assumes fewer than 2^32 resets between observations.

## Exact artifacts

| Artifact | SHA-256 |
|---|---|
| `build/fw/res1_controller_generation_candidate.bin` | `a7e4a13719d77af0c0d456c3dd5d5e9d7ee22fa0e3d1004664936127bfbe7593` |
| `build/controller/DO_NOT_FLASH_controller_generation_candidate.exe` | `ac7030c6707343608ae3f20f31f2db88e383602bfedd0adde60649d31aeea12c` |

TI C6000 8.5.0.LTS compiled with `--silicon_version=6740`, EABI, C99 and O2.
The payload is 2,976 bytes at `c01a0000..c01a0b9f`, inside the 16 KiB reservation.
The AIS firmware is 496,400 bytes. It uses the existing const-edited
`build/fw/res1_cfupd.bin` base, preserving artwork/text.

| Stock call site | Compiled target |
|---|---|
| `c0134e14` | `controller_start`, `c01a0654` |
| `c0134df0` | `controller_dispatch`, `c01a0b40` |
| `c015ffd0`, `c01600b0` | `controller_analog`, `c01a0980` |
| `c0149d4c` | `controller_worker_wait`, `c01a0144` |
| `c014a048` | `controller_reset_unlock`, `c01a070c` |

## Verification

- Full Python suite: **91 passed, 2 subtests passed**. Three new policy-model
  regressions cover ready-through-reset with stale edges, reset after accepted
  state, and full-ring replay with generation wrap. These do not execute TI
  firmware or establish host behavior.
- The builder verifies stock words, hook-only code edits, AIS placement,
  payload bytes and each target against the current linked ELF.
- Resource `0x81` read back from the new executable equals the firmware file.
  All other BIN resources equal the old candidate, including the 38-file
  effects image and presets. Resource `0x85` SHA-256 is
  `e6a8187b9effb15da9b75fdc1c3daea60bed650b86d2317fd2a2c6f1bcd00be8`;
  `0x88` is `e539e19f1443b90d9b1b03b4f65e438462cecb08d33a926199bdbded8e588e9c`.
- All six stages pass `tools/check_updater_stages.py`. Additional checks
  compare the exact six-row table and bound the full write-resource sizes
  within their allowed regions. Boot/update and settings regions are excluded.
- Negative checks restoring any one of the six hooks to its stock word are
  rejected by `validate_controller_fw`.
- Build-local verification and source/resource hashes are saved in
  `build/controller/verify_generation.py` and `generation_manifest.json`.
  Packet extracts for TI disassembly are under `generation_packet_audit/`.

## Compiled ABI and remaining stack gate

`controller_reset_unlock` at `c01a070c` receives the original lock in A4.
The generation store at `c01a075c` executes in the delayed-call sequence before
the original release at `c014a1c8`; `c01a0760..76c` then calls the event post.
The release return is saved in A11 and restored to A4 at `c01a0778`.
Its SP decrement is **24 bytes** (three 8-byte steps), restored by both
epilogues, matching the compiler's reported save area.

The worker prologue still decrements SP by **72 bytes**: two 8-byte steps,
four 8-byte pair steps, and one 24-byte step. Mode-off, not-ready and normal
epilogues restore those steps. The wait output is prezeroed at `c01a01c0`,
timeout 100 goes into A8 at `c01a01c8`, and the stock wait result is retained
in A15 at `c01a01d4`. Successful lock acquisition precedes generation reads
at `c01a0270/274`; batch release occurs at `c01a05d8` before the optional wake.

The known partial worker wait depth remains **312 bytes** below wrapper entry
(72 + 56 + 184), or **320 bytes** including the stock worker's 8-byte frame.
The [stack follow-up](helpers/STACK_AUDIT_2026-10-13.md) now traces the 2048-byte
stack request through task creation and allocation, identifies the `0xBE` fill
mechanism and 48-byte context-switch frame, and locates an interrupt stack
switch. The interrupt path uses 352 bytes plus alignment on the interrupted
stack before switching. These are partial costs, not worst-case headroom.
Deeper kernel calls, vector/nesting coverage and the reset caller's separate
stack remain open. No safe margin or hardware readiness is established.

## Rebuild

```powershell
.venv/Scripts/python.exe tools/make_controller_fw.py --base build/fw/res1_cfupd.bin --out build/fw/res1_controller_generation_candidate.bin
.venv/Scripts/python.exe tools/make_fs_restore_updater.py 'C:/Users/z/Downloads/G1X FOUR_v2.00_Win_E/ZOOM G1X FOUR System v2.00 Updater.exe' build/controller/DO_NOT_FLASH_controller_generation_candidate.exe --controller-fw build/fw/res1_controller_generation_candidate.bin --presets build/fw/cfupd_res85.bin --image build/fw/cfupd_res88.bin
.venv/Scripts/python.exe tools/check_updater_stages.py build/controller/DO_NOT_FLASH_controller_generation_candidate.exe
.venv/Scripts/python.exe tools/verify_controller_candidate.py --firmware build/fw/res1_controller_generation_candidate.bin --updater build/controller/DO_NOT_FLASH_controller_generation_candidate.exe --elf build/controller/controller.elf --reference-updater 'C:/Users/z/Downloads/G1X FOUR_v2.00_Win_E/ZOOM G1X FOUR System v2.00 Updater.exe' --presets build/fw/cfupd_res85.bin --effects build/fw/cfupd_res88.bin --manifest build/controller/phase_validation_manifest.json
.venv/Scripts/python.exe -m pytest -q
```

A hardware test proposal remains deferred until stack and lifecycle/context
gates are closed. Then the owner can review the exact hashes and a bounded
input/reconnect/reset test plan before separately authorizing flashing.
