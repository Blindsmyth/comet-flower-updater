# FW RND F5: Label column width data
## Status
running (step 3: column width capacity table and manifest label widths)

## Findings

### Finding 1: Memory dump of 0xc0181508 reveals 4-column center X coordinates (pitch 31 px), language tags, and glyph data — no pointers
- **Claim**:
  1. The 256 bytes at `0xc0181508` reside in AIS section `0xc016f780` (size `0x123a4`), mapped to file offset `0x75490` in `build/fw/res1_493412.bin`.
  2. The table contains **zero** pointers (no 32-bit values fall in `0xc0xxxxxx` or `0x118xxxxx`).
  3. The first four 32-bit LE words at `0xc0181508` are `[17, 48, 79, 110]` (`0x00000011, 0x00000030, 0x0000004f, 0x0000006e`). These represent the **center X pixel coordinates** of the 4 screen columns across the 128-pixel LCD. The column spacing (pitch) is exactly 31 pixels: $48 - 17 = 31$, $79 - 48 = 31$, $110 - 79 = 31$.
  4. In `c012dca4=ui_row_render_name` (`main.dis:46485..46505`), the column index `col % 4` is used to load `*B4[B0]` (`LDW.D2T1 *B4[B0], A0`) where `B4 = 0xc0181508`. The loaded center coordinate `A0` is passed to `c013a2d8=ui_text_draw_centered_6px` (`main.dis:63700..63720`), which computes `X_start = center_x + 1 - (len * 3)`, centering a 6-px-per-char string around the column center.
  5. The remaining 256 bytes contain additional coordinate tables, language tags, and icon/glyph descriptors:
     - `0xc0181518`: ASCII `"TXJ1"` (`0x314a5854`) followed by `0x00000000` (Text Japanese 1 tag, referenced at `c013102c`).
     - `0xc0181520`: ASCII `"TXE1"` (`0x31455854`) followed by `0x00000000` (Text English 1 tag, referenced at `c0131044`).
     - `0xc0181528`: `[9, 41, 72, 103]` (`0x09, 0x29, 0x48, 0x67`), a 4-column X offset table with pitches 32, 31, 31 px (referenced at `c012e360`).
     - `0xc0181548`: `[17, 48, 79, 110]` (referenced at `c016a990`).
     - `0xc0181558`: `[17, 48, 79, 110]` (referenced at `c0167208`).
     - `0xc0181568`: `[18, 50, 79, 110]` (referenced at `c01632c4`).
     - `0xc0181578..0xc0181607`: GFX box/glyph descriptors and bitmap data (referenced at `c0128de4`, `c01394a8`, `c015e48c..c015e4f8`).
- **Evidence**:
  - Script `build/fw_rnd/F5/dump.py` and output `build/fw_rnd/F5/dump_c0181508.txt`.
  - Disassembly `build/fw/map/main.dis:46485..46510` (`c012dd40..c012dd68`) and `build/fw/map/main.dis:63705..63725` (`c013a2f8..c013a320`).
  - Reference index `build/fw/map/refs.txt:c01815*`.
- **Confidence**: Confirmed.

### Finding 2: Glyph advance of the 5x7 font drawn by c011d4d8 is strictly fixed 6 px (monospace) for all printable characters
- **Claim**:
  1. The 5x7 font table starts at address `0xc01787e0` in flash/SDRAM (file offset `0x6c768` in `build/fw/res1_493412.bin`). The printable ASCII range `0x20..0x7e` begins at `0xc01788a0` (`0xc01787e0 + 0x20 * 6`).
  2. Each character cell consists of 6 contiguous bytes (1 vertical column of 8 bits per byte; 7 rows active). Columns 0..4 contain the 5-pixel glyph pattern; column 5 is always `0x00` (blank 1 px inter-character spacing).
  3. The string renderer `c011d4d8` loops over the input string and advances the X coordinate in register `A22`:
     - Printable characters: line `c011d524` executes `ADD.L1 6, A22, A22` unconditionally. The advance is **strictly fixed at 6 pixels per character**. It is NOT proportional.
     - Exception 1: ASCII `0x09` (`\t`) advances 3 px (`c011d54c: ADD.L1 3, A22, A22`).
     - Exception 2: ASCII `0x0c` (`\f`) advances 5 px (`c011d534: ADD.L1 5, A22, A22`).
  4. Character advance values:
     - `A-Z`: **6 px** fixed (5 px ink + 1 px blank space).
     - `a-z`: **6 px** fixed (5 px ink + 1 px blank space).
     - `0-9`: **6 px** fixed (5 px ink + 1 px blank space).
     - ` ` (space): **6 px** fixed (`00 00 00 00 00 00`, 0 px ink + 6 px space).
     - `.` (period): **6 px** fixed (`00 60 60 00 00 00`, 2 px ink + 4 px space).
     - `:` (colon): **6 px** fixed (`00 36 36 00 00 00`, 2 px ink + 4 px space).
  5. The centering wrapper `c013a2d8=ui_text_draw_centered_6px` independently confirms fixed 6 px pitch: it multiplies character count by 3 (`MPYLI.M2 3, B0, B1:B0` at `c013a30c`) to compute the half-width before subtracting from the column center coordinate.
- **Evidence**:
  - Disassembly `build/fw/map/main.dis:22798..22860` (`c011d4d8..c011d554`).
  - Disassembly `build/fw/map/main.dis:22744..22765` (`c011d438..c011d470`: base `0xc01787e0`, index `char * 6`).
  - Binary inspection of glyph bytes in `build/fw/res1_493412.bin` at offset `0x6c768 + char * 6`.
  - Disassembly `build/fw/map/main.dis:63700..63725` (`c013a2d8`).
- **Confidence**: Confirmed.



## Answers

## Not checked / open leads
- Full execution flow of c012dca4 / c013a2d8 caller and table index decoding (assigned to RE jobs).
