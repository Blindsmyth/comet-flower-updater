# USB optimization: Sonnet A3 (2026-10-16)

Task: brief docs/helpers/USB_OPT_BRIEF_2026-10-16.md, item A3 only. Static
analysis only; no pedal/MIDI/audio-device/updater/tools-flash access.
Inputs: build/fw/map/main.dis, build/fw/map/refs.txt, recon/18_round3.md,
recon/20_usb_audio_proto.md, recon/21_usb_audio_needs.md. Scratch:
build/scratch/sonnet_a3/ (unused so far; no script was needed).

## Summary

Stock USB0 FIFO RAM (4096 B total, SPRUFM9H 2.6/4.55-4.58): EP0 fixed
0x000-0x03f (64 B, hardware default, never software-written); RX3 (MIDI
OUT) 0x040-0x0bf (128 B, FIFOSZ 0x13); TX4 (MIDI IN) 0x0c0-0x13f (128 B,
FIFOSZ 0x13) — both set by the sole generic-allocator call site
`c01358b4 -> c01212e0/c012146e..c01214c6`. Today's EP1 sits at 0x140,
2x256B. **Yes, 2x512B EP1 (24-bit/270 B packets, TXFIFOSZ 0x16, TXMAXP
270) fits at the same unchanged address 0x140**: it ends at 0x540,
2752 B still free, no stock range touched. Confirmed by a global
`refs.txt`/`main.dis` scan: `c01212e0`/`c012146e..c01214c6` is the *only*
code in the whole image that ever writes INDEX/TXFIFOSZ/TXFIFOADDR/
RXFIFOSZ/RXFIFOADDR. It is reached only from stock SET_CONFIGURATION
(`c0135660`) and SET_INTERFACE (`c0135940`), and the bus-reset handler
(`c0138660`) does not touch USB0 MMIO at all. Under the firmware's own
adopted design (recon/21 3.1 "design (b)") neither path ever reaches EP1
(IF3 alt1 is intercepted before `c0135940`; IF3 alt0 has no endpoints), so
nothing clobbers a moved/enlarged EP1 today. The only residual hazard is
if a *future* patch routes EP1 through the stock alt-setting path
(recon/17's rejected "design (a)"), which would renumber RX3/TX4 — a
design-choice risk, not a risk in the current code, and unrelated to
EP1's size. Details and instruction evidence: Findings 1-4 below.

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

### Finding 3: 2 x 512 B EP1 (TXFIFOSZ 0x16) fits at the same address 0x140, with 2752 B to spare (confirmed arithmetic; design already anticipated)

24-bit stereo at 45 frames/ms needs 270 B/packet (brief's figure); rounding
up to the next power-of-two bank size per the stock allocator's own
rounding rule (Finding 1/2: low4 = log2(bank/8)) gives bank=512 B
(log2(512/8)=6 -> low4=0x6), double-buffered (bit4=1) -> **TXFIFOSZ =
0x16**, total FIFO = 2x512 = **1024 B**. This exactly matches recon/17 B2's
own statement ("270-byte packets need 512 B per bank... size 0x16").

Placed at the same tail address as today, byte **0x140 (FIFOADDR units =
0x140/8 = 0x28)**:
```
0x140 + 1024 = 0x540 (1344 decimal)
4096 - 1344  = 2752 B still free
```
0x540 < 4096, so it does not run off the end of FIFO RAM, and 0x140 is
exactly the first byte *after* TX4's range (0x0c0-0x13f, Finding 2) — i.e.
it does not overlap EP0 (0x000-0x03f), RX3 (0x040-0x0bf) or TX4
(0x0c0-0x13f) either. **Yes: 2 x 512 B fits without moving any stock
endpoint, at the unchanged address 0x140 (FIFOADDR 0x28).** Only the
TXFIFOSZ byte (0x15 -> 0x16) and TXMAXP (180 -> 270) need to change versus
today's `usb_audio_setup_ep1` (firmware/usb_audio_proto/usb_audio.c:
`USB_TXFIFOSZ`/`USB_TXMAXP` writes) — the FIFOADDR write stays 0x28.
Confidence: confirmed (pure arithmetic on confirmed stock ranges).

### Finding 4: what *would* clobber a moved/enlarged EP1 — none of it reaches EP1 in the currently-adopted design (b); it is a live risk only if a future patch routes EP1 through the stock path

Two places re-run the generic allocator after boot:
- **SET_CONFIGURATION**: `c0135660` -> `c01356fa CALLP c01357c8,B3` (loop
  over interfaces at alt 0) -> `c01357c8` -> `c01212e0` for each endpoint
  of each alt-0 interface descriptor it walks (recon/21 3.1, re-checked).
  IF3 alt 0 has no endpoint descriptors (recon/17 B5), so this pass never
  calls c01212e0 for EP1 under the adopted design.
- **SET_INTERFACE**: stock table slot 11, `c0135940`, also falls into
  `c01357c8` -> `c01212e0` for whichever alt the request selects. Per
  recon/21 3.1 (confirmed call-order tracing, not redone this pass): the
  common SETUP decoder (`c01359e4`/`c0135a18..a82`) dispatches to a
  registered **interface record's own callback first**, and only falls
  through to the standard table `c0180210`/`c0135940` when that callback
  returns `0xffff8a5b`. Design (b) (recon/21 3.1, "preferred") has IF3's
  callback handle `bRequest 11` itself and return 0 — it never falls
  through to `c0135940`, so `c01212e0` is never reached for EP1 this way
  either.

New check this pass (ruling out a *third*, undocumented path): grepped
`main.dis`/`refs.txt` for any other code that builds `0x1e0040e` or the
TXFIFOSZ/TXFIFOADDR/RXFIFOSZ/RXFIFOADDR low halves as an immediate
(Finding 1: zero hits beyond c01212e0/c012146e), and read the bus-reset /
deconfigure handler `c0138660` (callers `c015e8b0`, `c015e9f4`) in full —
it only clears two small software record tables at `c0110000+0xa4e8` and
`c0110000+0xa620` (SPLOOP byte/word clears, `c01386ec`/`c0138708`); it
touches **no** `0x1e0xxxxx` MMIO address at all. So there is no reset-path
FIFO rewrite outside the two SET_CONFIGURATION/SET_INTERFACE routes above.

**Conclusion:** under the firmware's own adopted design — IF3 alt 1 never
falls through to stock `c0135940`/`c01357c8` (recon/21 3.1, design (b)) and
IF3 alt 0 has no endpoints — `c01212e0`/the repacker is *never* invoked for
EP1, so enlarging EP1 to 2x512B at the same address 0x140 carries the same
"not reached" safety as today's 2x256B version; the existing comment in
`firmware/usb_audio_proto/usb_audio.c` ("fixed tail FIFO reservation...is
not later overwritten by c012146e..14c6's generic repacker") already
states this and remains correct for the enlarged size. The *residual* risk
recon/17 B2 flagged ("stock allocator repacks all endpoints numerically;
adding TX1 moves RX3/TX4") applies only to the **rejected** design (a),
where EP1's descriptor would be walked by the stock alt-setting configure
path and would then be inserted in numeric order (TX1 before RX3/TX4),
shifting them to higher addresses — this is a design-choice risk, not a
risk realized in the current firmware, and it is independent of EP1's
size (256 B or 512 B per bank, same hazard either way).
Confidence: confirmed (no other stock FIFO-register writer exists;
SET_CONFIGURATION/SET_INTERFACE call chains to c01212e0; c0138660 does not
touch USB0 MMIO) / likely (that no *third* record-callback path, beyond
the ones already traced in recon/21 3.1, could still reach c0135940 for
IF3 under some host request sequence not statically enumerated here).
