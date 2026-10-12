# Controller transport: offline redesign and proof boundary

This is the proposed replacement for the current MainApp sender. The state
machine is exercised by `tools/controller_transport_model.py` and
`tests/test_controller_transport_model.py`. A separate worker candidate is
now compiled and packaged offline; see
`docs/CONTROLLER_WORKER_CANDIDATE_2026-10-12.md`. The existing Controller TEST
updater remains unchanged. The model is not compiled into the pedal image.

## Contract

1. MainApp button/knob hooks and the AD expression hook publish state without
   waiting for MIDI locks or appending bytes.
2. A MIDI worker activation accepts a CC into the stock raw-byte ring as
   **all three bytes or none**. The controller commits an edge or an absolute
   value only after those three bytes are accepted. A full ring leaves work
   pending until a later space-available activation.
3. Button edges preserve FIFO order while the 15 usable queue slots last.
   On overflow, rapid taps may be lost, but the latest absolute state of
   each of the 12 buttons is reconciled after the queue drains. A dropped
   release cannot permanently leave the controller's intended state pressed.
4. Knobs and expression publish latest absolute values. If a producer changes
   a value while the worker is sending a snapshot, the newer value remains
   pending. A worker activation handles at most four CCs and requests another
   activation if work remains and it can make progress.
5. Disconnect invalidates the record of enqueued absolute states and discards
   old transient edges. Reconnect replays current button states and latest
   motion values. This only guarantees state **offered to the stock ring**;
   USB MIDI has no host receipt acknowledgment, so host delivery cannot be
   inferred from a successful ring append.

## Stock instruction anchors checked

| Anchor | Evidence | Integration consequence |
|---|---|---|
| MainApp housekeeping `c0134dc4`, mailbox wait `c0134dd0` | `recon/19_midi_tx.md` §1, `build/fw/map/main.dis`: `c015350c` receives with timeout -1. | MainApp cannot own retry timing. Its existing drain must be removed in the replacement. |
| MIDI worker `c0149d40`, wait call `c0149d4c` | The 32-bit word `0x10007193` at AIS offset `0x3dcc8` calls `c014a0cc` (event wait). It receives B14[90], mask 3, mode 1, output pointer `B15+4`, timeout -1 in A8; worker tests bit 1 of that output and then calls `c0149c14`. | Redirecting this call to a wrapper that first invokes the stock wait, then stages at most four CCs before the stock drain is a candidate retry point. Preserve the wait result and output word exactly. Disassemble the patched execute packet before accepting it. |
| Ring `c0117b28`, append `c0149d74` | 1025 positions, 1024 usable; append is bytewise and has no lock. Stock producer `c0149de4` holds B14[89]; worker drain also holds B14[89] (`recon/17` A3; `main.dis`). | Hold the same inner lock across a capacity check and three appends. Do not call `c0149de4` while holding its nonrecursive lock. Check each append result despite the capacity proof. |
| Existing `c01274cc` send | Takes B14[161] indefinitely, calls `c0144dc8`, then releases; its return is overwritten. `c0149de4` may accept only a prefix. | Do not call it from MainApp/AD or use its return as message acceptance. The worker path must preserve stock serialization and verify port readiness. |
| Worker event post `c014a240` → `c0155ac0` | `c014a240` passes B14[90] and bit 1; `c0155cf0..f4` ORs the event bit under DINT, with scheduler processing before return. The map's name `big_subsystem_init` for `c0155ac0` is stale. | This is a candidate wake mechanism after publishing producer state and after ring append. Audit its exact handle and context before using it in AD. |

## Required firmware implementation checks

- Use one writer/one reader ownership for the button edge queue: MainApp
  writes entries and publishes the tail last; the MIDI worker advances the
  head only after a complete enqueue. Prove C674x compiler ordering and memory
  visibility in the linked disassembly. Use atomic packed words or a short
  interrupt-guarded snapshot for concurrent expression and knob values; do
  not rely on two independently written `volatile` bytes as a transaction.
- Prove the proposed wait-wrapper's five-register ABI, output word, return
  value, stack use and execute-packet behavior. It must invoke the original
  `c014a0cc` exactly once on every activation. The bounded append occurs
  after the wait returns and before `c0149c14` drains. If less than three
  bytes fit, a single self-post can arrange a retry after that stock drain;
  it must not create an unbounded busy loop when USB cannot progress.
  Check lock order against all producers and the USB path.
- Trace port-ready, USB disconnect/reset and reconnect transitions. Decide
  when the ring is allowed to accept bytes and which existing event can wake
  a pending worker after reconnection. A worker event alone cannot prove
  transport progress while the USB endpoint is unavailable.
- Build a controller image in a **new output path**, disassemble every patched
  CALLP and the linked worker step, validate its AIS section and binary diff,
  and keep it separate from the identified Controller TEST updater. Only then
  repeat the updater stage/hash checks and consider a controlled pedal test.

## Offline checks completed

The model tests cover full-ring retry, dropped release repair, a concurrent
expression update, disconnect/reconnect replay, a four-message worker bound,
and the two-byte/three-byte capacity boundary. They verify the **policy**,
not the stock worker hook, USB lifecycle, scheduler timing or host delivery.

**Current decision:** the four-hook worker build is an offline-only candidate.
Its USB lifecycle, patched execute packet and real timing remain unproved;
the existing four-hook updater is retained for reference. A superficially
successful MIDI capture could hide a lost release or blocked worker path.
