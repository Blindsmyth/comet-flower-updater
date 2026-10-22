# FW RND F5: Label column width data
## Status
done

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

### Finding 3: Column character capacity limits and parameter label pixel width metrics
- **Claim**:
  1. With a fixed advance of 6 px per character, character capacity across requested column widths is:
     - **24 px**: 4 characters (cell width 24 px; ink width 23 px).
     - **30 px**: 5 characters (cell width 30 px; ink width 29 px).
     - **31 px** (standard 4-column pitch): 5 characters (cell width 30 px; ink width 29 px). 6 characters require 36 px (overflows by 5 px).
     - **32 px**: 5 characters (cell width 30 px; ink width 29 px). 6 characters require 36 px (overflows by 4 px).
     - **42 px** (standard 3-column pitch for multi-slot effects, $128 / 3 \approx 42.6$ px): 7 characters (cell width 42 px; ink width 41 px). 8 characters require 48 px (overflows by 6 px).
     - **64 px** (2-column half-screen pitch): 10 characters (cell width 60 px; ink width 59 px).
  2. Parameter label widths for CF Rotary (`effects/rotx/manifest.json`):
     - All 4 labels (`Speed` 5 ch / 30 px, `Depth` 5 ch / 30 px, `Ramp` 4 ch / 24 px, `Mix` 3 ch / 18 px) fit strictly within 30, 31, 32, and 42 px columns without truncation or overlap.
  3. Parameter label widths for CFM Pre (`effects/cfm_pre/manifest.json`):
     - Current manifest (post-F4 re-layout):
       - 1 label is 5 ch (`Level` = 30 px): fits 31 px and 42 px.
       - 1 label is 6 ch (`Dyn On` = 36 px): overflows 31 px by 5 px; fits 42 px.
       - 2 labels are 7 ch (`Dyn Out`, `Muff On` = 42 px): overflow 31 px by 11 px; fit 42 px exactly.
       - 8 labels are 8 ch (`Dyn Sens`, `MuffSust`, `MuffTone`, `Muff Vol`, `MistRate`, `MistRang`, `MistColr`, `Mist Mtx` = 48 px): overflow 31 px by 17 px; overflow 42 px by 6 px.
     - Original manifest (pre-F4):
       - 8 labels were 9 ch (54 px cell / 53 px ink): overflowed 31 px by 23 px; overflowed 42 px by 12 px.
  4. Longest stock label `D57:D421`:
     - 8 characters: 48 px cell width (47 px active ink). Overflows a 31 px column by 17 px; overflows a 42 px column by 6 px.
- **Evidence**:
  - Script `build/fw_rnd/F5/label_widths.py` and output `build/fw_rnd/F5/label_widths_report.txt`.
  - Manifests `effects/cfm_pre/manifest.json` and `effects/rotx/manifest.json`.
- **Confidence**: Confirmed.

## Answers

### (1) Memory dump of 0xc0181508
- **Answer**: The 256 bytes at `0xc0181508` contain 4-column LCD layout geometry tables, language tags, and glyph descriptors. Words 0..3 (`[17, 48, 79, 110]`) are the center X coordinates for a 4-column display across the 128 px screen (column pitch 31 px). There are zero memory pointers in the 256-byte block.
- **Can a firmware patch change it?**: Yes. The data lives in AIS section `0xc016f780` in SDRAM/flash.
- **Patch site + plan + risk**:
  - Patch site: Flash/file offset `0x75490` in `build/fw/res1_493412.bin` (mapped to load address `0xc0181508`).
  - Plan: Modify words 0..3 to alter column center positions.
  - Risk: High. The table is referenced by multiple UI renderers (`c012dca4`, `c012e1f8`, `c012e268`), so patching affects other system screens.

### (2) Glyph advance widths of the 5x7 font (c011d4d8)
- **Answer**: Strictly fixed at **6 pixels per character** (monospace: 5 px pattern + 1 px blank separator) for all printable characters (`A-Z`, `a-z`, `0-9`, space, `.`, `:`). Special control characters `0x09` (`\t`) advance 3 px and `0x0c` (`\f`) advance 5 px.
- **Can a firmware patch change it?**: Yes, but difficult. The 6-px increment is hardcoded as an immediate operand in the rendering loop and centering function.
- **Patch site + plan + risk**:
  - Patch site: Instruction `c011d524` (`ADD.L1 6, A22, A22`, file offset `0x217a0`) and centering multiplier `c013a30c` (`MPYLI.M2 3, B0, B1:B0`, file offset `0x2e588`).
  - Plan: Implementing proportional spacing requires replacing the hardcoded `ADD.L1 6` with an advance table lookup per character code and rewriting centering math.
  - Risk: High. `c011d4d8` is called by at least 13 subsystems (tuner, settings, popups, looper, edit screen).

### (3) Column capacity table and parameter label pixel widths
- **Answer**:
  - **Column capacities**:
    | Column Width (px) | Max Chars (Cell 6px) | Max Chars (Ink-only 6n-1) | Max Width Occupied (px) | Notes |
    |---|---|---|---|---|
    | 24 | 4 | 4 | 24 | Sub-column / narrow field |
    | 30 | 5 | 5 | 30 | Narrow 4-column |
    | 31 | 5 | 5 | 30 | Stock 4-column pitch (128 px / 4) |
    | 32 | 5 | 5 | 30 | 4-column alternate pitch |
    | 42 | 7 | 7 | 42 | Stock 3-column pitch (128 px / 3) |
    | 64 | 10 | 10 | 60 | 2-column half-screen |

  - **CF Rotary labels (`effects/rotx/manifest.json`)**:
    | Index | Label | Chars | Cell Width (px) | Ink Width (px) | Fits 31 px? | Fits 42 px? |
    |---|---|---|---|---|---|---|
    | 0 | `Speed` | 5 | 30 | 29 | YES (1 px margin) | YES (12 px margin) |
    | 1 | `Depth` | 5 | 30 | 29 | YES (1 px margin) | YES (12 px margin) |
    | 2 | `Ramp` | 4 | 24 | 23 | YES (7 px margin) | YES (18 px margin) |
    | 3 | `Mix` | 3 | 18 | 17 | YES (13 px margin) | YES (24 px margin) |

  - **CFM Pre labels (`effects/cfm_pre/manifest.json`, current manifest)**:
    | Index | Label | Chars | Cell Width (px) | Ink Width (px) | Fits 31 px? | Fits 42 px? |
    |---|---|---|---|---|---|---|
    | 0 | `Dyn Sens` | 8 | 48 | 47 | NO (+17 px) | NO (+6 px) |
    | 1 | `Dyn Out` | 7 | 42 | 41 | NO (+11 px) | YES (0 px margin) |
    | 2 | `Dyn On` | 6 | 36 | 35 | NO (+5 px) | YES (6 px margin) |
    | 3 | `MuffSust` | 8 | 48 | 47 | NO (+17 px) | NO (+6 px) |
    | 4 | `MuffTone` | 8 | 48 | 47 | NO (+17 px) | NO (+6 px) |
    | 5 | `Muff Vol` | 8 | 48 | 47 | NO (+17 px) | NO (+6 px) |
    | 6 | `MistRate` | 8 | 48 | 47 | NO (+17 px) | NO (+6 px) |
    | 7 | `MistRang` | 8 | 48 | 47 | NO (+17 px) | NO (+6 px) |
    | 8 | `MistColr` | 8 | 48 | 47 | NO (+17 px) | NO (+6 px) |
    | 9 | `Muff On` | 7 | 42 | 41 | NO (+11 px) | YES (0 px margin) |
    | 10 | `Mist Mtx` | 8 | 48 | 47 | NO (+17 px) | NO (+6 px) |
    | 11 | `Level` | 5 | 30 | 29 | YES (1 px margin) | YES (12 px margin) |

  - **Longest stock label (`D57:D421`)**:
    - Length: 8 characters.
    - Cell Width: 48 px; Ink Width: 47 px.
    - Fits 31 px: NO (overflows by +17 px).
    - Fits 42 px: NO (overflows by +6 px).
- **Can a firmware patch change it?**:
  Not necessary. Effect labels can be sized to fit column constraints directly in `manifest.json`. For 4-column displays, labels should be $\le 5$ characters. For 3-column displays (2-slot effects), labels should be $\le 7$ characters.
- **Patch site + plan + risk**:
  N/A (data handled at effect manifest level, zero risk).

## Not checked / open leads
- Physical LCD visual clipping behavior when labels overflow column width (whether text clips at column boundary or visually overlaps adjacent columns).




## Answers

## Not checked / open leads
- Full execution flow of c012dca4 / c013a2d8 caller and table index decoding (assigned to RE jobs).
