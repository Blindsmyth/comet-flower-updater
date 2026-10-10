# Codex firmware-map review

## chunk_01.md — in progress (2026-10-10)

| row | verdict | evidence |
|---|---|---|
| `118076c0` | ok | Task entry address is cited by recon/15. `118076f8 CALLP 1180b700` reaches `c0156f00` through `1180b700 MVK 0x6f00,B31; 1180b704 MVKH 0xc0150000,B31`; `11807764` increments index and `11807768 CMPGT 10,A10,A0` repeats while index < 10. `118077b6 CMPEQ A0,A4,A0; 118077b8 [A0] BNOP 118077c4,5; 118077c0 CALLP 1180a7ec` posts only when sampled words differ. |

Branch truth table for `118077b6`–`118077c0`: equal old/new word -> A0=1 -> branch to `118077c4` -> no `1180a7ec` call; unequal -> A0=0 -> call `1180a7ec`. This verifies the row's conditional post claim. Other branch logic in this function remains to be reviewed.

Review count so far: 1 row; ok 1, wrong 0, unproven 0. File review remains open.
