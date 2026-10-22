# CFMPRE Labels Cut to 5 Characters (Job F6)

## Status
done

## Findings

### Finding 1: Screen Column Width and 5-Character Constraint
- **Claim**: The Zoom G1 Four effect edit screen renders parameter labels centered in 31 px columns using a 5x7 glyph font with a fixed 6 px advance (`ADD 6` at `c011d524`, table at `0xc0181508` with column centers `17, 48, 79, 110`). A 5-character string rendered with 6 px advance takes 30 px, fitting entirely within the 31 px column width. Any label with 6 or more characters spans >= 36 px and visually overlaps adjacent columns on the pedal LCD.
- **Evidence**:
  - `docs/FW_RND_ANSWERS_2026-10-22.md` lines 173–180 (Q7 findings).
  - Reverse engineering confirmed centering logic `3 x chars` passed to `c013a2d8`.
- **Confidence**: Confirmed.

### Finding 2: Parameter Names Cut to <= 5 Characters with Invariants Preserved
- **Claim**: All 12 parameter labels in `effects/cfm_pre/manifest.json` have been reduced to <= 5 characters (D = DynaComp, M = Muff, F = Flanger/Mistress). The parameter order, maximum values, default values, and explanations remain strictly identical to git `HEAD`.
- **Evidence**:
  - Verification script `build/fw_rnd/F6/check_manifest_diff.py` verified the manifest against `git show HEAD:effects/cfm_pre/manifest.json`:
    - Param 0: `Dyn Sens` -> `DSens` (5 chars, max 100, default 50)
    - Param 1: `Dyn Out`  -> `DOut`  (4 chars, max 100, default 60)
    - Param 2: `Dyn On`   -> `DynOn` (5 chars, max 1, default 0)
    - Param 3: `MuffSust` -> `MSust` (5 chars, max 100, default 75)
    - Param 4: `MuffTone` -> `MTone` (5 chars, max 100, default 50)
    - Param 5: `Muff Vol` -> `MVol`  (4 chars, max 100, default 70)
    - Param 6: `MistRate` -> `FRate` (5 chars, max 100, default 35)
    - Param 7: `MistRang` -> `FRang` (5 chars, max 100, default 70)
    - Param 8: `MistColr` -> `FColr` (5 chars, max 100, default 65)
    - Param 9: `Muff On`  -> `MufOn` (5 chars, max 1, default 1)
    - Param 10: `Mist Mtx` -> `FMtx` (4 chars, max 1, default 0)
    - Param 11: `Level`    -> `Level` (5 chars, max 100, default 70)
  - Zero changes occurred to explanations, defaults, or maximums.
- **Confidence**: Confirmed.

### Finding 3: C Kernel Macro Synchronization and Build Verification
- **Claim**: In `effects/cfm_pre/cfm_pre.c`, parameter read indices were updated to match the newly generated macros in `sh_params.h`. Building with `bash tools/build_g1.sh cfm_pre "CFM Pre"` cleanly generates `build/CFMPRE.ZD2`. The binary passes `check_slot_mem.py` with 1,072 bytes of headroom, and header byte `0x58` remains strictly 2 (`g1_slots`).
- **Evidence**:
  - `C:/Users/z/zoomlab/stomphacks/effects/cfm_pre/build/sh_params.h`:
    - `SH_PARAM_DSENS` = 3
    - `SH_PARAM_DOUT` = 5
    - `SH_PARAM_DYNON` = 6
    - `SH_PARAM_MSUST` = 7
    - `SH_PARAM_MTONE` = 8
    - `SH_PARAM_MVOL` = 9
    - `SH_PARAM_FRATE` = 10
    - `SH_PARAM_FRANG` = 11
    - `SH_PARAM_FCOLR` = 2
    - `SH_PARAM_MUFON` = 12
    - `SH_PARAM_FMTX` = 13
    - `SH_PARAM_LEVEL` = 14
  - `tools/check_slot_mem.py build/CFMPRE.ZD2`:
    - `slot memory: build/CFMPRE.ZD2 uses 39888 of 40960 bytes (1072 free) tight`
  - Header inspection via `build/fw_rnd/F6/verify_zd2.py`:
    - Header offset `0x58` = `0x02` (2 slots).
    - Header offset `0x0c` = `0x0002` (G1 family target).
    - File size: 45,500 bytes (decreased by 64 bytes from 45,564 B due to shorter string lengths in PRME and PRMJ sections).
- **Confidence**: Confirmed.

### Finding 4: Test Suite Results
- **Claim**: Full test suite (`.venv/Scripts/python.exe -m pytest tests -q`) was executed. All tests passed except the single known, unrelated failure.
- **Evidence**:
  - Test summary: `1 failed, 339 passed, 146 subtests passed in 68.99s`.
  - The single failure: `FAILED tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx - assert 18464 == 18176` (known unrelated RATX heap test).
- **Confidence**: Confirmed.

## Parameter Layout Table

| Page | Stage | Index | New 5-Char Label | Previous Label | Max | Default | Coeff Slot | Generated Macro | Explanation |
|:---:|:---:|:---:|:---|:---|:---:|:---:|:---:|:---|:---|
| 1 | Dyna | 0 | `DSens` | `Dyn Sens` | 100 | 50 | [3] | `SH_PARAM_DSENS` | DynaComp sensitivity / compression ratio. |
| 1 | Dyna | 1 | `DOut` | `Dyn Out` | 100 | 60 | [5] | `SH_PARAM_DOUT` | DynaComp output level. |
| 1 | Dyna | 2 | `DynOn` | `Dyn On` | 1 | 0 | [6] | `SH_PARAM_DYNON` | DynaComp stage engage (0=Bypass, 1=Active). |
| 2 | Muff | 3 | `MSust` | `MuffSust` | 100 | 75 | [7] | `SH_PARAM_MSUST` | Ram's Head Big Muff sustain / fuzz gain. |
| 2 | Muff | 4 | `MTone` | `MuffTone` | 100 | 50 | [8] | `SH_PARAM_MTONE` | Big Muff tone tilt filter. |
| 2 | Muff | 5 | `MVol` | `Muff Vol` | 100 | 70 | [9] | `SH_PARAM_MVOL` | Fuzz output volume. |
| 3 | Mistress | 6 | `FRate` | `MistRate` | 100 | 35 | [10] | `SH_PARAM_FRATE` | Electric Mistress LFO sweep rate. |
| 3 | Mistress | 7 | `FRang` | `MistRang` | 100 | 70 | [11] | `SH_PARAM_FRANG` | Electric Mistress sweep range / depth. |
| 3 | Mistress | 8 | `FColr` | `MistColr` | 100 | 65 | [2] | `SH_PARAM_FCOLR` | Electric Mistress BBD feedback / color. |
| 4 | Switches | 9 | `MufOn` | `Muff On` | 1 | 1 | [12] | `SH_PARAM_MUFON` | Muff stage engage (0=Bypass, 1=Active). |
| 4 | Switches | 10 | `FMtx` | `Mist Mtx` | 1 | 0 | [13] | `SH_PARAM_FMTX` | Mistress Filter Matrix mode (freeze LFO). |
| 4 | Switches | 11 | `Level` | `Level` | 100 | 70 | [14] | `SH_PARAM_LEVEL` | Preamp master output trim. |

## Binary Comparison Summary

| Metric | Previous (F4 Layout) | New (F6 5-Char Layout) | Delta | Notes |
|---|---|---|---|---|
| `.text` section size | 29,216 bytes (0x7220) | 29,216 bytes (0x7220) | 0 bytes | Code logic unchanged |
| `.const` section size | 9,684 bytes (0x25d4) | 9,684 bytes (0x25d4) | 0 bytes | Constants blob identical |
| Per-slot heap used | 39,888 bytes | 39,888 bytes | 0 bytes | 1,072 bytes free in 40 KiB heap |
| ZD2 file size | 45,564 bytes | 45,500 bytes | -64 bytes | Shorter string bytes in PRME/PRMJ |
| Header byte 0x58 | 2 | 2 | 0 | `g1_slots` remains 2 |

## Answers

- **Can a firmware patch change it?**:
  No firmware patch is necessary. The 5-character constraint is dictated by the physical 128x32 display geometry and 31 px column pitch with the 6 px fixed font. Keeping labels <= 5 characters in `manifest.json` prevents column overlap on the hardware screen without requiring UI firmware changes.
- **Patch site + plan + risk**:
  N/A. Handled purely at the effect manifest and DSP kernel level. Zero risk to firmware.

## Not checked / open leads
- Hardware visual verification: photographing the LCD screen of the G1 Four editing CFMPRE to confirm column separation and visual appearance with the new 5-character labels.
- Unrelated failure in `tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx` was preserved as instructed.
