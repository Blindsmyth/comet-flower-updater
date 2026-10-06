# 09 — The ZOOM power-on logo

Date: 2026-10-06. Located by Codex (read-only analysis), checked by Claude.

## Where it is
The logo is a plain bitmap, not compressed: 184 bytes = 92×16 pixels in LCD
page format (2 pages × 92 columns, LSB = top row), drawn at x 18, y 8 of the
128×32 screen. Earlier mosaic scans missed it because they assumed 128-wide
rows. Two identical copies:

| Binary | File offset | Load address | Notes |
|---|---|---|---|
| main firmware `res1_493412.bin` (resource 129, flash 0x33000) | 0x6fec0 | 0xc017bf38 | the start-up code calls its logo routine |
| boot program `res5_163840.bin` (resource 142, flash 0x0) | 0x1be60 | 0xc0229720 | **never modify** |

Both binaries are TI AIS images (`TIPA` magic). Commands seen: one 0x63
(boot table / ping), two 0x0d (function execute / set), section loads 0x01
(11 in res1, 10 in res5), then jump-and-close 0x06. **No CRC commands**, so
the AIS loader checks nothing in the section data. The updater computes its
own transfer CRCs from whatever payload it sends.

## What that means
- The boot program draws its copy first, so the ZOOM logo still flashes at
  power-on whatever we do; replacing that copy would mean writing the boot
  program, which has no software recovery. Not done.
- The main firmware then draws its copy, so replacing that one should show
  our logo for the rest of the start-up. That is a write to the main firmware
  only (flash 0x33000), which Zoom's official updater restores.
- Not yet proven on the pedal: how long each logo stays on screen, and that
  the boot program does not check the main firmware some other way. If the
  pedal does not start, run Zoom's official v2.00 updater from update mode.

## Tooling
`tools/make_fs_restore_updater.py --logo <92x16 png>` finds the factory logo
bytes (exactly once) in resource 0x81, replaces them, and adds the same
erase/write stages for 0x33000 as Zoom's updater. Verified on the built copy:
the firmware resource differs from Zoom's only within 0x6fec0..0x6ff77, and
the boot resource is untouched. Logo used: `assets/logo_comet_flower.png`
("COMET FLOWER", 5×7 pixel font doubled vertically).
