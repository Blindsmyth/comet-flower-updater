# Brief 5, 2026-10-22: CF Probe link groundwork (jobs F8, F9, Gemini 3.8 Flash)

Goal: a TEST-only firmware feature that answers host requests over USB MIDI
SysEx (`peek` RAM ranges, set a `watch` list streamed on USB audio, LCD
screenshot), so firmware questions are answered by reading the pedal instead
of probe effects and photos. Hard rules as `docs/helpers/FW_RND_BRIEF_2026-10-22.md`
(static only, no pedal, SAVE_PROTOCOL: report first, commit THAT FILE ONLY after
every finding, never push, scratch build/fw_rnd/<job>/, confidence words with
disassembly excerpts, recompute derived addresses, "not found" is fine).

## F8 - Incoming SysEx path and a free command
Report `docs/helpers/FW_RND_F8_SYSEX_RX_FLASH_2026-10-22.md`.
Known: recon/15_controls_midi.md lines 70-100 (MIDI worker c01489a0 state table
c0181138 is the TX side packetizer; reply builder c0127500 copies `f0 52 00 00 00
00 f7` from c0181880; c01274cc sends raw bytes), FIRMWARE_MAP.md "Zoom SysEx
replies and MIDI c0128134..c0128dd4", MIDI task c0129118, recon/19_midi_tx.md,
docs/helpers (grep -il sysex). Steps:
1. Find where bytes the HOST sends (USB MIDI OUT endpoint -> pedal) are
   received and assembled into a SysEx message: the USB endpoint read / ring,
   the parser that collects F0..F7, the buffer address and its maximum length.
2. Find the dispatcher that handles a complete Zoom SysEx `F0 52 00 <model>
   <cmd> ... F7`: the compare/jump on the command byte, the list of command
   values handled (table or compare chain), and what happens for an unknown
   command (ignored? error reply?). Model byte for G1X Four (recon/15/19).
3. Propose the hook: one CALLP (or table entry) we can redirect so OUR handler
   sees every complete SysEx first and returns "not mine" for stock ones; give
   the instruction address, its current word, the calling convention (which
   registers hold buffer pointer and length), and the task/context it runs in
   (MIDI task? MainApp?).
4. The reply path: confirm c01274cc(buf, len) signature and limits (max bytes per
   call, blocking?), and which task may call it.

## F9 - Looper and drum machine: what is already known
Report `docs/helpers/FW_RND_F9_LOOPER_DRUMS_FLASH_2026-10-22.md`. Citation
index only (like job F1), no new disassembly conclusions. Sources:
`docs/helpers/*DRUM*`, `*LOOP*`, recon/map chunk rows for c013abc0..c013b690
(looper, LooperUI task c013b38c) and c0153f00..c0156660 (rhythm, RhythmService
c016aac0), recon/16, recon/21, docs/CF_USB_MODE_2026-10-16.md (looper/drum taps
11818e60, 11817640, gains 11f03d1c), tools/ua_channels*.json. For looper and
drums separately list: state variables (address, meaning, confidence, source
file:line), buffers (address, size, format), the audio-path hooks, the UI/task
entry points, the pattern/tempo tables. End with a "watch list v1": up to 32
addresses worth streaming live, with the expected value range of each.
