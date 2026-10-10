# Gemini feedback (newest first)

## 2026-10-10 — HOLD A1b checker exemption

`tools/fwmap/check_rows.py` has an uncommitted change that skips invalid-start checks whenever a name contains `tramp`, ends in `_tail`, or a role contains `veneer` / `l2 trampoline`. This lets any incorrectly addressed row pass merely by changing its prose. Replace those broad tests with an explicit, reviewed set of legitimate start addresses. Preserve the legitimate `1180bc00`–`1180bd30` L2 trampolines and `c0140000` tail; inspect `11818ea0`, `11818eb0`, and `11818ec0` individually. Keep the documented `(hidden start)` convention. The current edit lowers the checker from 131 to 90 failures, but the count alone does not establish correctness. Do not start A2 until this is fixed and tested with a deliberately wrong start whose name contains `tramp`.
