# Brief for Codex (gpt-6-astra, medium): controller audit, SDRAM gap, USB audio driver, reload paths

Follow `docs/helpers/SAVE_PROTOCOL.md` exactly. You may run out of quota at
any moment, so **save as you go**:
- Report file: **`recon/18_round3.md`**. If it already exists, read it and
  continue with the first item that has no "Status: done" line. Otherwise
  create it with the headings below and commit it.
- After EVERY finding: append it to the report and commit THAT FILE ONLY
  (`git add recon/18_round3.md` then `git commit`). Small commits, often:
  never hold more than one finding uncommitted. End each item with
  "Status: done" (or "Status: blocked: <what is missing>") and commit.
- Scratch folder: **`build/codex8/`**. Never write anywhere else.
- **Static analysis only.** Never touch the pedal. Never run MIDI tools,
  `tools/pedal_g1.py`, `tools/patch_g1.py`, any `.exe`, or anything that
  opens a USB device. Do not edit tools/, src/, firmware/, effects/ or other
  recon files. If you find a bug in the code, describe the fix in the report.
- Every finding gives addresses, a short disassembly excerpt, and a
  confidence: confirmed / likely / guess. Write down what is missing rather
  than filling gaps with plausible claims.

## Inputs
- Main firmware `build/fw/res1_493412.bin`, disassembly `build/fw/map/main.dis`,
  AIS walker `build/fw/map/ais.py`, boot program disassembly
  `build/codex7/boot.dis`, resolved constants `build/fw/map/refs.txt`.
- TI tools in `C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS/bin/` (cl6x, lnk6x, dis6x).
- Read first: `recon/17_usb_midi_audio.md` (all, especially "Placement in
  SDRAM" and B1-B5), `recon/15_controls_midi.md` (the last two sections),
  `recon/16_audio_hw.md` (C10-C12), `recon/14_effect_memory.md`.

## Items, in this order

### 1. Independent audit of the controller firmware
`firmware/controller/` and `tools/make_controller_fw.py` build
`build/fw/res1_controller.bin` (run the tool into build/codex8 with `--out`;
it only compiles and writes a .bin). Check, with dis6x on the built ELF
(`build/controller/controller.elf`) and on the patched hook sites:
- the C6000 calling convention at all three hooks: registers the stock
  caller expects preserved, B3/B15 handling, stack alignment (8 bytes), the
  parallel `EXTU` paired with the c015ffd0 CALLP;
- `controller_dispatch` (asm): the event pointer it passes (caller B15+4),
  the resume at c0134dc4, and that the MainApp loop state at c0134dc4 is
  consistent when stock handlers c0134acc/c0134d04 are skipped (B14[124],
  anything else the loop expects);
- `controller_start`: does skipping nothing and calling c015d428 last keep
  stock start-up identical? Is reading c0156f00 before c015d428 valid (is
  the switch sampler initialised by then; see c015710e and its caller)?
  If not, say what the read returns and propose the fix;
- calling c01274cc (MIDI send) from these contexts: which task each hook
  runs in, lock ordering against c01274cc's locks, and whether USB not
  being connected/enumerated makes the send block or fail fast.

### 2. Is the SDRAM gap c0187024..c01f4000 really unused at run time?
`recon/17` found no direct references. Look for computed users: heap
creation (sizes/bases computed at run time), memory tests, cache/MAR
operations covering the range, DMA (EDMA PaRAM) set-ups that could target
it, loops writing past c0187024 from a section end symbol, the update
program (res5) using SDRAM there while the main firmware runs (it does not
run then, but check flash read buffers during boot), and the effect loader.
Conclude "unused / used by <x> / unknown because <y>".

### 3. USB audio: driver facts still missing (recon/17 B5 step list)
- Capacity of the descriptor pointer array at c00643c0 and the control
  response buffer c0119fb0: can a 192-byte configuration be served?
  GET_DESCRIPTOR wLength handling.
- SET_INTERFACE / GET_INTERFACE: does the stock code handle alternate
  settings at all? Where are standard requests decoded; where would IF2/IF3
  requests go? Class-specific (bRequest for UAC1) requests to an interface:
  current behaviour (STALL?).
- Does the controller set up isochronous mode for an endpoint anywhere
  (TXCSR ISO bit, SPRUFM9)? Can endpoint 1 TX be configured ISO without
  disturbing RX3/TX4 FIFO addresses?
- Exact SOF hook context (c011fcb4 -> 11818e80): Hwi or Swi, priority, and
  whether a 180-byte PIO FIFO write fits there.
- Write a concrete patch list (addresses, what changes) for a first
  "silence stream" step: enumerate as MIDI + UAC1 and stream zeros.

### 4. Slot 0 residency: remaining reload paths (recon/16 C12)
Trace the unload-all path c01437b4 and error/failed-load paths of the
module loader. Do they substitute the silence callback before freeing or
reloading, as the traced paths in recon/16 B3 do? Any path that runs code
from the old image after reload starts?

### 5. What happens when an effect does not fit its 40 KiB slot?
Trace allocation failure in c015f72c -> c0151190 (recon/14): the error
returned, what the loader does with it, and what the user sees (error
screen, skipped effect, hang?). DR103 builds were ~10 KiB too big (see
`tools/check_slot_mem.py`), so this matters for the brick incident in
recon/04.
