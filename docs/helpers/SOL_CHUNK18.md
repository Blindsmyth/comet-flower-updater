# Brief (Codex gpt-5.6-sol, medium): map chunk 18

Follow `docs/helpers/FWMAP.md` (all of it, especially "Pitfalls") and
`docs/helpers/SAVE_PROTOCOL.md` (including Token economy) exactly.
- Your file: **`recon/map/chunk_18.md`** (new; create it first with the
  header `# chunk_18: <range> (68 functions)`, a Summary line, the table
  header, and empty Data / Open questions sections). Fact sheet:
  `build/fw/map/facts/chunk_18.md`. Hidden starts:
  `python tools/fwmap/hidden_starts.py chunk_18` (4: c016e1e0, c016e520,
  c016e7e0, c016ebc0).
- Map every fact-sheet `## addr` and every hidden start, in address order.
  This range holds the c016e0XX save/restore helpers and c016fXXX
  trampolines: name them from their own code.
- Commit THAT FILE ONLY after every 5-10 rows. Scratch: `build/sol_c18/`.
- Static only; never touch the pedal, USB/MIDI devices or any .exe; never push.
- When the table is complete: write the Summary paragraph, "Data" and
  "Open questions", then diff your rows against the fact sheet and the
  hidden-start list and fill any gap.

Pitfalls from your calibration: a CALLP to a c016e0XX epilogue ends a
function; delay-slot instructions run on both paths of a branch; take
constants from build/fw/map/refs.txt, don't compute MVK/MVKH by hand.

Predicated code (the errors in the chunk 17 low-effort pass): for any row
that states a condition, write the truth table (condition -> return / calls)
in the evidence. `[!B0] B X` / `[B0] B Y` pairs: exactly one is taken, and
an ADDKPC in the delay slots turns the branch into a call. Parallel
`[A0] ... || [!A0] ...` instructions both read the OLD A0.
