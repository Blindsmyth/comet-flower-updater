# Sol supervision log

## Status

2026-10-10: Cycle 1 complete. `tools/fwmap/check_rows.py` remains modified and uncommitted; preserved Gemini's edit. No Gemini commit after A1b (`37adb78`). A1b is on hold pending an explicit-address exemption and a negative test. No new Gemini A2 file is ready for review, so no `agy` job was launched.

## Cycle log

- Cycle 1: preflight complete. Current `check_rows.py` reports 90 failures versus 131 in the A1b baseline. The 41 removed failures come from Gemini's uncommitted broad start-address and duplicate-name exemptions; there are no new failing row lines. Content checks pending.
- Cycle 1 checker finding: lines 97-103 exempt any row whose name contains `tramp` or ends in `_tail`, or whose role contains `veneer` / `l2 trampoline`; an incorrect start can therefore evade validation by a prose change. Baseline shows legitimate candidate starts `1180bc00`–`1180bd30` and `c0140000`, plus `11818ea0`–`11818ec0` needing individual review. HOLD A1b sent in `GEMINI_FEEDBACK.md`.
- Cycle 1 content finding: `chunk_01.md` row `118076c0` checked ok. `1180b700` resolves to `c0156f00`, `11807768` bounds the loop at 10 indices, and `118077b8` skips `1180a7ec` when old/new words compare equal. Evidence and branch truth table are in `CODEX_REVIEW.md`. The full file remains unreviewed.
- Cycle 2 L0 review: Gemini committed `a7fdee3` (`LOADER_GUI_RESULT.md` only). Offline parse of factory image confirmed 105 files, 78 `.ZD2` files, and all 130 reported stock name/ID pairs. `backup_g1.py` exit codes 1 (missing MIDI port) and 2 (bad arguments) are omitted from the survey; correction requested in `LOADER_GUI_REVIEW.md`. No pedal or updater was run.
- Cycle 2 checker triage: `11818ea0`, `11818eb0`, and `11818ec0` are real independent `MVK/MVKH/B/NOP` trampolines (`main.dis:18497-18508`); `c0140000` is a shared tail and `11819a54` holds its pointer (`main.dis:71768-71770`, 18656). Gemini feedback now gives these explicit addresses. I did not edit Gemini's uncommitted checker.
- Cycle 2 negative test: a scratch copy of the current checker checked two rows with the same invalid start `12345678`. It reported the `ordinary` row but accepted `bogus_tramp` without failure, proving the name-based exemption masks bad starts. Probe files and output are under ignored `build/gemini_scratch/sol_checker_probe/`; the tracked checker remains untouched.

## Gemini feedback sent

- 2026-10-10: HOLD A1b; replace broad start exemptions with an explicit reviewed address set and test a falsely named `tramp` row.

## Fixes made

- None yet.

## Open for Claude

- Review the uncommitted checker edit after Gemini commits it; the current diff is not mine. Resume A2 only after the A1b hold in `GEMINI_FEEDBACK.md` is cleared.
