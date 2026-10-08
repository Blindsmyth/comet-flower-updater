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

### 1.3 Sampler returns its destination pointer and runs before normal GPIO setup
Confidence: confirmed (A4 value, initialized base and call order); actual pre-setup pin levels unknown.

`c0157020 MV A10,A4; c015702e STW A0,*A4[0]; c0157030 CALLP c016e000,A3` leaves A4 equal to the caller's output pointer. The restore helper c016e000..e00e restores saved registers/stack, not A4. Thus, if the bad call returns, startup tests bit 9 of that pointer twice, not switch state. The second bad call reuses the same pointer. It does not return a defined default/uninitialized bitmap.

The GPIO reader uses an already C-initialized MMIO base: decoded `build/codex3/init_1180bd40.bin` has 11813214=01e26000; `118094a0 LDW *A5[0],A0; 118094b2 LDW *A5[8],A0` reads hardware directly. However, MainApp normally calls `c015d440 CALLP c0160ad8` inside stock startup; that routine programs GPIO (`c0160aea STH A0,*A4[10]`, further direction/output stores through c0160b4c). Normal sampler setup is later still: `c0134e18 CALLP c0134db8; c0134dc0 CALLP c01341e4; c0134200 CALLP c01570a4; c015710e CALLP c0156f00` with a real output pointer. The hook runs before both. Reading a pre-setup register is not proof of the eventual stable switch level; boot inheritance may make it work but is not a substitute for this order audit. Fix both defects: call stock startup first, then sample through valid local storage before entering the event loop, or place the latch after c015710e using its produced bitmap. Verify the intended hold timing for that later latch. No source was edited.

### 1.4 Dispatcher preserves the event frame and loop bookkeeping
Confidence: confirmed for the traced loop/compiled instructions; whole-program event-side effects are not claimed equivalent.

At c0134db8 MainApp reserves 24 bytes. Queue receive uses `c0134dd4 ADD 4,B15,A4`; controller dispatch saves another 8 (`c01a0252 STW B3,*B15--[2]`) then forms `c01a0254 ADD 12,B15,A4`: exactly the original event pointer. `c01a0260 LDW *++B15[2],B3; c01a0262 NOP 4` restores both stack and return link before branching to c0134dc4. All stack deltas here are multiples of eight. Normal mode tail-branches to c0127fe0 with B3 intact and returns its B14[27] selector to c0134df4. The asm only additionally clobbers caller-scratch A0/B31; it does not change B14 or the A10..A15/B10..B13 preserved set.

The controller-mode resume executes housekeeping c01537f4 before `c0134dcc STW 0,*B14[124]`, receives the next event, then `c0134de0 STW 1,*B14[124]`. That is the same cycle reached by both stock handler returns and the stock event-42 skip. No missing B14[124] restore is required in the wrapper. The loop retains no scratch-register result across that resume; the event lives on the preserved frame. Skipping handlers intentionally suppresses their screen/system actions too, and does not imply the whole application retains stock behavior. Housekeeping remains able to run c01537a8, including its system-event path; controller mode is not total isolation from all stock UI work.

### 1.5 Existing patched hook words retain targets and analog parallel instruction
Confidence: confirmed for bytes read from the existing BIN and existing disassembly; fresh dis6x rebuild remains blocked.

Independent PowerShell byte reads of `build/fw/res1_controller.bin` decode the CALLP signed 21-bit displacement against its 32-byte fetch-packet base: c0134e14=10d64012 -> c01a0000; c0134df0=10d68c12 -> c01a0240; c015ffd0=10804513 -> c01a01e8. Analog p-bit remains 1, adjacent c015ffd4 remains 9862 (`EXTU A0,24,24,A4`), and fetch header c015ffdc remains e5e08000. Thus A4 is produced in the same execute packet before entering the wrapper; changing the branch target alone does not sever that pairing.

Existing startup wrapper saves/restores B13 and A11:A10 (`c01a0000 STW B13,*B15--[2]; c01a0002 STDW A11:A10,*B15--[1]; c01a0054 MV B13,B3; c01a0058 LDDW *++B15[1],A11:A10; c01a005a LDW *++B15[2],B13`). B15 moves by 16 total, preserving eight-byte alignment. Analog wrapper c01a01e8..022c is a tail-branch wrapper with no frame or preserved-register writes: stock path branches to c014aef4, controller path tail-branches to cc. cc uses a 16-byte frame (`c01a006c STW B3,*B15--[4]`, restore c01a0094) for the three-byte message. The stock analog caller's live A10 is preserved, allowing `c015ffd8 STW A0,*B14[76]` and A10 return after the hook. No B14 modification occurs in these wrappers. This closes these calling-frame checks, not the sampler ABI bug or transport safety.

## 2. SDRAM gap c0187024..c01f4000

## 3. USB audio driver and silence-stream patch list

## 4. Slot 0 residency and remaining reload paths

## 5. Effect exceeding its 40 KiB slot
