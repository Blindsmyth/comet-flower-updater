# 10 — What the main firmware could be changed to do

Date: 2026-10-06. Read-only scan of `build/fw/res1_493412.bin` (main
firmware) and `res5_163840.bin` (boot program), after the owner confirmed the
replaced ZOOM logo works (a main-firmware edit, recon/09).

## USB lives in the DSP firmware
- The USB stack is part of the main firmware: `g_Swi_UsbInterrupt`,
  `UsbTask`, `g_Task_MIDI`, `g_Event_MIDIDataReady`, `UsbTestMidi_Task`, the
  strings "ZOOM Corporation" / "ZOOM G Series". The boot program has its own
  copy (update mode).
- Device descriptor at res1 0x73364 (twice):
  `12 01 10 01 00 00 00 40 86 16 a1 04 00 01 01 02 00 01` = USB 1.1 full
  speed, EP0 64 B, VID 0x1686, PID 0x04A1. Config descriptor total 0x65 bytes
  (101 B, the size of a standard USB-MIDI 1.0 config), bus powered, 500 mA.
  Interface/endpoint descriptors are not stored as a plain block (built in
  code or split).
- The TMS320C6745 has no USB controller of its own (the C6747 has one), and
  the firmware has SPI0/SPI1 semaphores (`g_Semaphore_SyncTxSPI0` etc.). So
  the USB device controller is very likely a separate chip on SPI. **Not
  confirmed**: needs a board photo or a trace of the SPI register traffic.

## Consequences
- **MIDI controller:** the USB-MIDI port already exists and the firmware
  already sends MIDI on it. Sending CC/PC from the footswitches and the
  expression pedal is a code patch (hook the switch handler, call the
  existing MIDI send). It needs reverse engineering, but no new USB work.
  A zero-risk first step is a host-side bridge (the editor-mode SysEx the
  pedal sends on changes, mapped to CC on a virtual port).
- **USB audio:** needs new descriptors, isochronous endpoints and an audio
  path from the McASP to the USB chip. If the USB chip is an SPI peripheral
  controller of the MAX3420E kind (control/bulk/interrupt endpoints only, no
  isochronous), class-compliant USB audio is impossible on this hardware.
  Identify the chip before spending any effort.
- **Patch slot count:** the effect header already carries a slot count
  (byte 0x58) and patches already mark the second half of a double-width
  effect (id 0x1), and the declared dspload drives "Process Overflow". A
  solo effect can probably be made with those, without a firmware patch.
  Note that the real CPU limit (~96k cycles/block, recon/06) is the whole
  DSP already: one effect can use all of it even in a 5-slot patch.
