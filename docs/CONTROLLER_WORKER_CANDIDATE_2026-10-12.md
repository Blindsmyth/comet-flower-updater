# Controller worker candidate: offline build and remaining gates

The newer [generation candidate](CONTROLLER_GENERATION_CANDIDATE_2026-10-13.md)
implements reset invalidation and has a separately verified updater identity.
It also remains DO_NOT_FLASH. This document preserves the older build record.

This record identifies a **DO_NOT_FLASH** candidate. It was compiled and
packaged offline on 2026-10-12. No pedal or USB host test was performed. The
earlier `Comet Flower ZG1X4 Controller TEST Updater.exe` remains intact.

## Recheck on 2026-10-13

The packaged executable still hashes to `91b9894e30946bd6205a1dab699e5900f1b9834ae6c513fad60c7fae4ff7644a`;
its resource 0x81 still hashes to `0ecddd890ed7925471a00a749a11ccc3b8eda9c2b646ef1795bcaa81bcfc89e2`.
The loose `build/fw/res1_controller_worker_candidate.bin` now hashes to
`f1478153ed179d167a799ba4f94aedd3a1a4550f20ab771cfc38bc84b9d4c021`.
They have equal lengths (496,080 bytes), but differ at 180 byte positions.
In particular, the loose image redirects the second AD call at `c01600b0`
to `c01a0860`; the packaged image retains stock target `c014aef4` there.
The other four listed hook targets agree. The table below records the
original build, not the current loose file. These artifacts are not interchangeable.
All six packaged stage-table entries pass the offline stage checker again;
that check does not establish runtime correctness or approve flashing.

The timeout interpretation below has been corrected by the delayed-branch
audit in `docs/helpers/WORKER_ABI_AUDIT_2026-10-13.md`.

## Changes from the earlier controller

- MainApp and AD publish aligned 32-bit button, knob and expression records
  and request the stock MIDI-worker event. No producer calls the blocking
  stock MIDI send. The earlier MainApp housekeeping hook is removed, so the
  stock housekeeping call executes directly again.
- The worker hook redirects `c0149d4c CALLP c014a0cc` to
  `controller_worker_wait` at `c01a01a0`. It calls the stock wait once,
  retaining its argument and return contract, with timeout argument 100 in
  controller mode. The finite wait revisits pending state after a missed wake
  or reconnect. It sets output bit 0 only after appending a complete CC so
  the stock worker drains the ring. Stock `c014a0cc` returns `-50` on its
  timeout path and leaves the output word unchanged. The wrapper prezeros
  that word and sets bit 0 after an append, preserving positive event bits;
  its negative-output normalization is defensive.
- The worker holds the stock inner ring lock B14[89] around a free-space
  check and three calls to stock byte append `c0149d74`. It rolls back the
  write index if an append unexpectedly fails before releasing the lock.
  Each activation offers at most four CCs. A packed version remains pending
  when a concurrent expression value supersedes a sent snapshot. Overflowed
  button edges are repaired toward the latest absolute button state.
- The worker checks `c01152b8[3] == 1` and a nonzero port pointer at
  `c01152b8[9]`. On an observed disconnect/reconnect, it discards old
  transient edges and replays absolute button/knob/expression state. These
  checks match the traced stock send preconditions, but the complete USB
  lifecycle and reset ordering are **not yet proved**.

## Artifact identity and offline checks

| Artifact | SHA-256 |
|---|---|
| Existing Controller TEST updater, unchanged | `469b1e3e383fe8473bb09f71e84a3e1cfe0fa447eabf780be37ec45c383b2e47` |
| `build/fw/res1_controller_worker_candidate.bin` | `0ecddd890ed7925471a00a749a11ccc3b8eda9c2b646ef1795bcaa81bcfc89e2` |
| `build/controller/DO_NOT_FLASH_controller_worker_candidate.exe` | `91b9894e30946bd6205a1dab699e5900f1b9834ae6c513fad60c7fae4ff7644a` |

The linked payload occupies `c01a0000..c01a0a5f` (2,656 bytes inside the
reserved 16 KiB region). The new firmware has four decoded CALLP targets;
the worker hook word changes from `0x10007193` to `0x10ac8c13`, preserving
the execute-packet/parallel bits. An independent 32-byte packet extract was
assembled at `c0149d40` and disassembled by TI `dis6x`: it shows
`CALLP.S2 c01a01a0,B3` at `c0149d4c` parallel with `ADD 4,B15,B6` and
`MVK 1,A6`, while the neighboring stock instructions and `.fphead` agree.
The call site supplies A4 from B14[90], B4=3, A6=1, B6=B15+4 and A8=-1.
`validate_controller_fw` accepts the AIS
walk, original stock words, const-data edits, hook-only stock-byte changes,
and payload placement. The linked disassembly shows the stock wait call,
the inner-lock acquire/release, the three raw-byte append calls, and no
MainApp send call. The packager read back resource 0x81 after growing it.

Resources 0x85 (presets/splash) and 0x88 (38-file effects image) have the
same SHA-256 values as the existing Controller TEST updater:
`e6a8187b9effb15da9b75fdc1c3daea60bed650b86d2317fd2a2c6f1bcd00be8`
and `e539e19f1443b90d9b1b03b4f65e438462cecb08d33a926199bdbded8e588e9c`.
Resource 0x81 is byte-identical to the new firmware file. The stage checker
reports all six stages `ok`: presets at `0x28000`, effects FS at `0x102000`,
and main firmware at `0x33000`. No stage touches boot/update or settings.
The eight existing controller transport model tests pass; they model policy,
not the compiled worker or host delivery.

## Required before a pedal test

1. Runtime ABI proof & timeout behavior (**audited 2026-10-13** in
   `docs/helpers/WORKER_ABI_AUDIT_2026-10-13.md`): timeout return `-50` is
   confirmed via delayed branch at `c014a106` (store at `c014a10e` skipped,
   output word left untouched). Wrapper stack layout balances 72 bytes
   (known partial call depth 312 bytes). Timeout 100 is established as 100
   TI SYS/BIOS Clock ticks (~100 ms). Task stack headroom beyond 312 bytes
   remains an open audit item.
2. Trace every writer to the port-ready fields and ring during USB
   disconnect/reset/reconnect (**audited 2026-10-13** in
   `docs/helpers/USB_LIFECYCLE_AUDIT_2026-10-13.md`): B14[89] lock participants
   and event 2..8 dispatch table traced; confirmed observation gap for
   unobserved disconnect/reconnect or event-8 reset between 100 ms worker wakes.
   Requires generation invalidation token or reset hook (`c014a018`).
3. Rebuild under a new candidate identity to include the second AD channel hook
   (`c01600b0 -> c01a0860`), revalidate resources/stages, and verify SHA-256
   hashes before any pedal test.

Further trace: `c0144e6c..c0144e78` clears port pointer `[9]` and ready
field `[3]` before later USB cleanup calls. `c014a018..c014a04c` clears the
MIDI ring while holding B14[89]. These observations do not yet establish
all callback ordering or exclude a port-state race with `append_cc`.
