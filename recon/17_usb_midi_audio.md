# USB MIDI controller blockers and USB audio out

Static analysis only. No pedal or USB device access. Scratch: `build/codex7/`.

## A1. Boot cache configuration and payload residency
Pending.
## A2. Veneer cave references
Pending.
## B1. Current USB descriptors
Pending.
## B2. Endpoint FIFO allocation
Pending.
## A3. MIDI transmit backpressure
Pending.
## B3. Final audio output tap
Pending.
## B4. USB servicing
Pending.
## B5. USB audio verdict and patch plan
Pending.
## A4. Conditional controller image
Pending A1/A2.
## A5. Owner-only test checklist
Pending.

### A1 finding 1 — normal loader and cache-operation anchors (confirmed)
Independently wrapped res5 AIS sections in `build/codex7/boot.elf` and disassembled with TI dis6x into `boot.dis`. Normal loader reads section address/length and passes them directly to flash read; there is no destination-specific L2 configuration in this branch:
```text
c022bb54 CALLP c01fda8c,B3 ; read 8-byte section header
c022bb62 LDW *B15[3],A6   ; length
c022bb66 LDW *B15[2],B4   ; destination
c022bb68 CALLP c01fda8c,B3 ; flash -> destination
c022bb80 AND B0,B1,B0     ; round section size to four bytes
```
Identified res5 block-cache wrappers: c020d940 selects 01844018 (L2 invalidate), c020d960 selects 01844010 (writeback/invalidate), c020d980 selects 01844000 (writeback); each calls c0206480. c020b720 writes 1 to 01845028 (global L1P invalidate), after waiting on 01844004. These are cache maintenance, not evidence that 1182a000 is SRAM. Register-pair scan saved as `bootrefs.txt`; computed/table-derived pointers still require separate review.

### A1 finding 2 — boot initializer selects 128 KiB L2 cache (confirmed stores; execution-chain audit pending)
```text
c0203d3c/c0203d40 A4 = c022a274
c0203d44 LDW *A4[0],A3
c0203d46 MVK 0,B6
c0203d48 MVKH 01840000,B6
c0203d50 STW A3,*B6[0]       ; L2CFG = 3
c0203d54 ADDAD B6,8,B5       ; 01840040
c0203d62 STW B7,*B5[0]       ; L1DCFG = 3 from c022a270
c0203d6c SUB B5,0x20,A3
c0203d74 STW A4,*A3[0]       ; L1PCFG = 4 from c022a26c
```
AIS-backed words are c022a26c=4, c022a270=3, c022a274=3 (`inspect.py`). Initializer address c0203d20 occurs in startup table at c0229e58. This mode leaves only 11800000..1181ffff as L2 SRAM; 1182a000 is outside it. The main firmware **stock** c016d08c supplies 3, not 2; the brief's 2 refers to `patch_res1.py`'s proposed compact-instruction replacement. Main's later change cannot retroactively repair a load attempted into cache space. Need finish startup-table execution trace before making an unconditional boot-path verdict.

### A1 disposition — **no for the traced stock res5 startup** (likely overall; confirmed initializer/call-table evidence)
Startup goes c020ab60 -> c0208240 (C initialization) -> c02097a0; c0209828/c020982c calls the pointer at c022a534=c020dfa0. That wrapper supplies 12 startup modules (`c020dfa4 MVK 12,B4; c020dfa8 CALLP c0205340`). Module table c022a544=c0229e48 contains the cache initializer as entry 4, c0229e58=c0203d20. The repeated startup pass calls unfinished entries (`c02054e8 LDW *B4[0],B4; c02054f0 B B4`), including this entry initially zeroed at c0205368. It returns -1 at c0203f94 after setting cache/MAR configuration. Thus boot configures L2CFG=3 before the application loads main AIS. No subsequent cache-size reconfiguration was identified in the direct-address scan. An appended load at 1182a000/1182a100 therefore has no demonstrated SRAM destination and must not be built on the assumption that main's future L2CFG=2 fixes it.

Cache write inventory found by all 0184xxxx MVKH sites plus literal-pointer search: L2CFG c0203d50; L1DCFG c0203d62; L1PCFG c0203d74; MAR loop store c020c314 reached from c0203db0,3dec,3e28,3e68,3ea8,3ee8,3f28,3f6c; block BAR stores c0206580/c02065d8 and WC store c02065ec (B6 chosen by the three wrappers); global L1P invalidate c020b720. c0206668 additionally clears a table-selected memory-controller coherence register, not a proved cache-size register. Exhaustive arbitrary computed-address exclusion is not claimed.

[SPRUG82A section 2.7.2/Table 2-6](https://www.ti.com/lit/ug/sprug82a/sprug82a.pdf) requires moving data only out of SRAM converted into cache; unchanged SRAM is retained (inference from the documented procedure). A valid load in SRAM remaining below 11830000 would survive a transition to mode 2. Here 1182a000 begins in the **cache** portion under mode 3, so that preservation argument does not apply. [SPRS377F](https://www.ti.com/lit/gpn/TMS320C6745) establishes the 256 KiB L2 device memory map. [SPRABB1C](https://www.ti.com/lit/an/sprabb1c/sprabb1c.pdf) was checked: it does not provide an instruction-complete ROM cache-write trace. ROM image/revision and all indirect boot writes remain missing for an exhaustive inventory; they do not supply a basis for bypassing the observed res5 mode-3 write. A verified boot/staging change is required before A4.

### A2 — caves remain **unproved**, with no direct references found (confirmed scan; likely padding)
Scanned the full main AIS section data plus independently decoded C-initialized regions at every byte alignment for 32-bit values in each 16-byte cave. Also scanned all explicit disassembly operands and MVK/MVKH resolved pairs. `build/codex7/memory.py` and `cave-scan.txt` reproduce the checks. All three have zero bytes and no hits:
```text
c0134e28 BNOP B3,5 ; c0134e2c..c0134e3b = four NOP words
c01333cc BNOP B3,5 ; c01333d0..c01333df = four NOP words
c0150b08 BNOP B3,5 ; c0150b0c..c0150b1b = four NOP words
```
The return instructions include all five delay cycles, so these NOPs are not ordinary fall-through delay slots. This establishes plausible padding, **not** the requested proof against every computed target. The stripped AIS has no relocation records describing its original link; the generated analysis ELF cannot restore them. Dynamic effect relocations and runtime-computed callbacks cannot be excluded by a literal scan. Missing: whole-program indirect-target/value-range analysis, all loaded-module relocation/addend inputs and original linker map/relocation provenance. No particular incoming reference was found; answer to “proved free?” is **unknown**, not yes. A4 is independently disabled by both A1's boot issue and this unclosed proof obligation.

### B1 finding 1 — descriptor templates (confirmed data; builder pending)
Independent AIS mapping locates device descriptor at c017f3dc (res1 0x73364), duplicate at c017f3ee. Configuration headers are c017f400 and c017f40a; each is nine bytes plus alignment byte, **not** a contiguous 101-byte configuration. Device bytes: `12 01 10 01 00 00 00 40 86 16 a1 04 00 01 01 02 00 01`. Config bytes: `09 02 65 00 02 01 00 80 fa` (two interfaces, total 101, config 1, bus-powered, 500 mA). This is data evidence, not an instruction; no disassembly excerpt is invented for it. Reproduction: `build/codex7/descriptors.py`. Runtime copying/building and endpoint bytes are still to be traced.

### B1 finding 2 — exact full-speed configuration reconstructed (confirmed)
Builder **c0160ec0** clears a pointer array at c00643c0 and populates descriptor-fragment pointers. `c0160f2e STDW A7:A6,*A4[0]` installs device/config; c0160f4a,0f60,0f74,0f88 install interface/header/jacks; c0160fa0 installs FS OUT and c0160fd8 FS IN. B4==2 chooses alternate 512-byte packet templates at c017db34/db4e. Current-speed reader c0122710 supplies the selector to GET_DESCRIPTOR at c0134fe4. Configuration response copies each fragment's bLength bytes to c0119fb0, bounded by wTotalLength and host wLength:
```text
c0135014 CALLP c0160ec0,B3
c013506c LDHU *A5[1],B3 ; config wTotalLength
c01350a2 LDBU *A7[0],B1 ; fragment bLength
c01350c6 LDB *B5++[1],B0
c01350ca STB B0,*B4++[1]
c01350ce ADD A4,4,A0    ; next descriptor pointer
```
Exact normal full-speed bytes, one descriptor per line (total **101**), reproduced in `config-False.bin` by `config.py`:
```text
09 02 65 00 02 01 00 80 fa
09 04 00 00 00 01 01 00 00
09 24 01 00 01 09 00 01 01
09 04 01 00 02 01 03 00 00
07 24 01 00 01 25 00
06 24 02 01 0a 00
06 24 02 02 1e 00
09 24 03 01 14 01 1e 01 00
09 24 03 02 28 01 0a 01 00
09 05 03 02 40 00 00 00 00
05 25 01 01 0a
09 05 84 02 40 00 00 00 00
05 25 01 01 14
```
Interface 0 alt0: class 1/subclass 1/protocol 0, zero endpoints, AC header version 1.00 linking interface 1. Interface 1 alt0: class 1/subclass 3/protocol 0, two endpoints. Embedded/external MIDI IN jacks 10/30; embedded/external MIDI OUT jacks 20/40. OUT endpoint **0x03**, bulk, 64 B, associated embedded IN jack 10; IN endpoint **0x84**, bulk, 64 B, associated embedded OUT jack 20. Intervals/refresh/synchronization-address bytes are zero. No AudioStreaming interface exists. Device descriptor uses interface-defined class (0), USB 1.10, EP0=64, VID/PID 1686:04a1. Alternate speed templates exist but do not establish high-speed capability on C6745. “Exact host bytes” here means the full normal FS descriptor response; host requests may truncate it by wLength.

### B2 finding 1 — dynamic FIFO configuration routine (confirmed)
Endpoint setup is **c01212e0(A4=endpoint address, B4=attributes, A6=max packet)**. Endpoint low nibble selects INDEX at 01e0040e (`c0121338 STB A1,*B7[0]`). It rounds packet size up to a power of two, starting at 8 B, and always enables double buffering:
```text
c0121352 ADD B2,B2,B2 ; round up; A1 is size exponent
c0121368 ADD B2,B2,B2 ; reserved bytes doubled
c0121378 SET A0,4,4,A0
c0121380 STB A0,*B4[0] ; INDEX+85 = RXFIFOSZ 01e00463
c0121402 STB A0,*B4[0] ; INDEX+84 = TXFIFOSZ 01e00462
c012138c STH B0,*B4[0] ; RXMAXP indexed 01e00414
c012140c STH B0,*B4[0] ; TXMAXP indexed 01e00410
```
Address allocation is rebuilt for endpoints 1..4 at c012146e..14c6: starts at byte 64, adds each TX then RX reservation, writes INDEX at c01214b2, TXFIFOADDR at c01214c0 (01e00464), RXFIFOADDR at c01214c6 (01e00466). `EXTU ...,16,19` converts byte offsets to 8-byte FIFO-address units. Endpoint table stride is 680 bytes. Current allocation totals require checking initialized/reserved endpoints, not merely counting descriptor endpoints.

### B2 finding 2 — normal FS allocation: 320 B occupied, 3776 B available (confirmed traced configuration)
Only direct setup caller c01358b4 consumes standard endpoint descriptor fields (`c01358ac LDHU *A4[2],A6; c01358b0 LDBU *A4[3],B4; c01358b2 LDBU *A4[2],A4`). Thus normal configuration requests RX3=64 and TX4=64. c011fe70(1), called by c0122280, clears the TX/RX reservation tables for all four endpoints before configuration: `c011feb8 STW A1,*B6[8]` and `c011feda STW B0,*B5[1]`, with 680-byte increments c011fef8/c011ff14 and bound 4 at c011ff0c. No other endpoint descriptor is configured in this normal configuration.

| Active FIFO | Byte range | Size-register value | FIFOADDR units |
|---|---|---:|---:|
| EP0 shared | 000..03f | fixed 64 B | fixed 0 |
| RX3 | 040..0bf | RXFIFOSZ=0x13 (64 B x2) | 0x008 |
| TX4 | 0c0..13f | TXFIFOSZ=0x13 (64 B x2) | 0x018 |

Inactive endpoints' address fields can coincide; zero software reservations do not mean they should be enabled at those overlapping addresses. [SPRUFM9H sections 2.6/4.55–4.58](https://www.ti.com/lit/ug/sprufm9h/sprufm9h.pdf) supplies the 4096-byte total, fixed EP0, power-of-two sizing and address units. Free FIFO on this path is **4096-64-128-128=3776 bytes**. A new ISO IN endpoint 1 or 2 fits: 180-byte packets need 256 B per bank (512 B double buffered, size 0x15); 270-byte packets need 512 B per bank (1024 B double buffered, size 0x16). Configure TXMAXP=180 or 270 independently of rounded FIFO size. These are capacity calculations, not measured service guarantees. Stock allocator repacks all endpoints numerically; adding TX1 moves RX3/TX4, so reconfigure while quiescent and preserve exclusive ranges rather than inserting a live overlapping FIFO.

### A3 — partial enqueue plus blocking locks (confirmed); bounded coalescing design (likely)
Ring object is **c0117b28**, read index at +0, write index at +4; data starts **c0117b30**, 1025 byte positions (indices 0..1024), **1024 usable bytes**. Correcting shorthand in recon/15: c0117b28 is the object, not the first data byte.
```text
c0149d80 ADD A1,1,B1
c0149d84 SET A0,10,10,A0 ; limit 1024
c0149d86 CMPLT A1,A0,A0 ; wrap after index 1024
c0149d8e CMPEQ B1,B0,B0 ; next write == read: full
c0149da6 STB B2,*A5[8]  ; object + write index + 8
c0149dcc [A0] BNOP c0149dd8 ; first failed append ends batch
c0149dda MV A2,A4       ; accepted-byte count
```
No capacity wait occurs inside byte append: full returns ffff63be; bulk append returns its accepted prefix count (zero if already full). c0149de4 sets an overflow flag at c0117b24 and invokes registered callback with event 3 on **positive partial** acceptance, then wakes worker bit1. It does not retry the unsent suffix. A wakeup error can replace the accepted count at c0149e74. c0144dc8 rejects unready state with ffff63be. c01274cc hides transport result by releasing the outer semaphore.

The overall send API **can block**, independently of ring capacity: `c01274d4 CALLP c0150b20` with B4=-1 at c01274e0 (B14[161]); `c0149df0 CALLP c014a094` (B14[89]); and `c014a096 MVK -1,B4; c014a098 CALLP c0150b20`. Worker c0149d40 waits for an event, then c0149c14 holds B14[89] while draining/normalizing into c0117318 and calling packetizer (`c0149c8c CALLP c01489a0`), releasing at c0149c98. Thus calling the stock wrapper directly from MainApp, as the prototype does, fails the requested nonblocking guarantee.

Proposed rule: hooks only publish latest absolute 7-bit value plus dirty/version per (channel,CC), with four saturating knob accumulators and one expression slot; overwrite obsolete unsent motion. Use a short bounded critical section to synchronize MainApp and analog producer, with **no semaphore wait or send call in either hook**. Dedicated lower-priority transmitter takes a snapshot, round-robins at most a bounded number of CCs per activation, and keeps the dirty bit if version changed while sending. Under the existing serialization and ring lock, require at least three free bytes before appending a whole CC; otherwise release and retry later, retaining only latest unsent value. Do not call c0149de4 while already holding its nonrecursive lock: implement a reviewed atomic reserve/append path or refactor that boundary. Handle disconnect/reset by clearing partial transport state and publishing latest state on reconnect. Button edges need a separate bounded policy, not motion coalescing. The hook path is bounded by construction; actual critical-section timing and worker integration remain to implement. Do not blindly resend three bytes after a partial stock enqueue.

### B3 — final packed audio tap (confirmed addresses/context; estimated cost)
TX PaRAM1 source at **01c04024** selects which inactive 128-byte half packer **11818aa0** fills: **11f03630** or **11f036b0**. Each contains 16 interleaved stereo frames, two 32-bit words/frame. Planar inputs **11f038b0/11f038f0** are **not yet the exact DAC words**: packer applies fixed-point gain 0x4534fd79 and saturating shifts before storing.
```text
11818aa8 LDW *A3[0],A4      ; current DMA source
11818ad4 CMPGTU B5,A4,B0    ; B5=11f036b0
11818ad8 [B0] MV B5,A8      ; otherwise A8=11f03630
11818b00 SMPY32 A6,A7,A3
11818b04 SMPY32 B5,A7,B4
11818b0c SSHL A3,2,A5
11818b10 SSHL B4,2,A4
11818b18 STNDW A5:A4,*A8++[1]
11818c64 CALLP 11818aa0,B3  ; audio Swi final pack
```
Hook inside/around the packer, preserving its **selected destination base**, and copy after its last store, before returning to the audio Swi. Do not resample the live PaRAM source after return and assume it identifies the same half: DMA can advance. The scheduling chain from recon/16 is RX TCC0 c0151a90 -> c0164240(B14[141]) -> Swi object c0182a40 -> 11818ba0; this is audio **Swi**, not a place to wait for USB or take USB locks. Keep the audio producer bounded and the USB consumer independent.

A raw copy costs 128 B read +128 B write per block: 352800 B/s copied at 2756.25 blocks/s, 705600 B/s aggregate memory traffic. A simple doubleword loop needs 16 loads plus 16 stores and pointer/control work; exact cycles depend on placement, cache misses, contention, and instruction scheduling and are **unknown**, not 32 guaranteed cycles. Deferred conversion yields 64 B/block for stereo 16-bit, 96 B/block for packed 24-bit. Preserve channel order, signed saturation and the codec's significant-bit alignment; establish the desired 16/24-bit extraction numerically from the packed words before shipping. Ring size/drop policy, SRAM or cache-coherent DMA placement, and worst-case audio deadline headroom remain unallocated/unmeasured.

### B4 finding 1 — USB interrupt top half and CPPI descriptor path (confirmed)
USB init c0122260 installs **c011fc8c** as callback with interrupt/event argument **19** (`c0122288..2290` callback pointer; `c0122296 MVK 19,A0`; `c01222a8 CALLP c014a524`). Top half reads 01e00038, services DMA completion queues 24..27, masks interrupt bits through 01e00034, and posts B14[181]'s Swi:
```text
c011fc9a LDW *A4[0],B0 ; 01e00038
c011fcb8/c011fcc0 CALLP c011faa0 ; queues 24,25
c011fcc4/c011fcc8 CALLP c011fb94 ; queues 26,27
c011fd24 STW A0,*A4[0] ; interrupt mask clear
c011fd28 CALLP c0164240
c011fd2c LDW *B14[181],A4
c011fd36 STW A0,*A4[0] ; EOI 01e0003c = 0
```
The driver is **not PIO-only**. c0120250 obtains a free descriptor from queue 28, builds a 32-byte CPPI host descriptor at **c87b9000 + 32*index**, writes length/buffer/original-buffer fields and enqueues it:
```text
c0120280 SHL B7,5,B0
c01202b8 STW B0,*B4[0]
c01202e2 STW A6,*B4[4] ; buffer pointer
c01202ea STW A6,*B4[7] ; original buffer pointer
c0120318 CALLP c011fa70 ; queue submission
```
RX refill c0120d44 calls this path. TX uses related descriptor routines, requiring continuation below. Presence of USB FIFO CPU accesses for EP0 must not be generalized to MIDI endpoints.

### B4 finding 2 — Swi -> UsbTask -> endpoint dispatch, and existing SOF stub (confirmed)
Decoded B14[181] at c01850d4 points to **c0182aa0**, Swi entry **c015b0f0**, priority 13 (audio Swi priority 15). c015b100 calls c01387f0 with command A4=7 and B4=-1; command table c0180d40[7]=**c0138370**. USB worker **c0138310** comes from task-creation descriptor c01800bc (entry +8=c0138310), used at c01387ac. It receives messages on B14[95], indexes command table, and invokes the callback:
```text
c0138318 CALLP c014a214 ; receive USB command
c0138340 ADDAW B1,B0,B0 ; B1=c0180d40
c0138364 B B0
c0138378 CALLP c0121d80 ; decode USB/controller event
c01383e6 LDW *B5[B4],B0 ; B5=c01807a0
c01383ea BNOP B0       ; endpoint/event callback
```
In the Swi's command-7 path c01389ec.., submission details still need timing review; the task/handler association is confirmed by both tables. CPPI TX chain: c01204b4 -> c012042c -> c0120250; c012050c invokes cache operation c016e380 before queuing. Queue writer c011fa70 writes **01e0600c + 16*queue** (`c011fa90 ADDK 24588,A4; c011fa96 STW B0,*A4[0]`), matching CPPI queue manager. EP0 setup is CPU FIFO read: `c0122380 LDW *A4[0],A1; c0122386 LDW *A6[0],A0`, both from **01e00420**. This is mixed CPPI data transport / control PIO, not a general PIO-only stack.

SOF already has a top-half hook: c011fca2 extracts wrapper interrupt bit19; c011fcb2 acknowledges it; **c011fcb4 calls c016f770 -> 11818e80**, currently only `BNOP B3,5`. Rearm c0121576 writes 0x01ff1e1f to 01e00030, including bit19. This is a concrete bounded SOF-hook candidate, not an implemented audio scheduler. At full speed, stage the next packet ahead of the host IN token; use SOF/frame counter plus TX completion to handle buffer ownership and missed intervals. Copying/converting in a bounded high-priority service and PIO-feeding a dedicated endpoint is a simple first design; CPPI is an alternative but needs exact ISO mode, descriptor lifetime, cache and short-packet behavior review. Do not call the semaphore/task-oriented bulk API in Hwi/audio Swi or assume bulk retries apply to ISO.

Clock design (likely): asynchronous IN must derive packet counts from actual codec-produced frames/ring occupancy relative to USB SOF. Nominal sequence totals 441 frames/10 ms (44/45 per ms), but a fixed repeating sequence alone does **not** accommodate independent-clock drift. Track monotonic production/consumption and bounded ring fill; specify startup fill, underrun, overrun, suspend and reset behavior. No resampler is required solely to label the source asynchronous. Deadline/worst-case jitter remains an owner measurement, not closed by FIFO capacity.
