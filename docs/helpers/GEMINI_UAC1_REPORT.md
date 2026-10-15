# Gemini UAC1 Descriptor Validator Report

Offline validation report for combined USB-MIDI + USB-Audio-Class-1 (UAC1) configuration descriptors.

## 1. Goal and Specification References
The Zoom G1X Four prototype firmware presents a combined USB-MIDI + USB-Audio-Class-1 (UAC1) configuration.
This suite validates the descriptor byte stream offline against all normative requirements that would cause host audio drivers (Windows `usbaudio.sys`, macOS CoreAudio, and Linux ALSA `snd-usb-audio`) to reject or mis-bind the device.

### Governing Specifications
1. **USB 2.0**: Universal Serial Bus Specification Revision 2.0 (April 27, 2000), Chapter 9 ("USB Device Framework") & Chapter 5 ("USB Data Flow Model").
2. **USB Audio 1.0**: Universal Serial Bus Device Class Definition for Audio Devices, Release 1.0 (March 18, 1998) (`audio10.pdf`).
3. **USB Audio Formats 1.0**: Universal Serial Bus Device Class Definition for Audio Data Formats, Release 1.0 (March 18, 1998).
4. **USB MIDI 1.0**: Universal Serial Bus Device Class Definition for MIDI Devices, Release 1.0 (November 1, 1999) (`midi10.pdf`).

---

## 2. Validator Architecture (`tools/uac1_validate.py`)
The validator implements the 9 distinct check rules required by the brief, each associated with a unique check ID string:

### Check 1: Framing (`framing`)
- **Spec**: USB 2.0 §9.6.3 Table 9-10; USB Audio 1.0 §4.3.1, §4.3.2 Table 4-2, §4.3.2.1 Table 4-3, §4.3.2.2 Table 4-4, §4.5.2 Table 4-19, §4.6.1.1 Table 4-17, §4.6.1.2 Table 4-18; USB Audio Formats 1.0 §2.2 Table 2-1; USB MIDI 1.0 §6.1.2.1 Table 6-2, §6.1.2.2 Table 6-3/6-4/6-5, §6.2.1 Table 6-6, §6.2.2 Table 6-8.
- **Rule**: Every descriptor record starts with `bLength` (≥ 2) and `bDescriptorType`. Each standard and class-specific descriptor's `bLength` must match its type's specification requirement:
  - Configuration (0x02): 9 bytes.
  - Interface (0x04): 9 bytes.
  - Endpoint (0x05): 7 or 9 bytes (9 bytes for audio-class endpoints with `bRefresh`/`bSynchAddress`).
  - AC Header (0x24, 0x01): `8 + bInCollection` bytes.
  - Input Terminal (0x24, 0x02): 12 bytes.
  - Output Terminal (0x24, 0x03): 9 bytes.
  - AS Header (0x24, 0x01): 7 bytes.
  - Format Type I (0x24, 0x02, 0x01): `8 + 3 * bSamFreqType` (or 14 bytes for continuous).
  - AS Isochronous Endpoint (0x25, 0x01): 7 bytes.
  - MS Header (0x24, 0x01): 7 bytes.
  - MIDI IN Jack (0x24, 0x02): 6 bytes.
  - MIDI OUT Jack (0x24, 0x03): `6 + 2 * bNrInputPins + 1` bytes.
  - MS Bulk Endpoint (0x25, 0x01): `4 + bNumEmbMIDIJack` bytes.
- The descriptor walk must end exactly at `wTotalLength`, and `wTotalLength` must equal the total byte count.

### Check 2: Configuration (`configuration`)
- **Spec**: USB 2.0 §9.6.3 Table 9-10.
- **Rule**: `bNumInterfaces` must equal the number of distinct `bInterfaceNumber` values found in interface descriptors. Interface numbers must span `0..n-1` contiguously with no gaps. Configuration `bmAttributes` bit 7 must be set (reserved bit required to be 1 for USB 1.1/2.0 historical compatibility). `bMaxPower` must be non-zero (> 0).

### Check 3: Interfaces (`interfaces`)
- **Spec**: USB 2.0 §9.6.5 Table 9-12.
- **Rule**: Alternate settings for each interface must start at 0 and be contiguous (`0..m-1`). For each interface/alt setting, `bNumEndpoints` must match the exact number of standard endpoint descriptors (`bDescriptorType == 0x05`) following that interface descriptor.

### Check 4: Audio Control (`audio_control`)
- **Spec**: USB Audio 1.0 §3.2, §4.3.2 Table 4-2.
- **Rule**: Each AudioControl (AC) interface (class 1, subclass 1) must have exactly one CS HEADER descriptor. The header's `wTotalLength` must equal the sum of lengths of all CS AC descriptors that follow it (including the header itself and any units/terminals). The header's `baInterfaceNr` array must reference interfaces that exist in the configuration and are AudioStreaming (subclass 2) or MIDIStreaming (subclass 3). An interface cannot be claimed by more than one AC header.

### Check 5: Terminals (`terminals`)
- **Spec**: USB Audio 1.0 §4.3.2.1 Table 4-3, §4.3.2.2 Table 4-4.
- **Rule**: Terminal and unit IDs (`bTerminalID` / `bUnitID`) must be unique within an AC interface. Every source ID (`bSourceID`) and associated terminal ID (`bAssocTerminal`) must reference an existing terminal or unit ID within the AC interface (0 indicates no connection/association). Every Output Terminal of type USB Streaming (`wTerminalType == 0x0101`) must be linked by an AudioStreaming interface's `bTerminalLink`.

### Check 6: AudioStreaming (`audio_streaming`)
- **Spec**: USB Audio 1.0 §2.3.2.1, §2.4.2.1, §4.5.1, §4.5.2 Table 4-19, §4.6.1.1 Table 4-17, §4.6.1.2 Table 4-18; USB Audio Formats 1.0 §2.2 Table 2-1.
- **Rule**:
  - Alternate setting 0 is the zero-bandwidth idle setting and must have zero endpoints (`bNumEndpoints == 0`).
  - Alternate settings with endpoints must contain:
    - CS AS_GENERAL with `bTerminalLink` referencing an existing USB Streaming terminal (`0x0101`).
    - FORMAT_TYPE_I descriptor specifying `bNrChannels`, `bSubframeSize`, `bBitResolution`, and sample rate(s) `tSamFreq`.
    - Standard Audio Isochronous Endpoint descriptor of 9 bytes (containing `bRefresh` and `bSynchAddress`), with full-speed `bInterval == 1`.
    - `wMaxPacketSize` must be ≥ `ceil(maxrate / 1000) * bNrChannels * bSubframeSize`.
    - Endpoint direction must match terminal flow (an IN endpoint feeds a USB Streaming Output Terminal).
    - Class-specific isochronous audio data endpoint descriptor (`0x25, 0x01` EP_GENERAL) must follow the standard endpoint.

### Check 7: MIDIStreaming (`midi_streaming`)
- **Spec**: USB MIDI 1.0 §6.1.2.1 Table 6-2, §6.1.2.2 Table 6-3, Table 6-4, Table 6-5, §6.2.2 Table 6-8.
- **Rule**: The MS HEADER descriptor's `wTotalLength` must match the sum of lengths of all CS MS descriptors for the interface. MIDI Jack IDs (`bJackID`) must be unique within the interface. Each CS MS endpoint's `baAssocJackID` array must reference existing embedded jacks (`bJackType == 0x01`).

### Check 8: Endpoint Addresses (`endpoint_addresses`)
- **Spec**: USB 2.0 §9.6.6 Table 9-13.
- **Rule**: Endpoint addresses (`bEndpointAddress`, encoding endpoint number and direction) must be unique across different interfaces. Reusing an endpoint address is only permitted across alternate settings of the same interface.

### Check 9: Full-Speed Bandwidth (`bandwidth`)
- **Spec**: USB 2.0 §5.6.3, §5.6.4, §5.7.4, §9.6.6 Table 9-13.
- **Rule**: Full-speed isochronous `wMaxPacketSize` cannot exceed 1023 bytes. The total periodic bandwidth (sum of periodic endpoint packet sizes across concurrently active interfaces) must fit within the full-speed 1 ms frame periodic limit (≤ 1023 bytes).

---

## 3. Prototype Verification Findings (`firmware/usb_audio_proto/usb_audio.c`)
- **Confidence**: confirmed
- **Scan methodology**: Descriptors extracted directly from the compiled host harness via `usb_audio_copy_descriptors(storage, 65535, 512)` after `host_reset()`.
- **Total length**: 192 bytes (`0x00c0`).
- **Validation outcome**: **Zero violations** across all 9 check rules.

### Detailed Breakdown of Prototype Bytes (192 Bytes, 23 Descriptors):

| Index | Offset (hex) | Type (hex) | Sub (hex) | Length | Raw Hex Excerpt | Description & Spec Evidence |
|---|---|---|---|---|---|---|
| 0 | 0x00 | 0x02 | - | 9 | `0902c00004010080fa` | **Configuration Descriptor**: `wTotalLength`=192 (`0x00c0`), `bNumInterfaces`=4, `bmAttributes`=0x80 (bit 7 set), `bMaxPower`=250 (500 mA). USB 2.0 §9.6.3 Table 9-10. |
| 1 | 0x09 | 0x04 | - | 9 | `090400000001010000` | **Interface 0 Alt 0**: Class 0x01 (Audio), Subclass 0x01 (AudioControl), `bNumEndpoints`=0. USB 2.0 §9.6.5. |
| 2 | 0x12 | 0x24 | 0x01 | 9 | `092401000109000101` | **Stock AC Header**: `bcdADC`=0x0100, `wTotalLength`=9 (matches 9 B sum of CS AC descriptors), `baInterfaceNr`=[1]. USB Audio 1.0 §4.3.2 Table 4-2. |
| 3 | 0x1b | 0x04 | - | 9 | `090401000201030000` | **Interface 1 Alt 0**: Class 0x01, Subclass 0x03 (MIDIStreaming), `bNumEndpoints`=2. USB 2.0 §9.6.5. |
| 4 | 0x24 | 0x24 | 0x01 | 7 | `07240100012500` | **Stock MS Header**: `bcdMSC`=0x0100, `wTotalLength`=37 (`0x0025`, matches 7+6+6+9+9 = 37 B CS MS descriptors). USB MIDI 1.0 §6.1.2.1 Table 6-2. |
| 5 | 0x2b | 0x24 | 0x02 | 6 | `062402010a00` | **MIDI IN Jack (Embedded)**: ID 0x0a (10). USB MIDI 1.0 §6.1.2.2 Table 6-3. |
| 6 | 0x31 | 0x24 | 0x02 | 6 | `062402021e00` | **MIDI IN Jack (External)**: ID 0x1e (30). USB MIDI 1.0 §6.1.2.2 Table 6-3. |
| 7 | 0x37 | 0x24 | 0x03 | 9 | `0924030114011e0100` | **MIDI OUT Jack (Embedded)**: ID 0x14 (20), 1 input pin connected to Jack 0x1e pin 1. USB MIDI 1.0 §6.1.2.2 Table 6-4. |
| 8 | 0x40 | 0x24 | 0x03 | 9 | `0924030228010a0100` | **MIDI OUT Jack (External)**: ID 0x28 (40), 1 input pin connected to Jack 0x0a pin 1. USB MIDI 1.0 §6.1.2.2 Table 6-5. |
| 9 | 0x49 | 0x05 | - | 9 | `090503024000000000` | **Bulk OUT Endpoint**: Address 0x03, bulk transfer (0x02), `wMaxPacketSize`=64. USB MIDI 1.0 §6.2.1 Table 6-6. |
| 10 | 0x52 | 0x25 | 0x01 | 5 | `052501010a` | **CS MS Bulk Endpoint**: Associated with Embedded Jack ID 0x0a. USB MIDI 1.0 §6.2.2 Table 6-8. |
| 11 | 0x57 | 0x05 | - | 9 | `090584024000000000` | **Bulk IN Endpoint**: Address 0x84, bulk transfer (0x02), `wMaxPacketSize`=64. USB MIDI 1.0 §6.2.1 Table 6-6. |
| 12 | 0x60 | 0x25 | 0x01 | 5 | `0525010114` | **CS MS Bulk Endpoint**: Associated with Embedded Jack ID 0x14. USB MIDI 1.0 §6.2.2 Table 6-8. |
| 13 | 0x65 | 0x04 | - | 9 | `090402000001010000` | **Interface 2 Alt 0**: Class 0x01, Subclass 0x01 (AudioControl for UAC1 audio), `bNumEndpoints`=0. USB 2.0 §9.6.5. |
| 14 | 0x6e | 0x24 | 0x01 | 9 | `09240100011e000103` | **UAC AC Header**: `bcdADC`=0x0100, `wTotalLength`=30 (`0x001e`, matches 9+12+9 = 30 B CS AC descriptors), `baInterfaceNr`=[3]. USB Audio 1.0 §4.3.2 Table 4-2. |
| 15 | 0x77 | 0x24 | 0x02 | 12 | `0c2402010106000203000000` | **Input Terminal 1**: ID 0x01, Line Connector (`0x0601`), 2 ch stereo (`0x0003`). USB Audio 1.0 §4.3.2.1 Table 4-3. |
| 16 | 0x83 | 0x24 | 0x03 | 9 | `092403020101000100` | **Output Terminal 2**: ID 0x02, USB Streaming (`0x0101`), source ID 0x01. USB Audio 1.0 §4.3.2.2 Table 4-4. |
| 17 | 0x8c | 0x04 | - | 9 | `090403000001020000` | **Interface 3 Alt 0**: AudioStreaming idle setting, `bNumEndpoints`=0. USB Audio 1.0 §2.4.2.1 / §4.5. |
| 18 | 0x95 | 0x04 | - | 9 | `090403010101020000` | **Interface 3 Alt 1**: AudioStreaming active streaming setting, `bNumEndpoints`=1. USB 2.0 §9.6.5. |
| 19 | 0x9e | 0x24 | 0x01 | 7 | `07240102010100` | **CS AS_GENERAL**: `bTerminalLink`=0x02 (links to Output Terminal 2 USB Streaming). USB Audio 1.0 §4.5.2 Table 4-19. |
| 20 | 0xa5 | 0x24 | 0x02 | 11 | `0b2402010202100144ac00` | **FORMAT_TYPE_I**: 2 channels, 2 B subframe, 16 bits resolution, 1 discrete rate = 44,100 Hz (`0x00ac44`). USB Audio Formats 1.0 §2.2 Table 2-1. |
| 21 | 0xb0 | 0x05 | - | 9 | `09058105b400010000` | **Standard Audio Isochronous IN Endpoint**: Address 0x81 (IN), `bmAttributes`=0x05 (isochronous asynchronous), `wMaxPacketSize`=180 (`0x00b4`), `bInterval`=1 (1 ms full-speed). 180 ≥ ceil(44100/1000) * 2 * 2 = 180. USB Audio 1.0 §4.6.1.1 Table 4-17. |
| 22 | 0xb9 | 0x25 | 0x01 | 7 | `07250100000000` | **CS AS Isochronous Data Endpoint (EP_GENERAL)**: `bLockDelayUnits`=0, `wLockDelay`=0. USB Audio 1.0 §4.6.1.2 Table 4-18. |

---

## 4. Test Suite Execution (`tests/test_uac1_validate.py`)
Execution of `.venv/Scripts/python.exe -m pytest tests/test_uac1_validate.py -q`:

```
...........                                                              [100%]
11 passed in 0.36s
```

All 11 tests passed cleanly:
1. `test_prototype_real_bytes_validate_with_zero_violations`: verified prototype's live bytes produced from `host_harness.c` offline compile.
2. `test_known_good_reference_validates_cleanly`: verified hand-crafted minimal UAC1 configuration (100 bytes, stereo 16-bit 44.1 kHz IN-only, Linux `f_uac1` style).
3. `test_mutation_check1_framing`: verified that corrupting `wTotalLength` triggers check ID `framing` only.
4. `test_mutation_check2_configuration`: verified that clearing `bmAttributes` bit 7 triggers check ID `configuration` only.
5. `test_mutation_check3_interfaces`: verified that altering `bNumEndpoints` triggers check ID `interfaces` only.
6. `test_mutation_check4_audio_control`: verified that corrupting AC header `wTotalLength` triggers check ID `audio_control` only.
7. `test_mutation_check5_terminals`: verified that setting `bSourceID` to a nonexistent terminal ID triggers check ID `terminals` only.
8. `test_mutation_check6_audio_streaming`: verified that lowering `wMaxPacketSize` below required bandwidth triggers check ID `audio_streaming` only.
9. `test_mutation_check7_midi_streaming`: verified that altering MS header `wTotalLength` triggers check ID `midi_streaming` only.
10. `test_mutation_check8_endpoint_addresses`: verified that duplicating an endpoint address across interfaces triggers check ID `endpoint_addresses` only.
11. `test_mutation_check9_bandwidth`: verified that setting ISO `wMaxPacketSize` > 1023 triggers check ID `bandwidth` only.
