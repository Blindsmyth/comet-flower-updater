# Shootout TEST build: CF Dyna / CF Mistrss / CF CE2 + stock counterparts (2026-10-17)

Owner: add the new CF effects to the next build together with their Zoom counterparts, for the USB
stock-vs-CF shootout (Comfortably Numb solo).

| Updater | SHA-256 (start) | Firmware | Effects image |
|---|---|---|---|
| **Audio Bridge FX + shootout** `build/cf_shootout_2026-10-17/` (desktop: `GUITAR AUDIO 11 - Comet Flower Audio Bridge FX + shootout TEST.exe`) | `964933f2` | FX USB `d9eb45e2` (docs/CF_USB_MODE_2026-10-16.md) | `fs_shootout.bin` `abc319eb` |

Image: `make_g1_image.py --clean --keep <stock>... build/fw/res3_3137536.bin` + the five release CF effects
(extracted from the release image; the same command with only those five reproduces the release `fs_cf.bin`
`a0e0f86a` exactly) + the three new ones. 17 installed:

| CF | Stock counterpart |
|---|---|
| CF Dyna (`DYNACX`, 01000f86) | COMP (Comp, 01000010) |
| CF Mistrss (`MISTRX`, 06000f87) | VINFLNGR (VinFLNGR, 06000050) |
| CF CE2 (`CE2X`, 06000f88) | STEREOCH (StereoCho, 06000030) |
| (CF delay: kit not built yet) | ANDLY_3S (AnalogDly, 08000021) |
| CF 808 | TS_DRIVE |
| CF RAT | SQUEAK (recon/11: the Rat) |
| CF Muff | NYC_MUFF |
| CF Watt | HW100_1U + HW4X12 |
| G1 Gain | - |

New wrappers (`effects/{dynacx,mistrx,ce2x}`), the muffx pattern: mono DSP on A to both channels, guard
prologue, knob smoothing, bypass crossfade, output clamp. Knobs: Dyna Sustain / Level (-20..+20 dB);
Mistrss Rate (0.05..10 Hz) / Range / Color (feedback 0..0.95) / Matrix; CE2 Rate / Depth / Mix.
- Mistrss and CE2 keep their DSP state (2.1 / 4.2 KB, above the 392 B slot state) at the start of the slot's
  work buffer `instance[3] -> {base, end, size}` (docs/helpers/DELAY_MEM_SONNET_2026-10-17.md), checked
  (aligned, end - base = size >= state) or the effect outputs silence; zeroed on the first block after each load
  (primed flag in the loader-zeroed slot state), because stock zeroes that buffer only at boot. **First CF use of
  the work buffer on hardware.**
- Build fixes: the zero loop writes through `volatile` (cl6x turned it into a memset call, which the kernel
  check refuses); the CE-2 saturation table moved to a const_blob (`effects/ce2x/blob.bin`, `CE2_SAT_BLOB`) so
  the parameter table stays first in .const. Benches still PASS (Dyna -60.6 dB, Mistress INTERP -64.0, CE-2
  INTERP -57.3 / LOOSE -27.2). Slot memory 7.3 / 8.1 / 10.7 of 40 KB.
- Static per-block estimates (c6x_cycles, per-sample loop x 16): Dyna ~4k, Mistrss ~6k, CE2 ~4.3k. Static
  counts ran several times low for CF Muff (~5k static vs 50.6k measured): **measure on the pedal**. dspload
  placeholders 30 / 40 / 40.

## Pedal test (DSP_RULES section 5, steps 4-5)
AUTO SAVE off. Each new effect alone in an empty patch: audio passes, knobs act, no freeze or glitch; then beside
an amp. Mistrss/CE2: change patches back and forth (re-load must restart clean, no noise burst from old buffer
contents). Do not save patches holding them until they pass. Then the shootout pairs, recorded with the FX USB
template (1-2 mix unclipped, 3-4 guitar FX).
