# Brief for Codex: where does an effect's code and data live? (firmware map part 2)

## 0. First action
Create `recon/14_effect_memory.md` with the headings of section 2 below and
update it after every finding (addresses + short disassembly excerpts +
confidence: confirmed / likely / guess). Your usage cap can end the run at
any time; this file is what survives.

## 1. Context (read first, briefly)
- `recon/13_effect_loader.md`: Gemini's loader study with Claude's review
  box. Confirmed: cache split (0xc016d080 -> 0xc016c480: L1P 32K cache,
  L1D 16K cache + 16K RAM, L2 128K cache + 128K RAM). Likely but
  unverified: entry-struct fields [5]-[8] read at 0xc0146ce4.. and passed to
  allocators 0xc01510e8 / 0xc015f644 / 0xc0169fc0. Wrong in recon/13: EDMA
  IS used (Hwi_EDMA, g_Swi_EDMA, EDMA3 addresses in data near res1 file
  0x76a58).
- `recon/10_firmware_capabilities.md` "Firmware map, part 1": AIS layout of
  `build/fw/res1_493412.bin`, the tools in `tools/fwmap/`.
- `build/fw/map/main.dis` (full dis6x listing), `build/fw/map/refs.txt`
  (resolved MVKL/MVKH constants), `build/fw/map/strings.txt`.
- Why it matters: our CF RAT measured ~24k cycles/block on the pedal against
  a 15-17k static estimate. The suspicion is that its 8 KB table (a
  "const_blob" in the effect's `.const`) and/or its code sit in external
  SDRAM, not in on-chip L2 RAM. The owner's rule: the cheapest version that
  sounds the same wins, so memory placement is the biggest lever.

## 2. Questions, in priority order
1. **Effect image placement.** When the firmware loads a ZD2's ELF
   (`.text`, `.const`, `.bss`/state), where does each section go? Find the
   loader (ZDLF/ELF parsing, the relocation loop applying R_C6000 ABS32 /
   ABS_L16 / ABS_H16) and the allocation call that gives each section its
   address. Which heap/region: L2 RAM (0x118xxxxx, also 0x008xxxxx alias),
   L1D RAM, or SDRAM (0xc0xxxxxx)? Is the choice fixed, size-dependent, or
   controlled by something in the file (section flags, names, the INFO
   block, the entry struct)?
2. **Heaps.** Identify each heap: base address, size, which allocator
   function serves it. List the SYS/BIOS heap instances if their static
   configuration is in the data (look near the HeapMem/HeapBuf strings).
3. **Fields [5]-[8].** Verify recon/13's claim: which heap each request is
   served from, the unit (bytes / words / samples), alignment, limits, and
   how the effect receives the pointer (which instance/ctx word).
4. **Audio buffers.** Where are the 16-sample buffers the effect processes
   in place (`ctx[1]`)? L2 or SDRAM?
5. **Cacheability.** Which MAR bits does the firmware set (MAR192+ for
   0xc0000000..)? Is the SDRAM region holding effects cacheable?
6. **Levers** (end section): concrete ways a DIY effect could get its hot
   table/state into fast memory without firmware changes (e.g. a [5]
   request used as a table buffer filled at init), and what a firmware
   patch would need to change otherwise. Mark each as evidence-based or
   speculative.

## 3. How
- Grep and read small windows of `main.dis`; follow call graphs from the
  strings and from known addresses above. `tools/fwmap/calls.py` lists
  constant arguments of calls to a function.
- A stock effect to cross-check the entry struct: `extracted/NYC_MUFF/DATA.elf`
  and `.venv/Scripts/python.exe tools/fwmap/elfsyms.py list <elf>`.
- Do not trust names alone; quote the instructions that prove each claim.

## 4. Hard rules
- **Never touch the pedal**: no MIDI ports; do not run `tools/pedal_g1.py`,
  `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  `make_fs_restore_updater.py`, or any `.exe` other than dis6x.
- Edit only `recon/14_effect_memory.md` and files under `build/codex3/`.
- No git commits or pushes; Claude reviews and commits.
- Finish with a 5-line summary: confirmed facts, open questions.
