# FW RND F5: Label column width data
## Status
running (step 2: glyph advance widths of 5x7 font)

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


## Answers

## Not checked / open leads
- Full execution flow of c012dca4 / c013a2d8 caller and table index decoding (assigned to RE jobs).
