# Ghidra test (2026-10-09)

**Question:** would Ghidra plus a Ghidra MCP make the firmware map faster or
better than our `dis6x` + `tools/fwmap` pipeline?

**Set-up:** Ghidra 12.1.3 (`C:/Users/z/tools/ghidra_12.1.3_PUBLIC`, JDK 21) with
the C6000 extension geepot/ghidra-c6000 v1.0.1 (Apache-2.0, built for 12.1.3).
Import `build/fw/map/main.elf` as `C6000:LE:32:default`, headless. Scripts are in
`tools/ghidra/` (ExportMap.java exports functions and xrefs; Seed2.java seeds
our 3010 known starts; compare.py compares the result with coverage.tsv,
hidden_starts and recon/map rows).

**Result: not useful yet.** Ghidra decodes about 8% of the code.

| run | functions | our 2790 starts found | hidden starts (220) | refs to c0119fb0 (9 known) | callers of c01357c8 (2 known) |
|---|---|---|---|---|---|
| plain auto-analysis | 2023 | 1238 | 26 | 1 | 1 |
| seeded with our starts + flow overrides | 3011 (seeds) | seeded | seeded | 0 | 0 |

Instructions decoded: about 12k against about 150k in main.dis.

**Why (three extension problems on this firmware):**
1. `CALLP c016e020,A3`, the save-on-entry helper call that opens most
   functions, is not followed by fall-through. Disassembly stops after the
   first instruction of the function (c0135940 decodes only its CALLP).
2. Disassembly cannot start in the middle of a compact fetch packet. Even
   with a CALL flow override on every CALLP, the 611 fall-through addresses
   would not disassemble.
3. The "C6000 Late Branch Flow" analyzer crashes on the ELF's non-loaded
   blocks (`_elfSectionHeaders`, `.shstrtab`): "Start and end addresses must be
   in same address space". Removing those blocks in a pre-script avoids it.
Also: the ELF has no block for the RAM at c0100000..c011adc0, so Ghidra
cannot record references to globals such as c0119fb0 until one is added
(Seed2.java adds it).

**Verdict:** keep the `dis6x` pipeline. A Ghidra MCP is worth revisiting only if
the extension fixes items 1 and 2; they could be reported to geepot/ghidra-c6000
with c0135940 as the repro. REA (morluto/rea) drives Ghidra too, so it has the
same limits here.
