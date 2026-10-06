# 10 — What the main firmware could be changed to do

Date: 2026-10-06. Read-only scan of `build/fw/res1_493412.bin` (main
firmware) and `res5_163840.bin` (boot program), after the owner confirmed the
replaced ZOOM logo works (a main-firmware edit, recon/09).

## USB lives in the DSP firmware
- The USB stack is part of the main firmware: `g_Swi_UsbInterrupt`,
  `UsbTask`, `g_Task_MIDI`, `g_Event_MIDIDataReady`, `UsbTestMidi_Task`, the
  strings "ZOOM Corporation" / "ZOOM G Series". The boot program has its own
  copy (update mode).
- Device descriptor at res1 0x73364 (twice):
  `12 01 10 01 00 00 00 40 86 16 a1 04 00 01 01 02 00 01` = USB 1.1 full
  speed, EP0 64 B, VID 0x1686, PID 0x04A1. Config descriptor total 0x65 bytes
  (101 B, the size of a standard USB-MIDI 1.0 config), bus powered, 500 mA.
  Interface/endpoint descriptors are not stored as a plain block (built in
  code or split).
- The TMS320C6745 has no USB controller of its own (the C6747 has one), and
  the firmware has SPI0/SPI1 semaphores (`g_Semaphore_SyncTxSPI0` etc.). So
  the USB device controller is very likely a separate chip on SPI. **Not
  confirmed**: needs a board photo or a trace of the SPI register traffic.

## Consequences
- **MIDI controller:** the USB-MIDI port already exists and the firmware
  already sends MIDI on it. Sending CC/PC from the footswitches and the
  expression pedal is a code patch (hook the switch handler, call the
  existing MIDI send). It needs reverse engineering, but no new USB work.
  A zero-risk first step is a host-side bridge (the editor-mode SysEx the
  pedal sends on changes, mapped to CC on a virtual port).
- **USB audio:** needs new descriptors, isochronous endpoints and an audio
  path from the McASP to the USB chip. If the USB chip is an SPI peripheral
  controller of the MAX3420E kind (control/bulk/interrupt endpoints only, no
  isochronous), class-compliant USB audio is impossible on this hardware.
  Identify the chip before spending any effort.
- **Patch slot count:** the effect header already carries a slot count
  (byte 0x58) and patches already mark the second half of a double-width
  effect (id 0x1), and the declared dspload drives "Process Overflow". A
  solo effect can probably be made with those, without a firmware patch.
  Note that the real CPU limit (~96k cycles/block, recon/06) is the whole
  DSP already: one effect can use all of it even in a 5-slot patch.

## Firmware map, part 1: the display (2026-10-06)

### Layout of the main firmware (res1, AIS)
| Load address | Size | File offset | Contents |
|---|---|---|---|
| 0x11800400 | 0xb940 | 0x40 | fast code in internal L2 |
| 0x118164c0..0x11819d20 | small | 0xb98c.. | L2 data |
| 0xc011adc0 | 0x549c0 | 0xed3c | main code (SDRAM) |
| 0xc016f780 | 0x123a4 | 0x63708 | constant data: rhythm table, strings, fonts, bitmaps |
| 0xc0183b74..0xc0187024 | small | 0x75ab8.. | initialised data |
Entry 0xc0169a20. It runs TI SYS/BIOS; the task names are in the strings
(g_Task_MainApp, g_Task_UpdateUI, g_Task_MIDI, g_Task_SwitchNrmlSpdRead,
g_Task_AD (knobs/expression?), g_Task_TunerService, g_Task_LooperUI, ...).
The firmware also lists bass effect files (SVT.ZD2, B15N.ZD2, ...): it is
very likely shared with the B1 Four.

### Drawing
- `0xc011c508(ctx, x=B4, y=A6, w=B6, h=A8, bitmap=B8)` draws an LCD-page
  bitmap. ctx is `*(B14+122*4)`.
- Glyph routines at 0xc011e898.. map a character to a cell and call it.

### Fonts (all fixed cells, LCD page format, page-major per glyph)
| Name | Address | Cell | Characters |
|---|---|---|---|
| font_5x7 | 0xc01788a0 | 6×8, 6 B | ASCII 0x20–0x7e |
| font_bold7 | 0xc01783b0 | 7×8, 7 B | ASCII 0x20–0x7e (table starts at char 0, 0xc01782d0) |
| font_8x13 | 0xc0177180 | 8×16, 16 B | ASCII 0x20–0x7e |
| font_11x13 | 0xc0176250 | 11×16, 22 B | ASCII 0x20–0x7e |
| font_14x18 | 0xc01757f8 | 14×24, 42 B | A–Z a–z 0–9 - |
| font_16x21 | 0xc0174170 | 16×24, 48 B | A–Z a–z 0–9 |
| font_25x40 | 0xc0172fd8 | 25×40, 125 B | A–Z 0–9 (copied straight to the screen buffer) |

### Bitmaps
54 found as constant arguments of 0xc011c508 (list:
`build/fw/map/bitmaps.txt`); 51 are in `tools/g1fw_gfx.py`. They include
the full-screen messages (Low Battery, PC MODE, MISSING EFFECT / NOT FOUND,
PROCESS OVERFLOW / CHANGE EFFECT, LOOPER CANCELED, Edited! Can't swap.),
the ZOOM logo, looper and rhythm icons, CHAIN/DELETE bars, small arrows.
Bitmaps drawn with a computed pointer or size are not in the list yet.

### Tools
- `tools/g1fw_gfx.py export|import|selftest`: fonts and bitmaps to PNG and
  back; the round trip is byte-exact.
- `tools/make_fs_restore_updater.py --firmware <res1.bin>`: writes an edited
  firmware; refuses any byte change outside the constant-data section.
  Regression: rebuilding the logo updater the owner ran gives a
  byte-identical file, through both `--logo` and `--firmware`.
- `tools/fwmap/`: ais.py (sections), mkelf.py (wrap for dis6x), refs.py
  (MVKL/MVKH address constants), calls.py (constant arguments of calls),
  glyphs.py (render glyph runs).
  ```
  P=.venv/Scripts/python.exe
  $P tools/fwmap/mkelf.py build/fw/res1_493412.bin build/fw/map/main.elf 0x11800400,0xc011adc0
  ~/ti/ti-cgt-c6000_8.5.0.LTS/bin/dis6x.exe build/fw/map/main.elf build/fw/map/main.dis
  $P tools/fwmap/refs.py build/fw/map/main.dis > build/fw/map/refs.txt
  $P tools/fwmap/calls.py build/fw/map/main.dis c011c508 B4 A6 B6 A8 B8
  ```

### Limits of a graphics-only edit
Glyph and bitmap sizes are fixed by the code; changing a size, adding a
screen or moving where something is drawn is a code patch (next part of the
map). Text strings can be swapped for strings of the same length or shorter.
