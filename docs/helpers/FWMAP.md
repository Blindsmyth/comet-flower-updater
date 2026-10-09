# Firmware map brief (helpers, from 2026-10-08)

Goal: every function in the G1X Four main firmware gets a name and a
one-line role with a confidence, grouped into subsystems, before we change
the firmware further. Coverage is measured by `tools/fwmap/coverage.py`.

Follow `docs/helpers/SAVE_PROTOCOL.md` (including Token economy) exactly.
Static analysis only: never touch the pedal, USB/MIDI devices or any .exe.
Edit nothing except your own report file.

## Your inputs
- Your fact sheet: `build/fw/map/facts/chunk_NN.md` (regenerate with
  `.venv/Scripts/python.exe tools/fwmap/facts.py` to pick up names other
  helpers have committed). It lists, per function: size, reaching tasks,
  callers, callees, strings, MMIO bases, B14 globals, table pointers, recon
  mentions.
- Disassembly `build/fw/map/main.dis`: read windows of at most 60 lines
  (`grep -n "^ADDR" build/fw/map/main.dis` then `sed -n 'a,bp'`).
- Strings `build/fw/map/strings.txt`. Existing knowledge: `recon/13`..`recon/20`,
  and names already in `recon/map/*.md`.
- Tasks (recon/15, init_c0181b28): MainApp c0134e10, UpdateUI c013c754,
  QFuncService c0161ce4, TunerService c01674e0, MIDI c0129118,
  SwitchNrmlSpdRead 118076c0, RepeatEventHandler 11809d40, PopUpTimeCounter
  11809580, RhythmService c016aac0, LooperUI c013b38c, AD 11809004, PreLoad
  c016c0c0, DataStore c016d340, BatteryManagement 11809bd4.
- Useful tables found so far: TI dynamic-loader error names at c0183608
  (DLE_SUCCESS...), flash file system API names at c01834f8 (ffs_init, f_read,
  ...), settings menu entries around c0182b38, rhythm patterns at c0182730.

## Your output
Report file `recon/map/<your file>.md` (named in your task). Start it with a
one-paragraph summary of the subsystem(s) in your range, then ONE table row
per function, in address order, exactly this format:

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| c0167b00 | memset | fill A6 bytes at A4 with B4 | confirmed | loop STB, callers pass (ptr,0,size) |

- `addr`: 8 lowercase hex digits, no 0x. `name`: a C identifier you choose
  (prefix by subsystem, e.g. `ui_draw_text`, `ffs_read`, `bios_sem_pend`);
  use `unknown` only if you truly cannot tell.
- `conf`: confirmed (read the code and it is unambiguous) / likely / guess.
- `evidence`: a few words: key instruction, string, caller pattern.
- After the table: "Data" (globals/B14 slots and structures you identified)
  and "Open questions".

Commit your report after every 10-20 rows (`git add` your file only) and at
the end. Never guess a role and mark it confirmed. A short honest "guess" is
better than a wrong "confirmed".

## Pitfalls seen in review (read before you start)
- **Indexed addressing is scaled.** `LDW *+A3[A4]` with A4=96 reads byte offset 96*4 = 0x180,
  not 0x60 (LDH scales by 2, LDB by 1; `*+A3[5]` immediate forms scale too; only the
  `(offset)` byte form with parentheses is unscaled). Always state byte offsets.
- `c016e020`/`c016e000` (`CALLP ...,A3`) are register save/restore helpers, not logic.
- High caller counts can be shared epilogues reached by branch (recon/map/00 notes).
- **Check for gaps.** Every `## addr` in your fact sheet gets a row, even a 10-byte stub.
  Before finishing, diff your rows against the fact sheet. Also give each start from
  `tools/fwmap/hidden_starts.py chunk_NN` its own row ("(hidden start)"); the fact
  sheets fold about 150 such functions into their neighbours.
- **Callbacks have callers too.** A function with no CALLP caller is usually loaded as
  an address (`MVK 0xffffd138` + `MVKH 0xc0140000` = c014d138). `grep <addr>
  build/fw/map/refs.txt` before writing "no caller".
- **Address arithmetic:** MVKH sets only the top 16 bits; write the full 8-digit result
  (0xc011adb8, not 0xc010adb8 or 0xc0110052cc). c0/118/11f addresses are memory, not MMIO.
- **Branches:** `[!A0]` is taken when A0 == 0; `CMPLTU k,A4,A0` is (k < A4).
  `BNOP t,N` with N < 5 runs the next 5-N cycles of code before the jump lands.
- Row text must agree with its evidence (byte order, which branch picks which value).
