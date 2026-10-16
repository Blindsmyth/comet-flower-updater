# Effects/MIDI mode toggle + MIDI screen: candidate (2026-10-16)

Folder: `build/cf_modes_2026-10-16/` (owner use only: it contains Zoom's firmware code).

| File | SHA-256 (start) | Contents |
|---|---|---|
| `Comet Flower G1X4 Updater (modes candidate).exe` | `1317c46cd2c84622` | The release plus the mode toggle and the new MIDI screen |
| `res1_cf_modes.bin` | `21099861345374c4` | Main firmware (`make_controller_fw.py --ui`, base `res1_cf_usbname.bin`) |

The presets (`cfupd_res85.bin`) and effects (`fs_cf.bin`) are the same as in the release
(`docs/CF_RELEASE_2026-10-16.md`); only the main firmware differs. `check_updater_stages.py` passes.
**It has not run on the pedal.** Flash it after the release has been checked.

## What changed (commits 7f7354f, 6bc2f2b)

- **Run-time toggle (owner choice: hold Rhythm 2 s).** GPIO0, the button held at power-up for
  MIDI mode, likely Rhythm. Holding it at power-up still starts in MIDI mode.
  - Effects mode: a press is held back until release. If released within 2 s, stock gets the press and then
    the release (the release is reposted to MainApp's mailbox), so the stock button still works,
    but it acts on release, not press. Held 2 s or more and then released: MIDI mode.
  - MIDI mode: a short press sends a CC31 tap (127 then 0). Hold it 2 s and the screen shows
    `LET GO=EFFECTS`; releasing it returns to effects mode, and the stock screen redraws
    (UpdateUI event bit 0 = full redraw).
  - Audio keeps running in both modes (owner decision).
- **MIDI screen:** top line `MIDI CH1 USB` (or `NO USB` / `STALL`) and the last CC number; middle line (8x13) the
  last control's name (FS1, B3, K2, EXP) with ON/OFF or value + bar; bottom line K1..K4 bars.
  Previews: `build/ui_mock/fw_ctl_*.png` (written by `tests/test_controller_ui.py`).

## Pedal checklist

1. Normal boot: stock screen, patches and effects as before; a short Rhythm press opens what it
   opened before (on release now).
2. In effects mode, hold Rhythm for 2 s or more and release: the MIDI page appears; audio continues.
3. In MIDI mode: footswitches, buttons and knobs show their name and value; the knob bars follow the knobs;
   VPB sees the CCs on "Comet Flower 0".
4. In MIDI mode, hold Rhythm 2 s: `LET GO=EFFECTS`; release: the stock screen comes back and the stock
   controls work again.
5. Repeat 2 and 4 a few times; switch with USB unplugged and plugged.

## Risks to watch

- The repost goes through the stock mailbox post `c0166780` with timeout 0. If the mailbox were
  full, the release would be lost (stock would see only the press). Unlikely: MainApp has just
  taken one message.
- Which stock action Rhythm triggers, and whether it does so on press or on release, was not traced. If a short press
  misbehaves, report it. Fallback: pass the press through at once and toggle on a long release.
- Physical legends are still unverified (recon/17 A5): if the toggle button is not Rhythm, note
  which button it is.
