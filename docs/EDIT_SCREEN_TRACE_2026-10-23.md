# Edit screen trace, live over CF Probe (2026-10-23)

Goal: groundwork for our own menu / edit-page system (owner, 2026-10-23). Method: RAM snapshots
(`build/probe/snap.py`, 372 KiB) between owner actions on Updater 30, diffed with
`build/probe/diff.py` (noise list applied), then the disassembly (`build/codex6/main-all.dis`) for the
code that touches each cell. Patch: CFM Pre, CF Delay, CF Watt, CF Rotary, CF Delay.

## UI state cells (confirmed live)

| Cell | Meaning | Evidence |
|---|---|---|
| `c011acf0` + 4*n, n = 0..4 | edit page per slot, 0-based (PAGE 1/4 = 0) | p1 -> p2 -> p3: 0 -> 1 -> 2; reset to 0 when the selected effect changes |
| `c011abf4` | selected slot, 0-based | slot 1 -> 2 -> 3: 0 -> 1 -> 2 |
| `c011abe4`..`c011abfb` | 24-byte UI struct around it (cleared by c012fc18, `c0167b00(p, 0, 24)` = memset) | |
| `11811900`.. 4 words | window of slot indices that follows the selection (0,1,2,3 -> 1,2,3,4 -> 2,3,4,0) | |
| `118115b8`, `11811940`, `11811cc8` | three copies of the edited param value (FRate 35 -> 40 on knob 1, page 3) | knob turn |
| `118123a8`.. | patch buffer rewritten on edit: the 5 effect IDs (07000f91 08000f8b 04000f81 06000f8a 08000f8b), tags `TXJ1`/`TXE1`/`EDTB`/`PPRM` | knob turn |
| `c011ac00`..`c011ac5f` | column-major glyph bytes that change with the page (rendered value / label text cache) | p1/p2/p3 |

## Page helpers (c015acec..c015addc)

- `c015ad3c`: change page with wrap/clamp: `page[slot] += delta`, limited to `0..c016f650(...)` (page count).
- `c015ad8c` (slot) -> `page[slot]`; `c015ad98` the same, clamped by `c016f650`.
- `c015adb4` (slot): `page[slot] = 0`; `c015adc8`: reset all 5.
- Callers of `c015ad98` (get page): **c012e340 (inside c012e330, the `%1d/%1d` page counter of the S7
  edit-screen lead: now confirmed as the live edit screen)**, c012f330 / c012f3f4 / c012f410 (param index
  math: `page * per_page + column (+2)`, i.e. knob -> param), c015ae3a.
- Callers of reset-all `c015adc8`: c012fc54 (on a change of the selected slot, reads `c011abf4`),
  c012fd64, c012ffc8, c01344c8, c0134748, c015ae20.

## What this means for our own edit page

- The S7 chain (c013c060 row dispatch -> c012e5a8 row render hub -> c012dca4 name, c012e164,
  c012e330 page counter; labels by c013a2d8 with the 5x7 font, column table 0xc0181508) is the
  live edit screen.
- An overlay can read `c011abf4` (which slot), `c011acf0[slot]` (which page) and the effect ID from the
  patch buffer, and redraw the page for CF effects only, from the UpdateUI hook we already use.
- Owning the knobs (more than 3 per page, sub-pages, routing pages) means taking over the c012f3xx
  knob -> param mapping; the page count comes from `c016f650`.

## Open
- The screen-id cell that says "the edit screen is showing" (vs SETTING / tuner): not taken live yet
  (the SETTING chooser mechanism is c0149664 / descriptor table c01495c0).
- `c016f650` (page count) and `c016f640` arguments; `c012ee80` (per-param visibility test?) in the
  c012f2e4 loop.
