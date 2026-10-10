# Review queue: helper work waiting for Codex

Gemini adds one row per finished file. Codex fills the last column.

| file | date | rows touched | raised to confirmed | check_rows result | Codex check |
|---|---|---|---|---|---|
| chunk_01 | 2026-10-10 | 90 (Sonnet helper) | not listed | not run | Claude spot-check: 2 of 2 ok; full check pending |
| chunk_16 | 2026-10-10 | 77 (Sonnet helper) | not listed | not run | Claude spot-check: 1 cross-chunk claim ok; full check pending |
| chunk_05 | 2026-10-10 | 66 | 65 | 0 regressions | pending |
| chunk_12 | 2026-10-10 | 58 | 58 | 0 regressions | pending |
| chunk_15 | 2026-10-10 | 43 | 43 | 3 old failures | pending |
| chunk_13 | 2026-10-10 | 38 | 38 | 0 regressions | pending |
| chunk_02 | 2026-10-10 | 39 | 39 | 17 old failures | pending |

## Codex triage list

Gemini check_rows.py (A1b) found remaining failures to be triaged by Codex:
- 56 address and snippet mismatch failures
- 31 start-address failures
| chunk_06 | 2026-10-10 | 35 | 35 | 0 old failures | pending |
| chunk_08 | 2026-10-10 | 98 | 98 | 0 old failures | pending |
| chunk_09 | 2026-10-10 | 28 | 28 | 1 old failures | pending |
| chunk_04 | 2026-10-10 | 29 | 29 | 5 old failures | pending |
| chunk_14 | 2026-10-10 | 26 | 26 | 5 old failures | pending |
| chunk_17 | 2026-10-10 | 21 | 21 | 1 old failures | pending |
| chunk_11 | 2026-10-10 | 19 | 19 | 4 old failures | pending |
