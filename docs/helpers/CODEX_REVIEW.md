# Codex firmware-map review

## chunk_01.md â€” in progress (2026-10-10)

| row | verdict | evidence |
|---|---|---|
| `118076c0` | ok | Task entry address is cited by recon/15. `118076f8 CALLP 1180b700` reaches `c0156f00` through `1180b700 MVK 0x6f00,B31; 1180b704 MVKH 0xc0150000,B31`; `11807764` increments index and `11807768 CMPGT 10,A10,A0` repeats while index < 10. `118077b6 CMPEQ A0,A4,A0; 118077b8 [A0] BNOP 118077c4,5; 118077c0 CALLP 1180a7ec` posts only when sampled words differ. |
| `118086e4` | wrong boundary evidence; fixed | Evidence cited `11808823`, which is not an instruction address. `11808820 MVK 0,A4` and `11808822 BNOP B3,5` close this function; `11808824 STW B3,*B15--[2]` begins the next row. Replaced the range claim with those exact instructions. |

Branch truth table for `118077b6`â€“`118077c0`: equal old/new word -> A0=1 -> branch to `118077c4` -> no `1180a7ec` call; unequal -> A0=0 -> call `1180a7ec`. This verifies the row's conditional post claim. Other branch logic in this function remains to be reviewed.

Review count so far: 2 rows; ok 1, wrong 1, unproven 0. File review remains open.

## A1/A1b checker repair — 2026-10-11

Scope: check_rows.py, res5_boot.md, two A3 rows and their related notes in chunks 15/16, this report, REVIEW_QUEUE.md, and validate_boot_survey.py. Unrelated working-tree changes were left alone. No A2 chunk is fully verified by this run.

Boot selection now uses the res5_boot.md basename, boot.dis and independently extracted boot candidate starts; other files use main.dis, fact starts and hidden_starts.py output. Temporary copies must preserve the basename. Fixed the arbitrary `(hidden start)` bypass, missing quoted addresses outside code ranges, `0x` evidence scanning, operand-prefix token collisions (A1/A10), explicit predicate inversion, parallel `||` table parsing and `||^` normalization. Directives retain their leading dot and cannot be starts. Subprocess failures propagate; report directories are created; nonzero exit means failing rows. Existing main trampoline exceptions remain, but require an instruction. Omitted predicates remain accepted for legacy abbreviated quotes: this checker cannot prove prose, omitted operands, boundaries or semantics. Unquoted numeric evidence outside the selected code ranges may be data and is not rejected. Hidden starts missing from the heuristic require manual resolution, not arbitrary row self-authorization.

validate_boot_survey.py exercises temporary res5_boot.md, chunk_05.md and chunk_08.md copies: baseline plus wrong start, nonexistent in-range evidence address, wrong quoted mnemonic, duplicate name, nonexistent out-of-range quoted address and forged hidden-start label. Expected: each baseline succeeds and all six mutations per file fail with the intended diagnostic (21 file cases); two additional assertions reject A1/A10 prefix collisions and explicit inverted predicates. Fixture main rows use the known c01604a0 start deliberately; these tests prove routing/validation, not chunk ownership. No production map is mutated by the regressions.

## res5_boot.md / A4 — 2026-10-11

Replaced 496 generated rows with 802 explicitly uncertain candidate rows: 495 retained, 1 excluded (c022e458 is a .word directive), 307 added from pointer evidence. All 802 have guess confidence and a quoted target instruction. Script covers exact row content, candidate completeness under the extraction rule, all 1,414 CALLP source edges, 43 literal .word pointer edges and 523 materialized-pointer edges from bootrefs.txt. These are source-site counts, not unique caller functions. The row checker reports zero failing boot rows.

Removed every unsupported size, nearby printable-fragment string association and interval-owned MMIO claim. Sizes are uncertain, strings unverified and MMIO unassigned. Candidates must be in a declared TEXT section and decode as an instruction, but TEXT itself contains data: materialized pointers and literal words do not prove function starts. This inventory intentionally preserves that uncertainty rather than inventing roles. It is not a complete set of boot functions; indirect transfers, branch-only entries and tables decoded as instructions can escape extraction. bootrefs values are tool-produced candidates, not independently proved pointer uses.

Manual sample (six old target records, instruction windows plus provenance):
- c01f4000: MVK 15,B0 then SHL B0,0x15,B0; scaled LDW at c01f400c. First CALLP c01f40b4; 20 direct sites script-counted. No boot role promoted.
- c01f4550: MVK 0,A4; c01f4552 BNOP B3,5; next code c01f4554. Old size 6 was unjustified; visible return is at +2 (two compact instructions).
- c01f6114: literal pointer c022de0c; starts MVK 12,A6 and ADD A5,A6,A6, then a conditional branch at c01f611a. Pointer provenance verified; function entry remains unproven.
- c022be80: two CALLPs c022be84/c022be88, restore B3 at c022be90, return c022be98 BNOP B3,5. Old size 9688 crosses the visible return and is rejected.
- c022e458: .word 0x10000401; incoming .word at c022e574 does not establish an executable start. Excluded.
- c0229de0: bootrefs source c01f4650 B0; repeated PACK2 and branch-looking data illustrates why instruction decoding alone cannot prove code. Kept only as an uncertain candidate, not a named function.

Checked 6 manual records: ok 0, wrong 3 (two sizes and one claimed start), unproven 3. All 802 replacement rows mechanically checked; their semantic roles and full extents remain unproven. No strings or MMIO roles are verified in this survey.

## chunk_15.md / A3 — 2026-10-11

c0162460: old audio name correctly rejected, but replacement `rts_stream_buffer_fill` and confirmed status were unsupported. Renamed rts_stream_buffer_configure, guess. c0162474 loads fp word 0; c0162488 compares it with -1. c0162462 tests mode A6==4; c0162468 forces B5=0 for that mode; c0162478 otherwise computes B5=(B6==0). c016248e ORs these rejection predicates; c0162490 branches to c01625cc. A11 starts -1 at c0162464 and becomes return A4 at c01625d0. Successful setup stores buffer state at byte offsets 4/8/12/16 and flags at 20; c0162548 branches toward allocation helper c0169f20. A fill/read operation is not established. Exact API, allocator semantics and flags remain unresolved.

Truth table for the entry gate:
| fd == -1 | mode == 4 | B6 == 0 | c0162490 |
|---|---|---|---|
| yes | either | either | reject, return -1 |
| no | yes | either | continue |
| no | no | yes | reject, return -1 |
| no | no | no | continue |

On continuation, fp buffer word at byte offset 4 is zero -> c01624a0 branches to c0162524; nonzero -> existing-buffer path. This is not a mode==4 branch. Later predicates were read to constrain naming, not fully verified as an API specification.

c01604a0: caller correction is correct: sole literal CALLP found is c0168d88, inside c0168d00. Whole main.dis search finds two branches into c0162460 (c0166430 and c01689b0). Decoded refs.txt contains no materialized reference to either target; absence does not rule out indirect calls. Corrected the unsupported no-match early-return claim and downgraded to likely. Located MMIO base construction: c01605b4 MVK 0x0104,A5 plus c01605c4 MVKH 0x1800000,A5 gives 01800104.

Scan truth table: c01604e0 equal -> A0=1 -> c01604ee sets B4=0 -> c01604f0 B0=0 terminates scan. Unequal -> index A5 increments and B5 decrements; B0 follows remaining count. Exhaustion also terminates into c0160500, with no early return. IER mask is (1<<index)&0xffff (c0160512/c0160514); index 16 therefore clears no bit, but the function continues writing fields.

Field-mode truth table from B8 word 4 at c0160540: 0 -> branch c01605a0, clear destination halfwords at byte offsets 4/6 in delay slots; 1 -> write 0xffff to both; 3 -> copy LDHU source offsets 36/38 to destination offsets 4/6; other -> write A9 mask to both. c0160564 and c0160570 change B0 for mode 1; treating them as the original predicate would invert the result. Later vector access at c01605f8 executes only for unsigned index 4..15 (CMPGTU 4,A4 and CMPLTU 15,A4 combined into B0; [!B0] load). Full interrupt-controller semantics remain unverified.

Checked 2 rows: ok 0, wrong 2, unproven 0 (verdicts on old claims; replacement roles retain explicit uncertainty). No other chunk_15 semantic claims were certified.

## chunk_16.md / A3 adjacency — 2026-10-11

Checked the caller/target claims in c0166380, c0168940 and c0168d00 only. Corrected stale buffer-fill/name wording and appended a superseding cross-chunk note. c0168d30 slot==0 -> c0168d48 branch to c0168d78 with vector branch c0168d58 in the delay sequence; occupied slot -> error dispatch c0168d54 then vector branch c0168d6c. Both converge on c0168d88. c0168da2 tests returned status: zero -> [!A0] c0168da8 returns saved zero; nonzero -> default 2 from c0168da4. Detailed scheduler/delay semantics and the whole FILE helper rows are not fully verified here.

Checked 3 restricted caller/target claims: ok 3, wrong 0, unproven 0. This does not certify all claims in those three rows or the remainder of chunk_16.

## Final mechanical coverage — 2026-10-11

Full checker: 169 failing rows; 183 diagnostics. Exit 1 is expected while unresolved map failures remain. Per-file failing-row counts: 00_library_kernel.md=0, chunk_00.md=33, chunk_01.md=17, chunk_02.md=26, chunk_03.md=23, chunk_04.md=5, chunk_05.md=0, chunk_06.md=1, chunk_07.md=1, chunk_08.md=8, chunk_09.md=2, chunk_10.md=12, chunk_11.md=5, chunk_12.md=0, chunk_13.md=0, chunk_14.md=5, chunk_15.md=10, chunk_16.md=15, chunk_17.md=1, chunk_18.md=0, chunk_19.md=5, res5_boot.md=0. Detailed diagnostics: build/gemini_scratch/check_rows.txt. Counts include stricter-start/confidence findings requiring review, not necessarily proven semantic defects. Boot checker exit 0; regression/survey validation must exit 0. No A2 full-verification claim.

## Mechanical follow-up â€” 2026-10-11 (supersedes the 169-row count)

Full check_rows.py now exits 0: every main-map file and res5_boot.md reports zero failures. coverage.py now counts names despite literal pipes in role prose: **2790 of 2790 extracted main-image starts named** (1415 confirmed, 1340 likely, 35 guess). This is coverage of the extractor's CALLP/pointer start set, not proof that no other starts exist. The 802 boot survey rows remain guess candidates, not verified boot functions.

Checker repairs distinguish source spans from instruction sites, accept equivalent numeric spellings, parse literal pipes in role text, require valid identifier names, and recognize starts immediately after visible returns, including the c016e000 restore helper and its 1180bcc0 veneer. Three unusual starts have separate instruction/pointer evidence checks: c0165020, c01687c0, 118164c0. Direct disassembly corrections include 11800400's scaled word index (byte offset 0x180, not 0x60), 11803804's equality-gated scratch clear (the old branch interpretation was inverted), and wrong instruction sites in chunks 00/02/03/04/07/10/11/14. Cross-reference markers, literal source ranges, and the non-code 11819820 data table no longer masquerade as invalid functions. Three ELF rows in chunk_10 and 28 malformed hidden-start name fields now have identifiers.

validate_boot_survey.py: 27 temporary-file cases plus 8 matcher/start assertions passed. git diff --check passed. The checker still cannot prove prose, omitted operands/predicates, complete function extents, or boot roles; full semantic review of the guess-pass chunks remains open. Detailed current diagnostics are in build/gemini_scratch/check_rows.txt.