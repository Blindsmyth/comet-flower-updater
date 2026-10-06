# Brief for Gemini (Antigravity): the remaining 8 stock drives, numbers only

Follow these steps exactly. Earlier helpers went wrong by guessing from
symbol names, by inventing cycle costs, and by writing nothing before their
quota ran out. Each rule below exists because of one of those mistakes.

## 0. First action (before any analysis)
Create `recon/11b_stock_drives_rest.md` with this skeleton, then fill it in
**one effect at a time, saving after each effect**:

```
# 11b — Remaining stock drives, second pass (Gemini)
Method: docs/helpers/AGY_DRIVES_REST.md. Format follows recon/11 "Second pass".
## Summary table
| Effect | OVS filter = shared? | OS factor | Clipper symbols | Knob tables decoded | SPLOOP cycles/block | Confidence |
## SWEETDRV
## TB_MK15
## RCBOOST
## REDCRUNC
## BGTHRTTL
## DISTPLUS
## VIOLETDS
## ACOSIM
## Not done / open questions
```

Do NOT edit `recon/11_stock_drives.md` or any other existing file.

## 1. Read first (short)
- `recon/11_stock_drives.md`: read the "Review by Claude" boxes and the
  `### TS_DRIVE` subsection of "Second pass (Codex)". That subsection is
  the **format to copy** for each of your effects.

## 2. Per effect: exact commands
Run from the repository root. `P=.venv/Scripts/python.exe`.

1. Extract (note: `-o` makes a sub-folder named after the effect):
   `.venv/Scripts/zd2 extract -o build/agy2 backup/2026-10-04/files/<FILE>.ZD2`
   → `build/agy2/<FILE>/DATA.elf`, `PRME.bin`, `TXE1.txt`.
2. Disassemble **to a file argument, never with `>`** (redirecting in
   PowerShell makes UTF-16 that grep cannot read):
   `C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS/bin/dis6x.exe build/agy2/<FILE>/DATA.elf build/agy2/<FILE>/DATA.dis`
3. Symbols: `$P tools/fwmap/elfsyms.py list build/agy2/<FILE>/DATA.elf`
4. Oversampling filter: `$P tools/fwmap/elfsyms.py ovs build/agy2/<FILE>/DATA.elf`
   Copy its output lines into the report. If it prints "identical ...: True",
   write "shared filter (same bytes as TS_DRIVE)". Do not re-derive it.
5. Each knob table (every symbol ending `_tbl`, `_TBL`, `_Tbl`):
   `$P tools/fwmap/elfsyms.py dump build/agy2/<FILE>/DATA.elf <symbol> f32`
   Put ALL values in the table. If the values look wrong as f32 (huge or
   tiny numbers), try `f64` or `i32` and say which you used. Match each
   table to a knob name from PRME/TXE1 **only if the code shows it**
   (the table's address is loaded in the parameter handler for that knob);
   otherwise write "knob: not traced".
6. Oversampling factor: count how many times the clipper code runs per
   input sample inside the per-sample loop (the loop with count 16). Quote
   the addresses. If you cannot see it, write "factor not verified".
7. Clipper: name the clipper symbol(s) (e.g. `*_CLIPPER_KAWAOD`,
   `ToneBender_CLIPPER_TR`). Write its parameter values if they come from a
   table you dumped. Do not write a formula you have not read in the code.
8. Cost: list each `SPLOOP`/`SPLOOPD`/`SPLOOPW` inside the audio kernel with
   its address and ii, and the trip count only if you can see it in the
   code (the ILC/loop-count register setup). Cycles = ii × (trips + stages −
   1) × invocations per block. If anything is unknown, write "unknown" —
   **never estimate a cost from the effect's name or dspload.** Loops that
   belong to string/editor functions (names like GetString_*) are not audio.

## 3. Words you must not write without code evidence
"models a Klon / Rat / Bogner ...", "envelope follower", "fakes",
"sounds better", "~Nk cycles" without the SPLOOP arithmetic. Table and
symbol names suggest, they do not prove.

## 4. Order and budget
SWEETDRV, TB_MK15, RCBOOST, REDCRUNC, BGTHRTTL, DISTPLUS, VIOLETDS, ACOSIM.
After each effect: update its row in the summary table and save. If you run
low on budget, stop cleanly and list unfinished items under "Not done".

## Hard rules
- **Never touch the pedal**: no MIDI ports; do not run `tools/pedal_g1.py`,
  `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  `make_fs_restore_updater.py`, or any `.exe` other than dis6x.
- Write only `recon/11b_stock_drives_rest.md` and files under `build/agy2/`.
  Do not change `tools/`.
- Another helper is working on `recon/13_effect_loader.md` at the same
  time: do not touch it.
- No git commits or pushes; Claude reviews and commits.
