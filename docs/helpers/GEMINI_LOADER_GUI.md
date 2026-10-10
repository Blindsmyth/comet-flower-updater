# Brief for Gemini: the Comet Flower effects loader (GUI) (2026-10-10)

Goal: a small Windows desktop app, "CF Loader", so the owner can pick built
effects (`build/*.ZD2`), put them on the G1X Four the proven safe way, and run
the on-pedal tests, without typing commands. This is front-end work around
tools that already exist and are proven. **The app does not invent a new way
to talk to the pedal.** That is where the one real brick came from.

You never touch the pedal. You build and test the app with fixtures. The owner
runs every installer and every test by hand.

Read first: `docs/DSP_RULES.md` (§2 installing, §5 order of work),
`docs/RECOVERY_G1.md`, `docs/helpers/SAVE_PROTOCOL.md`,
`docs/helpers/GEMINI_EFFECT_DESIGN.md` (§9 describes the files the app handles),
and the docstrings of `tools/make_g1_image.py`, `tools/make_fs_restore_updater.py`,
`tools/check_updater_stages.py`, `tools/backup_g1.py`, `tools/g1fs.py`,
`tools/pedal_g1.py` (only its `--dry-run` / `writetest` docs).
Your known weakness: plausible claims. Quote the doc or code for every
behaviour you rely on; if a tool's behaviour is unclear, run it with
`--help` or on a scratch copy and paste the output.

## 1. What "load" means here (decided, do not redesign)

| Path | Status | In the app |
|---|---|---|
| Update-mode image: `make_g1_image.py` -> `make_fs_restore_updater.py --image` -> owner runs the patched updater in update mode | **proven on the pedal 2026-10-06** | the ONLY install path. Fully implemented |
| MIDI `install` / `replace` / `uninstall` (`pedal_g1.py`) | **bricked the pedal** (DSP_RULES §2) | **not offered. No button, no hidden option, no code path that sends a MIDI write** |
| `pedal_g1.py writetest`, `backup_g1.py` (read-back, read-only apart from a verified temp file) | proven, still risky when USB is marginal (the pedal's USB is a hand-soldered repair, recon/07) | shown under "Advanced", off by default, with the DO-NOT-POWER-CYCLE banner text from the tools reproduced; only `backup_g1.py` is wired in (run it before the first image) |

Consequence for the user experience: loading an effect = building a 3 MB file
system image and flashing it in update mode (both footswitches held while
connecting USB). The app makes that routine and checked; it cannot make it
instant. Say so in the UI help text.

The app builds the patched updater from the official Zoom updater that **the
user selects themselves** (file picker, remembered). It never bundles or
downloads Zoom binaries (project rule, ROADMAP end goal). It never launches
the patched updater: it shows the path, "Show in Explorer" and the checklist.

## 2. Screens (tkinter + ttk, standard library only)

Use tkinter: it ships with the Python in `.venv` (check with
`.venv/Scripts/python.exe -c "import tkinter"` and paste the result). No new
dependencies, no installer. Min window 900x600, resizable, keyboard usable.

```
+------------------------------------------------------------------+
| CF Loader        [Library] [Build image] [Test] [Recovery] [Log] |
+------------------------------------------------------------------+
| LIBRARY                                                          |
|  [x] RATX      CF RAT    id 03000f83  .text 6.1K state 220  OK   |
|  [ ] MUFFX     CF Muff   id 03000f84  ...                   OK   |
|  [ ] DR103     DR103     id 04000f81  ...        OVERSIZE (!)    |
|  status: built | in image | audio-pass | cost-measured | ok-save |
|  [Rescan build/]  [Details...]                                   |
+------------------------------------------------------------------+
| BUILD IMAGE                                                      |
|  Official updater: [ ...ZOOM G1X FOUR System v2.00 Updater.exe ] |
|  Base: (o) clean + chosen effects  ( ) keep stock: [list]        |
|  [ ] add PROBE10 (cost test)   [ ] empty patches  [ ] splash png |
|  Pre-flight:  7 checks ...  all green / first red blocks Build   |
|  [Build image]  ->  build/loader/<stamp>/ (image, updater, report)|
+------------------------------------------------------------------+
| TEST   wizard, one step visible at a time (section 5)            |
+------------------------------------------------------------------+
| RECOVERY  restore-to-factory updater + the steps from RECOVERY_G1|
+------------------------------------------------------------------+
| LOG   every command run, its output and exit code, saved to file |
+------------------------------------------------------------------+
```

### Library
- Scan `build/*.ZD2`. Per file show: filename, name/id/target from
  `zd2 inspect`, size, `.text`/const/state/stack from the matching
  `build/<FILE>.ZD2.REPORT.md`, `check_slot_mem.py` result, and whether a
  `.ZD2.oversize` sibling exists (red, cannot be selected).
- Refuse to select a file whose target is not G1 (0x02), whose CRC fails, or
  whose id collides with another selected file or a stock effect id.
- Status per effect is stored by the owner, never inferred (section 5).

### Build image
Pre-flight checks, each a visible green/red line with the reason; **Build is
disabled until all are green**:
1. the official updater file exists and is the v2.00 G1X FOUR one (the file
   the patch tools accept); record its size and CRC32 in the report;
2. every selected `.ZD2` passes the Library rules above;
3. no duplicate id or filename within the selection;
4. file count in the resulting image: stay well under 127 (DSP_RULES §2);
   red above 110, with the count and why;
5. each effect file `<= 40 KiB` slot check passed (from `check_slot_mem.py`);
6. no limit on how many effects are chosen (slots are patch positions), but
   show a reminder that CPU for a full patch is the owner's G6 test;
7. after building: `g1fs.check_image` on the image (via `make_g1_image.py`'s
   own re-read), then `check_updater_stages.py` on the updater must print
   `ok` for every stage. Any failure deletes nothing but marks the output
   folder `FAILED` and shows the reason.
Run steps by calling the existing scripts as subprocesses with
`.venv/Scripts/python.exe` (never import their `main`, never copy their
logic). Output goes to a fresh timestamped folder under `build/loader/`; an
existing folder is never overwritten. A `report.txt` records: inputs with
CRC32, options, tool commands and exit codes, check results.

### Test (wizard)
Steps copied from DSP_RULES §5 step 5/6 and §4, one screen each, owner ticks
each: AUTO SAVE off; enter update mode (hold both footswitches while
connecting USB); run the patched updater, MIDI IN/OUT = "ZOOM G Series",
wait for "Version update completed"; power cycle; effect alone in an empty
patch; audio passes? (yes/no/notes); cost test with PROBE10 next to it
(show the formula exactly as DSP_RULES §4 states it, quote it in code
comments, and have a field for the reading and a computed number; if the
procedure text is not precise enough, say so in your result file rather than
inventing it). Results are saved to `build/loader/status.json`
(effect filename -> stage reached, dates, notes). The Library shows the stage;
"ok to save patches" is only offered after audio-pass AND cost-measured. A red
banner "do not save patches with this effect" shows on every earlier stage.

### Recovery
- Button "Build restore updater" -> `make_fs_restore_updater.py` with no
  `--image` (factory), then `check_updater_stages.py`.
- The text of RECOVERY_G1.md "What fixed it" as a numbered checklist, and
  "What does NOT fix it". Always reachable, works with no `build/*.ZD2`.

### Log
Append-only file `build/loader/loader.log` + the Log tab. Each command
shown as the user would type it, exit code, last 40 lines of output. Nothing
is hidden.

## 3. Architecture

```
tools/cf_loader/
  core.py       pure functions: scan library, parse reports, pre-flight
                checks, run a tool (subprocess wrapper, streams lines, timeout,
                cancel), status.json read/write. NO tkinter import.
  app.py        tkinter UI, calls core only; runs subprocesses in a worker
                thread and posts lines to the Log via queue + after().
  __main__.py   `python -m tools.cf_loader` (from the repo root)
tests/cf_loader/test_core.py   pytest, no display, no pedal
docs/LOADER_GUI.md             user-facing guide (screenshots optional)
```
Rules: UI never blocks (long commands in a worker thread); every path is
quoted/argument-list (no shell strings, no `shell=True`); paths with spaces
must work (the repo path has a space: "zoom project"); the repo root is found
from the file location, not the working directory; config (updater path, last
options) in `build/loader/config.json`.

## 4. Safety requirements (each must have a test or a pasted proof)
1. `grep -rn "mido\|rtmidi\|pedal_g1\|midi" tools/cf_loader` shows no code that
   opens a MIDI port; the only allowed pedal-touching call is launching
   `backup_g1.py` as a subprocess from the Advanced panel, behind a
   confirmation dialog that repeats its DO-NOT-POWER-CYCLE rule.
2. No code launches any `.exe`. Test: assert the string `.exe` is only ever
   passed as an argument to `make_fs_restore_updater.py` /
   `check_updater_stages.py`, never to `subprocess` as the program.
3. Build is impossible with a red pre-flight (test it by faking each check red).
4. Output folders are never overwritten or deleted by the app (test).
5. A failed or cancelled step leaves a `FAILED` marker and the report; the
   previous good output is untouched.
6. No Zoom binary is copied into the repo's tracked files; `build/` stays
   untracked scratch.

## 5. Tasks (do in order; report file first)
Create `docs/helpers/LOADER_GUI_RESULT.md` first (headings: Status, Findings,
Decisions, Tests, Problems) and update it after every step. Commit only the
files named in the step.

- **L0 Survey (no code).** For each tool in the table of §1 write: exact
  command line used by the app, its inputs/outputs, exit codes, how long it
  takes, what it prints on success. Run `--help`/dry-run only. Anything
  unknown -> "unknown", with how to find out. Also list the stock effect ids
  and filenames the app must refuse to reuse (from `tools/g1fs.py list` on
  `build/fw/res3_3137536.bin` and the effect list). Commit the result file.
- **L1 `core.py` + tests.** Everything in §2 that is not drawing. Tests use
  tiny fixture ZD2 files copied from `build/` and a fake tool runner. Paste
  `pytest tests/cf_loader -q` output.
- **L2 Library + Build tabs.** Run it and paste the pre-flight panel text for
  (a) all green with RATX selected, (b) red with DR103's oversize file
  selected (if the file is not oversized in this tree, fake it in a temp
  copy), (c) red for a duplicate id. Build once for real against the official
  updater only if the owner's file path is configured; otherwise stop at
  "pre-flight green" and say so. Check the produced updater with
  `check_updater_stages.py` and paste its `ok` lines.
- **L3 Test wizard + status.json.** Unit-test the stage rules (cannot reach
  "ok to save" without audio-pass and cost-measured).
- **L4 Recovery + Log + Advanced (backup).** Same rule: tested with the fake
  runner; never run `backup_g1.py` for real.
- **L5 Docs.** `docs/LOADER_GUI.md`: install (nothing), first run, the loading
  flow in 8 numbered steps, what each red check means, where the logs are.

## 6. Do not
- Edit anything outside `tools/cf_loader/`, `tests/cf_loader/`,
  `docs/LOADER_GUI.md`, `docs/helpers/LOADER_GUI_RESULT.md`. In particular not
  the tools in §1, not `docs/DSP_RULES.md`, not effects.
- Run `pedal_g1.py`, `backup_g1.py`, `midi_listen_g1.py`, any updater
  `.exe`, or open any MIDI port. Fixtures only.
- Add dependencies, a web server, auto-update, telemetry, or network code.
- Invent behaviour of a tool; if it is unclear, write "unknown" and ask via the
  result file.
- Commit build outputs, Zoom binaries, or `build/loader/`. `git push` ever.

## 7. Acceptance (reviewer = Sol, then Claude)
Pytest green; all six §4 items demonstrated; Library and pre-flight work on
the real `build/*.ZD2`; the app cannot build with a red check; the only
install path is the update-mode image; no MIDI write path exists anywhere in
`tools/cf_loader`. Sol writes `docs/helpers/LOADER_GUI_REVIEW.md`; Claude
spot-checks when quota returns. The first real flash is the owner's, by hand.
