# Brief: accuracy pass on "guess" rows

Follow `docs/helpers/FWMAP.md` (all of it, "Pitfalls" especially) and
`docs/helpers/SAVE_PROTOCOL.md` (including Token economy). Static only; never
touch the pedal, USB/MIDI devices or any .exe; never push. Scratch:
`build/guess_pass/`.

## Task
In the file(s) named in your task, take every row whose confidence is
`guess` (and every `unk_*` name). For each:
1. Read the function's own code (from its address to its real return; watch
   for hidden starts) and its callers (CALLP grep in main.dis, plus refs.txt
   for address constants: a function with no CALLP caller is usually a
   callback or table entry).
2. Rewrite the row: a real name (subsystem prefix), what it does, evidence
   with instruction addresses. Raise the confidence only when the code
   supports it: `confirmed` = unambiguous from the code; `likely` = the code
   plus context; leave `guess` if it is still unclear, and say what is
   missing.
3. If a row is wrong in a way that affects its neighbours (a hidden start, a
   wrong boundary), fix both rows and say so.
4. Commit only the file you edit after every 10 rows:
   `git add recon/map/<file>; git commit -m "<file>: guess pass <first>..<last>"`.

Predicated code: write the truth table for any condition. `[!B0] B X` /
`[B0] B Y` pairs take exactly one; an ADDKPC in delay slots makes a call;
parallel `[A0] .. || [!A0] ..` both read the OLD A0; SPLOOPD ii=1 runs ILC+4
times. Constants come from refs.txt. A CALLP to c016e000 ends a function.

Finish with a line under the file's Open questions:
"Guess pass <date>: N rows checked, M raised to likely/confirmed, K still guess."
