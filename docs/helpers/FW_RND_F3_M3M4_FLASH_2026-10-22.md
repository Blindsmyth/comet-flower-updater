# CF M3 / CF M4 Slot-Count Probes (Job F3)

## Status
done

## Findings

### Finding 1: Creation and Build of Probe Effects CFM3P and CFM4P
- **Claim**: Created `effects/cfm3/` and `effects/cfm4/` based on `effects/cfm2/`. `effects/cfm3/manifest.json` and `effects/cfm4/manifest.json` were modified strictly per specification:
  - `name`: "CF M3" / "CF M4"
  - `display`: "CF M3" / "CF M4"
  - `filename`: `CFM3P` / `CFM4P`
  - `id`: `07000f8e` / `07000f8f`
  - `g1_slots`: 3 / 4
  - `kernel`: `cfm3.c` / `cfm4.c`
  - `description`: updated slot count to 3 / 4, preserving "Never save it in a patch."
  - All parameter definitions, ranges, defaults, and DSP settings were left untouched.
- **Evidence**:
  - `effects/cfm3/manifest.json` and `effects/cfm4/manifest.json`
  - Built cleanly using `bash tools/build_g1.sh cfm3 "CF M3"` and `bash tools/build_g1.sh cfm4 "CF M4"`.
  - Output files generated: `build/CFM3P.ZD2` (11,416 B) and `build/CFM4P.ZD2` (11,416 B).
- **Confidence**: confirmed

### Finding 2: ZD2 Header Byte-by-Byte Survey and Difference Analysis
- **Claim**: Header byte `0x58` is set strictly to `3` for `CFM3P.ZD2` and `4` for `CFM4P.ZD2`. Every other header byte (in the 128-byte range `0x00..0x7F`) matches `CFM2P.ZD2` exactly, except for the four expected differing fields: file CRC32 checksum, slot count, effect ID, and effect name.
- **Evidence**:
  - Verification script `build/fw_rnd/F3/verify.py` compared `CFM2P.ZD2` against `CFM3P.ZD2` and `CFM4P.ZD2` byte-for-byte across offset range `0x00..0x7F`.
  - Detailed differing offsets between `CFM2P.ZD2` and `CFM3P.ZD2` (7 bytes differ total):
    - `0x08..0x0B`: CRC32 checksum (`0xba 0xd9 0x4a 0x40` -> `0x40 0xc1 0x76 0xb7`)
    - `0x58`: Slot count / g1_slots (`0x02` -> `0x03`)
    - `0x60`: Low byte of Effect ID (`0x8d` -> `0x8e`, corresponding to `0x07000f8d` -> `0x07000f8e`)
    - `0x68`: Name character digit ('2' / `0x32` -> '3' / `0x33` in `"CF M3"`)
  - Detailed differing offsets between `CFM2P.ZD2` and `CFM4P.ZD2` (7 bytes differ total):
    - `0x08..0x0B`: CRC32 checksum (`0xba 0xd9 0x4a 0x40` -> `0x98 0x0e 0xd6 0x2b`)
    - `0x58`: Slot count / g1_slots (`0x02` -> `0x04`)
    - `0x60`: Low byte of Effect ID (`0x8d` -> `0x8f`, corresponding to `0x07000f8d` -> `0x07000f8f`)
    - `0x68`: Name character digit ('2' / `0x32` -> '4' / `0x34` in `"CF M4"`)
  - All other 121 header bytes are 100% identical.
- **Confidence**: confirmed

### Finding 3: Slot Memory Compliance (40 KiB Rule)
- **Claim**: Both `CFM3P.ZD2` and `CFM4P.ZD2` satisfy the 40 KiB per-slot memory limit with ample headroom (35,392 bytes free).
- **Evidence**:
  - `tools/check_slot_mem.py` results:
    - `build/CFM3P.ZD2`: uses 5,568 of 40,960 bytes (35,392 free) - OK
    - `build/CFM4P.ZD2`: uses 5,568 of 40,960 bytes (35,392 free) - OK
- **Confidence**: confirmed

### Finding 4: Summary Table
- **Claim**: Summary of probe effects compared with CFM2P and CFM5P:

| file | size | 0x58 | id | dspload |
|---|---|---|---|---|
| `CFM2P.ZD2` | 11416 | 2 | `0x07000f8d` | 10.00 |
| `CFM3P.ZD2` | 11416 | 3 | `0x07000f8e` | 10.00 |
| `CFM4P.ZD2` | 11416 | 4 | `0x07000f8f` | 10.00 |
| `CFM5P.ZD2` | 11416 | 5 | `0x07000f8c` | 10.00 |

- **Confidence**: confirmed

### Finding 5: Test Suite Execution
- **Claim**: Executed pytest across repository test suite: 333 passed, 1 failed, 146 subtests passed.
- **Evidence**:
  - Command: `.venv/Scripts/python.exe -m pytest tests -q`
  - Unrelated failure: `tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx` (`assert 18464 == 18176` on `build/RATX.ZD2`).
- **Confidence**: confirmed

## Answers

### Q1. Slot-Count Ceiling Probes (Header 0x58 <= 4)
- **Answer**: The static analysis in `docs/FW_RND_ANSWERS_2026-10-22.md` identified the firmware ceiling at `c0129908` (`CMPLTU.L2 0x4, B0, B0; [B0] B c0129b40`), which enforces that header byte 0x58 must be `<= 4` during ZD2 header validation. Probes `CFM3P` (header 0x58 = 3) and `CFM4P` (header 0x58 = 4) are now constructed and verified. Since both have header 0x58 `<= 4`, they are predicted to pass the file validation check that rejected `CFM5P` (header 0x58 = 5).
- **Can a firmware patch change it?**: Yes, if testing on hardware shows that 3-slot or 4-slot effects are accepted while 5-slot effects are rejected, the ceiling can be patched at `c0129908` (`CMPLTU 0x4` -> `CMPLTU 0x5`). However, as noted in Q2 of the firmware R&D answers, header N does not expand runtime memory allocation (each effect still receives one slot's 40 KiB heap, state, and work buffer).
- **Patch site**: `c0129908`
- **Plan**: Compare behavior on physical hardware or test updater with CFM3P and CFM4P before considering firmware patching.
- **Risk**: Low for validation logic itself, but unknown for UI display / patch slot reservations on hardware.

## Not checked / open leads
- Physical installation and loading on G1 Four hardware: Not tested (per hard safety rules, no pedal interaction or updater image modifications performed).
- How the G1 Four UI/screen renders 3-slot and 4-slot effects (e.g. whether it pads or claims adjacent slots on the patch grid): Awaiting hardware testing by the bench owner.
