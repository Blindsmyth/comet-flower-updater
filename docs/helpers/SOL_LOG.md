# Sol supervision log

## Status

2026-10-10: Began supervision from `SOL_SUPERVISE.md`. Preflight found `tools/fwmap/check_rows.py` modified and uncommitted; preserving Gemini's edit. No Gemini commit after the A1b checker commit (`37adb78`).

## Cycle log

- Cycle 1: preflight complete. Current `check_rows.py` reports 90 failures versus 131 in the A1b baseline. The 41 removed failures come from Gemini's uncommitted broad start-address and duplicate-name exemptions; there are no new failing row lines. Content checks pending.

## Gemini feedback sent

- None yet.

## Fixes made

- None yet.

## Open for Claude

- Review the uncommitted checker edit after Gemini commits it; the current diff is not mine.
