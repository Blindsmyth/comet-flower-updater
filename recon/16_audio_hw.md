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
