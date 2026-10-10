# Brief for Sol: build the latest test updater, and the honest feature / MIDI status (2026-10-10)

Written by Claude before its quota ran out. Part A is the job (build one
update-mode updater with everything ready to test). Part B is what is built vs
not. Part C answers the owner's question about the MIDI controller: is there a
GUI, does it report which button was touched, can controls be named.
Companion briefs: `SOL_SUPERVISE.md` (your standing job), `GEMINI_LOADER_GUI.md`.

Rules that stay: Sol `gpt-5.6-sol`, low/medium effort, `< /dev/null`, one job at
a time, log to `docs/helpers/SOL_LOG.md`. You **build files only**. Never run an
updater `.exe`, never touch the pedal or a MIDI port, never push. The owner
flashes by hand (hold BOTH footswitches while connecting USB).

---------------------------------------------------------------------------
## Part A. Build the latest test updater

### A0. State at hand-off (checked 2026-10-10)
- Newest effects image `build/fw/img/fs_cf_ab_mufft.bin` (built 10-08 22:14)
  is STALE: it holds MUFFX built before the dspload fix. `build/MUFFX.ZD2`
  (10-08 23:18, dspload 53) is newer. Also nothing yet applies the dspload rule
  to CF 808 / CF RAT (rule: 3.7 x measured cold kernel kcycles, rounded up ->
  808 = 65, RAT = 64; both declare 80 today; recon/04 row 2026-10-08).
- Three existing .exe: `Comet Flower ZG1X4 Updater.exe` (CF firmware, no
  controller), `... + MuffT.exe`, `... Controller TEST Updater.exe` (controller
  mode, built 10-08 11:41, never run). The image inside the Controller TEST one
  is older than the MuffT image.
- Official updater path used so far:
  `C:/Users/z/Downloads/G1X FOUR_v2.00_Win_E/ZOOM G1X FOUR System v2.00 Updater.exe`
  (if missing, stop and write "needs the owner's updater" in SOL_LOG.md).
- Files in `build/fw/`: `res1_493412.bin` = stock main firmware;
  `res1_cfupd.bin` = CF firmware (logo/text edits, 176 bytes from stock);
  `res1_controller.bin` and `res1_cf_controller.bin` = controller firmware (both
  494,928 bytes). **Unresolved which base each one was built from**: byte
  compare shows `res1_controller.bin` differs from stock by only 14 bytes
  (= stock + hooks, no CF edits) and from `res1_cfupd.bin` by 190. The TEST exe
  is documented as "CF firmware + controller". Resolve this first (A1).

### A1. Decide the controller firmware, with proof
1. Extract resource 0x81 from `Comet Flower ZG1X4 Controller TEST Updater.exe`
   (pefile; `tools/make_fs_restore_updater.py` shows how resources are read) and
   compare its SHA-256 with `res1_controller.bin` and `res1_cf_controller.bin`
   (recon/04 and HANDOFF_2026-10-08 quote SHA-256 c6317cac...).
2. The wanted firmware = CF firmware (logo + start-up text identical to
   `res1_cfupd.bin`) + controller hooks. Build it with
   `python tools/make_controller_fw.py --base build/fw/res1_cfupd.bin --out build/fw/res1_cf_controller.bin`
   (check the script's `--stock` check accepts a const-edited base; its help
   says it does). Diff the result against `res1_cfupd.bin`: only the AIS
   section-load record, the 4 CALLP hook words and the new section may differ.
   List the differing offsets in SOL_LOG.md.
3. Do NOT use `--patch-fw` (slot-0 L2 residency): `make_fs_restore_updater`
   refuses it with `--logo`, and it still needs a heavy-effect test first.

### A2. Rebuild the effects image
Contents (what is worth testing now): the DIY effects CF 808 (`DRV808X.ZD2`,
display name "CF 808"), CF Muff (`MUFFX.ZD2`, rebuilt), CF RAT (`RATX.ZD2`),
the diagnostics PROBE10, PROBE30, G1GAIN, MEMPRB, RATT, T808, MUFFT, plus the
stock effects kept for A/B: TS_DRIVE and NYC_MUFF (`--keep`). Do NOT include
the retired `DRV808.ZD2` or the DR103 files.
1. If you change dspload for 808/RAT: edit only `effects/drv808x/manifest.json`
   (80 -> 65) and `effects/ratx/manifest.json` (30 -> 64; note it is 30 today,
   not 80), rebuild with `bash tools/build_g1.sh <name> ...` using the exact
   label/pic arguments from `git log` of the last build of each (see
   GEMINI_EFFECT_DESIGN.md §9), confirm the code bytes are identical to the
   previous build (only CRC + INFO dspload may change, as for Muff 83e4371).
   If you are not sure, skip the dspload change and say so in SOL_LOG.md:
   it is a number shown on the display, not a safety setting.
2. `.venv/Scripts/python.exe tools/make_g1_image.py --clean --keep TS_DRIVE.ZD2 --keep NYC_MUFF.ZD2 build/fw/res3_3137536.bin build/fw/img/fs_cf_latest.bin build/DRV808X.ZD2 build/MUFFX.ZD2 build/RATX.ZD2 build/G1GAIN.ZD2 build/PROBE10.ZD2 build/PROBE30.ZD2 build/MEMPRB.ZD2 build/RATT.ZD2 build/T808.ZD2 build/MUFFT.ZD2`
   (check the exact `--keep` syntax with `--help`; it must print `verified`).
   Existing images (`fs_cf_ab_mufft.bin`) are the reference: the new one should
   list the same files except for the rebuilt ones (`g1fs.py list` both and diff).
3. Presets: reuse `build/fw/img/presets_cf.bin` (patch 10 "CF test", 49 Empty;
   see recon/04 2026-10-06). Patches only change after a factory reset: put that
   in the test steps.

### A3. Build the updater and gate it
```
UPD="C:/Users/z/Downloads/G1X FOUR_v2.00_Win_E/ZOOM G1X FOUR System v2.00 Updater.exe"
.venv/Scripts/python.exe tools/make_fs_restore_updater.py "$UPD" \
  "build/fw/Comet Flower ZG1X4 Controller TEST Updater 2.exe" \
  --image build/fw/img/fs_cf_latest.bin --presets build/fw/img/presets_cf.bin \
  --splash <the splash png used for the existing updater> \
  --controller-fw build/fw/res1_cf_controller.bin
.venv/Scripts/python.exe tools/check_updater_stages.py "build/fw/Comet Flower ZG1X4 Controller TEST Updater 2.exe"
```
Find the splash/logo arguments used for `Comet Flower ZG1X4 Updater.exe` in
HANDOFF_2026-10-06/08 and `assets/`; **--logo conflicts with --patch-fw only**,
the existing CF updater used a logo, so keep it the same way (`--controller-fw`
and `--logo` combine: that is how the existing TEST updater was built; if the
tool refuses, say exactly which message). New file name, never overwrite the
old `.exe` files (they are the owner's known-good fall-backs).
Gate: `check_updater_stages.py` prints `ok` for every stage and none touches
boot 0x0-0x28000 or settings 0xbf000-0xc0000. If any stage is not ok: do not
leave the exe in place under a normal name; rename `FAILED_...` and log why.

### A4. Write the owner test card and log
Write `docs/OWNER_TEST_CARD_2026-10.md` (short, numbered, owner-facing) and
append the build to `recon/04_hardware_log.md` as "built, NOT run" with SHA-256
of exe, image, firmware. The card must contain, in this order:
1. Pre-check: AUTO SAVE off; have the factory-restore updater
   (`G1X FOUR FS restore (patched updater).exe` if present, else rebuild with
   no `--image`) and docs/RECOVERY_G1.md at hand.
2. Flash: update mode (both footswitches held while connecting USB), run the
   exe, MIDI IN/OUT "ZOOM G Series", wait for "Version update completed",
   power-cycle. Do not unplug mid-write.
3. **Boot normally first** (no buttons): the pedal must behave exactly as the
   CF build before: CF logo, CF-ZGX4 screen, effects present, a factory reset
   to get the new presets. If it does not boot: recovery per RECOVERY_G1.md
   (Zoom's official v2.00 updater rewrites main firmware).
4. Effect checks (each alone in a fresh patch, never save): CF 808, CF Muff,
   CF RAT audio passes; Probe 10 Load sweep for the freeze point; CF MuffT
   (timing tone) only if the owner wants a repeat.
5. **Controller mode** (recon/04 2026-10-08 row): power off, hold the GPIO0
   button (bitmap bit 9, believed Rhythm/Looper) while powering on; keep it
   held until the logo is gone. Then run `python tools/midi_listen_g1.py` on the
   PC and press things one at a time, writing the observed CC per physical
   control in the table in Part C. Power-cycle without the button: must be
   stock behaviour.
6. Report back: what booted, what each control sent, anything odd.

---------------------------------------------------------------------------
## Part B. Feature status (as of 2026-10-10, from the repo, not from memory)

| Feature | State | What is missing |
|---|---|---|
| CF 808 / CF Muff / CF RAT effects | built; audio proven on the pedal (808: tone test; Muff: 2026-10-08; RAT: plays) | none for sound; dspload numbers for 808/RAT not yet updated; no 5-slot full-patch CPU test (G6) |
| Kernel cost numbers | measured by TSCL (RAT 17.2k cold, 808 17.4k, Muff 14.1k per block) | block period vs clock mismatch (139.5 MHz vs 364.8 MHz) unresolved; Load-test costs withdrawn |
| Effects installed by update-mode image | proven 2026-10-06 | MIDI install/replace remains forbidden (bricked the pedal) |
| Splash / logo / presets | built and run (CF logo, CF-ZGX4 screen, empty presets) | none |
| USB MIDI **controller mode** (`firmware/controller`) | **built, never run on the pedal**; static audit recon/17-19 | owner's power-on test (Part A5); legends of the buttons |
| Slot-0 L2 residency patch (`--patch-fw`) | static checks closed | needs a heavy test effect on the pedal |
| USB audio | design + compiled prototype `firmware/usb_audio_proto/`, three TXCSR fixes | **blocked on controller-mode pass**; then silence-stream image, enumeration test, producer tap 11818c64; S8 needs the pedal |
| CF Loader GUI (effects) | Gemini is building it (`GEMINI_LOADER_GUI.md`, L0 done, `tools/cf_loader/` started) | L1-L5, Sol review (`LOADER_GUI_REVIEW.md`) |
| **MIDI monitor GUI / naming of controls** | **does not exist** (see Part C) | to be built; spec below |
| 5-slot accurate-effects CF firmware (vision) | nothing yet | long road; effect design gates G0-G7 |
| Firmware map | rows done, Gemini doing A2 guess pass, A5 merge is Claude's | see SOL_SUPERVISE.md |

---------------------------------------------------------------------------
## Part C. The MIDI controller: the honest answer

Facts below are from `firmware/controller/controller.c` (read 2026-10-10) and
recon/15, 17, 18, 19.

**Is there a GUI?** No. The only PC-side tool is `tools/midi_listen_g1.py`, a
command-line monitor (needs `mido`) that prints raw MIDI messages. Nothing
shows a picture of the pedal, nothing maps numbers to names, nothing stores
names. The CF Loader GUI brief deliberately does NOT open MIDI ports.

**Will it report which button was touched?** Yes, in the firmware as written,
every control has its own message, but only by number, and nothing has been
verified on hardware. Channel 1, status 0xB0 (Control Change):

| Control | Message | Values | Note |
|---|---|---|---|
| Footswitch (GPIO3 / GPIO5 fast path, events 0-3) | CC 20 and CC 21 | 127 press, 0 release | which is left/right is NOT confirmed |
| Ten normal buttons, bitmap bit i (events 5+2i / 6+2i) | CC 22 + i = CC 22..31 | 127 press, 0 release | bit -> GPIO pin: 0:4 1:2 2:6 3:27 4:24 5:26 6:37 7:38 8:86 9:0 (recon/15 table); **panel legends are not mapped** |
| Four knobs (events 25..28) | CC 40..43 | absolute 0..127, starts at 64 | firmware turns encoder deltas into an absolute value; the value is lost at power-off; which knob is which = to find out |
| Expression pedal | CC 11 | 0..127 calibrated | |
| Both footswitches together (event 4), repeats, system events | nothing | | consumed silently |

Quirks to know before trusting the table:
- The entry button (GPIO0, CC 31) is held at power-on; its press and release
  events (23/24) are swallowed until it is released, so CC 31 is not reported for
  that first press.
- Bursts: at most 4 messages per MainApp pass, queue of 16 button edges; when
  full the newest edge is dropped. Fine for a human, not for stress tests.
- Mode 0 (stock) sends nothing; the pedal's own screens and effect controls
  still run only when controller mode is OFF. In controller mode the dispatch
  hook consumes events (recon/17-18): confirm on the pedal whether the stock UI
  still reacts, and write it in the test card result.
- Press polarity: low = pressed was proven for the footswitches and the update
  check; assumed for the ten buttons.

**Can we name them?** Not in the pedal (the firmware only sends numbers). Naming
belongs on the PC side, and is cheap. What to build (a task for Gemini after
L5, or for you if Gemini is done; small, tkinter only, no new dependencies):

`tools/cf_midi_monitor.py` (or a tab in `tools/cf_loader` once L5 is
reviewed, but a separate script is safer: the loader has a "no MIDI port"
safety rule and must keep it):
1. Lists input ports, opens ONE input port (receive only; no output port is
   ever opened; no SysEx send). Needs `mido`+`python-rtmidi` or the same backend
   `midi_listen_g1.py` uses: copy its port-selection code, do not invent.
2. A table of the 17 controls above (id, default label "Button 3 (GPIO27)"),
   each with a **user-editable name** and a live state (pressed/released,
   last value, a small bar for 0..127). Highlight the row when its message
   arrives, and show a scrolling log: time, raw bytes, resolved name.
3. Names persist in `build/loader/midi_names.json` (control id -> name); a
   "Learn" mode: press "Learn Button A", touch a control on the pedal, the app
   binds that CC to the name. Export as CSV for the owner's DAW mapping.
4. Self-test without hardware: a "Simulate" button that feeds recorded messages
   (fixture list in the script) so Sol can test the mapping logic with pytest
   (`tests/test_midi_monitor.py`) with a fake port. The mapping lives in a pure
   function module with no tkinter import.
5. Safety: grep proof that the file contains no `open_output`, `send`, `Output`,
   or `pedal_g1` import.
6. Document the owner's physical test: press each of the 17 controls in turn,
   fill the names, save. This also resolves recon/17 A5 (legends), the owner's
   one remaining blocker before USB audio work.

What it cannot do: rename anything on the pedal, show which effect is loaded,
or work until the controller-mode firmware has been flashed and has booted.

---------------------------------------------------------------------------
## Order of work for you
1. A1 (identify firmware) -> log. 2. A2 -> A3 gate -> A4 card and hardware log
row, commit (docs + hardware log; `build/` is untracked). 3. Tell the owner the
exe name and SHA. 4. Then return to SOL_SUPERVISE.md cycles. 5. The MIDI monitor
is queued in `docs/helpers/GEMINI_NEXT.md` as M0..M2 after L5.
If any step needs a decision about boot, res5 or settings regions, stop and put
it in SOL_LOG.md "Open for Claude".
