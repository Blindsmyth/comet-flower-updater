# Gemini UAC1 Descriptor Validator Report

Offline validation report for combined USB-MIDI + USB-Audio-Class-1 (UAC1) configuration descriptors.

## 1. Goal and Specification References
- USB 2.0 Specification, Chapter 9 (Universal Serial Bus Specification Revision 2.0, April 27, 2000)
- USB Audio 1.0 Specification (Universal Serial Bus Device Class Definition for Audio Devices, Release 1.0, March 18, 1998)
- USB Audio Formats 1.0 (Universal Serial Bus Device Class Definition for Audio Data Formats, Release 1.0, March 18, 1998)
- USB MIDI 1.0 Specification (Universal Serial Bus Device Class Definition for MIDI Devices, Release 1.0, Nov 1, 1999)

## 2. Validator Architecture (`tools/uac1_validate.py`)
Implementation plan for the 9 required check rules.

### Check 1: Framing (`framing`)
- USB 2.0 §9.6.3 Table 9-10; USB Audio 1.0 §4.3.1.
- `bLength` matches type requirement.
- Descriptor walk ends exactly at `wTotalLength`, and `wTotalLength` equals byte count.

### Check 2: Configuration (`configuration`)
- USB 2.0 §9.6.3 Table 9-10.
- `bNumInterfaces` equals distinct `bInterfaceNumber` count.
- Interface numbers are `0..n-1` without gaps.
- `bmAttributes` bit 7 is set (reserved bit, must be 1 for USB 1.1/2.0 legacy compliance).
- `bMaxPower` > 0.

### Check 3: Interfaces (`interfaces`)
- USB 2.0 §9.6.5 Table 9-12.
- Alternate settings per interface are contiguous starting at 0.
- `bNumEndpoints` matches actual endpoint descriptors following each interface.

### Check 4: Audio Control (`audio_control`)
- USB Audio 1.0 §4.3.2 Table 4-2; USB Audio 1.0 §3.2.
- Exactly one CS HEADER per AC interface (class 1, subclass 1).
- Header `wTotalLength` matches sum of CS AC descriptors following it.
- `baInterfaceNr` references valid interfaces that are AudioStreaming (subclass 2) or MIDIStreaming (subclass 3).
- No interface is claimed by more than one AC header.

### Check 5: Terminals (`terminals`)
- USB Audio 1.0 §4.3.2.1 Table 4-3, §4.3.2.2 Table 4-4.
- Unique terminal IDs per AC interface.
- `bSourceID` and `bAssocTerminal` references exist (0 = none).
- USB streaming Output Terminal (0x0101) must be linked by an AS interface `bTerminalLink`.

### Check 6: AudioStreaming (`audio_streaming`)
- USB Audio 1.0 §4.5.1, §4.5.2, §4.6.1.1; USB Audio Formats 1.0 §2.2.
- Alt 0 has zero endpoints.
- Streaming alt has CS AS_GENERAL (`bTerminalLink` pointing to USB streaming terminal).
- FORMAT_TYPE_I descriptor: `bNrChannels`, `bSubframeSize`, `bBitResolution`, `tSamFreq`.
- `wMaxPacketSize` >= `ceil(maxrate/1000) * channels * subframe`, with full-speed `bInterval == 1`.
- Standard audio isochronous endpoint descriptor is 9 bytes (`bRefresh`, `bSynchAddress`).
- Class-specific isochronous audio data endpoint descriptor (0x25, EP_GENERAL) follows it.
- Endpoint direction matches terminal direction.

### Check 7: MIDIStreaming (`midi_streaming`)
- USB MIDI 1.0 §6.1.2.1 Table 6-2, §6.1.2.2 Table 6-3, §6.2.2 Table 6-8.
- MS HEADER `wTotalLength` matches following CS MS descriptors.
- Unique Jack IDs within MS interface.
- CS MS endpoint `baAssocJackID` references existing embedded jacks.

### Check 8: Endpoint Addresses (`endpoint_addresses`)
- USB 2.0 §9.6.6.
- Endpoint addresses (address + direction) are unique across distinct interfaces, only permitted to repeat across alternate settings of the same interface.

### Check 9: Full-Speed Bandwidth (`bandwidth`)
- USB 2.0 §5.6.3, §9.6.6 Table 9-13.
- Full-speed ISO endpoint `wMaxPacketSize` <= 1023.
- Periodic endpoint bandwidth sum fits full-speed frame budget.

## 3. Prototype Verification Findings (`firmware/usb_audio_proto/usb_audio.c`)
(To be evaluated against the prototype descriptor bytes).

## 4. Test Suite Execution (`tests/test_uac1_validate.py`)
(To be updated upon test execution).
