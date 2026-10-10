# CF Loader GUI review

## L0 survey — 2026-10-10

Verdict: **correction needed before L1**. No GUI code exists in this commit, so the six safety requirements and L1–L5 acceptance remain untested.

- **Confirmed:** The factory image contains 105 files, including 78 `.ZD2` files. Parsing its `FLST_SEQ.ZT2` with `pedal_g1.flst_entries` gives 130 name/ID pairs. All 130 pairs in `LOADER_GUI_RESULT.md` match, with no missing names, extra names, or wrong IDs. This used `.venv/Scripts/python.exe` on the image only; no pedal command was run.
- **Confirmed:** `make_fs_restore_updater.py` accepts the reported `--image`, `--splash`, and `--presets` options (`tools/make_fs_restore_updater.py:331-337`). Its image length and stage checks are at lines 294-305, and it writes the destination only after those checks (line 322).
- **Correction:** The `backup_g1.py` exit-code list is incomplete. `tools/backup_g1.py:95-97` returns **2** for wrong argument count, and line 105 exits with **1** when no `ZOOM G` MIDI port is found. The survey lists only 0, 3, and 4. Add 1 and 2 before using the list for app error handling.
- **Unverified:** The report says `--help` and dry runs were performed but pastes no command output. This review relied on source inspection and the offline image check. L1 tests should use fake runners as required by the brief.
