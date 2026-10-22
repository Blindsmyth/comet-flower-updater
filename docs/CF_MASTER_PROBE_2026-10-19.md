# CF Master loader probe (2026-10-19)

Step 3 of the CF Master plan (docs/C6745_DESIGN.md). Before any CF Master DSP: does an effect that claims
several patch slots load, how is it called, how many knobs reach it, and does it get more memory.

## The updater
**Also in updater 22** (`docs/C6745_BENCH_2026-10-19.md`): bench firmware + the C6745 effect rebuilds + these
probes, one flash for both tests. Updater 21 below is the same probes on the 20B firmware.

`GUITAR AUDIO 21 - CF Master probe TEST.exe` (desktop, `build/cfm_probe_2026-10-18/`), sha256 `2507cf43`.
It is updater 20B (`7830391d`, same firmware `d9eb45e2`: 8 ch, looper on 8) plus two effects. Rebuilding with
the 20B image gives 20B byte for byte, so nothing else changes. Image = `fs_cfloads.bin` + `CFM5P.ZD2`
+ `CFM2P.ZD2` (`make_g1_image.py`, 48 files, 21 effects installed).

| Effect | File | Header 0x58 | Knobs |
|---|---|---|---|
| CF M5 | CFM5P.ZD2 | 5 (no stock effect does this) | 12: Mode, Gain, P3..P12 |
| CF M2 | CFM2P.ZD2 | 2 (as the stock 1U amps) | same |

Stock effects have at most 9 knobs (`zd2 audit`: 11 table entries). 12 is the stomphacks maximum.

Kernel: `effects/common/cfm_probe.h`. Mode 0 = guitar x Gain (50 = unity, 100 = 2x). Mode 1 = tone-code
report, two alternating pages, about 8 s each (decoder: `tools/decode_memprobe.py`):
- page 0: calls per block, instance/coef/state addresses, work buffer (which slot's), code address (which
  slot region);
- page 1: which slot work buffers changed or are empty (read-only check of the first 4 KB of each), and the
  12 knob values.

## Safety
- AUTO SAVE **off** before adding either probe. Never save a patch with one in it. If the pedal saved such a
  patch and hangs at boot, recovery is any earlier updater (update mode is entered before patches load).
- Use an empty patch.
- The probes only read memory outside their own state.

## Steps for the owner
1. Flash it as usual: FIRMWARE UPDATE screen first (hold both footswitches while plugging USB), then Execute.
2. Empty patch, AUTO SAVE off. Add **CF M2** in slot 1. Note: does it go in, how is it drawn, which slots
   look taken, can you add effects after it, how many knob pages, can all 12 knobs be turned?
3. Mode 0, play. Gain 50 should sound unchanged, Gain 100 louder by 6 dB. CF Monitor: record ch 3-4
   and ch 7 (DI) at Gain 100. If ch 3 is about +30 dB over the DI instead of +6 dB, the firmware runs the effect
   in every slot it occupies.
4. Mode 1: record ch 3 for at least 20 s with CF Monitor (two pages), then
   `python tools/decode_memprobe.py build/recordings/<file>.wav`. Set the knobs P3..P12 to known values
   first (e.g. 30, 40, ... 120 capped at 100) to check every knob reaches the DSP.
5. Same again with **CF M5** in slot 1. Then, if allowed, CF M5 in slot 3 (does the pedal refuse it,
   wrap, or overflow?).
6. Remove the probes and go back to 20B whenever you want (or keep this one: it is 20B plus two effects).

## What the answers decide
- Loads with 5 slots: CF Master is one 5-slot effect. If only 2 work: CF Master is split differently (e.g. two
  or three multi-slot effects), or the slot count is handled by a firmware patch.
- Calls per block 1 and one instance: one kernel per block, the plan's single schedule.
- Memory: if the work buffers of the occupied slots stay unchanged, CF Master can use them (5 x 0x81330 B of
  SDRAM). Code and const would still be in one 40 KiB region unless page 0 shows otherwise.
- Knobs: how many CF Master controls fit, and on how many pages.

## Results
(pending)


### Owner session 2026-10-20 (Updaters 24 and 25, bench firmware, `tools/ua_capture8.py`, 30 s)

- **CF M2 (2 slots): loads and is listed.** With Mode 1 set the report decodes cleanly (3 frames, identical on both channels, `build/probe_cfm2p_m1b*.wav`). Mode 0 recorded silent on the output the first time.
  - 1.00 calls per block (43,164 calls over 43,164 blocks), a single instance.
  - instance, coef and state in on-chip L1D RAM (`0x11f03ad0`, `0x11f00000`, `0x11f013b0`).
  - work buffer 529,200 B at `0xc0226000`, slot 0 (the full CF Master buffer was granted).
  - code `0xc01f41e0`, slot region 0.
  - knobs 1-12 read back `100 50 3 4 5 6 7 8 9 10 11 12`: all 12 knobs reach the DSP.
  - work buffers 1-4: first 4 KB all zero (empty).
- **CF M5 (5 slots): NOT offered by the pedal.** Absent from the effect list on Updater 24 and 25 (CF M2 and CFM Pre are listed). `CFM5P.ZD2` is in both images.
- **Still open:** code/const heap size for a multi-slot effect, the maximum slot count the pedal lists (3? 4?), and how many slots CF M2 visibly occupies.

**Consequence:** a single 5-slot CF Master cannot be selected as built. Options: the largest accepted slot count (needs 3- and 4-slot probes), split into `cfm_pre` (2 slots) + `cfm_amp` (3 slots), or a firmware patch for the slot count.
