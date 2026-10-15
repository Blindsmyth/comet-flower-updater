# USB lifecycle continuation — 2026-10-14

Offline instruction review of the seven-hook lifecycle candidate. **DO_NOT_FLASH
remains in effect.** No firmware/tool changes, updater execution, device operation,
or runtime measurements were performed. This report narrows specific ownership
and event-dispatch gaps; it does not close the complete USB lifecycle gate.

Inputs: `build/fw/map/main.dis` (SHA-256
`e824b1e0effdaaca35cf87bd3a0bcc9b6242291e4def5e471120b28a762c82d1`),
`build/fw/res1_493412.bin` (SHA-256
`43060686fce75e175a217194ab1be3aeffe0be7d59f9d3df4181d41b9d3cc5a7`),
and the controller source. The stock addresses below come from `main.dis`;
they are not a fresh independent disassembly of the packaged candidate. Candidate
identity is recorded in [the build record](../CONTROLLER_LIFECYCLE_CANDIDATE_2026-10-13.md).
The seven candidate hook sites do not alter the downstream routines described here.

## 1. Packetization and physical transmission are separate

`c01489a0` is the MIDI-byte packetizer, not the physical submitter. Its table
`c0181138` dispatches by the per-cable parser state in `c0116308 + 12*cable`.
The instruction loop at `c01489ec..c0148a3a` advances the input pointer and
remaining byte count by the count returned in the stack result word. The parser
helpers accumulate one USB-MIDI packet and call `c0148668 -> c0148600`.

The latter copies an actual four-byte word into `c0115300[count]` at `c0148634`
and increments the halfword count at `c0116300` at `c0148640`. It rejects a count
above 1023 (`c0148610..8618`); the successful maximum becomes 1024 packets,
4096 bytes. The packet storage ends at `c01162ff`, immediately before the count.
`c0148a80` returns that count times four (`EXTU A0,18,16` at `c0148a8c`), and
`c0148a94` returns `c0115300`. Thus the source buffer `c0117318` used by the
byte-ring drain is copied into distinct static packet storage before the drain
releases B14[89]. No DMA ownership of `c0117318` is established by this path.

The next worker phase, `c0149ce8`, snapshots packet pointer and byte count while
holding B14[89], releases the lock at `c0149d04`, then invokes:

```text
c0149d10 CALLP c016a9c0
c0149d14 A4 = c0115300
c0149d16 B4 = packet_count * 4
c0149d18 A6 = -1
```

After nonnegative return it takes B14[89] again and clears the packet count
through `c0148a50` (`c0149d24..34`). Negative return skips that clearing at
`c0149d22`, retaining the packet count for a later worker iteration. Therefore
ring acceptance, parser copy, lower-layer submission and host delivery are
separate milestones. Controller `sent` records ring acceptance only.

## 2. Normal send uses a synchronous completion semaphore

The argument trace is:

| Edge | Instruction evidence | Live values |
|---|---|---|
| `c016a9c0 -> c0152240` | `c016a9c8..d4` | temporary `{count, pointer}` record, B4=-1 |
| `c0152240 -> c01520f4` | `c0152284..22a6` | command 3, B4=-1, A6=`c011ac80`; pointer/count stored at +32/+36 |
| command 3 -> `c015af48` | table word `c0184488=c0152176`, `c0152180..2190` | endpoint at +12, pointer/count from +32/+36, B6=1; A8 retains -1 |
| `c015af48 -> c01387f0` | `c015af78..af90` | command 4; stack record +28 (word 7) receives A8=-1, +32/+36 receive callback/context |

`c01387f0` copies the 40-byte transfer record into the endpoint record
`c011a4e8 + 52*slot` at `c01388d4..88f0`, retaining the caller's data pointer.
It does **not** copy the entire packet payload. Because record word 7 is -1,
the `-2` asynchronous branch at `c01388f4..8900` is not selected. It captures
the caller task identity (`c0138880..8894`), stores that identity in endpoint
word 2 and prepares its semaphore (`c0138904..8910`). The transfer command is
queued at `c0138914`. It then calls `c014a120(-1)` at `c0138940` and waits.

`c014a120` reads the current task from `c01820ec` via `c016e920`, gets its
word-13 semaphore via `c016e900`, and passes the original -1 timeout to
`c0150b20` (`c014a140..144`). There is no finite controller poll timeout on this
lower-layer wait. A normal successful release returns the endpoint result and
remaining count (`c013898c..89ac`), clearing endpoint word 2 to -1 and word 1 to
zero before return.

The endpoint completion/abort helper `c0138400` distinguishes synchronous and
asynchronous requests using endpoint word 10. For the synchronous case, it
stores the completion result to endpoint word 9 then calls `c014a080(task)`
(`c0138416..8428`); the asynchronous callback branch is at `c0138450` or
`c0138494`. The stock MIDI worker's normal send therefore relies on the task
semaphore release, rather than the asynchronous callback's caller-owned buffer
lifetime.

**Bounded conclusion:** on this traced normal return path, the worker does not
refill/reuse `c0115300` until the synchronous submission returns. This addresses
the specific concern that normal `c016a9c0` immediately returns after handing
DMA a temporary parser buffer. It does not prove that every semaphore release
corresponds to DMA relinquishing the buffer, that every task identity remains
valid across deletion, or that the wait always progresses under traffic.

## 3. Reset reaches endpoint abort and descriptor teardown

`c01522d8` tests the open/transfer bits at `c011ac84`, then dispatches command 5
with A6=`c011ac80` and B4=-1 (`c01522f2..22fa`). The pinned tables resolve:

```text
c0184490 = c015215a       ; c01520f4 command 5
c0152160 -> c015b128     ; endpoint from c011ac80[3]
c015b138 -> c01387f0(5)
c0180d54 = c0138070      ; c01387f0 command 5
```

Commands 5/6 bypass the USB worker mailbox and use the direct table branch at
`c0138a40..58`. `c0138070` aborts one endpoint, or visits six endpoint records
if its argument is -1. `c0137fe4` calls `c01229e8(endpoint,1)` first and, for an
IN endpoint, `c01229e8(endpoint,0)` next (`c0137ff0..8006`). If the endpoint
record has an active command (word 1 nonzero), it calls
`c0138400(record,5,ffff8a66)` at `c0138054..58`. For a synchronous request this
can release the waiting worker's task semaphore. Reset is consequently not a
leaf and can cause scheduler work before acquiring the MIDI ring lock.

The IN cancellation path reaches `c0122924 -> c0120650` for an active TX channel.
`c0120650` issues channel operations through `c01201e0`, polls MMIO at
`c0120716..0728` for at most 128 iterations. When the poll reaches its bound,
`c0120730..32` branches to `c0120764`, **skipping** the first descriptor-drain
loop at `c0120734..0762` (`c011fa20/c011fa54/c0120550`). Both paths then reach
the later queue drain at `c0120780..07aa`, followed by FIFO/channel operations
through `c0120628` and `c01201e0` (`c01207ac..07c2`). Thus expiry proceeds with
partial cleanup rather than reporting a timeout or proving that the first queue
was drained. This is stock behavior, not a new candidate bug. An elapsed
iteration count does not establish actual DMA quiescence. Ownership on this
poll-expiry path remains an explicit hardware/MMIO semantic gate.

`c014a018` performs this stock abort before taking B14[89]. The new hook is
later, on release after ring/parser reset; it does not add an endpoint abort
callback or kernel post. The retained pre-lock abort cannot be described as a
short, callback-free operation. The report does not infer deadlock freedom from
the order alone.

## 4. Concrete producers of callback events 2, 3 and 5

The stock registered MIDI record has +8=`c0151ff4`. Its event table
`c0184544..50` resolves incoming record events 0,1,2,3 to `c0152058`,
`c0152034`, `c01520b4`, `c01520a4`. All successful branches use the callback
stored at `c011ac80` via `c01520cc..20e4` (registered target `c0144c0c`), with
B4=0 and A6 pointing to the saved input word. These event numbers belong to two
different dispatch layers and must not be conflated.

| Record event | Concrete producer | MIDI callback event | Action before callback |
|---:|---|---:|---|
| 0 | `c015e8f4`, walker `c015e880` | 2 | `c0152058..2094`; may abort both endpoints and clear flag bits for zero input, or set bit 8 for nonzero input |
| 2 | `c015ea38`, walker `c015e9d0` | 3 | clear open bit 0 at `c01520b4..20ba` |
| 3 | `c0135798`, SET_CONFIGURATION walker | 5 | set open bit 0 at `c01520a4..20ac`; input word is SET_CONFIGURATION wValue |

`c015e9d0` aborts/reinitializes endpoints before walking records: calls at
`c015e9d8`, `c015e9e4`, `c015e9ec`, `c015e9f4`, then `c01359b8` at
`c015ea00`. Thus event 3's callback alone clearing readiness is not the entire
bus lifecycle operation. `c015e880` likewise has lower-layer calls before its
record walk; the exact branch depends on the status returned by `c01222d8`.

Both walkers are reached through `c0138370`: it gets the lower-layer event index
from `c0121d80`, loads table `c01807a0[index]` at `c01383e6`, and branches at
`c01383ea`. Static table entries 0 and 2 are `c015e880` and `c015e9d0`.
These are concrete event-service chains; the exact electrical/host meaning of
the lower-layer event indices and every producer context is still unproved.

SET_CONFIGURATION dispatch supplies wValue through `c0135790`, including zero.
The record-event-3 branch always sets open bit 0 and MIDI event 5 always sets
`PORT_STATE[9]=1` (`c0144c46..48`); those individual instructions do not test
wValue. This is stock behavior. Whether config-zero can falsely satisfy the
combined controller readiness test depends on the full preceding endpoint
configuration/port cleanup. This report records the condition for investigation,
not an established complete false-readiness execution.

## 5. Teardown failure paths remain open

The direct normal teardown `c0149e80` continues to delete the event and lock
after a nonzero worker-delete result, and it clears each handle only on that
handle's successful deletion. The init guard prevents reinitialization while
any saved worker/event/lock handle is nonzero (`c0149f00..24`), but does not
itself prevent a surviving worker from using a subsequently deleted event/lock.
Deleting a different task goes through `c014a2b0`; the self-delete case returns
-41. Kernel hook failures, delayed deletion and external serialization still
require a complete trace. No proven new candidate interleaving is claimed here.

Initialization cleanup also does **not** consistently clear saved handles:
when event creation fails, `c0149f8c` deletes the already-created lock without
zeroing B14[89]. When worker creation fails, `c0149fb8..9fc8` delete the saved
lock/event without zeroing B14[89]/[90]. The later start-failure cleanup
`c0149fe4..9ff8` deletes all three without clearing their saved words. This is
concrete stock stale-handle behavior. A later normal teardown may encounter
already-deleted handles, while the init guard rejects a direct retry. The new
pre-create hook executes only after the guard and does not create this failure
path. Determining whether callers always route failures through a safe recovery
or halt remains necessary before asserting lifecycle completeness.

## Remaining gate and next bounded work

Follow-up: [USB_ABORT_OWNERSHIP_2026-10-14.md](USB_ABORT_OWNERSHIP_2026-10-14.md)
pins the poll to PEND0 queue 25, verifies the stored TX queue templates and
descriptor-recycling path, and compares the sequence with TI's register guide.
The shared teardown queue and unchecked descriptor association remain open;
the successful-pending path as well as expiry needs ownership evidence.

- Prove lower-layer completion and poll-expiry ownership: follow `c0120550`,
  `c0120628`, completion callbacks and descriptor queues; determine what the
  tested MMIO bit guarantees before treating semaphore release as safe reuse.
- Trace all `c0138370` entry contexts and `c0121d80` event producers, plus
  SET_CONFIGURATION zero's full endpoint/port cleanup. Observe the physical
  semantics separately from recovered callback IDs.
- Trace direct teardown callers `c0144ec0` and `c0145104` through return/failure
  handling and kernel task deletion, including callback identities stored in
  in-flight endpoint records. Handle checks alone are insufficient serialization.
- Finish computed/aliased readiness writer enumeration and timing measurement.
  Normal worker buffering is now much better specified; ownership during abort,
  failure recovery, bounded progress and hardware/audio CPU budget remain open.
