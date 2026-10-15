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

Details and next instruction-level work:
[STACK_CONTINUATION_2026-10-14.md](docs/helpers/STACK_CONTINUATION_2026-10-14.md),
[USB_TEARDOWN_DECISION_2026-10-14.md](docs/helpers/USB_TEARDOWN_DECISION_2026-10-14.md),
[USB_TEARDOWN_PATCH_SITES_2026-10-14.md](docs/helpers/USB_TEARDOWN_PATCH_SITES_2026-10-14.md),
[OWNER_DIAG_TEST_PREP_2026-10-15.md](docs/helpers/OWNER_DIAG_TEST_PREP_2026-10-15.md).
The former **1,784-byte ceiling is withdrawn**; there is no verified worker
stack margin. No firmware was flashed or updater executed.
The original untracked `.agents/` and `bridge/` directories were preserved.

## Continue from this point

1. Continue from the 60 reviewed physical extents. Resolve remaining indirect
   targets and model live save-helper frames and context transitions. No cycles
   in an incomplete ordinary-call graph does not establish a worker-stack bound.
2. Complete USB downstream ownership, readiness aliases and lock/handle
   lifecycle review using the current lifecycle candidate. Poll/lock timing
   remains unmeasured. Prioritize teardown descriptor association, Hwi exclusion
   or safe coexistence, and poll-expiry ownership using the abort follow-up.
3. For hardware runtime diagnosis, prepare a bounded owner-run procedure using
   the diagnostic candidate (`--diag-teardown`) and `tools/decode_ctl_diag.py`
   to capture `ctl_diag` state upon disconnect/reconnect events. Keep the
   distinction between this observer-only diagnostic and an ownership fix explicit.
4. If firmware changes become necessary, rebuild and package a new named
   candidate, then verify its exact identity and updater stages.
5. Prepare a bounded owner-run MIDI test after the offline gates close;
   flashing remains a separate owner decision. Then proceed to USB audio.

Current candidate identity and complete verifier commands:
[CONTROLLER_LIFECYCLE_CANDIDATE_2026-10-13.md](docs/CONTROLLER_LIFECYCLE_CANDIDATE_2026-10-13.md).
**DO_NOT_FLASH remains in effect.**

