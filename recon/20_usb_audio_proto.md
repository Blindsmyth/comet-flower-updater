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

### 1.7 New finding: TXCSR's indexed MMIO address is traceable in main.dis, correcting the 3.6 "direct EP1 TXCSR 01e00512" guess
c0121336 confirms **A10 = 0x1e0040e (the INDEX register)** directly:
```text
c012132c MVK.S2 0x040e,B4
c0121330 MVKH.S2 0x1e00000,B4   ; B4 = 0x1e0040e
c0121336 MV.L1X B4,A10          ; A10 = INDEX register address
c0121338 STB.D2T1 A1,*+B7[0]    ; select endpoint: INDEX = A1 (low nibble)
```
Every later FIFO-config field in c01212e0 is then computed as a fixed offset
from A10, matching B2's own annotations exactly: TXMAXP = A10+2 (0x1e00410,
c0121406/0c), RXMAXP = A10+6 (0x1e00414, c0121386/8c), TXFIFOSZ = A10+0x54
(0x1e00462, c01213f6/c0121402), RXFIFOSZ = A10+0x55 (0x1e00463,
c0121374/80). The ISO/DMA CSR store at c0121444 (re-verified in 1.3) uses
`B4 = A10+4` (c012142e `ADD.L2 B4,4,B4` where B4 is A10's value via the
`MV.L2X A10,B0` at c012142c) — i.e. **TXCSR's indexed address is
0x1e00412 (INDEX+4), confirmed by the same firmware arithmetic that
produces every other B2-confirmed offset**, not merely asserted.

This corrects, rather than merely flags, the gap from 1.6: 3.6 point 5's
"direct EP1 TXCSR 01e00512" is a datasheet-only, unconfirmed address with
zero stock cross-reference. The address actually exercised by this
firmware for TXCSR is the **indexed** one at 0x1e00412 (select endpoint 1
via INDEX=0x1e0040e, then access 0x1e00412) — the same mechanism already
used, confirmed, for every other per-endpoint register in c01212e0. Section
3's SOF routine uses this confirmed indexed path instead of the
unconfirmed direct address. The FIFO *data* register address (0x1e00424
for EP1, by extrapolation from EP0's confirmed fixed FIFO0 at 0x1e00420,
c0122380/86) remains a pattern-based, not firmware-confirmed, address —
EP0's FIFO is genuinely a separate non-indexed register in the standard
MUSB layout, so this extrapolation is independently well-motivated, but
still "likely," not "confirmed" (no stock instruction ever touches
0x1e00424).
Confidence: confirmed (TXCSR indexed address 0x1e00412); likely (EP1 FIFO
data register 0x1e00424, pattern-based).

Status: done.

## 2. 3.6 turned into exact work items

Convention: "new target" means the work item retargets a call/branch/data
pointer to a new address; exact re-encoded instruction bits are produced by
lnk6x at build/patch time, not hand-computed here (C6000 CALLP/BNOP use
PC-relative fields). Where the stock code sets an address via an
MVK-low16/MVKH-high16 immediate pair, I give the exact MVK operand to change
(that half **is** a plain absolute-value word, independent of PC).

### 2.1 Pointer-array relocation and bound (3.6 point 2) — new findings beyond 3.1/3.6
- `c0160ec8 MVK.S1 0x43c0,A1` (+ `c0160ecc MVKH 0xc0060000,A1`): THIS is the
  single place that hardcodes the stock pointer-array base c00643c0. Change
  the MVK operand (and MVKH if moving out of the c0060000 1MB page) to the
  new 25-word array's address in the CTL region (confirmed: A1 feeds A4,
  which the rest of the function writes through — traced live, not just
  cited).
- `c0160ed0 MVK.L2 11,B0` feeding `MVC B0,ILC` then `SPLOOPD 1 / STW
  *A4++[1] / SPKERNEL 1,0` (c0160ed6..e0): this is the array's **clear**
  loop, trip-count source ILC=11. New finding: raising the pointer count to
  25 without raising this clear count leaves words 11..24 unzeroed (stale
  data if the new array is reused memory, undefined if freshly-allocated
  static storage — low risk for a `.const`-backed array we zero at compile
  time, but the loop itself must still cover every slot the new builder
  writes before the explicit per-fragment stores, or skip the loop
  entirely and zero-initialize the C array instead). Work item: either (a)
  change the MVK 11 to MVK 24 (if keeping the SPLOOP clear), or (b) drop
  the loop's relevance by having the new builder statically initialize all
  25 words from a const template, never relying on a runtime clear. (b) is
  simpler and is what build/sonnet4b/usb_audio.c below does.
  Confidence: confirmed instruction addresses/values; the SPLOOPD/ILC exact
  trip-count semantics (ILC=11 -> 11 or 12 iterations) are not independently
  re-derived here — not needed for design (b).
- `c0161044 CMPLT.L2 14,B0,B0`: change immediate 14 -> 24 (reject only
  counts above the new bound). `c0161050 MVK.S1 0xffff8acf,A0` (error value)
  is unaffected.
- `c0160ff6 STW.D1T1 A7,*A4[13]`: this is the stock null-terminator write at
  index 13 (14 pointers total, 0..13). New design needs the null at index
  24 instead; this specific store either moves or the new builder simply
  writes 25 slots (0..23 populated, 24 = null) from scratch.
- Confirmed (new, this pass): the function's output parameter is register
  **A6** at entry (`c0160ec2 MV.S1 A6,A5`), and the final `c0161040 STW.D1T1
  A0,*+A5[0]` writes the array base through that same A5 — i.e. "returns
  its pointer through A6" (3.1's phrasing) is precisely an output-parameter
  write-through, not a return-register convention. This matters for the
  replacement: any hook/replacement must honor the same A4=count-ish,
  A6=out-pointer, B4=? calling convention when invoked from
  c0135014 (`CALLP c0160ec0,B3`) — a stock caller — unless that call site
  itself is also patched to supply the new pointer directly and skip the
  stock builder.
- New fragment data: 10 new UAC fragments (IF2 AC-interface, AC header,
  IT1, OT2, IF3 alt0, IF3 alt1, AS-general, format-type-I, EP1-endpoint,
  CS-endpoint — the recon/17 B5 91-byte block) need their own storage; they
  are new `.const` bytes, not an "old word to change" since nothing stock
  references them yet. Placed in build/sonnet4b/usb_audio.c (section 3
  below) at c01a8000+.
- Response buffer: `c0135094 MVK.S2 0xffff9fb0,B4` and `c01350f0 MVK.S2
  0xffff9fb0,B4` (both confirmed, each paired with an MVKH c0110000 not
  separately re-quoted) hardcode the response-buffer address c0119fb0.
  Work item: change both MVK operands to point at a new >=512-byte buffer
  allocated explicitly in the CTL region (avoids relying on the unproven
  stock allocation size per 3.1). Any other reader/writer of c0119fb0 found
  later must be retargeted identically; this pass found exactly these two
  sites by grepping `main.dis` for the `0xffff9fb0` immediate — no third
  site exists in the image.

### 2.2 IF2/IF3/IN1 registration and routing (3.6 point 3)
- Confirmed (new, this pass): `c015c638 MVK.S1 0xffffaac0,A4` +
  `c015c64a STW.D1T1 A0,*A4++[1]` is a clear loop over the c011aac0
  interface-ownership table (3.2's table), and `c015c66c MV.L1 A4,A0` is
  registration-function entry taking (A4=interface pointer/value, A6=?,
  B4=table) with an internal `CMPEQ 6,A0,A0` sanity check before writing
  through c011aa4c/c011aac0/c011aa18-relative fields (addresses c015c678,
  c015c68c, c015c698, all confirmed MVK/MVKH pairs resolving into the
  c0110000 page). This confirms c015c66c is a **generic** one-registration
  helper, not something that itself special-cases IF0/IF1 — the hardcoding
  3.2 describes must live in c015c66c's caller(s), which call it once per
  interface with fixed arguments.
- Blocked (not resolved this pass, flagged honestly rather than guessed):
  I did not locate and read the caller(s) of c015c66c (the code at/after
  c015c638 that presumably loops a fixed 2 times for IF0/IF1 and OUT3/IN4).
  Work item for a follow-up pass: disassemble forward from c015c638 past
  c015c64a to find every `CALLP c015c66c` site, extract its fixed
  arguments, and add two more calls (IF2->new AC handler, IF3->new AS
  handler) plus an IN1 endpoint registration, all using the **same**
  pattern. This is explicitly listed as unresolved in 3.2 already
  ("Registration c015c66c hard-codes only IF0/IF1 and OUT3/IN4" was itself
  not given call-site addresses in 3.2); I could not close that gap within
  this run's token budget. Marking per-item status below.
- `c0151ed0`/`c0151ed4`/`c0151ee4`/`c0151eec`/`c0151ef0`/`c0151f64`
  (MIDI callback shortcut, confirmed in 1.5): work item is to replace this
  routine's SET_INTERFACE branch (currently an unconditional ACK at
  c0151f64 via `CALLP c015af48,B3`) with a call into a new checked
  handler that (a) validates wValue is 0 or 1, (b) for IF3 only, defers to
  the new alternate-setting handler (2.4) instead of ACKing blindly, (c)
  for the stock-registered MIDI interfaces continues the existing ACK.
  Old word: the branch target of c0151ee4's `[B0] BNOP .S1
  0xc0151f90,5`/c0151ef0's `[B0] BNOP .S1 0xc0151f5a,5` stay as stock
  routing; the new work is entirely inside the body reached after
  c0151eec, i.e. c0151f5a..c0151f90's block gets a new conditional guard.
  Exact byte patch requires re-disassembling c0151f5a..c0151f90, which
  3.5/3.6 do not fully list and which I have not re-read in full this pass
  (token economy) — flagged as needing the next pass to quote in full.
- Table entries `c0180238`=0xc0134e68 (GET_INTERFACE) and
  `c018023c`=0xc0135940 (SET_INTERFACE), both confirmed in 1.2: new target
  for each is a wrapper that enforces configured-state/valid-interface/
  alt range before falling into the existing c0134e68/c0135940 bodies (or
  replaces them outright). These two words are the cleanest single-word
  patch points in the whole plan: each is a plain `.word` (absolute
  pointer, not PC-relative), so "new word" = the literal new handler
  address, no re-encoding needed.
- `c013566c`/`c01359cc` (both confirmed `MVK 0xffffa1b0,A4`, i.e. two
  SPLOOP-based one-byte clears of the c011a1b0 per-interface alternate
  array, matching 3.6 point 3's "one-byte alternate-array clearing...needs
  replacement for all four interfaces"): work item is widening whatever
  count feeds each SPLOOP's ILC so all 4 interface slots are cleared on
  reset/disconnect, not just the interfaces stock cares about. I confirmed
  the base-address instructions only; the ILC values at each site were not
  re-read this pass (two more SPLOOPD sites beyond the one already read in
  2.1) — flagged as a follow-up read, not guessed here.

### 2.3 IN1 FIFO/endpoint reservation (3.6 point 4)
- `c01358b4 CALLP.S2 0xc01212e0,B3` (confirmed in 1.2): this is the only
  caller of the endpoint-setup routine c01212e0, invoked once per
  descriptor endpoint found by the alt-setting walker. Work item: either
  (a) let IF3 alt1's new endpoint descriptor (0x81, iso, 180) flow through
  this same call unmodified and separately patch c012146e..14c6's address
  allocator to special-case endpoint 1 with the fixed tail placement
  (FIFOADDR=0x28, TXFIFOSZ=0x15, TXMAXP=180) instead of the generic
  byte-64-forward repacking (3.3's recommendation), or (b) intercept
  endpoint-1 setup before it reaches the generic allocator and hand-write
  its FIFO registers directly, leaving c012146e..14c6 untouched for
  endpoints 3/4. (b) is lower-risk (does not touch the shared allocator's
  control flow for any existing endpoint) and is what section 3 implements
  as a standalone routine, not a patch to c012146e.
  Confidence: (a)/(b) design choice is mine (likely); the underlying
  FIFOADDR/TXFIFOSZ/TXMAXP constants are 3.3/B2's confirmed arithmetic
  (64-byte power-of-two rounding rule, confirmed at c0121352/68/78 in B2),
  re-used, not re-derived.
- `c0121444 STH.D2T1 A0,*B4[0]` (confirmed in 1.3, ISO/DMA-oriented TXCSR
  write): explicitly NOT reused for the PIO producer per 3.6 point 4 and
  3.3's own warning. Work item: new routine writes TXCSR directly with
  ISO+MODE bits set and DMA bits clear, at the EP1 CSR address — this is
  exactly the "likely, datasheet-only" gap flagged in 1.6 (01e00512); no
  stock instruction confirms that literal address, so section 3's code
  isolates it behind one named constant for easy correction.

### 2.4 SOF hook (3.6 point 5)
- `c011fcb4 CALLP.S2 0xc016f770,B3` (confirmed in 1.4): old target chain is
  c016f770 (veneer) -> 11818e80 (`BNOP B3,5`, confirmed bit-exact in 1.4).
  Work item: retarget c011fcb4's CALLP to a new bounded SOF routine
  instead of the veneer. Because CALLP is PC-relative, the "new word" is
  not hand-computable here; the work item is precisely "relink this call
  site against the new routine's address," which is what a real patch tool
  (not run in this pass) would do. Equivalently, and lower-risk: retarget
  the **veneer** c016f770's `MVK 0xffff8e80,B31`/`MVKH 0x11810000,B31` pair
  (both plain absolute-value immediates, confirmed in 1.4) to point at the
  new SOF routine's address instead of 11818e80, leaving c011fcb4 itself
  untouched. This second option only requires changing two MVK/MVKH
  immediate words, not re-encoding a CALLP — the practical choice for a
  hand-specified patch list. Old words: c016f770's `0fc7402a` (MVK
  0xffff8e80,B31) and c016f774's `0f88c0ea` (MVKH 0x11810000,B31); new
  words encode the new routine's address with the same MVK-low/MVKH-high
  split.
- New routine (section 3): runs in the SOF Hwi context identified in 1.4
  (CPU interrupt 7, event 19) — i.e. it executes with Hwi semantics, not as
  a Swi/Task; per 3.4/3.6 it must be a short, bounded, lock-free PIO
  sequence (no semaphore, no stock send/message API), writing fixed-zero
  frames and setting TXPKTRDY for endpoint 1 only when configured/alt1.

### 2.5 Explicit non-goals carried over from 3.6 point 6
Not attempted as "work items" because 3.6/B5 already mark them owner-only
or unprovable statically: worst-case Hwi/PIO cycle budget, host
enumeration behavior, long-run clock drift. These are restated in item 4.

Status: done (2.2's two sub-points — c015c66c's caller arguments, and the
c0151f5a..c0151f90 body, and the two alternate-array SPLOOP ILCs in 2.2's
last bullet — are explicitly left as **blocked: not read this pass**,
rather than guessed; everything else in 3.6 is turned into a concrete
address-level item above).

## 3. New routines (C/asm) compiled for c01a8000, disassembly check

Files (scratch, not referenced by firmware/tools, no image built):
- `build/sonnet4b/usb_audio.c` — state, MMIO constants with per-register
  confidence comments, `usb_audio_setup_ep1`, `usb_audio_sof_tick`,
  descriptor fragments (recon/17 B5 + recon/17 B1's stock bytes),
  `usb_audio_build_descriptors`, `usb_audio_copy_descriptors`.
- `build/sonnet4b/usb_audio_hooks.asm` — `usb_audio_descriptor_veneer`
  (adapts the C builder to c0160ec0's A6-out-pointer convention,
  recon/20 2.1).
- `build/sonnet4b/usb_audio.cmd` — linker command file, CTL2 region
  c01a8000, length 0x8000, with explicit `--retain` lines (see below).
- `build/sonnet4b/count_desc.sh` — the byte-count check from item 1.6.

Compiled with the exact flags from `tools/make_controller_fw.py`'s
`build_payload()` (silicon_version=6740, abi=eabi, c99, opt_level=2,
mem_model:data=far, mem_model:const=data):
```text
cl6x --silicon_version=6740 --abi=eabi --c99 --opt_level=2 \
     --mem_model:data=far --mem_model:const=data \
     --compile_only usb_audio.c usb_audio_hooks.asm
```
Both files compiled with **zero warnings/errors**. (The .c and .asm files
needed distinct basenames — `usb_audio.c`/`usb_audio_hooks.asm`, not two
files both named `usb_audio.*` — cl6x's default `--obj_directory` output
naming collided and silently overwrote one `.obj` with the other when I
first tried matching basenames; this is a build-script pitfall, not a
code issue, noted in case it recurs.)

lnk6x needed one addition beyond controller.cmd's pattern: at
`--opt_level=2`, cl6x emits one subsection per symbol (`.text`,
`.ua_state:init`, `.ua_state:uninit`, `.const:<name>` etc., confirmed via
`ofd6x --obj_display=sections`), and with no `_c_int00` entry point
lnk6x's default reachability analysis discarded all of them
("no input section is linked in"). Adding explicit `--retain="<symbol>"`
lines for every routine/global (`usb_audio_descriptor_veneer`,
`usb_audio_setup_ep1`, `usb_audio_sof_tick`, `usb_audio_build_descriptors`,
`usb_audio_copy_descriptors`, `desc_ptrs`, `usb_audio_state`,
`usb_audio_resp_buf`) fixed it; controller.cmd did not need this because
it only retains `.text:dispatch`/`.ctl_state` by *section* name, but this
file's per-symbol subsections needed per-symbol retains instead. This is
new, generally-useful information for any later helper hitting the same
linker error.

Link result fits easily in the 32 KiB window:
```text
CTL2   origin c01a8000  length 00008000  used 000007d5  unused 00007b2b
.text     c01a8000  0x360   (usb_audio.obj .text + usb_audio_hooks.obj .text)
.ua_state c01a8360  0x20c   (usb_audio_resp_buf 512B + usb_audio_state 12B)
.const    c01a8570  0x205   (descriptor fragments, silence_frame, etc.)
.far      c01a8778  0x064   (desc_ptrs[25])
```

dis6x (`dis6x usb_audio.elf`) placed and disassembled all five routines
correctly:
```text
c01a8000  usb_audio_sof_tick
c01a80c8  usb_audio_setup_ep1
c01a8100  usb_audio_copy_descriptors
c01a8204  usb_audio_build_descriptors
c01a8340  usb_audio_descriptor_veneer
```
Spot-checked disassembly confirms the source's intent was compiled
exactly as designed — every MMIO address used by the SOF routine and the
setup routine resolves to the constant intended, matching the confirmed
values from items 1.3/1.7:
```text
c01a8044 MVK.S2 0x040e,B8 / c01a8048 MVKH.S2 0x1e00000,B8   ; B8=USB_INDEX (0x1e0040e)
c01a805c STH.D2T2 B31,*+B8[0]                               ; INDEX=1 (B31=1, c01a802c)
c01a8054 ADD.S2 4,B8,B7                                     ; B7=USB_TXCSR (0x1e00412)
c01a8060 LDHU.D2T2 *+B7[0],B9                                ; read TXCSR (TXPKTRDY poll)
c01a807c ADDAH.D2 B8,0xb,B5                                  ; B5=USB_EP1_FIFO (0x1e0040e + 0xb*2 = 0x1e00424)
c01a8094 LDW.D1T1 *A4++[1],A3 / c01a8098 MV.L2X A3,B4 / c01a80a0 STW.D2T2 B4,*B5[0]
                                                              ; SPLOOP: n words from silence_frame[] into EP1 FIFO
c01a80a4 MVK.S1 0x4001,A4 / c01a80ac STH.D1T1 A4,*+A5[0]     ; TXCSR = ISO(0x4000)|TXPKTRDY(0x0001)
```
```text
c01a80c8 MVK.S1 0x040e,A5 / c01a80cc MVKH.S1 0x1e00000,A5    ; A5=USB_INDEX
c01a80d8 MVK.S1 180,A5 ... c01a80ec STH.D1T1 A5,*+A3[0]      ; TXMAXP=180, A3=INDEX+2
c01a80e4 STH.D1T2 B5,*A5[0] (B5=40=0x28) -> TXFIFOADDR=0x28  ; (A5 here is the +4-offset reuse seen in the fuller excerpt)
c01a80f0 STB.D2T2 B5,*+B4[0] (B5=21=0x15) -> TXFIFOSZ=0x15
c01a80f8/fa STH.D1T1 A3,*A4[0] twice (8 then 0)              ; FLUSHFIFO then clear, A4=INDEX+4=TXCSR
```
```text
c01a8340 usb_audio_descriptor_veneer:
  STW B3,*B15--[2]; CALLP usb_audio_build_descriptors,B3; LDW *++B15[2],B3
  MVK 0xffff8778,A0 / MVKH 0xc01a0000,A0   ; A0 = &desc_ptrs (0xc01a8778, matches the .far entry in the map)
  STW A0,*A6[0]                            ; write through the caller's A6, per c0160ec0's own convention (recon/20 2.1)
  BNOP B3,5
```
Every constant (0x1e0040e, +2, +4, +0xb*2=0x16 byte offset giving 0x424,
180, 0x28, 0x15, 0x4001, the desc_ptrs address matching the map file) is
exactly what the C source specified — i.e. the compiler did not
mis-resolve any of the hand-reasoned MMIO addresses from items 1.3/1.7/2.3.
This confirms the *code I wrote* is internally consistent with my own
design, not that the design is correct on real hardware (see item 4).

Status: done.

## 4. What can only be proven on hardware
