# Indirect-callback resolution for the worker stack bound - 2026-10-13

**Superseded in part:** [the 2026-10-14 continuation](STACK_CONTINUATION_2026-10-14.md)
traces additional slots and runtime registrations, corrects `c013ce6c` to a
formatter callback, and distinguishes ready/switch hook fields. The 1,784-byte
ceiling is withdrawn. The table below records the earlier analysis.

**DO_NOT_FLASH stands. Offline analysis only; no device accessed.** Follow-up to
`STACK_BOUND_2026-10-13.md`. Method: for each unresolved register branch, find
the instructions that load the branch register, recover the config-slot address
(`MVK`/`MVKH 0xc018....`), read its static initial value from `main.elf`, and
search `main.dis` for writers. Measured with `tools/stack_depth.py [--resolve]`.

## Slot to target table

| Site(s) | Register source (slot) | Static value | Target | Depth: direct / `--resolve` |
|---|---|---|---|---|
| `c0144784` | `*c01802e4` | `c015d160` | leaf-like | 64 / 64 |
| `c0162990` `c0162d34` `c0164438` `c015dfec` | `*c018173c` | `c0161540` | leaf-like | 56 / 56 |
| `c015de82` | `*c01817ac` | `c016cc00` | calls `c015de40` | 112 / 984 |
| `c015a978` | `*c01819f8` | `c0168c40` | calls `c0169ca0` chain | 936 / 1040 |
| `c016a648/650/668` | `*c0181a40` | `c016bb40` | calls `c0168340` | 64 / 976 |
| `c0169aac` | constant `MVK/MVKH` | `c0167940` | direct jump, not data-driven | 8 / 928 |
| `c015a8fc` | `*c01819ec` | `0` | runtime-set (no static writer found) | unknown |
| `c016b992` | `*c0183aec` | none (BSS) | runtime registration; one writer `c016e0c4` | unknown |
| `c0150bf8` | not traced (load precedes the window) | - | - | unknown |
| `c0166b28` `c0166b38` | `A11`, a function parameter | caller-defined | - | unknown |
| `c013ce6c` `c0162c70` `c015df2c` | entries in the hook-record tables (`c0181860`, `c0181684`) | six known handlers | already in `--resolve` set | - |
| `c016def8` | `0x11809160` | off-image | in a misdecoded data region (`.word` lines) | not code |

Closed by this pass: `c0144784` and the four `c018173c` sites (small bounded
leaves, zero unresolved items), and `c0169aac` (constant target).

## Verdict on the 1784 B ceiling

**Not confirmed, not refuted.** Targets `c016cc00`, `c0168c40` and `c016bb40`
re-enter the scheduler subtree, and `--resolve` charges them 976-1040 B each.
The earlier 1104 B kernel path does not include them stacked on top of the frame
at their call site. If `c0168c40` (1040 B) were reached from a path already
deeper than about 336 B below the worker, the total would pass the 1376 B left
after wait/interrupt frames and the 2048 B stack. Whether any chain reaches it
that deep is not shown. Four sites (`c015a8fc`, `c016b992`, `c0150bf8`,
`c0166b28/38`) remain unresolved because their targets are set at runtime.

The gate stays **open**. Static analysis alone is unlikely to close it. The
practical options are: (a) raise the worker stack request from 2048 to 3072 or
4096 bytes if the kernel allocation and 40 KiB budget allow it, then re-verify;
or (b) measure the `0xBE` watermark in an owner-run test. Option (a) changes the
firmware and needs a rebuild and new identity.
