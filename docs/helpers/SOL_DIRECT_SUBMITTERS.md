# Brief (Codex gpt-5.6-sol, medium): what triggers the ungated TX submitters c0120c00 and c01219d0

Follow `docs/helpers/SAVE_PROTOCOL.md` exactly, including its Token economy section.
- Report: **`docs/helpers/SOL_DIRECT_SUBMITTERS_REPORT.md`**. Create it with the
  headings below and commit it. After every finding, commit THAT FILE ONLY.
- Scratch folder: `build/sol_direct/`. This is static analysis only. Never touch the
  pedal, devices or any .exe, and never push. Do not edit any other file.
- Inputs: `build/fw/map/main.dis`; names in `recon/map/chunk_02.md`. Background:
  read the "Claude review" block at the top of
  `docs/helpers/SOL_EXPIRY_RECOVERY_REPORT.md`. It corrects two of your earlier
  predicates (`c0120fa0`, `c011fb38`). Re-check every `[B0]`/`[!B0]` against the
  register's meaning before writing a truth table.

## Background
TX record N is at `0xc011297c + 0x2a8*N`. Field [5] is the outstanding
descriptor count. The public enqueue `c0120f64` defers while [5] != 0. Two
other sites call `c0120250` (build + push descriptor) with no visible gate on
[5]: `c0120c14` (in the routine around `c0120c00`) and `c01219d0` (in the
routine around `c01219a4`).

## Questions (one report section each)
1. **Enclosing routines.** For each site: the routine's start (prologue), its
   callers (direct CALLP plus address-constant/table references), and its
   recon name if it has one.
2. **Gate.** Before reaching the submit, does any predicate in the routine (or
   its callers) depend on TX field [5], field [3], field [9], or queue state? Give
   the truth table with addresses.
3. **Does it update [5]?** After a successful submit, is field [5]
   incremented, as `c01204aa..04ae` does for the `c0120484` path? If not, how is
   the descriptor accounted when it returns via queue 24 → 32/34 → `c0120550`
   (which decrements [5])? Could [5] go negative, or wrap?
4. **Endpoint/direction.** Are these TX-data paths for MIDI IN (slot 4), or
   something else (EP0, RX-side refill using the TX table, zero-length packets)?
5. **Verdict.** Can either site submit a buffer while an earlier descriptor for
   the same slot is still DMA-owned? Answer yes, no or unknown, with the evidence.

Every claim needs an address, an excerpt of at most 8 lines, and a confidence
(confirmed / likely / guess). Pitfalls:
- `CALLP c016e0XX` is a function epilogue.
- Delay slots execute on both paths of a branch.
- `||` means the instruction runs in the same packet and reads old register values.
