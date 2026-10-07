# 16 — Audio hardware and the cache patch study (firmware map part 4)

Helper: Antigravity (Claude Opus 5.5). Static analysis only of `build/fw/map/main.dis`.
Scratch: `build/agy5/`. Confidence tags: confirmed / likely / guess.

## 1. Codec setup (TLV320AIC3101 over I2C)

(in progress)

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
