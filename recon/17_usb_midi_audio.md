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
