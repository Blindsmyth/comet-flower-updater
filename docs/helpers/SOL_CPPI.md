# Brief (Codex gpt-5.6-sol, medium): can stock CPPI TX send isochronous EP1?

Follow `docs/helpers/SAVE_PROTOCOL.md` (including Token economy) exactly.
- Report: **`recon/23_cppi_iso.md`**. Create it with the headings below,
  commit it, then commit THAT FILE ONLY after every finding.
- Scratch: `build/sol_cppi/`. Static only; never touch the pedal, MIDI/USB
  devices or any .exe; never push.
- Inputs: `build/fw/map/main.dis`, `build/fw/map/refs.txt`, names in
  `recon/map/chunk_*.md` (grep). Background (grep, don't print whole):
  `recon/17_usb_midi_audio.md` (B4: all stock TX goes through CPPI),
  `recon/18_round3.md` 3.3, `recon/21_usb_audio_needs.md` 3.3,
  `recon/22_s5_activate_core.md` finding 14.
- TI SPRUFM9 (USB OTG for OMAP-L137/C674x) documents CPPI 4.1: if you can
  fetch it, use it for descriptor and queue layout; otherwise say so.

## Background
USB audio needs one ISO IN packet (176/180 bytes) per 1 ms frame on EP1.
Stock sends MIDI IN on EP4 through CPPI DMA. c01212e0 sets TXCSR 0x3440 |
ISO (DMAEN|DMAMODE|MODE|CLRDATATOG). Question: reuse that DMA path, or PIO?

## Questions (report sections)
1. **TX submission path.** From the MIDI IN send down to the hardware:
   functions, the CPPI registers / queue manager addresses written
   (0x01e0xxxx), descriptor layout (fields written, sizes), completion
   handling (interrupt, queue pop, buffer recycle).
2. **Channel selection.** How the TX channel/queue is chosen from the
   endpoint number. Is EP1 TX channel 0? Is any channel/queue/descriptor
   pool hard-wired to EP4 only, or sized for one channel?
3. **Coexistence.** Could EP1 TX and EP4 TX be active at once (pool
   sizes, shared state, locks)?
4. **ISO behaviour.** Per-packet length, whether a 0-length or varying
   length (176/180) works, requeue per frame, any dependence on bulk
   semantics (short-packet / ZLP logic, retries).
5. **Verdict for USB audio:** reuse CPPI (what calls, from which context,
   what to add) vs PIO (what the PIO producer must undo). Name the risks.

Every claim: instruction address, short excerpt (≤ 8 lines), confidence
(confirmed / likely / guess). Pitfalls: a CALLP to a c016e0XX epilogue ends
a function; delay-slot instructions run on both paths of a branch; use
refs.txt for MVK/MVKH constants.
