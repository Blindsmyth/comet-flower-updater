# USB abort ownership follow-up — 2026-10-14

Static review of `main.dis` and `main.elf`, using the identities recorded in
[the lifecycle continuation](USB_LIFECYCLE_CONTINUATION_2026-10-14.md).
No device was accessed and no firmware changed. **DO_NOT_FLASH remains.**

## Exact queue and register trace

The previous continuation left the MMIO poll at `c0120716` unnamed. Its
address is **`0x01e04090`**, and its mask for any TX endpoint 1..4 is
**`1 << 25`** in this image. It polls queue 25, rather than a per-channel
DMA-enable bit.

The little-endian ELF words at `c01805c4 + 12*N` are:

| Software slot N | Submit word [0] | Normal-return word [1] | Teardown-return word [2] |
|---:|---:|---:|---:|
| 0 | 4 | 26 | 27 |
| 1 | 16 | 24 | 25 |
| 2 | 18 | 24 | 25 |
| 3 | 20 | 24 | 25 |
| 4 (MIDI IN) | 22 | 24 | 25 |

These were read from the ELF, not inferred from channel numbering. The same
words appear as `.word` entries in the pinned disassembly. This establishes
stored values; it does not establish the completeness of runtime writers.

`c0120250` takes the submission queue from template word [0] at `c0120320`.
The descriptor builder takes word [1] at `c01202c6`, masks its low 12 bits
at `c01202d0`, and incorporates them into descriptor word 2 at `c01202da`.
Thus the ordinary TX packet's return queue is 24.

`c01201e0(N,B4,A6)` selects template word [1] for A6=0
(`c01201f0..020a`), or word [2] for A6!=0 (`c0120210..0226`). Its output is
written at `0x01e017e0 + 32*N` (`c0120232..024c`). For N=4 that is
`0x01e01860`. B4 selects bit 31 and A6 selects bit 30. The abort entry calls
this helper with B4=1 and A6=1 at `c01206ec..06f2`, selecting queue 25.
The tail calls at `c01207b0/07b8` use A6=0 and select queue 24 again.

The poll's queue number is loaded into A14 from
`c01805d0 + 12*N - 4` (`c0120658..0674`). The same value is loaded into A1
at `c012068c`, then becomes A8=`1 << A1` at `c0120690..0698`.
`c01206f4..0708` build A5=`0x01e00000 + (144 | (1 << 14))`.
The load/mask at `c0120716/0718` therefore tests queue-25 pending.

The request mask is formed separately as `1 << (N-1)` at
`c012069a..06a4`, shifted to endpoint bits 17..20 at `c0120704`, and written
to `0x01e0001c` at `c0120720/072e`. Those writes are requests, distinct from
the pending status read.

[TI SPRUFM9H](https://www.ti.com/lit/ug/sprufm9h/sprufm9h.pdf),
sections 2.8.4, 4.69 and 4.84, identifies TXGCR bit 30 as a teardown request,
its low queue field as the teardown return destination, and PEND0 as queue
occupancy. Its TX teardown sequence requires receipt of a teardown descriptor
before FIFO flushing and channel re-enabling. These register meanings support
the interpretation above; they do not establish a successful execution of the
stock routine.

## What the completion drain verifies

After observing pending, `c0120734` pops from the queue in A14 (25).
`c011fa20` converts the queue result into a descriptor index, returning -1
when the pointer is below the descriptor pool. `c011fa54` reads descriptor
word 0's type field and returns whether it equals 16 (`c011fa64..6c`).

The abort loop calls that type helper at `c0120744`, but does not branch on
its returned A4. The next call, at `c0120748`, replaces A4 with the saved
descriptor index in its argument packet (`c012074a`) and sets B4=0,
A6=1, B6=N. No channel field is inspected by these instructions. It repeats
until queue 25 is empty (`c0120754..0762`).

`c0120550` captures incoming B4 in B0 at `c0120556`. With B4=0 its branch
at `c0120560` goes directly to `c0120618`, which recycles the descriptor
through `c011fa70(28,index)` at `c0120618..0622`. The per-channel outstanding
count and restart logic is skipped on that path. It does not validate the
descriptor's channel identity. By comparison, the deferred normal service
at `c0121a18..1a22` explicitly branches on the type-helper result.

**Bounded finding:** queue 25 is shared by the four TX endpoints in the
stored templates. The reviewed abort drain establishes no check that the
entry making its poll succeed is the requested endpoint's teardown descriptor.
A proof must account for queue contents and serialization, including earlier
aborts and the Hwi consumer. This is not a demonstrated unsafe interleaving.

## Expiry and later cleanup

The existing expiry finding still stands: reaching 128 iterations skips the
queue-25 drain at `c0120732` and reaches `c0120764`. Both observed-pending
and expired paths later drain a queue at `c0120778..07aa`.
*Corrected 2026-10-15:* that queue is template word [0] (the slot's submit
queue, 22 for MIDI IN), loaded via `*-A4[3]` from `c01805d0 + 12N`. It is
neither runtime state nor queue 24. See
[USB_TX_TEMPLATE_WRITERS_2026-10-15.md](USB_TX_TEMPLATE_WRITERS_2026-10-15.md).

`c0120628` forms `0x01e00502 + 16*N`, reads a halfword, computes
`((old | 8) & 0xff98)`, and writes that result twice at `c0120648/064a`.
It does not read TXGCR or a descriptor after those writes. The later
`c01201e0` calls disable and enable with queue 24 selected; this tail has no
new wait that repairs an expired queue-25 poll.

The first-level caller `c0137fe4` does not test the `c01229e8` result before
continuing to endpoint-record completion (`c0137ff4..8008`, `c0138054`).
The earlier continuation already traces that completion to the synchronous
task-semaphore release. Consequently the release alone cannot prove that
the requested endpoint's teardown descriptor was received first.

## Caller context and interrupt-mask evidence

The registered USB Swi entry `c015b0f0` submits command 7 through
`c01387f0` at `c015b100`. Its command-7 path allocates/enqueues a message
at `c01389f4..8a10`. The task entry `c0138310` receives that message via
`c014a214` at `c0138318`, releases the message at `c013834c`, then invokes
the command-table target through B0 at `c0138364`. Slot 7 is `c0138370`.
Thus this traced event-service chain runs in the receiving task. Treating the
entire service as the USB Swi callback would assign it the wrong context.

`c0138370` repeatedly calls `c0121d80` and dispatches returned events at
`c01383ea`. Only its finished/error branch calls `c012154c` at `c0138390`.
The top half can mask wrapper interrupts first: `c011fd24` writes
`0x01ff1e1f` to `0x01e00034`, then posts the USB Swi at `c011fd28`.
`c012154c` clears the software notification word and writes the same mask
to `0x01e00030` at `c0121576`. This rearm is bracketed by
`c0121530(1)` and `c0121530(0)`; their concrete targets are
`c014a230` (DINT at entry) and `c014a0b4` (set CSR bit 0 at
`c014a0b8..0c0`). This is not a saved-state interrupt restore.

The reset callback's command 5 takes the separate direct branch at
`c0138818 -> c0138a40..58`, bypassing the message-queue path. No DINT or
call to `c0121530` appears in that direct command branch or the traced
`c0137fe4 -> c01229e8 -> c0122924 -> c0120650` instruction path.
That absence does not establish an enabled interrupt on entry. Conversely,
the top-half mask write alone does not establish that every abort caller
inherits that mask or that all sources capable of invoking the Hwi are
excluded. The task association and mask/rearm ordering narrow the context
question without proving either a race or complete serialization.

## Remaining proof obligations

1. Trace all runtime writers to the TX templates and per-channel queue words.
2. Establish the entry interrupt state and serialization for `c0120650`.
   *2026-10-15:* descriptor ownership under Hwi preemption is resolved in
   [USB_HWI_COEXISTENCE_2026-10-15.md](USB_HWI_COEXISTENCE_2026-10-15.md).
   Every queue-25 entry is recycled to 28 exactly once, via either consumer.
   The entry interrupt state is still unproved.
   The Hwi path `c011fc8c -> c011faa0` also drains queue 25. Determine whether
   it can run during this poll. For a non-type-16 descriptor, `c011faa0`
   bypasses the ordinary packet branch at `c011fab6`: A7 was set to zero
   at `c011faae`, so `c011fb70..78` forwards the descriptor to queue 32
   (A6=32 from `c011faae`). The deferred `c01219f4` path then recycles
   non-type-16 entries through `c0121a24`. Thus an enabled Hwi can consume
   the queue-pending indication; proving its exclusion or safe coexistence
   is necessary before interpreting poll expiry as hardware failure.
3. Prove the matching endpoint's teardown completion on every path, or
   specify reviewed recovery that preserves buffer ownership after expiry.
4. Trace later initialization and failure recovery before claiming buffer
   reuse is safe. A bounded iteration count and descriptor recycling are
   insufficient ownership evidence on their own.
