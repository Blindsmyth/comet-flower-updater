# Brief (Codex gpt-5.6-sol, medium): what happens after a TX abort poll expires

Follow `docs/helpers/SAVE_PROTOCOL.md` exactly, including its Token economy section.
- Report: **`docs/helpers/SOL_EXPIRY_RECOVERY_REPORT.md`**. Create it with the
  headings below and commit it. After every finding, commit THAT FILE ONLY.
- Scratch folder: `build/sol_expiry/`. This is static analysis only. Never touch
  the pedal, MIDI/USB devices or any .exe, and never push. Do not edit any other file.
- Inputs: `build/fw/map/main.dis` (pinned disassembly). For names, grep
  `recon/map/chunk_02.md` and `recon/map/chunk_03.md`.
- Background (read these, do not repeat their work):
  `docs/helpers/USB_ABORT_OWNERSHIP_2026-10-14.md`,
  `docs/helpers/USB_HWI_COEXISTENCE_2026-10-15.md`,
  `docs/helpers/USB_Q25_ASSOCIATION_2026-10-15.md`,
  `docs/helpers/USB_TX_TEMPLATE_WRITERS_2026-10-15.md`.

## Known facts (do not re-derive)
- `c0120650(N)` is the TX abort for slot N=1..4 (TX DMA channel N-1). It
  requests a teardown, then polls PEND0 bit 25 at most 128 times
  (`c0120716..0728`). On expiry, `c0120732` branches to `c0120764` and
  skips the queue-25 drain.
- Both paths then drain the slot's submit queue (template word [0]: 16, 18,
  20 or 22) with `c0120550(idx, B4=1, A6=1, B6=N)` (`c0120778..07aa`). After
  that come `c0120628` (FIFO flush halfword at `0x01e00502+16N`) and
  `c01201e0(N,0,0)` / `c01201e0(N,1,0)` (channel disable/enable, queue 24).
- `c011fa20` pops, `c011fa70` pushes, and queue 28 is the free pool.
  `c0120550` with B4=0 just recycles the descriptor to queue 28.

## Questions (one report section each)
1. **The c0120550 B4=1 path** (`c0120564` onward, A6=1). What does it do with
   the per-slot state? Look at the outstanding count, the pending table
   (`c01200f4`), and the restart/resubmit (`c01203b8`, `c01204b4`). Does it
   ever resubmit a buffer to the hardware during an abort? Give the
   predicated branch truth table.
2. **In-flight descriptors after expiry.** Suppose a host packet descriptor
   was already taken by DMA (not in the submit queue) when the teardown was
   requested. Where does it return: queue 24 or 25? Which consumer handles
   it (`c011faa0` for 24, the type-16 path at `c011fab8..fb6e`)? What state
   does that consumer update? After the abort, can it double-count or touch
   a buffer that the abort already considered freed?
3. **Per-slot state left by the abort.** Look at the fields of the slot record
   at `0xc0112c08 + 0x2a8*N - ...` (see `c01206aa..06e8`; field [3] is set to 1
   and later 0). After an expired abort, is any field left inconsistent
   (outstanding count, busy flag, pending table)? What does the next submit
   (`c0120250` via `c0120484`, `c0120c00` or `c01219a4`) check before it
   proceeds?
4. **Later re-initialization.** Do `c0121224` (usb_ep_reset_full: `c011fd40`,
   `fd98`, `fdc8`, `fe20`, `fe4c`) or `c0120dd0` (resume) reset that state
   completely? Which fields does each one clear?
5. **Verdict.** After an expired poll, can a buffer be reused while DMA still
   owns it? List each concrete path with its evidence, or state that none
   exists, and name what stays unproven.

Every claim needs an instruction address, a short excerpt of at most 8
lines, and a confidence (confirmed / likely / guess). Pitfalls:
- A CALLP to a `c016e0XX` epilogue ends a function.
- Delay-slot instructions run on both paths of a branch.
- `||` marks an instruction that runs in the same packet as the one before it.
- Compact 16-bit instructions without `||` start a new packet.
