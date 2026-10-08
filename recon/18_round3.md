# Round 3 static audit

Static analysis only; no pedal, MIDI, USB-device access, or executable toolchain invocation. Scratch: `build/codex8/`. Findings are committed individually.

## 1. Independent audit of the controller firmware

### 1.1 Fresh build conflicts with the run constraints
Confidence: confirmed (source paths); existing machine-code provenance not independently rebuilt.

`tools/make_controller_fw.py:32,103..112` fixes intermediate output at `build/controller/` and launches cl6x, lnk6x and dis6x; `--out` changes only the final BIN. Running it as requested would violate this run's scratch-only writes and the brief's executable ban. No build tool was run. Audit continues against existing `build/controller/controller.elf` and `controller.dis`; a fresh isolated rebuild remains missing. Existing disassembly anchor: `c01a0000 STW B13,*B15--[2]; c01a0010 B A11; c01a0014 ADDKPC ...,B3,4` (startup wrapper). This is evidence from the existing artifact, not a claim that source and ELF were rebuilt together.

## 2. SDRAM gap c0187024..c01f4000

## 3. USB audio driver and silence-stream patch list

## 4. Slot 0 residency and remaining reload paths

## 5. Effect exceeding its 40 KiB slot
