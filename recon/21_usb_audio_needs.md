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
| S3 | Alternate-setting state machine | streaming only on alt 1, clean stop on alt 0 | see 3.1 below | **answered** (routing: record callback first, design (b)) |
| S4 | When the USB interfaces are registered, and whether the bus is quiet then | safe point to register IF2/IF3 and set up EP1 | see 3.2 below | **answered** (confirmed call order) |
| S5 | `usb_interface_activate_core` c014a58c: only about 90 of its 349 instructions read; a DINT section touches c01819bc/c0181ae4/c0181ae8/c0181f74 | probably the configure/attach path that our new interfaces pass through | chunk_11 | **answered** (recon/22): not on the interface path; UAC interfaces need not pass through it |
| S6 | Stock TXCSR value 0x3440: bits 6/10/12/13 | the highest-risk ISO setting (recon/20 4.2) | see 3.3 below | **answered**: SPRUFM9H Table 65 confirms the layout |
| S7 | Descriptor capacity for 192 B, the pointer array at c00643c0 and response buffer c0119fb0 | the new configuration descriptor is 192 B (stock 101 B) | recon/20 2.1 has the plan; re-check against the new disassembly | mostly done |
| S8 | Free cycles in the audio Swi with 5 slots loaded | the ring copy costs 128+128 B per block | measured budget 96-102k cycles (recon/04); tap cost small | measure on the pedal |

### 3.1 S3 findings (Claude, read in full 2026-10-09)

Standard-request table c0180210 (4 bytes per bRequest): slot 10 = c0134e68
GET_INTERFACE, slot 11 = c0135940 SET_INTERFACE, slot 9 = c0135660
SET_CONFIGURATION, slot 12 = c0134e60 SYNCH_FRAME.

`c0135940` SET_INTERFACE:
```text
c0135948 LDW *+B14[11],B0        ; configured flag (byte offset 44); 0 -> error ffff8acc
c013595c LDHU *+A5[2],A4         ; wIndex (setup byte offset 4) = interface
c0135960 LDHU *+A5[1],A0         ; wValue (byte offset 2) = alternate setting
c0135964 MVK 0xffffa1b0 / MVKH 0xc0110000,A5
c013596e STB A0,*A4[A5]          ; alt[interface] = wValue, NO bounds check on wIndex
c0135970 CALLP c01357c8          ; usb_interface_altsetting_configure(cfg, iface, alt)
c0135988 CALLP c015af48          ; zero-length status ACK when it returned 0
```
`c01357c8` (shared with SET_CONFIGURATION) gets the descriptor list from
c0160ec0. It walks it for a type-4 (interface) descriptor with matching
bInterfaceNumber (+2) and bAlternateSetting (+3), then configures that
alternate's endpoints through c01212e0, the FIFO/CSR path that sets the ISO
bit from bmAttributes (recon/18 3.3).
Its only other caller is c01356fa inside SET_CONFIGURATION c0135660, which
loops over the interfaces with alt 0 (found by the gpt-5.6-sol calibration run,
checked by Claude). So after SET_CONFIGURATION, IF3 starts at alt 0 (no
endpoints) through the same path.

What this means:
- **No new alt-setting code is needed for the endpoint side.** Once the
  192-byte descriptor (recon/17 B5) is served, SET_INTERFACE(IF3, alt 1)
  configures EP1 IN as isochronous through the stock path, and alt 0 (no
  endpoints) configures nothing.
- The stream still needs a **start/stop signal**. The MIDI interface's
  handler record (c018137c, callback c0151ed0) receives bRequest 11, so an
  IF3 record registered the same way (c015afa0) should see SET_INTERFACE and can
  switch the SOF producer on (alt 1) or off and flush (alt 0). Still unchecked:
  whether the record callback runs before or after c0135940, and on which
  interface number the dispatcher routes it.
- **Routing order (answered, Claude 2026-10-09): the record callback runs
  first and replaces c0135940.** The common SETUP decoder c01359e4 reads the
  packet (c0122370), splits bmRequestType into recipient (EXTU ..,27,27 at
  c01359f8) and type (AND 0x60 at c0135a06). For recipient 1..3 it looks up a
  record by (recipient, wIndex) through c015c804/c015c788 (c0135a18..a38) and
  calls the record's +12 callback with A4 = type, B4 = &setup
  (c0135a52..a6c). Only when that returns **0xffff8a5b** ("not handled",
  c0135a74..a82), or no record matches, does it fall through to the
  standard table c0180210 (c0135a90..aaa) and so to c0135940. A non-zero
  result then STALLs through c0120ef8(0x80, 1) (c0135ab4..c4).
  The MIDI callback c0151ed0 returns 0xffff8a5b for any non-standard type
  (c0151ed8..e4), but **handles bRequest 11 itself**: it sends the
  zero-length ACK through c015af48(128, 0, 0) and returns 0 (c0151eec..f0,
  c0151f5a..8c). So for the MIDI interface, stock c0135940 and c01357c8 never
  run on SET_INTERFACE; they run only at SET_CONFIGURATION (c01356fa).
- **What this means for IF3.** Two designs:
  (a) IF3 callback returns 0xffff8a5b for bRequest 11: stock c0135940 stores
  the alt and configures EP1 through c01212e0 (CPPI DMA on, 0x7440), then
  ACKs, and **our code gets no call afterwards**. The stream start would
  have to be detected elsewhere (for example by polling the alt array
  c011a1b0[3] from the SOF Hwi).
  (b) **Preferred:** IF3 callback handles bRequest 11 like MIDI does. It
  calls `usb_audio_set_alt(wValue)` (FIFO set-up, DMA bits cleared, producer
  on/off), ACKs through c015af48(128, 0, 0) and returns 0. It must also
  answer GET_INTERFACE (bRequest 10) for IF3, because the stock alt array is
  not updated in this design. Stock still runs c01357c8 for IF3 alt 0 at
  SET_CONFIGURATION, which configures nothing (alt 0 has no endpoints).
  Still to check: that c015c788 keys interface records by bInterfaceNumber
  (likely, from the (recipient, wIndex) arguments), and the record layout
  at c015afa0 for registering IF2/IF3.
- Hardening: c0135940 does not bound-check wIndex against the 0xc011a1b0
  array. The patch should check `wIndex < 4`.
- c01359b8 is a separate leaf function placed right after SET_INTERFACE's
  return (already in the map as `usb_ctrl_helper_small`). It zeroes B14[10],
  B14[11] (configured flag) and the alt array (SPLOOP STB). Its only caller is
  c015e9d0 (1200 B, chunk 15, being mapped). That caller also calls
  usb_endpoint_records_reset c0138660 and usb_ifmap_set_default_ptr c015c804,
  so it is probably the bus-reset/deconfigure event handler. The stream must
  stop there too.

### 3.2 S4 findings (Claude, 2026-10-09)

USB bring-up runs in **task context**, from the SwitchNrmlSpdRead task, not at
boot:
```text
118076c0 task_switch_nrml_spd_read
 -> 1180a7ec switch_repeat_notify
   -> c016ab8c: c016ab90 STW 1,*+B14[24]      ; "USB started" gate (byte offset 96)
                c016ab94 CALLP c015b114 -> c0138a78 usb_endpoint_layer_init
                c016ab98 CALLP c016ab70:
                  c016ab78 CALLP c0159758      ; creates "UsbTestMidi_Task" and calls
                     c0145124 (ctx): clear 40 B at 0xc01152b8, ctx -> word 0,
                     c0145154 MVK 0x4c0c / MVKH 0xc0140000,A4 ; callback = c0144c0c
                     c0145158 CALLP c0152410 usbmidi_open    ; installs MIDI IF record c018137c
                  c016ab80 CALLP c015af18 -> c0138720 usb_worker_start
                     -> c0120dd0: c0120e10 MVK 0x0401 / MVKH 0x1e00000,A4
                                  c0120e1a SET A0,6,6,A0 ; c0120e20 STB A0,*A4
                                  ; POWER.SOFTCONN = 1: the device appears on the bus
```
So every interface is registered **before** the soft-connect. That is the
quiet window: registering the IF2/IF3 records and reserving the EP1 FIFO just
after usbmidi_open, for example by chaining from c0145124's return, happens
before the host can enumerate. That closes recon/20 item 4.5 statically.

Corrections that follow: c0145124 is the USB MIDI device init
(`usbmidi_device_init`), not a switch-speed task entry. The callback it
registers, c0144c0c, is the MIDI TX port-op dispatcher chunk_09 found
embedded in c0144ba0 (table 0xc01843d8, ops 2..8), so the halt-recovery codes
7 and 8 from c0151ed0 land in that table. What makes 1180a7ec take the
c016ab8c branch (first switch scan? USB VBUS?) is not read yet.

### 3.3 S6 findings and prototype fixes (Claude, 2026-10-09)

Stock composes the TX CSR word as `MVK 209` << 6 = **0x3440**, then ORs in ISO
(bit 14) from bmAttributes (c0121432..c0121444, recon/18 3.3). In the standard
MUSB peripheral TXCSR layout (the one SPRUFM9H documents for this USB0 core;
taken from the MUSB register map, **not yet re-read in the TI PDF**):

| bit | name | in 0x3440 | for a PIO ISO IN endpoint |
|---|---|---|---|
| 0 | TXPKTRDY | 0 | set after each packet is loaded |
| 3 | FLUSHFIFO | 0 | once at set-up and on alt 0 |
| 6 | CLRDATATOG | **1** | set once at set-up (harmless for ISO) |
| 10 | DMAMODE | **1** | 0 (PIO) |
| 12 | DMAEN | **1** | 0 (PIO) |
| 13 | MODE (1 = TX) | **1** | **keep 1** |
| 14 | ISO | from bmAttributes | 1 |
| 15 | AUTOSET | 0 | 0 |

**Checked against SPRUFM9H (July 2010) Table 65, PERI_TXCSR (Claude,
2026-10-09):** 15 AUTOSET, 14 ISO, 13 MODE, 12 DMAEN, 11 FRCDATATOG,
10 DMAMODE, 9..7 reserved, 6 CLRDATATOG, 5 SENTSTALL, 4 SENDSTALL,
3 FLUSHFIFO, 2 UNDERRUN, 1 FIFONOTEMPTY, 0 TXPKTRDY. The table above is
right. Notes from the same document that change the producer:
- 2.7.1.4.1: DMA "is not particularly useful with Isochronous endpoints"
  (packets are not max size and TXCSR must be checked after every packet).
  This supports PIO.
- FLUSHFIFO acts only while TXPKTRDY is set; double-buffered FIFOs may need
  two flushes. UNDERRUN (bit 2) is set on an IN with an empty FIFO (a null
  packet is sent); software clears it.
- 2.7.1.4.1.2: start-up of a double-buffered ISO IN pipe can send the first
  packet too early; set POWER.ISOUPDATE (0x01e00401 bit 7). Stock RMWs POWER
  for SOFTCONN (c0120e1a, c011ff4a). The prototype now sets it on alt 1.
- TI suggests loading on SOF (our design) and double buffering (DPB, TXFIFOSZ
  bit 4).

So only bits 10 and 12 are DMA bits. Bit 13 is the endpoint direction and
bit 6 is a one-shot toggle reset. The 0x3440 value is "TX endpoint, CPPI DMA
on, toggle cleared", which matches recon/17 B4's finding that all stock TX goes
through CPPI. The "single highest-risk unknown" in recon/20 4.2 becomes one
specific choice.

Fixes needed in `firmware/usb_audio_proto/usb_audio.c`. **Made 2026-10-09**
(compiles clean with the recon/20 flags; not linked or run). Fix 2 is the new
`usb_audio_set_alt()`: on alt 1 it writes MODE|ISO|DMAMODE (drop DMAEN first,
the MUSB order rule) then 0x6048; on alt 0 it stops the producer and flushes.
Its call point (IF3 record callback, after c0135940) depends on the open S3
routing question:
1. **Keep MODE.** Every 16-bit TXCSR write also rewrites bits 8..15, and
   `TXCSR_ISO | TXCSR_TXPKTRDY` (0x4001) clears MODE. Use **0x6001**
   (MODE | ISO | TXPKTRDY) for each packet, and 0x6048 (MODE | CLRDATATOG |
   FLUSHFIFO) in set-up instead of FLUSHFIFO then 0.
2. **Stock will configure EP1 for DMA first.** Per 3.1, SET_INTERFACE(IF3,
   alt 1) runs c01357c8 -> c01212e0, which writes 0x3440 | ISO = 0x7440
   (DMAEN on) for EP1. A PIO producer must clear DMAEN/DMAMODE after that, or
   the endpoint descriptor must not be routed through c01212e0's CPPI branch.
   Alternative worth checking (S5 reading): submit ISO packets through the
   stock CPPI TX path that MIDI IN4 uses, instead of PIO.
3. **No INDEX in the SOF interrupt.** `usb_audio_sof_tick` sets
   `USB_INDEX = 1` and uses the indexed TXCSR 0x01e00412. The SOF Hwi can
   interrupt the USB Swi between its own INDEX write and access (recon/20
   review). Use the direct block: EP1 TXCSR **0x01e00512** (stock reads and
   clears bit 5 there at c0122000..c0122014), and the FIFO 0x01e00424, which
   is not indexed. The prototype's comment that 0x01e00512 "has zero stock
   cross-reference" is wrong.

## 4. Hardware-only (owner tests, after controller mode passes)

From recon/20 section 4: EP1 FIFO address 0x01e00424, TXPKTRDY/ISO bit
semantics, worst-case SOF Hwi timing, host enumeration (Windows/macOS UAC1
binding), FIFO reconfiguration while MIDI is live, long-run clock drift,
alt-setting transitions, MIDI coexistence.

## 5. Order of work

1. Chunk 19 (S1, S2): helper running.
2. S3 and S4: short targeted reads (a helper, or Claude).
3. S5: read c014a58c in full. **Done (recon/22).**
4. S6: read the TXCSR bit table in SPRUFM9 and compare with 0x3440.
5. Update recon/20's patch list with the results, then build a
   **silence-stream** test image (recon/20). It waits until the
   controller-mode test passes on the pedal.
