# CF Loader GUI review — 2026-10-15 (Claude, offline)

Owner request: check how the GUIs are built and whether they work, with the
expected visual indicators and features. The only GUI is CF Loader
(`tools/cf_loader/app.py`, tkinter). `cf_midi_monitor.py` and the diag
capture tools are CLIs.

Method: code read, a launch at the 960x640 minimum size with screenshots of
every tab, and checks against the current project state (handoff 2026-10-15).

## Fixed now (commit 5c02458)

| # | Finding | Fix |
|---|---|---|
| F1 | **The GUI crashed on launch.** `geometry("1024, 700")` raised `TclError: bad geometry specifier`, so the window never opened. No test constructed the window. | `"1024x700"`. New `tests/cf_loader/test_app_smoke.py` builds every tab. |
| F2 | "Authorize OK to Save" was enabled at construction. It was disabled only after an effect was selected in the Test tab, so with an empty library it started enabled. The core still refused the save. | The button is created disabled. The smoke test asserts it. |
| F3 | Dead `_record_cost_test` read a removed `freeze_load_var`. | Removed. The core still rejects the Probe 10 inference. |

## Open: visual indicators

| # | Where | Finding | Proposed |
|---|---|---|---|
| V1 | Library | Rows have no colour. An invalid, oversize or near-limit effect looks the same as a good one. T808 has **456 B** of slot heap free and is not flagged. | Treeview tags: red = rejected, amber = < 2 KiB free, green = in image or tested. Add a legend line. |
| V2 | Library | Selection is the text `[ ]`/`[x]` and needs a double-click or the space key. Nothing tells the user how to select. | A hint label, or a checkbox-style image column; a selected-count and total-slot-memory summary. |
| V3 | Library | Diagnostics (CLKT, MEMPRB, PROBE10/30, DR103D) are mixed in with real effects. | A "Kind" column or a filter (effect / diagnostic), from `manifest.json`. |
| V4 | Build | The pre-flight panel is clipped at 960x640: Check 7's message is hidden and there is no scrollbar. | Add a scrollbar, or put the checks in a Treeview with ✔/✖ icons. |
| V5 | Build / Recovery | There is no busy indicator during a build: no progress bar or spinner, only a status string. Cancel is always enabled. Recovery's button is not disabled while it runs. | Indeterminate `ttk.Progressbar`; disable action buttons while busy and enable Cancel only then. Show the current pipeline step (image / patch / stage check). |
| V6 | All | `style="Accent.TButton"` is never defined, so primary buttons look like every other button. | Define the style (colour and bold). |
| V7 | Library | The Stage column is plain text. | Colour by stage. A tooltip with the history and date from `status.json`. |

## Open: workflow and features

| # | Finding | Proposed |
|---|---|---|
| W1 | The Test wizard's checkboxes 1–5 gate nothing. "Record Audio Pass" works with every box unchecked and for an effect that was never in an image. | Enable each step only after the previous one. Require stage ≥ `in image` for audio pass. Reset the checklist when the effect changes. |
| W2 | Steps 2–4 (update mode, flash, power cycle) are per image, not per effect, but the wizard repeats them per effect. | Move them to a per-build "Flash checklist" tied to the `build/loader/<timestamp>` output. |
| W3 | Step 7 (CPU) has no input. The TSCL route now exists (CF ClkT, `docs/CYCLE_BUDGET_2026-10-15.md`), but the GUI cannot record a reading. The core caps cost at 96,000, from the old budget; the current estimate is ~132.4k cycles per block, pending the ClkT run. | After the ClkT run: an input for per-block TSCL cycles (and a ClkT readback import). Tie the cap to the measured budget, not a constant. |
| W4 | There is no full-patch (5-slot) view: the summed cost and memory of a planned patch. | A "Patch planner" panel: pick up to 5 effects and show the summed cycles against the budget. |
| W5 | The firmware candidates (controller B1, USB audio C, slot-0 B4) do not appear. This is correct while DO_NOT_FLASH applies. When they are released, they need the same pre-flight and hash-pinning display. | A read-only "Firmware candidates" panel that shows each candidate's hash and state (DO_NOT_FLASH). Building stays CLI-only until the owner approves. |
| W6 | The diag readback (`capture_ctl_diag.py` / `decode_ctl_diag.py`) is CLI-only. | Optional: a Diag tab that runs the receive-only capture and shows the decoded report. It must stay receive-only. |
| W7 | Status keys are stored uppercased (`filename.upper()`), and the app reads them by the scanned name. This works only because every build output is uppercase. | Normalise on both sides. |

## Suggested order (owner's call)

V4, V5, V1 and W1 are small and high-value; they can be done offline now.
W3 and W4 depend on the CF ClkT result. W5 and W6 wait until the hardware
gates open.
