# Brief (Antigravity / Gemini): a strict UAC1 configuration-descriptor validator

Follow `docs/helpers/SAVE_PROTOCOL.md` for your report, and commit your own files only.
- Deliverables (the ONLY files you may create or edit):
  - `tools/uac1_validate.py`: a validator library and CLI.
  - `tests/test_uac1_validate.py`: unittest tests.
  - `docs/helpers/GEMINI_UAC1_REPORT.md`: your report. Commit it after each step.
- Scratch folder: `build/gemini_uac1/`. Offline only. Never touch devices, MIDI ports
  or any .exe, and never push. Do not edit `firmware/`, other `tools/` files or other tests.

## Goal
The pedal will present a combined USB-MIDI + USB-Audio-Class-1 (UAC1) configuration.
Its bytes come from `firmware/usb_audio_proto/usb_audio.c` (`usb_audio_copy_descriptors`)
and can be obtained offline through the host harness in
`tools/test_usb_audio_proto.py` (`build_host_library()`, then call
`usb_audio_copy_descriptors(buf, 0xffff, len)`; read that test for the ctypes
setup). We cannot test it on a host computer now, so we want a validator
that catches anything that would make Windows `usbaudio.sys`, macOS or Linux
`snd-usb-audio` reject or mis-bind it.

## Required checks (each a named check id; return a list of (id, message) violations)
Base them on USB 2.0 ch. 9, USB Audio 1.0 (audio10.pdf) and USB MIDI 1.0 (midi10.pdf).
Cite the spec section in a comment for each check.
1. **Framing.** Every descriptor's bLength matches its type's required size. The walk ends
   exactly at wTotalLength, and wTotalLength equals the real byte count.
2. **Configuration.** bNumInterfaces equals the number of distinct bInterfaceNumber values,
   and the interface numbers are 0..n-1 with no gaps. bMaxPower and bmAttributes bit 7
   are set.
3. **Interfaces.** Alternate settings for one interface are contiguous and start at 0.
   bNumEndpoints matches the endpoint descriptors that follow each interface descriptor.
4. **Audio Control.** Each AC interface (class 1, subclass 1) has exactly one CS
   HEADER. Its wTotalLength equals the sum of the CS AC descriptors that follow it,
   and its baInterfaceNr list names interfaces that exist and are
   AudioStreaming (subclass 2) or MIDIStreaming (subclass 3). An interface listed by
   two AC headers is an error.
5. **Terminals.** Terminal IDs are unique within an AC interface, and every
   bSourceID/bAssocTerminal refers to an existing ID (0 = none). An Output
   Terminal of type USB streaming (0x0101) must be linked by an AS
   interface's bTerminalLink.
6. **AudioStreaming.** Alt 0 has zero endpoints. An alt with an endpoint has CS AS_GENERAL
   (with bTerminalLink pointing at a USB-streaming terminal) and a FORMAT_TYPE_I
   descriptor: bNrChannels, bSubframeSize, bBitResolution, tSamFreq.
   wMaxPacketSize >= ceil(maxrate/1000) * channels * subframe, with full-speed
   bInterval == 1. The ISO endpoint descriptor is 9 bytes (audio-class form,
   with bRefresh/bSynchAddress), and a CS_ENDPOINT (0x25) EP_GENERAL follows it.
   The endpoint direction matches the terminal (an IN endpoint feeds the host's input).
7. **MIDIStreaming.** The MS HEADER wTotalLength matches. Jack IDs are unique, and each
   CS MS endpoint's baAssocJackID refers to existing embedded jacks.
8. **Endpoint addresses.** No endpoint address appears twice across different
   interfaces, except in alternates of the same interface.
9. **Full-speed bandwidth.** The ISO wMaxPacketSize is <= 1023, and the sum of the
   periodic endpoints fits a full-speed frame.

## Tests (`tests/test_uac1_validate.py`)
- The prototype's real bytes (through the harness; use `skipUnless` when no host
  compiler is available) validate with **zero** violations. If they do not, do
  NOT change `usb_audio.c`. Report each violation in your report with the
  spec citation; Claude decides the fix.
- One mutation test per check id: copy good bytes, break exactly one thing,
  and assert that check id fires and no unrelated id does.
- A known-good reference: build by hand in the test a minimal valid UAC1
  stereo 16-bit 44.1 kHz IN-only configuration (Linux `f_uac1`-style), and
  assert that it validates clean.

Every finding in your report needs the evidence (byte offset, field, value, spec
section). Do not claim host OS behaviour you cannot cite. Run
`.venv/Scripts/python.exe -m pytest tests/test_uac1_validate.py -q` before you finish,
and put the output in your report.
