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

### 2.2 Per-Patch `PTCF` Record Format & 904-Byte (`0x388`) In-RAM Unpacked Struct (`confirmed`)
- **Live DataStore records `0..49` are 736-byte (`0x2E0`) `PTCF` records (`confirmed`):**
  Every live patch stored in DataStore records `0..49` uses the exact same 736-byte (`0x2E0`) `PTCF` chunked binary layout as the 50 factory preset records in `0x028000` (`recon/08`).
  - **Validator (`c01312c4`, `confirmed`):** `c01312c4(ptcf_ptr)` checks only three structural invariants — no CRC or checksum exists inside `PTCF`:
    1. Leading 4-byte magic `"PTCF"` (`0xc01810f2` at `c01312dc..c01312ec`).
    2. Presence of chunk tag `"EDTB"` (`0xc01810f7` at `c01312fa..c013130e`) within `ptcf_ptr[+0x04]` (`active_length`, loaded at `c01312ce LDW *A10[1],A11`) via chunk walker `c01311f0`.
    3. Presence of chunk tag `"PPRM"` (`0xc01810fc` at `c0131312..c0131320`) within `active_length`.
  - **Blank `"empty"` `PTCF` constructor (`c0130ab4`, `confirmed`):** If a live record is unwritten (`0xFF`-filled) or fails validation during unpack (`c0131680..c013168e`), `c0130ab4(dst_ptcf)` zeros 736 bytes (`c0130ac0..c0130ad8`: `92 * 8 = 736`), writes `"PTCF"` at `+0x00`, `slot_count = 5` at `+0x0C` (`c0130af0`), `target_bits = 0x20` at `+0x10` (`c0130afc..c0130b02`), patch name `"empty"` (`0xc01818a8` at `c0130b04..c0130b14`) at `+0x1A..+0x23`, a 200-byte `"TXJ1"` chunk, a 200-byte `"TXE1"` chunk, a 120-byte (`5 * 24`) `"EDTB"` chunk, and a 12-byte `"PPRM"` chunk with `volume = 100` (`c0130da0`), then computes `active_length` at `+0x04` (`c0130df0`).
- **Pack (`c0130e04`) & Unpack (`c013150c`) between 736-byte `PTCF` and 904-byte (`0x388`) in-RAM struct (`confirmed`):**
  At runtime, active and edited patches are held in a **904-byte (`0x388` = `113 * 8`) unpacked structure**:

| Unpacked Offset | Size | Field | Evidence (`c013150c` unpack / `c0130e04` pack) |
|---|---:|---|---|
| `+0x000..+0x1A3` | `420` B (`5 × 84` B) | 5 effect slots (`84` B = `21` words each: `+0x00` enable `u32`, `+0x04` effect ID `u32`, `+0x08..+0x53` 19 unpacked parameter `u32`s) | `c0131484` unpacks each 24 B `"EDTB"` entry into 84 B (`c01315a4..c01315bc`, stride `0x54` at `c01315b2`) using bitfield table `0xc017f648` (`c015f260`); `c0130db4` packs 84 B -> 24 B (`c015eff0`) |
| `+0x1A4..+0x347` | `420` B (`5 × 84` B) | Reserved slots `5..9` (zeroed; max 10-slot schema shared with larger ZDL pedals) | `c0131518` zeros `113 * 8 = 904` B (`c0131518 MVK 113,A6; SHL A6,3,A6`) |
| `+0x348..+0x377` | `48` B (`12` words) | Unpacked `"PPRM"` parameters (`+0x348` [`105*8`] = Rhythm/Looper bitmask, `+0x364` [`217*4`] = patch volume `0..120`, `+0x368` [`109*8`] = current slot cursor `0..4`) | `c0131468` unpacks 12 B `"PPRM"` into `+0x348` (`c01315f8 MVK 105,A0; SHL A0,3,A0`) via table `0xc0180660`; `c0130df8` packs `+0x348` -> 12 B `"PPRM"` |
| `+0x378..+0x381` | `10` B | ASCII patch name (10 chars, not null-terminated) | `c0131624` (`MVK 111,B0; SHL B0,3,B0` = `+888` = `+0x378`) copies 10 B from `PTCF+0x1A`; `c0130ea4` copies `+0x378` -> `PTCF+0x1A` |
| `+0x384..+0x385` | `2` B (`u16`) | `num_slots` (clamped to `5` on G1X Four by `11806466..11806492`) | `c0131538` (`MVK 225,B0; SHL B0,2,B0` = `+900` = `+0x384`) loads `PTCF+0x0C` (`u32`) and stores `u16` at `+0x384` |

  When packing (`c0130e04(A4=dst_ptcf, B4=src_904B, A6=prev_ptcf)`), if `prev_ptcf` is non-NULL (`c0130ecc`), `c0130ee0..c0130f94` copies existing `"TXJ1"` and `"TXE1"` description chunks from `prev_ptcf` into `dst_ptcf` (or emits empty 8-byte `"TXJ1\0\0\0\0"` / `"TXE1\0\0\0\0"` headers from `0xc0181518` / `0xc0181520`), packs `num_slots * 24` bytes of `"EDTB"` (`c0130fa4..c0131080`) and 12 bytes of `"PPRM"` (`c0131084..c01310dc`), and updates `dst_ptcf[+0x04] = active_length` (`c0131118`).

### 2.3 Boot Initialization, Patch Selection Load Path, and Edit/Store Save Path (`confirmed`)
- **In-RAM Patch Buffers & State Variables (`confirmed`):**
  - `B14[99]` (`0xc0184f8c`): `uint32_t g_current_patch_idx` (`0..49`, active patch number).
  - `0xc00fc498..0xc01053d7` (`50 × 736` = `36,800` B): **Factory preset RAM mirror** (`g_factory_ptcf_mirror[50][736]`), populated once at boot by `c015d7e0` (`c015d7f8 CALLP c01454f4` reading `0x9014` = `36,884` B from SPI flash `0x028000` into `0xc00fc298`, placing `0x028000 + 0x200` at `0xc00fc498`; indexed by `c016d240(idx)` -> `0xc00fc498 + 736 * idx`).
  - `0xc01191a0` (`736` B) & `0xc0119498` (`736` B): Scratch `PTCF` buffers used during patch load (`11807614`) and pack/save (`c0131144..c0131168`).
  - `0x11811598..0x1181191f` (`904` B): **Working unpacked patch (`g_working_patch_904`)** — live edited state of the current patch.
  - `0x11811920..0x11811ca7` (`904` B): **Saved baseline unpacked patch (`g_saved_patch_904`)** — snapshot of `0x11811598` taken on patch load (`11807670`) or save (`c012f7c8`); compared against `0x11811598` by `c01317c4` (904 B `memcmp`) and `c0131740` / `118062b4` (active-parameter dirty check) to detect unsaved edits.
  - `0x11811ca8..0x11811fd7` (`840` B = `105 × 8` B): **Active DSP slot table** (`10 × 84` B), copied from the first 840 bytes of `0x11811598` by `11807310` (`11807350..11807360`).
- **Boot Sequence (`c015d428` -> `c01342ac`, `confirmed`):**
  1. `c015d488`: Calls `c015d7e0`, reading the entire factory preset flash sector (`0x028000`, `0x9014` B) into `0xc00fc298` (`PTCF` array at `0xc00fc498`) and verifying the header strings `"G3Xn"`/`"G3X"`/`"G1 FOUR"`/`"G1X FOUR"` (`0xc0180fd8..0xc0180feb` at `c015d818..c015d974`) and `preset.bin` CRC32 (`c0160acc`).
  2. `c015d498`: Calls `c0136a18` (`datastore_boot_init`). **If `c0136a18` returns `7` (neither Bank 0 at `0x0C0000` nor Bank 1 at `0x0E1000` has a valid header), `c015d4a4` automatically calls `c0137204()` (formats Bank 0 & Bank 1) and `c015d4ac` calls `c01409d8(1, 1)` (copies all 50 factory presets from `0xc00fc498` into live DataStore records `0..49` without any user prompt!).**
  3. `c01342ac`: Calls `c0131294()`, which reads 4-byte DataStore record `51` (`c0131296 MVK 51,A4; CALLP c016f510 -> 118092a0`; defaults to `0` if `>= 50`), stores it into `B14[99]` (`c01342b0 STW A4,*+B14[99]`), and calls `c012f878(-1, 1, 0)` (`c01342b4`) to load the active patch.
- **Loading Patch N into Active Memory (`c012f878` -> `118075e4` -> `1180738c`, `confirmed`):**
  When selecting a patch (`c0134838 STW A0,*+B14[99]` then `c0134864` / `c0134874 CALLP c012f878`) or at boot:
  1. `c012f878(A4=patch_idx, B4=prev_patch_idx, A6=flag, B6=notify_flag)` calls `c016f5b0` (`118075e4`).
  2. If `0 <= patch_idx < 50` (`11807600..11807610`), `11807624` calls `11806258(patch_idx, 0xc01191a0)` -> `118092a0` to read the 736 B `PTCF` record from the live DataStore (`0x0C0000` / `0x0E1000`) into `0xc01191a0`. (If `patch_idx < 0`, e.g. `-1` at boot, `11807638` calls `c016f730` -> `1180b06c` to read `B14[99]` first.)
  3. `11807664` calls `1180738c(0xc01191a0, patch_idx, prev_patch_idx, flag, notify_flag)`:
     - If `prev_patch_idx != -1` and AUTO SAVE (`1180b800` -> `c01317c4`) is enabled (`118073b4..118073e6`), copies the old `0x11811598` (904 B) to stack and saves it to `prev_patch_idx` via `1180b760` (`c012f74c`) at `118075a8`!
     - `118073f4`: Calls `1180b7e0` (`c013150c(0x11811598, 0xc01191a0)`), unpacking the 736 B `PTCF` into `0x11811598` (`904` B).
     - `118074b0`: Calls `11806450(0x11811598)` to sanitize slot count (`<= 5`), effect IDs (`c0140220` / `c012b180`), and volume (`<= 120`, default `100` at `11806232..11806242`), then loads the 5 effect `.ZD2` binaries (`11807564 CALLP 118063c8`) and copies `840` B (`105 * 8`) into `0x11811ca8` (`1180757a CALLP 11807310`).
  4. `11807688`: Copies all 904 bytes (`113 * 8`) from `0x11811598` into the clean baseline buffer `0x11811920`.
  5. `11807690`: Calls `1180b720` (`c0130a80(patch_idx)`), writing the new 4-byte `patch_idx` to **DataStore record `51`** so the selection persists across power cycles.
- **Saving an Edited Patch (`AUTO SAVE` vs. Manual `STORE` / `SWAP`, `confirmed`):**
  - **Low-level pack-and-write (`c0131138` / `c0131188` -> `c0131128`, `confirmed`):**
    1. `c0131138(A4=dst_idx, B4=unpacked_904_ptr, A6=src_text_idx)` calls `c016f720` (`11806258(src_text_idx, 0xc0119498)`) at `c0131154` to read the existing 736 B `PTCF` from DataStore into `0xc0119498` (so `"TXJ1"`/`"TXE1"` chunks are preserved).
    2. `c0131160`: Calls `c0130e04(0xc01191a0, unpacked_904_ptr, 0xc0119498)` to pack the 904-byte struct into `0xc01191a0`.
    3. `c013116c`: Calls `c0131128(dst_idx, 0xc01191a0)` -> `c016be58` -> `c016be20(dst_idx, 0xc01191a0, 1)`:
       - `c016be28`: Calls `c016ec90` (`11809224`), which acquires semaphore `B14[177]`, copies 736 bytes into `0x118123a8`, and stores `dst_idx` at `0x11812688`.
       - `c016be4c`: Calls `c016d0c0` (`c0155ac0(*B14[179], 1)`), waking the `DataStore` task (`c016d340`), which calls `c016ecb0` (`1180933c` -> `11809160`) to write the 24-byte descriptor and 736-byte `PTCF` payload to SPI flash (`0x0C0000` / `0x0E1000`).
  - **Auto-Save path (`c0134a00` & `118075a8`, `confirmed`):** When a parameter is edited, `c0134a80` checks `c016f3d0` (`118060e4`, AUTO SAVE setting at `0x11812f74 + 0x10`) and `c01317c4` / `c0131740` (904 B dirty comparison between `0x11811598` and `0x11811920`), arming the save timer (`c0155314`). When the timer fires (`c0134a00`) or the user switches patches (`118075a8`), `c012f7a4` (`c0134a28`) checks `!c0127fe0()` (`*B14[27] == 0`, i.e., not in Handy Guitar Lab PC-Edit mode), calls `c012f74c(*B14[99], 0x11811598)` -> `c0131188` to write `0x11811598` to DataStore record `B14[99]`, and copies `0x11811598` -> `0x11811920` (`c012f7d4`, `113 * 8 = 904` B).
  - **Manual UI `STORE` / `SWAP` path (`c0138ca4..c0138d88`, `confirmed`):**
    - UI state `7` (Manual `STORE` to `dst_idx`): `c0138d4c` updates `B14[99] = dst_idx`, `c0138d68` calls `c0131138(dst_idx, 0x11811598, src_idx)`, and `c0138d78` calls `c012f878(dst_idx, -1, 1, 1)` (which also updates record `51`).
    - UI state `8` (`SWAP` between `B14[99]` and `other_idx`): `c0138d08` reads `other_idx`'s 736 B `PTCF` into stack (`B15+8`), `c0138d24` saves `0x11811598` into `other_idx` via `c0131138`, and `c0138d30` writes `other_idx`'s old `PTCF` into the original patch slot via `c0131128`.

## 2.4 Spot-check of Argon's report (Sonnet, 2026-10-17)

Picked the claims most load-bearing for everything that follows (if `118092a0` were wrong, all of
section 2.3's "loading/selecting a patch reads the live DataStore" claims would be wrong too) and
recomputed two pieces of arithmetic Argon flagged as the error-prone kind.

- **`118092a0` really is the live-DataStore record reader, not the factory mirror (`confirmed`, no error found).**
  Disassembled it directly instead of trusting the call chain: `118092e8 MVK.S1 0x1ff0,A5; 118092ec MVKH.S1
  0x11810000,A5` forms `A5 = 0x11811ff0` (Argon's cached `data_flash_addr` array), `118092f2 LDW.D1T1 *A5[A4],A4`
  loads the cached pointer for `record_idx` (`A4`), and `118092fa CMPEQ A4,-1` branches to a blank-record
  path (`11809300..1180930c`, `A10=5`) only when that slot has never been written. The non-blank path at
  `11809310` forms `B1 = 0x11810000 | 0x9be8 = 0x11819be8` (Argon's record-size table) and calls `1180b390`
  with the record's byte count. No path in this function touches `0xc00fc498` (the factory-preset RAM
  mirror) or flash `0x28000`. This matters for section 3 below: it means the SysEx `46` download handler,
  which calls this same function, reads the *live* store, not the factory region, contrary to the
  hardware-log's current working theory (see 3.3).
- **`c01409d8`'s factory->live copy loop recomputed arithmetically (`confirmed`, no error found) — see
  section 4. `50` iterations x one record each, bounded by `c0140a00 MVK.S1 50,A0; c0140a02 CMPLT.L1
  A1,A0,A0` where `A1 = idx+1` (`c01409f8`), so the loop body runs for `idx = 0..49` inclusive: correct,
  matches Argon's "50 live patches" record count.
- **Arithmetic recheck, section 1.2 bank table:** `0x000C0000 + 0x00021000 = 0x000E1000` (bank 0 end) and
  `0x000E1000 + 0x00021000 = 0x00102000` (bank 1 end) both check out against Argon's stated end addresses.
  **Arithmetic recheck, section 2.1 compaction budget:** `36 + 53*24 + 50*736 + 20 + 4 + 4` = `36 + 1272 +
  36800 + 20 + 4 + 4 = 38136`, matching Argon's stated `38,136` B. **Record-size-table recheck, section 2.1:**
  `0x11819be8 + 50*4 = 0x11819be8 + 0xC8 = 0x11819cb0`, matching Argon's stated address for record 50's size
  entry. No arithmetic errors found in the three cells checked.

No error found in any of the three claims spot-checked. (Not exhaustive: only the claims most load-bearing
for sections 3-5 below were checked; the rest of Argon's report was not independently re-verified.)

## 3. SysEx `45`/`46` Handlers & Full SysEx Dispatch Table

### 3.1 Byte-level SysEx receive state machine and command classifier (`confirmed`)
The MIDI receive task entry (`c0129118`, per `recon/15`) feeds each received byte through a running-status
parser at `c0129118..c012932c` (handles system-common/real-time bytes 0xF6/0xF7, the SysEx-start byte 0xF0 =
240, and a special 5-byte `F0 52 00 <model> 52 F7` "PC mode" toggle recognized inline at `c0129218` /
`c0129242` via direct `CMPEQ ...,82` checks — this is the brief's `52 00 6e 52` sequence, handled *before*
reaching the generic command table, which is why it is not in the dispatch table below).

For a general SysEx message, each data byte after the Zoom manufacturer-ID byte (`0x52`) is staged into
`B14[164..168]` and, for the byte immediately after the manufacturer/model header, the raw **command byte**
is cached at runtime address **`0xc0183b60`** (confirmed write site `c0127c40..c0127cec`, a two-mode
store/classify helper; confirmed read site below).

**The command-byte classifier is `c0127cf4` (`confirmed`):**
```
c0127d08  MVK.S1 0x3b60,A7 ; MVKH.S1 0xc0180000,A7      ; A7 = 0xc0183b60
c0127d10  LDHU.D1T1 *A7[0],A5                            ; A5 = cached command byte
c0127d14  CMPLTU.L1 0x9,A5,A0 ; [!A0] BNOP 0xc0127d4c,5  ; A5<=9  -> jump table @0xc0183b74 (indirect branch, not decoded further)
c0127d1a..28         A5-40 <=7 (A5 in 40..47)  -> jump table @0xc0183b9c (indirect branch, not decoded further)
c0127d2a  MVK 69,A0 ; CMPEQ A5,A0,A0 ; [A0] BNOP 0xc0127da2,5   ; A5==69  (0x45) -> CALLP 0xc01276b4,B3
c0127d30  MVK 70,A0 ; CMPEQ A5,A0,A0 ; [A0] BNOP 0xc0127d94,5   ; A5==70  (0x46) -> CALLP 0xc0127558,B3
c0127d36  MVK 96,A0 ; CMPEQ A5,A0,A0 ; [A0] BNOP 0xc0127d88,5   ; A5==96  (0x60) -> CALLP 0xc012c914,B3
c0127d40  MVK 100,A0 ; CMPEQ A5,A0,A0 ; [A0] BNOP 0xc0127d78,5  ; A5==100 (0x64) -> CALLP 0xc016f760,B3 (tail-jumps to 0x11803010)
c0127d48  BNOP 0xc0127f58,5                                     ; else: return without dispatch (message silently ignored)
```
**Correction note for future readers of this file:** an earlier pass by this agent misread the branch
targets at `c0127d2e`/`c0127d3a` (swapped 0x45 and 0x60's targets). The table above was re-derived
address-by-address from `grep -n "^c0127d" build/fw/map/main.dis` with explicit line numbers and is
`confirmed`; the mapping **0x45 -> `c01276b4`, 0x46 -> `c0127558`, 0x60 -> `c012c914`, 0x64 -> `0x11803010`**
is the one trust.

Everything not in this table (including raw Program Change and the `64 12` "current-patch upload" the
brief says is ignored) falls through to `c0127d48`'s unconditional return: **confirmed, the firmware
silently drops any command byte it does not recognize** — matches the brief's "ignored, no reply" note.

### 3.2 `0x46` (download) handler: reads the *live DataStore*, not the factory region (`confirmed`)
`c0127558(A4=byte, B4=stage 0..5)` is a byte-position state machine. Stages 0-4 store the raw byte at
`B14[112..117]`; stage 5 combines all five into a 35-bit value via nested `MPYLI` by 5 then 10
(`c01275ac..c01275e4`, the same `(((b0*128+b1)*128+b2)*5+b3*10+b4)`-style formula Zoom's protocol uses to
encode bank+location as one index) and checks it against 50:
```
c01275e4  CMPLT.L1X A0,B1,A0        ; A0 = (combined_index < 50)
c01275e6  [!A0] BNOP 0xc01275f0,5   ; invalid -> NAK
c01277f0  CALLP 0xc0127500,B3 ; A4=10   ; NAK reply, data byte 10 (0x0A)
```
On success, completion is dispatched through the big command-*class* table `c0128e54` (keyed on `B14[38]`,
a value distinct from the raw command byte — see `recon/15`-style per-byte state fields) to the fallback
default case at `c0129000`, which **recomputes the same combined index from `B14[112..117]` again**
(`c0129000..c0129046`, identical `*128+... MPYLI by 10, by 50` arithmetic) and calls `c0129028 -> c0128474`:
```
c0128480  MVK.S1 50,A0 ; CMPLT A1,A0,A0 ; [!A0] BNOP 0xc0128578,5     ; re-validate idx<50
c0128488  LDW *+B14[161],A4 ; CALLP 0xc0150b20,B3                     ; take the MIDI-TX semaphore (c0185084, recon/15)
c0128490  MVK 0x0c78,B10 ; MVKH 0xc0110000,B10                        ; scratch PTCF buffer 0xc0110c78 (SDRAM)
c0128498  MV B10,B4 ; MV A12,A4 ; CALLP 0xc016f720,B3                 ; 11806258(idx, 0xc0110c78) -> 118092a0 : LIVE DataStore read
c01284b0  CALLP 0xc013150c,B3                                         ; unpack 736B PTCF -> 904B struct @0xc0110f70
c01284c8  CALLP 0xc0130e04,B3                                         ; re-pack 904B -> 736B PTCF @0xc0110980
c01284d4..dc  send F0(240), 0x52(82), model byte, then **0x45 (69)** as the reply's own command byte, ...
```
`c016f720` resolves to `11806258`, which (spot-checked above) tail-calls `118092a0` — **the exact same
record reader Argon documented for boot/patch-select in section 2.3**, reading the live DataStore banks at
`0x0C0000`/`0x0E1000` via the cached pointer table `0x11811ff0` and record-size table `0x11819be8`. **This
is `confirmed` by direct instruction trace, and it contradicts the brief's current working premise that
`45`/`46` hit the factory region at flash `0x28000`.** The pedal's reply to a `46` download is itself tagged
command byte `0x45` (`69`), i.e. Zoom's "Patch Data Dump" message is bidirectional: the editor sends it to
*write*, the pedal sends it to *reply to a read request*, same wire format.

### 3.3 `0x45` (upload) handler: validated, but its commit call was not located (`likely` / open)
`c01276b4(A4=byte, B4=stage 0..7+)` is the write-side counterpart: stages 0-4 store the bank/location bytes
(same `B14[112..117]`), stages continue through a second 4-byte sub-stage (`B14[37]` = 1..4) that assembles
a **declared payload length** into `B14[33]`, then validates both fields together:
```
c0127794  ADD.L2 B1,B0,B0            ; B0 = combined bank/location index
c0127796  CMPGT.L1X A0,B0,A0         ; A0 = (50 > B0)      [A0 was MVK'd to 50 at c0127762]
c0127798  [!A0] BNOP 0xc01277c2,5    ; index >= 50 -> CALLP 0xc0127500,B3 ; A4=10   (NAK, same code as 46's)
c012779c  MVK 248,B0 ; SET B0,9,9,B0 ; B0 = 760 (0x2F8)
c01277a2  CMPEQ.L2 B3,B0,B0          ; B3 = declared payload length from the header
c01277a4  [!B0] BNOP 0xc01277b0,5    ; length != 760 -> CALLP 0xc0127500,B3 ; A4=7    (NAK, different code)
c01277a8  BNOP 0xc01277cc,5          ; both valid -> fall through, no NAK
```
**New finding not in Argon's report, `confirmed`:** the `0x45` handler independently validates that the
declared packed length equals exactly **760 bytes (0x2F8)** — matching the brief's "760-byte ZPTC" — and
rejects with a distinct NAK data byte (7 vs. 10) for a bad length vs. a bad bank/location.

Payload bytes (after the 9-byte header) are buffered via a generic 7-bit unpacker at `0xc0110288`
(SDRAM, the same `0xc0110xxx` scratch region the `46` handler's buffers live in — `c0127840..48`, `CALLP
0xc012764c,B3`). **I could not, within budget, trace the final "all 760 bytes received, commit this record"
call.** I exhaustively grepped every caller of the two documented live-DataStore single-record write
primitives (`CALLP.*0xc0131128`, `CALLP.*0xc0131138`, whole-file) and found exactly **7 call sites**, all
already accounted for by Argon's section 2.3 and this report's section 4: AUTO SAVE (`c012f820`), the
manual UI `STORE`/`SWAP` handlers (`c0138ce4`, `c0138d24`, `c0138d30`, `c0138d68`), `c0131138`'s own internal
call into `c0131128` (`c013117a`, `c01311c2`), and the factory-reset copy loop (`c01409f0`, section 4).
**None of these is reachable from the SysEx receive path** (`c0127cf4`/`c01276b4`/the `c0128e54` class
dispatcher) by direct `CALLP` — the commit, wherever it is, is at least one more hop away than I reached.

I also checked whether `0x45` instead writes straight to the SPI flash primitive (`c01453b4`, Argon 2.1A):
every caller of that primitive outside the DataStore module (`c0136xxx`-`c0137xxx`) is a single generic
veneer pair (`c0141e50` erase / `c0141e68` write) with only one caller in the whole SysEx-adjacent code
region (`c012c5b0`), and that caller computes its flash address from two *config/geometry* words at
`0xc01062bc`/`0xc01062c0` shifted into a sector address — consistent with a firmware/version-table write,
not a 736-byte patch record (`likely` unrelated; not chased further).

**What this means (`likely`, not `confirmed`):** `0x46` downloads provably read the live DataStore.
Whatever `0x45` uploads eventually write, it is *not* through either of the two mechanisms this firmware
uses everywhere else to persist a patch (the log-structured DataStore writer, or the raw SPI primitive via
an unrelated veneer). The brief's own hardware observation — a `45` write to location 10 persists across
power cycles, named `"CF test"`, while the on-screen patch list still shows that slot as `Empty` — is
consistent with `45` committing to a *different* persistent copy than the one the boot/UI path and `46`
read from. The single most likely remaining candidate, not reached in this trace, is the factory-preset
mirror (`0xc00fc498` RAM, backed by flash `0x28000`): writing there would (a) explain persistence without
needing AUTO SAVE, (b) explain why `46`'s *current* "CF test" result could still be real even though it
reads the live DataStore (if the live DataStore was reseeded from that same factory image by the boot-time
auto-copy in section 2.3 or by an explicit factory reset, section 4 — which would independently explain the
discrepancy without `45`/`46` needing to disagree about which store they target), and (c) explain why the
on-screen list (presumably reading the live DataStore, like `46`) never saw the owner's `45`-written patch
if it landed in the factory mirror instead. This chain is **plausible and internally consistent, but not
instruction-level `confirmed`** the way section 3.2's `46`-reads-live-DataStore finding is.

### 3.4 Dispatch table (as decoded; gaps marked)
| Command byte | Hex | Handler | Purpose | Confidence |
|---:|---|---|---|---|
| 69 | 0x45 | `c01276b4` | Patch upload (bank/location + 760B packed `ZPTC`); validates index<50 and length==760; NAK via `c0127500` (codes 10 / 7); final commit call not located | handler+validation `confirmed`, commit target open |
| 70 | 0x46 | `c0127558` -> (class 0 fallback) `c0129000` -> `c0128474` | Patch download; validates index<50; reads **live DataStore** via `11806258`/`118092a0`; replies as command `0x45` | `confirmed` |
| 96 | 0x60 | `c012c914` | Unknown; 7-bit-unpacks a short received field, sends an ACK (`c01274cc`); calls `c0141d80`/`c0142028`/`c0141f14`-family effect-parameter routines (not patch-store related) | handler address `confirmed`, purpose `guess` |
| 100 | 0x64 | tail-jump to `0x11803010` | Sub-dispatches on a further byte; this is the brief's `64 13` (current-patch dump, works) / `64 12` (current-patch upload, ignored) family; sub-opcode split not decoded | entry point `confirmed`, sub-dispatch `guess` |
| 82 | 0x52 | handled inline in the byte-receive state machine (`c0129218`/`c0129242`), *before* reaching `c0127cf4` | `F0 52 00 <model> 52 F7` "PC mode on/off" 5-byte toggle | `confirmed` (presence/position), semantics per brief |
| 0-9 | — | indirect jump table at `0xc0183b74` (`A7[A5]`) | not decoded | `guess` |
| 40-47 | 0x28-0x2F | indirect jump table at `0xc0183b9c` (`(A5-40)*4 + 0xc0183b9c`) | not decoded (possibly SDS/firmware-transfer family, unexplored) | `guess` |
| anything else | — | `c0127d48`: return, no dispatch | silently ignored (matches brief's "ignored" PC/`64 12` notes) | `confirmed` |

No command byte in this table matches a "reload/select-patch-from-UI" opcode distinct from `45`/`46`/`64`;
if one exists it is inside the undecoded 0-9 or 40-47 jump tables.

## 4. Factory Reset Copy Routine (Factory -> Live) (`confirmed`)

`c01409d8(A4=select_patch0_and_notify_flag?, B4=notify_flag)` is the exact routine Argon's section 2.3 named
(called from boot as `c01409d8(1,1)` when `c0136a18` finds neither DataStore bank valid) and is also the
routine an explicit on-pedal factory reset almost certainly reaches (not independently verified — no caller
other than the boot path at `c015d4ac` was found by grepping `CALLP.*0xc01409d8`, so **the menu-driven
"Factory Reset" UI action was not traced to this address and remains unconfirmed** as the same code path;
it is `likely` given there is no other factory->live copy routine in the file).

```
c01409d8  CALLP 0xc016e020,A3                         ; take lock
c01409e4  MVK 0,A10                                   ; idx = 0
c01409e8  CALLP 0xc016d240,B3                         ; factory_ptr = &factory_mirror[idx]  (0xc00fc498 + 736*idx, backed by flash 0x28000)
c01409f0  MV A10,A4 ; MV factory_ptr,B4 ; CALLP 0xc0131128,B3   ; **live-DataStore single-record write**, dst_idx=idx, src=factory_ptr (same primitive Argon's 2.3 AUTO SAVE/STORE path uses)
c01409f8  ADD 1,A1,A10(effectively) ; CMPLT A1,50,A0 ; [A0] BNOP 0xc01409e8,4   ; loop idx = 0..49
c0140a18  CALLP 0xc0130a80,B3                          ; write DataStore record 51 (current patch index) = 0
c0140a24  [!A11] BNOP 0xc0140a2c,5 ; CALLP 0xc01369d0,B3  ; conditional notify (only if B4 arg != 0)
c0140a2c  CALLP 0xc016e000,A3                          ; release lock
```

**Confirmed, directly answers the brief's task 4:** the factory->live copy is a 50-iteration loop, one
record at a time, reading an already-`PTCF`-formatted 736-byte record straight from the factory mirror
(`c016d240`, Argon 2.3) and handing it to **the same `c0131128` live-DataStore single-record writer** that
AUTO SAVE and the manual UI `STORE`/`SWAP` actions use (Argon 2.3) — not a raw bulk flash copy, and not a
separate code path. It then resets the "current patch" system record (51) to patch 0. This is strong
independent confirmation that `c0131128`'s descriptor/payload format (section 2.1) is the one true format
for a live patch record: the factory-reset path, the AUTO SAVE path, and the manual STORE path all converge
on it.

## 5. Recommendation

**Preferred: (b) an update-mode stage that writes a freshly-formatted bank image directly into the live
region (`0x0C0000`, bank 0, size `0x21000`), built from Argon's `confirmed` section 2.1/2.2 format.** This is
the only one of the three options with a fully `confirmed`, CRC-free, byte-exact target format already in
hand, and the project already has the tooling pattern for it (`tools/make_fs_restore_updater.py` already
patches an arbitrary flash region via a modified updater; `recon/08`/`docs/CF_STOCK_IMAGE_2026-10-15.md`-style
image builders already assemble `PTCF` records). Concretely:

1. Build `N` 736-byte `PTCF` records (one per generated test patch) satisfying the only three structural
   checks `c01312c4` enforces (Argon 2.2): leading `"PTCF"` magic, an `"EDTB"` chunk and a `"PPRM"` chunk
   both present within the declared `active_length` at offset `+0x04`. No CRC exists anywhere in this
   format (Argon 2.1, confirmed no-checksum finding, and independently confirmed here: the 50-record
   factory->live copy in section 4 moves these records verbatim with no checksum step).
2. Lay out bank 0 exactly as Argon's section 2.1 template: 36-byte header at `+0x00` with the **active**
   byte pattern (`+0x00`=`aa`x12, `+0x0C`=`00`x8, `+0x14`=`00`x8, `+0x1C`=`ff`x8), then one 24-byte
   directory descriptor per record growing up from `+0x24` (`[+0x00]=0x7fffffff`, `[+0x04]=record_idx`,
   `[+0x08]=data_flash_addr`, `[+0x0C]=0xbfffffff`, `[+0x10]=0xdfffffff`, `[+0x14]=0x00000000` — all four
   stage markers set, i.e. write it as already-fully-committed, not as an in-progress log entry), and the
   736-byte payloads packed down from `+0x21000`. Include system records 50/51/52 (record 51 = the desired
   boot-selected patch index, 4 bytes) the same way. Leave bank 1 (`0x0E1000`) fully erased (`0xFF`) — an
   all-`0xFF` bank already reads as "standby" per Argon's header template, so it needs no construction.
3. This is a **static flash-image edit**, not a firmware code change and not a SysEx session: lower risk
   than (c), and unlike (a) it does not depend on resolving section 3.3's open question (where `45` actually
   commits), because it writes the live region directly and bypasses the SysEx path entirely.

**Not recommended as the primary path: (a) a `45` SysEx sequence.** Section 3.3 shows the `45` handler is
reachable and validates correctly, but this agent could not confirm, within budget, that it commits to the
live DataStore `46`/boot/UI read from — and the brief's own hardware log (a `45` write persists but the
on-screen list still shows the slot `Empty`) is itself evidence it may not. Using it as the bench's patch
loader risks writing to the wrong region.

**Not recommended: (c) a firmware hook.** Strictly more code-change risk than (b) for no format benefit,
since (b)'s format is already fully `confirmed` and (b) reuses an existing, already-tested patching
toolchain (`make_fs_restore_updater.py`-style).

**Pedal test (for the owner/user to run — this agent touched no hardware):**
1. Before building anything: on the **current** hardware, send one `46` download for a bank/location whose
   content is already known from the current firmware's factory image (e.g. location 10), and diff the
   736-byte reply against that image's record 9. If they match exactly, that is consistent with the live
   DataStore currently holding a factory-reseeded copy (section 3.3's working theory) rather than `46`
   reading flash `0x28000` directly — useful confirmation before touching anything, and it is read-only.
2. Flash the update-mode image with bank 0 rewritten per steps 1-2 above. Power on **normally** (no
   button held — the boot-time auto-reseed in section 2.3 only fires when the bank header is *invalid*;
   this image's header must read as valid so it is *not* overwritten by that auto-copy on first boot).
3. Confirm normal boot (no stuck logo). On the LCD, open the patch-select screen and confirm the `N` test
   patches show their real names at their intended slots (not `Empty`, not stale factory names).
4. Select one, confirm audio reflects its effect chain, power-cycle, and re-check both the LCD and a `46`
   read-back for persistence.
5. Run `tools/ua_bench.py` / `docs/CF_BENCH_2026-10-17.md`'s bench against the new patches.

STATUS: done
