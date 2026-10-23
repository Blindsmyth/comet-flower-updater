# Handoff 2026-10-23 evening (ceiling test, gate 340, installer app, start-up bloom)

Workspace `c:\Users\z\Documents\zoom project`, branch master (not pushed). Python `.venv/Scripts/python.exe`.
Owner flashes; Claude never flashes. Earlier handoff today: `HANDOFF_2026-10-23_NIGHT.md`.
Every build and its status: **`docs/BUILDS.md`** (version scheme 0.\<updater\>.\<rebuild\>, shown on the
start-up screen). Details per build: `docs/FW_RND_BENCH_2026-10-22.md` sections 13-19.

## On the pedal now
**0.34.7** (`f3e9beae`, firmware `d8068692`, FS `fs_bench343.bin`): owner confirmed the bloom plays at start-up.
Contents: CF edit header + CPU meter (inverted from 88 %), PROCESS OVERFLOW gate 340, CF effects declare
their measured load, PROBE 10/30 in the effect list, CF WattL, CF Probe link + watchdog, timed start-up bloom.
Power-on today: ZOOM (boot program, ~1 s) -> bloom (bud -> petals -> "COMET FLOWER") -> "CF-ZGX4 / TEST 0.34.7".

## Waiting on the owner (in order)
1. **Did the owner run the one-time boot-logo installer?** `build/fw_rnd_2026-10-22/COMET FLOWER BOOT LOGO - bud
   - run once.exe` (`052c94b2`) replaces the boot program's ZOOM with the bloom's bud. Unclear whether it was run.
   If it was run and ZOOM is still there: stop, ask what the updater window said (boot write not taken?).
   Procedure: mains power, direct USB, nothing else open, update mode, run once, do not touch.
2. 0.34.3+ checks (section 15): CN patch plays, meter ~80 % not inverted; CFM Pre + Watt + RA200 + 808 + RAT
   must give PROCESS OVERFLOW (sum 349 > 340); looper/rhythm on a heavy (~80 %) patch stays responsive (unmeasured).
3. Postponed since 33: CF Watt vs CF WattL by ear; `tools/ua_bench.py run` with each (WattL dspload still 69, unmeasured).
4. First real use of the new installer app (below): backup, effect ticks, build.

## Learned / built this session
- **CPU ceiling** (probes, `tools/ceiling_test.py watch`, `build/ceiling.csv`): one slot trips our watchdog at
  64k cycles (48 %); two slots: audio keeps running at 2756 blocks/s up to 92 % mean, but **the UI/knobs lock up
  at ~92 % mean**; ~90 % usable. Hence meter warning 88 % and gate 340 (= ~88 % on 7 + 3 x kcycles).
- **Gate:** one MVKH at c0141b54 (file 0x35ad0, the only 230.0f); `make_controller_fw.py --gate 340`, packager
  accepts only that constant (230..400). Re-declared dsploads: `build/fw_rnd_2026-10-22/dspload_0.34.3/`.
- **Splash with version:** `tools/make_splash.py <ver> <png>` + `make_fs_restore_updater.py --presets
  build/fw/cfupd_res85.bin --splash <png>` on every TEST build.
- **Effects must be added with `tools/make_g1_image.py`** (it adds the FLST_SEQ.ZT2 list entry); Updater 34 lacked it.
- **Start-up bloom:** `firmware/controller/cf_boot.c` (`--boot-anim`, hook c014db78 = the start-up logo blit
  c011c508). UI ticks never arrive during the logo screen (0.34.4/0.34.5 stuck on frame 0), so it now plays
  inside the call on TSCL (70 ms/frame, capped waits, starts TSCL if stopped). Frames + boot logo:
  `tools/make_boot_anim.py` (`boot_anim.h`, `assets/boot_logo_bud.png`, preview `build/boot_anim.gif`).
  Controller payload ~15.5 KiB of its 16 KiB (c01a0000..c01a4000): little room left; next additions need the
  reservation grown (c01a4000..c01a8000 is free) in `controller.cmd` + `CTL_SIZE`.
- **Boot logo:** `tools/make_boot_logo_updater.py` = Zoom's own boot stages only, stock v2.00 boot program
  (SHA pinned) with only the 184 logo bytes changed; `check_updater_stages.py` refuses it on purpose.
  Undo = Zoom's official v2.00 updater.
- **Comet Flower Installer app** (`.venv/Scripts/python.exe -m tools.cf_loader`; Gemini 3.8 Flash High +
  Claude review, `docs/helpers/GEMINI_INSTALLER_2026-10-23.md`): black/gold, pages Backups / Effects / Patches /
  Firmware & Build / Profiles; screenshots `build/installer_pages.png`. Firmware default = the "flash this" row
  of docs/BUILDS.md (`approved_firmware_hash`; 0.34.5 was packaged with a shelved build before this fix);
  shelved binaries in `build/cf_header/shelved/`. Default effect ticks = newest bench image.
  **Open:** default patch set (needs `g1presets.py` to compose .ZPTC into the presets region; today the build
  keeps the CF presets); live MIDI patch write (`patches.write_patch_live`) untested on the pedal;
  "On Pedal" column needs a fresh backup (only 2026-10-04 exists).

## Next work (suggested)
1. Owner answers item 1 above; then CF Rig step 1 (`docs/RIG_DESIGN_2026-10-23.md`): live trace per-slot
   on/off + effect name with the probe, then the RIG overview screen.
2. `g1presets.py compose` (default patch set for the installer).
3. Measure CF WattL on the pedal and re-declare its dspload.

## Housekeeping
- Untracked, not ours: `comet_flower_drums.html`, `tools/drums/*`, `tests/test_comet_flower_studio.py`,
  `docs/HANDOFF_DRUM_MACHINE_EMULATOR.md`; three deleted bridge files still unstaged. Leave for the owner.
- Tests: `.venv/Scripts/python.exe -m pytest -q --ignore=tests/host --deselect
  tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx` (425 pass; the deselected one is a known failure).
