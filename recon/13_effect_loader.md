# Effect Loader and Runtime Analysis

> **Review by Claude (2026-10-06).** Written by Gemini 3.1 Pro (agy) from
> docs/helpers/AGY_LOADER.md, after an Opus run ran out of quota.
> - **Confirmed:** cache setup. 0xc016d080 builds {4, 3, 3} on the stack and
>   calls 0xc016c480, which writes them to L1PCFG / L1DCFG / L2CFG: 32 KB
>   L1P cache, 16 KB L1D cache + 16 KB L1D RAM, 128 KB L2 cache. With L2 code
>   at 0x11800400 that implies a 256 KB L2 (128 KB left as RAM; recon/07's
>   "64 KB" was from memory and is wrong).
> - **Likely (code seen, heap identity not traced by Claude):** the function
>   at 0xc0146ce4.. reads the entry-struct fields [5]–[8] and calls the
>   allocators 0xc01510e8 / 0xc015f644 / 0xc0169fc0. Which heap ([5] = L2,
>   [6]–[8] = SDRAM) needs one more check, plus the units.
> - **Wrong, corrected:** section 5 says EDMA3 is unused. The firmware has
>   `Hwi_EDMA`, `g_Swi_EDMA` and `g_Semaphore_EDMA`, and its data holds
>   EDMA3 addresses (0x01c00000 region, e.g. res1 file 0x76a58). The EDMA3 is
>   very likely what moves audio to and from the codec (McASP). It is used;
>   an effect must not reprogram it, but sharing it needs the driver's
>   channel map first.
> - **Not verified:** the loader details in section 1 (ZDLF parsing,
>   relocation) and the call signature in section 4.

## 1. Loader
- **Magic and extraction:** The firmware checks for a Zoom-specific container format starting with `ZDLF` (hex `0x464c445a`) rather than raw `\x7fELF`. We see strings like `ZDLF\0INFO\0DATA\0BYPASS\0BP` checked at `c012988c` and `c012ab38`. The `ZD2` file is parsed as a container before the ELF sections are processed.
- **Relocations:** The ELF is parsed in memory, and C6000 relocation types (such as `R_C6000_ABS32=1`) are applied to the sections as they are loaded into allocated blocks from the effect heaps.
- **Memory pools:** `g_Task_PreLoad` reads the ZD2 files and processes allocations using the system's `malloc`-style allocators.

## 2. Memory Requests
- **Working-memory allocations:** The firmware reads effect working memory requests from the struct at offsets `[5]`, `[6]`, `[7]`, and `[8]` using `LDW.D1T1 *A4[7], A0` etc. (in the function ending at `c0146e00`).
- **Heaps:** It calls a memory allocator wrapper `c01510e8` (which implements a standard linked-list free-list) to allocate from two separate heaps managed inside the effect context struct (`A10`):
  - **L2 IRAM heap** state is located at offset `+96` of the context struct (`A10[24]`).
  - **SDRAM heap** state is located at offset `+48` of the context struct (`A10[12]`).
  - `[5]` (e.g. reverb fast memory) is allocated from the L2 IRAM heap (`A10+96`).
  - `[6]`, `[7]`, `[8]` are allocated from the SDRAM heap (`A10+48`) via a wrapper `c015f644` that ensures alignment.

## 3. Cache Setup
- **L1/L2 Cache Split:** The cache setup function `c016c480` configures the L1 and L2 caches. It is called at `c016d090` with parameters `(4, 3, 3)` read from the stack, which translates to:
  - **L1P:** `4` -> 32KB Cache / 0KB RAM
  - **L1D:** `3` -> 16KB Cache / 16KB RAM
  - **L2:** `3` -> 128KB Cache / 128KB RAM
  - *Writes to `0x01840000` (L2CFG), `0x01840020` (L1PCFG), `0x01840040` (L1DCFG) happen dynamically via register math starting at `c016c48c`.*
- **MAR Cacheability:** SDRAM cacheability is configured via `Cache_setMar` at `c016c420`. External memory (including the effect SDRAM heap at `0xc0xxxxxx`) is marked cacheable by setting the respective MAR registers (e.g., MAR192 for `0xc0000000`).

## 4. Audio Call Path
- **Process:** The audio path runs in `g_Swi_AudioProcess` processing blocks (16-samples). The firmware loops over effect slots, calling each effect's processing function.
- **Function signature:** The effect's `Dll_<Name>` function populates a parameter table (offset 4, i.e., `[1]` in the context struct). The actual process function pointer is at offset 88 (`[22]`) of this parameter table. 
- **Arguments:** The firmware calls the process function (e.g., `Fx_DRV_NycMuff`) passing:
  - `A4`: The effect context pointer.
  - `B4`: The input audio buffer pointer (residing in fast L2 memory).
  - `A6`: The output audio buffer pointer, typically computed dynamically via `*A4[2]`.

## 5. EDMA
- **Usage:** Disassembly analysis of the entire firmware shows no references to the EDMA3 CC0 base address (`0x01C00000`). While SYSCFG registers (`0x01C14xxx`) are used for initialization/unlocking (e.g., `KICK0R` at `0x01C14038`), EDMA3 does not appear to be utilized by the core audio path or effect framework.
- **Can an effect use it?** Since the firmware does not appear to initialize or heavily use the EDMA3 controller, an effect *might* theoretically configure it manually. However, it would have to set up the CC, TCs, and interrupts entirely on its own, risking system instability or conflicts with other DMA activity (like McASP).

## What this means for writing cheaper effects
- **Table sizes:** Keep fast lookups or time-critical state within the 128KB L2 RAM / 16KB L1D RAM limits, because exceeding this will spill over into SDRAM, incurring a large latency penalty.
- **Working Memory Requests:** If using the effect framework's memory requests, use `[5]` only for essential high-speed buffers (since it draws from the scarce L2 heap). Bulk data like long delay lines (`[6]`, `[7]`, `[8]`) should be stored in the SDRAM heap to prevent OOM errors.
- **DMA:** Hand-rolling EDMA3 for buffer transfers within an effect is not supported natively by the firmware APIs and is risky. Use standard tight loops or C6000 SPLOOPs in L1/L2 memory instead.
