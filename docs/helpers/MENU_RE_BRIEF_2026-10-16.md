# Brief: Zoom G1X Four settings-menu RE (2026-10-16)

Goal: let the owner pick **MIDI mode** and **USB-audio mode** from the pedal's own settings menu.
We need to know how Zoom's settings menu is built, drawn, navigated and persisted, and the
smallest safe way to add (or repurpose) one item, e.g. "MODE: FX / MIDI / USB".

Offline analysis only. **Never** touch the pedal, MIDI ports, updater `.exe` files or `tools/*flash*`.
Edit only your own report file and your scratch folder. Follow docs/helpers/SAVE_PROTOCOL.md
(create the report first, commit only your report after each finding, never push).
Tag every claim with address + instruction text and confidence (confirmed / likely / guess).

## Inputs
- Disassembly `build/fw/map/main.dis` (TI C674x, little-endian; compact 16-bit ops, `.fphead` words), ELF `build/fw/map/main.elf`.
- Constant-load xrefs: `build/fw/map/refs.txt` (`<insn addr> <reg> <value>`), strings: `build/fw/map/strings.txt`.
- ELF file offset -> address: addr = offset + 0xc010c0c0 for the .const area around the menu strings.
- Prior UI work: docs/helpers/ONDEVICE_UI_RECON_REPORT.md (UpdateUI task `c013c754`, table dispatcher `c013c060`,
  screen selector `c01595e4`), docs/ONDEVICE_UI_2026-10-15.md. Our hook mechanism: `HOOKS` in
  tools/make_controller_fw.py (retargets existing CALLP words), our C code in the controller payload (controller.c).

## Known leads (from Claude's scoping)
Menu strings at `c0180690..c01806e4`, NUL-separated:
`BPM` c0180690, `AUTO` c0180694, `SAVE` c0180699, `PRE-` c018069e, `SELECT` c01806a3, `BANK` c01806aa,
`HOLD` c01806af, `SETUP` c01806b4, `BATTERY` c01806bc, `ECO` c01806c4, `BACK-` c01806c8, `LIGHT` c01806ce,
`CONTRAST` c01806d4, `PWR/LCD` c01806dd. So two pages: SETUP {BPM, AUTO SAVE, PRE-SELECT, BANK HOLD} and
PWR/LCD {BATTERY, ECO, BACKLIGHT, CONTRAST}. Direct loads: `c01671f8 B6=c01806b4` (SETUP), `c01632b4 B6=c01806dd` (PWR/LCD).
Other item strings are probably reached as base+offset or via a pointer table: search for it.
Also seen: `SETTING` c018179c (loaded at c0157bf4), `OUTPUT/CALIB/TYPE/FLAT/TUNER` near c0180910.

## Split

### Argon (agy, Gemini 4 Argon) -> report `docs/helpers/MENU_RE_ARGON_2026-10-16.md`, scratch `build/scratch/argon_menu/`
A1. Find the menu data: item table(s) (string pointers, value ranges, value-to-text formatters, per-item handlers),
    page list, how many items per page. Dump the table words with addresses.
A2. Find the draw routine(s) for a menu page (who calls the text/bitmap primitives with these strings), and which
    task/caller chain reaches them (relate to UpdateUI `c013c754` / dispatcher `c013c060` if possible).
A3. Find where each item's current value lives (global struct/offset, e.g. ECO flag, BPM, contrast).
A4. List free/unused room: unused table slots, a page with spare rows, or an item we could repurpose.

### Codex Astra -> report `docs/helpers/MENU_RE_ASTRA_2026-10-16.md`, scratch `build/scratch/astra_menu/`
B1. How the menu is entered from effects mode (which button/combination; the input event path to the menu state).
B2. Menu state machine: current page/item variables, how knobs/footswitches/buttons change item and value,
    how exit works.
B3. Persistence: how a changed value is saved (system settings file / flash write routine) and loaded at boot.
    Is there a spare/reserved byte in the saved settings we could own?
B4. Insertion design: concrete candidate CALLP hook sites (address, existing word, live registers, task context)
    for (a) drawing an extra "MODE" item or overriding one item's text/value, (b) intercepting its value change so
    our code can switch mode. Prefer reusing the existing table over code patches. Note what stays unproved.

Both: if you find the other half on the way, record it briefly; do not stop. Finish with a "Summary" section
(<= 15 lines) at the top of your report.
