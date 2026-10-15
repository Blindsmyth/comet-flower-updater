# USB TX template writers — 2026-10-15

Static review of the pinned `build/fw/map/main.dis` and `main.elf`. This
addresses obligation 1 of the
[abort ownership follow-up](USB_ABORT_OWNERSHIP_2026-10-14.md): find the
runtime writers to the TX templates and the per-channel queue words. No device
was accessed and no firmware changed. **DO_NOT_FLASH remains.**
Pinned by `tests/test_tx_template_writers.py`.

## Table placement

The 5×3-word table `c01805c4..c01805ff` sits in section `sc016f780`
(`0xc016f780`, size `0x123a4`, `SHF_WRITE|SHF_ALLOC`, PROGBITS). Because the
section is writable, the absence of a direct reference does not, on its own, show
that the table is constant. The next object starts at `c0180600`, which the
literal at `c0180dd8` references. No aligned word in any PROGBITS section
points into `c01805c4..c01805ff`.

## Every instruction-level reference

These are the only `MVK` low halves in the table range that are paired with
`MVKH 0xc0180000`. The other `0x05dc`/`0x05fc` immediates in the image are
numeric constants with other high halves or none, e.g. `c012bd88` → `0xc01005fc`
and `c015e7cc` (a multiplier).

| Site | Address formed | Use |
|---|---|---|
| `c01201f0` | `c01805c8 + 12N` (word [1]) | `LDW *A4[0]` at `c012020a` |
| `c0120210` | `c01805cc + 12N` (word [2]) | `LDW *A4[0]` at `c0120226` |
| `c0120484` | `c01805c4 + 12N` | passed to `c0120250` as A4 |
| `c0120658` | `c01805d0` base | `LDW *-B4[1]` (`c0120674`), `*-A4[1]` (`c012068c`), `*-A4[3]` (`c0120778`) |
| `c0120c00` | `c01805c4 + 12N` | passed to `c0120250` as A4 |
| `c01219a4` | `c01805c4 + 12N` | passed to `c0120250` as A4 |

`c0120250` copies its A4 to A7 at `c0120258`. It reads only `*A7[1]`
(`c01202c6`) and `*A7[0]` (`c0120320`). All of its stores go through B4, the
descriptor at `0xc87a9000 + 32*index` (`c0120274..0282`). No instruction
writes the table through any of the six formed addresses.

**Bounded finding:** no instruction-level writer to the TX template table
exists in the stock image. Two kinds of write remain unexcluded: a
computed-pointer write into section `sc016f780` (a bulk copy or clear), and a
write from outside this ELF (bootloader, DMA). On the evidence available, the
table reads as initialized data.

## Correction: the abort tail's queue is template word [0]

The abort follow-up said the drain at `c0120778..07aa` uses "runtime state".
The register trace shows otherwise:

- `c0120658/0664` A3 = `0xc01805d0`; `c0120672` B5 = A3; `c0120714` A12 = B5.
- `c0120680/0684` B0 = 12 × B4, where B4 = A10 = N (`c012067a`); `c0120692` A15 = B0.
- No later instruction before `c0120774` writes A12 or A15.
- `c0120772` A1 = A12; `c0120774` A4 = A1 + A0 (= A15) = `c01805d0 + 12N`.
- `c0120778` `LDW *-A4[3]` reads `c01805c4 + 12N`, which is **template word [0]**.

The tail therefore pops the slot's **submission queue** (16/18/20/22 for
N=1..4; 22 for MIDI IN), not queue 24. It does not depend on mutable state,
subject to the bounded finding above. For each entry it calls
`c0120550(index, B4=1, A6=1, B6=N)` (`c0120790..0796`), the path that
updates the outstanding count. It repeats until `c011fa20` returns a negative
index (`c01207a8/07aa`).

Then `c0120628` and two `c01201e0` calls follow. Those calls pass `A6=0`, so
they select queue 24 in TXGCR.

Taken together, after the queue-25 wait (or its expiry), the stock routine
removes descriptors still waiting in the endpoint's own submission queue.
The submit queue is per-endpoint in the templates (unlike 25), so this
step's endpoint association is static. The shared-queue-25 association
problem is unchanged.

## Effect on the remaining obligations

1. **Narrowed.** Template words have no instruction-level writer. Still open:
   bulk or external writes to `sc016f780`. The TXGCR MMIO written by
   `c01201e0` has its own writers, which were not reviewed here.
2. Unchanged: entry interrupt state and Hwi coexistence for `c0120650`.
3. Unchanged: matching-endpoint teardown completion on queue 25 and the
   expiry recovery.
4. Unchanged: later initialization/failure recovery before claiming reuse safety.
