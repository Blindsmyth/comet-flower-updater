# CF rig and multichannel USB: design (2026-10-17)

Owner decisions, 2026-10-17:
- The USB layer must never compromise the pedal's input or output audio.
- Keep stereo. USB grows into a multichannel interface (owner's idea: drums and looper as their own channels).
- The rig comes in two steps: (1) a 5-slot CF patch with Zoom's native per-slot on/off and one page per
  effect; (2) a **CF W/D/W mixer** in the last slot that produces the **stereo output**: dry in the centre,
  wet returns left/right, Bob Bradshaw style. Stereo out is the normal case.

## 1. Rules for every USB tap (non-negotiable)
1. Read-only: copy from a buffer after the stock code has finished writing it for this block; never write an
   audio buffer, never change what the codec plays.
2. Bounded: fixed copy work per block and per SOF; no waits, no allocation, no stock queue posts from the
   Swi/Hwi (recon/17 B4).
3. Off unless chosen: with USB mode off every hook runs the stock code (as today).
4. Measured: the total tap cost is measured with CF ClkT next to a full 5-slot patch before release (today's
   2-channel tap: ~0.4 % static estimate, unmeasured).
5. Every new tap point gets a host test (harness) and a hardware check that the channel is what we think it is.

## 2. USB channel map (target)
| Ch | Signal | Source | Status |
|---|---|---|---|
| 1-2 | pedal output, stereo (= the W/D/W mixer's output once it exists) | TX planar 11f038b0 / 11f038f0, stock pack math | working (tap3) |
| 3 | guitar DI | RX unpack, left ADC 11f03730 (negated full-scale int32, high half) | built in tap4, unflashed |
| 4 | right ADC | 11f03770 (wiring of MIC3R unknown) | to measure |
| 5-6 | drum machine | pending RE (docs/helpers/RHYTHM_LOOPER_TAP_2026-10-17.md) | open |
| 7-8 | looper playback | pending RE (likely buffer c04abff0, 0x2b1100 B) | open |
| later | per-slot taps (e.g. dry post-amp for W/D/W stems) | after slot N in the slot-call sequence | open |

Limits: full speed, 45 frames/ms worst case: 16-bit x 8 ch = 720 B/packet (<= 1023), EP1 FIFO 2 x 1024 B
(fits: stock uses 320 B of 4 KB, docs/helpers/USB_OPT_A3_SONNET_2026-10-16.md). Descriptor: keep
wTotalLength % 64 != 0 (port-13 lesson). Every descriptor change gets a Windows enumeration test on the hub
AND a root port.

## 3. Rig step 1: the 5-slot CF patch
comp -> drive (Muff) -> amp (CF Watt) -> modulation (Mistress / CE-2) -> delay. Native Zoom per-slot on/off and
pages. Open: CF Muff costs ~50.6k cycles alone; the patch budget must be measured (CF ClkT) and Muff optimised
(cheapest version that sounds the same) before all five fit.

## 4. Rig step 2: CF W/D/W mixer (last slot, stereo out)
- Dry: an earlier CF slot (normally the amp) publishes its output block to a small shared buffer in the free
  SDRAM gap (c0187024..c01f4000, ~435 KiB unused, recon/17; must be confirmed untouched at run time).
- Wet: the time/modulation effects run 100 % wet (no dry in their own mix); their stereo output arrives at the
  mixer's input as the chain signal.
- Mixer: L = g_dry * dry + g_wet * (wetL * width terms), R = g_dry * dry + g_wet * (wetR ...); knobs dry level,
  wet level, width; output is the patch's stereo out. Block-aligned, read-only on the shared buffer.
- Open: the shared-buffer contract between slots (block sequencing: the publisher runs earlier in the same Swi
  pass; what happens when the publisher slot is off or holds a stock effect: mixer falls back to dry = 0 and
  passes the chain through).

## 5. Order of work
1. RE: drum / looper tap points (running).
2. Multichannel USB build (1-4 first: wet stereo, DI, right ADC), then 5-8 when the RE confirms the buffers.
3. CF effects: Dyna Comp, Mistress, CE-2 (round 2 running), Delay kit, wrappers, cycle measurements.
4. W/D/W mixer + shared-buffer publisher.
