# CF Loader GUI review — 2026-10-11

Reviewed Gemini's brief, loader core/UI/tests, DSP and recovery requirements, and the existing image, updater, stage, presets and slot-memory tools. Changes are confined to tools/cf_loader, tests/cf_loader and this review. No commit, push, reset, cleanup, device access, backup execution or updater execution was performed. Existing unrelated untracked files were left alone.

## Findings and fixes

- **Timeout/cancel (high):** Both regressions reproduced on Windows: a silent 1.5-second Python child returned success despite a 0.15-second deadline/cancellation. Blocking pipe reads now run in a reader thread; the controlling thread checks timeout/cancel independently, kills and waits for the child, drains output, closes the pipe and logs its exit. Streaming stderr and final text without a newline are covered.
- **PROBE10 preflight bypass (high):** Baseline HEAD loaded in memory with fake runners reproduced both missing and wrong-target probes being accepted. The effective selection now includes the required probe before validation and counting, without adding the same path twice. GUI preflight includes the option; build re-inspects all selected files. Tests cover missing probe, target, CRC, slot memory, oversize marker, selected ID/name collision, stock ID collision and the 110-file boundary.
- **Failure handling:** Report-input errors after folder creation now leave FAILED/report.txt. Reports record quoted attempted commands, exit codes/output and updater size/CRC. Image and recovery workflows reject empty/refused stage output even with exit zero. Tests cover nonzero exits, cancellation and stage failures while preserving previous output.
- **Cost gate:** Missing, nonfinite and impossible cost/readings are rejected. A new built/in-image stage clears old audio/cost approval, preventing reuse of prior approval after a rebuild. GUI validates input before recording it.
- **Empty presets:** BLANK.ZPTC is a 760-byte patch, not the 0xB000 resource required by --presets. The loader now invokes g1presets.py blank on build/fw/res2_45056.bin into the fresh output folder and passes that resource. Missing input fails explicitly. Selected splash paths are no longer silently ignored when missing.
- **GUI:** Deferred failure callbacks now capture exception strings before Python clears the exception variable. Build/recovery cancellation is wired; recovery refuses a concurrent build. Backup uses a fresh output folder and an explicit confirmation dialog repeating the power-cycle rule; this path was not executed.
- **Launch boundary:** run_tool now accepts only resolved configured/current Python interpreter paths, rather than any executable whose name ends in python.exe.
- **Stage gate:** A zero-exit stage check with only one harmless stage line previously passed. The loader now requires the filesystem erase at 0x102000/0x2fe000 and the resource 0x88 write at 0x102000, both marked ok. A read-only check of an existing patched updater produced this pair and passed the gate.

## Verification

Final command: `.venv/Scripts/python.exe -m pytest tests/cf_loader -q -p no:cacheprovider`

Result: **61 passed in 1.69s** (final rerun, including the stage-pair regression cases). `git diff --check` passed.

Tests use synthetic ZD2 fixtures and fake build runners; real subprocess tests execute only Python children. Existing RATX inspection tests also pass. All seven red preflight lines are individually tested to block execution. Recovery succeeds without scanning the library, omits --image and invokes stage verification.

Static safety proof: the loader has one Popen site, guarded by the interpreter-path check, with argument lists and no shell=True. Updater paths are data arguments to packaging/checking scripts. UI startfile calls open output directories or loader.log, never updater files. No loader imports mido, rtmidi or pedal_g1 or opens a MIDI port; Advanced backup is the sole device-capable subprocess route. make_g1_image.py imports offline helpers from pedal_g1 but its image-building path does not call open_session. Its existing g1fs.check_image gate remains intact. No Zoom binaries or build outputs were added to tracked paths.

## Remaining limitations

- No display-driven GUI test, real updater packaging/stage run, or hardware validation was performed. Packaging/recovery tests verify orchestration with fake runners, not actual firmware acceptance.
- File counts remain estimates for the documented factory layout (105 total, 27 non-effect files); arbitrary replacement factory images are not counted dynamically. Official-updater identification checks structure/resource size, not a pinned full-file hash.
- Slot-memory calculation duplicates the existing helper; the brief's requirement to invoke that helper for every validation is not fully implemented. Preflight does not expose every optional-input failure as a separate red line. Library scan/preflight still run on the UI thread.
- Status is filename-keyed, not content-hash-keyed. Rebuilds revoke approval, but replacing a file without rebuilding can leave old status visible. The wizard does not persist every checklist tick or provide a structured audio-failure record.
- Timeout cleanup covers the direct Python child used by loader tools. A future tool spawning descendants that inherit stdout would require process-tree/job-object cleanup. Disk-write failure can prevent FAILED/report creation; concurrent external input changes are not fully isolated.
- Recovery instructions remain reachable without effects. Physical recovery and CPU-test procedure precision remain owner/hardware work; no device claims were inferred from these tests.
