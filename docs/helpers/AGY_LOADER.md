# Brief for Antigravity: how the G1X Four firmware loads and runs effects

Context: this project writes new DSP effects (`.ZD2` files, each holding a
TI C6000 ELF) for a Zoom G1X Four (TI C6745 DSP, likely 375 MHz, 32 KB L1D,
32 KB L1P, 256 KB L2 per the datasheet (check), 8 MB external SDRAM). Read
first: `recon/10_firmware_capabilities.md` (firmware layout, tools),
`recon/06_g1_resources.md` (entry-struct fields), `docs/DSP_RULES.md`.

## Goal
Answer, with evidence (function addresses, disassembly lines), how the main
firmware places and runs an effect, so that effects can be made cheaper:
1. **Loader.** Find the code that reads a ZD2's ELF (look for the ELF magic
   0x464c457f compare, section header walks, the relocation types ABS32 /
   ABS_L16 / ABS_H16 = R_C6000_ABS32 1, ABS_L16 8?, ABS_H16 9? — check).
   Where are an effect's `.text`, `.const` (tables) and `.bss`/state copied
   to: internal L2/IRAM (0x118xxxxx / 0x008xxxxx) or SDRAM (0xc0xxxxxx)?
   Which allocator or heap supplies the address?
2. **Memory requests.** The effect entry function `Dll_<Name>` fills a
   struct; fields [5]–[8] look like working-memory requests (recon/06:
   reverbs [5], delays [5]+[6], pitch [7], heavy amps [8]). Find where the
   firmware reads them: units (bytes? words? samples?), which memory each
   comes from (L2 or SDRAM), alignment, limits.
3. **Cache setup.** Find writes to the C674x cache registers: L2CFG
   0x01840000, L1PCFG 0x01840020, L1DCFG 0x01840040, the MAR registers at
   0x01848000+ (which SDRAM ranges are cacheable). State the L1/L2 split
   the firmware chooses.
4. **Audio call path.** From `g_Swi_AudioProcess`: how each slot's effect
   function is called per 16-sample block, what it is given (buffer
   location: L2 or SDRAM), and anything done between slots.
5. **EDMA.** Does the firmware use EDMA3 (registers at 0x01C00000 /
   0x01C14000 ...) for audio or for effect buffers? Could an effect use it?

## How
- `build/fw/map/main.dis` is a full dis6x listing of the main firmware
  (`build/fw/res1_493412.bin`, sections in recon/10). `build/fw/map/refs.txt`
  resolves MVKL/MVKH address constants. Regenerate with the commands in
  recon/10 if missing. Scripts: `tools/fwmap/` (ais.py, mkelf.py, refs.py,
  calls.py).
- Useful strings (`build/fw/map/strings.txt`): heap and SYS/BIOS messages,
  task names (g_Task_PreLoad, g_Swi_AudioProcess, g_Semaphore_FFS).
- A stock effect to compare with: `extracted/NYC_MUFF/DATA.elf`
  (disassemble with `C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS/bin/dis6x.exe`).
- Your context is limited: grep and read small windows of main.dis rather
  than whole files. Keep notes as you go in the output file.

## Output
- `recon/13_effect_loader.md`: one section per question above, each with
  the evidence (addresses + short disassembly excerpts) and a confidence
  (confirmed / likely / guess). End with "What this means for writing
  cheaper effects" (e.g. keep tables under N KB because they live in X).
- Helper scripts in `build/agy/` (gitignored).
- Stop when done or out of budget; list what is unanswered.

## Hard rules
- **Never touch the pedal**: no MIDI ports; do not run `tools/pedal_g1.py`,
  `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  `make_fs_restore_updater.py`, or any `.exe` other than dis6x.
- Edit only `recon/13_effect_loader.md` and `build/agy/`.
- No git commits or pushes; Claude reviews and commits.
