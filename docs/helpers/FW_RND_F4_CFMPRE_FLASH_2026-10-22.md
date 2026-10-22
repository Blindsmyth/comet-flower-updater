# CFM Pre Page Re-layout, One Stage Per Page (Job F4)

## Status
running

## Findings

### Finding 1: EDTB Patch Field Bit-Widths and 8-Bit Parameter Capacity
- **Claim**: In Zoom G1/G1X Four EDTB preset records, the 12 parameter fields have bit-widths `[12, 12, 12, 12, 12, 8, 8, 8, 12, 12, 12, 12]`. Fields 6..8 (0-based 5..7: Muff Vol, MistRate, MistRang; or fields 5..7: MuffTone, Muff Vol, MistRate) are restricted to 8 bits (maximum value 255). In the re-laid out CFM Pre parameter set, all parameters across the entire effect have maximum values of either 1 or 100. Consequently, every parameter placed into the 8-bit fields strictly obeys `max <= 255`, preventing truncation or preset corruption.
- **Evidence**:
  - `tools/ua_bench.py` line 44: `PARAM_BITS = [12, 12, 12, 12, 12, 8, 8, 8, 12, 12, 12, 12]`.
  - `docs/FW_RND_ANSWERS_2026-10-22.md` lines 85–89: "the EDTB slot entry is 24 bytes with 12 packed fields `[12,12,12,12,12,8,8,8,12,12,12,12]` bits... Note params 6-8 are only 8 bits (max 255)."
  - Parameter max values in the re-ordered manifest: `MuffTone` max = 100, `Muff Vol` max = 100, `MistRate` max = 100, `MistRang` max = 100. All <= 255.
- **Confidence**: Confirmed.

### Finding 2: Baseline Binary Metrics (CFMPRE.ZD2)
- **Claim**: Prior to the re-layout, the baseline `build/CFMPRE.ZD2` had `.text` size of 29,248 bytes (0x7240), total slot memory usage of 39,920 bytes out of the 40,960 byte (0xa000) slot heap (1,040 bytes free), and header byte `0x58` equal to 2 (`g1_slots` = 2).
- **Evidence**:
  - `build/CFMPRE.REPORT.md`: `.text 29248 B`.
  - `tools/check_slot_mem.py build/CFMPRE.ZD2`: `slot memory: build/CFMPRE.ZD2 uses 39920 of 40960 bytes (1040 free) tight`.
  - Binary inspection of `build/CFMPRE.ZD2`: offset `0x58` is byte value `0x02`.
- **Confidence**: Confirmed.

## Answers

## Not checked / open leads
