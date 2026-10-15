# USB Hwi / abort-poll coexistence — 2026-10-15

Static review of pinned `build/fw/map/main.dis`. This addresses obligation 2 of the
[abort ownership follow-up](USB_ABORT_OWNERSHIP_2026-10-14.md): can the USB
Hwi run during the `c0120650` queue-25 poll, and what happens to the
teardown descriptor when it does? No device was accessed and no firmware
changed. **DO_NOT_FLASH remains.** Pinned by `tests/test_usb_hwi_coexistence.py`.

## Summary

The entry interrupt state of `c0120650` is **still unproved**. The result
below holds whether or not the Hwi can preempt the poll: **on every traced
path, each queue-25 descriptor is popped by exactly one consumer and recycled
to free queue 28 exactly once.** Preemption changes what poll expiry means,
not who owns the descriptor. This discharges the descriptor-ownership part of
obligation 2. It does not touch the endpoint-association part (obligation 3).

## Queue primitives

- **Pop** `c011fa20(q)`: `LDW` from `0x01e00000 + 16q + 4·0x1803` =
  `0x01e0600c + 16q` (`c011fa20..fa2c`), which is QMGR queue *q* register D. The
  result is masked with `CLR 0,4` and converted to `(ptr - 0xc87b9000) >> 5`.
  Pointers below the pool return −1 (`c011fa34..fa50`). Empty queues read 0,
  which also returns −1.
- **Push** `c011fa70(q, index)`: `STW` of `(0xc87b9000 + 32·index) | 2` to
  `0x01e0600c + 16q` (`c011fa74..fa96`).
- **Type** `c011fa54(index)`: `(word0 >> 27) == 16` (`c011fa64..fa6c`), i.e.
  host packet. The type for TI CPPI 4.1 teardown descriptors is 19, so they
  return 0.

Per [SPRUFM9H](https://www.ti.com/lit/ug/sprufm9h/sprufm9h.pdf), reading
queue register D pops the head atomically. Two CPU contexts therefore cannot
both obtain the same entry. That is a hardware-documentation premise; it has
not been measured on this device.

## The Hwi consumes queue 25 unconditionally

`c011fc8c` is the installed event-19 callback (`c0122288` pointer;
`c0122296 MVK 19`; `c01222a8 CALLP c014a524`, per recon chunk 02).
After reading `0x01e00038` (INTMASKEDR) at `c011fc9a`, it calls
`c011faa0(24)` and `c011faa0(25)` at `c011fcb8/fcc0`. These calls do not
depend on any status bit. The INTMSKCLR write of `0x01ff1e1f`
(`c011fd24`) masks wrapper sources, but the Hwi services the CPPI queues
itself. This review has not established that the mask also gates the
interrupt line for queue-pending events. The mask therefore cannot be
assumed to exclude the Hwi.

`c011faa0` loops until the pop returns −1 (`c011fb82..fb88`). A non-type-16
entry leaves the branch at `c011fab6` with A7=0 (`c011fab0`), so
`c011fb74/fb76` pushes it to queue **32** (A6=32 from `c011faae`).

## Queue 32 is serviced and recycles to 28

The event decoder `c0121d80` sets A11=`0x01e04094` (`c0121d84..0d90`, PEND1,
queues 32..63). Before it reaches the INTSRCR bits, it tests bit 2 → queue
34 (`c0121db0/0db4`) and bit 3 → queue 35 (`c0121dc0/0dc4`). Later it tests
bit 0 → queue 32 (`c0121e38/0e40` → `c0121e94`, B4=32) and bit 1 → queue 33.
`c01219f4` pops one entry (`c0121a04`). If the entry is not type 16
(`c0121a18/1a22`), it calls `c0120550(index, B4=0, …)` (`c0121a24..1a2e`).
With B4=0, `c0120560` branches to `c0120618`, which pushes the index to
queue **28** (`c0120618..0622`).

The abort drain recycles through the same function with the same B4=0
argument (`c0120748..0750`). Either route therefore ends with one push to
queue 28.

## Interleavings with the poll (`c0120716..0762`)

| Hwi timing | Abort observes | Descriptor fate |
|---|---|---|
| Before the poll sees PEND0 bit 25 | poll may run to the 128-iteration bound; `c0120732` skips the drain | Hwi → q32 → `c01219f4` → q28 |
| After pending seen, before `c0120734` pop | pop returns −1; `c012073a/0740` branches to `c0120764` (no recycle of −1) | Hwi → q32 → q28 |
| Between drain-loop pops | `c0120754..0760` exits on −1 | split between consumers, each entry once |
| Not at all (masked/no preemption) | normal drain | abort → q28 |

No row double-pushes an index or recycles −1.

## What this changes

- **Poll expiry is not evidence of hardware failure.** If the Hwi can
  preempt, a software consumer can clear PEND0 bit 25. The existing expiry
  finding stands, but its cause cannot be attributed to hardware.
- **Ownership on the expiry path, for queue-25 entries:** these descriptors
  are recycled by the Hwi route. The abort does not leak them and cannot
  double-free them.
- **Unchanged (obligation 3):** queue 25 is shared by all four TX endpoints.
  Neither consumer checks which channel an entry came from. A descriptor
  from another endpoint's earlier teardown can still satisfy the poll.
- **Unchanged:** the entry interrupt state of `c0120650`; whether `c01219f4`
  service is timely (it runs in the event-service task loop `c0138370`); and
  whether the Hwi or the abort runs first under real latency.

## Diagnostic relevance

The `--diag-teardown` observers sit at `c0120744` (abort pop) and `c0121a18`
(queue 32..35 consumer). With this result, a hardware capture of a disconnect
can now separate two cases:

- an abort-site record shows the abort received the teardown descriptor;
- a site-2 record for a non-type-16 entry, with no abort record, shows that the
  Hwi got it first. An expired poll in that case is the software race above,
  not a hardware failure.
