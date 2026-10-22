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

## Not checked / open leads
