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

## Answers

## Not checked / open leads
