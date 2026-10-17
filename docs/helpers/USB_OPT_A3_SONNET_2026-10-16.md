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
