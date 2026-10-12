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
| chunk_10 | 2026-10-10 | 16 | 16 | 9 old failures | pending |
| chunk_03 | 2026-10-10 | 14 | 14 | 18 old failures | pending |
| chunk_19 | 2026-10-10 | 6 | 6 | 3 old failures | pending |
| 00_library_kernel | 2026-10-10 | 194 | 2 | 0 old failures | pending |

## Scoped Codex repair/check — 2026-10-11

| scope | coverage | status |
|---|---|---|
| A1/A1b checker | Boot/main routing; 21 temporary-file regression cases plus 2 matcher assertions | Repaired; detailed results and limitations in CODEX_REVIEW.md |
| A4 res5_boot | 802 guess candidates, all rows reproduced from sources; 6 manual records | 0 checker failures; semantic roles, extents, strings and MMIO unresolved |
| A3 chunk_15 | c0162460 and c01604a0; predicate tables and caller sources | 2 old rows corrected; guess/likely; remaining chunk review pending |
| A3 chunk_16 | 3 caller/target claims and stale adjacency wording | Restricted checks only; full row/chunk review pending |
| A2 guess-pass chunks | Mechanical checker only | All full semantic reviews remain pending |

The older 56/31 triage totals above are superseded by the dated per-file counts in CODEX_REVIEW.md; build/gemini_scratch/check_rows.txt contains current diagnostics. A nonzero global checker result remains unresolved, not waived.

## Mechanical queue update â€” 2026-10-11

The 56/31 triage totals and the later 169-row result above are intermediate snapshots. The current full checker reports zero failures; build/gemini_scratch/check_rows.txt has the latest per-file results. This closes the mechanical queue only. Full semantic review and boot-function proof remain pending; see the superseding follow-up in CODEX_REVIEW.md.