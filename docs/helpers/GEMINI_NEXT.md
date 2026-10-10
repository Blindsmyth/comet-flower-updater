# Brief for Gemini (agy): firmware-map work queue (2026-10-10)

Run, in the background (the owner authorised the flag):
`agy -p "Read docs/helpers/GEMINI_NEXT.md and do task A1" --dangerously-skip-permissions --model gemini-3.1-pro-high`
Do NOT use the agy-bridge MCP `delegate` (it times out at 600 s).

FIRST read `docs/helpers/GEMINI_FEEDBACK.md` if it exists (Sol, the reviewer,
writes corrections and HOLD orders there; obey them before anything below).
Read first: `docs/helpers/SAVE_PROTOCOL.md` (report/commit after every
finding, token economy), `docs/helpers/FWMAP.md` (table format, Pitfalls),
`docs/helpers/GUESS_PASS.md` (the pass procedure). Static analysis only: never
touch the pedal, USB/MIDI devices, any .exe, and never `git push`. Edit only
the files named per task. Scratch: `build/gemini_scratch/`.

## Your known weakness: read this
In earlier runs you traced code badly and filled gaps with plausible claims
(screens mislabelled, "EDMA unused", invented costs). Common code-reading
errors in this firmware: inverted `[!B0]`/`[B0]` branch pairs; code after a
`CALLP c016e000` epilogue folded into the wrong function; values loaded in
delay slots; MVKH typos (`0xc010...`); "no caller" for callbacks (check
`build/fw/map/refs.txt`); wrong scaled-index offsets. Therefore:
- Quote the instruction addresses and text you rely on, copied from
  `build/fw/map/main.dis`, never from memory.
- If you cannot show it in the code, leave `guess` and say what is missing.
  `guess` is a good answer. A wrong `confirmed` is the worst answer.
- Never raise to `confirmed` unless every claim in the row has a quoted line.

## Tasks, in order
**A1. Row checker** (a script; do this first).
Write `tools/fwmap/check_rows.py`. For every table row in `recon/map/*.md`
check (a) the row address is a function start in the fact sheets or a hidden
start with a row, (b) every 8-hex address cited in the evidence exists in
`main.dis`, (c) every quoted `addr MNEMONIC operand` snippet matches the
disassembly text at that address (normalise spacing), (d) no duplicate names
within a chunk. Write per-file failure counts and the failing rows to
`build/gemini_scratch/check_rows.txt`. Run it on all files and report the
counts; do not fix rows in this task. Test it by hand on 3 rows you break on
purpose. Commit only the script.

**A1b. Fix the row checker (Claude review of A1, 2026-10-10; do this before A2).**
`tools/fwmap/check_rows.py` reports ~430 failures, mostly false positives:
(c) compares quoted snippets to `main.dis` text exactly, but the disassembly
has unit suffixes (`LDW.D1T1`, `CLR.S2`), `||` prefixes, `[ B0]` predicates and
full operands, while the map quotes omit or annotate them (`A4=96`).
Normalise both sides (drop `.XXX` unit suffix, `||`, predicate; collapse
spaces) and require the same mnemonic and that the quoted operands are a
prefix of the disassembly operands. (b) flags MMIO/data addresses
(`01e27128`, `11800200`, `11f039b0`): only require presence in `main.dis`
for addresses inside the code range. Then run it on all files, and report
counts; real failures should drop to a number a human can read. Test by hand
on 3 deliberately broken rows (wrong mnemonic, wrong address, duplicate
name) in a scratch copy of chunk_05 and chunk_08 (which currently report 0,
confirm they are checked, not skipped). Paste the test results in your report.
Commit only the script.

**A2. Guess pass** per GUESS_PASS.md, one file at a time, in this order:
chunk_05, chunk_12, chunk_15, chunk_13, chunk_02, chunk_06, chunk_08,
chunk_09, chunk_04, chunk_14, chunk_17, chunk_11, chunk_10, chunk_03,
chunk_19, then 00_library_kernel (skip any row that also exists in a chunk
file; chunk rows win). After each file run `tools/fwmap/check_rows.py` and fix
every failure in rows you touched before moving on. Commit message:
`chunk_NN: guess pass <first>..<last>`. Finish each file with the line
"Guess pass <date>: N rows checked, M raised, K still guess." under Open
questions, and add a row for the file to `docs/helpers/REVIEW_QUEUE.md`
(rows touched, rows raised to confirmed, check_rows result).

**A3. Cross-chunk fixes** from chunk_16 Open questions: chunk_15 `c0162460`
(name) and `c01604a0` (caller). Read the code, fix the rows, note it.

**A4. res5 survey** (boot/update program, disassembly `build/codex7/boot.dis`;
the boot decision is already in `recon/25_boot_safety.md`). Make
`recon/map/res5_boot.md`: function starts (CALLP targets + code pointers),
size, callers, strings, MMIO bases, one-line role with confidence. Survey
only: default `guess`; do not claim roles you cannot quote.

## Do not
- Edit anything outside the task's files, or delete other helpers' text.
  Corrections go in the row plus a one-line note under Open questions.
- Run more than one agy job at a time against the repo.
- Rewrite `recon/map/chunk_*.md` wholesale; edit rows in place.

**E0. Effect candidate sheet** (offline, after A1b; may be interleaved with A2).
Read `docs/helpers/GEMINI_EFFECT_DESIGN.md` fully, then do its section 8.
That brief also tells you how any future effect must be designed so it cannot
brick the pedal or overrun slot memory; you stop at its gate G3.

**L0..L5. CF Loader GUI** (offline; independent of the map work, do after E0
or when A2 is on hold). Read `docs/helpers/GEMINI_LOADER_GUI.md` fully and
follow its task order. Install path = update-mode image only; no MIDI write
path may exist in the app.
