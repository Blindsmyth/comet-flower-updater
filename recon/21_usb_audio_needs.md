# USB audio: what we know and what is still needed (2026-10-09)

Goal: add a USB Audio Class 1 stereo IN stream (pedal -> computer, 44.1 kHz,
16-bit first) next to the stock USB MIDI interface. The design is in
recon/17 B5 (descriptor bytes, patch sequence) and recon/20 (silence-stream
prototype compiled for c01a8000). This file lists every piece of firmware
knowledge that design depends on, where it stands, and who closes it.

Static analysis only. Nothing here has run on the pedal. The controller-mode
test comes first (recon/04), and no USB audio image will be built before it
passes.

## 1. Known (confirmed in the code)

| piece | where | source |
|---|---|---|
| USB0 controller is on the DSP (MUSB, base 0x01e00000), ISO-capable | MMIO | recon/15, 17 |
| Full-speed configuration descriptor, 2 interfaces (AC 0 + MIDIStreaming 1), MIDI OUT3/IN4 | templates; builder c0160ec0 | recon/17 B1 |
| Descriptor pointer store c00643c0, response buffer c0119fb0 | c0160ec0 | recon/18 3.1, recon/20 1.1, 2.1 |
| Standard request table: GET/SET_INTERFACE at c0180238/c018023c, response sender c015af48 | | recon/20 1.2; chunk_14 |
| Endpoint FIFO allocator, 320 B used, 3776 B free; TXCSR written indexed (c0121444) and direct EP1 TXCSR 0x01e00512 (c0122000) | c012146e..14c6 | recon/17 B2, recon/20 review |
| SOF top half in CPU INT7 / event 19 (callback c011fc8c) -> CALLP c016f770 -> **11818e80, an empty `BNOP B3`** | | recon/18 3.4, recon/20 2.4; now decoded (below) |
| Final stereo output store `11818b18 STNDW A5:A4,*A8++[1]` | audio Swi, L2 | recon/17 B3; now decoded |
| Interface registration chain: c01521a8 (action slot 0) -> c015afa0 `usb_request_handler_register` -> c0138a6c -> c015c6b4 `usb_ifmap_reconfigure` -> c015c66c `usb_ifmap_register_one` (tables c011aa18..c011aac0) | | **new 2026-10-09**, closes recon/20 2.2 "c015c66c callers not located" |
| USB MIDI driver API = action table c018447c (slots 0..5). `usbmidi_open` c0152410 stores a callback at 0xc011ac80, then installs the MIDI interface record c018137c | chunk_12 | **new 2026-10-09** |
| MIDI interface request handler c0151ed0: class requests STALL; SET_INTERFACE gets a zero-length ACK; CLEAR_FEATURE(HALT) on EP3/EP0x84 calls the driver callback (7/8) | chunk_12 | **new 2026-10-09**, read in full |
| USB string descriptor table (5 slots, 168 B stride) at 0xc0119bb0, built by c0154ec0/c0154f94, entry swap c015514c | chunk_13 | new 2026-10-09 |
| Code placement for patch code in free SDRAM c01a0000 (no L2, no veneers) | | recon/17 end, recon/18 |

## 2. Fixed today in the map tools

The disassembly the map was built from (`build/fw/map/main.dis`) marked only
two of the image's code sections as code. The three on-chip L2 code sections
`0x118164c0..0x11818ee0`, `0x11819820..0x11819d0c` and
`0x11819d20..0x1181a1a0` came out as `.word` data. That is the audio Swi path,
the output store, the knob decoder and the SOF hook, so the map had no rows
for them. It is now rebuilt with all five code sections (recon/10 command
updated). Only those 3299 lines changed. They are chunk 19 (22 functions)
plus c014f594 (chunk 20), mapped by a helper now.

## 3. Still needed before an image can be built (static)

| # | question | why USB audio needs it | where to look | state |
|---|---|---|---|---|
| S1 | Audio Swi order and the output block: buffer address, format (STNDW = two 32-bit words per frame?), 16 frames, which slot runs last | the producer side of the ring (recon/17 B5 step 4) | chunk 19 (11818b20.., 11818aa0) | helper running |
| S2 | How the SOF top half reaches 11818e80, and what may run there (registers saved, nesting with USB Swi prio 13 / audio Swi prio 15) | the SOF handler sends one ISO packet per 1 ms frame | chunk 19 + c011fc8c (chunk 02) | helper running |
| S3 | Alternate-setting state machine: GET/SET_INTERFACE handlers behind c0180238/c018023c, and how SET_INTERFACE alt 1/0 should start or stop streaming | streaming only on alt 1, clean stop on alt 0 | chunk_14 rows near c015af48; table c0180238 | open |
| S4 | When usbmidi_open runs (c0145124 is its only caller, and that task-entry name looks wrong) and whether the bus is quiet then | safe point to register IF2/IF3 and set up EP1 | chunk_09 c0145124, caller c0159758 | open |
| S5 | `usb_interface_activate_core` c014a58c: only about 90 of its 349 instructions read; a DINT section touches c01819bc/c0181ae4/c0181ae8/c0181f74 | probably the configure/attach path that our new interfaces pass through | chunk_11 | open |
| S6 | Stock TXCSR value 0x3440: bits 6/10/12/13 | the highest-risk ISO setting (recon/20 4.2) | c0121432..c0121444 plus the SPRUFM9 bit table | open (datasheet read) |
| S7 | Descriptor capacity for 192 B, the pointer array at c00643c0 and response buffer c0119fb0 | the new configuration descriptor is 192 B (stock 101 B) | recon/20 2.1 has the plan; re-check against the new disassembly | mostly done |
| S8 | Free cycles in the audio Swi with 5 slots loaded | the ring copy costs 128+128 B per block | measured budget 96-102k cycles (recon/04); tap cost small | measure on the pedal |

## 4. Hardware-only (owner tests, after controller mode passes)

From recon/20 section 4: EP1 FIFO address 0x01e00424, TXPKTRDY/ISO bit
semantics, worst-case SOF Hwi timing, host enumeration (Windows/macOS UAC1
binding), FIFO reconfiguration while MIDI is live, long-run clock drift,
alt-setting transitions, MIDI coexistence.

## 5. Order of work

1. Chunk 19 (S1, S2): helper running.
2. S3 and S4: short targeted reads (a helper, or Claude).
3. S5: read c014a58c in full.
4. S6: read the TXCSR bit table in SPRUFM9 and compare with 0x3440.
5. Update recon/20's patch list with the results, then build a
   **silence-stream** test image (recon/20). It waits until the
   controller-mode test passes on the pedal.
