# Handoff 2026-10-23 night (menu / budget / rig session)

Workspace `c:\Users\z\Documents\zoom project`, branch master (not pushed). Python `.venv/Scripts/python.exe`.
Owner flashes; Claude never flashes. Helpers: Sonnet subagents (Agent tool) and agy Gemini 3.8 Flash (High)
work; Argon quota back around 2026-10-24. Earlier handoff (CN chain main line): `HANDOFF_2026-10-23.md`.

## On the pedal now
**Updater 31** (`52995666`): Updater 30 (CF Probe link + watchdog + CFM Pre 5-char labels) + the **CF edit
header** (CFM Pre's name box reads "CFM PRE>DYNA COMP / MUFF FUZZ / MISTRESS / OUTPUT"). Owner: looks good.

## Built, not flashed (in order; steps in `docs/FW_RND_BENCH_2026-10-22.md` sections 11-12)
- **Updater 32** (`7015a3cb`) = 31 + **CF WattL** (DR103L, id 04000f8a) next to CF Watt.
- **Updater 33** (`b29f89c8`) = 32 + **CPU budget meter**: "NN%" top right of every edit page (worst block of
  the last ~0.74 s; inverted from 95 %); CFM Pre bar shortens to "PRE>stage". Flash 33 (it includes 32).
Files: `build/fw_rnd_2026-10-22/GUITAR AUDIO 3x - ... TEST.exe`.

## Next session, in order
1. Owner flashes **Updater 33**; check the meter on CF and stock effects, and that it never draws on
   Settings / Tuner / Rhythm screens (`tools/cf_probe.py screenshot`).
2. **Sound tests (owner postponed them):** CF Watt vs CF WattL by ear, and `tools/ua_bench.py run` (USB audio
   mode) on the CN patch with each: slot median + peak (baseline Watt 23.4k, peak 107 %).
3. **CPU ceiling test:** stack probe10/probe30, raise Load until lost frames / freeze; note the meter. Then
   re-declare CF dspload from measured cost (7 + 3 x kcycles, `tools/zd2_set_dspload.py`).
4. **CF Rig step 1** (`docs/RIG_DESIGN_2026-10-23.md`): live-trace per-slot on/off state and effect name with
   the probe (owner toggles effects; `build/probe/snap.py` + `diff.py`, as in
   `docs/EDIT_SCREEN_TRACE_2026-10-23.md`), then build the RIG overview display (rig patch = name prefix "RIG").

## What was learned / built this session
- **Edit screen, live** (`docs/EDIT_SCREEN_TRACE_2026-10-23.md`): page per slot `c011acf0+4n`, selected slot
  `c011abf4`, effect id `1181159c+84*slot`, edit renderer `c012e5a8` (called c013c050, c0135b08); knob value
  copies 118115b8/11811940/11811cc8. Screen-id cell still not found (c0184fe0 is the Settings sub-screen ptr).
- **Header + meter code:** `firmware/controller/cf_header.c` (`--cf-header` in `make_controller_fw.py`;
  `cf_edit_draw` wraps the stock renderer; `cf_header_tick` refreshes the meter from UpdateUI idle wake-ups
  while its pixels are still shown). Audio side: `ua_cpu` record at fixed **0xc01a8020**
  (`make_usb_audio_fw.py --cpu-meter`, usb_audio_tap.c). Tests: `tests/test_cf_header.py` (8).
  Recipe for 33: `make_controller_fw.py --base build/fw/res1_cf_usbname.bin --ui --cf-header --usb-product
  "Comet Flower ZG1X4 MIDI" --usb-audio-name "Comet Flower Audio Bridge"` -> `make_usb_audio_fw.py --probe
  --watchdog --cpu-meter` -> `make_fs_restore_updater.py <v2.00 updater> "<name> TEST.exe"
  --test-controller-fw <fw> --image build/fw_rnd_2026-10-22/fs_bench32.bin`. Without the new flags the recipe
  still gives Updater 30's firmware `d2af52c7`. v2.00 updater: `C:/Users/z/Downloads/G1X FOUR_v2.00_Win_E/`.
- **Free memory:** SDRAM c0187024..c01f4000 never written since power-on except our payloads (~370 KiB).
- **CF WattL** (Gemini, reviewed, f232dee): `effects/common/hiwatt_lite.h`, -18 % static (20.4k -> 16.7k),
  output within 8e-6 of CF Watt. Kit: `tests/host/build_hiwatt_lite.bat` + `hiwatt_lite_score.py` (36 tests).
  Further savings = fit the NFB-loop tube/power maths (7.5k) -> a model change, needs owner ABX.
- **Storage** (`docs/helpers/CF_STORAGE_SONNET_2026-10-23.md`): per-patch data = custom PTCF chunk (hook pack
  c0130e04, which zeroes the record, + unpack c013150c); global = DataStore record 53 (5 code sites); no free
  flash range (4 MiB chip full).
- **6th slot** (`docs/helpers/SLOT5_INVENTORY_SONNET_2026-10-23.md`): large/risky (517 KiB work buffer per
  slot, used SDRAM after the 5th, slot table inside a live pointer block, 25-30 edits). Decision direction:
  budget model + rig instead (`docs/BUDGET_MODEL_2026-10-23.md`).
- **CF Rig decisions (owner):** Bradshaw layout; rig engine in our firmware, not a slot effect; 5 slots = the
  switcher's loops; in a rig patch the RIG overview replaces the patch screen. AMP (CF WattL) + rack (delay,
  chorus, later pitch) + W/D/W mixer at the Post-looper hook. 6-step build order in the design doc.
- Small offer still open: CFM Pre labels without stage letters (Sens/Out/On, Sust/Tone/Vol, ...).

## Housekeeping
- Untracked, not ours this session: `comet_flower_drums.html`, `tools/drums/*` (studio files),
  `tests/test_comet_flower_studio.py` - leave for the owner. Three deleted bridge files still unstaged.
- Known unrelated test failure: `tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx`
  (run the suite with `--ignore=tests/host --deselect` it; 386 pass).
