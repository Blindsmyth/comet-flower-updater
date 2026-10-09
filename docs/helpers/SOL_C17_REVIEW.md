# Brief (Codex gpt-5.6-sol, medium): review chunk 17 predicate logic

Follow `docs/helpers/SAVE_PROTOCOL.md` (including Token economy) exactly.
- Your file: **`recon/map/chunk_17.md`**. Edit rows in place; commit THAT
  FILE ONLY after every 5 corrected rows. Scratch: `build/sol_c17r/`.
- Static only; never touch the pedal, USB/MIDI devices or any .exe; never push.

## Why
A low-effort pass mapped rows c016bcc0..end. Claude sampled 5 of them and
2 had the logic inverted or wrong (now fixed: c016c3c0, c016d8c0; plus
c016b0c0 from an earlier pass). The errors are all in **predicated code**:
- `[!B0] B X` and `[B0] B Y` in consecutive packets: exactly one is taken;
  the 5 delay slots after each run on that path. An `ADDKPC` in delay slots
  makes the branch a call that returns to the ADDKPC address.
- `[A0] CMPGT 0,A3,A0 || [!A0] MVK 1,A0`: both read the OLD A0.
- Conditional MVKs that set the return value A4 on one path only.

## Task
For every row after c016bcc0 whose role states a condition (if / when /
otherwise / clear / set / returns X or Y / gate / guard), re-read the code
and write out the truth table (condition -> return value / calls made).
If the row is wrong, rewrite role and evidence, and add
"(corrected in review 2026-10-09)". If it is right, append "(reviewed)" to its
evidence. Skip rows already marked "Claude review". Finish with a line under
"Open questions": "Review: N rows checked, M corrected."
