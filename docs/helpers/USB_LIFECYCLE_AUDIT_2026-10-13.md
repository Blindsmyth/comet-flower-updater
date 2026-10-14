# USB lifecycle audit — 2026-10-13

Status: in progress, offline only. Candidate remains DO_NOT_FLASH.

## Validation-phase follow-up

The generation fix is committed in `c72f789`. The current candidate passes
`tools/verify_controller_candidate.py`: all six hook targets match the ELF,
embedded firmware matches the loose image, all BIN resources match the official
template plus the three explicit inputs, and all eight stage-table rows match
the required six operations followed by two zero rows. This establishes artifact
identity and structure, not callback context or runtime lifecycle correctness.

Additional bounded instruction evidence:

- Registration `c0145154..5160` passes callback `c0144c0c` to `c0152410`.
  The latter stores it at `c011ac80` (`c0152436`). A producer at
  `c0151f30..1f40` loads that callback and invokes it with event **8** when its
  input discriminator is 132. This links one indirect producer to the reset-only
  branch. The discriminator's host meaning and all caller contexts remain open.
- `c0148a64` calls `c0148a50`, clears `c0116308`, then calls
  `c0148648(0)`. These leaf helpers clear `c0116300` and offsets +4/+8/+9
  from `c0116308`. There is no port-readiness write or indirect callback in this
  particular packetizer-reset subtree. This does not cover downstream ownership
  or the separate `c01522d8` subtree.
- Reset's first call `c01522d8` reads flags at `c011ac84` and may call
  `c01520f4(5, -1, c011ac80)` before taking the MIDI lock. Its transitive
  effects still need inspection; classifying it as a leaf would be incorrect.
- Normal teardown `c0149e80..9ef4` requests worker deletion first, event deletion
  second, and lock deletion third. Each handle is cleared only on its own
  successful deletion. Calls continue after an earlier deletion failure, so this
  sequence alone does not prove that callbacks cannot post a deleted event or
  that a failed worker deletion cannot overlap later cleanup. Trace teardown
  callers and external serialization before changing or approving the hook.

The stack follow-up is in [STACK_AUDIT_2026-10-13.md](STACK_AUDIT_2026-10-13.md).
Neither audit closes the hardware gate.

Follow-up: the [generation candidate](../CONTROLLER_GENERATION_CANDIDATE_2026-10-13.md)
now hooks the unlock boundary inside `c014a018` and serializes worker generation
observation, acceptance and sent-state commit. The findings below describe the
pre-fix source; lifecycle completeness and context gates remain open.

## Scope and evidence
Bounded trace of port readiness/pointer writers, transmit ring reset, and B14[89] lock participants against build/fw/map/main.dis. No source changes or device actions.

## Confirmed findings

### Shared ring lock (confirmed for traced direct participants)
The stock consumer c0149c14 takes B14[89] before ring count/read, retaining it through packetization and downstream submission, then releases it. The producer c0149de4 takes the same handle. Reset c014a018 takes it before clearing read/write indexes. Evidence:
```text
c0149c18 CALLP c014a094; c0149c20 LDW *B14[89],A4
c0149c2c CALLP c0149b20 ; ring count, c0117b28
c0149c52 CALLP c0149b38 ; byte consumer
c0149c5a CALLP c0149b60 ; packetizer
c0149c8c CALLP c01489a0 ; downstream submission
c0149c98 CALLP c014a1c8; c0149ca0 LDW *B14[89],A4
c0149df0 CALLP c014a094; c0149df4 LDW *B14[89],A4
c0149e20 CALLP c0149db0 ; append bytes
c0149e2c CALLP c014a1c8; c0149e30 LDW *B14[89],A4
c014a024 CALLP c014a094; c014a028 LDW *B14[89],A4
c014a038 CALLP c014a010 ; c0117b28 indexes zeroed
c014a048 CALLP c014a1c8; c014a04c LDW *B14[89],A4
```
The other worker drain c0149cac holds B14[89] around c0148a94/c0148a80 (c0149cec..c0149d08), releases it for c016a9c0, then reacquires it for c0148a50 (c0149d24..c0149d34). This is not a lock covering the entire worker lifecycle.

A literal B14[89] scan found 17 references, all c0149c20..c014a04c. Additional references concern handle create/store c0149f64/70, delete/cleanup c0149ecc, c0149f8c, c0149fb8, c0149fe4, and existence tests c0149f04. Literal enumeration does not exclude alias/computed handle references or all indirect consumers.

### Lifecycle flag, readiness, and reset-only dispatch (confirmed instructions)
PORT_STATE is c01152b8. Word [9] at c01152dc is demonstrably written as a Boolean flag, not an established port pointer. Existing descriptions calling it a pointer should be corrected. Callback c0144c0c dispatches event IDs 2..8 through c01843d8. The jump-table entries establish:

| Event | Branch | Visible state/reset action |
|---|---|---|
| 2 | c0144cc6 | Store supplied word into [7]; if zero, clear [9] then c014a058(0) |
| 3 | c0144c88 | If [9] nonzero, clear it then c014a058(0) |
| 4 | c0144d1a | Store supplied word at c01152d8 ([8]) |
| 5 | c0144c38 | Set [9]=1 then c0144ba0 and c014a058(1) |
| 6 | c0144d2c | Return |
| 7 | c0144d14 | Call c014be68 |
| 8 | c0144d0c | Call c014a018 ring reset directly |

Event names/host triggers are not assigned without tracing their producers. Evidence:
```text
c0144c14 SUB A1,2,A0; c0144c18 CMPLTU 6,A0,A0
c0144c24/c28 B0=c01843d8
c0144c2c SHL A1,2,A0; c0144c2e ADD A0,-8,A0
c0144c32 LDW *A5[0],A0; c0144c34 BNOP A0,5
c01843d8..c01843f0 .word c0144cc6,c0144c88,c0144d1a,c0144c38,c0144d2c,c0144d14,c0144d0c
c0144c46 MVK 1,A0; c0144c48 STW A0,*A4[0] ; A4=c01152dc
c0144c94 MVK 0,B0; c0144c96 STW B0,*A4[0]
c0144cda STW B0,*B4[9] ; B4=c01152b8, B0=0
c0144d0c CALLP c014a018 ; no readiness/[9] store in this branch
c014a06c [A0] BNOP c014a074,5
c014a070 CALLP c014a018 ; c014a058 resets only for zero argument
```
The event-8 branch is a stronger offline concern than polling frequency alone: the ring can be cleared without that branch itself making port_ready() false. Calls inside reset (c01522d8 and c0148a64) still require their full side-effect audit before claiming neither ever changes port state. There is no explicit controller tx sent-state invalidation anywhere in this unmodified stock branch.

Additional confirmed readiness writers: c0144e60..c0144e78 clear [9], [1], and [3]; initialization c0145144..c014514c zeroes all 40 bytes at c01152b8. Endpoint-discovery loops set words through computed indexes: c0145028 SUBAW B6,4,B0 (B6=c01152cc), c014502c ADDAD B0,B1,B5, c0145030 STW 1,*B5[0]; c01450a4 SUBAW B6,3,B0 (B6=c01152d0), c01450a8 ADDAD B0,B1,B5, c01450ac STW 1,*B5[0]. The second loop begins at c01152c4 ([3]); the first begins at [1] and strides eight bytes. These writes are not visibly surrounded by B14[89] acquisition. Enumerating loop bounds and all aliases remains a gate.

### Observation gap (confirmed source limitation; firmware schedule remains open)
controller.c port_ready() samples [3]==1 and [9]!=0. tx.connected is cleared only when the worker samples false, and append_cc() uses the same Boolean test. A 1->0->1 flag cycle entirely between checks is indistinguishable from no transition. Holding B14[89] protects ring append against the traced drain/reset participants, but does not itself supply a generation token or force a worker observation between the lifecycle writes above. No schedule proof found here excludes that interleaving. This is a source-level counterexample, not an observed pedal failure.

## Open completeness gates
- Trace event producer meanings and task/priorities for callback events 2, 3, 5, 8; prove actual possible ordering against the MIDI worker or implement explicit invalidation.
- Audit reset callees c01522d8/c0148a64 and all computed/aliased port/ring writes, plus callbacks reachable while holding B14[89]. A literal reference scan cannot establish completeness or deadlock freedom.
- Close lock-handle initialization/destruction concurrency, packetizer downstream ownership, and task/scheduler interactions. Only the named direct consumers are confirmed to share the lock.
- Validate any remedy in actual compiled instructions and exact packaged image, then owner-run USB tests. No source, image, or hardware validation was performed by this audit.

## Minimal next remedy proposal (not implemented)
Add an explicit controller transport generation invalidation at an audited common ring-reset/lifecycle boundary, with generation comparison and replay invalidation in the worker. c014a018 is a concrete reset entry to investigate because it covers the reset-only dispatch and c014a058(0) path. It is not yet proven sufficient for every lifecycle transition. Serialize generation and ring acceptance using the established lock where its call context permits; do not infer this automatically protects lock-free readiness writers. Check generation before committing sent-state so a reset after append cannot leave a message marked sent after it has been discarded. Discard obsolete button edges and replay current desired state when the generation changes. A shorter timeout alone cannot close either unobserved transitions or reset-only invalidation.
