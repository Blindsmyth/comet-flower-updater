# FW RND S7: Locate the LCD effect-edit screen

## Status
running

## Findings

### Finding 0: scope check against S5 before starting
Read `docs/helpers/FW_RND_S5_MENU_2026-10-22.md` in full first, per the job brief. S5's
conclusion: `11807eb8`/`11808360`/`118082f8` (the `fxparam_page_size`/`fxparam_row_text`
cluster) are reached ONLY from the MIDI/USB SysEx string builder `11803514` (via
`1180af60`/`1180af8c`), never from `UpdateUI`/`MainApp`; the real on-screen effect-param
draw function was explicitly "not found" by S5. This job starts from a different
approach the brief itself suggests: `tools/fwmap/subsystems.py`'s output
(`build/fw/map/subsystems.tsv`), which tags each function with the set of SYS/BIOS task
roots that reach it via **direct** CALLP/B edges (separately from "pointer-only"
functions reached only through tables). Confidence: confirmed (own read of S5's report
and its Finding 4/caveat).

### Finding 1: c012afe0 (the 56-byte param descriptor accessor) has a direct UpdateUI-reachable path, separate from S5's MIDI-only cluster
`grep -n '^c012afe0' build/fw/map/subsystems.tsv` → `c012afe0	40	15,16,18	MIDI,MainApp,UpdateUI`.
This is the SAME function S5 Finding 3 confirmed holds the 56-byte param record (label at
byte offset 0). Unlike `11807eb8` (empty roots field = pointer-only / MIDI-table-reached
per S5), `c012afe0` is tagged `UpdateUI` by subsystems.py's direct-call BFS, meaning there
is at least one call chain of plain CALLP/B edges from the UpdateUI task entry
(`c013c754`) down to `c012afe0` that does **not** pass through the MIDI SysEx dispatcher
S5 ruled out. This is the concrete new lead the brief asked for. Confidence: confirmed
(subsystems.tsv is generated from the same coverage/call-edge data facts.py uses; the
tool's docstring explicitly distinguishes direct-edge roots from pointer-only).

### Finding 2: the hub is c012e5a8=ui_row_render_dispatch; it fetches the param descriptor directly and renders name/type/table-value/page-counter, with the literal strings "Dummy" and "%1d/%1d"
Walked callers of `c012afe0` in `build/fw/map/facts/chunk_*.md` (`grep -rn 'c012afe0'`).
Among ~30 call sites, one function's call list stood out:
`c012e164=ui_row_render_table_value` (`chunk_05.md:34-36`, size 460) calls
`c012afe0=usb_desc_table_get` **and** `c012ee80=usb_desc_or_table_fetch` — the exact
same pair S5's Finding 2 decoded as "fetch param descriptor `idx`, then test bit
`(15+idx)` of its 64-bit flag word at descriptor+48" — plus font/gfx primitives
`c011c508` and `c011e4b4`. Its only caller is `c012e5a8=ui_row_render_dispatch`
(size 1752, `chunk_05.md:83-85`), which also directly calls `c012afe0` itself and three
siblings:
- `c012dca4=ui_row_render_name` (size 688) — **`strings: Dummy`** (`chunk_05.md:21-24`).
  This is the exact placeholder label the corpus survey (F2) found padding stock 2-slot
  effects' 9-knob list; finding it hard-coded inside a row-NAME renderer is strong
  corroboration this is a real per-param-row text draw, not formatting for a MIDI
  message.
- `c012e010=ui_row_render_type2` (size 340).
- `c012e330=ui_row_render_page_counter` (size 120) — **`strings: %1d/%1d`**
  (`chunk_05.md:38-41`), i.e. a literal "page/total" format string, calling
  `c015ad98=usbdesc_page_count_helper` for the count.
Confidence: confirmed (direct read of each function's `calls`/`strings` line in the
fact sheets; the descriptor-fetch and bit-flag-48 pairing independently matches S5
Finding 2's own disassembly-level decode of `c012ee80`, so this is not just a name
coincidence).

### Finding 3: c012e5a8 has exactly two static callers — one USB, one a generic on-screen "row commit" path reached via a small per-row-kind jump table
`grep -n '^c012e5a8' build/fw/map/subsystems.tsv` and the chunk_05 facts entry
(`chunk_05.md:83-85`) agree: callers are `c01359e4=usb_ctrl_setup_common_decoder` and
`c013c044=ui_row_commit_render`. The first is USB-side (name and its own facts entry
both point to USB control-transfer handling), not our target. The second,
`c013c044` (`chunk_08.md:307-309`, size 28), is called by exactly one function,
`c013c0ba=ui_menu_row_handler_39c` (`chunk_08.md:367-...`), which is one of a row of
tiny table-entry veneers (`c013c090`..`c013c0ba`) whose addresses are each stored at a
4-byte-stride table around `0xc018439c..0xc01843b8` (`ptr@` lines, `chunk_08.md:316-338`,
cross-checked against `build/fw/map/refs.txt`). Sibling veneers in the same table go to
`tuner_calib_screen_draw` (`c0154878`), `ui_check_and_fallback_draw` (`c016aa88`),
`ui_value_row_draw_dispatch` (`c01595e4`), and three `ui_row_commit_wrap_*` functions —
i.e. this is a **generic "row kind" dispatch table** used by more than one on-screen
list (tuner calibration rows, value rows, etc.), and `ui_row_commit_render`
(slot `0x39c`) is the row-kind that renders from the param-descriptor engine (Finding 2).
Caveat: `0xc0184398` and `0xc01843bc/c0`, immediately adjacent to this table, hold
unrelated `ramp_curve_arm_*` function pointers (`chunk_12.md:395-417`) — the C6000
compiler packs multiple switch-jump-tables back to back in `.switch`, so this table's
exact entry count/bounds were read from the `ptr@` hits only, not independently bounds-
checked against a loop instruction; **likely**, not confirmed, that the table is exactly
the 8 entries `0x39c..0x3b8`.

### Finding 4: three static callers reach the row-dispatch table; none is confirmably "turn a knob on a loaded effect"
The table-indexing function is `c013c060=ui_menu_row_dispatch` (`chunk_08.md:311-314`,
subsystems.tsv roots **MIDI,UpdateUI**). Its three callers (facts + subsystems.tsv):
- `c013c0c8=ui_menu_row_dispatch_locked` (roots **UpdateUI**) — called by
  `c013c54c=ui_settings_screen_build` and `c013c6f8=ui_settings_screen_dispatch`
  (both roots UpdateUI, `chunk_08.md:427-459`).
- `c013c914=midi_edit_ui_row_dispatch_locked` (roots MIDI) — called by
  `c0128b00=midi_edit_ui_refresh` <- `c0128b48=midi_param_edit_coordinator`
  (`chunk_04.md:93-101`) — this looks like the on-screen "assign a MIDI CC to a
  parameter" editor, which also needs to show param names, hence reuses the same
  renderer.
- `c013c948=ui_menu_row_dispatch_wrap` — called by `c0135b14=mainapp_rhythm_menu_popup_sub`,
  `c0135c00=mainapp_menu_popup_open`, `c01363cc=mainapp_screen_draw_variant`,
  `c0157a38=mainapp_settings_rows_commit_dispatch` (`chunk_06.md:623-669`,
  `chunk_14.md:35-42`) — all Rhythm-menu-popup / Settings-field-commit machinery;
  `c0157ae8=mainapp_settings_field_commit` (caller of the last one) itself calls
  `c0149664=ui_active_item_switch`, the SAME screen-descriptor switcher S5 Finding 5
  confirmed drives the Settings/Chooser screens — corroborating that this branch is the
  gear-icon Settings system, not a per-effect edit screen.
None of these three names or call contexts ties to "the 4 physical parameter knobs edit
the currently loaded effect in Stomp/Play mode." This chain is a materially better
candidate than S5's (it is UpdateUI-direct per Finding 1, not MIDI/USB-table-only), but
it is **not** a confirmed trace to the knob-turn trigger. Confidence: confirmed (call
edges); **not found** (the knob-turn -> screen trigger itself).

### Finding 5: label font — c012dca4 draws through c013a2d8=ui_text_draw_centered_6px, whose only callee is the SAME font function Argon/S5 already confirmed (c011d4d8, 5x7, 6px pitch)
`c012dca4=ui_row_render_name`'s calls list (`chunk_05.md:23`) includes
`c013a2d8=ui_text_draw_centered_6px`. That function's own facts entry
(`chunk_07.md:581-585`) shows it has exactly **one** callee: `c011d4d8=unk_d4d8` — the
font function `MENU_RE_ARGON_2026-10-16.md` independently confirmed (and S5's Answer (b)
cited) as the 5x7 glyph set at 6px pitch, single line. Read `c013a2d8`'s own 80-byte
disassembly directly (`main.dis:63700..63728`): it walks a string with a byte-fetch loop
(`SPLOOPW`, `LDB.D1T1 *++A4[1],A3`) then does `MVK.L2 3,B1 ; MPYLI.M2 B1,B0,B1:B0`
(multiply the scanned length by 3) before combining it with the caller-supplied width
(`SUB.L2 B7,B0,B0`) — i.e. "half of 6px per character" used as a centering offset,
which matches the function's own `_6px` name and Argon's figure. Confidence:
**confirmed** that `c013a2d8`'s only callee is the Argon-confirmed font function;
**likely** (not fully hand-verified) for the `x3 = half-of-6px` centering-math reading,
since `SPLOOPW` software-pipelined loop epilogues are easy to misread (the brief's own
pitfall list) and I did not step through every pipeline stage.

### Finding 6: the specific column pixel width / max-label-chars for THIS row renderer is not located (open, same gap as S5's Answer (b), narrowed but not closed)
Traced the call site of `c013a2d8` inside `c012dca4` (`main.dis:46492..46499`): the
width/box argument fed into it (register B4 at the call) is loaded from
`ADDAW.D2 B15,0x4,B4` (a stack-frame address, i.e. a local buffer), not a bare
immediate, and an earlier value of the same register chain was built from
`MVK.S1 0x1508,A15 ; MVKH.S1 0xc0180000,A15` (pointer `0xc0181508`) combined with a
`SUB`/`ANDN` bit-masking sequence I did not fully decode in the time available. So the
actual pixel box width for this specific renderer could not be pinned to a constant.
**Not found**: the column width / char-clip point for this row. Best available number
remains S5's Answer (b) by analogy (Settings-menu columns: ~31 px, ~5-6 chars at 6px
pitch, same font) since Finding 5 confirms the same font function is used — but this is
carried over by analogy, not independently measured for this renderer. Confidence:
not found (own attempt, abandoned for time, not "nothing is there").

### Finding 7: side-check — the expression-pedal-to-param pipeline is a different, unrelated path (noted to avoid confusing future jobs)
While grepping for other callers of `c012afe0`, found `c014aef4=analog_cc_apply_to_effect_params`
(roots MainApp, `chunk_11.md:417-421`) called by `c015ff60=ad_value_calibrate_scale` /
`c016004c=ad_value_calibrate_scale_ch2` — this is the analog expression-pedal-position
-> assigned-MIDI-CC -> `c0141684=effect_param_value_store` pipeline (writes a param
value from pedal position), not the 4-knob on-screen editor. It also touches
`c012afe0`, which is a reminder that this accessor is heavily multiplexed across MIDI,
USB, expression-pedal and (candidate) screen uses; a patch at `c012afe0` itself would
hit all of them. Confidence: confirmed (direct read of calls list; distinct caller set
from Findings 2-4's chain).

### Finding 8: ui_settings_screen_render (c013c0f4) is a sibling per-FIELD-type dispatcher, not part of the row-dispatch chain — correcting my own mis-association
Initially suspected `c013c0f4=ui_settings_screen_render`'s calls list included
`c013c0c8` (the row-dispatch entry point); re-reading its facts line
(`chunk_08.md:427-432`, 17 calls) shows it does not — `c013c54c=ui_settings_screen_build`
calls `c013c0c8` directly, `c013c0f4` is a sibling called BY `c013c54c` too but dispatches
separately. Read `c013c0f4`'s full 272-byte body (`main.dis:66358..66446`): it loops an
index register (A10) calling `c016f2b0(A10)` for a per-field flags word, then bit-tests
individual bits to select among ~13 widget-draw callees (`ui_settings_draw_backdrop`,
`ui_settings_draw_output`, `ui_settings_mode_dispatch` x3, `ui_assignment_panel_dispatch`,
`ui_assignment_alias_draw`, two icon-draw functions, four `ui_settings_field_*`
functions). This confirms the Settings-screen has its own, separate per-field bitmask
dispatch (distinct from the per-row-kind jump table of Finding 3) — i.e. there are at
least two different "which widget to draw" mechanisms layered in this one screen family.
The loop's exact termination condition (how many fields / what c016f2b0 returns at the
end) was **not resolved**: the visible branch structure always eventually jumps back to
the loop-continue point regardless of the flag bits tested in this excerpt, so the real
bound must be inside `c016f2b0` (unread). Confidence: confirmed (own disassembly read)
for the bit-dispatch structure; not found for the loop bound; this finding is reported
mainly to correct the mis-association and flag the loop bound as a concrete open lead
for whoever resumes this.

### Finding 9: overall assessment — a better-targeted, still-unconfirmed candidate
Net result: Findings 1-4 identify a call chain from `UpdateUI` (confirmed direct, not
pointer-only, unlike S5's cluster) through a generic on-screen row renderer that
genuinely fetches the ZD2 param descriptor and renders the known "Dummy" placeholder and
a page-counter — a much better match to "the LCD effect-edit screen" than S5's MIDI/USB
cluster. But its three confirmed static callers (Settings-screen build/dispatch,
MIDI-param-assign UI, Rhythm/Settings popups) do not include anything nameable as "the
per-effect knob-turn editor in Stomp/Play mode." Two explanations remain open and
undistinguished: (A) the stock firmware's per-effect param editor really is implemented
as one more caller of this same generic row-dispatch engine, reached through a call
edge this job did not find (e.g. another indirect/pointer-based entry, or a caller inside
one of the many `.calls` lists truncated by the fact-sheet generator at a fixed count —
several entries above literally ended in `...`); or (B) it is a genuinely separate,
still-unlocated piece of code (S5's original conclusion), and the matching "Dummy"/
page-counter evidence here is coincidental reuse of the same low-level widgets for a
different screen. Confidence: likely for (A) being plausible and worth a follow-up job
that specifically re-reads the truncated `calls (42)`/`calls (54)` lists in full from
`main.dis` rather than the fact-sheet summaries; not confirmed either way.

## Answers

### (a) Params per page, what decides it — for this (candidate) UpdateUI-direct path
**Not located**, same bottom line as S5's Answer (a), now for a different, more
UpdateUI-direct candidate chain (Findings 1-4) that S5 did not have. No equivalent of
the `4*c012af98()-r` arithmetic was found on this path: `c012e5a8`/`c013c044` render ONE
row at a time, dispatched through the per-row-kind table (Finding 3); any "how many
rows fit on this screen" decision would live in whatever loop calls `c013c060` per
visible row, which was not traced. The page-counter widget (`c012e330`,
`"%1d/%1d"`) gets its count from `c015ad98=usbdesc_page_count_helper` — a name that, by
the same auto-naming pattern that mis-tagged S5's MIDI-rooted cluster as "fxparam", may
itself be shared between the confirmed-USB caller (`c01359e4`) and this candidate
on-screen caller; not independently verified as screen-only. Patch site: none proposed
(would be patching a shared widget with an unconfirmed screen target). Risk: unknown.

### (b) Label drawing: font, pixel width, chars before clipping
**Font: likely** the 5x7 font at 6px pitch via `c011d4d8`, independently reached from
`c012dca4=ui_row_render_name` through `c013a2d8=ui_text_draw_centered_6px` (Finding 5) —
this is the SAME font function already confirmed by the Argon menu report and cited in
S5, now shown to also be reachable from a param-descriptor-driven row renderer, not only
the Settings-menu's already-documented renderer. **Pixel width per column / chars before
clipping for this specific renderer: not located** (Finding 6) — the box-width argument
traces to a stack buffer and an undeciphered table at `0xc0181508`. No better number than
S5's analogy-based "~5-6 chars at 6px pitch" is available. Patch site for the font/width
itself (if ever confirmed to be the right screen): inside `c013a2d8` or its caller's
width argument; risk high because `c011d4d8` and `c013a2d8` are shared by at least a
dozen other screens (`chunk_02.md:149-152` lists 13 callers of `c011d4d8` alone,
including tuner, save-slot, field-editor, and rhythm-row renderers) — any patch here is
not effect-param-exclusive.

### (c) Can labels change per page?
Same answer as S5: **yes, trivially**, because each parameter's label lives inline in
its own 56-byte ZD2 descriptor (S5 Finding 3), and this job additionally confirms
(Finding 2) that the NEW candidate renderer (`c012e5a8`/`c012dca4`) also fetches through
`c012afe0` directly — so even if this candidate turns out to be the real screen, the
same "no patch needed, it's data-driven" conclusion holds.

### (d) Sub-menu
Out of scope for S7 (the brief assigns this to S5; see S5 Finding 5 and its Answer (d)).
Not re-investigated here.

## Not checked / open leads
