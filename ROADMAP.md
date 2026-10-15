# Roadmap — Comet Flower ZG1X4 (written 2026-10-10)

Latest lead checkpoint: [HANDOFF_2026-10-14_LEAD.md](HANDOFF_2026-10-14_LEAD.md).
The seven-hook lifecycle MIDI candidate passes offline packaging checks;
worker stack and USB lifecycle gates remain open. The prior 1,784-byte stack
ceiling is withdrawn; do not use it to approve a hardware test.

Update 2026-10-11: The main-image extractor now has names for 2790/2790 discovered starts, and `check_rows.py` reports zero mechanical failures. The 802 res5 boot rows remain uncertain candidates. Semantic review of the map is still open; see `docs/helpers/CODEX_REVIEW.md`. The feature-by-feature evidence gate is in `docs/FEATURE_PREFLIGHT_AUDIT_2026-10-11.md`.

End goal (owner, 2026-10-06): a Comet Flower firmware for the Zoom G1X Four:
5 slots of accurate effects, USB audio and MIDI control, installable by other
owners as a patch tool that converts their own downloaded Zoom v2.00 updater
(no Zoom binaries are redistributed).

## Where we are
- Firmware map: all 2790 extracted starts named (1415 confirmed, 1340 likely,
  35 guess); 802 boot rows are uncertain candidate starts. Mechanical checks
  pass; a full semantic and indirect-target audit has not been completed.
- USB audio: static analysis finished (recon/21 S1..S7). An offline silence-stream
  candidate builds (`tools/make_usb_audio_fw.py`,
  docs/USB_AUDIO_SILENCE_CANDIDATE_2026-10-15.md; DO_NOT_FLASH). It layers on stock
  or on the controller candidate. No host or pedal has seen it.
- Effects on file: CF 808 (808X, circuit-exact), CF RAT, CF Muff, DR103
  (Hiwatt), TS Drive, probes. Several are installed; cost tests are pending.
- Update-mode file-system recovery worked once on the pedal; current updater
  stage restrictions and loader tests pass offline (docs/RECOVERY_G1.md).

## Phase A — finish the map (no pedal; helpers)
| # | task | work | check |
|---|---|---|---|
| A1 | `tools/fwmap/check_rows.py`: machine check of every row (addresses exist, quoted instructions match main.dis, row address is a function start) | Gemini | Codex |
| A2 | Guess pass on the remaining files (order in docs/helpers/GEMINI_NEXT.md) | Gemini | A1 script + Codex |
| A3 | Cross-chunk fixes flagged by the chunk_16 helper (chunk_15 `c0162460` name, `c01604a0` caller) | Gemini | Codex |
| A4 | Per-function survey of the boot/update program (res5; recon/25 has only the boot decision) | Gemini (survey only) | Codex |
| A5 | Merge duplicates, stable subsystem prefixes, final `docs/FIRMWARE_MAP.md` | Claude, when quota returns | — |

## Phase B — pedal evidence and next tests (owner; needs the owner at the pedal)
Order matters: B1 gates USB audio image work.
1. **B1 USB MIDI controller mode:** an isolated worker transport updater is
   built and stage-checked offline (`docs/CONTROLLER_WORKER_CANDIDATE_2026-10-12.md`),
   never run on the pedal. Close its USB lifecycle, wait/ABI and timing gates;
   then test the exact approved hash with one physical control at a time.
2. **B2 CF 808/RAT/Muff:** all have sound evidence. RAT/808/Muff kernel TSCL
   measurements exist; the Probe Load cost formula was withdrawn after it
   contradicted MuffT. Resolve block period/clock and test a full patch.
3. **B3 CF MEMPRB:** done; slot-1 memory predictions confirmed on the pedal.
4. **B4 Slot 0 L2 residency:** hash-pinned static patch ready; no pedal test.
   Use a heavy effect and record exact image hash, load and audio behavior.
5. **B5 DR103:** early builds played but overran; later oversized replacement
   contributed to an FS recovery incident. Redesign under both memory and
   measured time limits before another install.

Rules: autosave OFF, never save experimental effects, install only through
update-mode images (docs/DSP_RULES.md, docs/RECOVERY_G1.md).

## Phase C — USB audio (after B1 passes)
1. ~~Apply patch list v2~~ done offline 2026-10-15: the descriptor builder is replaced
   (supersedes the P1-P3 relocation), IF2/IF3 are registered, the c015c66c map is
   rewritten via the c015c674 gate, and the SOF hook is in place. Pending: an
   independent review and a strict UAC1 validator.
2. Silence-stream test image; owner checks enumeration (Windows/macOS UAC1)
   and MIDI coexistence.
3. Producer tap at `11818c64` (recon/21 S1): copy the finished 128-byte TX
   half into a ring; the SOF Hwi sends one packet per ms using the direct EP1
   registers (no INDEX writes). PIO, not CPPI (recon/23).
4. Measure S8 (spare cycles in the audio Swi); long-run drift; alt-setting
   transitions.

## Phase D — effects
- Rule: accuracy first, then the cheapest version that sounds the same.
  The true per-block cycle budget is open: CF MuffT measured ~50.6k TSCL
  cycles per block while Probe Load implied 96-102k. Resolve this before
  assigning a five-slot budget; a full five-slot patch must be measured.
- Next effects come from the owner's JUCE pedalboard. Needs an owner pick;
  the amp (Tweed 5E3) is undecided.
- Work pattern that works for Gemini: a test-gated kit (header contract,
  reference bench, PASS/FAIL scorer, edit whitelist), as in
  `docs/helpers/AGY_RAT.md`; Claude or Codex reviews.

## Phase E — distribution
- Patch tool (owner supplies their v2.00 updater), CF branding, installer
  presets, res5 left untouched unless proven safe (recon/25).
- Public docs: FORMAT.md, FIRMWARE_MAP.md, DSP_RULES.md, safety notes.

## Waiting for measurement
- Controller mode, slot-0 residency, USB audio enumeration/timing and full
  five-slot load require owner-run pedal observations after their offline gates.
