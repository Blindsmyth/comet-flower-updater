---
trigger: always_on
description: "Argon Web Browser Bridge Workflow"
---

# Argon Web Browser Bridge Workflow Protocol

This rule governs the autonomous "Human-in-the-Loop" bridge between the local agent (Gemini 3.8 Flash) and Gemini 4 Argon running in the user's web browser (Firefox / Chrome) for the Zoom G1X Four hardware / DSP reverse-engineering workspace.

## 1. Division of Labor

### A. Local Assistant (Gemini 3.8 Flash) — Autonomous Local Execution
- **Authority**: Execute all local file operations, disassembly dumps, Python container scripts (`zd2`, `tools/*`), TI C6000 (`cl6x -mv6740`) compilation, symbol verification (`nm6x`, `ofd6x`, `dis6x`), and `.ZD2` / firmware checksum packing without pausing for micro-approvals.
- **Toolchain Location**:
  - TI CGT C6000: `C:\Users\z\ti\ti-cgt-c6000_8.5.0.LTS\bin\` (`cl6x.exe`, `nm6x.exe`, `ofd6x.exe`, `dis6x.exe`, etc.)
  - Python Environment: `c:\Users\z\Documents\zoom project\.venv\Scripts\python.exe`
  - ZD2 Tooling: `c:\Users\z\Documents\zoom project\.venv\Scripts\zd2.exe`
  - Clipboard Utility: `C:\Windows\system32\clip.exe`
- **When to Pause**: Only hand off to Argon when facing heavy architectural reverse engineering (USB Audio/MIDI register tracing, main firmware disassembly analysis) or complex C++ DSP to bare-metal TI C674x C transpilation.

### B. Remote Specialist (Gemini 4 Argon) — Architectural & DSP Synthesis
- Reverse engineers complex firmware structures in `build/fw/map/main.dis` (MMIO, MUSB, EDMA3, audio Swi, USB alt-setting descriptors).
- Transpiles high-level C++ DSP models (JUCE, circuit MNA, ADAA) into bare-metal C conforming strictly to TI C674x constraints.
- Emits structured `# FLASH_3.8_ACTION_PLAN` blocks, C code files, or binary patches formatted for immediate consumption by Flash 3.8.

---

## 2. Outbound Protocol (Flash 3.8 -> Argon via Clipboard)

Whenever an architectural or DSP synthesis task requires Argon:
1. **Self-Contained Packet Generation**:
   - Write a complete, self-contained prompt to `bridge/to_argon.md`.
   - Include:
     - Onboarding summary & architectural context.
     - Relevant firmware addresses, register offsets, or disassembly snippets.
     - Exact hardware & DSP rules (e.g. 40 KiB slot limit, no switch, no divide, no libm, TSCL cycle budget).
     - Strict output format requirements (e.g. ask Argon to provide code files or `# FLASH_3.8_ACTION_PLAN`).
2. **Clipboard Piping**:
   - Automatically pipe `bridge/to_argon.md` to the Windows system clipboard:
     ```powershell
     Get-Content -Raw "bridge/to_argon.md" | C:\Windows\system32\clip.exe
     ```
3. **User Alert Banner & Terminal Bell**:
   - Trigger the terminal bell:
     ```powershell
     [Console]::Beep(1000, 300)
     ```
   - Print a prominent banner in the output:
     ```
     ========================================================================
     [>>] READY FOR ARGON: Just press Ctrl+V in Firefox / Chrome
     ========================================================================
     Prompt copied to clipboard. Output written to bridge/to_argon.md.
     Waiting for Argon's response in bridge/from_argon/ or next instruction.
     ========================================================================
     ```

---

## 3. Inbound Protocol (Argon -> Flash 3.8 via Files or User Confirmation)

1. **Drop Location**:
   - The user saves or pastes Argon's response into `bridge/from_argon/` (e.g. `bridge/from_argon/response.md`, `effect.c`, `patch.json`, etc.) or drops files in the project root.
2. **Ingestion & Verification**:
   - As soon as a file is detected or the user signals "go", Flash 3.8 automatically:
     1. Ingests the latest file from `bridge/from_argon/`.
     2. Extracts any `# FLASH_3.8_ACTION_PLAN`, `.c`, `.h`, `.json`, or patch instructions.
     3. Compiles code with `cl6x -mv6740` and checks memory footprint against `tools/check_slot_mem.py` (≤ 40 KiB slot heap limit).
     4. Runs relevant Python tests (`pytest tests/`) or verification scripts.
     5. Logs all build and verification results cleanly.
