# G1X Four recovery: pedal hangs at the ZOOM logo

Proven on the owner's G1X Four on 2026-10-06 (incident in `recon/04`).

## Symptom
After a file write to the pedal went wrong, it hangs at the ZOOM logo on
every start: no input, no USB device. The pedal stopped answering right after
an acknowledged file close, during the replace of a 56 KB DIY effect.

## What does NOT fix it
- **Zoom's official updater (v2.00):** it rewrites only the boot program,
  graphics, main firmware and settings sector (its 8-stage table). It never
  writes the effect file system, although it carries a factory image of it.
- **Factory reset** (hold MEMORY/STOMP/EDIT at power-on): it resets patches
  and settings, not the file system.

## What fixed it
Write the factory file-system image into the file-system region from
update mode:
1. Download `G1X_FOUR_v2.00_Win_E.zip` from zoomcorp.com and extract the
   updater.
2. Build the restore copy:
   `python tools/make_fs_restore_updater.py "<...>/ZOOM G1X FOUR System v2.00 Updater.exe" "build/fw/G1X FOUR FS restore (patched updater).exe"`
3. Enter update mode: hold both footswitches while connecting USB, until the
   FIRMWARE UPDATE screen appears.
4. Run the copy, select ZOOM G Series for MIDI IN and OUT, then Execute.
   Don't disconnect until "Version update completed".
5. Unplug USB and power on.

The result is the factory effect set and effect list. DIY effects are gone
and must be reinstalled. Patches live outside this region.

## Flash map (from the updater table and the firmware's region table)
| Region | Flash range | Updater resource |
|---|---|---|
| boot program | 0x000000-0x028000 | 142 (163,840 B) |
| graphics | 0x028000-0x033000 | 133 (45,056 B) |
| main firmware | 0x033000-0x0BF000 | 129 (493,412 B) |
| settings | 0x0BF000-0x0C0000 | 139 (4,096 B, erased) |
| (patches?) | 0x0C0000-0x102000 | not in the updater |
| effect file system | 0x102000-0x400000 | 136 (3,137,536 B, never sent by the official table) |

The main firmware also contains a service menu (VERSION / SYSTEM / PRESET /
BOOT / CheckSum / ALL INITIALIZE) and the file-system calls
(`f_findfirst "*.*"`, `f_unlink`, `ffs_format`). At boot it scans every file
in the file system, not only those on the effect list.

## Lessons
- A hang after a file close can leave the file system in a state the boot
  scan cannot get past.
- Never kill a hung transfer without a recovery plan. Here there was no
  alternative: the process was stuck in the USB driver.

## Before any test image (added 2026-10-09, recon/25)
- Run `.venv/Scripts/python.exe tools/check_updater_stages.py "<updater.exe>"`.
  It must print `ok` on every stage: no stage may touch the boot/update-mode
  program (flash 0x0-0x28000) or the settings sector (0xbf000-0xc0000).
- Update mode is chosen by the boot program **before** it loads the main
  firmware, so a bad main-firmware image is always recoverable: hold both
  footswitches at power-on and run a restore updater.
- The boot program itself has no backup. Zoom's official updater rewrites
  it; run that only when needed, on a stable USB connection, and never
  unplug during it.
