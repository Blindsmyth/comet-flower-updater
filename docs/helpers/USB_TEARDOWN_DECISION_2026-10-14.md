# USB teardown decision and corrected evidence — 2026-10-14

This offline follow-up identifies a concrete correction to the interrupt-mask
argument and defines the next implementation boundary. **DO_NOT_FLASH remains.**
No firmware, shared tools or shared JSON changed; no device/updater ran.

Inputs independently hashed during this review:

| Input | SHA-256 |
|---|---|
| `build/fw/map/main.dis` | `e824b1e0effdaaca35cf87bd3a0bcc9b6242291e4def5e471120b28a762c82d1` |
| `build/fw/map/main.elf` | `b0625c7a055020ddcbc61bb6966311891ead03bb6dae865b6f3f72ed45fb3946` |

## 1. Correction: the top half preserves SOF in the wrapper mask

The earlier [abort follow-up](USB_ABORT_OWNERSHIP_2026-10-14.md) incorrectly
identifies the mask at `c011fd24` as `0x01ff1e1f`, equal to the later rearm
mask. The actual instruction pair is:

```text
c011fd14  MVK.S1   0x1e1f,A0
c011fd20  MVKH.S1  0x01f70000,A0
c011fd24  STW.D1T1 A0,*+A4[0]    ; A4 = 0x01e00034
```

The written value is **`0x01f71e1f`**. Its bit 19 is zero. In contrast,
`c0121568` loads low `0x1e1f` and `c0121570` loads high `0x01ff0000`, so
`c0121576` writes **`0x01ff1e1f`** to `0x01e00030`. Their XOR is `0x00080000`.
This is an instruction-level correction, not an assumption about runtime state.

The Hwi reads the masked status at `0x01e00038` (`c011fc98..fca0`), extracts
bit 19 at `c011fca2`, acknowledges that bit at `c011fcb2`, and calls the empty
SOF veneer at `c011fcb4`. Whether the SOF branch runs or is skipped, the Hwi
then calls `c011faa0(24)` and `c011faa0(25)` at `c011fcb8..fcc2`.

The mask-clear operation therefore does **not itself exclude a SOF-triggered
execution of the same queue consumer**. This establishes an available control
flow, not that SOF is enabled on every abort entry or that a particular race has
occurred. CPU masking, pending delivery, other DMA interrupts and exact entry
state still determine actual interleaving.

The register meanings are supported by TI's mask/source register descriptions;
INTRUSB bit 3 maps to wrapper bit 19. The same guide separately describes DMA
interrupt routing, so the USB-core mask is not a substitute for proving all
queue-consumer interrupt sources excluded. [TI SPRUFM9H, sections 2.8.9,
4.9 and 4.12–4.15](https://www.ti.com/lit/ug/sprufm9h/sprufm9h.pdf).

Independent little-endian bytes read from the ELF's loadable sections:

| Address | Bytes |
|---|---|
| `c011fd14` | `a9 0f 0f 00` |
| `c011fd20` | `e8 fb 00 00` |
| `c011fd24` | `74 02 10 00` |
| `c0121570` | `ea ff 00 00` |

## 2. Correction: the late drain selects the endpoint's submit queue

The previous reports call the queue read at `c0120778` runtime per-channel
state. Its address is more specific:

```text
A3 = c01805d0                 ; c0120658..0664
A15 = 12*N                    ; c0120680..0692
A12 = A3                      ; c0120714, before any drain calls
A4 = A12 + A15                ; c0120770..0774
A11 = *(A4 - 3 words)         ; c0120778
     = *(c01805c4 + 12*N)
```

This is the same template word 0 used for submission. For MIDI N=4, the
stored template at `c01805f4..05fc` is `{22,24,25}`. The second loop at
`c0120780..07aa` drains **submit queue 22** for those stored values, rather
than ordinary return queue 24. The ELF bytes are `16 00 00 00`,
`18 00 00 00`, `19 00 00 00`; instruction `c0120778` is `64 60 90 05`.

Draining queue 22 reclaims descriptors still waiting for this endpoint. It does
not prove receipt of this endpoint's teardown descriptor, reclaim an already
in-flight DMA descriptor, or drain every intermediate completion queue. Thus
it narrows the cleanup semantics without repairing the original ownership gap.

Literal-reference review found template readers at `c01201f0`, `c0120210`,
`c0120484`, `c0120658`, `c0120c00` and `c01219a4`; these inspected accesses
are loads/address passing, not writes to the template. This is not a complete
computed-alias writer proof. The queue identities above are conditional on
those stored template values remaining intact.

## 3. What would actually close the ownership condition

Ordinary-packet type 16 and teardown type 19 are different objects. A useful
completion predicate must inspect teardown word 0: type `[31:27]=19`, TX/RX
bit 16 clear for TX, DMA identity `[15:10]`, and channel identity `[5:0]`.
For MIDI endpoint/software slot 4 the hardware TX channel is 3. TI's sequence
requires teardown receipt before FIFO flushing and channel re-enabling.
[TI SPRUFM9H, section 2.8.4 and Table 24](https://www.ti.com/lit/ug/sprufm9h/sprufm9h.pdf).

The current abort calls a helper that tests type 16, ignores that result,
and recycles the entry (`c0120744..0750`). Its queue-25 pending test cannot
distinguish another channel, an older request, or an entry already removed
by the Hwi. The Hwi can move a non-type-16 entry to queue 32 before deferred
service recycles it (`c011faa0`, `c011fab6`, `c011fb70..78`, `c0121a18..24`).
Observing only queue 25 after that point loses the teardown evidence.

There is no sufficient software-only test using the existing pending/count
values to establish which teardown completed. Restricting a MIDI smoke test
to one cable connection does not remove host-initiated USB reset. A clean
success run also cannot validate the unexecuted expiry path. Current candidate
verification can establish unchanged inherited code, not this missing ownership
property.

## 4. Recommended bounded implementation work

Do not enlarge the poll count or wrap the existing routine in DINT and call
that an ownership fix. Neither adds descriptor association; globally masking
interrupts for an unmeasured hardware wait also affects the audio budget.

The next implementation should be a separately named **diagnostic ownership
candidate**, after patch feasibility review, with the following small contract:

1. Record matching type-19 teardown information before either queue consumer
   discards or forwards it. The relevant consumers are the Hwi's `c011faa0`
   path and the abort's direct drain at `c0120734..0762`. Both must use the
   same observer; a hook only at deferred recycle is too late for the abort.
2. Associate one outstanding request with each software slot/hardware channel.
   Establish a clean initial state; never permit a subsequent request after
   timeout or ambiguous history. A descriptor has no software generation tag,
   so merely incrementing a software epoch cannot distinguish a late old
   descriptor after unsafe continuation. Preserve ordinary type-16 service.
3. Replace the lower abort's success predicate with observation of that request's
   matching TX/DMA/channel teardown, then reclaim its submit queue and perform
   the existing FIFO/channel tail. Preserve the original returned reclaimed
   descriptor count: `c0120800` tests that count at `c012084c`.
4. Make expiry enter a reviewed quarantine/fault path **before** the upper
   endpoint completion can release the worker and before packetizer reuse.
   Returning a negative result from a replacement `c0120650` is insufficient:
   `c0137fe4` does not test the lower abort result. The propagation or fail-stop
   design must include that caller and all paths that clear/refill `c0115300`.
5. Model the handful of decisive interleavings: Hwi consumes matching teardown;
   another endpoint completes first; old descriptor arrives after timeout;
   queue pop loses a race; failed deletion leaves a worker; and matching
   teardown never arrives. Assert no success/reuse on every ambiguous path.

This is a concrete design proposal, **not implemented or verified code**. Direct
callers of `c0120650` found in the pinned disassembly are `c0120848` (compact
16-bit CALLP), `c0121280` and `c012296c` (32-bit CALLP). The existing seven-hook
builder only handles selected 32-bit CALLP sites. A replacement therefore needs
reviewed compact-call/trampoline support or a reviewed entry rewrite; appending
these addresses to the existing hook list blindly would be wrong. The descriptor
observer likewise cannot be treated as an ordinary source-level callback added
to the unmodified stock image. Reserve and verify exact instruction packets.

No single local source edit in `controller_worker_wait` can establish these
lower-layer conditions, because its hook runs after previous stock sends and the
current reset hook runs after stock abort/parser reset. Delaying controller
generation publication does not delay stock buffer reuse.

## 5. Runtime evidence to collect once a diagnostic candidate is cleared

Use a fixed-size memory trace, with no printing/kernel calls in Hwi: request
slot and epoch, descriptor index and teardown word 0, consumer context,
request/receipt timestamps, poll expiry, submit/return queue snapshots,
semaphore release and packet-buffer reuse. Include a sticky fault code and
maximum Hwi/lock duration. Demonstrate that each reused buffer follows a matched
completion and that no expiry/ambiguous event is followed by reuse.

Measure normal/abort latency, poll-to-Clock-tick timing and audio high-priority
service delay under controller replay. Include reset during traffic, removal,
re-enumeration and allocation/deletion failure through an explicitly reviewed
fault-injection route. These measurements can validate progress/timing on tested
runs; the offline failure contract must separately prevent unsafe continuation.

For the processed USB audio goal, keep first EP1 silence transport on the
already proposed bounded PIO path. Adding a second CPPI producer before closing
the shared teardown accounting would multiply this condition. PIO setup still
needs to prevent stock EP1 DMA activation and prove FIFO ownership; this report
does not clear either audio path.

Confidence is high for the mask arithmetic, exact late-drain queue selection
and observed consumers/callers. Actual harmful interleaving, elapsed timing,
complete alias writers and any replacement's patch/fault semantics remain
unproved. The bounded next action is implementing and reviewing the diagnostic
contract, rather than repeating a broad stock call-graph audit.
