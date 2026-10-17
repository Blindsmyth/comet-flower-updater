# USB optimization: Sonnet A3 (2026-10-16)

Task: brief docs/helpers/USB_OPT_BRIEF_2026-10-16.md, item A3 only. Static
analysis only; no pedal/MIDI/audio-device/updater/tools-flash access.
Inputs: build/fw/map/main.dis, build/fw/map/refs.txt, recon/18_round3.md,
recon/20_usb_audio_proto.md, recon/21_usb_audio_needs.md. Scratch:
build/scratch/sonnet_a3/ (unused so far; no script was needed).

## Summary

Work in progress.

## A3. USB0 FIFO RAM map and 24-bit EP1 feasibility

### Finding 1: the generic allocator (c01212e0 / c012146e..c01214c6) is re-confirmed directly, and is the *only* code in the image that ever touches the indexed FIFO registers (confirmed)

Read `c01212e0` through `c01214c6` in `build/fw/map/main.dis` (lines 28617-28832)
directly, independent of the prior recon passes. It matches recon/18 3.3,
recon/20 1.3/1.7 and recon/17 B2 instruction-for-instruction:

```text
c012132c MVK.S2   0x040e,B4
c0121330 MVKH.S2  0x1e00000,B4      ; B4 = A10 = 0x1e0040e  (USB_INDEX)
c0121338 STB.D2T1 A1,*+B7[0]        ; INDEX = endpoint# (low nibble of A1)
...
c0121374 MVK.S2   85,B4   || c0121378 ADD B0,B4,B4 || c0121380 STB A0,*+B4[0]
                                     ; A10+0x55 = 0x1e00463 = RXFIFOSZ
c01213f6 MVK.S2   84,B4   || c0121400 ADD B0,B4,B4 || c0121402 STB A0,*B4[0]
                                     ; A10+0x54 = 0x1e00462 = TXFIFOSZ
c012142e ADD.L2   B0,4,B4 ; c0121444 STH A0,*B4[0]
                                     ; A10+4   = 0x1e00412 = TXCSR (indexed)
```
then, falling straight through (no intervening RTS) into the "repacker":
```text
c012146e MVK.S2   64,B3             ; running byte offset starts at 64
...
c0121480 MVK.S2   86,B4 || c0121484 ADD B5,B4,B4   ; B4 = A10+0x56 = 0x1e00464 = TXFIFOADDR
c012148a ADD.L1X  B4,2,A6                            ; A6 = 0x1e00466 = RXFIFOADDR
...
c01214b4 EXTU.S2  B2,16,19,B0 || c01214b8 EXTU.S1 A0,16,19,A1
c01214c0 STH.D2T2 B0,*B4[0]         ; TXFIFOADDR write (8-byte units, 4-bit field)
c01214c6 STH.D1T1 A1,*A6[0]         ; RXFIFOADDR write
```
All six register offsets the brief names (INDEX 0x40e, TXFIFOSZ 0x462,
TXFIFOADDR 0x464, RXFIFOSZ 0x463, RXFIFOADDR 0x466, plus TXCSR 0x412) are
reproduced exactly from the live instruction stream, not taken on recon's
word alone.

### Finding 2: the stock FIFO RAM map (EP0, RX3, TX4, EP1) — cross-confirmed

Sole caller of the setup routine is `c01358b4 CALLP c01212e0,B3` (confirmed:
`grep c01212e0 main.dis` returns exactly the definition line and this one
call site). recon/17 B2 finding 2 already traced its arguments
(`c01358ac LDHU *A4[2],A6` = max packet, `c01358b0 LDBU *A4[3],B4` =
attributes, `c01358b2 LDBU *A4[2],A4` = endpoint#) back to the stock
descriptor bytes (recon/17 B1: OUT endpoint 0x03 / IN endpoint 0x84, both
bulk, both wMaxPacketSize=64). That table, which I re-derive here
independently from the "base byte 64" constant at `c012146e` plus the
confirmed 64-rounding/double-buffer logic at `c0121352..8c` (same block
re-read in Finding 1) and cross-check against it exactly:

| FIFO | byte range | size | FIFOSZ (SPRUFM9H enc.) | FIFOADDR (8-B units) |
|---|---|---:|---|---:|
| EP0 (fixed, non-indexed) | 0x000-0x03f | 64 B | n/a — hardware default, never written by software (see note) | n/a |
| RX3 (MIDI OUT, bulk) | 0x040-0x0bf | 2x64 B = 128 B | 0x13 (low4=3=log2(64/8), bit4=1 dbuf) | 0x008 |
| TX4 (MIDI IN, bulk) | 0x0c0-0x13f | 2x64 B = 128 B | 0x13 | 0x018 |
| EP1 (stock/current, ISO) | 0x140-0x33f | 2x256 B = 512 B | 0x15 (low4=5=log2(256/8), bit4=1) | 0x028 |

Total stock (EP0+RX3+TX4) = 64+128+128 = **320 B used**, matching
recon/17/18/20/21's figure exactly; `320+3776=4096`. 4096 B is the USB0
FIFO RAM total per [SPRUFM9H](https://www.ti.com/lit/ug/sprufm9h/sprufm9h.pdf)
sections 2.6/4.55-4.58 (cited already in recon/17 B2; not independently
re-opened the PDF this pass — inherited citation, confidence likely for
the *document* claim, confirmed for the arithmetic it is checked against).
EP0 row: confirmed-by-absence — refs.txt/main.dis show **zero** software
writes to any EP0-indexed FIFOSZ/FIFOADDR (INDEX is never set to 0 before
such a write anywhere in the image: `c0121338`'s STB writes whatever
endpoint number the caller passed, and the only caller c01358b4 always
passes 3 or 4, read from real descriptor bytes, never 0), consistent with
standard MUSB behavior where EP0's FIFO is a fixed 64 B single-buffered
block at RAM offset 0, not part of the indexed allocation space (this
part — the *hardware default value* itself — is "likely": datasheet-
standard, not literally present as a disassembled constant, since there
is nothing to disassemble for a register nobody writes).
Confidence: confirmed (RX3/TX4/EP1 ranges, sizes, SZ encoding, total);
likely (EP0's hardware-default placement/size, and the SPRUFM9H 4096 B
citation, both inherited/datasheet-based, not re-derived from a new PDF
read this pass).

New check (not in prior recon passes): grepped `build/fw/map/refs.txt`
(global scan of every resolved MVK+MVKH absolute-address constant in the
whole image, 4527 lines) for `01e0040e` — **exactly one hit**, at
`c012132c` (inside c01212e0 itself) — and grepped `main.dis` for the low
halves of TXFIFOSZ/TXFIFOADDR/RXFIFOSZ/RXFIFOADDR (`0x462,`/`0x463,`/
`0x464,`/`0x466,`) — **zero hits** anywhere outside the offset arithmetic
already quoted above (those addresses are never built as their own
MVK/MVKH immediate pair; they only ever appear as `INDEX + constant`).
Confidence: confirmed. This means `c01212e0`/`c012146e..c01214c6` is
provably the *only* place in the firmware image that programs the indexed
FIFO registers — there is no second, hidden allocator.
