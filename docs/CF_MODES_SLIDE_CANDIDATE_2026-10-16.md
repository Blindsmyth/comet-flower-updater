# Modes candidate + slide transition (2026-10-16)

Folder: `build/cf_modes_slide_2026-10-16/` (owner use only: it contains Zoom's firmware code).

| File | SHA-256 (start) | Contents |
|---|---|---|
| `Comet Flower G1X4 Updater (modes slide candidate).exe` | `745d3f37bf53795a` | Modes candidate + sideways slide on mode change |
| `res1_cf_modes_slide.bin` | `01a9a96285337f6a` | Main firmware (`make_controller_fw.py --ui`, base `res1_cf_usbname.bin`) |

Owner feedback on the modes candidate (flashed 2026-10-16): "looks better"; asked for an animation like
the stock change to Rhythm, which slides in sideways. Presets, effects and the other resources are
byte-identical to the modes candidate (`build/cf_modes_2026-10-16/`); only resource 0x81 differs.
`check_updater_stages.py` ok. Payload 8,672 B of 16 KiB (1 KiB of it the two frame copies).

## What changed (controller_ui.c)

- **Entering MIDI mode** (Rhythm held 2 s): the MIDI page pushes in from the right and pushes the stock
  screen out to the left. 7 frames, ease-out, 30 ms each (~200 ms).
- **Leaving MIDI mode:** stock redraws its screen as before (event bit 0); the next UpdateUI wait then
  slides it in from the left over a saved copy of the MIDI page, before its first wait.
- Frames are built from two 512-byte copies of the page buffer and flushed through the same gate as
  every other UI draw, in UpdateUI's task. No division, no switch. A real event during a slide is
  returned as before; the next frame overwrites the whole buffer.
- Booting straight into MIDI mode (button held at power-up) shows the page without a slide.

## Pedal checklist

1. Hold Rhythm 2 s in effects mode and release: the MIDI page slides in from the right, smoothly.
2. Hold Rhythm 2 s in MIDI mode and release: the stock screen slides back in from the left.
   **Watch for a short flash** of the stock screen just before that slide starts (stock flushes
   its redraw once before our first frame). If it is visible, report it: the fix is a second hook.
3. Speed: if it feels slower or faster than the Rhythm slide, say which; `ANIM_TICKS`/`slide[]` set it.
4. Everything in `docs/CF_MODES_CANDIDATE_2026-10-16.md` still applies.
