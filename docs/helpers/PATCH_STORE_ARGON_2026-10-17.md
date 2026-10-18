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

### 2.1 Flash erase/write/read primitives & Dual-Bank Log-Structured Container (`confirmed`)

#### A. SPI Flash Primitives (`c01451a0..c0145790`, `confirmed`)
All main-firmware SPI flash operations lock recursive gate `B14[149]` (`c016f160` / `c016d880`) and check only `addr + len < 0x800000` (`1 << 23` = 8 MiB at `c01453e8` and `c014558a`); they do **not** consult `0xc0183660`.
- **Erase granularity (`c0145568`, `confirmed`):** **4 KiB (`0x1000` bytes)** minimum sector size.
  - `c0145568(A4=flash_addr, B4=len)` rejects any `flash_addr` not aligned to 4 KiB (`c01455a0 EXTU.S1 A0,20,20,A0; [!A0] BNOP 0xc01455b6`, else returns `-1`).
  - It issues **4 KiB Sector Erase (SPI opcode `0x20`)** via `c0145270` (`c0145274 MVK 0x0020,B0; STB B0,*+B15[8]`, advancing by `ADDK 4096,A0` at `c0145650`) until `flash_addr` reaches a 64 KiB boundary (`c01455d8 EXTU.S1 A0,16,16,A0`), then issues **64 KiB Block Erase (SPI opcode `0xD8`)** via `c0145378` (`c0145380 MVK 0x00d8,B0; STB B0,*+B15[8]`, advancing by `0x10000` at `c0145658 SET A3,16,16,A3`), and erases any trailing bytes in **4 KiB sectors (`0x20`)** (`(rem + 4095) >> 12` at `c01456f0..c0145724`).
- **Write (`c01453b4(A4=src_buf, B4=flash_addr, A6=len)`, `confirmed`):** splits into 256-byte (`0x100`) page-aligned chunks (`c0145448 EXTU A0,24,24,A1; c0145450 SUB 0x100,A1,A1`) and for each chunk calls `c0145220` (SPI `0x06` WREN), `c01452ac` (SPI `0x02` Page Program), and `c01451a0` (SPI `0x05` RDSR bit-0 WIP poll).
- **Read (`c01454f4(A4=flash_addr, B4=dst_buf, A6=len)`, `confirmed`):** calls `c01451a0` (WIP poll) then `c0145320` (SPI `0x0B` Fast Read with 24-bit big-endian address from `c0145254` + 1 dummy byte).

#### B. Dual-Bank Log-Structured DataStore (`0x000C0000` & `0x000E1000`, `confirmed`)
The live store manages **53 logical records (`record_idx = 0..52`)** across the two `0x21000`-byte (135,168 B = 33 × 4 KiB) banks defined at `0xc0183a50` (Bank 0: `0x000C0000..0x000E0FFF`, Bank 1: `0x000E1000..0x00101FFF`).
- **Record size table `0x11819be8..0x11819cbc` (`53` × `u32`, accessed by `c01371e4`, `c01367a4`, `11809168`, `1180926c`, `11809310`, `confirmed`):**
  - **Records `0..49`** (`0x11819be8..0x11819caf`): **`0x000002e0` (736 bytes)** each — the **50 live patches** (0-indexed: patch 10 is `record_idx = 0`, patch 59 is `record_idx = 49`).
  - **Record `50`** (`0x11819cb0`): **`0x00000014` (20 bytes)** — system/global settings record A.
  - **Record `51`** (`0x11819cb4`): **`0x00000004` (4 bytes)** — system/global settings record B (e.g. current patch index).
  - **Record `52`** (`0x11819cb8`): **`0x00000004` (4 bytes)** — system/global settings record C.
- **36-byte (`0x24`) Bank Header at `bank_base + 0x00..0x23` (`confirmed`):**
  Templates live at `0x11819cc0..0x11819cef`. NOR flash bytes erase to `0xFF` and transition `0xFF -> 0x00` without erase:

| Offset | Size | Standby bank | Active bank | Migrating (old) bank | Template VMA & Evidence |
|---|---:|---|---|---|---|
| `+0x00` | 12 B | `aa` × 12 | `aa` × 12 | `aa` × 12 | `0x11819cc0` (`c0136974`, `c013724c`, checked at `c0136af8`) |
| `+0x0C` | 8 B | `00` × 8 | `00` × 8 | `00` × 8 | `0x11819cd0` (`c01369a0`, `c0137240`, checked at `c0136b28`) |
| `+0x14` | 8 B | `ff` × 8 | `00` × 8 | `00` × 8 | `0x11819cd8` (`c0136944`, `c01372a8`, checked at `c0136ba4`) |
| `+0x1C` | 8 B | `ff` × 8 | `ff` × 8 | `00` × 8 | `0x11819ce8` (`ff`×8) / `0x11819ce0` (`00`×8 written at `c0136834`) |

- **Append-only log & 24-byte (`0x18`) Directory Descriptors (`c0136744`, `11809160`, `confirmed`):**
  Within the active bank (`*0x11813448` = `0` or `1`), **24-byte directory descriptors grow upward** from `bank_base + 0x24` (`*0x11813440` holds the last written descriptor address; initialized to `bank_base + 0x0C` at `c0136860` / `c01372e4` so the first `+24` pre-increment lands at `bank_base + 0x24`), while **4-byte-aligned record payloads grow downward** from `bank_base + 0x21000` (`*0x11813444` holds the lowest written payload address, decremented by `c0136720(record_size, 4)` before each write).
  Each write (`c0136744(A4=record_idx, B4=desc_addr, A6=data_addr, B6=src_buf)`) programs the 24-byte descriptor at `desc_addr` and the payload at `data_addr` in 7 sequential `c01453b4` calls:

| Desc Offset | Size | Value written | Template VMA | Meaning / Stage |
|---|---:|---|---|---|
| `+0x00` | 4 B | `0x7fffffff` | `0x11819cf0` (`c0136758`) | Stage 1: descriptor slot claimed (`c0136f94` boot forward scan key) |
| `+0x04` | 4 B | `record_idx` (`0..52`) | stack `B15+4` (`c013676c`) | Stage 2: logical record ID |
| `+0x08` | 4 B | `data_flash_addr` | stack `B15+8` (`c0136780`) | Stage 3: absolute flash address of payload |
| `+0x0C` | 4 B | `0xbfffffff` | `0x11819cf8` (`c013678c`) | Stage 4: pointer valid (`c0137030` boot `data_cursor` recovery key) |
| *(payload)* | `size` | `src_buf[0..size-1]` | `B6` (`c01367b4`) | Stage 5: `record_size` bytes written to `data_flash_addr` |
| `+0x10` | 4 B | `0xdfffffff` | `0x11819d00` (`c01367c0`) | Stage 6: payload write finished |
| `+0x14` | 4 B | `0x00000000` | `0x11819d08` (`c01367e0`) | Stage 7: record committed (`c0137150` boot directory populate key) |

- **No CRC/checksum in DataStore (`confirmed`):** Neither `c0136744` (writer), `c0136a18` (boot scanner), nor `118092a0` (reader) computes any CRC or checksum over the descriptor or the 736-byte record payload. Validity is determined solely by `desc[+0x14] == 0x00000000`.
- **In-RAM directory & wear-levelling compaction (`11809160`, `c01367f8`, `confirmed`):**
  - `0x11811ff0..0x118120c3` (`53` × `u32`) caches the current `data_flash_addr` for each `record_idx` (`-1` if unwritten).
  - At boot, `c0136a18` scans descriptors forward from `bank_base + 0x24` while `desc[+0x00] == 0x7fffffff` (`c0136f54..c0136fe8`) to set `*0x11813440`, scans backward for the last `desc[+0x0C] == 0xbfffffff` (`c0137000..c0137110`) to set `*0x11813444`, and scans backward from `*0x11813440` to `bank_base + 0x24` (`c013711a..c01371ba`): for each descriptor with `desc[+0x14] == 0x00000000`, if `0x11811ff0[record_idx] == -1`, it sets `0x11811ff0[record_idx] = desc[+0x08]` (latest committed entry wins).
  - On each save (`11809160`), if `(*0x11813440 + 72) > (*0x11813444 - aligned_size)` (`118091a4 ADDAD A0,9,A0; 118091aa CMPGTU A0,A1,A0`), `118091c0` calls `c01367f8` (`1180b3b0` veneer), which marks the current bank migrating (`+0x1C` = `00`×8), copies all non-`-1` records in `0..52` into the standby bank via `0x118120c8`, marks the new bank active (`+0x14` = `00`×8), erases the old bank (`c013696c CALLP c0145568`), formats its standby header (`+0x00` = `aa`×12, `+0x0C` = `00`×8), and flips `*0x11813448`. A freshly compacted bank with all 53 records uses `36 + 53*24 + 50*736 + 20 + 4 + 4 = 38,136` B, leaving `97,032` B (~127 single-patch saves) before the next bank switch.


## 3. SysEx `45`/`46` Handlers & Full SysEx Dispatch Table

## 4. Factory Reset Copy Routine (Factory -> Live)

## 5. Recommendation
