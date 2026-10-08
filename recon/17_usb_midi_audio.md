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
