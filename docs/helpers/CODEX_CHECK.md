# Brief for Codex: check Gemini's map work (start after 2026-10-13 20:30)

Run ONE job at a time:
`codex exec -m gpt-5.6-sol -c model_reasoning_effort=medium < /dev/null`
(medium for logic checks; low is fine for address/format checks). If Sol is
refused or fails, use gpt-6-astra. Follow `docs/helpers/SAVE_PROTOCOL.md`
(token economy: grep, windows of at most 60 lines).

Input: `docs/helpers/REVIEW_QUEUE.md` lists the files Gemini finished.
Static analysis only; never touch the pedal, USB devices, .exe files, or push.
Write findings to `docs/helpers/CODEX_REVIEW.md` (one section per file) and
commit only that file. Do NOT edit `recon/map/*`: Claude applies fixes later.

## What to check, in priority order
1. Every row Gemini raised to `confirmed`: re-derive each claim from
   `build/fw/map/main.dis`. Verdict per row: ok / wrong (give the correct
   statement and the instruction addresses) / unproven.
2. Every row whose function has predicated branches (`[B0]`/`[!B0]` pairs),
   conditional returns, or delay-slot loads: write the truth table.
3. A random 20% of rows raised to `likely`.
4. `tools/fwmap/check_rows.py`: does it verify what the brief says? Try 3 rows
   with deliberately wrong addresses and instructions.
5. Name clashes, or neighbour rows made inconsistent by Gemini's edits.

Finish each section with: "Checked N rows: ok A, wrong B, unproven C."
Mark the file as checked (with the date) in REVIEW_QUEUE.md.
