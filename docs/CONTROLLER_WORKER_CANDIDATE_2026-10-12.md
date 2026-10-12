# Controller worker candidate: offline build and remaining gates

This record identifies a **DO_NOT_FLASH** candidate. It was compiled and
packaged offline on 2026-10-12. No pedal or USB host test was performed. The
earlier `Comet Flower ZG1X4 Controller TEST Updater.exe` remains intact.

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
  the stock worker drains the ring. Stock `c014a0cc` writes `-50` to the
  output word on timeout; the wrapper now replaces that negative value with
  `1` after an append, while preserving positive event bits.
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

1. Finish the worker wrapper's runtime ABI proof: timeout output `-50` is
   traced at `c014a102..c014a10e`, and the compiled wrapper's signed check
   is visible at `c01a058c..c01a0598`. Confirm the return behavior, stack use
   and worst-case scheduling cost. The patched call packet itself has been
   independently disassembled, as described above.
2. Trace every writer to the port-ready fields and ring during USB
   disconnect/reset/reconnect. Confirm that a ready port with a stale ring
   cannot interleave an old partial MIDI message with a new CC, and that
   `c014a240` is bounded and valid from the AD task. Audit the complete
   B14[89] lock graph, including packetizer callbacks.
3. Establish the timeout unit and bound the retry latency and
   CPU cost. Check the compiled publication/consumption order under task
   preemption, and test the real worker against ring-full, overflow, reset,
   concurrent expression and failed-wake schedules.
4. After those proofs, rebuild under a new hash, revalidate resources/stages,
   then observe normal-mode boot and one controller input at a time on the
   pedal. Do not promote this candidate based on offline success alone.

Further trace: `c0144e6c..c0144e78` clears port pointer `[9]` and ready
field `[3]` before later USB cleanup calls. `c014a018..c014a04c` clears the
MIDI ring while holding B14[89]. These observations do not yet establish
all callback ordering or exclude a port-state race with `append_cc`.
