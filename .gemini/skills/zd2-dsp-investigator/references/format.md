# Zoom .ZD2 Patch File Format

## Status
Reverse-engineered, partial. Verified against version 1.40.

## Overview
A `.ZD2` file (ZDL container) consists of a fixed-length header followed by a series of tagged data blocks.

## File Layout

### Header (ZDLF)
| Offset | Length | Field | Type | Notes |
|--------|--------|-------|------|-------|
| 0x00   | 4      | Magic | Char[4] | `ZDLF` |
| 0x04   | 4      | Length| UInt32LE | Header length? (typically 120 / 0x78) |
| 0x08   | 4      | CRC32 | UInt32LE | Checksum (Poly: 0x104C11DB7) |
| 0x18   | 4      | BOffset| UInt32LE| Offset to first block (typically 128 / 0x80) |
| 0x59   | 4      | Version| Char[4] | e.g., `1.40` |
| 0x5F   | 1      | Group | Byte | 3=Drive, 4=Amp, etc. |
| 0x60   | 4      | ID    | UInt32LE | Unique Effect ID |
| 0x64   | 9      | Name  | CString | Effect name (e.g., `NYC Muff`) |
| 0x6D   | 11     | GName | CString | Group tag (e.g., `m=DRIVE`) |

### Tagged Blocks
Blocks start at offset `0x80` (or the value at `0x18`).
Each block starts with a 4-byte Tag followed by a 4-byte Data Length.

| Tag | Description | Notes |
|-----|-------------|-------|
| `ICON`| Effect Icon | Bitmap data |
| `TXJ1`| Japanese Text| Null-terminated description |
| `TXE1`| English Text| Null-terminated description |
| `INFO`| Metadata    | 20 bytes. Last 4 bytes = Float32LE (DSP Load) |
| `DATA`| DSP Binary  | Compiled TI C6000 ELF binary |
| `PRMJ`| Param JSON  | JSON fragment defining parameters |
| `PRME`| Param XML   | XML fragment (redundant to PRMJ?) |

### Footer
The file ends with a 16-byte footer after the last block.

## References
- [mungewell/zoom-zt2](https://github.com/mungewell/zoom-zt2)
