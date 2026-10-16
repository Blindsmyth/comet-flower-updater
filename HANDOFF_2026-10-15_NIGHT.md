# Handoff 2026-10-15 (night): hardware is back, Comet Flower image and on-pedal screen

**Start here.** The previous handoff was `HANDOFF_2026-10-15_OFFLINE.md`; its queue and pitfalls still
apply where not superseded below. The owner is at the workstation **with the pedal**. Flashing stays
the owner's manual step (update mode: hold both footswitches at plug-in; select MIDI "ZOOM G Series";
press Execute). Never commit `.agents/` or `bridge/`. Commit small and often; push only on request.

Tests: `.venv/Scripts/python.exe -m pytest tests tools/test_usb_audio_proto.py -q` → **255 passed, 615 subtests**.
The lifecycle controller image must stay byte-identical (`tests/test_diag_readback.py` checks `3e7f5236…28b9`).

## What happened this session (all committed)

1. **Stack watermark read path reviewed:** every Task_create refills the stack with 0xbe
   (`c015f820 -> c016b140`), so the mark resets per worker; the readback now carries a worker-creation count.
2. **CF Loader GUI:** it crashed on launch (bad geometry); fixed, with indicators and gating
   (`docs/helpers/GUI_REVIEW_2026-10-15.md`). The owner then clarified that "GUI" means the pedal's own screen
   (memory `project-ondevice-ui`).
3. **On-pedal screen (works on hardware):** `firmware/controller/controller_ui.c`, built with
   `make_controller_fw.py --ui` (and `--diag-teardown` for the diag page). It hooks UpdateUI's infinite
   Event_pend at `c013c76c` (a 32-bit CALLP), waits in 50-tick slices, and draws in UpdateUI's own task:
   5x7 `c011d2d4(ctx,ch,page,x)`, 8x13 `c011ec48(ctx,s,x,y)`, flush = gate `c0161200(B14[149])` →
   `c016df00(0)` → `c016d880`. Host-compiled tests render the real draw calls
   (`tests/test_controller_ui.py`). Design: `docs/ONDEVICE_UI_2026-10-15.md`; recon:
   `docs/helpers/ONDEVICE_UI_RECON_REPORT.md` (+ Claude review: Sol had x/page swapped and chose a compact CALLP).
   - Controller page header "COMET FLOWER …"; diag page header "CLAUDE W#… t…" (the owner's nod), with the
     bottom line `b<beacons> s<sent> CC<n>=<v>`.
   - UpdateUI stack: 8 KB static task, +168 B (closed).
4. **First hardware runs (recon/04, 2026-10-15 rows; captures in `docs/hardware/`):**
   - **Worker stack max 940/2048 B** (3 workers): the stack gate is closed by measurement.
   - **4 USB re-plugs on batteries: no TX stall**; the readback works after reconnect: the liveness gate is closed.
   - Type-19 teardowns (~19 per (re)connect) all go through the queue 32/33 consumer (benign);
     **the abort drain (site 1) never runs**, even on unplug.
5. **Packaging:** `make_fs_restore_updater.py --test-controller-fw` accepts lifecycle + DIAG/UI hooks
   (the output name must contain TEST); `--controller-fw` stays strict. Test kit: `build/test_kit_2026-10-15/`
   (+ `RESTORE_stock_fw_factory_fs.exe`). Procedure: `docs/TEST_RUN_2026-10-15.md`.
6. **Comet Flower image:** `docs/CF_STOCK_IMAGE_2026-10-15.md`.
   - USB name "Comet Flower" (`tools/cf_usb_name.py`: const data; the descriptor builder `c01352a4` copies by
     bLength). **Update mode keeps "ZOOM G Series"** (the boot program res5 has its own strings).
   - Host tools find either name: `tools/pedal_ports.py`.
   - Clean FS (Zoom effects removed): CF 808 (DRV808X), CF RAT, CF Muff, DR103 (redesign; **first pedal
     run pending**), G1 Gain, CF ClkT. Presets `cfupd_res85.bin` (49 Empty + "CF test"; patches change only
     after a factory reset). CF logo, no "v2.0".
   - **Unified updater:** `build/cf_unified_2026-10-15/Comet Flower G1X4 Updater (TEST build).exe`
     (`056738e5…`, with timing beacons) + RESTORE + `Comet Flower Setup.cmd`.
7. **Tick test without a stopwatch:** the diag build sends a 7-CC beacon (CC118 begin/end, CC112..116 = tick
   word) every 1000 ticks; `tools/cf_tick_test.py` (guided, receive-only) fits ticks against the PC clock. Tests:
   `tests/test_tick_test.py`.
8. **Intro / installer front-end (owner request):** `tools/cf_intro/` (cracktro style, greetings to Razor 1911;
   original chip tune over the Bm–A–G–Em Comfortably Numb solo changes, shaped like Shine On pt. 1;
   `--no-music` or the [MUSIC] toggle). INSTALL only opens the updater after showing the steps. Launcher:
   `build/cf_unified_2026-10-15/Comet Flower Setup.cmd`. The owner has not listened to it yet.

## Pending from the owner (next session, in order)

1. Flash the **unified TEST updater** (056738e5…), then run `tools/cf_tick_test.py` → **the tick period**.
2. Listen to the intro; collect tweaks (tempo, lead, colours, scroller).
3. Confirm the Windows MIDI port name shows "Comet Flower" (if not: uninstall the device with hidden devices
   shown, then re-plug).
4. First pedal run of the **DR103 redesign** (alone, AUTO SAVE off), and the **CF ClkT** cycle-budget run
   (`docs/CYCLE_BUDGET_2026-10-15.md`).

## Next work (Claude)

1. **Release build** once the tick period is in: drop the diag hooks → "COMET FLOWER" controller page;
   decide with the owner whether the UI hook joins the strict `HOOKS` packaging (currently TEST-only).
   Keep a separate CLAUDE diagnostics updater.
2. **EDTB slot format** (recon/08) → `g1presets.py` can write patches holding CF effects → a CF starter bank.
3. **USB-audio status** on the screen once the audio candidate is layered with the UI (producers only store words;
   no drawing from the SOF Hwi).
4. ~~Intro `.exe`~~ done: `build/cf_installer/Comet Flower G1X4 Installer.exe` (one file: intro + tune +
   packed updater, hash-checked on unpack; `python -m tools.cf_intro.build_exe --updater <exe>`). Owner use only
   (contains Zoom code); a distributable must build the updater locally (Phase E). Remaining: optional reskin of Zoom's updater window (PE resources; separate, careful job).
5. Older queue items: the patch tool (Phase E), NAM A2 last.

## Owner decisions open

- **Boot-program rename** ("ZOOM G Series" in update mode): advised against for now (it writes the only recovery
  path; Zoom's updater reverts it anyway). Only on an explicit go, last, on adapter power.
- Which JUCE effects fill the 5 slots; the amp model (Tweed 5E3 undecided).

## Pitfalls added this session

- `c011e000` (the 5x7 string routine) has **no caller**; use the glyph routine `c011d2d4` in a loop and mark
  dirty pages (`11813250+ctx |= 1<<page`) yourself.
- UpdateUI pends forever: a draw hook alone never runs without a posted event; the pend wrapper is what ticks.
- The payload has no RTS: no division, no `switch` (refused `.switch`/`.cinit`), no sprintf.
- A shell `&& tail` chain masks pytest failures. Check the summary line before committing.
- Helpers: Codex Sol works without `--dangerously-bypass-approvals-and-sandbox` (that flag is denied by auto
  mode). Verify every helper claim against `main.dis`.
