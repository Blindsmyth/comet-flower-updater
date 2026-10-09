# Brief (Codex gpt-5.6-sol, medium): recon/21 S5 — read c014a58c in full

Follow `docs/helpers/SAVE_PROTOCOL.md` exactly, including its token economy.
- Report file: **`recon/22_s5_activate_core.md`**. Create it first with the
  section headings below, commit it, then commit THAT FILE ONLY after every
  finding.
- Scratch folder: **`build/codex_s5/`**. Never write anywhere else.
- **Static analysis only.** Never touch the pedal, MIDI tools,
  `tools/pedal_g1.py`, `tools/patch_g1.py`, updater `.exe` files, or
  anything that opens a USB device. Never push.
- Every finding: instruction addresses, a short disassembly excerpt (≤ 8
  lines), confidence confirmed / likely / guess. If you can't close a
  question, write exactly what is missing. Don't fill gaps with plausible
  claims.

## Inputs
- `build/fw/map/main.dis` (one instruction per line, `<addr> <op> <insn>`);
  `build/fw/map/refs.txt` (`<insn addr> <reg> <constant>` for every
  MVK/MVKH constant — use it, do not add MVK/MVKH by hand).
- `docs/helpers/FWMAP.md` "Pitfalls" (delay slots, BNOP/CALLP, MVKH, c016fXXX
  trampolines, callbacks). Read that section only.
- Context: `recon/21_usb_audio_needs.md` sections 1–3 (what USB audio needs);
  `recon/map/chunk_11.md` rows for c0149ef8 and c014a58c (`grep -n`).
- Names for callees: `grep -n '<addr>' recon/map/chunk_*.md | head -3`.

## Background
c014a58c (1396 bytes, about 349 instructions; sole caller c0149ef8,
"usb_interface_configure_and_activate", whose caller is c0144f74 in the USB
MIDI init) was only read up to c014a644. Its later part saves a full register
set, loads globals at c01819bc / c0181ae4 / c0181ae8 / c0181f74, enters a DINT
critical section, calls c016e460 and dispatches on those globals.

## Questions (report sections)
1. **Structure.** Basic blocks and every exit path with its return value.
   Is it one function, or does it contain a second entry (hidden start)?
2. **Arguments and globals.** What do A4/B4/A6 hold on entry (check what
   c0149ef8 passes)? What are the objects at c01819bc, c0181ae4, c0181ae8,
   c0181f74 (type, fields used, who else references them — grep refs.txt)?
3. **The critical section.** Exactly what is done between DINT and RINT:
   which fields are written, which lists linked, which callees run.
4. **Callees.** For each call: target (resolve trampolines), its map name,
   and what it does here.
5. **For USB audio.** Is this the path that registers an interface /
   endpoint record (the kind c015afa0 registers for MIDI, recon/21 3.1)? Does
   it touch endpoint hardware, CPPI/DMA channels or FIFO set-up? Would an
   added interface 2/3 (UAC, recon/21) have to pass through it, and what
   would it need (table entries, record fields)? Could the stock CPPI TX path
   used by MIDI IN be reused for an isochronous EP1 (recon/21 3.3 fix 2)?
6. **Proposed map row** for c014a58c in the chunk_11 table format, and any
   corrections to the c0149ef8 row.

Stop when all six are answered or marked open with what is missing.

## Known errors from your calibration run (avoid them)
- A `CALLP c016e000` (or another c016eXXX epilogue) ends a function. Code
  after it is a separate function, not part of the one you are reading.
- Instructions in a branch's delay slots run on both paths. Report the
  values they load, for example an error code set in a BNOP delay slot.
