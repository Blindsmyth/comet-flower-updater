# Brief: second independent review of the USB audio candidate (2026-10-15)

Output: `docs/helpers/REVIEW2_USB_AUDIO_CANDIDATE.md`. Follow
`docs/helpers/SAVE_PROTOCOL.md` (create the report first, commit only that file
after each finding, never push, token economy).

**DO_NOT_FLASH.** No pedal, no updater, no `.exe`. Do not edit any file under
review. Correctness only.

## Context

- Design: `docs/USB_AUDIO_SILENCE_CANDIDATE_2026-10-15.md`.
- First review and Claude's response: `docs/helpers/REVIEW_USB_AUDIO_CANDIDATE.md`.
  It found the STRING bug; the fix is commit `9ac88a4`.
- Stock disassembly: `build/fw/map/main.dis`. Candidate: rebuild with
  `.venv/Scripts/python.exe tools/make_usb_audio_fw.py`, then read
  `build/usb_audio/usb_audio.dis`.
- Tests: `.venv/Scripts/python.exe -m pytest tests tools/test_usb_audio_proto.py -q`
  (206 must pass).

## Scope (focus on code changed or not deeply checked by review 1)

1. **Descriptor veneer delegation** (`firmware/usb_audio_proto/usb_audio_hooks.asm`).
   For A4 ∉ {1, 2} it must tail-branch to stock `c0160ec0` with every argument
   register (A4, B4, A6, B6, ...), B3 and SP exactly as received. Check every
   path, the delay slots, and that nothing is written before the branch. For
   A4 ∈ {1, 2}, check the return value matches what each of the 7 callers reads.
   Compare against the stock test at `c0160ee2..ee6`.
2. **`ua_map_thunk`** (`firmware/usb_audio/ua_thunks.asm`). Entry state at the
   overwritten gate `c015c674`, the return to `c015c768`, the claim that it
   clobbers only A0/A4/A5/B3, and slot 0/1/2 mapping (slot 0 → stock IF0, IF1,
   EP3, EP 0x84; slot 1 → IF2; slot 2 → IF3). Is `c015c66c` really single-caller?
3. **IF3 SETUP callback** (`usb_audio.c` / `ua_glue.c`). Only SET_INTERFACE
   (bRequest 11) handled. Check the SETUP packet field offsets it reads, the
   alt-setting it stores, what happens on every other request (must be stock
   behaviour or STALL, never a hang), and the `c015af48` ACK argument (A4=128)
   copied from the MIDI callback: trace the MIDI callback in stock and say
   whether the convention fits IF3.
4. Anything else you find that is a real bug. Do not report style.

## Report format

One section per scope item. Each finding: verdict (BUG / RISK / OK), evidence
(addresses plus a ≤10-line disassembly excerpt), confidence
(confirmed / likely / guess). Put a 3-line headline at the top. Write every
predicate truth table out explicitly (`[B0]` executes when B0 != 0).
