# USB audio "silence stream" prototype (Helper B, round 4)

Scope: docs/helpers/ROUND4.md Helper B. Static analysis and offline compile
only, scratch in build/sonnet4b/, no firmware image built, no hardware/USB
touched. Follows docs/helpers/SAVE_PROTOCOL.md token-economy rules.

## 1. Re-verification of recon/18 3.1-3.6 claims against main.dis

### 1.1 (3.1) descriptor builder/pointer bound and response buffer: confirmed
All cited instructions match main.dis exactly:
```text
c0160ec0 MV.L1 A4,A7                    ; builder entry (confirmed, line 114684)
c0160ff6 STW.D1T1 A7,*A4[13]            ; writes pointer slot 13
c0161044 CMPLT.L2 14,B0,B0              ; count bound 14
c0161050 MVK.S1 0xffff8acf,A0           ; error path
```
c0154c18/c0154c48 both resolve A4=0xc00643fc (MVK 0x43fc,A4 + MVKH 0xc0060000,A4) then `CALLP 0xc0167b00` with B4=0,A6=4 in the delay slots (`MVK 0,B4 || MVK 4,A6`) — a 4-byte memset, exactly as 3.1 describes. c0134e7c/80 and c0134e84/88 resolve A5=0xc011a1b0 and B4=0xc0119fb0 respectively (MVK low16 + MVKH upper16, OR-style combine), confirming both the alternate-setting array address and the response-buffer address used throughout 3.1-3.2. c013506c/70/76/80 (wTotalLength/wLength clip) and c01350c6/ca (byte copy loop) and c0135108 (MV B3,A6 into c015af48's length arg) all match.
Confidence: confirmed (every cited address/opcode matches; the 512-byte buffer *size* remains unproved from the image itself, as 3.1 already states).

### 1.2 (3.2) standard request table, GET/SET_INTERFACE, alt walker, IF mapping: confirmed
Table c0180210 is a `.word` array; c0180238 = 0xc0134e68 (index 10, GET_INTERFACE) and c018023c = 0xc0135940 (index 11, SET_INTERFACE) match exactly. c01359e4 (`CALLP 0xc016e020,A3` — a veneer, consistent with "common decoder"), c0135a52/60 (callback load+branch), the standard-fallback predicate at c0135a90/a6/aa ([B0] BNOP B1,0) and the stall path c0135ab8/c0/c4 (CALLP c0120ef8, MVK 0x80,A4, MVK 1,B4) all match. c0135840/4c/58 (CMPEQ 4,A0,A0; CMPEQ A0,A10,A0; CMPEQ A0,A11,A0 — descriptor-type-4 + interface + alt match) and c013596e/70 (STB then CALLP c01357c8) match.
Confidence: confirmed for every address cited; I did not re-walk c015c788/c015c66c/c011aac0 (interface-ownership table) byte-for-byte — those are data-table claims in 3.2, lower risk, not re-verified here for token economy.

### 1.3 (3.3) ISO CSR bit pattern and FIFO allocator: confirmed
```text
c0121412 AND.L2 B1,B0,B0        ; transfer-type mask
c0121414 CMPEQ.L2 1,B0,B0       ; ==1 (ISO)
c0121434 XOR.L1 1,A0,A1
c012143a SHL.S1 A1,0xe,A1       ; <<14 (bit14 DMA/ISO per 3.3's reading)
c0121440 SHL.S1 A0,0x6,A0
c0121442 OR.L1  A0,A1,A0
c0121444 STH.D2T1 A0,*B4[0]     ; TXCSR store
```
c012146e (MVK 64,B3 — base byte 64) and c01214c0/c6 (STH into B4[0]/A6[0], the TXFIFOADDR/RXFIFOADDR writes) match. I did not independently recompute "A0=209 before the shift -> CSR 0x7440"; that arithmetic depends on a run-time register value, not a disassembly fact, so it stays at 3.3's own confidence (confirmed logic shape, the specific numeric CSR value is a traced-execution claim I have not re-run).
Confidence: confirmed instruction shapes; the specific CSR numeric value is inherited, not independently re-traced here.

### 1.4 (3.4) SOF top half, Hwi vector chain, veneer target: confirmed
```text
c011fca2 EXTU.S2 B0,12,31,B0
c011fcb2 STW.D1T2 B0,*A4[0]
c011fcb4 CALLP.S2 0xc016f770,B3   ; SOF hook call site
c011fd28 CALLP.S2 0xc0164240,B3  ; deferred Swi post
```
c0122290/92/96 (STW B0,*B15[1]; MVK 7,B0; MVK 19,A0) match the {CPU interrupt=7, event=19} registration claim. c016f770 is confirmed to resolve to 0x11818e80 (`MVK 0xffff8e80,B31` then `MVKH 0x11810000,B31`), and 11818e80 itself is the raw word 0x008ca362, which is the exact encoding used elsewhere in this image for `BNOP B3,5` (e.g. c0154c34) — so "veneer branches to a BNOP B3,5 stub" is confirmed, not inferred from a mnemonic the disassembler failed to produce (that address falls inside a DATA-tagged section in main.dis, so dis6x prints it as a `.word`, but the bit pattern decodes to BNOP B3,5 exactly as 3.4 states).
Confidence: confirmed for all cited addresses and the veneer target decode. Worst-case timing is explicitly not re-derived (3.4 already marks it unknown; nothing here changes that).

### 1.5 (3.5) MIDI callback shortcut: confirmed
```text
c01521a8 MVK.S2 0x137c,B4 ; MVKH c0180000,B4 -> 0xc018137c
c01521b0 CALLP.S2 0xc015afa0,B3   ; registration call
c0151ed0 CALLP.S1 0xc016e020,A3   ; request-callback veneer (word at c0181388 = 0xc0151ed0, confirmed)
c0151ed4 MV.L2X A4,B0
c0151ed8 MVK.S1 0xffff8a5b,A1
c0151ee4 [ B0] BNOP.S1 0xc0151f90,5   ; nonzero request-type -> immediate return
c0151eec CMPEQ.L2 11,B1,B0           ; bRequest==11 (SET_INTERFACE)
c0151ef0 [ B0] BNOP.S1 0xc0151f5a,5
c0151f64 CALLP.S2 0xc015af48,B3      ; zero-length status ACK
```
Every address and predicate matches 3.5's description exactly, including the predicate sense ( `[B0]`, not `[!B0]` ) on both branches.
Confidence: confirmed.

### 1.6 (3.6) patch-list anchors and the B5 descriptor bytes: confirmed where checkable, one gap found
The six "instruction anchors" (c0161044, c0135aaa, c0151ef0, c0121444, c01214c0/c6, c011fcb4) are all re-confirmed above. The recon/17 B5 proposed descriptor bytes are internally self-consistent: each fragment's declared bLength matches its byte count, the new 91-byte append sums correctly, 101(stock)+91=192 matches the stated "Total 192 bytes", the new config header `09 02 c0 00 04 01 00 80 fa` encodes wTotalLength=0x00c0=192 and bNumInterfaces=4, and the AC header `01 1e 00 01 03` encodes bcdADC=0x0100 (UAC1), wTotalLength(AC)=30, bInCollection=1, baInterfaceNr(1)=3 — all matching the prose. (Reproduced in `build/sonnet4b/count_desc.sh`.) These are, as B5 says, *design* bytes, not bytes recovered from the image, so "confirmed" here means internal arithmetic consistency only.

Gap found: 3.6 point 5 cites "endpoint-1 FIFO 01e00424 and direct EP1 TXCSR 01e00512" as if these were established addresses. `grep` of main.dis for `0x1e00424`/`0x1e00512` (and the surrounding `0x1e0042`/`0x1e0051` prefixes) finds **zero** stock references — expected, since EP1 is never configured by stock (3.3 already says FIFO/CSR setup only touches endpoints 1..4 generically through the indexed allocator, and stock only activates RX3/TX4). These two addresses rest entirely on the SPRUFM9H register map (direct, non-indexed per-endpoint FIFO/CSR block alongside the indexed CSR at 01e0040c used by c0121444), not on anything visible in main.dis. This does not make them wrong, but they are a datasheet-only claim, one level less certain than the rest of 3.6's confirmed instruction addresses.
Confidence: confirmed (anchors, byte arithmetic) / likely (EP1 direct FIFO/CSR addresses — datasheet-derived, no stock cross-check possible).

Status: done.

## 2. 3.6 turned into exact work items

## 3. New routines (C/asm) compiled for c01a8000, disassembly check

## 4. What can only be proven on hardware
