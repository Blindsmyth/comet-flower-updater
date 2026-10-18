# Brief for Argon (agy): find the drums and looper signals on their own (2026-10-17)

Goal: two more USB channels carrying **the drum machine alone** and **the looper alone**. Your job is to find,
in the firmware, a buffer (or a point in code) where each signal exists before it is mixed with the guitar,
so the USB tap can copy it. Static analysis only.

## Rules
- Read first: `docs/helpers/SAVE_PROTOCOL.md` (token economy, save after every finding),
  `docs/helpers/FWMAP.md` Pitfalls, `docs/helpers/RHYTHM_LOOPER_TAP_2026-10-17.md` (the previous pass: the
  audio Swi call graph R1, the buses R5, buffer table R4), `recon/16_audio_hw.md`.
- Disassembly: `build/fw/map/main.dis`; tools in `tools/fwmap/` (`refs.py` for MVK/MVKH immediates, `calls.py`).
- Never touch the pedal, USB/MIDI tools, any `.exe`; never push. Edit only your report.
- **First action:** create `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md`, commit it (that file only), and
  append + commit after every finding. If your quota ends mid-job, the report must already say what is done.
- Quote the instruction addresses for every claim. Mark each claim `confirmed` / `likely` / `guess`.
  A wrong `confirmed` is the worst outcome; "not found, here is what I checked" is a good outcome.
- Watch predicated instructions (`[B0]` / `[!B0]`) and loads in branch delay slots.

## New hardware facts (owner listening test, 2026-10-17, 8ch build tapping at TX pack 11818c64)
| USB ch | Buffer read at TX-pack time | Owner hears |
|---|---|---|
| 1-2 | 11f038b0 / 11f038f0 (int32, post master) | full mix: effects + **drums + looper**, loud |
| 3-4 | 11f03730 / 11f03770 (high half) | **the same full mix incl. drums + looper**, quieter |
| 5-6 | 11f03830 / 11f03870 (float bus) | silent (exact zeros) |
| 7-8 | 11f03930 / 11f03970 (float) | **clean guitar DI**, no effects/drums/looper |

Consequences you must use:
1. **11f03730 is overwritten after RX unpack (11818b20)**: at TX time it holds the mix *including* drums and
   looper, before the master level. The previous report assumed it still held the ADC input; it does not.
2. So drums and looper are added **before or into 11f03730**, and not via 11f03830 (silent).
3. 11f03930 carries the dry input, so the R5 "bus" analysis (gain c011acd0) is about the dry path, not
   drums/looper.

## Tasks (in order; save after each)
1. **Every writer of 11f03730 / 11f03770 in one audio block**, in Swi order (R1 call list): direct stores,
   pointer-table entries, and functions that receive it as an argument. Which step turns the input into the
   mix? Give the step address and what it adds (operands, source buffers).
2. **The add of drums and looper.** At that step (or earlier), find the source buffer(s) added in that are not
   the effect chain output (11f037b0/f0) or the dry input. For each candidate: address, format (float/int,
   planar/interleaved, 16 samples?), gain cell, and who fills it (producer) if you can find it.
   Likely shapes: a ring/FIFO read from a different task (rhythm/looper run outside the Swi: look for a
   read index advanced by 16 per block), the looper buffer candidate c04abff0 (0x2b1100 B, ~32 s 16-bit),
   or a sample-playback routine for drum samples.
3. **Separable?** Are drums and looper added as two separate sources, or summed together first? If summed
   first, where is each before the sum?
4. **Tap proposal:** for each signal, the earliest code point where it exists alone and the buffer/pointer to
   copy (and whether it is still intact at 11818c64, or a second hook point is needed).

## Done =
Report with: the 11f03730 writer chain (task 1), candidate buffers with evidence (2), the separability answer
(3), a concrete tap proposal or a clear "not found" with what was checked (4). Final line: `STATUS: done`.
