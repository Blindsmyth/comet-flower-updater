# Brief for Argon (agy): map the 5-slot effect loop for per-slot USB taps (2026-10-17)

Goal: a USB channel pair carrying **the sound after a chosen effect slot** (and later a slot's wet-only
part = its output minus its input). Find where each slot's input and output live in one audio block and
propose the cheapest hook. Static analysis only.

## Rules
- Read first: `docs/helpers/SAVE_PROTOCOL.md`, `docs/helpers/FWMAP.md` Pitfalls,
  `docs/helpers/RHYTHM_LOOPER_TAP_2026-10-17.md` (R1 Swi call list, step 11 = the slot loop),
  `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md` (your last report: same style), `recon/16_audio_hw.md`,
  and grep `recon/` for "slot" (recon/B2-B3 describe the loop mechanism).
- Disassembly `build/fw/map/main.dis`; tools in `tools/fwmap/`.
- Never touch the pedal, USB/MIDI tools, any `.exe`; never push. Edit only your report.
- **First action:** create `docs/helpers/SLOT_TAP_ARGON_2026-10-17.md`, commit it (that file only), append +
  commit after every finding. Last line when finished: `STATUS: done`.
- Quote instruction addresses for every claim; mark each `confirmed` / `likely` / `guess`. **Recompute every
  derived address** (base + offsets) and show the arithmetic: last time one derived cell was wrong
  (11f03d08 vs the real 11f03d1c).
- Watch predicated instructions and delay-slot loads.

## Known
The loop is in the audio Swi 11818ba0: 11818bd4..11818c38. Counter at *(B14 + 102*4) (0..4), skip-all branch
at 11818bec (`[B0] BNOP 0x11818c44` with B0 = *(B14+101*4)), per slot: CALLP 0x11818eb0 (a 1181->c0 veneer:
find its c0 target), then `LDW *+B11[B10],B5` with B11 = 0x118133e0 (a function-pointer table indexed by slot)
and an indirect call `BNOP B5` at 11818c16, return 11818c20. After the loop (11818c38..c44) the chain output
is the float bus 11f037b0 (L) / 11f037f0 (R), 16 samples each. The USB tap code lives at c01a8000 and can add
veneers in dead padding (zero words after a BNOP return), as at 11818c88, 11818d4c, 11818e84.

## Tasks (in order; save after each)
1. **Per-slot call contract**: what 11818eb0's target does per slot (argument A4 = slot index?), what the
   table 118133e0 holds (static or rewritten at patch load: find the writers), and what each slot effect
   function reads and writes: does every slot process the bus 11f037b0/f0 in place, or ping-pong between
   buffers? Give the buffer addresses for slot n input and output.
2. **Mono/stereo**: is the bus stereo through all slots, or mono until some slot? (The G1X Four chain is
   mostly mono with stereo effects late; find where R becomes distinct.)
3. **Bypassed / empty slots**: what the table holds for an empty or bypassed slot and whether the bus is then
   untouched.
4. **Tap proposal**: the cheapest way to copy "bus after slot N" each block for a runtime-chosen N (e.g. one
   hook after the indirect call at 11818c16..c20, or wrapping the table entries), and how to get "slot N wet
   only" (after - before). Note any slot that runs outside this loop (e.g. a split chain).

## Done =
Report with the call contract, the buffers per slot, mono/stereo, empty-slot behaviour and a concrete hook
proposal, or "not found, checked X". `STATUS: done`.
