# Brief for Sol (gpt-5.6-sol): supervise and fix Gemini's work (written 2026-10-10)

Claude's quota is spent; the owner reset Codex, so Codex is available NOW
(the "after 2026-10-13" dates in CODEX_CHECK.md, the handoff and ROADMAP.md
are stale). You are the reviewer and corrector for Gemini (agy). Claude
returns later and will review YOU, so leave evidence for every change.

Run: `codex exec -m gpt-5.6-sol -c model_reasoning_effort=low < /dev/null`
for coverage work; `medium` for rows with predicated branches, conditional
returns or delay-slot loads (at low, 2 of 5 sampled rows had inverted
`[!B0]`/`[B0]` logic). Never high. ONE job at a time (two parallel Sol runs
hit the shared cap in 12 min). If refused or capped, use `gpt-6-astra`; if
that fails too, stop and write the state to SOL_LOG.md. If the cap hits
mid-job, the log must already say what is done.

Read first: `docs/helpers/SAVE_PROTOCOL.md` (token economy: grep, windows of
at most 60 lines), `docs/helpers/FWMAP.md` Pitfalls,
`docs/helpers/GEMINI_NEXT.md`, `docs/helpers/CODEX_CHECK.md`,
`docs/helpers/GEMINI_EFFECT_DESIGN.md`.
Static analysis only. Never touch the pedal, USB/MIDI, any .exe; never push.

## 0. First action
Create or append `docs/helpers/SOL_LOG.md` (sections: Status, Cycle log,
Gemini feedback sent, Fixes made, Open for Claude). After every finding
append a line and commit that file. Update it before starting each step.

## 1. One supervision cycle (repeat; a cycle is one codex job)
1. **Preflight.** `git status`: if a tracked file is modified and is not
   yours, Gemini may be mid-run; do not commit or revert it, wait or work on
   other files. `git log --oneline` since the last cycle; list Gemini commits
   (they carry `Co-Authored-By: Gemini` or an `A<n>` task prefix).
   Known at hand-off: Gemini had an uncommitted edit to `check_rows.py` adding
   start-address exemptions (names containing "tramp", ending `_tail`, role
   containing "l2 trampoline"/"veneer") and skipping `Duplicate name: see ...`.
   When it is committed, review it: the name-substring exemptions are loose
   and could hide a genuinely wrong start. Prefer an explicit address list.
   The baseline file was made from the committed A1b version, so exempted
   rows still appear in it; after a reviewed exemption, regenerate it.
2. **Mechanical check.** `python tools/fwmap/check_rows.py`; compare with
   `docs/helpers/check_rows_baseline.txt`. The baseline holds the failures
   that existed when A1b finished (about 150: 56 evidence addresses, 31 start
   addresses, 17 duplicate-name, about 25 snippet). **Any failure not in the
   baseline is a regression by whoever touched the row**: fix it if the fix is
   certain from the code, else restore the row's previous text
   (`git show <old>:file`) and note it in GEMINI_FEEDBACK.md.
3. **Content check** (the real review; the script only proves quoted lines
   match the disassembly, not that the claims follow from them):
   - every row raised to `confirmed`: re-derive each claim from
     `build/fw/map/main.dis`; verdict ok / wrong / unproven;
   - every row with predicated branches or conditional returns: write the
     truth table first, then judge the row;
   - a random 20 % of rows raised to `likely`;
   - neighbours made inconsistent by an edit (names, boundaries, duplicates).
4. **Correct.** You MAY now edit `recon/map/*.md` (this overrides the "do not
   edit" line in CODEX_CHECK.md, because Claude is away). Rules:
   - fix a row only with instruction addresses you quoted from `main.dis`;
   - if you cannot prove a claim, set the row back to `guess` and say what is
     missing: that is a correct fix; a wrong `confirmed` is the worst case;
   - one file per commit, message
     `chunk_NN: Sol review <date>: N ok, W wrong, U unproven`;
   - no mass renames or restructuring; no A5 work (merging duplicates, final
     FIRMWARE_MAP.md): that is Claude's, leave it.
5. **Baseline triage** (do after step 3, on a quiet cycle). For each baseline
   failure decide: checker limitation or real defect.
   - Hand-added trampoline and tail rows (chunk_02 `1180bc..` L2 trampolines,
     chunk_09 `c0140000`) are legitimate starts: add a documented exemption in
     `check_rows.py` (a small list, one comment each); do not delete rows.
   - `Duplicate name: see 00_library_kernel.md` rows are cross-reference
     placeholders: make the checker skip them.
   - Odd or unaligned evidence addresses (`11806c8b`, `c0169bff`): read the
     line; fix typos in the row, or exempt only when it is clearly a data
     constant. Snippet `CALLP` mismatches: find the real format difference
     (predicate or `||` placement) and fix the checker or the row.
   - Regenerate the baseline only when triage lowered it, and commit the new
     `check_rows_baseline.txt` in the same commit.
6. **Steer Gemini.** Append to `docs/helpers/GEMINI_FEEDBACK.md` (create it;
   newest entry on top): the concrete errors found (file, row, what was
   wrong, the rule it broke) and one-line standing rules. Gemini reads this
   file first (GEMINI_NEXT.md says so). Short and specific; quote addresses.
7. **Release or hold the next task.** Look at the Gemini queue (A2 files in
   order, A3, A4, E0). Let it continue to the next file only if the last
   file's review found at most 2 wrong rows per 50 `confirmed`; otherwise put
   "HOLD: redo <file>, rows ..." at the top of GEMINI_FEEDBACK.md. If you can
   run `agy` from your shell, start ONE job as GEMINI_NEXT.md says
   (background, `--dangerously-skip-permissions`, never the bridge `delegate`);
   if you cannot, write the exact command into SOL_LOG.md under "Open for
   Claude" for the owner to paste.
8. Update the last column of `docs/helpers/REVIEW_QUEUE.md` and SOL_LOG.md.

## 2. Gemini effect work (gates G0..G3 in GEMINI_EFFECT_DESIGN.md)
If Gemini has produced an effect design sheet, bench result or a `.ZD2`, you
are draft gate G4. Check, and record in `docs/helpers/<name>_REVIEW.md`:
- the sheet's arithmetic: state bytes <= 392, slot total <= 40 KiB with 1 KiB
  spare, hot table bytes, cycles loop by loop with trip counts;
- no mutable global or static, no libm, division, `switch` or non-inline
  call, table indices clamped, output and feedback clamped, guard prologue
  kept (compare with `effects/ratx/ratx.c`);
- the scorer and bench files were not edited to obtain the PASS
  (`git log -p` on `tests/host/*`);
- manifest id unique, `state_bytes` correct, `.ZD2.oversize` absent.
Verdict: "passes G1..G3" or "not yet", with reasons. Do NOT install, build
update images, or call the effect safe: only the owner's G5/G6 tests do that.
You may fix small, certain code defects in Gemini's effect files; anything
that changes the sound (filters, tables, oversampling) goes back to Gemini
through GEMINI_FEEDBACK.md or waits for Claude.

## 2b. Gemini loader GUI (`GEMINI_LOADER_GUI.md`)
Review each L-step against its section 4 safety list and section 7
acceptance. Must-check items: no MIDI port or write path in `tools/cf_loader`
(grep), no `.exe` launched, Build disabled by any red pre-flight, outputs never
overwritten, tools called as subprocesses (not re-implemented), nothing edited
outside its whitelist. Write `docs/helpers/LOADER_GUI_REVIEW.md`. Run the
pytest; never run backup/pedal tools or an updater.

## 3. Standing rules for you
- Cheapest check first: grep and 60-line windows, not whole-file reads.
- Do not trust Gemini's text, its row, or your memory of a function: re-read
  the instructions. Known traps: inverted branch pairs, code after
  `CALLP c016e000` folded into the wrong function, values loaded in delay
  slots, MVKH typos, "no caller" for callbacks (check refs.txt), scaled-index
  offsets.
- Stop and write to SOL_LOG.md "Open for Claude" (do not guess) when: a fix
  needs a decision about the boot/update program (res5) or the USB patch
  list; two helpers disagree and the code does not settle it; a Gemini commit
  touched files outside its task (undo it with `git revert`, never
  `reset --hard`, and note it).
- Never: push, rewrite history, delete other helpers' text, edit scorers or
  thresholds, run pedal tools.

## 4. What Claude does when it returns
Reads SOL_LOG.md and GEMINI_FEEDBACK.md, spot-checks 5 Sol-fixed rows (those
with predicated logic first), then A5 and Phase C code. Make that cheap:
every fix commit message names the file and row addresses, and SOL_LOG.md
lists them.

## 5. Extra job (2026-10-10): build the latest test updater
Do `docs/helpers/SOL_BUILD_UPDATER.md` Part A (build files only, never run the
exe) before the next supervision cycle; Part C is the honest MIDI status.
