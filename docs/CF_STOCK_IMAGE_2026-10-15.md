# Comet Flower stock image (2026-10-15)

Folder: `build/cf_stock_2026-10-15/`. Built from the owner's official v2.00 updater.
No Zoom binaries are added; Zoom's main-firmware code stays.

| Updater | SHA-256 (start) | Contents |
|---|---|---|
| `Comet Flower G1X4 Updater.exe` | `5184cbc1953b179f` | CF effects only, CF presets/start-up screen, CF logo, USB name **Comet Flower** |
| `TEST Comet Flower G1X4 + controller diag-UI Updater.exe` | `f985d02428aa18e3` | The same, plus the TEST controller-mode + on-screen diag firmware (`docs/TEST_RUN_2026-10-15.md`) |

Stages (both, `check_updater_stages.py` ok): presets `0x28000`, effects FS `0x102000`, main
firmware `0x033000`. The boot/update program and the settings sector are never written.

- **Effects (clean FS, 78 Zoom effects removed):** CF 808 (DRV808X), CF RAT (RATX), CF Muff
  (MUFFX), DR103 (redesign; **first pedal run**, the old build overran its slot), G1 Gain, and
  CF ClkT (the cycle-budget diagnostic; remove it from later images).
- **Presets:** `cfupd_res85.bin`: 49 × Empty plus "CF test", with the CF-ZGX4 start-up screen.
  The live patches change only after a **factory reset** (they sit in `0x0C0000`, which no updater writes).
  Patches that contain CF effects need the EDTB slot format decoded first (recon/08); not done yet.
- **Firmware:** `res1_cfupd.bin` (CF logo, no "v2.0") + `tools/cf_usb_name.py`: manufacturer
  and product strings → "Comet Flower" (const data only; the descriptor builder `c01352a4` copies by
  bLength). **Update mode still shows "ZOOM G Series"** (the boot program's own strings), so
  Zoom's updater and ours work unchanged.
- Host tools find either name (`tools/pedal_ports.py`).

Caveats: Windows may cache the old port name per device. If it still shows "ZOOM G Series",
uninstall the device in Device Manager (View → Show hidden devices) and re-plug. Editors that look for
"ZOOM G Series" by name (ToneLib, Zoom Guitar Lab) may no longer find the pedal.

## Unified updater (2026-10-15, later)

`build/cf_unified_2026-10-15/Comet Flower G1X4 Updater (TEST build).exe` (`2268ca95c907b852`): one
updater with all of the above plus controller mode and the on-pedal screen. Normal mode shows
"COMET FLOWER …"; the diagnostics page is headed "CLAUDE W#…" (the owner's nod). It is still a
TEST build: the diag hooks stay in until the stack and liveness gates are measured. Its
`RESTORE_stock_fw_factory_fs.exe` is in the same folder. The boot program still says "ZOOM G Series"
in update mode (owner decision pending; see the risk note in the session record).
