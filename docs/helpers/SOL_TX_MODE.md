# Brief (Codex gpt-5.6-sol, medium): which TX slots use ring mode, and who starts the ring

Follow `docs/helpers/SAVE_PROTOCOL.md` exactly, including its Token economy section.
- Report: **`docs/helpers/SOL_TX_MODE_REPORT.md`**. Create it with the headings
  below and commit it. After every finding, commit THAT FILE ONLY.
- Scratch folder: `build/sol_txmode/`. This is static analysis only. Never touch the
  pedal, devices or any .exe, and never push. Do not edit any other file.
- Inputs: `build/fw/map/main.dis`, `build/fw/map/refs.txt` (MVK/MVKH constants),
  and names from `recon/map/chunk_*.md` (grep only).
- Read first: the "Claude review" block at the top of
  `docs/helpers/SOL_DIRECT_SUBMITTERS_REPORT.md`.

## Background
TX record N = `0xc011297c + 0x2a8*N` (the same address can also be formed as
`0xc0112c08 + 0x2a8*N - 0x28c`, or as `0xc0112984 + 0x2a8*N` for field [2]).
Field [2] selects the mode:
- 0 = counted mode: public enqueue `c0120f64`, completions decrement [5].
- nonzero = ring mode: the kick `c0120c44` starts when [9] == -1, and each
  queue-34 completion submits the next entry via `c0121960`/`c01219d0`. The ring
  lives at record+0x168, with [8] the length and [9] the index.

A first search found no direct store to field [2]. It may be written through a
computed base, a memset/memcpy (`c0167b00` = memset?), or a structure copy.

## Questions (one report section each)
1. **Writers of TX field [2].** Every store that can reach `0xc0112984 + 0x2a8*N`.
   Include: computed bases (any base plus offset whose sum is the record plus 8),
   stores via `*+Bx[2]` or `*Ax[2]` with a TX-record base, and bulk clears/copies
   over the TX table range `0xc011297c .. 0xc011297c+0x2a8*5`. Write a Python
   scan in your scratch folder that tracks the MVK/MVKH pairs and the ADD/SUB
   into the same register within about 20 lines; do not eyeball.
2. **Caller of the kick `c0120c44`.** It has no direct CALLP. Search for
   address constants `0x0c44` paired with MVKH `0xc0120000`, `.word 0xc0120c44`,
   and function-pointer tables. Who calls it, with what slot, and in what context?
3. **Ring setup.** Which routine fills the ring at record+0x168 and sets [8]? (Candidates:
   `c011fd40` clears it; `c01204b4`; `c01216c4`/`c01218d8` store [8]/[10].)
   What is the per-entry content: buffer pointers, lengths?
4. **Which slots use which mode.** For slot 4 (MIDI IN) and slot 1 (likely the ISO
   audio IN endpoint), state the mode with evidence, or "unknown".
5. **Verdict for USB audio.** Does a stock ring-mode TX path exist that an ISO IN
   stream could reuse (kick once, then completion-driven resubmit)? List what
   it requires (ring entries, [8], [10] length).

Every claim needs an address, an excerpt of at most 8 lines, and a confidence
(confirmed / likely / guess). Pitfalls:
- `CALLP c016e0XX` is a function epilogue.
- Delay slots execute on both paths of a branch.
- `||` means the instruction runs in the same packet and reads old register values.
- `[B0]`/`[!B0]`: state what B0 means before writing any truth table. Two of
  your earlier rows were inverted this way.
