# 03 — G1X Four corpus audit (87 installed effects)

Date: 2026-10-04. Source: read-only backup of the owner's G1X Four
(`tools/backup_g1.py`, firmware 2.00 assumed). 114 files: 87 `.ZD2`,
`FLST_SEQ.ZT2`, `GUARDZDL.ZT2`, `G_OUT_EQ.BDL`, 24 rhythm `.raw` samples.
Zero transfer checksum errors (every 512-byte block is CRC-checked on the wire).

## Pedal state
- Storage: ~3.0 MB total, **~8 KB free** (99.7% used). New effects beyond a few
  KB need stock effects uninstalled first.
- `FLST_SEQ.ZT2`: 8502 bytes (same size as MS Plus), 148 entries, **87 installed**.
  The other 61 are listed with `installed=0` and have no file. Groups 1–9 and 11.
  Group 7 (SFX) holds 4 entries, 1 installed (LPROLL3S).

## Invariants (all 87 effects)
| Property | Finding | Consequence for DIY |
|---|---|---|
| Relocations | always ABS32/ABS_L16/ABS_H16 | same as stomphacks |
| `.audio` section | **always empty (NOBITS)**; all code in `.text` | build with `kernel_section: "text"` |
| Entry | `Dll_<Name>` exported in `.dynsym` at `e_entry` in all 87 | export it (`--export`) |
| Target | `0x7` ×65, `0x2` ×20, `0x6` ×2: **bit 0x2 in every one** | use `0x02` |
| Header 0x10 / 0x18 | always `01` / `80` | copy |
| Header 0x58 | `01`, or `02` for double-width effects (1U amps, 47/50-px icons) | **slot count**; `01` |
| Header 0x12, 0x14 (+0x28, 0x38 = 80) | vary in pairs, meaning unknown | leave zero (21 stock effects do) |
| INFO class | 0 (86), 1 (1, the graphic EQ) | 0 |
| INFO text | fixed per group: `DYNDYNMCS`, `FLTFILTER`, `DRVDRIVE`, `AMPAMP`, `CABCAB.`, `MODMOD.`, `SFXSFX`, `DLYDELAY`, `REVREVERB`, `PDLPEDAL` | set from group |
| ICON | 1-bpp BMP, 23×30 (48) or 24×30 (24) = 182 B; double-width 47/50×30 | 24×30 |
| ELF image list | `pic+category+add/del` common; **7 effects have only the 23×30 pic** | single pic is stock-precedented |
| dspload | 9.13 (PDL_VOL) … 89.41 (BGMK1_1U), median 22.8 | gain declares 8 |

## Integrity checks the pedal does NOT seem to make
- **Header CRC:** `MK1_1X12.ZD2` and `MS4X12GB.ZD2` are installed and in use, but their
  stored CRC does not match (verified: no transfer errors). So the pedal does not
  reject a file on a bad CRC. Ours is correct anyway.
- **Trailer:** only 23 distinct trailers across 87 files, shared across unrelated
  effects (16 files share `2923be84…`). It is filler, not a signature. Zeroed in DIY
  builds.

## Open
- Patch DSP budget on the G1X Four (MS-70CDR+: 270 raw). Can be found by stacking
  stock effects until "Process Overflow" and summing their declared loads.
- Meaning of header 0x12/0x14 and the 0x28/0x38 pair.
- Block size / channel count, inferred from the stock SPLOOP code but not confirmed.

## Recovery path
The G1 Four has a hardware firmware-update mode: hold both footswitches while
connecting USB (manual p.57). Zoom's v2.00 updater reinstalls the firmware and its
effect set, so a bad effect or a broken effect list should be recoverable.
Not tested.
