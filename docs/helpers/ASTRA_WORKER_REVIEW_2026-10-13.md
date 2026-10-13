# Controller worker review — 2026-10-13

Status: in progress, offline only. The current candidate remains DO_NOT_FLASH.
No updater or device operation was performed.

## Directed helper setup

Helper audits were conducted to inspect the worker ABI, timeout control flow, and USB lifecycle in `build/fw/map/main.dis`. The resulting audits are recorded in `docs/helpers/WORKER_ABI_AUDIT_2026-10-13.md` and `docs/helpers/USB_LIFECYCLE_AUDIT_2026-10-13.md`.

## Confirmed: model reset coverage does not establish candidate behavior

`tools/controller_transport_model.py` increments `connection_epoch` on both
disconnect and reconnect, and `worker_step` rejects acceptance if that epoch
changes. Its `test_reset_during_worker_snapshot_requires_replay` directly
invokes both lifecycle methods during an append.

`firmware/controller/controller.c:78` samples ready flag and port pointer.
The worker at line 128 clears `tx.connected` only when it samples an
unready port; it has no connection generation. A down/up transition entirely
between observations can leave `tx.connected == 1`, so the replay branch is
not entered and pending old edges need not be discarded. This is a source
level counterexample to inferring reset correctness from the Python model.
Whether stock lifecycle scheduling makes that sequence possible remains an
open firmware trace question; no claim of an observed hardware failure is made.

Stock anchors: `c0144e6c` clears port pointer word 9, `c0144e78` clears ready
word 3, and `c014a024..c014a04c` surrounds ring reset with B14[89] locking.
These alone do not prove complete lifecycle ordering or invalidate controller
sent-state on every connection change.

## Confirmed: stock caller consumes output word, not return value

At `c0149d4c` the original call receives event A4, mask B4=3, mode A6=1,
output B6=B15+4, timeout A8=-1. After return, `c0149d56` loads that output
word into B1, `c0149d60` tests bit 0, and `c0149d68..c0149d6e` runs drain
calls. The caller does not test returned A4 here.

The compiled wrapper sets A8=100 at `c01a0208`, preserves the stock return
in A15 at `c01a0212`, and restores it to A4 at `c01a05a6`. The underlying RTOS
is TI SYS/BIOS, where timeout arguments represent Clock ticks. With default
SYS/BIOS configuration (`Clock.tickPeriod = 1000 µs`), timeout 100 equals ~100 ms.

## Resolved: timeout output behavior and delayed branch proof

The candidate document's earlier claim that stock wait writes -50 into the output
word has been disproved and corrected. As traced in `docs/helpers/WORKER_ABI_AUDIT_2026-10-13.md`:
on timeout, the lower wait returns 0, and `c014a0cc` falls through to
`c014a106 BNOP c014a114, 3`. The delay slots compute -50 in A0, and the branch
lands at `c014a114`, completely skipping the store at `c014a10e`. The output word
`*out_bits` is left untouched on timeout, and -50 is returned in A4.
The wrapper prezeros `*out_bits`, keeping the output non-negative.

## Next gates

Local validation: `python -m pytest tests/test_controller_transport_model.py -q`
passed all eight tests on 2026-10-13.

1. Implement explicit transport generation invalidation or hook ring reset
   (`c014a018`) so unobserved disconnect/reconnect transitions between 100 ms
   wakes trigger state replay.
2. Complete task stack capacity audit (confirming worst-case stack headroom beyond
   the 312-byte known call depth).
3. Rebuild, verify new hash with the second AD channel hook (`6ac9489`), and package
   under a new candidate identity before proposing any pedal test.
