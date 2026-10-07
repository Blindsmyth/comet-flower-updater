# Brief for Codex: finish firmware map parts 3 and 4

Follow `docs/helpers/SAVE_PROTOCOL.md` exactly (commit your report file after
every finding; only that file). Scratch: `build/codex6/`.

## A. Finish `recon/15_controls_midi.md` (your own report)
1. Section 4 "Start-up" is empty: find where start-up decides between normal
   run and update mode (both footswitches held at power-on), and a hook
   point for a "button held at power-up" controller-mode test.
2. Section 6 "Plan": complete the minimal patch plan for the MIDI controller
   mode: hook points for switch events and the calibrated 7-bit analog
   change, the call to the existing CC send path, and how to stop normal
   patch/effect actions in that mode. Evidence vs guess for each.

## B. Continue `recon/16_audio_hw.md` (started by another helper; append below
its findings, keep its text)
3. Audio path: McASP0/1 + EDMA channels, PaRAM sets, buffer addresses and
   sizes, ping-pong scheme, how g_Swi_AudioProcess is triggered; confirm
   16-sample blocks at 44.1 kHz from the counts.
4. CPU clock from the PLLC0 setup (0x01C11000..): DSP and EMIF/SDRAM clocks.
5. Cache patch study: our effects lose 19-25% to cache refill between blocks
   (recon/14 top boxes). Concrete patch designs (addresses, values) to keep
   active effects' hot code/data on chip: e.g. L1PCFG 16K cache + 16K RAM
   with each slot's .text copied there; slot regions moved into L2 RAM (map
   what else uses L2 RAM first); line locking. Risks and a safe test plan
   (installers run from update mode; Zoom's updater restores the firmware).

## Rules
Static analysis only. **Never touch the pedal**: no MIDI ports; do not run
`tools/pedal_g1.py`, `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
`make_g1_image.py`, `make_fs_restore_updater.py`, or any `.exe` other than
dis6x. Edit (and commit) only the two report files; scratch in `build/codex6/`.
