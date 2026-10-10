# CF Loader GUI - Helper Result Log

## Status
- **Current Phase:** L0 Survey (no code)
- **Last Updated:** 2026-10-10
- **Environment:** Windows, Python in `.venv`, tkinter verified operational (`import tkinter` OK).

## Findings

### L0 Tool Survey (Tools in §1 & §2)

#### 1. `tools/make_g1_image.py`
- **Command Line:**
  `.venv/Scripts/python.exe tools/make_g1_image.py [--clean [--keep STOCK.ZD2]...] <factory_image_bin> <out_image_bin> <effect1.ZD2> [<effect2.ZD2>...]`
- **Inputs:**
  - Base factory image: e.g. `build/fw/res3_3137536.bin` (or resource 136 extracted from official updater).
  - List of effect `.ZD2` files.
  - Optional `--clean`: uninstalls all stock effects in `FLST_SEQ.ZT2` (marks `installed = 0`), removes stock `.ZD2` files from filesystem, compacts directory.
  - Optional `--keep <STOCK.ZD2>` (repeatable with `--clean`): keeps specified stock effects.
- **Outputs:**
  - File system binary image file of exactly 3,137,536 bytes (`FS_SIZE = 0x2FE000`).
- **Exit Codes:**
  - `0`: Success.
  - Non-zero (e.g. `1` or string error via `sys.exit`): Missing args, container check failure, duplicate/invalid entries, or `g1fs.check_image` verification failure.
- **Execution Time:** ~0.2 - 0.5 seconds.
- **Success Output:**
  `image <out_path>: <N> files (<R> removed, <A> added: ...); effect list <E> entries, <I> installed; verified`

#### 2. `tools/make_fs_restore_updater.py`
- **Command Line:**
  `.venv/Scripts/python.exe tools/make_fs_restore_updater.py <official_updater.exe> <out_patched_updater.exe> [--image <out_image_bin>] [--splash <splash.png>] [--presets <presets.bin>]`
- **Inputs:**
  - `src`: Zoom's official "ZOOM G1X FOUR System v2.00 Updater.exe" (must match PE header, resource 0x88 size 0x2FE000, and expected stage table).
  - `dst`: Path for generated patched updater executable.
  - `--image <fs_image>`: The 3,137,536-byte file-system image to inject (from `make_g1_image.py`). If omitted, builds the factory restore updater.
  - Optional `--splash <png>`: 128x32 1-bit PNG startup splash.
  - Optional `--presets <bin>`: blank or custom presets.
- **Outputs:**
  - Standalone patched updater `.exe` targeting flash 0x102000 (and 0x28000 if presets/splash provided).
- **Exit Codes:**
  - `0`: Success.
  - Non-zero: Invalid official updater table/size, missing input files, or validation mismatch.
- **Execution Time:** ~0.5 - 1.0 seconds.
- **Success Output:**
  ```
  image <image>: <N> files, verified, placed at file offset <offset>
  wrote <dst>; stages:
     erase 0x00102000 size 0x2fe000
     write 0x00102000 resource 0x88
  ```

#### 3. `tools/check_updater_stages.py`
- **Command Line:**
  `.venv/Scripts/python.exe tools/check_updater_stages.py <updater.exe>`
- **Inputs:**
  - Path to updater executable to inspect.
- **Outputs:**
  - Standard output listing each stage in the 8-entry stage table.
- **Exit Codes:**
  - `0`: All stages safe (`ok` on all lines).
  - `1`: Any stage touches protected regions (`[0, 0x28000)` boot/update-mode program or `[0xbf000, 0xc0000)` settings sector).
- **Execution Time:** ~0.1 seconds.
- **Success Output:**
  ```
  <path>
     erase 0x00102000 size 0x2fe000       ok
     write 0x00102000 resource 0x88       ok
  ```

#### 4. `tools/backup_g1.py` (Advanced tab only, read-only readback)
- **Command Line:**
  `.venv/Scripts/python.exe tools/backup_g1.py <output_directory>`
- **Inputs:**
  - Output directory path. Pedal connected in standard operational mode.
- **Outputs:**
  - `<output-dir>/files/*`: downloaded files.
  - `<output-dir>/wire.log`: log of all MIDI traffic.
  - `<output-dir>/walk.txt`: file list.
- **Exit Codes:**
  - `0`: Backup complete.
  - `3`: Incomplete backup (registered effects missing).
  - `4`: Pedal timeout / unresolved session.
- **Execution Time:** Several minutes on physical hardware over USB. In app: runs in worker thread under Advanced tab with explicit DO-NOT-POWER-CYCLE confirmation.
- **Success Output:** `Backup complete: <N> files in <files_dir>`

#### 5. `tools/pedal_g1.py writetest --dry-run`
- **Command Line:**
  `.venv/Scripts/python.exe tools/pedal_g1.py writetest <effect.ZD2> --dry-run`
- **Inputs:**
  - Effect `.ZD2` file.
- **Outputs:**
  - Offline container verification output.
- **Exit Codes:**
  - `0`: Container valid.
  - `2`: Refused (bad container, size, CRC, target).
- **Execution Time:** ~0.2 seconds.
- **Success Output:**
  ```
  pedal_g1: offline checks passed for <FILE> (id <ID>, '<NAME>', <BYTES> bytes)
  pedal_g1: --dry-run, no MIDI port opened
  ```

#### 6. Stock Effect IDs and Filenames to Refuse
Extracted from `build/fw/res3_3137536.bin` (`FLST_SEQ.ZT2` and filesystem directory):
- Filesystem holds 105 files (78 `.ZD2` files).
- `FLST_SEQ.ZT2` lists 130 effects total (including uninstalled stock effects).

Full list of 130 stock effect filenames and IDs:
1. `ACOSIM.ZD2` (0x030000c0)
2. `AIR.ZD2` (0x09000010)
3. `ANA234CH.ZD2` (0x06000150)
4. `ANDLY_3S.ZD2` (0x08000021)
5. `APANDL3S.ZD2` (0x080000d1)
6. `AUTOPAN.ZD2` (0x07000020)
7. `AUTOWAH.ZD2` (0x02000010)
8. `BENDCHO.ZD2` (0x06000140)
9. `BGMK1_1U.ZD2` (0x04000041)
10. `BGMK3_1U.ZD2` (0x04000043)
11. `BGN4X12.ZD2` (0x05000050)
12. `BGTHRTTL.ZD2` (0x030000e0)
13. `BG_GRID.ZD2` (0x030000f0)
14. `BLACKOPT.ZD2` (0x01800010)
15. `BOMBER.ZD2` (0x07000010)
16. `CHAMBER.ZD2` (0x090000d0)
17. `CHORUS.ZD2` (0x06000020)
18. `CHURCH.ZD2` (0x090000a0)
19. `CLONECHO.ZD2` (0x06000100)
20. `COMP.ZD2` (0x01000010)
21. `CRNTRI3S.ZD2` (0x06000131)
22. `CRY.ZD2` (0x02000030)
23. `DELAY_3S.ZD2` (0x08000011)
24. `DETUNE.ZD2` (0x060000a0)
25. `DISTPLUS.ZD2` (0x03000160)
26. `DIST_1.ZD2` (0x03000120)
27. `DUALDL3S.ZD2` (0x080000a1)
28. `DUOPHA1U.ZD2` (0x06000171)
29. `DYNDRIVE.ZD2` (0x03000060)
30. `DZ4X12F.ZD2` (0x05000090)
31. `DZ_DRV1U.ZD2` (0x04000091)
32. `EARLYREF.ZD2` (0x09000080)
33. `EP_STOMP.ZD2` (0x03000020)
34. `EXCITER.ZD2` (0x020000b0)
35. `FD2X12.ZD2` (0x05000020)
36. `FDB4X10.ZD2` (0x05000027)
37. `FDBMAN1U.ZD2` (0x04000028)
38. `FDDLXR1U.ZD2` (0x0400002c)
39. `FDDX1X12.ZD2` (0x0500002a)
40. `FDMA2X12.ZD2` (0x0500002b)
41. `FDMSTR1U.ZD2` (0x0400002d)
42. `FDSPRING.ZD2` (0x09000060)
43. `FD_TWR1U.ZD2` (0x04000021)
44. `FLTRDLY.ZD2` (0x08000090)
45. `GATE_REV.ZD2` (0x090000e0)
46. `GOLD_DRV.ZD2` (0x03000040)
47. `GRAYCOMP.ZD2` (0x01000060)
48. `GTGEQ71U.ZD2` (0x02000054)
49. `GT_GEQ1U.ZD2` (0x02000051)
50. `HALL.ZD2` (0x09000030)
51. `HD_HALL.ZD2` (0x09000040)
52. `HOTSPICE.ZD2` (0x07000050)
53. `HPS.ZD2` (0x060000d0)
54. `HW100_1U.ZD2` (0x04000061)
55. `HW4X12.ZD2` (0x05000060)
56. `ICEDLY3S.ZD2` (0x08000101)
57. `LFO_FLTR.ZD2` (0x020000d0)
58. `LMT1176.ZD2` (0x01800020)
59. `LOWPASSF.ZD2` (0x020000a0)
60. `LPROLL3S.ZD2` (0x07000041)
61. `MA2X12.ZD2` (0x050000a0)
62. `MACH301U.ZD2` (0x040000a1)
63. `MK1_1X12.ZD2` (0x05000040)
64. `MK3_1X12.ZD2` (0x05000042)
65. `MODDELAY.ZD2` (0x08000050)
66. `MONOPITC.ZD2` (0x060000c0)
67. `MS19591U.ZD2` (0x04000019)
68. `MS45OS1U.ZD2` (0x0400001b)
69. `MS4X12.ZD2` (0x05000010)
70. `MS4X12AL.ZD2` (0x0500001a)
71. `MS4X12GB.ZD2` (0x05000018)
72. `MS800_1U.ZD2` (0x04000011)
73. `MTLWRLD.ZD2` (0x03000080)
74. `MUTESW.ZD2` (0x01000050)
75. `NYC_MUFF.ZD2` (0x030000d0)
76. `N_GATE.ZD2` (0x01000070)
77. `OCTAVE.ZD2` (0x06000080)
78. `OCTFUZZ.ZD2` (0x030000a0)
79. `OPTCOMP.ZD2` (0x01000080)
80. `ORG1201U.ZD2` (0x04000081)
81. `ORG_4X12.ZD2` (0x05000080)
82. `OUT_BST.ZD2` (0x03000150)
83. `PARAEQ.ZD2` (0x02000070)
84. `PHASDL1U.ZD2` (0x080000e1)
85. `PHASER.ZD2` (0x06000040)
86. `PITCHSHF.ZD2` (0x060000b0)
87. `PLATEREV.ZD2` (0x09000070)
88. `PPDLY_3S.ZD2` (0x08000081)
89. `PTCHDL3S.ZD2` (0x080000b1)
90. `RACKCOMP.ZD2` (0x01000020)
91. `RCBOOST.ZD2` (0x03000030)
92. `RCT4X12.ZD2` (0x05000070)
93. `RCTORG1U.ZD2` (0x04000071)
94. `REDCRUNC.ZD2` (0x03000070)
95. `RESONANC.ZD2` (0x02000020)
96. `RINGMOD.ZD2` (0x06000090)
97. `RNDMFLTR.ZD2` (0x02000090)
98. `ROOM.ZD2` (0x09000020)
99. `RVRSDL3S.ZD2` (0x08000041)
100. `SEQFLTR.ZD2` (0x02000040)
101. `SLATDL3S.ZD2` (0x08000111)
102. `SLICER.ZD2` (0x060000f0)
103. `SLPBKD3S.ZD2` (0x080000c1)
104. `SLWATK.ZD2` (0x01000030)
105. `SOFTEC3S.ZD2` (0x08000121)
106. `SPRING.ZD2` (0x09000050)
107. `SPTBOOST.ZD2` (0x030000b0)
108. `SQUEAK.ZD2` (0x03000130)
109. `STEP.ZD2` (0x020000c0)
110. `STEREOCH.ZD2` (0x06000030)
111. `STGTGE1U.ZD2` (0x02000061)
112. `STONEPHA.ZD2` (0x06000120)
113. `SUPERCHO.ZD2` (0x06000110)
114. `SWEETDRV.ZD2` (0x03000050)
115. `TAPEECHO.ZD2` (0x08000030)
116. `TB_MK15.ZD2` (0x03000090)
117. `THEVIBE.ZD2` (0x06000060)
118. `TPEC3_3S.ZD2` (0x080000f1)
119. `TREMOLO.ZD2` (0x06000010)
120. `TS_DRIVE.ZD2` (0x03000010)
121. `UK2X12.ZD2` (0x05000030)
122. `UK30A_1U.ZD2` (0x04000031)
123. `UPOCTBST.ZD2` (0x03000140)
124. `VIBRATO.ZD2` (0x06000070)
125. `VINFLNGR.ZD2` (0x06000050)
126. `VIOLETDS.ZD2` (0x03000190)
127. `WRPPHASE.ZD2` (0x06000160)
128. `XTSBLU1U.ZD2` (0x04000051)
129. `ZEN_DRV.ZD2` (0x03000170)
130. `ZNR.ZD2` (0x01000040)

Also non-effect system files in the filesystem:
- `Clap.raw` .. `TomL.raw` (24 rhythm sample files)
- `GUARDZDL.ZT2`
- `G_OUT_EQ.BDL`
- `FLST_SEQ.ZT2`

## Decisions
- Subprocesses must be executed with `.venv/Scripts/python.exe` and arguments passed as lists (no `shell=True`).
- Path handling must support spaces in path names (e.g. `zoom project`).
- Stock effect IDs and names are codified in `core.py` directly (using the verified 130 stock entries) so offline validation does not depend on having `res3_3137536.bin` mounted.
- App will never touch MIDI directly; no mido / rtmidi imports in `tools/cf_loader`.
- `tools/cf_loader/core.py` is pure logic with no tkinter import.
- Status safety transitions: an effect can only transition to 'ok-save' if both 'audio-pass' and 'cost-measured' have completed.

## Tests
- Python and tkinter availability verified.
- Tool CLI syntax verified via `--help` and dry runs.
- **L1 Pytest Suite:** `pytest tests/cf_loader -q` passes 10/10 tests:
  ```
  tests/cf_loader/test_core.py::test_safety_grep_no_midi PASSED
  tests/cf_loader/test_core.py::test_safety_no_exe_as_program PASSED
  tests/cf_loader/test_core.py::test_slot_heap_calculation_ratx PASSED
  tests/cf_loader/test_core.py::test_inspect_zd2_valid_ratx PASSED
  tests/cf_loader/test_core.py::test_inspect_zd2_oversize_sibling PASSED
  tests/cf_loader/test_core.py::test_inspect_zd2_stock_collision PASSED
  tests/cf_loader/test_core.py::test_preflight_checks_green_and_red PASSED
  tests/cf_loader/test_core.py::test_output_folder_never_overwrites PASSED
  tests/cf_loader/test_status_safety_gates PASSED
  tests/cf_loader/test_probe10_cost_calculation PASSED
  10 passed in 0.15s
  ```
- Full repo pytest suite passes 18/18 tests in 0.21s.

## Problems
- None.

---

## Status Update (L1 Complete)
- **Phase:** L1 `core.py` + tests complete.
- **Next Phase:** L2 Library + Build tabs (`app.py` UI implementation).

