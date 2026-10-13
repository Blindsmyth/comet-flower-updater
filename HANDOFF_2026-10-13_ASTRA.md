# Handoff for Astra — 2026-10-13

## Owner's priority

The defining goal is **processed pedal audio sent to a computer over USB while USB MIDI controller messages also work**. Treat this combined feature as the priority ahead of adding more effects or rewriting the whole firmware. Here, "USB audio out" means pedal-to-host audio (an isochronous IN endpoint). If the owner means host-to-pedal playback as well, clarify that separately; it is not the current prototype.

The broader goal is a Comet Flower G1X Four with five accurate effect slots, USB MIDI control, USB audio, and a patch tool that modifies each owner's own Zoom v2.00 updater. Prefer focused, evidenced changes to the stock firmware. Preserve the stock res5 boot/update path.

## Current evidence, not just plans

- Main firmware: TI `dis6x` listing and a map naming 2,790/2,790 *extracted* starts (1,415 confirmed, 1,340 likely, 35 guess). This is not a recovered C codebase or a complete semantic/indirect-call audit. The 802 res5 boot rows are uncertain candidates. See `docs/FIRMWARE_MAP.md`, `docs/helpers/CODEX_REVIEW.md` and `docs/FEATURE_PREFLIGHT_AUDIT_2026-10-11.md`.
- Effects: CF 808, RAT and Muff have on-pedal sound observations. A memory probe confirmed the predicted slot layout. The 40 KiB per-slot limit is checked. The real five-slot CPU budget is unresolved: TSCL between-call timing conflicts with the old Probe Load formula, which has been withdrawn. DR103 ran too slowly; a later build also exceeded slot memory. See `docs/DSP_RULES.md` and `ROADMAP.md`.
- USB MIDI: `firmware/controller/controller.c` and `tools/make_controller_fw.py` build an **offline worker-transport candidate**. Its updater is explicitly `DO_NOT_FLASH`; no host or pedal test has been performed. The model tests do not validate the compiled worker. See `docs/CONTROLLER_WORKER_CANDIDATE_2026-10-12.md` for exact hashes and remaining ABI, locking, reconnect/reset and timing gates.
- USB audio: stock USB and audio paths have instruction-level traces, and a compiled silence-stream prototype exists in `firmware/usb_audio_proto/`. It is **not wired into a firmware image**. `recon/20_usb_audio_proto.md` section 2.6 has the patch list; `recon/21_usb_audio_needs.md` covers S1–S8. S8 spare-cycle measurement requires the pedal. The prototype targets USB Audio Class 1 audio from pedal to host on EP1 while retaining MIDI. Enumeration, streaming and coexistence have not been tested.
- Update-mode file-system recovery worked once on the pedal. That result applies to the exact tested image, not every future updater. The loader has offline tests but not full display or real packaging validation. See `docs/RECOVERY_G1.md` and `docs/helpers/LOADER_GUI_REVIEW.md`.

## Recommended sequence

1. Close the controller worker's documented offline gates. In particular prove the patched call ABI, all relevant USB port/ring writers and lock users, the event timeout unit, and behavior across ring-full, disconnect/reset/reconnect and missed wakes. Rebuild and verify an exact new hash before proposing a pedal test.
2. Test the approved MIDI candidate on the pedal one input at a time and observe messages at the host. Confirm physical control labels. Do not treat the GUI simulation or Python transport model as a host test.
3. Integrate a **silence-only** USB audio image using the `recon/20` v2 patch list (P1–P3, P5, P6, P10), with exact byte/resource/stage checks. First owner test: host enumeration as audio plus MIDI, then sustained silence without disrupting MIDI.
4. Only after that, tap the processed audio at `11818c64` as described in `recon/20` and `recon/21`; measure real streaming, drift, interrupt cost, alt-setting transitions, resets and MIDI coexistence.
5. Independently calibrate DSP timing with TSCL and a running hardware timer over the same audio callbacks, then stress a populated five-slot patch. Do not restore the withdrawn Probe Load CPU formula.

These are milestones, not claims that the hardware test is already authorized or that the candidate is safe to flash. The owner runs installers and pedal tests.

## Review findings and working tree

At handoff, `master` is at `9b054ed`. Four **pre-existing uncommitted edits** must be preserved: `docs/helpers/MIDI_MONITOR_RESULT.md`, `tests/test_midi_monitor.py`, `tools/cf_midi_mapping.py`, `tools/cf_midi_monitor.py`. They repair direct GUI launch, persistence/export of learned CC bindings, and unverified left/right footswitch labels. They were not committed by this handoff.

The MIDI monitor still has two review issues: quick reconnect can revive an old listener because `stop_listening` is cleared without joining the previous thread (`tools/cf_midi_monitor.py` around lines 196–246), and CC mapping ignores MIDI channel (`tools/cf_midi_mapping.py` around lines 166–171). The requested fake-port GUI test is absent. The controller firmware has a separate unresolved risk: an entire disconnect/reconnect between worker checks may not be observed; the USB lifecycle proof remains open.

The full offline Python suite passed **86 tests** on 2026-10-12. Rerun after changes; tests are not proof of USB host behavior. No files or devices were modified during the review that produced these findings.

## Useful entry points

- `ROADMAP.md` — project order and desired features.
- `docs/FEATURE_PREFLIGHT_AUDIT_2026-10-11.md` — evidence for each feature and exact-image rule.
- `docs/CONTROLLER_WORKER_CANDIDATE_2026-10-12.md` — controller candidate identity and gates.
- `recon/20_usb_audio_proto.md` section 2.6 and `recon/21_usb_audio_needs.md` — USB audio design and remaining measurements.
- `firmware/usb_audio_proto/README.md` — compiled-only prototype status.
- `docs/DSP_RULES.md` — memory, installation and CPU measurement constraints.

Recheck repository status and current documents when work resumes; this handoff records the state observed on 2026-10-13.
