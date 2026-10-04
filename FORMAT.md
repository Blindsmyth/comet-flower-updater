# Zoom .ZD2 Effect File Format

## Status
Reverse-engineered, partial. Verified against G1X Four effects v1.40/v1.50
and cross-checked with the MS Plus documentation in
[thammer/stomphacks `docs/zd2-format.md`](https://github.com/thammer/stomphacks/blob/main/docs/zd2-format.md).

## Overview
A `.ZD2` file is one effect module: a 128-byte header, tagged blocks
(metadata, icon, text, **the compiled DSP code**), and a 16-byte trailer.
The `DATA` block is a TI C6000 ELF, so a ZD2 *does* define DSP. Custom
effects are possible; see `recon/02_g1x4_abi_comparison.md`.

## Header
| Offset | Length | Field | Type | Notes |
|--------|--------|-------|------|-------|
| 0x00 | 4 | Magic | char[4] | `ZDLF` |
| 0x04 | 4 | Header length | u32le | always 120 (0x78): header size after the 8-byte prefix |
| 0x08 | 4 | Checksum | u32le | `zlib.crc32(file[12:-16]) ^ 0xFFFFFFFF` |
| 0x0C | 4 | Target | u32le | bitfield of pedal families. G1X Four stock: `0x07`; MS Plus: `0x80` (+`0x10` on DIY builds) |
| 0x10 | 73 | ? | bytes | zero on MS Plus DIY; G1X Four stock has `01`/`80` words at 0x10, 0x14, 0x18, 0x28, 0x38 (TODO) |
| 0x59 | 4 | Version | char[4] | e.g. `1.40` |
| 0x5D | 2 | ? | | zero |
| 0x5F | 1 | Group | u8 | equals the top byte of the ID (3 = DRIVE, 6 = MOD, 7 = SFX…) |
| 0x60 | 4 | ID | u32le | patches reference effects by this |
| 0x64 | 11 | Name | padded CString | bytes after the NUL are build-tool garbage |
| 0x6F | 11 | Group name | padded CString | e.g. `DRIVE`, `MODULATION` |
| 0x7A | 6 | ? | | |

## Blocks
Blocks start at 0x80 and tile the file exactly up to the trailer. Each is a
4-byte ASCII tag, a u32le length, then the data.

| Tag | Content |
|-----|---------|
| `ICON` | G1X Four: 1-bpp BMP, 23×30 (182 bytes). MS Plus: colour frame (icons also ship as separate `.ZIC`) |
| `TXJ1` | Japanese description (Shift-JIS) |
| `TXE1` | English description |
| `INFO` | 20 bytes: u32 class (0 normal, 1 EQ, 2 line selector), 12-byte text (`DRVDRIVE`), f32le **dspload** |
| `DATA` | TI C6000 ELF (C6740, EABI, ET_DYN). See *Effect ELF* |
| `PRMJ` | parameter UI descriptions, JSON (Japanese) |
| `PRME` | parameter UI descriptions, JSON (English) |

## Trailer
16 bytes. Non-zero on G1X Four stock and not an MD5 of any block. Zero on MS
Plus DIY builds, which still load, so MS Plus does not verify it. Unknown
on G1 (TODO).

## Effect ELF (summary)
- Entry `Dll_<Name>` fills a struct: `[0]` u8 table entry count, `[1]` parameter
  table pointer, `[3]` image-info pointer.
- Parameter table: 56-byte records. Record 0 is `OnOff` (on/off handler),
  record 1 carries the effect name, the init function and the audio function,
  then one record per knob (name, max, default, edit handler, flags; `0x16` =
  stock VOL curve).
- Image info follows the table: `{width, height, bitmap*}` triples, ending
  with a NULL pointer. G1X Four: screen picture 23×32 or 23×30, category
  icon 20×10, optional add/delete icon 24×22.
- Firmware services through ctx (B4): +160 get_param, +172 memcpy,
  +176 memset (also +12 ramp, +16 smooth per stomphacks). The audio bus is
  `ctx[1]`.
- Only `R_C6000_ABS32`, `ABS_L16`, `ABS_H16` relocations.

Full ABI: stomphacks `docs/zd2-abi.md`.

## References
- [mungewell/zoom-zt2](https://github.com/mungewell/zoom-zt2): container grammar, MIDI install
- [thammer/stomphacks](https://github.com/thammer/stomphacks): ABI, DIY effect build pipeline (MS Plus)
