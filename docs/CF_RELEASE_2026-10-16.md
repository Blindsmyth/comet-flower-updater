# Comet Flower release build (2026-10-16)

Folder: `build/cf_release_2026-10-16/` (owner use only: it contains Zoom's firmware code).

| File | SHA-256 (start) | Contents |
|---|---|---|
| `Comet Flower G1X4 Updater.exe` | `3adc2c97f62651f6` | Release: controller mode + on-pedal screen, **no diag hooks** |
| `RESTORE_stock_fw_factory_fs.exe` | `38c6b74d6877b5aa` | Back to stock v2.00 firmware + factory effects |
| `Comet Flower Setup.cmd` | | The intro, pointing at the release updater |
| `res1_comet_flower.bin` | `62efda9be77383a3` | Main firmware (498,160 B) |
| `fs_cf.bin` | | Effects image |

- **Firmware:** `res1_cf_usbname.bin` (CF logo, USB name "Comet Flower") + `make_controller_fw.py --ui`:
  the seven lifecycle hooks plus the UpdateUI screen hook; no `--diag-teardown` (no CLAUDE page,
  no timing beacons). Controller page header "COMET FLOWER".
- **Packaging:** `--controller-fw` (strict). The strict check now accepts the screen hook
  (UI_HOOKS), which ran on hardware 2026-10-15 (stack, reconnect, tick gates closed: recon/04).
  The diag hooks stay `--test-controller-fw` only.
- **Effects:** CF 808, CF RAT, CF Muff, **CF Watt** (was "CF DR103": display name and icon only;
  file DR103.ZD2 and id 04000f81 unchanged, so patches keep it; the 28 KB code block is
  byte-identical), G1 Gain. CF ClkT removed (rebuild from `effects/clkt` for budget runs).
- **Stages** (`check_updater_stages.py` ok): presets 0x28000, effects 0x102000, main firmware
  0x033000. Boot/update program and settings sector untouched.
- **Not tested on the pedal yet.** Its parts are: the hardware-run lifecycle + screen code without the
  diag hooks, and the same effects with one renamed. Flash it in update mode as usual.

Diagnostics: keep `build/cf_unified_2026-10-15/Comet Flower G1X4 Updater (TEST build).exe` (the
CLAUDE page and timing beacons) as the separate diagnostics updater.
