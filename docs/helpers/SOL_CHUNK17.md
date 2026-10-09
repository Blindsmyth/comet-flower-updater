# Brief (Codex gpt-5.6-sol, low): continue map chunk 17

Follow `docs/helpers/FWMAP.md` (all of it, especially "Pitfalls") and
`docs/helpers/SAVE_PROTOCOL.md` (including Token economy) exactly.
- Your file: **`recon/map/chunk_17.md`** (67 rows so far). Fact sheet:
  `build/fw/map/facts/chunk_17.md`. Hidden starts:
  `python tools/fwmap/hidden_starts.py chunk_17`.
- Continue after the last row in the table (about c016bcc0), in address
  order. Every fact-sheet `## addr` and every hidden start gets a row.
- Commit THAT FILE ONLY after every 5-10 rows. Scratch: `build/sol_c17/`.
- Static only; never touch the pedal, USB/MIDI devices or any .exe; never push.
- When the table is complete: write the Summary paragraph, "Data" and
  "Open questions", then diff your rows against the fact sheet and the
  hidden-start list and fill any gap.

Pitfalls from your calibration: a CALLP to a c016e0XX epilogue ends a
function; delay-slot instructions run on both paths of a branch; take
constants from build/fw/map/refs.txt, don't compute MVK/MVKH by hand.
