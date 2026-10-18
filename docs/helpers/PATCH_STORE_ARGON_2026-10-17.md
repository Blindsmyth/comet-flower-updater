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

### 1.2 Live patch store region table at file `0x77F69` -> runtime `0xc0183a50` (`confirmed`)
The `0x00042000`-byte gap (`0x000C0000..0x00101FFF`) omitted from `0xc0183660` is described by a separate **2-entry `(base, size)` table** in the same `.cinit` record 0 stream at file `0x77F69..0x77F78`, which decompresses to runtime RAM **`0xc0183a50..0xc0183a5f`** (`2 * 8 = 16` bytes):

| Bank index | Runtime VMA | File offset (`.cinit`) | Flash base | Size (bytes) | Flash end (excl.) | Purpose |
|---:|---|---|---|---|---|---|
| 0 | `0xc0183a50` | `0x77F69..0x77F70` | `0x000C0000` | `0x00021000` (132 KiB = 33 × 4 KiB) | `0x000E1000` | Live DataStore bank 0 (50 patches + 3 system records) |
| 1 | `0xc0183a58` | `0x77F71..0x77F78` | `0x000E1000` | `0x00021000` (132 KiB = 33 × 4 KiB) | `0x00102000` | Live DataStore bank 1 (50 patches + 3 system records) |

Together, Bank 0 (`0x000C0000..0x000E0FFF`) and Bank 1 (`0x000E1000..0x00101FFF`) account for the entire `0x000C0000..0x00102000` (`0x00042000` B = 264 KiB) live patch/settings region.

**Instruction evidence (`confirmed`):**
`c0136a18` (`DataStore` / `MainApp` live-store initializer) loads `0xc0183a50` at `c0136a74..c0136a78`, verifies that the minimum required capacity `A6` fits within both banks' sizes (`*A4[3]` = byte offset `+12` from `0xc0183a48` -> `0xc0183a54` and `0xc0183a5c`, both `0x00021000`), and then reads the 36-byte bank header from each bank's `base` (`0xc0183a50` and `0xc0183a58`):
```
c0136a74  MVK.S1   0x3a50,A0
c0136a78  MVKH.S1  0xc0180000,A0    ; A0 = 0xc0183a50
c0136a82  ADD.L1   A0,-8,A4         ; A4 = 0xc0183a48
c0136a84  MV.L1    A1,A11           ; A11 = 0xc0183a50
c0136a86  MVK.S1   2,A3             ; 2 banks
c0136a88  LDW.D1T1 *A4[3],A0        ; byte offset +12: 0xc0183a54 (bank 0 size), then 0xc0183a5c (bank 1 size)
c0136a8a  CMPGTU.L1 A6,A0,A1
c0136a94  ADD.L1   A4,8,A4          ; advance 8 bytes per bank entry
...
c0136ae8  LDW.D2T2 *B4[0],B0        ; B4 = 0xc0183a50 + 8*bank -> B0 = bank flash base (0x000C0000 or 0x000E1000)
c0136aec  MVK.S1   36,A6            ; 36-byte bank header
c0136af0  CALLP.S2 0xc01454f4,B3    ; flash_read(bank_base, stack_buf, 36)
```


## 2. Live Store Format (Boot/Select Load & Save/Store)

## 3. SysEx `45`/`46` Handlers & Full SysEx Dispatch Table

## 4. Factory Reset Copy Routine (Factory -> Live)

## 5. Recommendation
