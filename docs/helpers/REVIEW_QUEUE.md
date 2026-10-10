# Review queue: helper work waiting for Codex

Gemini adds one row per finished file. Codex fills the last column.

| file | date | rows touched | raised to confirmed | check_rows result | Codex check |
|---|---|---|---|---|---|
| chunk_01 | 2026-10-10 | 90 (Sonnet helper) | not listed | not run | Claude spot-check: 2 of 2 ok; full check pending |
| chunk_16 | 2026-10-10 | 77 (Sonnet helper) | not listed | not run | Claude spot-check: 1 cross-chunk claim ok; full check pending |
