# Lead continuation — 2026-10-14

Start here for the latest continuation. The priority remains processed USB
audio to the host alongside MIDI control. The next milestone is still the
controller's offline stack and USB lifecycle review, before an owner-run MIDI
test and subsequent silence-only USB audio integration.

## Latest pickup and commit review

Picked up at `3a16797`; reviewed that commit and `7e5cd86`. Integrated the
pending kernel extent, execution-context and USB lifecycle notes, keeping
their unresolved semantic conditions explicit. Fixed a further analyzer gap:
explicit stack-pointer replacement/alignment now blocks graph subtotals,
and constant ADD decrements are counted. Added seventeen regressions across
this pickup and its continuation. Evidence loading now requires instruction
anchors at both extent boundaries and verifies unresolved-record anchors;
`--elf` additionally checks the image identities recorded by all evidence.

The reviewed switch-owner extent `c01520f4..c0152240` reveals USB command
handlers previously missed by the catalog split. The send-root inventory
expands from six to 130 entries; its dispatch, helper frames and downstream
ownership remain unresolved. The recovered extent/context evidence removes
the false idle/scheduler cycle. The next pass removes another false cycle
caused by merging `c0164380` with `c01644c0`, and separates `c0166780` from
the next wrapper. The four current graphs have no DFS cycles; unresolved
callbacks, live helper frames and stack/context transitions still block bounds.

**148 tests and two subtests pass.** Exact candidate identity, seven hooks,
embedded resources, eight stage rows and all six stage operations reverified.
No firmware was changed or updater executed. Original `.agents/`
and `bridge/` content remains untouched. The stack and USB lifecycle gates
remain open and **DO_NOT_FLASH still applies**.

Fresh report: `build/controller/stack_review_2026-10-14.json`. Commands,
counts and remaining work are in the
[stack continuation](docs/helpers/STACK_CONTINUATION_2026-10-14.md).
The [USB continuation](docs/helpers/USB_LIFECYCLE_CONTINUATION_2026-10-14.md)
narrows normal synchronous buffer ownership but leaves abort poll-expiry,
teardown failures, readiness aliases and timing open.
The [abort follow-up](docs/helpers/USB_ABORT_OWNERSHIP_2026-10-14.md)
identifies shared TX teardown queue 25, the poll's PEND0 mask and descriptor
recycling. Association of a queue entry with the requested endpoint, Hwi
coexistence and the expiry recovery path still need proof.

## Reviewed committed work

At the preceding pickup, HEAD was `76fee2c`. Recent commits fix MIDI monitor reconnect/channel
behavior, add controller replay after resets, remove producer event-handle
lifetime races, invalidate recreated workers, and add offline artifact checks.
The stack follow-ups (`0523215`, `ccbe1c5`, `76fee2c`) correctly leave the gates
open, but their numerical stack ceiling and some callback classifications are
superseded by this continuation.

## Work completed

- Reverified the current lifecycle candidate: all seven hooks, payload,
  embedded resources and eight stage-table rows pass. The separate six-stage
  checker also passes. Artifact hashes match the lifecycle build record.
  New local manifest: `build/controller/lead_validation_2026-10-14.json`.
- Corrected the stack analyzer so unknown calls/cycles do not produce a finite
  bound, callback observations apply per site, helper frames are flagged,
  unknown extents are not scanned, and each root has independent state.
  Added input-hashed JSON reports and disassembly-pinned callback observations.
- Traced the `c0150bf8` and formatter callback slots, three registration
  arguments for `c0183aec`, and the separate ready/switch hook fields.
- Verified worker wait tail-call thunk (`c0149d4c` CALLP `c014a0cc`), preserving
  worker SP across `EVENT_WAIT` and tail-calling `controller_worker_pump`.
- Decoded USB abort drain loop (`c0120734..0762`, queue 25) and deferred queue
  32..35 consumer (`c01219f4` / `c0121a04..1a38`); detailed in
  `docs/helpers/USB_TEARDOWN_PATCH_SITES_2026-10-14.md`.
- Implemented offline USB teardown diagnostic candidate (`--diag-teardown`), adding
  dual observer hooks at `c0120744` (site 1, abort drain) and `c0121a18` (site 2,
  queue 32..35 consumer), recording pops, recycles, timestamps, and sticky fault
  flags into a 24-entry ring (`ctl_diag`, 408 B in `.ctl_state`) guarded by `DINT`/`RINT`.
  Lifecycle candidate remains byte-identical (`3e7f5236...28b9`).
- Created offline host decoder `tools/decode_ctl_diag.py` to inspect memory dumps
  containing `ctl_diag` (JSON and formatted table modes).
- Full suite: **168 passed, 471 subtests passed**.
- 2026-10-15: TX template writer review
  ([USB_TX_TEMPLATE_WRITERS_2026-10-15.md](docs/helpers/USB_TX_TEMPLATE_WRITERS_2026-10-15.md)).
  The table at `c01805c4` has six references, all reads, and no instruction-level
  writer. The abort tail at `c0120778` drains template word [0], the submit
  queue (22 for MIDI IN), not runtime state. Pinned by
  `tests/test_tx_template_writers.py`. 
- 2026-10-15: Hwi coexistence
  ([USB_HWI_COEXISTENCE_2026-10-15.md](docs/helpers/USB_HWI_COEXISTENCE_2026-10-15.md)).
  The Hwi `c011fc8c` drains queue 25 unconditionally and forwards teardown
  descriptors via q32 to `c01219f4`, which recycles them to q28. The abort drain
  recycles to q28 too, and an empty pop exits safely. Each descriptor has one
  owner whether or not preemption occurs. Poll expiry is therefore not evidence
  of hardware failure. Still open: endpoint association (shared q25) and the
  entry interrupt state.
- 2026-10-15: q25 association
  ([USB_Q25_ASSOCIATION_2026-10-15.md](docs/helpers/USB_Q25_ASSOCIATION_2026-10-15.md)).
  Only `c0120650` (N=1..4) feeds q25; RX teardowns use q27. All identified
  abort callers dispatch from the `c0138370` task (`c01383ea`), so aborts are
  sequential. Mis-association requires a prior expired poll. The diag's
  FAULT_CHANNEL_MISMATCH would detect it.
- 2026-10-15: entry IRQ state is likely GIE=1
  ([USB_ABORT_ENTRY_IRQ_2026-10-15.md](docs/helpers/USB_ABORT_ENTRY_IRQ_2026-10-15.md)).
  Obligation 4: Sol report plus Claude review
  ([SOL_EXPIRY_RECOVERY_REPORT.md](docs/helpers/SOL_EXPIRY_RECOVERY_REPORT.md)).
  No premature buffer reuse via the enqueue (it defers while field [5] != 0).
  Liveness risk: a never-returned descriptor stalls that slot's TX permanently.
  Direct submitters `c0120c00`/`c01219d0` are untraced. Suite: **178 passed, 579 subtests**.

Details and next instruction-level work:
[STACK_CONTINUATION_2026-10-14.md](docs/helpers/STACK_CONTINUATION_2026-10-14.md),
[USB_TEARDOWN_DECISION_2026-10-14.md](docs/helpers/USB_TEARDOWN_DECISION_2026-10-14.md),
[USB_TEARDOWN_PATCH_SITES_2026-10-14.md](docs/helpers/USB_TEARDOWN_PATCH_SITES_2026-10-14.md),
[OWNER_DIAG_TEST_PREP_2026-10-15.md](docs/helpers/OWNER_DIAG_TEST_PREP_2026-10-15.md).
The former **1,784-byte ceiling is withdrawn**; there is no verified worker
stack margin. No firmware was flashed or updater executed.
The original untracked `.agents/` and `bridge/` directories were preserved.

## Continue from this point

**State at 2026-10-15 (Claude, with Sol and Gemini helpers).** The four USB abort
obligations in `docs/helpers/USB_ABORT_OWNERSHIP_2026-10-14.md`:

| # | Status | Doc |
|---|---|---|
| 1 template writers | narrowed: no instruction writer | USB_TX_TEMPLATE_WRITERS_2026-10-15 |
| 2 Hwi coexistence | ownership resolved (single owner); entry state likely GIE=1 | USB_HWI_COEXISTENCE / USB_ABORT_ENTRY_IRQ |
| 3 q25 association | narrowed: needs a prior expired poll; diag detects it (0x2) | USB_Q25_ASSOCIATION |
| 4 expiry recovery | counted mode: no premature reuse; **liveness risk**: stuck [5] stalls the slot | SOL_EXPIRY_RECOVERY_REPORT (Claude review) |

Ring mode (TX field [2] != 0) is dormant in stock: [2] is only ever written 0
(SOL_TX_MODE_REPORT review), so its double-chain risk is moot. Its kick/case-D
machinery is a candidate base for USB-audio ISO IN. Association assumptions are
closed: a single UsbTask (GEMINI_TASK_INSTANCES_REPORT), and op 8 = host
CLEAR_FEATURE(HALT) on EP 0x84 (GEMINI_OP8_REPORT). The diag readback also
reports the measured worker-stack high-water mark. The diag build now has a MIDI
readback (both footswitches), so the owner test in
OWNER_DIAG_TEST_PREP_2026-10-15 can produce data.

1. Stack gate, unchanged: continue from the 60 reviewed physical extents.
   Resolve the indirect targets, then model the save-helper frames and context
   transitions. A graph without cycles is not a bound.
2. USB audio: an offline silence-stream candidate builds
   (docs/USB_AUDIO_SILENCE_CANDIDATE_2026-10-15.md). Pending: the Sonnet review
   (docs/helpers/REVIEW_USB_AUDIO_CANDIDATE.md) and Gemini's UAC1 validator
   (tools/uac1_validate.py). Slot mapping: endpoint N = slot N (recon/23). PIO is the
   first design. Ring mode is dormant in stock (SOL_TX_MODE_REPORT review), an
   option for later. Op 8 = host CLEAR_FEATURE(HALT) on EP 0x84 (GEMINI_OP8_REPORT).
3. Decide whether the counted-mode liveness risk needs a fix candidate, or
   first an owner diag run to see whether it happens (recommended: run the
   diag first).
4. Then: the owner-run MIDI test (owner's decision), then USB audio.

Current candidate identity and complete verifier commands:
[CONTROLLER_LIFECYCLE_CANDIDATE_2026-10-13.md](docs/CONTROLLER_LIFECYCLE_CANDIDATE_2026-10-13.md).
**DO_NOT_FLASH remains in effect.**

