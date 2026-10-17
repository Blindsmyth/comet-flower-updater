# Brief: make ua_capture's defect detector reliable on real strumming (2026-10-17)

`tools/ua_capture.py` `detect_glitches()` (linear-prediction residual detector, docs/helpers/USB_OPT_ARGON_2026-10-16.md)
is clean on hum and synthetic plucks but flags 14-89 "lost frames" per 3 s take on REAL strummed guitar
(`build/ua_takes/starts_tap3/s1.wav` .. `s15.wav`, Bm-G-F#-Em strums, -22..-28 dBFS). Claude inspected the flagged
spots (e.g. s13 frames 20054, 20252, 20283): smooth waveforms at pick attacks, no steps: false positives.
These 15 takes are the false-positive corpus: treat them as clean except the leading priming zeros.

## Task
1. Add tests in `tools/test_ua_capture_glitch.py` (skip if the wavs are missing):
   a. each of s1..s15 must give 0 events (priming excluded);
   b. inject real USB-style defects into those same takes at known random positions (fixed seed), one per
      take per kind: splice out 1, 8, 44 and 45 frames; repeat 1 and 44 frames; insert a zero run of 44/45
      frames; each must be found within +-2 frames, with the right kind;
   c. all existing tests keep passing (hum, synthetic plucks, the 5-min hum take
      `build/ua_takes/longrun_20261016_hum.wav` must still report its one real splice near frame 217).
2. Change `detect_glitches` (and only code in `tools/ua_capture.py`) until all tests pass. Ideas, not
   requirements: confirm a forward-prediction outlier with a backward-prediction outlier at the same index (a
   splice breaks both directions, a pick attack mostly only the forward one); require the residual jump to be
   a single-sample step, not the onset of sustained higher residual energy; adaptive local scale (MAD over
   +-256 frames) instead of per-4096-block. Keep the runtime for a 10-min take under 60 s.
3. Report in `docs/helpers/GLITCH_TUNE_RESULT_2026-10-17.md`: method, numbers (false events per take, detection
   rate per kind, runtime), pytest output.

Run: `.venv/Scripts/python -m pytest tools/test_ua_capture_glitch.py tests/test_usb_audio_pattern.py -q`.
Edit only tools/ua_capture.py, tools/test_ua_capture_glitch.py and your result file. Follow
docs/helpers/SAVE_PROTOCOL.md (commit only those files, never git add -A, never push; retry if .git/index.lock
is held). Never record audio, never touch the pedal, MIDI/audio devices, updater .exe files or tools/*flash*;
ua_capture.py only with --wav.
