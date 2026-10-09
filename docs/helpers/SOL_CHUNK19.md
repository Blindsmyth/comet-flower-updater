# Brief (Codex gpt-5.6-sol, medium): chunk 19 sections + recon/21 S1/S2

Follow `docs/helpers/FWMAP.md` (inputs, pitfalls, row format) and
`docs/helpers/SAVE_PROTOCOL.md` (including Token economy) exactly.
- Your file: **`recon/map/chunk_19.md`** (it already has 30 rows). Commit
  THAT FILE ONLY after every finding. Scratch: `build/sol_c19/`.
- Static only; never touch the pedal, MIDI/USB devices or any .exe; never push.
- Context: `recon/21_usb_audio_needs.md` sections 1-3 (read with sed windows),
  `recon/16_audio_hw.md` (audio path, EDMA ping-pong) — grep, don't print.

## Tasks
1. **Review 2 claims per row** for the 30 existing rows (address arithmetic,
   branch senses, callers). Fix wrong rows in place; add "(reviewed)" to the
   evidence column of each row you checked.
2. **S1 — audio Swi order and the output block.** From the orchestrator
   11818ba0: the exact call order per block; the output buffer address(es)
   (ping/pong?), sample format (is STNDW two 32-bit words per frame? int or
   float, which bits carry audio), frames per block (16?), which effect slot
   runs last, and where the final output store (11818b18 / 11818aa0) writes.
   Name the best tap point for a USB audio ring copy (after the last slot,
   before the codec output) with its address and what is in registers there.
3. **S2 — SOF path.** How the SOF top half (Hwi, c011fc8c region, chunk_02 —
   `grep -n c011fc8c recon/map/chunk_02.md`) reaches 11818e80; which registers
   it saves; the priorities (USB Swi 13, audio Swi 15 per recon/21) and
   whether 11818e80 runs in Hwi or Swi context; what code may safely run
   there (no INDEX writes, bounded time).
4. Fill **Summary**, **Data** (globals/buffers with roles), **Open
   questions**, and **For USB audio** (answers to S1/S2 with addresses).

Every claim: instruction address, short excerpt (≤ 8 lines), confidence.
Pitfalls from your calibration: a CALLP to a c016e0XX epilogue ends the
function; delay-slot instructions run on both paths of a branch.
