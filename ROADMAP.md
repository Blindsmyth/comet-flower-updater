# Roadmap — Comet Flower ZG1X4 (written 2026-10-10)

End goal (owner, 2026-10-06): a Comet Flower firmware for the Zoom G1X Four:
5 slots of accurate effects, USB audio and MIDI control, installable by other
owners as a patch tool that converts their own downloaded Zoom v2.00 updater
(no Zoom binaries are redistributed).

## Where we are
- Firmware map: 2768 of 2790 functions named; every hidden start has a row.
  577 rows were still `guess` (chunk_01 and chunk_16 were done today).
- USB audio: static analysis finished (recon/21 S1..S7). Prototype exists
  (`firmware/usb_audio_proto/`). Nothing is built for the pedal.
- Effects on file: CF 808 (808X, circuit-exact), CF RAT, CF Muff, DR103
  (Hiwatt), TS Drive, probes. Several are installed; cost tests are pending.
- Safe-install tooling and debrick path are proven (docs/RECOVERY_G1.md).

## Phase A — finish the map (no pedal; helpers)
| # | task | work | check |
|---|---|---|---|
| A1 | `tools/fwmap/check_rows.py`: machine check of every row (addresses exist, quoted instructions match main.dis, row address is a function start) | Gemini | Codex |
| A2 | Guess pass on the remaining files (order in docs/helpers/GEMINI_NEXT.md) | Gemini | A1 script + Codex |
| A3 | Cross-chunk fixes flagged by the chunk_16 helper (chunk_15 `c0162460` name, `c01604a0` caller) | Gemini | Codex |
| A4 | Per-function survey of the boot/update program (res5; recon/25 has only the boot decision) | Gemini (survey only) | Codex |
| A5 | Merge duplicates, stable subsystem prefixes, final `docs/FIRMWARE_MAP.md` | Claude, when quota returns | — |

## Phase B — pedal tests (owner; needs the owner at the pedal)
Order matters: B1 gates all USB audio work.
1. **B1 USB MIDI controller mode** test updater (`build/fw/Comet Flower ZG1X4
   Controller TEST Updater.exe`, steps in recon/04). Must pass first.
2. B2 CF 808X and CF RAT cost tests (Probe 10 first, tone must distort).
3. B3 CF MEMPRB recording (confirms recon/14 memory split).
4. B4 Slot 0 L2 residency patch (needs a heavy test effect).
5. B5 DR103 writetest / install / play / cost.

Rules: autosave OFF, never save experimental effects, install only through
update-mode images (docs/DSP_RULES.md, docs/RECOVERY_G1.md).

## Phase C — USB audio (after B1 passes)
1. Apply patch list v2 (recon/20 §2.6): 192-byte descriptor, relocate the
   pointer array c00643c0, register IF2/IF3 after `usbmidi_open` (recon/24),
   patch c015c66c for the 3-slot registry.
2. Silence-stream test image; owner checks enumeration (Windows/macOS UAC1)
   and MIDI coexistence.
3. Producer tap at `11818c64` (recon/21 S1): copy the finished 128-byte TX
   half into a ring; the SOF Hwi sends one packet per ms using the direct EP1
   registers (no INDEX writes). PIO, not CPPI (recon/23).
4. Measure S8 (spare cycles in the audio Swi); long-run drift; alt-setting
   transitions.

## Phase D — effects
- Rule: accuracy first, then the cheapest version that sounds the same.
  Real cost must stay at or below ~80k cycles/block for a full patch
  (UI freezes at ~96-102k). A full 5-slot patch must fit.
- Next effects come from the owner's JUCE pedalboard. Needs an owner pick;
  the amp (Tweed 5E3) is undecided.
- Work pattern that works for Gemini: a test-gated kit (header contract,
  reference bench, PASS/FAIL scorer, edit whitelist), as in
  `docs/helpers/AGY_RAT.md`; Claude or Codex reviews.

## Phase E — distribution
- Patch tool (owner supplies their v2.00 updater), CF branding, installer
  presets, res5 left untouched unless proven safe (recon/25).
- Public docs: FORMAT.md, FIRMWARE_MAP.md, DSP_RULES.md, safety notes.

## Blocked / waiting
- Claude weekly limit hit 2026-10-10: Claude-side work (reviews, A5, USB
  patch code) resumes when it resets.
- Codex capped until 2026-10-13 20:30 local; checks start then.
- Everything in Phase C and D hardware validation waits for the owner.
