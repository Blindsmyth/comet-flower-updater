# CF Loader: Comet Flower Effects Loader (GUI)

CF Loader is a Windows desktop GUI application for packaging DIY effects (`build/*.ZD2`) into verified update-mode images for the Zoom G1X Four pedal, without typing command-line scripts.

**Crucial safety rule:** CF Loader does not invent a new way to communicate with the pedal. It uses exclusively the proven update-mode flashing workflow (`make_g1_image.py` -> `make_fs_restore_updater.py` -> owner flashes in update mode). It never opens a MIDI write stream and never launches any updater executable automatically.

---

## 1. Installation

**No installation or external packages required.**
CF Loader runs entirely on Python's built-in `tkinter` and `ttk` modules included in the repository's `.venv` virtual environment.

---

## 2. First Run

Run the loader from the repository root:

```powershell
.venv\Scripts\python.exe -m tools.cf_loader
```

The application window will open (minimum 960x640, resizable).

---

## 3. The Loading Flow (8 Numbered Steps)

1. **Launch CF Loader**:
   Run `.venv\Scripts\python.exe -m tools.cf_loader` from the repository root.
2. **Select effects in the Library tab**:
   Review the list of built effects in `build/*.ZD2`. Click or double-click to select desired effects. The app checks every effect against the 40 KiB slot heap limit, CRC32, target target bit, and stock ID collisions. Rejected or oversize effects cannot be selected.
3. **Select Zoom's official updater**:
   In the **Build image** tab, click **Browse...** under section 1 and locate `ZOOM G1X FOUR System v2.00 Updater.exe` (extracted from Zoom's official `G1X_FOUR_v2.00_Win_E.zip`). The app verifies the PE header, stage table, and filesystem resource. The path is remembered for subsequent sessions.
4. **Choose build options and verify pre-flight**:
   Select the base filesystem: **Clean test environment** (recommended; wipes stock effects, compacts directory, preserves system files) or **Keep stock**. Check that all 7 pre-flight checks in section 3 are green. If any check is red, the **Build** button remains disabled.
5. **Build image and patched updater**:
   Click **Build Image and Patched Updater**. The app runs the proven tool pipeline in a background worker thread:
   - Builds the 3,137,536-byte file-system image (`make_g1_image.py`);
   - Patches the updater stage table to flash flash region `0x102000` (`make_fs_restore_updater.py`);
   - Verifies that boot and settings flash sectors remain untouched (`check_updater_stages.py`).
   Outputs are placed in a fresh timestamped directory under `build/loader/<timestamp>/`. The directory is opened in Windows Explorer.
6. **Enter update mode on the pedal**:
   Disconnect USB. Hold **both footswitches** down while connecting the USB cable to your PC. Keep holding until the pedal screen displays **FIRMWARE UPDATE**.
7. **Run the patched updater by hand**:
   In the output folder (`build/loader/<timestamp>/`), launch `ZOOM G1X FOUR Patched Updater.exe` yourself.
   - Select **ZOOM G Series** for MIDI IN and MIDI OUT.
   - Click **Execute**.
   - Do NOT disconnect the USB cable until the screen reports **Version update completed**.
8. **Power cycle and run the Test Wizard**:
   Unplug the USB cable and reconnect to boot normally. Navigate to the **Test (Wizard)** tab in CF Loader:
   - Confirm AUTO SAVE is OFF on the pedal;
   - Place the DIY effect alone in an empty patch;
   - Verify audio output passes cleanly and click **Record Audio Pass**;
   - Run the Probe 10 cost test, enter the freeze load reading to compute CPU cycle cost, and click **Calculate & Record Cost**;
   - Only after both tests pass, click **Authorize 'OK to Save Patches'**.

---

## 4. What Each Pre-Flight Check Means

The **Build image** tab performs 7 strict pre-flight checks before permitting any build:

| # | Check Title | Red Meaning & Remediation |
|---|---|---|
| **1** | **Official updater** | The updater file is missing, not a valid Windows executable, or fails verification (stage table or resource 0x88 size mismatch). Ensure you select the official v2.00 G1X Four updater. |
| **2** | **Selected effects** | One or more selected effects are invalid: CRC invalid, target lacks G1 Four bit 0x02, or an oversize marker (`*.oversize`) exists. Fix or rebuild the effect. |
| **3** | **Unique IDs & names** | Two selected effects share the same filename or effect ID, or an effect collides with a stock Zoom effect ID/name. Change the effect ID or filename in `manifest.json` and rebuild. |
| **4** | **Image file count** | The resulting image would contain more than 110 files. The pedal's filesystem directory has exactly 127 slots (DSP_RULES §2), and exceeding 110 files risks bricking on boot scan. Use Clean mode or deselect effects. |
| **5** | **40 KiB slot heap limit** | One or more selected effects exceed the pedal's fixed 0xa000 (40,960-byte) per-slot image heap (evaluated via `check_slot_mem.py`). Reduce `.text`, inline functions, or constant tables. |
| **6** | **Patch CPU reminder** | Informational reminder that each patch has a 96k cycle limit (G6 hardware test). Always passes. |
| **7** | **Post-build verification** | Informs that `g1fs.check_image` and `check_updater_stages.py` will gate the output. Both must print `ok` on all stages. |

---

## 5. Recovery Procedure

If the pedal hangs at the ZOOM logo following an interrupted write:
1. Open the **Recovery** tab in CF Loader.
2. Ensure the official Zoom updater path is configured.
3. Click **Build Factory Restore Updater**.
4. The tool builds a patched updater carrying Zoom's factory file-system image (resource 136) targeting flash 0x102000.
5. Put the pedal in update mode (hold both footswitches while connecting USB).
6. Run the generated `ZOOM G1X FOUR Factory Restore Updater.exe` by hand. Select ZOOM G Series for MIDI IN/OUT and click Execute.
7. Power cycle the pedal. The factory effects and file system are fully restored.

---

## 6. Where the Logs and Data Are Stored

All data generated by CF Loader resides under `build/loader/` (untracked scratch):

- `build/loader/loader.log`: Append-only chronological log of all tool executions, command arguments, output lines, and exit codes.
- `build/loader/<timestamp>/report.txt`: Complete build manifest recording input file CRC32s, configuration parameters, command stdout, and stage verification results.
- `build/loader/<timestamp>/FAILED`: Error marker left if a build step or check failed.
- `build/loader/status.json`: Persistent record of effect verification lifecycle (`built` -> `in image` -> `audio-pass` -> `cost-measured` -> `ok-save`), test dates, and notes.
- `build/loader/config.json`: Saved user configuration (official updater path, clean mode preference).
