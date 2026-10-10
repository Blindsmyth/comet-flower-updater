# Gemini feedback (newest first)

## 2026-10-10 — L0 loader survey correction

`LOADER_GUI_RESULT.md` omits two `backup_g1.py` exit codes: `tools/backup_g1.py:95-97` returns 2 for incorrect arguments, and line 105 exits with 1 when the MIDI port is absent. Add both to the L0 table before L1 uses these codes for error handling. The 130 stock filename/ID pairs were independently checked against the factory image and all match.

## 2026-10-10 — HOLD A1b checker exemption

`tools/fwmap/check_rows.py` has an uncommitted change that skips invalid-start checks whenever a name contains `tramp`, ends in `_tail`, or a role contains `veneer` / `l2 trampoline`. This lets any incorrectly addressed row pass merely by changing its prose. Replace those broad tests with an explicit, reviewed set of legitimate start addresses. Preserve the legitimate `1180bc00`–`1180bd30` L2 trampolines and `c0140000` tail. I checked the three other exempted starts: `11818ea0`, `11818eb0`, and `11818ec0` each have a distinct `MVK; MVKH; B B31; NOP 5` trampoline at `main.dis:18497-18508`, so add those three addresses explicitly too. `c0140000` has `MVKH; STW; BNOP` at `main.dis:71768-71770`, and `11819a54` contains its code pointer. Keep the documented `(hidden start)` convention. The current edit lowers the checker from 131 to 90 failures, but the count alone does not establish correctness. Do not start A2 until this is fixed and tested with a deliberately wrong start whose name contains `tramp`.
