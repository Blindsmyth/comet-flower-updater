# Stock CPPI TX and isochronous EP1

## 1. TX submission path

### Finding 1 — MIDI reaches a generic per-endpoint CPPI host-descriptor submitter (confirmed)

The stock MIDI worker drains its byte ring and packetizes through `c01489a0` (the
dispatch table selects the USB transport).  At the transport layer `c01384ac`
loads a buffer pointer/length record and calls `c012116c`; that routine masks the
endpoint address to its low nibble and calls `c0120f64`.  For MIDI IN address
`0x84`, this is channel/index 4.  `c0120f64` stores the caller's pointer and
length in the 680-byte-stride TX state record at `0xc011297c + 680*channel`, and
submits immediately through `c01204b4` when state word 5 says the channel is
ready.

```text
c0138508 CALLP c012116c,B3
c013850c LDW   *A4[6],B4       ; transport record buffer
c013850e MV    A12,A4          ; endpoint address
c0138510 ADD   8,B15,A6        ; length/result pointer
c012118c AND   A4,15,A1
c012118e CALLP c0120f64,B3
c0121190 LDW   *A6[0],A6       ; byte count
```

```text
c0120f6c SET   A0,9,9,A0       ; 168|512 = 680-byte stride
c0120f74 MVK   0x297c,B0
c0120f78 MVKH  0xc0110000,B0   ; TX state base c011297c
c0120f94 STW   B1,*B4[6]       ; buffer pointer
c0120f96 STW   A1,*B4[7]       ; length
c0120fa4 CALLP c01204b4,B3     ; if state[5] != 0
```

`c01204b4` snapshots the buffer and count, clears the pending slots, performs a
cache operation through `c016e380`, then calls `c012042c(channel, buffer,
length, ...)`.  `c012042c` clamps the submission length to the channel's current
allowance, selects the 12-byte channel template at `0xc01805c4 + 12*channel`,
and calls the common `c0120250` builder.

```text
c012050a LDW   *A4[9],B4       ; length
c012050c CALLP c016e380,B3     ; cache maintenance on buffer
c0120510 LDW   *A4[8],A4       ; buffer
c0120526 CALLP c012042c,B3
c0120528 MV    A11,A4          ; channel
c012052a MV    B9,B4           ; buffer
c012052c MV    B8,A6           ; length
```

Confidence: **confirmed** for the transport-to-CPPI chain and state writes;
**likely** that `c016e380` is specifically writeback (its exact library
operation is not re-derived here).

### Finding 2 — descriptor, queue-register, and interrupt-completion layout (confirmed)

`c0120250` pops one entry from free queue 28, converts the returned descriptor
address to an index, and addresses `0xc87b9000 + 32*index`.  It writes the
eight-word CPPI host descriptor as follows: word 0 contains the packet length
plus bit 31; word 1 contains the tag/channel field in bits 31:27; word 2 holds
the template's low 12 bits plus bit 29 and descriptor type bits 28:26 = 5;
word 3 is the buffer length; word 4 the buffer pointer; word 5 zero; and words
6/7 repeat the original buffer length/pointer.  The call's `B6` flag also feeds
bit 19 of word 2.  This is a single-buffer, 32-byte host descriptor, not an
endpoint-specific four-byte FIFO transaction.

```text
c01202b8 STW B0,*B4[0]        ; length/control
c01202c4 STW A0,*B4[1]        ; tag/channel << 27
c01202da STW A0,*B4[2]        ; type/template/flag
c01202e0 STW B2,*B4[3]        ; buffer length
c01202e2 STW A6,*B4[4]        ; buffer pointer
c01202e6 STW A0,*B4[5]        ; zero
c01202e8/c01202ea STW B2/A6,*B4[6]/[7] ; original buffer
```

Queue pop reads `0x01e0600c + 16*queue`; queue push writes the same queue-N
register and sets descriptor-size bit 1 in the pointer.  `c01221c0` initially
pushes all 4096 descriptor indices (128 KiB total at 32 bytes each) to queue
28.  Submission uses the queue number in template word 0 (`c0120320 LDW
*A7[0],A4` immediately before `c011fa70`), so it is selected per channel by
the `0xc01805c4 + 12*channel` template rather than fixed in the builder.

```text
c011fa22 SHL  B0,0x15,B0      ; 0x01e00000
c011fa26 ADD  A0,B0,A4        ; + 16*queue
c011fa2c LDW  *A4[0x1803],A0  ; +0x600c, queue pop
c011fa90 ADDK 24588,A4        ; +0x600c, queue push
c011fa94 SET  B0,1,1,B0       ; 32-byte descriptor size flag
c011fa96 STW  B0,*A4[0]
```

The installed Hwi entry `c011fc8c` reads `0x01e00038`, then drains completion
queues 24, 25, 26, and 27.  `c011faa0`/`c011fb94` decode descriptor fields,
update the per-channel ring/state, and forward completed descriptors to queues
32/34 or 33/35 respectively; the larger event/service path later consumes
these.  Thus completion is interrupt-driven but split between the Hwi drain
and deferred USB service; direct recycling to free queue 28 is **not** done by
the shown Hwi routines.

```text
c011fc9a LDW   *A4[0],B0      ; 01e00038 interrupt status
c011fcb8 CALLP c011faa0,B3 || MVK 24,A4
c011fcc0 CALLP c011faa0,B3 || MVK 25,A4
c011fcc4 CALLP c011fb94,B3 || MVK 26,A4
c011fcc8 CALLP c011fb94,B3 || MVK 27,A4
```

Confidence: **confirmed** for descriptor writes, queue-register addresses,
pool count, and Hwi queue numbers; **likely** for the exact semantic names of
the intermediate 32--35 queues and deferred-recycle boundary.

## 2. Channel selection

## 3. Coexistence

## 4. ISO behaviour

## 5. Verdict for USB audio
