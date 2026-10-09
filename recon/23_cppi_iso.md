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

## 2. Channel selection

## 3. Coexistence

## 4. ISO behaviour

## 5. Verdict for USB audio
