# Round 3 static audit

Static analysis only; no pedal, MIDI, USB-device access, or executable toolchain invocation. Scratch: `build/codex8/`. Findings are committed individually.

## 1. Independent audit of the controller firmware

### 1.1 Fresh build conflicts with the run constraints
Confidence: confirmed (source paths); existing machine-code provenance not independently rebuilt.

`tools/make_controller_fw.py:32,103..112` fixes intermediate output at `build/controller/` and launches cl6x, lnk6x and dis6x; `--out` changes only the final BIN. Running it as requested would violate this run's scratch-only writes and the brief's executable ban. No build tool was run. Audit continues against existing `build/controller/controller.elf` and `controller.dis`; a fresh isolated rebuild remains missing. Existing disassembly anchor: `c01a0000 STW B13,*B15--[2]; c01a0010 B A11; c01a0014 ADDKPC ...,B3,4` (startup wrapper). This is evidence from the existing artifact, not a claim that source and ELF were rebuilt together.

### 1.2 Startup calls the switch sampler with the wrong ABI
Confidence: confirmed (signature mismatch and stores); corruption destination depends on incoming A4.

The sampler is not `u32(void)`: it writes through an output pointer supplied in A4. Evidence: `c0156f04 MV A4,A10; c0156f08 STW B0,*A4[0]` clears that destination; subsequent GPIO results are merged into it (`c0156f28 STW B0,*A4[0]`). Its stock caller supplies 11813308 explicitly: `c01570f4 MVK 3308,A10; c01570f8 MVKH 11810000,A10; c015710e CALLP c0156f00,B3 || c0157110 MV A11,A4`, then reads `c0157114 LDW *A4[0],A0` after restoring A4=A10. Existing controller code `c01a0010 B A11; c01a0014 ADDKPC ...,B3,4` passes no valid output buffer; the second call at c01a0018 also lacks one. Consequently the two purported bitmap return values are not valid sampler results and startup can overwrite an uncontrolled address before stock startup runs. Calling stock startup last does not preserve its behavior.

Proposed source fix (report only): declare the sampler as `void (*)(u32 *)`, allocate initialized local bitmap(s), and pass their addresses; consume the written bitmap, never the return register. Separately establish GPIO initialization before sampling, or move the latch after sampler/GPIO setup and before event processing. Two back-to-back reads are not timed debounce. Exact returned A4 and initialization ordering are traced separately below.

## 2. SDRAM gap c0187024..c01f4000

## 3. USB audio driver and silence-stream patch list

## 4. Slot 0 residency and remaining reload paths

## 5. Effect exceeding its 40 KiB slot
