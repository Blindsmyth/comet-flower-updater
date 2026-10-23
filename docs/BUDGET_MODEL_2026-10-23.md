# Budget model: effects limited by CPU, not by a slot count (2026-10-23)

Owner, 2026-10-23: "If we can add a 6th slot, what stops us? Budget. So why not move to a budget model.
Cheaper effects means more slots." This note sets out the numbers, the meter that shows the budget on the
pedal (Updater 33), the test that finds the real ceiling, and the route to "more effects than 5".

## The budget
- One audio block = 16 frames = **132,354 CPU cycles** (SYSCLK1 364.8 MHz; docs/CF_BENCH_RESULTS_2026-10-18.md).
- The audio Swi also does fixed work: empty patch = 8.8k Swi busy (CPU 21 % mean, 45-47 % peak, other tasks
  included). Stock 5-slot patch: 66 % mean / 100.9 % peak, audio fine. Owner's CN chain (CFM Pre, CF Delay,
  CF Watt, CF Rotary, CF Delay): 83 % mean / **107 % peak, 0 lost frames**. So the "% of block" figure can pass
  100 % for single blocks without audio loss; the real ceiling is not known yet (test below).
- Zoom's own gate: the declared `dspload` of the 5 slots must sum below 230.0 (c0141ad8). Calibrated scale
  (docs/DSP_RULES.md 4): dspload = 7 + 3 x kcycles, so Zoom budgets about (230 - 35) / 3 = **65k cycles of
  effects** per patch. Our CF effects do not declare their measured cost yet, so the gate does not protect them.

## Measured costs (slot medians, cycles per block)
| Effect | cycles | % block |
|---|---:|---:|
| CFM Pre (Dyna + Muff + Mistress) | 29.2k | 22 |
| CF Watt | 23.4k (39.7k before 2x / caching) | 18 |
| CF WattL (static -18 %; pedal: not measured yet) | ~19k expected | ~14 |
| CF Delay | 5.7k / 7.4k | 4-6 |
| CF Rotary | 5.1k | 4 |
| CF 808 / CF RAT / CF Muff | 16.2k / 16.0k / 14.5k | 11-12 |
| CF Dyna / CF Mistrss / CF CE2 | 7.8k / 6.6k / 4.1k | 3-6 |
| Stock: HW100 21.9k, TS_DRIVE 10.3k, NYC_MUFF 8.8k, COMP 2.3k, VINFLNGR 2.2k, ANDLY_3S 1.9k | | |

## 1. See the budget: the CPU meter (Updater 33)
`make_usb_audio_fw.py --cpu-meter`: the audio code publishes, every block, a record at **0xc01a8020**
(`ua_cpu`: magic "CPUM", seq, busy mean (~64 blocks), busy peak (worst block of the last 2048 blocks,
~0.74 s), mean cost per slot). busy = TX pack - Pre looper, the same figure as the bench's CPU %.
`make_controller_fw.py --cf-header`: the edit page shows the peak as **"NN%"** in the top right corner
(columns 102..127, right of the stock name box), inverted at 95 % and above; it refreshes on UpdateUI's idle
wake-ups (~20 Hz) while its own pixels are still on screen (no screen-id needed). The CFM Pre stage bar
shortens to "PRE>MUFF FUZZ" to make room. Readable over the probe too: `cf_probe.py peek 0xc01a8020 36`.
The record also holds per-slot means: the next screen (a budget page) can show each slot's share.

## 2. Find the real ceiling (next pedal session; no listening needed)
probe10 / probe30 (effects/probe10, probe30) burn a knob-set number of cycles per block. With the meter on
screen and `tools/ua_bench.py run` watching lost frames: stack them on a CN patch and raise Load until frames
are lost or the screen freezes. The meter value just before = the usable ceiling. Then:
- set the warning threshold of the meter to that ceiling minus a margin;
- re-declare every CF effect's `dspload` from its measured cost (`tools/zd2_set_dspload.py`, 7 + 3 x kcycles)
  so Zoom's own PROCESS OVERFLOW gate protects CF patches too; if needed, move the 230.0 constant to match the
  measured ceiling (one constant at c0141ad8..c0141b60).

## 3. More effects than 5: rack slots, not a 6th slot
A real 6th slot (docs/helpers/SLOT5_INVENTORY_SONNET_2026-10-23.md): each stock slot owns a 40 KiB code heap
AND a 0x81330-byte (~517 KiB) work buffer from fixed tables (c01839c0/c01839a8/c01839f0); the SDRAM after
the last buffer (c04abff0) is already in use; the slot callback table 0x118133e0 sits inside a block of other
live pointers; plus 25-30 small `CMPGT 5` edits in patch load, UI, the audio loop and the dspload gate.
**Large, with two unresolved memory conflicts.** The patch format itself is ready (10-slot struct, count at
+900; docs/helpers/CF_STORAGE_SONNET_2026-10-23.md).

The budget model does not need it. **One slot can run several effects in series**, as CFM Pre already does
(Dyna -> Muff -> Mistress in one slot, 29.2k cycles). What limits a slot is CPU (the meter) and its 40 KiB
code + const heap, not a count. So:
- "CF Rack" effects: chains built from the CF kernels (each stage switchable, its own page with the stage
  header), e.g. Comp + Drive + Amp in one slot; 5 slots of racks = 10-15 effects if the budget allows.
- Routing lives inside a rack: a rack gets the stereo bus, so split / parallel / wet-dry-wet mixing
  (dry centre, wet stages left/right) is DSP inside one slot, no firmware routing change.
- Per-rack settings beyond 9 knobs (stage on/off, order, mix) go in the PTCF custom chunk
  (CF_STORAGE Q1/Q5: hook pack c0130e04 + unpack c013150c).
- Cheaper kernels = more stages per rack (CF WattL is the first; next candidates by size: CFM Pre's
  Muff stage, CF 808, CF RAT).

## Next steps
1. Owner: flash Updater 33, check the meter on the edit page (stock and CF effects), then the ceiling test (2).
2. Claude: budget page (per-slot share from the same record) in the CF menu; dspload calibration tool run.
3. Design "CF Rack" (which stages, page layout, routing modes, W/D/W) with the owner.
