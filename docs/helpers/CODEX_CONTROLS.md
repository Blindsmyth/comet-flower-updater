# Brief for Codex: firmware map part 3, controls and MIDI

Follow `docs/helpers/SAVE_PROTOCOL.md` exactly. Your report:
`recon/15_controls_midi.md`; scratch: `build/codex5/`.

## Context (read briefly)
- `recon/10_firmware_capabilities.md`: firmware layout, the USB stack lives
  in the main firmware (descriptors at res1 0x73364, VID 0x1686 PID 0x04A1),
  SPI semaphores, the display map, tools in `tools/fwmap/`.
- `recon/14_effect_memory.md`: style and depth expected (Codex's own work).
- `build/fw/map/main.dis` (full listing of `build/fw/res1_493412.bin`),
  `build/fw/map/refs.txt` (resolved address constants),
  `build/fw/map/strings.txt` (task names: g_Task_SwitchNrmlSpdRead,
  g_Task_AD, g_Task_MIDI, g_Event_MIDIDataReady, g_Task_RepeatEventHandler,
  g_Task_MainApp, g_Semaphore_MIDI, g_Swi_UsbInterrupt, UsbTask ...).

## Why
The owner wants a power-up "MIDI controller mode": footswitches, knobs,
buttons and the expression pedal send MIDI CC to a PC over USB instead of
running effects (recon/10, "MIDI controller"). We need the code to hook.

## Questions, in order
1. **Footswitches and buttons.** The task that reads them
   (g_Task_SwitchNrmlSpdRead?): how switches are read (GPIO registers,
   addresses), the event/message produced per press, and where it is
   dispatched (patch up/down, effect on/off, menu).
2. **Knobs and expression pedal.** g_Task_AD: which ADC (internal? the codec's
   spare channel? an SPI ADC?), the read routine, the value range, and
   where a knob change is delivered to the effect parameter path.
3. **MIDI out.** The routine that sends a MIDI/SysEx message to the PC over
   USB (what the editor replies use): its address, arguments, and the
   USB-MIDI packet format it builds. Is there an existing path that sends
   short messages (program change / CC)?
4. **Start-up.** Where main start-up decides between normal run and the
   update mode check (both footswitches held): a place where a "button held
   at power-up" test for a controller mode could be added.
5. **USB controller.** From the SPI traffic in the USB code: which external
   USB device controller chip it is (register map patterns, e.g. MAX3420E
   has registers like EPIRQ/USBIRQ at known offsets). This decides whether
   USB audio is possible at all.
6. **Plan** (end section): the minimal firmware patch for the controller
   mode, as a list of hook points, with what is evidence and what is guess.

## Rules
- Static analysis only. **Never touch the pedal**: no MIDI ports; do not run
  `tools/pedal_g1.py`, `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  `make_g1_image.py`, `make_fs_restore_updater.py`, or any `.exe` other
  than dis6x.
- Edit only your report (and commit only it) and files in `build/codex5/`.
