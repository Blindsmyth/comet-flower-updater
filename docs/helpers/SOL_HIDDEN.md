# Brief (Codex gpt-5.6-sol, medium): hidden-start clean-up pass, batch <B>

Follow `docs/helpers/FWMAP.md` (all of it, especially "Pitfalls" and "Host
rows after a hidden start") and `docs/helpers/SAVE_PROTOCOL.md` (including
Token economy) exactly. Static only; never touch the pedal, USB/MIDI devices
or any .exe; never push. Scratch: `build/sol_hidden/`.

## Input
`build/ghidra_test/hidden_norow.txt`: one line per hidden function start that
has no map row yet: `<addr>  chunk_NN  inside <host>`. Do only the lines
whose chunk is in your batch:
- batch A: chunk_00 .. chunk_04
- batch B: chunk_06 .. chunk_09
- batch C: chunk_10 .. chunk_16

`tools/fwmap/hidden_starts.py` misses prologue-less leaves, and some of its
candidates may be false (a prologue-like store inside a function). Check
each one: a real start has its own entry (a caller, a branch target, or an
address constant in refs.txt) or sits right after the host's return
(`BNOP B3`, `B B3`, or a CALLP c016e000 epilogue) plus padding.

## For each start
1. Read it. Add a row to `recon/map/<its chunk>.md` in address order, in the
   table format, with "(hidden start)" in the role. If it is NOT a real
   start, add no row; list it under that file's "Open questions" as
   "hidden_starts false positive: <addr> (<reason>)".
2. **Rewrite the host row** from the host's own code only: its real end, and
   only its own calls and callers (the fact sheet credits the hidden
   function's calls and callers to the host).
3. Commit only the chunk files you edited (`git add recon/map/chunk_NN.md`)
   after every 5 starts: `git commit -m "chunk_NN: hidden starts <addrs>"`.

Predicated code: write the truth table for any condition. `[!B0] B X` /
`[B0] B Y` pairs take exactly one; an ADDKPC in delay slots makes a call;
parallel `[A0] .. || [!A0] ..` both read the OLD A0. SPLOOPD ii=1 runs
ILC+4 times. Constants come from refs.txt.

Finish with one line per edited chunk under "Open questions":
"Hidden-start pass <date>: N rows added, M host rows rewritten, K false positives."
