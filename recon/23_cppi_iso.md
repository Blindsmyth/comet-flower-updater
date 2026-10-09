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

### Finding 3 — endpoint N uses software slot N and TX hardware channel N-1 (confirmed)

Endpoint setup accepts low nibbles 1 through 4.  It uses the endpoint number
itself for the 680-byte TX state table and writes it to MUSB `INDEX`.  The TX
service then forms `1 << (endpoint-1)` for the CPPI TX-channel mask.  Therefore
EP1 is software slot 1 but **CPPI TX channel 0**; MIDI IN4 is software slot 4
and CPPI TX channel 3.  It would be wrong to pass channel 0 to the public
endpoint submission API: `c012116c` derives slot 1 from endpoint address
`0x81`, and the lower layer performs the minus one conversion.

```text
c01212ec AND   A3,15,A1       ; endpoint low nibble
c01212f4 CMPLT 4,A1,A0       ; reject endpoint > 4
c012130c MPYLI 680,A1,...     ; state slot N
c0121338 STB   A1,*B7[0]      ; MUSB INDEX = N
```

```text
c012069a MV    A10,A0         ; endpoint/software channel N
c01206a0 MVK   1,B0
c01206a2 ADD   A0,-1,A0
c01206a4 SHL   B0,A0,A0       ; CPPI channel mask 1 << (N-1)
```

The descriptor template is likewise selected with a 12-byte stride from
`0xc01805c4 + 12*N`; submission reads its word 0 as the queue number.  TX
completion service uses a separate nine-word-per-endpoint table at
`0xc01805d0 + 36*N`.  No observed address or branch is hard-wired to EP4.
The code and tables cover endpoints 1--4; exact constant values in the data
templates were not recoverable from the text disassembly, so the precise
submit-queue number for EP1 remains unproved here.

```text
c0120484 MVK/MVKH c01805c4,B0
c012048c SHL   A1,3,A6
c0120490 ADDAW A6,A1,A6       ; 12*N
c0120494 CALLP c0120250,B3
c0120496 ADD   A6,B0,A4       ; per-N template
```

Confidence: **confirmed** for endpoint/software/CPPI-channel mapping and the
generic four-endpoint tables; **likely** that every table entry is fully
initialized for an otherwise unused EP1; **unknown** for EP1's exact queue
constant without decoding the data image.

## 3. Coexistence

### Finding 4 — EP1 TX and EP4 TX are structurally independent and share a large pool (likely)

The driver allocates distinct TX state records at `c011297c + 680*N`, distinct
template entries, and distinct per-channel hardware mask bits.  The common
descriptor pool contains 4096 descriptors, initialized on queue 28, so it is
not a one-channel or EP4-sized pool.  Completion records encode a channel/tag
and are demultiplexed by the shared interrupt drain; the Hwi services four
completion queues rather than an EP4-only queue.

```text
c01221c2 MVK   0,A3
c01221c4 SET   A3,12,12,A3    ; limit 4096
c01221cc CALLP c011fa70,B3
c01221d0 MVK   28,A4          ; shared free queue
c01221d2 ADD   A2,1,A2
c01221d4 CMPLT A2,A3,A0
```

There is no lock in the leaf enqueue `c0120f64`; serialization therefore
depends on its higher-level USB worker/task and interrupt/deferred-service
design.  Stock MIDI submission is task-oriented and its upper API can block.
An EP1 audio producer must not call that upper message path from the SOF Hwi or
audio Swi.  Coexistence is **likely** if EP1 submission is performed in the
same serialized USB service context (or with a new bounded ownership scheme),
but concurrent direct mutation of the shared queue/state machinery from Hwi
and task context is not proved safe.

Confidence: **likely** for simultaneous EP1/EP4 hardware and pool capacity;
**confirmed** that storage/pool sizing is not EP4-only; **unknown** for
race-free direct submission from a new Hwi context.

## 4. ISO behaviour

### Finding 5 — arbitrary one-packet lengths and ZLP exist, but stock code is not an ISO scheduler (likely)

The host descriptor carries the caller's exact length in both packet-length
word 0 and buffer-length words 3/6.  `c012042c` detects a zero requested length
and passes a flag to `c0120250`, which places it in descriptor word 2 bit 19.
Consequently 176 and 180 are representable without padding, and a true
zero-length packet is representable too.

```text
c0120458 LDW   *B4[0],B3      ; available/request length
c012045a CMPGT B1,B3,B0       ; clamp requested length
c0120468 [B1] BNOP c0120480   ; nonzero -> ZLP flag 0
c0120476 MVK   1,A0           ; zero -> ZLP flag 1
c0120494 CALLP c0120250,B3
c01202ca XOR   B1,1,B1
c01202cc SHL   B1,0x13,B1     ; descriptor word 2 bit 19
```

This matches [TI SPRUFM9H, HPD words 0 and
2](https://www.ti.com/lit/ug/sprufm9h/sprufm9h.pdf): packet length is 22 bits,
and word 2 bit 19 explicitly requests a transmit ZLP.  The same guide's queue
table confirms EP1 submit queues 16/17, EP4 queues 22/23, shared TX completion
queues 24/25, and application queues 28--63.  Thus the earlier unknown exact
EP1 queue pair is closed at the hardware-allocation level, although the stock
template's choice between queue 16 and 17 remains unextracted.

Stock endpoint setup recognizes ISO attributes and writes `0x7440`:
ISO|MODE|DMAEN|DMAMODE plus the one-shot CLRDATATOG write.  It also programs
TXMAXP from the endpoint descriptor and enables double-buffered FIFO allocation.

```text
c0121412 AND   B1,3,B0
c0121414 CMPEQ 1,B0,B0        ; ISO transfer type
c0121426 MVK   1,A0           ; endpoint state ISO flag
c0121438 MVK   209,A0
c0121440 SHL   A0,6,A0        ; 0x3440
c0121442 OR    A0,A1,A0       ; add ISO bit 14
c0121444 STH   A0,*B4[0]
```

However, CPPI completion only proves that a submitted packet left the DMA path;
the stock chain has no 1-ms cadence, no 44/45-frame phase accumulator, and no
per-packet read of `PERI_TXCSR` for UNDERRUN.  TI states that ISO has no retries,
data must be loaded before the IN token, double buffering is advisable, and
TXCSR must be checked after every packet; with DMAMODE enabled, normal endpoint
completion interrupts are suppressed.  Requeueing one descriptor per SOF is
therefore new policy, not behavior supplied by `c0120f64`.

Bulk short-packet/ZLP termination is not a reason to pad 176 to 180: each ISO
descriptor should describe exactly one USB packet.  The DMA must remain in
transparent mode for a non-64-byte maximum; TI explicitly excludes generic
RNDIS mode for endpoints whose maximum is not a multiple of 64.  The stock
firmware's exact per-channel DMA mode constant is not conclusively decoded in
this pass, so transparent-mode configuration for EP1 must be verified or
written explicitly.

Confidence: **confirmed** for exact-length/ZLP descriptor construction and
`0x7440`; **confirmed from TI documentation** for queue allocation and ISO
requirements; **likely** that 176/180 work once EP1 is explicitly placed in
transparent mode; **unknown** for stock underrun recovery because none was
found in the traced submit/completion path.

## 5. Verdict for USB audio

### Finding 6 — stock CPPI can carry EP1 ISO packets, but PIO is the safer first implementation (likely)

**Answer:** the stock CPPI TX machinery is not hard-wired to MIDI/EP4.  It can
build and route a single exact-length 176- or 180-byte host descriptor for
EP1/CPPI channel 0, while EP4/channel 3 remains active.  What it does **not**
provide is the frame scheduler, bounded producer handoff, ISO underrun check,
or alt-setting teardown needed for audio.  Therefore “reuse CPPI” is feasible,
but it is not a call-only patch.

For a CPPI implementation, configure endpoint `0x81` through `c01212e0` with
attributes `0x05` and max packet 180; explicitly set EP1 DMA transfer mode to
transparent; reserve its double-buffer FIFO; and keep the next descriptor
queued before the host's IN token.  Submit exact packet buffers through the
audited leaf equivalent of `c0120f64(A4=1,B4=buffer,A6=len)` (or
`c012116c(A4=0x81,...)`) from the serialized USB task/service context, **not**
from the audio Swi or SOF Hwi.  The SOF hook should only publish a bounded
wakeup/phase tick; completion queues 24/25 own buffer recycling.  Maintain at
least two owned packet buffers, check EP1 TXCSR UNDERRUN after each frame, and
perform CPPI channel teardown plus FIFO flush on alt0/reset/disconnect.

```text
c011fca2 EXTU  B0,12,31,B0    ; SOF wrapper bit 19
c011fcb2 STW   B0,*A4[0]      ; acknowledge SOF
c011fcb4 CALLP c016f770,B3    ; existing empty SOF hook
c011fcb8 CALLP c011faa0,B3    ; then TX completion queue 24
c011fcc0 CALLP c011faa0,B3    ; TX completion queue 25
```

For the first silence/audio proof, prefer bounded **PIO** on EP1.  The packet is
only 176/180 bytes per millisecond, and PIO makes the USB packet boundary and
TXCSR underrun check explicit.  Crucially, do not merely OR TXPKTRDY into the
stock `0x7440`: `c01212e0` has already enabled DMA and then calls the generic
DMA service.  The PIO setup must bypass that branch or undo it by tearing down
and disabling EP1 CPPI TX, flushing both FIFO banks, and programming EP1 TXCSR
to ISO|MODE with DMAEN and DMAMODE clear before writing FIFO data and setting
TXPKTRDY.  Preserve MODE on every 16-bit TXCSR write and use direct EP1
registers (`FIFO 0x01e00424`, `TXCSR 0x01e00512`) to avoid shared-INDEX races.

```text
c0121444 STH   A0,*B4[0]      ; stock ISO write is 0x7440 (DMA on)
c0121454 CALLP c011fd98,B3    ; ISO-side DMA/channel setup
c0121460 CALLP c011fd40,B3    ; non-ISO sibling setup
c012146a CALLP c0121224,B3    ; generic endpoint DMA service
```

PIO scheduling should stage one packet ahead using the existing SOF hook,
alternate 44/45 stereo frames (176/180 bytes), set TXPKTRDY once per packet,
read/clear UNDERRUN every frame, and reset phase/ownership on alt0 or bus reset.
If there is no packet ready, record/drop the missed frame rather than spin;
never “retry” an ISO packet.  For real audio, drive the 44/45 choice from
producer/consumer fill or clock estimation rather than assuming a permanently
fixed ten-frame sequence.

Principal CPPI risks are unproved stock transparent-mode constants, completion
latency relative to 1 ms, races if the leaf is called outside the USB task,
cache ownership, teardown with descriptors in flight, and missing underrun
inspection.  Principal PIO risks are Hwi execution time, accidentally leaving
DMA bits/channel active, shared INDEX races, double-buffer flush ordering, and
writing TXPKTRDY too late or too early (POWER.ISOUPDATE policy also needs an
explicit decision).  Neither route is validated on hardware by this static
report.

Confidence: **likely** that CPPI can transmit EP1 ISO correctly with the added
mode/scheduling/teardown work; **confirmed** that stock primitives provide the
necessary channel, exact-length descriptor, and completion queues; **likely**
that PIO is the lower-risk first proof because it makes the required per-frame
TXCSR handling explicit.

## Review (Claude, 2026-10-09)
Spot-checked: the CPPI channel mask `1 << (N-1)` (c012069a..a4), the endpoint
bound (c01212f4 CMPLT 4), and c01212e0's DMA calls c011fd98 / c011fd40 /
c0121224 (c0121454..6a). All confirmed. The verdict (PIO first, CPPI possible
later with its own scheduler and teardown) matches recon/21. Note: with design
(b) in recon/21 3.1, the IF3 callback handles SET_INTERFACE itself, so
c01212e0 never runs for EP1 and no CPPI channel 0 set-up has to be undone.
That holds only if stock never configures EP1 elsewhere (SET_CONFIGURATION
reaches IF3 alt 0 only, which has no endpoints).
