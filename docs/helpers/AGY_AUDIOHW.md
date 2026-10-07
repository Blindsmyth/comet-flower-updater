# Brief for Antigravity (Claude): firmware map part 4, audio hardware and the cache patch study

Follow `docs/helpers/SAVE_PROTOCOL.md` exactly. Your report:
`recon/16_audio_hw.md`; scratch: `build/agy5/`. Another helper (Codex) is
writing `recon/15_controls_midi.md` at the same time: do not touch it.

## Context (read briefly)
- `recon/07_hardware.md`: confirmed parts: TI TMS320C6745 (likely 375 MHz),
  **TI TLV320AIC3101 codec (I2C control)**, 8 MB SDRAM, 4 MB SPI flash.
- `recon/14_effect_memory.md` (top boxes are measured on the pedal):
  effect code + tables in 40 KiB SDRAM slot regions (cached via MAR192),
  state/knobs/audio in L1D RAM, stack in L2 RAM; cache split L1P 32K cache,
  L1D 16K cache + 16K RAM, L2 128K cache + 128K RAM (set at 0xc016c480 from
  {4,3,3} built at 0xc016d080). Kernel timing: cache refill costs 19-25%.
- `recon/13_effect_loader.md` (Claude's review box: EDMA IS used).
- `build/fw/map/main.dis`, `refs.txt`, `strings.txt` (g_Semaphore_SetI2C0,
  g_Semaphore_SyncI2C0, Hwi_EDMA, g_Swi_EDMA, g_Semaphore_EDMA,
  g_Swi_AudioProcess ...). Tools: `tools/fwmap/`.

## Questions, in order
1. **Codec setup.** Find the I2C writes to the TLV320AIC3101 (7-bit address
   0x18 usually): list every register/value pair the firmware writes and
   decode them with the AIC3101 register map (sample rate / PLL, ADC PGA
   input gain, DAC volume, AGC, the digital effects filters and their
   biquad coefficients, de-emphasis, which ADC channels are used).
   Answer: is the codec's second ADC channel used (for what)? Are its
   built-in DAC biquads in use, and could they be set by a firmware patch?
2. **Audio path.** McASP + EDMA: the EDMA channel(s), PaRAM sets, buffer
   addresses and sizes, ping-pong scheme, how g_Swi_AudioProcess is
   triggered, and the sample format. Does the firmware process 16-sample
   blocks at 44.1 kHz (confirm from the McASP/EDMA counts)?
3. **The cache patch study.** Our effects lose 19-25% to cache refill
   between blocks (recon/14). Design, on paper, a firmware patch that keeps
   the active effects' hot code/data on chip, e.g.: change L1P config to
   16K cache + 16K RAM and copy each slot's .text there; or move the slot
   regions into the 128K L2 RAM (what else uses L2 RAM? map it from the
   linker/heap data); or lock lines. For each option: exact patch points
   (addresses, values), what could break, and how to test it safely with
   the update-mode installer (Zoom's official updater restores firmware).
4. **CPU clock.** From the PLL setup code (PLLC0 registers 0x01C11000..):
   the DSP clock (375 or 456 MHz) and the EMIF/SDRAM clock.

## Rules
- Static analysis only. **Never touch the pedal**: no MIDI ports; do not run
  `tools/pedal_g1.py`, `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  `make_g1_image.py`, `make_fs_restore_updater.py`, or any `.exe` other
  than dis6x.
- Edit only your report (and commit only it) and files in `build/agy5/`.
- Read code in small windows (grep, then read ~100 lines); your context is
  limited.
