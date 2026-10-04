---
name: zd2-dsp-investigator
description: Analyze, reverse-engineer, and extract DSP logic from Zoom .ZD2 patch files. Use when you need to understand the binary structure, parameter mappings, or DSP math of Zoom effects modules.
---

# ZD2 DSP Investigator

This skill provides workflows for analyzing Zoom `.ZD2` files (ZDL containers) to extract metadata and reverse-engineer DSP algorithms.

## Workflow: Initial Reconnaissance

When given a `.ZD2` file, identify its purpose and structure:

1.  **Extract Header**: Use the `zd2 inspect <file>` tool to read the magic bytes (`ZDLF`), Effect ID, and Name.
2.  **Verify Offsets**: Check if the block start offset (usually `0x80`) matches the file.
3.  **Analyze Parameters**: Examine the `PRMJ` (JSON) block to see the user-facing knobs and their internal names.

## Workflow: DSP Extraction & Reverse Engineering

To translate a hardware effect into a software model (e.g., JUCE):

1.  **Extract Binary**: Run `zd2 extract <file>` to save the `DATA.elf` block.
2.  **Analyze Assembly**: Use Ghidra or a similar disassembler (target: TI TMS320C6x) to locate the main process loop.
3.  **Identify Math Patterns**:
    *   Look for `OVS_UP_COE` / `OVS_DOWN_COE` symbols for oversampling logic.
    *   Look for `_tbl` symbols for look-up tables (Waveshapers, Filter coefficients).
    *   Parallel filter paths (LPF/HPF) often indicate a "Tilt" tone stack.

## Reference Materials

- **Binary Format**: See [references/format.md](references/format.md) for field-by-field offsets.
- **Example Analysis**: See [references/muff-case-study.md](references/muff-case-study.md) for a deep dive into the NYC Muff DSP logic.
- **Prior Art**: Refer to the `mungewell/zoom-zt2` project for additional context on ZDL containers.

## Best Practices

- **Zero-Guessing**: If a field is unknown, mark it as `TODO` or `?`.
- **Parameter Alignment**: Always map `PRMJ` parameter names (e.g., `SUSTN`) to their corresponding `_edit` symbols in the binary for accurate modeling.
