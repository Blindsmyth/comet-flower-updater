# USB audio real-audio tap candidate (2026-10-15, OFFLINE, DO_NOT_FLASH)

ROADMAP C3, recon/21 S1. It layers on the silence candidate
([USB_AUDIO_SILENCE_CANDIDATE_2026-10-15.md](USB_AUDIO_SILENCE_CANDIDATE_2026-10-15.md))
and streams the pedal's final stereo output to the host instead of zeros.

Build: `.venv/Scripts/python.exe tools/make_usb_audio_fw.py --tap` →
`build/usb_audio_tap/DO_NOT_FLASH_usb_audio_tap.bin`. Without `--tap`, the
silence image is byte-identical to before (SHA-256 `bfee93d1…b9bd`).
Source: `firmware/usb_audio_proto/usb_audio_tap.c`, which includes `usb_audio.c` unchanged.

## Patches (16 words; the silence list with the SOF target changed, plus 5)

| Site | Stock | New |
|---|---|---|
| `c016f770/774` MVK/MVKH | `0x11818e80` | `usb_audio_sof_tick_tap` (replaces `usb_audio_sof_tick`) |
| `11818c88..c94` | four zero words: dead padding. The epilogue `BNOP B3,0` at `11818c7a` has taken its branch by `11818c84 NOP 4`, and nothing references them. | `MVK/MVKH B31 = ua_tx_pack_tap; B B31; NOP 5`. This is the stock 1181→c0 veneer shape (`11818ea0`). |
| `11818c64` CALLP `11818aa0` (TX pack) | p = 0, 32-bit | CALLP `11818c88` (bits kept). A CALLP cannot reach `c01a8000` (±4 MB), hence the veneer. |

`ua_tx_pack_tap` (verified in `build/usb_audio_tap/usb_audio.dis`) branches to the
stock pack with B3 at its own continuation, then tail-calls
`usb_audio_tap_block(0x11f038b0, 0x11f038f0)` with B3 restored. The audio Swi
keeps nothing in scratch registers across `11818c64` (`11818c68..c70` are bare
CALLPs), so an EABI callee is safe there.

## Samples

The tap does not read the DMA half. It recomputes each word from the pack's
planar inputs with the pack's own math, `SSHL(SMPY32(x, 0x4534fd79), 2)`
(`11818b00..b18`). Word 0 is `11f038b0` (left) and word 1 is `11f038f0` (right), as
`STNDW A5:A4` stores A4 first. Re-reading PaRAM1 SRC after the pack could pick
the wrong half when the Swi ends near its deadline; this cannot. The words are
full-scale int32 (`11818428` scales by 2^31), so the 16-bit sample is the high
half, truncated. The compiler inlines and software-pipelines the conversion
(SPLOOPD). `ring_wr` is stored after SPKERNEL, so an SOF interrupt during the
loop never sees unpublished frames.

## Ring and clock policy

- 256 frames (1 KB, 5.8 ms), one u32 per frame (L low, R high). The Swi is the only
  writer of `ring_wr` and the Hwi the only writer of `ring_rd`. The Hwi preempts the
  Swi, never the reverse.
- The codec runs at 44.1 kHz from the 19.2 MHz MCLK PLL (recon/16). The host SOF is a
  separate clock. EP1 is asynchronous IN (`0x05`), so the packet size sets the rate:
  45 frames when the fill is above 80, else 44. That covers 44.0–45.0 kHz,
  −0.2 % / +2 % around nominal, far beyond crystal drift.
- Priming: the Hwi sends the silence pattern until 128 frames exist, then starts
  from the newest 128 frames. That adds about 1.8–2.9 ms of latency.
- Underrun: pad with zeros, count, re-prime. Overrun: drop the whole 16-frame block, count.
- While the stream is off, every SOF discards the ring (`rd = wr`), so a restart
  never replays old audio. The Swi stores nothing while the stream is off.
- Hwi cost: at most 45 ring reads + 45 FIFO writes, the same FIFO count as silence.

## Tests (`tests/test_usb_audio_tap.py`, 17)

The host harness (`host_harness_tap.c`) logs every FIFO write. The tests cover:
conversion vs a Python model of the stock math (2000 random values plus edge
values); L/R order; priming; underrun; overrun; restart discard; and 10 s
simulations at the real block/SOF rates at 0, −1000 and +10000 ppm. Each
simulation checks that the received stream is an exact contiguous slice of the
produced stream, with no underruns or overruns. The image tests cover: the patch
set; the bits kept at `11818c64`; the veneer's shape and target; the SOF target;
and that the padding is dead.

## Open, for the pedal run (after B1 and the silence enumeration test)

1. The sample level: whether the high half of the DAC word is the right scale.
   Record a known tone and compare with the analog output.
2. Underrun/overrun counters and `packets45` over a long run. Expect `packets45`
   ≈ 10 % of packets at nominal; the exact ratio measures the clock offset.
3. S8: the tap's cycle cost in the audio Swi (16 frames, pipelined; expected
   below 100 cycles) and the Hwi cost with a full five-slot patch.
4. Not covered by host tests: a real Hwi preempting the Swi inside the loop.
   This relies on the SPLOOP interrupt drain and on the publish order checked above.
