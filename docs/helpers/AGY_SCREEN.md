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

## Hard rules
- **Never touch the pedal**: do not open MIDI ports, do not run
  `tools/pedal_g1.py`, `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  `tools/make_fs_restore_updater.py`, or any `.exe` (updaters in `build/fw/`
  or Downloads). Building `build/fw/res1_cf.bin` is the end of your job.
- Do not edit any file outside `assets/screen_cf/`, `docs/design/` and
  `build/fw/` (scratch). Do not change the tools.
- No git commits or pushes; Claude reviews and commits.
- Finish with a short summary of what you made and what is left.
