# Brief (Codex gpt-5.6-sol, medium): review and finish map chunk 15

Follow `docs/helpers/FWMAP.md` ("Pitfalls" especially) and
`docs/helpers/SAVE_PROTOCOL.md` (including Token economy) exactly.
- Your file: **`recon/map/chunk_15.md`** (177 rows, including 21 hidden starts;
  "Summary: TBD"; Data section empty). Commit THAT FILE ONLY after every 10
  reviewed rows. Scratch: `build/sol_c15/`. Static only; never touch the
  pedal, USB/MIDI devices or any .exe; never push.

## Tasks
1. **Review.** For every row, check 2 claims against `build/fw/map/main.dis`
   and `build/fw/map/refs.txt` (constants from refs.txt, not by hand). Fix
   wrong rows in place with "(corrected in review 2026-10-09)"; otherwise
   append "(reviewed)" to the evidence. Rows with conditions: write the truth
   table (condition -> return value / calls). Predicated-code traps:
   `[!B0] B X` / `[B0] B Y` pairs take exactly one; an ADDKPC in the delay
   slots turns a branch into a call; parallel `[A0] .. || [!A0] ..` both read
   the OLD A0. A CALLP to c016e000 ends a function.
2. **Host rows.** For each hidden start, check that its host's row describes
   only the host's own code (FWMAP pitfall "Host rows after a hidden start").
3. Fill **Summary** (one paragraph: subsystems in this range) and **Data**
   (globals/structures with roles). Keep both open-question sections; add a
   last line: "Review: N rows checked, M corrected."
