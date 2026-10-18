# G1X Four Live Patch Store Analysis (2026-10-17)

Static analysis of `build/fw/map/main.dis` (stock v2.00 main firmware) and `build/fw/res1_493412.bin`.

## 1. Region Table (offset 0x77C82)

### 1.1 Full decode of the table at file `0x77C82` -> runtime `0xc0183660` (`confirmed`)
File offset `0x77C82` in `build/fw/res1_493412.bin` lies inside AIS section 10 (VMA `0xc0185260..0xc0187024`, size `0x1dc4`, file `0x76998..0x7875c`; raw VMA `0xc0185260 + (0x77C82 - 0x76998) = 0xc018654a`). That section is the TI EABI `.cinit` compressed initialization stream: `auto_init` at `c0163700` walks the `.cinit` record table at `0xc0186ef4..0xc0187024` (`c0163718 MVK 0x6ef4,A3; c0163720 MVK 0x7024,B4; MVKH 0xc0180000`) and dispatches record 0 (`0xc0186ef4`: `src = 0xc0185260`, `dst = 0xc0181b28`) to handler 1 (`0xc0186de0 = c016e1a0 -> c0161e60`, 24-bit RLE decompressor with escape byte `0x1a`).

Because of an RLE run at file `0x77C74` (`1a 05 00`, which expands to five `0x00` bytes: the four bytes of `0x00000000` plus the low byte of `0x00028000`), inspecting file `0x77C82` raw without RLE decompression missed the first two entries (`0x00000000` and `0x00028000`). Decompressed into RAM starting at `0xc0181b28 + 0x1b38 = 0xc0183660`, the table is a **5-entry `(base, size)` array** (`5 * 8 = 40` bytes, `0xc0183660..0xc0183687`):

| Index | Runtime VMA | File offset (`.cinit`) | Raw `.cinit` bytes | Flash base | Size (bytes) | Flash end (excl.) | Purpose |
|---:|---|---|---|---|---|---|---|
| 0 | `0xc0183660` | `0x77C74..0x77C79` | `1a 05 00 80 02 00` | `0x00000000` | `0x00028000` (160 KiB) | `0x00028000` | Boot / update-mode program (`res5`, updater res 142) |
| 1 | `0xc0183668` | `0x77C7A..0x77C81` | `00 80 02 00 00 b0 00 00` | `0x00028000` | `0x0000B000` (44 KiB) | `0x00033000` | Startup splash (`0x200` B) + 50 factory presets (`res2`, updater res 133) |
| 2 | `0xc0183670` | `0x77C82..0x77C89` | `00 30 03 00 00 c0 08 00` | `0x00033000` | `0x0008C000` (560 KiB) | `0x000BF000` | Main firmware AIS image (`res1`, updater res 129) |
| 3 | `0xc0183678` | `0x77C8A..0x77C91` | `00 f0 0b 00 00 10 00 00` | `0x000BF000` | `0x00001000` (4 KiB) | `0x000C0000` | Firmware signature / boot-check sector (`res4`, updater res 139) |
| — | *(omitted)* | — | — | `0x000C0000` | `0x00042000` (264 KiB) | `0x00102000` | **Mutable user/live data region** (omitted from factory CheckSum) |
| 4 | `0xc0183680` | `0x77C92..0x77C99` | `00 20 10 00 00 e0 2f 00` | `0x00102000` | `0x002FE000` (3,064 KiB) | `0x00400000` | Effect flash file system (`res3`, updater res 136) |

The words immediately following at runtime `0xc0183688` (file `0x77C9A`: `0x0000008c, 0xc0164cc0, 0xc0164d20, 0xc0164d44, 0xc0133f28`) are **not** part of this table: they are the ELF dynamic loader's `EM_C6000` (`0x8c`) machine-handler descriptor referenced at `c01235f0` (`MVK 0x3688,A4; MVKH 0xc0180000,A4`).

**Instruction evidence for `0xc0183660` consumer (`confirmed`):**
`c0165e2c` computes the 16-bit byte sum over all 5 static flash regions in `0xc0183660..0xc0183687` and stores the result in `B14[21]` (`0xc0184e00 + 21*4 = 0xc0184e54`, read by `c0165d80`):
```
c0165e38  MVK.S1   0x3660,A10
c0165e40  MVK.L1   5,A0
c0165e42  MV.L1    A0,A11
c0165e44  MVKH.S1  0xc0180000,A10   ; A10 = 0xc0183660, A11 = 5 regions
c0165e48  MV.L1    A10,A4
c0165e4a  LDW.D1T2 *A4[0],B4        ; B4 = region base
c0165e4c  CALLP.S2 0xc0165db0,B3    ; accumulate region byte sum in 4 KiB blocks via c01454f4 -> c0165d88
c0165e4e  LDW.D1T1 *A4[1],A6        ; A6 = region size (byte offset +4)
c0165e50  ADD.L1X  4,B15,A4         ; A4 = &sum on stack
c0165e54  ADD.L1   8,A10,A10        ; next 8-byte (base, size) entry
c0165e68  LDHU.D2T2 *+B15[2],B0     ; low 16 bits of sum (byte offset +4)
c0165e70  STW.D2T2 B0,*+B14[21]     ; store at 0xc0184e54
```


## 2. Live Store Format (Boot/Select Load & Save/Store)

## 3. SysEx `45`/`46` Handlers & Full SysEx Dispatch Table

## 4. Factory Reset Copy Routine (Factory -> Live)

## 5. Recommendation
