# Brief: CF Installer redesign (Gemini 3.8 Flash High, 2026-10-23)

You are redesigning the **CF Loader** desktop app (`tools/cf_loader/app.py` Tkinter UI, `tools/cf_loader/core.py`
logic; run with `.venv/Scripts/python.exe -m tools.cf_loader`) into the **Comet Flower Installer**: the one place
where the owner backs up the pedal, chooses which effects and patches go on it, and builds the update-mode
installer (.exe) for the Zoom G1X Four.

## Hard rules (read first)
1. **Never touch the pedal.** Do not run anything that opens a MIDI port or talks to hardware
   (`tools/pedal_g1.py`, `backup_g1.py`, `backup_pedal.py`, `ua_bench.py run/measure`, `cf_probe.py`,
   `ceiling_test.py`, anything with `mido`). Never run any `.exe`. You may *write code* that calls these tools;
   test it with mocks / fake subprocess results.
2. Edit only: `tools/cf_loader/**`, `tests/cf_loader/**`, new files under `tools/cf_loader/assets/`, and your
   report `docs/helpers/GEMINI_INSTALLER_2026-10-23.md`. Do not edit any other tool; if one needs a change, write
   it in the report as a request. Do not commit (Claude reviews and commits).
3. **Write the report file first** (plan + checklist) and update it after every finished item, so nothing is lost
   if you run out of quota.
4. Python edits: `read_text/write_text(encoding="utf-8")` (default codepage here is cp1252).
5. Standard library Tkinter/ttk only, plus Pillow (already in `.venv`) for images. No new packages.
6. Before you finish: `.venv/Scripts/python.exe -m pytest -q tests/cf_loader` AND the whole suite
   `.venv/Scripts/python.exe -m pytest -q --ignore=tests/host --deselect tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx`
   must pass. Keep or update the existing tests; add tests for every new core function.

## Look and feel
- **Black and gold** theme (owner: "black and [g]old design"): near-black background (#0d0d0d / #161616 panels),
  gold accents (#d4af37 for headings, selected rows, primary buttons; #8a7020 for borders/disabled), off-white text
  (#eeeeee). One consistent ttk style (configure a custom theme via `ttk.Style`; `clam` as the base works).
- **Comet Flower branding:** window title "Comet Flower Installer"; header bar with the logo
  `assets/logo_comet_flower.png` (and/or `assets/splash_comet_flower.png`, both 1-bit, white on black: tint the
  white pixels gold with Pillow and scale up with NEAREST so they stay pixel-crisp). Set the window icon from the
  logo too.
- Layout: a left navigation column (Backups / Effects / Patches / Firmware & Build / Profiles) and the selected
  page on the right; a log pane at the bottom (keep the current non-blocking worker-thread + log-queue design).

## Pages
### 1. Backups
- "Back up pedal now": runs `tools/backup_g1.py <dir>` (all files: effects + FLST_SEQ.ZT2) and
  `tools/backup_pedal.py <dir>` (50 patches `PATCH_001..050.ZPTC` + manifest) into
  `build/backups/<YYYY-MM-DD_HHMMSS>/` in a worker thread, streaming output to the log.
- A list of existing backups (date, number of effects, number of patches, size) with Open folder / Delete
  (confirm dialog) / "Use as source" (feeds Effects and Patches pages).
- Backup is offered automatically (checkbox, default on) before building an installer.

### 2. Effects (checkbox list)
- One table of **every effect the installer can put on the pedal**: Zoom stock effects (from the factory effect
  list `FLST_SEQ.ZT2` inside the factory file-system image; see `tools/make_g1_image.py`, `tools/g1fs.py`,
  `tools/pedal_g1.py flst_entries`) and CF effects (the current CF library: `core.scan_library()`, plus the
  ZD2s in the newest `build/fw_rnd_*/fs_bench*.bin` image, readable with `g1fs.current_dir/read_file`).
- Columns: checkbox, name, file, group (category), source (Zoom / CF), declared dspload, on pedal now (from the
  selected backup, if any), and a filter box + "Zoom only / CF only / all" toggle + select all / none.
- Checked = installed by the next installer, unchecked = removed. Maps onto `make_g1_image.py`
  (`--clean` + `--keep NAME.ZD2` per checked stock effect, CF files as positional args; read its docstring) via
  `core.build_image_and_updater` (extend it; keep its preflight checks).
- Show a running total of the checked effects' file size against the file-system space (the image is
  0x2FE000 bytes; `g1fs` can tell free blocks) and refuse to build if it would not fit.

### 3. Patches (checkbox list)
- Lists the 50 patches from the selected backup (name + the effects in each slot: decode with
  `tools/ua_bench.py` `decode_entry` / the zoom-zt2 preset decoder used there; ids -> names via the effect table).
- Per patch: checkbox; actions **Back up** (copy the .ZPTC out), **Load** (from a backup/file into a chosen
  location), **Remove** (replace with Zoom's empty patch). Live patches are written over MIDI
  (`ua_bench.py` `pedal_session`, `load_patch`: write + read-back, proven on patch 50). Put those MIDI actions
  behind a clear confirmation ("this writes to the pedal now") and mark them **untested in the GUI**.
- **Default set** ("build a default"): the owner picks which patches form the factory set; the installer writes
  it into the presets region (`tools/g1presets.py`, passed to `make_fs_restore_updater.py --presets`). Explain in
  the UI that these appear only after a factory reset; live patches are never touched by the installer.
  If composing a presets region from arbitrary .ZPTC files needs a tool change, write the exact request in the
  report instead and offer only what `g1presets.py` supports today (blank + named patches).

### 4. Firmware & Build
- Build an installer exactly like the current TEST builds (see `docs/BUILDS.md` and
  `docs/FW_RND_BENCH_2026-10-22.md` sections 12-15 for the recipe): firmware `.bin` picker (default: newest in
  `build/cf_header/`), FS image built from page 2, presets from page 3, start-up screen from
  `tools/make_splash.py <version> <png>`, then `tools/make_fs_restore_updater.py <official updater> "<name> TEST.exe"
  --test-controller-fw <fw> --image <fs> --presets <bin> --splash <png>`.
- **Version**: field prefilled with the next `0.<updater>.<rebuild>` after the last row of `docs/BUILDS.md`; it goes
  on the start-up screen and into the file name. After a build, show the SHA-256 and the stage table the packager
  printed, and append a row to a JSON build log under `build/installer_log.json` (do not edit docs/BUILDS.md).
- Never flash: the app only writes the .exe and tells the owner to run it with the pedal in update mode.

### 5. Profiles ("set a default so when you update you can set")
- Save / load / rename / delete named profiles (JSON next to the existing config): the checked effects, the
  default patch set, firmware choice, splash version scheme, backup-before-build. One profile is the default and
  is preselected on start. "Update with default" button = backup (if ticked) + build with the default profile.

## Deliverables
- The redesigned app, working offline (no pedal) with clear disabled states when the pedal or a backup is
  missing; screenshots are not required (you cannot open a display reliably) but describe the layout in the report.
- Tests: core functions for effect list assembly, profile save/load, version bump, command lines built for
  make_g1_image / make_fs_restore_updater (assert exact argv), patch list decoding from a fake backup folder.
- Report `docs/helpers/GEMINI_INSTALLER_2026-10-23.md`: what was built, what is untested, every requested change to
  files outside your whitelist, and open questions.

Not yours (Claude does it): the boot logo / flower animation in firmware.
