# Initial Analysis: NYC_MUFF.ZD2

## File Overview
- **File Name:** `samples/NYC_MUFF.ZD2`
- **Size:** 17,440 bytes
- **Type:** Zoom ZDL Effect Module (G1 Four series)

## Header Layout (ZDLF)
| Offset | Length | Field | Value/Sample | Notes |
|--------|--------|-------|--------------|-------|
| 0x00   | 4      | Magic | `ZDLF`       | Followed by `x` (0x78) in this file |
| 0x04   | 4      | Length| 120 (0x78)   | Likely header length |
| 0x08   | 4      | Checksum| `61 e4 56 dd`| CRC32 (Poly: 0x104c11db7) |
| 0x59   | 4      | Version| `1.40`       | ASCII |
| 0x5F   | 1      | Group  | `0x03`       | 3 = Drive/Distortion |
| 0x60   | 4      | ID     | `0x030000D0` | 32-bit ID (LE) |
| 0x64   | 11     | Name   | `NYC Muff`   | Null-terminated ASCII |
| 0x6F   | 11     | GRP Name| `m=DRIVE`    | Metadata tag |

## Tagged Blocks (Preliminary)
- **ICON (0x80):** Bitmap/Icon data for the pedal display.
- **TXJ1 / TXE1:** Description text in Japanese/English.
- **INFO:** Metadata and DSP load factor.
- **PRMJ / PRME:** Parameter definitions (JSON/XML fragments).
- **DATA:** Binary DSP code (TI C6000 ELF).

## Key Strings
- `ZDL_DRV_NYC_Muff.out`: Original build output name.
- `Electro-Harmonix Big Muff Pi`: Model description.
- `TMS320C6x`: Target processor architecture.
- Parameters: `SUSTN`, `Tone`, `BAL`, `VOL`.

## Open Questions
- [TODO] Verify if the `Length` at 0x04 is indeed just the header or the whole ZDL container before sections.
- [TODO] Confirm CRC32 calculation algorithm.
- [TODO] Map all Group IDs (e.g., 1=Dynamics, 3=Drive).

## Prior Art Comparison
Matches `mungewell/zoom-zt2` implementation. The `ZDLFx` magic seen in hex is actually `ZDLF` + a length byte `0x78` (120).
