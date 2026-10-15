# USB queue-25 endpoint association — 2026-10-15

Static review of pinned `build/fw/map/main.dis`. Obligation 3 of the
[abort ownership follow-up](USB_ABORT_OWNERSHIP_2026-10-14.md): can the
`c0120650` poll be satisfied by a teardown descriptor that belongs to a
different endpoint? No device was accessed and no firmware changed.
**DO_NOT_FLASH remains.** Pinned by `tests/test_usb_q25_association.py`.

## 1. Only `c0120650` (N=1..4) can put entries on queue 25

The teardown-request bit in TXGCR/RXGCR is written only through two helpers.
`c01201e0` handles TX (`0x01e017e0 + 32N` = TX channel N−1, `ADDK 6112`), and
`c0120888` handles RX (`ADDK 6120`). In both helpers, bit 30 is `A6 != 0`
(`c01201e0..01ec`, `c0120236..0242`).

| Writer | Call | A6 | Teardown queue |
|---|---|---|---|
| `c0120650` (TX abort) | `c01206f0` | 1 (`c01206f2`) | template word [2]: 25 for N=1..4, 27 for N=0 |
| `c0120650` tail | `c01207b0/07b8` | 0 | none |
| `c0120dd0` (resume) | `c0120e00` loop N=1..4 | 0 (`c0120dec`; neither `c0120888` nor `c01201e0` writes A6) | none |
| `c0120904` (RX abort) | `c01209c4` → `c0120888` | 1 (`c01209c8` MV B4→A6, B4=1) | RX table `c018059c + 12N` = 27 |

The RX teardown words `c01805a8/b4/c0/cc` all hold 27; the normal RX words
`c01805a4/b0/bc/c8` hold 26. A scan for `MVKH 0x1e00000` paired with offset
28 finds one TEARDOWN-register (`0x01e0001c`) writer: `c01209ba` in the RX
abort, which writes RX bits 1..4. The scan misses bases built another way,
including `c0120650`'s own (`15 << 21`), so it is not exhaustive. The queue
choice comes from the GCR helpers above, not from this register.
**Queue 25 therefore receives only TX teardown descriptors requested by
`c0120650` for N=1..4.**

## 2. Every identified `c0120650` call runs from the USB event-service task

| Call site | Chain upward | Dispatched from |
|---|---|---|
| `c012296c`, `c0122978→c0120800→c0120848` | `c0122924` ← `c01229e8` | see below |
| `c01229e8` ← `c015b26c/b298/b344/b388` | handlers `c015b168/c015b2b4/c015b290` | table `c01807b4/b8/bc` |
| `c01229e8` ← `c015e9d8` | `c015e9d0` | table `c01807a8` |
| `c01229e8` ← `c0137ff0/8000` | `c0137fe4` ← `c0138070` ← cmd 5 direct (`c0138a40..58`) | issued by `c015b128/c015b138` from the handlers above or from MIDI callback `c0144c0c` ops 2/3/5/8 (`c014a018 → c01522d8`) |
| `c0121280` ← `c0121224` ← `c0122ad0` | `c015e9e4` in `c015e9d0` | table `c01807a8` |
| `c0121224` ← `c012146a` | `c01212e0` ← `c01358b4` in `c01357c8` ← SET_CONFIGURATION `c0135660` / SET_INTERFACE `c0135940` | std-request table `c0180210` loaded in `c01359e4` = table `c01807ac` |

The handler table `c01807a0..c01807c8` has exactly one dispatch site:
`c01383d8..c01383ea` in `c0138370`. The
[abort follow-up](USB_ABORT_OWNERSHIP_2026-10-14.md) traces that function to
the event-service task entry `c0138310`. The
[lifecycle continuation](USB_LIFECYCLE_CONTINUATION_2026-10-14.md) traces the
known producers of callback `c0144c0c` events 2/3/5 to walkers in the same
table. *Update:* op 8 (`c0144d0c`) is produced by `c0151ed0` (`c0151f30`) on a host
CLEAR_FEATURE(ENDPOINT_HALT) for EP 0x84, which arrives through slot 3 (`c01359e4`) of the same table. See
[GEMINI_OP8_REPORT.md](GEMINI_OP8_REPORT.md).

**Bounded finding:** every identified abort runs in a single task loop, so
aborts are sequential, not nested. One task instance runs `c0138310` (`GEMINI_TASK_INSTANCES_REPORT.md`: one creation site, guarded on `B14[94]`). Op 8's producer is traced to the same loop.

## 3. Consequence: a stale descriptor needs a prior expired poll

With sequential aborts, a stale descriptor can sit on queue 25 when abort *N*
starts only if all of these hold:

1. an earlier abort *M* expired its 128-iteration poll (`c0120732`) before
   *M*'s teardown descriptor arrived;
2. that descriptor arrived later; and
3. the Hwi (`c011fcc0`, which drains 25 unconditionally; see
   [coexistence](USB_HWI_COEXISTENCE_2026-10-15.md)) did not run between its
   arrival and *N*'s poll.

When all three hold, *N*'s poll succeeds on *M*'s descriptor. The drain then
recycles it (ownership is still single-owner), and *N* goes on to the FIFO
flush (`c0120628`) and re-enable without receiving its own descriptor. That
departs from TI's teardown sequence, which requires the descriptor before the
flush. *N*'s own descriptor arrives later and the Hwi recycles it.

No stock instruction reads a channel identity from a popped queue-25 entry
(`c0120734..0762`, `c011faa0`, `c01219f4`). The stock image therefore cannot
detect this case.

## 4. Status of the obligations

- **3. Narrowed, not closed.** Mis-association requires a prior poll expiry
  and Hwi latency. It is not possible in a clean, non-expiring sequence. It
  cannot be excluded statically, because expiry and Hwi timing are
  hardware-dependent.
- The owner-run diagnostic can detect it directly. Site 1 (`c0120744`) logs
  word0, and `FAULT_CHANNEL_MISMATCH` (0x2) flags a type-19 entry whose channel
  differs from slot−1 (TX channel = N−1, from `0x01e017e0 + 32N`). See
  [OWNER_DIAG_TEST_PREP](OWNER_DIAG_TEST_PREP_2026-10-15.md).
  Caveat: the diagnostic has no observer on the expiry branch (`c0120732`).
  An expired poll appears only as missing site-1 records for that abort.
- **If a fix is needed:** at `c0120744`, compare the word0 channel against N−1
  and keep polling on a mismatch instead of accepting the entry. That would be
  a new named candidate. Nothing has been built.
- Since resolved: a single `c0138310` task instance (GEMINI_TASK_INSTANCES_REPORT),
  elsewhere: entry IRQ state (USB_ABORT_ENTRY_IRQ), the op-8 producer
  (GEMINI_OP8_REPORT), and recovery after expiry (SOL_EXPIRY_RECOVERY_REPORT review).
