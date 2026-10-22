# CFM Pre Page Re-layout, One Stage Per Page (Job F4)

## Status
done

## Findings

### Finding 1: EDTB Patch Field Bit-Widths and 8-Bit Parameter Capacity
- **Claim**: In Zoom G1/G1X Four EDTB preset records, the 12 parameter fields have bit-widths `[12, 12, 12, 12, 12, 8, 8, 8, 12, 12, 12, 12]`. Fields 6..8 (0-based 5..7: `Muff Vol`, `MistRate`, `MistRang`; or fields 5..7: `MuffTone`, `Muff Vol`, `MistRate`) are restricted to 8 bits (maximum integer value 255). In the re-laid out CFM Pre parameter order, every single parameter across the entire effect has a maximum value of either 1 or 100. Consequently, all parameters placed into the 8-bit fields strictly obey `max <= 255` (specifically `max <= 100`), preventing truncation, bit spill, or preset corruption.
- **Evidence**:
  - `tools/ua_bench.py` line 44: `PARAM_BITS = [12, 12, 12, 12, 12, 8, 8, 8, 12, 12, 12, 12]`.
  - `docs/FW_RND_ANSWERS_2026-10-22.md` lines 85–89: "the EDTB slot entry is 24 bytes with 12 packed fields `[12,12,12,12,12,8,8,8,12,12,12,12]` bits... Note params 6-8 are only 8 bits (max 255)."
  - Manifest inspection: `MuffTone` max = 100, `Muff Vol` max = 100, `MistRate` max = 100, `MistRang` max = 100. All parameters have `max <= 100 <= 255`.
- **Confidence**: Confirmed.

### Finding 2: Parameter Re-layout and Label Length Invariant (≤ 8 Characters)
- **Claim**: The pedal LCD displays 3 parameters per page for 2-slot effects. The 12 parameters have been re-ordered so each of the 4 pages hosts exactly one functional stage: Page 1 = DynaComp, Page 2 = Ram's Head Big Muff, Page 3 = Electric Mistress, Page 4 = Stage switches and master output trim. All parameter labels were shortened to ≤ 8 characters (stock maximum is 8 characters), while preserving all defaults, maximums, and explanations unchanged.
- **Evidence**:
  - Manifest `effects/cfm_pre/manifest.json`:
    - Page 1 (Dyna): `Dyn Sens` (8 ch), `Dyn Out` (7 ch), `Dyn On` (6 ch)
    - Page 2 (Muff): `MuffSust` (8 ch), `MuffTone` (8 ch), `Muff Vol` (8 ch)
    - Page 3 (Mistress): `MistRate` (8 ch), `MistRang` (8 ch), `MistColr` (8 ch)
    - Page 4 (Switches): `Muff On` (7 ch), `Mist Mtx` (8 ch), `Level` (5 ch)
  - Every label length is in the range 5..8 characters, eliminating horizontal label truncation against stock 8-character column boundaries.
- **Confidence**: Confirmed.

### Finding 3: Build Verification, `.text` Size Reduction, and Memory Integrity
- **Claim**: The modified `effects/cfm_pre/` builds cleanly via `tools/build_g1.sh cfm_pre "CFM Pre"`. The `.text` section decreased by 32 bytes (from 29,248 B to 29,216 B). Slot heap usage decreased by 32 bytes (from 39,920 B to 39,888 B), leaving 1,072 bytes free within the 40 KiB (40,960 B) per-slot heap limit (`check_slot_mem.py` passes). Header byte `0x58` remains strictly `2`.
- **Evidence**:
  - `build/CFMPRE.REPORT.md`:
    - Entry: `Dll_CFMPre @ 0x6c60; audio fn Fx_SFX_CFMPre @ 0xc (text)`
    - Sections: `['.const', '.text']; .text 29216 B` (was 29,248 B).
  - `tools/check_slot_mem.py build/CFMPRE.ZD2`:
    - Output: `slot memory: build/CFMPRE.ZD2 uses 39888 of 40960 bytes (1072 free) tight`.
  - Header inspection via `build/fw_rnd/F4/check_zd2.py`:
    - File size: 45,564 bytes (was 45,622 bytes).
    - Header byte `0x58` = `0x02` (confirmed 2 slots).
    - Target byte `0x0c` = `0x02` (G1 family target).
  - Generated header `/c/Users/z/zoomlab/stomphacks/effects/cfm_pre/build/sh_params.h` confirms exact macro correspondence:
    - `SH_PARAM_DYN_SENS` = 3
    - `SH_PARAM_DYN_OUT` = 5
    - `SH_PARAM_DYN_ON` = 6
    - `SH_PARAM_MUFFSUST` = 7
    - `SH_PARAM_MUFFTONE` = 8
    - `SH_PARAM_MUFF_VOL` = 9
    - `SH_PARAM_MISTRATE` = 10
    - `SH_PARAM_MISTRANG` = 11
    - `SH_PARAM_MISTCOLR` = 2
    - `SH_PARAM_MUFF_ON` = 12
    - `SH_PARAM_MIST_MTX` = 13
    - `SH_PARAM_LEVEL` = 14
- **Confidence**: Confirmed.

### Finding 4: Test Suite Results
- **Claim**: Full test suite run (`.venv/Scripts/python.exe -m pytest tests -q`) completed with 333 passed and 1 unrelated failure.
- **Evidence**:
  - Test summary: `1 failed, 333 passed, 146 subtests passed in 67.35s`.
  - The single failure: `FAILED tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx - assert 18464 == 18176` (unrelated RATX slot heap test; unchanged by F4).
- **Confidence**: Confirmed.

## Parameter Layout Table (Old vs New)

| Page | Stage | New Idx | New Label | Old Idx | Old Label | Max | Dflt | Coeff Slot | Generated Macro | Explanation |
|:---:|:---:|:---:|:---|:---:|:---|:---:|:---:|:---:|:---|:---|
| 1 | Dyna | 0 | `Dyn Sens` | 8 | `Dyna Sens` | 100 | 50 | [3] | `SH_PARAM_DYN_SENS` | DynaComp sensitivity / compression ratio. |
| 1 | Dyna | 1 | `Dyn Out` | 9 | `Dyna Out` | 100 | 60 | [5] | `SH_PARAM_DYN_OUT` | DynaComp output level. |
| 1 | Dyna | 2 | `Dyn On` | 10 | `Dyna On` | 1 | 0 | [6] | `SH_PARAM_DYN_ON` | DynaComp stage engage (0=Bypass, 1=Active). |
| 2 | Muff | 3 | `MuffSust` | 0 | `Muff Sust` | 100 | 75 | [7] | `SH_PARAM_MUFFSUST` | Ram's Head Big Muff sustain / fuzz gain. |
| 2 | Muff | 4 | `MuffTone` | 1 | `Muff Tone` | 100 | 50 | [8] | `SH_PARAM_MUFFTONE` | Big Muff tone tilt filter. |
| 2 | Muff | 5 | `Muff Vol` | 2 | `Muff Vol` | 100 | 70 | [9] | `SH_PARAM_MUFF_VOL` | Fuzz output volume. |
| 3 | Mistress | 6 | `MistRate` | 4 | `Mist Rate` | 100 | 35 | [10] | `SH_PARAM_MISTRATE` | Electric Mistress LFO sweep rate. |
| 3 | Mistress | 7 | `MistRang` | 5 | `Mist Rang` | 100 | 70 | [11] | `SH_PARAM_MISTRANG` | Electric Mistress sweep range / depth. |
| 3 | Mistress | 8 | `MistColr` | 6 | `Mist Colr` | 100 | 65 | [2] | `SH_PARAM_MISTCOLR` | Electric Mistress BBD feedback / color. |
| 4 | Switches | 9 | `Muff On` | 3 | `Muff On` | 1 | 1 | [12] | `SH_PARAM_MUFF_ON` | Muff stage engage (0=Bypass, 1=Active). |
| 4 | Switches | 10 | `Mist Mtx` | 7 | `Mist Mtrx` | 1 | 0 | [13] | `SH_PARAM_MIST_MTX` | Mistress Filter Matrix mode (freeze LFO). |
| 4 | Switches | 11 | `Level` | 11 | `Pre Level` | 100 | 70 | [14] | `SH_PARAM_LEVEL` | Preamp master output trim. |

## Binary Comparison Summary

| Metric | Before (Old Layout) | After (New Layout) | Delta | Notes |
|---|---|---|---|---|
| `.text` section size | 29,248 bytes (0x7240) | 29,216 bytes (0x7220) | -32 bytes | Fits well within slot budget |
| `.const` section size | 9,684 bytes (0x25d4) | 9,684 bytes (0x25d4) | 0 bytes | Constant blob + tables unchanged |
| Per-slot heap used | 39,920 bytes | 39,888 bytes | -32 bytes | 1,072 bytes headroom in 40 KiB heap |
| ZD2 file size | 45,622 bytes | 45,564 bytes | -58 bytes | Shorter string lengths in PRME/PRMJ |
| Header byte 0x58 | 2 | 2 | 0 | `g1_slots` remains 2 |

## Answers

- **Can a firmware patch change it?**:
  No firmware patch is necessary. The 3-params-per-page display is the stock UI paging convention for multi-slot effects. Re-ordering manifest parameters in groups of three naturally allocates one dedicated page per stage on the pedal's display without requiring any firmware-level modifications.
- **Patch site + plan + risk**:
  N/A. Done entirely at the effect level (`effects/cfm_pre/manifest.json` and `effects/cfm_pre/cfm_pre.c`). Zero risk to firmware stability.

## Not checked / open leads
- On-device visual confirmation: requires photographing the G1 Four pedal screen when editing CFM Pre to visually verify text layout, glyph alignment, and page transitions across the 4 stages.
- Unrelated test failure in `tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx` (`assert 18464 == 18176`) was observed and left untouched per instructions.
