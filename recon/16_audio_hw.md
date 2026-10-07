# 16 — Audio hardware and the cache patch study (firmware map part 4)

Helper: Antigravity (Claude Opus 5.5). Static analysis only of `build/fw/map/main.dis`.
Scratch: `build/agy5/`. Confidence tags: confirmed / likely / guess.

> **Review by Claude (2026-10-07).** Antigravity on Claude Opus 5.5; the run
> ended at Antigravity's weekly Claude quota (resets ~2026-10-13) after two
> committed findings: codec init decoded (44.1 kHz PLL from 19.2 MHz, codec
> = clock master, 32-bit I2S, both ADCs used via MIC3L/R, no AGC, no DAC
> biquads) and the peripheral pointer block (I2C0, codec 0x18, McASP0/1,
> EDMA, 44100). Not yet checked by Claude in detail. Unfinished: the audio
> path (McASP/EDMA), the cache patch study, the CPU clock.

## 1. Codec setup (TLV320AIC3101 over I2C)

**Driver (confirmed).** I2C0 (base `0x01C22000` from `0x1181340c`), slave 0x18
(`0x11813414`), 100 kHz, transfers by EDMA (event 25 = I2C0 TX):
- `0x118088d0` i2c_write(buf, len, dev) (L2 code; far stub `c016f200`): copies buf to
  `0xc87d9000`, programs ICMDR (`*A4[9]`, base+0x24), EDMA ch 25, ICCNT, ICSAR from table `0x11813410`.
- `c013dca0` **codec_write(reg, val)**: `STB A0,*+B15[8]` (reg) / `STB B0,*+B15[9]` (val) /
  `CALLP 0xc016f200 || MVK 2,B4`.
- Shadow of both pages: `0xc010a780` (page 0) and `0xc010a800` (page 1), byte 0 = current page.
  `c013dce0` select_page(p) (write reg 0), `c013dd2c` **setbits(page, reg, bits)**,
  `c013de18` **clrbits(page, reg, bits)** — both read-modify-write the shadow and skip the
  I2C write if unchanged.
- `c013e1ac` codec_reset: `memcpy(0xc010a780, 0xc0182940, 0x100)` (table = datasheet reset
  values for page 0 + page 1) then setbits(0, 1, 0x80) (soft reset).
- Only caller of the whole init: `c016e160`: `MVK 0xffffac44,A4 / MVKH 0,A4 / CALLP 0xc013e4f4`
  -> **codec_init(44100)** (called from `c015d4e4`).

**Every register the firmware writes (confirmed: these are the only callers of
setbits/clrbits, all inside `c013df0c..c013e5f0`, all with page = 0).**
Order of `codec_init` at `c013e4f4`:

| # | call site | write | AIC3101 meaning |
|---|---|---|---|
| 1 | `c013e4fa` | reset (`c013e1ac`) | shadow := reset table; R1 = 0x80 soft reset |
| 2 | `c013e500` | R82, R92 low 7 bits := 118 (`c013e3b8(118)`) | DAC_L1->LEFT_LOP / DAC_R1->RIGHT_LOP volume -59 dB (anti-pop) |
| 3 | `c013e504` | R8 \|= 0xC0 | BCLK and WCLK are **outputs: codec is the I2S master** |
| 4 | `c013e50c` | R9 \|= 0x30 | I2S mode (bits 7:6 = 00), **32-bit word length**, BCLK = 64*fs |
| 5 | `c013e514` | `c013e1ec(44100)`: R8 &= ~0xC0, R3 &= ~0x80, R7 &= ~0x60, R3 P=1, R11 R=1, R4=0x10 (**J=4**), R5=0x6E, R6=0x00 (**D=7040**), R8 \|= 0xC0, R3 \|= 0x80, then delay `c0158980(10)` | PLL on, P=1 R=1 K=4.7040 from 19.2 MHz MCLK: fs = 19.2e6*4.704/2048 = **44100.0 Hz** exactly. (48000 / 96000 branch: J=5 D=1200, K=5.12 -> 48000.0; 96k also sets R7 dual-rate bits 0x60. Unused.) |
| 6 | `c013e518` | `c013e114(1)`: R19 \|= 0x04, R22 \|= 0x04 | **left AND right ADC powered up** |
| 7 | `c013e520` | `c013e0d8(1)`: R37 \|= 0xC0 | left and right DAC powered up |
| 8 | `c013e526` | R40 \|= 0x40 | output common mode 1.5 V |
| 9 | `c013e52c` | R14 \|= 0xC0 | output driver AC-coupled config bits (HP drivers otherwise unused) |
| 10 | `c013e536` | R42 \|= 0x9E | pop reduction: power-on delay 800 ms, ramp step 4 ms, CM from bandgap |
| 11 | `c013e540` | `c013e304(0)`: R17 = (R17 & 0x0F) \| 0<<4 = 0x0F | **MIC3L -> left ADC, 0 dB** (MIC3R not to left) |
| 12 | `c013e544` | `c013e2c4(0)`: R18 = (R18 & 0xF0) \| 0 = 0xF0 | **MIC3R -> right ADC, 0 dB** |
| 13 | `c013e548` | R7 \|= 0x0A | left DAC <- left slot, right DAC <- right slot; fsref bit 7 left 0 |
| 14 | `c013e554` | R82 \|= 0x80 | DAC_L1 routed to LEFT_LOP/M |
| 15 | `c013e564` | R92 \|= 0x80 | DAC_R1 routed to RIGHT_LOP/M |
| 16 | `c013e56a` | `c013e080(1)`: R86 \|= 1, R93 \|= 1 | LEFT_LOP/M and RIGHT_LOP/M powered |
| 17 | `c013e570` | R14 \|= 0xC0 (again) | — |
| 18 | `c013e57a` | `c013e3e4(0)`: R15, R16 &= ~0x80 | ADC PGAs unmuted, **gain 0 dB** (bits 6:0 stay 0) |
| 19 | `c013e582` | `c013e440(0)`: R43, R44 &= ~0x80 | DACs unmuted, digital volume 0 dB |
| 20 | `c013e586` | `c013e498(0)`: R86, R93 \|= 0x08 | line outputs unmuted, level 0 dB |
| 21 | `c013e58a` | `c013e3b8(0)`: R82, R92 vol := 0 | DAC->LOP 0 dB |

`c013e594` codec_mute(flag) runs steps 20,19,18,16,7 in reverse (mute/power down).

**Registers never written (confirmed by absence of any call):** R2 (fs = fsref/1),
R10 (data offset 0), **R12 (ADC high-pass off, DAC de-emphasis off, DAC digital effects
filters OFF)**, R26–R35 (**AGC off**), R25 (MICBIAS off), LINE1/LINE2 routing, HP/MONO
drivers, R43/R44 volume bits, and **nothing on page 1** (biquad / de-emphasis / ADC-HPF
coefficients stay at reset defaults).

**Answers.**
- *Second ADC channel*: **both ADCs are powered and both are routed** (MIC3L -> left,
  MIC3R -> right, 0 dB PGA). Whether the DSP uses the right-slot samples is in §2.
  (confirmed for the codec side)
- *Built-in DAC biquads*: **not used** (R12 bits 3/1 never set, page 1 never written).
  A patch could use them: the driver already has everything needed — `setbits(1, reg, v)`
  works for page 1 (shadow at `0xc010a800`, select_page in `c013dce0`). A patch would
  write the 2×(N0,N1,N2,D1,D2) 16-bit coefficients to page 1 regs 1–20 (left) / 27–46
  (right) and then set R12 bit 3 (left) / bit 1 (right) (effects filter enable). Easiest
  hook: replace the final `CALLP 0xc013e3b8` at `c013e58a` with a call to a small routine
  placed in free space. Note TI requires the filter to be disabled while coefficients
  are written. (likely — patch untested)
- Note (guess): R7 bit 7 (fsref = 44.1 kHz) is left 0; per the datasheet this bit only
  matters for the internal processing blocks (e.g. de-emphasis), which are off.


## 2. Audio path (McASP + EDMA)

(in progress)

## 3. Cache patch study

(in progress)

## 4. CPU clock (PLLC0)

(in progress)

## Findings log

### F1. Peripheral base pointers live in cinit-initialised L2 data (confirmed)
Code never builds I2C/McASP/EDMA/PLL bases with MVK/MVKH; they are loaded from
a pointer block in L2 RAM that is initialised by the EABI cinit table.
- auto_init at `c0163700`: `MVK 0x6ef4 / MVKH 0xc0180000,A3` and `MVK 0x7024,B4`
  -> cinit table `c0186ef4..c0187024` (8-byte load/run pairs); handler table
  `c0186ddc` = {`c0167860` zero, `c016e1a0` RLE24 (core `c0161e60`, delimiter
  byte first; `delim,n<4` = n delimiters; `delim,n,v` run; `delim,0,hi,lo` long
  run; `delim,0,0,0` end), `c016e180` copy}.
- Decoder: `build/agy5/cinit.py` (overlay used by `build/agy5/mem.py`).
- Key RLE record: load `c01868f4` -> run `0x1180bd40`, 0x7761 bytes (L2 .data/.far).
- Decoded pointer block (run addresses):
  `0x1181329c`=0x01D00000 (McASP0 cfg), `0x11813314`=0x01D04000 (McASP1 cfg),
  `0x1181340c`=0x01C22000 (I2C0), `0x11813414`=**0x18** (codec 7-bit address),
  `0x11813418`=100000 (I2C bus 100 kHz), `0x11813450/54/58`=0x01C00000/0x01C02000/0x01C02200
  (EDMA3 CC0 + shadow regions), `0x11813494`=0x01C00000, `0x11813468`=0x01C14000 (SYSCFG),
  `0x1181346c`=0x01C10000 (PSC0), `0x11813470`=0x01E27000 (PSC1), `0x11812fec`=0x01C41000 (SPI0),
  `0x118133bc`=**0xAC44 = 44100** (sample rate), `0x118133b0`=0x0124F800 (19.2 MHz),
  `0x118133c4`=0x01C20000 (TIMER64P0).

## Codex continuation (2026-10-07)

### Audio DMA and scheduling

### PLLC0 and memory clocks

### On-chip occupancy and cache patch designs

### Risks and staged test plan

Static analysis only; scratch: build/codex6/. Original findings above are preserved.

### C1. Audio ping-pong PaRAM construction (confirmed)
The main McASP0 audio setup is c0153cb8 (TX) and c0153d6c (RX). Both call c016ef60, a veneer to 1180a954. That builder emits the eight EDMA PaRAM words and calls 1180a580 with A4=temporary descriptor, B4=PaRAM index. Evidence: `1180a98a STW A5,*B15[2]` (SRC), `1180a98c SHL A4,16,A0; 1180a990 OR B4,A0,B0` (BCNT:ACNT), `1180a994 STW B2,*B15[4]` (DST), `1180a996 SHL A3,16,A0; 1180a998 OR A0,B3,A0` (DSTBIDX:SRCBIDX), `1180a9a0 EXTU A2,16,16,A0` (LINK), `1180a9a8 MVK 1,B0` (CCNT).

| Direction | PaRAM index | Source | Destination | ACNT / BCNT / CCNT | SRCBIDX / DSTBIDX | LINK |
|---|---:|---|---|---|---|---|
| TX initial | 1 | 11f03630 | 01d00218 | 4 / 32 / 1 | 4 / 0 | 4800 |
| TX ping | 64 | 11f03630 | 01d00218 | 4 / 32 / 1 | 4 / 0 | 4820 |
| TX pong | 65 | 11f036b0 | 01d00218 | 4 / 32 / 1 | 4 / 0 | 4800 |
| RX initial | 0 | 01d02000 | 11f03530 | 4 / 32 / 1 | 0 / 4 | 4840 |
| RX ping | 66 | 01d02000 | 11f03530 | 4 / 32 / 1 | 0 / 4 | 4860 |
| RX pong | 67 | 01d02000 | 11f035b0 | 4 / 32 / 1 | 0 / 4 | 4840 |

Call evidence: TX c0153cf4/c0153d24/c0153d54; RX c0153d98/c0153dc8/c0153df4. `c0153d00 MVK 32,A12`, `c0153d14 MVK 0x4820,A6`, `c0153d2c MVK 0x40,A8`; RX `c0153d84 MVK 0x4840,A6`, `c0153db8 MVK 0x42,A8`, `c0153dc4 MVK 0x4860,A6`. OPT construction at 1180a978..a986 gives TX 0x00101000 (TCC 1, completion interrupt) and RX 0x00100000 (TCC 0, completion interrupt), A-synchronized; stack argument 2 supplies interrupt-enable bit after shifting. Each half is 128 bytes; each direction has two adjacent halves (256 bytes). The 32 transfers are 32-bit words, not 32 stereo sample frames: paired left/right words give 16 frames. Combined with the codec's 44,100 frames/s configuration above, one half spans 16/44100 = 362.812 microseconds, or 2756.25 blocks/s. Stereo framing and the active event/channel mapping are checked separately below.

**C1 arithmetic correction (confirmed):** OPT is TX **0x00101200**, RX **0x00100200**. The stack argument 2 contributes `2<<8 = 0x200` (FWID field), not interrupt enable; B12=1 contributes bit 20 (TCINTEN). Evidence: `1180a978 SHL B1,8,B1; 1180a97a OR B0,B1,B0; 1180a980 SHL B0,4,B0; 1180a984 OR A0,B0,A0; 1180a986 SHL A0,8,A0`. SYNCDIM remains zero (A-sync). This supersedes the two OPT values and stack-argument interpretation in C1.

### C2. Stock cache split is explicitly initialized (confirmed)
Startup c0159da0 disables interrupts, writes L2CFG=3, L1DCFG=3, L1PCFG=4, reads back, and restores CSR. Constants are c0181728=3, c0181724=3, c0181720=4 (AIS res1 offsets 0x756b0, 0x756ac, 0x756a8). Evidence: `c0159dc4 LDW *A4[0],A3; c0159dc8 MVKH 0x01840000,B6; c0159dd0 STW A3,*B6[0]`; `c0159dd4 ADDAD B6,8,B5` gives 01840040; `c0159de2 STW B7,*B5[0]`; `c0159de8 MVK 0x20,A3; c0159dec SUB B5,A3,A3; c0159df4 STW A4,*A3[0]` gives 01840020. Thus the configuration words are patchable data, not guessed MMIO literals. Hardware mode encoding (TI SPRUFK5A) makes this 128 KiB L2 cache, 16 KiB L1D cache, 32 KiB L1P cache; the remaining L1D 16 KiB is already occupied by framework/state/DMA storage. [TI megamodule reference](https://www.ti.com/lit/pdf/sprufk5), sections on L2CFG/L1PCFG/L1DCFG. A concrete 16 KiB L1P cache experiment changes **c0181720 from 4 to 3**, freeing the lower L1P half as SRAM; it does not itself relocate any effect code (design: likely, untested).

### C3. RX completion schedules the audio Swi (confirmed chain; symbol name likely)
EDMA descriptor copier 1180a580 writes 32 bytes to **01c04000 + 32*PaRAM_index** (`1180a5a4 SHL B0,5,B0; 1180a5ae SET B0,14,14,B0; 1180a5b4 CALLP 1180ba70`). Thus PaRAM 0/1 are 01c04000/01c04020; linked sets 64..67 are 01c04800..01c04860. Initialization c01516e0 registers TCC0 callback **c0151a90**, TCC1 callback **c0151a8c** via c015c94c (table **11813130**); c0151720 enables completion interrupt 0 with c015c9a0(0,1), while (1,0) skips enabling completion interrupt 1. c015c9a0 sets DRAE1 bit at 01c00348, and conditionally writes IESR at **01c02260**.

Dispatcher **1180a5d0** reads IPR at **01c02268**, walks set bits, calls `11813130[index]` with A4=index, and acknowledges at **01c02270**. Evidence: `1180a5e4 MVK 0x2268,A0`; `1180a61a LDW *A6[A7],A0; 1180a624 B A0; 1180a62c MV A10,A4`; `1180a638 MVK 0x2270,A2; 1180a646 STW A0,*A4[0]`. RX callback: `c0151a94 CALLP c0164240; c0151a98 LDW *B14[141],A4`. TX callback c0151a8c simply returns 0. B14[141]=c0185034 contains **c0182a40**, whose function pointer at +8 is **11818ba0**, priority 15 at +20 and mask 0x8000 at +24. The adjacent Swi object c0182a70 has function 1180a5d0, priority 14. c0164240 is the Swi-post path. The audio routine calls processing stages, then five slot callbacks from 118133e0 (`11818c0c LDW *B11[B10],B5; 11818c16 BNOP B5; 11818c28 CMPGT 5,B10,B0`). This identifies the high-priority object as the audio-processing Swi; string c0172e6e is `g_Swi_AudioProcess` (name association likely, no symbol table).

Important disassembly completeness correction: main.dis marked AIS section **118164c0..11818edf** as data, so its audio code appeared only as `.word`. Rewrapped all AIS sections as executable and ran only the permitted dis6x, producing build/codex6/main-all.dis. The recovered 11818ba0 disassembly above is real code, not an inferred function from word values. No original firmware or prior helper scratch was changed.

### C4. Software selects the inactive DMA half; both input slots reach DSP (confirmed)
RX unpack routine **11818b20** reads current PaRAM0 DST at **01c0400c** and compares it with **11f035b0**. If DMA is still writing the lower half, it reads the upper half; otherwise it reads the lower half. `11818b28 LDW *A3[0],A3; 11818b3c CMPGTU B7,A3,B0; 11818b4c [B0] MV B7,A5; 11818b50 LDNDW *A5++[1],A7:A6`. It processes 16 doublewords (`11818b30 MVK 16,B4`, pipelined loop) into planar integer buffers **11f03730** and **11f03770** (64 bytes each). Both A6 and A7 are multiplied and stored, so the second ADC word is not discarded here. 11818360 converts those integer buffers into float processing buffers including **11f037b0** and **11f037f0**, matching recon/14's two 16-float channels.

TX pack **11818aa0** similarly reads current PaRAM1 SRC at **01c04024**, compares with **11f036b0**, and writes the inactive half. Evidence: `11818aa8 LDW *A3[0],A4; 11818ad4 CMPGTU B5,A4,B0; 11818ad8 [B0] MV B5,A8; 11818b18 STNDW A5:A4,*A8++[1]`. Inputs are planar buffers **11f038b0** and **11f038f0**, 16 integers each. Audio Swi calls RX unpack at 11818bb0 and TX pack at 11818c64. Ping-pong phase is derived from live DMA addresses, not a blind software toggle. This needs the processing deadline to hold: an overrun can cause stale/overwritten blocks and does not gain safety from the address comparison alone. All four DMA halves are explicitly zeroed with length 128 at c0165c90/c0165ca8/c0165cc0/c0165cd0.

### C5. PLL setup lives in the AIS header, before executable startup (confirmed bytes; clock inference likely)
Both res1 and res5 start with the same AIS function-execute command: file **0x04=5853590d**, **0x08=00030005**, arguments **0x0c=12000202**, **0x10=000501f9**, **0x14=00000003**. The next command at 0x18 invokes function 2 with four arguments: **0001c620, 109129c8, 30080005, 00000768**. Reproduction: build/codex6/ais.ps1 parses section-load/function-execute/jump-close records read-only. These are command data, not DSP instructions, so no fictitious PLLC STW address is assigned.

[TI C6747/45/43 bootloader SPRABB1C](https://www.ti.com/lit/an/sprabb1c/sprabb1c.pdf), Appendix D, identifies function 5 as combined PLL/boot-peripheral-clock configuration: PLLM=0x12, POSTDIV=0, PLLDIV3=2, PLLDIV5=2; CLKMODE=0, PLLDIV7=5, lock count=0x1f9. Function 2 configures EMIFB SDCR, SDTIM1, SDTIM2, SDRFC in that order. Do not use the different C6748 AIS function numbering or argument layout.

[TI SPRUH91D](https://www.ti.com/lit/ug/spruh91d/spruh91d.pdf), PLLM field definition, gives multiplier=PLLM+1 (some illustrative clock tables confusingly label the actual multiplier as a register setting). With the firmware's **19.2 MHz** reference (initialized 118133b0=0124f800), the intended PLL output/core SYSCLK1 is **19.2 MHz * 19 / 1 = 364.8 MHz**. SYSCLK2 = **182.4 MHz**; SYSCLK3 and SYSCLK5 = **121.6 MHz**; SYSCLK4 = **91.2 MHz**; SYSCLK7 = **60.8 MHz**. Nominal core budget: **132353.741 cycles per 16-frame block**, before interrupts/framework/control work. This is a static intended-clock inference, not a TSCL measurement or proof of the physical oscillator. A 96k-cycle user-load threshold is not the full clock budget.

PLLC0 register targets implied by ROM configuration are PLLM **01c11110=0x12**, POSTDIV **01c11128 ratio=0**, PLLDIV3 **01c1111c ratio=2**, PLLDIV5 **01c11164 ratio=2**, PLLDIV7 **01c1116c ratio=5** (divider enable bits are set by the ROM routine, not included in packed argument bytes). EMIFB peripheral-bus VCLK is SYSCLK2; SDRAM MCLK selection requires CFGCHIP3.EMB_CLKSRC: SYSCLK5 would be 121.6 MHz, DIV4P5 would be **81.0667 MHz**. The mux setting is not established by the PLL header alone. Supporting executable evidence for the 19.2 MHz software reference: c0167440..7448 writes 118133b0; timer/accounting c11809f40..9f4c reads it (address is **11809f40**, without the leading c). No later PLL rewrite has yet been established.
