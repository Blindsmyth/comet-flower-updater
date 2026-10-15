# Interrupt state on entry to `c0120650` — 2026-10-15

Static review of pinned `build/fw/map/main.dis`. This covers the part of
obligation 2 in the [abort ownership follow-up](USB_ABORT_OWNERSHIP_2026-10-14.md)
that the [coexistence note](USB_HWI_COEXISTENCE_2026-10-15.md) left open.
No device was accessed. **DO_NOT_FLASH remains.** Pinned by
`tests/test_usb_abort_entry_irq.py`.

## Method

Every identified abort call runs in the event-service task
(`c0138310 → c0138370 → c01383ea`; see
[association](USB_Q25_ASSOCIATION_2026-10-15.md) §2). I scanned the
whole image for GIE/IER-changing instructions (`DINT`, `RINT`,
`MVC …,CSR`, `MVC …,IER`): 60 routines contain at least one. For each
root, I followed direct `CALLP` callees up to six levels deep (epilogue
helpers `c016e0xx` excluded), stopping each routine at its first return.
I then intersected the result with that set. Roots: `c0138370`, `c0120650`,
`c014a018`, `c0121224`, `c0122ad0`, `c015e9d0`.

## Result

| Reached routine | Ops | Net effect |
|---|---|---|
| `c015ee80` (L2 cache op), reached from `c0120650` via `c0120550 → c0120614 → c01204b4 → c012050c → c016e380` | three pairs `MVC CSR,Bx; DINT … MVC Bx,CSR` (`c015eeb0/eeb4…eec8`, `c015eecc/eed0…eff0`, `c015f044/f048…f078`) | **restores** the entry CSR |
| `c014a230` / `c014a0b4`, reached from `c0138370` only via `c012154c` (`c0121550` arg 1, `c0121578` arg 0) | `DINT` (`c014a230`), then `CSR |= 1` (`c014a0b4..0c0`) | ends with **GIE = 1** |
| `c015e9d0` | DINT/CSR ops in its later body | its `c01229e8` call is the **first** instruction pair (`c015e9d8`), before any of them |

No routine on the traced chains leaves GIE cleared on return. No `MVC …,IER`
was found on them.

**Finding (likely):** `c0120650` runs with the GIE state of the event
task. The task loop leaves interrupts **enabled** after `c012154c`.
Under the SYS/BIOS convention, a task also starts with GIE=1 (the kernel
was not reviewed). The "interrupts enabled" row of the coexistence table
therefore applies: the event-19 Hwi can preempt the queue-25 poll. Poll
expiry caused by the Hwi draining queue 25 is a realistic case, not a
corner case.

## Not established

- **IER for event 19's CPU interrupt.** GIE=1 does not show the specific
  interrupt is enabled while the abort runs. Nothing in this chain writes IER.
- **INTMSK.** The wrapper INTMSK (`0x01e00034` written by the top half)
  may be armed or masked when the abort is entered. Whether that mask gates
  queue-pending delivery is still unproved.
- **Kernel.** The task-start GIE value and the kernel's Mailbox pend
  (`c014a214 → c0166680`) save/restore behaviour were not traced.
- **Depth and scope.** The search went six levels deep and followed only
  direct `CALLP`s. Calls through registers inside the traced routines were
  not followed.
