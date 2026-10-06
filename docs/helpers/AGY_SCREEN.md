# Brief for Antigravity: a Comet Flower look for the pedal's screen

You are helping on a project that customises a Zoom G1X Four guitar pedal.
Its screen is a 128×32 monochrome LCD. We can now replace every font and
screen bitmap in its firmware. Read `recon/10_firmware_capabilities.md`
("Firmware map, part 1: the display") and the docstring of
`tools/g1fw_gfx.py` first.

## Goal
Design proposals for a **Comet Flower** (CF) look: the owner's brand,
already used for the start-up screen (`assets/splash_cf_zgx4.png`,
`assets/splash_comet_flower.png`) and the logo (`assets/logo_comet_flower.png`,
92×16, replaces the ZOOM logo). The owner reviews the proposals before
anything goes on the pedal.

## Steps
1. Export the originals:
   `.venv/Scripts/python.exe tools/g1fw_gfx.py export build/fw/res1_493412.bin build/fw/gfx`
   (7 font sheets + 51 bitmaps, white = lit pixel, grey = grid lines).
2. Make the CF set in `assets/screen_cf/` with **exactly the same file names
   and pixel sizes**. Copy every original you do not redesign unchanged, so
   the folder is complete. Priorities:
   - the full-screen messages (128×32): PC MODE, Low Battery, MISSING EFFECT,
     PROCESS OVERFLOW, LOOPER CANCELED, the two framed panels;
   - `bmp_c017bf38_92x16.png` = `assets/logo_comet_flower.png`;
   - the fonts: one consistent CF style across the sizes. Every glyph must
     stay readable at 1:1 on a real 128×32 LCD; keep the character order
     and cells exactly as exported (font_25x40 is A–Z 0–9, font_14x18 is
     A–Z a–z 0–9 -, font_16x21 is A–Z a–z 0–9, the others ASCII 0x20–0x7e).
     Do not change the grey grid lines.
   - small icons only if there is time.
   Pixels must be pure black (0) or white (255); no anti-aliasing.
3. Build and check:
   `.venv/Scripts/python.exe tools/g1fw_gfx.py import build/fw/res1_493412.bin assets/screen_cf build/fw/res1_cf.bin`
   It must succeed and list what changed.
4. Make `assets/screen_cf/PREVIEW.png`: originals and CF versions side by
   side at 4× scale, and a mock of a few screens built with the new fonts
   (e.g. a patch name and number), so the owner can judge them.
5. Write `docs/design/SCREEN_CF.md`: the design idea, what was changed, and
   any glyph or screen you were unsure about.

## Which file is which (checked by Claude against the originals)
| File | What it is | Rule |
|---|---|---|
| bmp_c0178ae0_128x32 | blank framed panel (corner screws); the firmware draws other content inside it | frame style may change, interior must stay empty |
| bmp_c0178ce0_128x32 | "Low Battery!" + battery icon | keep text and icon |
| bmp_c0178ee0_128x32 | "PC MODE" + USB icon (white background) | keep text and icon |
| bmp_c01790e0_128x32 | "MISSING EFFECT / NOT FOUND" + "?" icon; small hollow square top-left | keep both lines, icon and the square's area |
| bmp_c01792e0_128x32 | "PROCESS OVERFLOW / CHANGE EFFECT" + warning triangle | keep both lines and icon |
| bmp_c01796e0_128x32 | framed panel split by a vertical line; content is drawn into both parts | keep the divider position and empty interiors |
| bmp_c01798e0_128x32 | "LOOPER" (small) "CANCELED" (large) | keep both words |
| bmp_c017a8d8_128x20 | "Edited! Can't swap." | keep text |
| bmp_c017a458_128x21 | looper STOP / HOLD CLEAR | keep |
| bmp_c017bf38_92x16 | the logo | = assets/logo_comet_flower.png |

General rules for the messages: keep every word and icon of the original
(restyling is welcome), text at least 1 px clear of any frame line.

## Fonts
No mechanical transforms (shear, scale): they leave jagged strokes. A font
is changed only if every glyph is drawn cleanly by hand; otherwise keep the
original. font_25x40 is 40 px tall, taller than the 32 px screen; we do not
yet know where the firmware uses it, so do not use it in mock-ups.

## Hard rules
- **Never touch the pedal**: do not open MIDI ports, do not run
  `tools/pedal_g1.py`, `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  `tools/make_fs_restore_updater.py`, or any `.exe` (updaters in `build/fw/`
  or Downloads). Building `build/fw/res1_cf.bin` is the end of your job.
- Do not edit any file outside `assets/screen_cf/`, `docs/design/` and
  `build/fw/` (scratch). Do not change the tools.
- No git commits or pushes; Claude reviews and commits.
- Finish with a short summary of what you made and what is left.
