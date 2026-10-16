# Zoom G1X Four Settings-Menu RE — Argon Report (2026-10-16)

## Summary
*(Pending final synthesis — <= 15 lines)*

## A1. Menu Data: Item Table(s), Page List, and Table Word Dump

### 1. Where the Menu Tables Live: `.cinit` RLE24 -> RAM `0xc0181b28..0xc0183b71` (Confirmed)
- In `build/fw/map/main.elf`, `0xc0181b28..0xc0183b74` is an uninitialized RAM region populated at boot by `__TI_auto_init` (`c0163708..c0163790`) via the `.cinit` record at `c0186ef4..c0186ef8`:
  ```
  c0186ef4   c0185260   .word 0xc0185260   ; source in DATA Section sc0185260 (.cinit)
  c0186ef8   c0181b28   .word 0xc0181b28   ; destination in RAM
  ```
- Byte 0 at `c0185260` (`0x1b281a01`) is handler index `1` (`c0186de0 -> c016e1a0 -> c0161e60`, TI RLE24 with delimiter byte `0x1a` at `c0185261`), decompressing `0xc0185260..0xc01868f2` into `8,265` (`0x2049`) bytes at `0xc0181b28..0xc0183b71`.
- Note on file offsets: because `sc016f780` (`0xc016f780..0xc0181b24`, `diff = 0xc010c0c0`) is followed in `main.elf` by `sc0183b74` (`diff = 0xc010e110`) and `sc0185260` (`diff = 0xc010e94c`), naive `addr = file_off + 0xc010c0c0` past `0xc0181b24` lands inside the RLE24-compressed `sc0185260` stream. Below, both the **runtime RAM addresses** (`0xc0182b00..0xc0183818`, referenced by code in `refs.txt`) and the **exact `.cinit` `.word` source addresses** (`0xc0185c6c..0xc01866c4` in `main.dis`) are given.

### 2. Top-Level `SETTING` Page Lists and Screen Descriptor Switch (Confirmed)
- **Screen descriptor lookup (`c01495c0`)**: takes screen ID `A4` (`0..14`), indexes `.switch` table `0xc018413c..0xc0184174` (`c01495cc MVK 0x413c,A5; MVKH 0xc0180000,A5; LDW *A5[A4],A0`), and calls a getter returning a **9-word (`0x24`-byte) screen descriptor** stored as active screen in `*+B14[120]` by `c0149664` (`c0149698 STW.D2T1 A0,*+B14[120]`).
- **9-word (`0x24`-byte) Screen Descriptor Layout** (verified via `c0149664`, `c0149724`, `c0149840`, `c0149a68`, `c0149ad4`):
  - `w0` (`+0x00`): `uint32_t screen_id` (`0..14`, read by `c01497f4`: `c0149802 LDW.D2T1 *B4[0],A0`)
  - `w1` (`+0x04`): `const uint8_t *icon_bmp_type0` (24x30 bitmap, selected by `c0149ad4` when `B4==0`: `c0149b00 LDW *+A4[1],A4`)
  - `w2` (`+0x08`): `const uint8_t *icon_bmp_type1` (24x30 bitmap, selected by `c0149ad4` when `B4==1`: `c0149b08 LDW *+A4[2],A4`)
  - `w3` (`+0x0c`): `const uint8_t *icon_bmp_type2` (24x30 bitmap, selected by `c0149ad4` when `B4==2`: `c0149b10 LDW *+A4[3],A4`)
  - `w4` (`+0x10`): `void (*on_enter)(void)` (called on screen entry at `c01496a4 LDW *A4[4],A0; B.S2X A0`)
  - `w5` (`+0x14`): `void (*on_exit)(void)` (called on screen exit at `c0149686 LDW *B4[5],B0; B.S2 B0`)
  - `w6` (`+0x18`): `void (*draw)(int arg)` (called to render screen at `c0149a7a LDW *B4[6],B0; B.S2 B0`)
  - `w7` (`+0x1c`): `void (*on_tick_or_poll)(void)` (called from `c0149724`: `c0149744 LDW *B4[7],B0; BNOP.S2 B0,0`)
  - `w8` (`+0x20`): `int (*on_event)(event_t *ev)` (called on button/knob input at `c014990a LDW *B4[8],B0; B.S2 B0`)

- **All 15 Screen Descriptors (`id = 0..14`)** (decoded from `.cinit` `0xc01861d6..0xc01866b6`, verified against getters in `c01495e4..c0149658`):

| ID | RAM Addr (`cinit` Addr) | Getter | `w0` | `w1` (icon0) | `w2` (icon1) | `w3` (icon2) | `w4` (enter) | `w5` (exit) | `w6` (draw) | `w7` (poll) | `w8` (event) | Role / Page Name |
|---:|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | `c01833dc` (`c018634f`) | `c0157c50` | `0` | `00000000` | `00000000` | `00000000` | `00000000` | `00000000` | `c0157c0c` | `c01579c0` | `c0157bac` | `SETTING` top menu (List A: `c0181350`) |
| 1 | `c0183400` (`c018635c`) | `c0157c44` | `1` | `00000000` | `00000000` | `00000000` | `00000000` | `00000000` | `c0157c0c` | `c01579c0` | `c0157bac` | `SETTING` alt top menu (List B: `c0181368`) |
| 2 | `c01836b0` (`c0186579`) | `c0164950` | `2` | `00000000` | `00000000` | `00000000` | `00000000` | `00000000` | `c01648fa` | `00000000` | `c0164850` | `TEMPO` screen |
| 3 | `c01836f8` (`c01865ac`) | `c0153110` | `3` | `c017ea28` | `c017e728` | `c017e428` | `c01530e2` | `c0152da8` | `c01530f8` | `c0152d80` | `c01530a6` | Chain / effect slot page B |
| 4 | `c01836d4` (`c0186588`) | `c0146338` | `4` | `c017e9c8` | `c017e6c8` | `c017e3c8` | `c0146312` | `c0145dd4` | `c014632c` | `c0145da0` | `c01462d4` | `CHAIN` page |
| 5 | `c0183740` (`c01865eb`) | `c016a9ac` | `5` | `c017ea88` | `c017e788` | `c017e488` | `c016a978` | `00000000` | `c016a97a` | `c016a940` | `c016a95a` | `OUTPUT` EQ (`Lo/MID/Hi/MVOL`, table `c0182b00`) |
| 6 | `c0183764` (`c018660e`) | `c014c870` | `6` | `c017eae8` | `c017e7e8` | `c017e4e8` | `c014c6b2` | `c014c3ce` | `c014c79a` | `c014c3c0` | `c014c66c` | `PATCH` (`CHAR/SKIP/VALUE/LEVEL`) |
| 7 | `c0183200` (`c01861d6`) | `c0139620` | `7` | `c017ee48` | `c017ede8` | `c017ed88` | `c0138bc0` | `00000000` | `c0139504` | `c0138c1c` | `c0139404` | `SAVE` patch page |
| 8 | `c0183248` (`c018621c`) | `c0139610` | `8` | `c017ef68` | `c017ef08` | `c017eea8` | `c0138b58` | `00000000` | `c0139504` | `c0138c1c` | `c0139404` | `SWAP` patch page |
| 9 | `c01837d0` (`c0186678`) | `c0159378` | `9` | `c017ec08` | `c017e908` | `c017e608` | `c0159216` | `00000000` | `c0159234` | `c01591da` | `c01591e8` | `TUNER` (`OUTPUT/CALIB/TYPE/FLAT`, table `c0182d10`) |
| 10 | `c0183788` (`c0186632`) | `c0167230` | `10` | `c017eb48` | `c017e848` | `c017e548` | `c01671da` | `00000000` | `c01671f6` | `c01671a0` | `c01671ac` | `SETUP` (`BPM/AUTO SAVE/PRE-SELECT/BANK HOLD`, table `c0182bb0`) |
| 11 | `c01837ac` (`c0186655`) | `c01632ec` | `11` | `c017eba8` | `c017e8a8` | `c017e5a8` | `c0163296` | `00000000` | `c01632b2` | `c0163258` | `c0163268` | `PWR/LCD` (`BATTERY/ECO/BACKLIGHT/CONTRAST`, table `c0182c60`) |
| 12 | `c01837f4` (`c018669b`) | `c0167310` | `12` | `c017ec68` | `c017e968` | `c017e668` | `c0167252` | `00000000` | `c01672ee` | `c0167240` | `c016724e` | `VERSION` (`SYSTEM/PRESET/BOOT`, custom draw) |
| 13 | `c018371c` (`c01865d0`) | `c01579b0` | `13` | `00000000` | `00000000` | `c017ed88` | `c0157876` | `00000000` | `c0157898` | `c0157720` | `c0157838` | `EDITED! SAVE?` (`YES/NO`) dialog |
| 14 | `c0183224` (`c01861f9`) | `c013962c` | `14` | `c017ee48` | `c017ede8` | `c017ed88` | `c0139580` | `00000000` | `c0139504` | `c0138c1c` | `c0139404` | `SAVE` confirmation variant |

- **Top-Level `SETTING` 5-Icon Page Lists (`0xc0181338..0xc0181378` in `sc016f780`, Confirmed)**:
  - `c0157c0c` (the `draw` function for Screen IDs `0` and `1`) loops `A10 = 0..4` (`c0157c20..c0157c34: CMPGT.L1 5,A10,A0`) calling `c01579cc(slot_idx=A10, is_page1=A11, icon_variant=0)`, then calls `c0157bf0` which draws the `"SETTING"` title bar (`c018179c`).
  - `c01579cc` (`c01579e4..c0157a30`) and `c0157ae8` (`c0157b00..c0157b28`) select between two 5-word page-ID arrays in `.const` (`sc016f780`), verified in `main.dis`:
    ```
    ; 5 icon X-coordinates (c0157a14 MVK 0x1338,A1; MVKH 0xc0180000,A1):
    c0181338   00000002   .word 0x00000002   ; Slot 0 (Button 1): x = 2
    c018133c   0000001b   .word 0x0000001b   ; Slot 1 (Button 2): x = 27
    c0181340   00000035   .word 0x00000035   ; Slot 2 (Button 3): x = 53
    c0181344   0000004d   .word 0x0000004d   ; Slot 3 (Button 4): x = 77
    c0181348   00000066   .word 0x00000066   ; Slot 4 (Button 5): x = 102

    ; Page List A (Screen ID 0, c01579f0 / c0157b00 MVK 0x1350,A4):
    c0181350   00000004   .word 0x00000004   ; Slot 0 -> ID 4  (CHAIN)
    c0181354   00000006   .word 0x00000006   ; Slot 1 -> ID 6  (PATCH)
    c0181358   00000007   .word 0x00000007   ; Slot 2 -> ID 7  (SAVE)
    c018135c   0000000a   .word 0x0000000a   ; Slot 3 -> ID 10 (SETUP)
    c0181360   0000000b   .word 0x0000000b   ; Slot 4 -> ID 11 (PWR/LCD)

    ; Page List B (Screen ID 1, c01579e4 / c0157b08 MVK 0x1368,A4):
    c0181368   00000005   .word 0x00000005   ; Slot 0 -> ID 5  (OUTPUT: Lo/MID/Hi/MVOL)
    c018136c   00000009   .word 0x00000009   ; Slot 1 -> ID 9  (TUNER: OUTPUT/CALIB/TYPE/FLAT)
    c0181370   00000003   .word 0x00000003   ; Slot 2 -> ID 3  (Chain/Effect slot page B)
    c0181374   00000008   .word 0x00000008   ; Slot 3 -> ID 8  (SWAP)
    c0181378   0000000c   .word 0x0000000c   ; Slot 4 -> ID 12 (VERSION: SYSTEM/PRESET/BOOT)
    ```

### 3. Menu Item Table Structure (`0x2c` = 44 Bytes = 11 Words per Item, Confirmed)
- Four 4-item tables exist contiguously at runtime RAM `0xc0182b00..0xc0182dc0` (`4 * 4 * 0x2c = 0x2c0` bytes):
  1. **`0xc0182b00..0xc0182bb0`** (4 items, passed at `c016a984 MVK 0x2b00,B4` with `A4=4`): **`OUTPUT`** (`Lo`, `MID`, `Hi`, `MVOL`)
  2. **`0xc0182bb0..0xc0182c60`** (4 items, passed at `c01671c4` & `c0167200 MVK 0x2bb0,B4` with `A4=4`): **`SETUP`** (`BPM`, `AUTO SAVE`, `PRE-SELECT`, `BANK HOLD`)
  3. **`0xc0182c60..0xc0182d10`** (4 items, passed at `c0163280` & `c01632b8 MVK 0x2c60,B4` with `A4=4`): **`PWR/LCD`** (`BATTERY`, `ECO`, `BACKLIGHT`, `CONTRAST`)
  4. **`0xc0182d10..0xc0182dc0`** (4 items, passed at `c0159200` & `c0159244 MVK 0x2d10,A3` with `A4=4`): **`TUNER`** (`OUTPUT`, `CALIB`, `TYPE`, `FLAT`)
- **11-Word (`0x2c`-byte) Item Struct Layout** (verified via draw loop `c0154338..c0154558` and knob handler `c0149948..c0149a08`):
  - `w0` (`+0x00`): `uint32_t item_id` (`0..3`)
  - `w1` (`+0x04`): `uint32_t reserved1` (always `0x00000fff`)
  - `w2` (`+0x08`): `uint32_t reserved2` (always `0x00000fff`)
  - `w3` (`+0x0c`): `const char *label_line1` (`c0154372 LDW *A4[3],A5`)
  - `w4` (`+0x10`): `const char *label_line2` (`c0154366 LDW *A4[4],A0`; if `NULL`, single-line label; if non-NULL, two-line label drawn at `y=9` and `y=15`)
  - `w5` (`+0x14`): `int32_t min_val` (`c01499b6 LDW *A4[5],B4`, passed to clamp `c01418ec`)
  - `w6` (`+0x18`): `int32_t max_val` (`c01499ac LDW *A4[6],A4`, passed to step scaler `c0153464` and clamp `c01418ec`)
  - `w7` (`+0x1c`): `const char *(*val_to_str)(int val)` (`c01544c4 LDW *A4[7],A1`; if `NULL`, `c01544d8` formats `get_val()` with `"%d"` (`0xc018178c`); if non-NULL, `c0154500` calls `w7(get_val())` and formats with `"%s"` (`0xc018178f`))
  - `w8` (`+0x20`): `int (*get_val)(void)` (`c01544ba` & `c0149992 LDW *A4[8],A0`; if `NULL`, item value is neither drawn nor editable)
  - `w9` (`+0x24`): `void (*set_val)(int new_val)` (`c01499d2 LDW *A4[9],A0`; called when clamped knob value changes)
  - `w10` (`+0x28`): `void (*on_change)(int new_val)` (`c01499ea LDW *A4[10],A0`; post-set apply/persist hook called immediately after `w9`)

### 4. Complete 16-Item Table Word Dump (`0xc0182b00..0xc0182dc0`, Verified Against `main.dis`)

| Page | Col | RAM Addr (`cinit` range) | `w0` (`+00`) | `w1` (`+04`) | `w2` (`+08`) | `w3` (`+0c` str1) | `w4` (`+10` str2) | `w5` (`+14` min) | `w6` (`+18` max) | `w7` (`+1c` fmt) | `w8` (`+20` get) | `w9` (`+24` set) | `w10` (`+28` hook) |
|---|---:|---|---:|---|---|---|---|---:|---:|---|---|---|---|
| **OUTPUT** | 0 | `c0182b00` (`c0185c6e..5c8c`) | `0` | `00000fff` | `00000fff` | `c01810d4` (`"Lo"`) | `00000000` | `0` | `100` (`0x64`) | `00000000` (`%d`) | `11805e48` | `11805bd4` | `00000000` |
| **OUTPUT** | 1 | `c0182b2c` (`c0185c8d..5cae`) | `1` | `00000fff` | `00000fff` | `c01810d7` (`"MID"`) | `00000000` | `0` | `100` (`0x64`) | `00000000` (`%d`) | `11805e38` | `11805bc4` | `00000000` |
| **OUTPUT** | 2 | `c0182b58` (`c0185caf..5cd0`) | `2` | `00000fff` | `00000fff` | `c01810db` (`"Hi"`) | `00000000` | `0` | `100` (`0x64`) | `00000000` (`%d`) | `11805e54` | `11805be8` | `00000000` |
| **OUTPUT** | 3 | `c0182b84` (`c0185cd1..5cf2`) | `3` | `00000fff` | `00000fff` | `c01810de` (`"MVOL"`) | `00000000` | `0` | `120` (`0x78`) | `00000000` (`%d`) | `11805ef8` | `11805cc4` | `00000000` |
| **SETUP** | 0 | `c0182bb0` (`c0185cf2..5d14`) | `0` | `00000fff` | `00000fff` | `c0180690` (`"BPM"`) | `00000000` | `40` (`0x28`) | `250` (`0xfa`) | `00000000` (`%d`) | `11805e64` | `00000000` | `c016716c` |
| **SETUP** | 1 | `c0182bdc` (`c0185d15..5d3e`) | `1` | `00000fff` | `00000fff` | `c0180694` (`"AUTO"`) | `c0180699` (`"SAVE"`) | `0` | `1` | `c0167178` (`OFF/ON`) | `11805ec4` | `c0168488` | `00000000` |
| **SETUP** | 2 | `c0182c08` (`c0185d3f..5d69`) | `2` | `00000fff` | `00000fff` | `c018069e` (`"PRE-"`) | `c01806a3` (`"SELECT"`) | `0` | `1` | `c0167178` (`OFF/ON`) | `11805e2c` | `11805bb0` | `c0167160` |
| **SETUP** | 3 | `c0182c34` (`c0185d6a..5d93`) | `3` | `00000fff` | `00000fff` | `c01806aa` (`"BANK"`) | `c01806af` (`"HOLD"`) | `0` | `1` | `c0167178` (`OFF/ON`) | `11805f30` | `11805d0c` | `00000000` |
| **PWR/LCD** | 0 | `c0182c60` (`c0185d93..5db5`) | `0` | `00000fff` | `00000fff` | `c01806bc` (`"BATTERY"`) | `00000000` | `0` | `1` | `c0163230` (`ALKALI/Ni-MH`) | `11805f24` | `11805cf8` | `00000000` |
| **PWR/LCD** | 1 | `c0182c8c` (`c0185db6..5ddc`) | `1` | `00000fff` | `00000fff` | `c01806c4` (`"ECO"`) | `00000000` | `0` | `1` | `c016320c` (`OFF/ON`) | `11805eb4` | `11805c68` | `c01631ac` |
| **PWR/LCD** | 2 | `c0182cb8` (`c0185ddd..5e07`) | `3` | `00000fff` | `00000fff` | `c01806c8` (`"BACK-"`) | `c01806ce` (`"LIGHT"`) | `0` | `3` | `c01631d4` (`OFF/ON/15s/30s`) | `11805f08` | `11805cd4` | `c01631ca` |
| **PWR/LCD** | 3 | `c0182ce4` (`c0185e08..5e2d`) | `2` | `00000fff` | `00000fff` | `c01806d4` (`"CONTRAST"`) | `00000000` | `1` | `13` (`0x0d`) | `00000000` (`%d`) | `c0163200` | `c01631a0` | `c01631b8` |
| **TUNER** | 0 | `c0182d10` (`c0185e30..5e53`) | `0` | `00000fff` | `00000fff` | `c0180910` (`"OUTPUT"`) | `00000000` | `0` | `1` | `c0159134` (`BYPASS/MUTE`) | `11805dcc` | `11805b30` | `c01591cc` |
| **TUNER** | 1 | `c0182d3c` (`c0185e54..5e7a`) | `1` | `00000fff` | `00000fff` | `c0180917` (`"CALIB"`) | `00000000` | `0` | `10` (`0x0a`) | `c0159198` (`435Hz..445Hz`) | `11805de8` | `c0168434` | `c0159354` |
| **TUNER** | 2 | `c0182d68` (`c0185e7b..5ea0`) | `2` | `00000fff` | `00000fff` | `c018091d` (`"TYPE"`) | `00000000` | `0` | `6` | `c0159120` | `11805dc0` | `c0168400` | `00000000` |
| **TUNER** | 3 | `c0182d94` (`c0185ea1..5ec6`) | `3` | `00000fff` | `00000fff` | `c0180922` (`"FLAT"`) | `00000000` | `0` | `3` | `c0159160` (`OFF/x1/x2/x3`) | `11805dd8` | `c01591ac` | `00000000` |

- **Column Center X-Coordinate Tables** (4 words each in `sc016f780`, passed in `A6` to `c0154564`, verified in `main.dis`):
  - `TUNER` (`0xc01814e8`, `c0159240 MVK 0x14e8,B10`): `{0x11 (17), 0x30 (48), 0x50 (80), 0x72 (114)}`
  - `OUTPUT` (`0xc0181548`, `c016a990 MVK 0x1548,A6`): `{0x11 (17), 0x30 (48), 0x4f (79), 0x6e (110)}`
  - `SETUP` (`0xc0181558`, `c0167208 MVK 0x1558,A6`): `{0x11 (17), 0x30 (48), 0x4f (79), 0x6e (110)}`
  - `PWR/LCD` (`0xc0181568`, `c01632c4 MVK 0x1568,A6`): `{0x12 (18), 0x32 (50), 0x4f (79), 0x6e (110)}`
- **Value-to-Text Formatter Details (`w7`, Confirmed)**:
  - `c0167178` (`AUTO SAVE`, `PRE-SELECT`, `BANK HOLD`): `CMPGTU 2,A4,A0; ADDAW 0xc0181848,A4,A0` -> `"OFF"\0` (`0xc0181848`), `"ON"\0\0` (`0xc018184c`).
  - `c0163230` (`BATTERY`): `CMPGTU 2,A4,A0; ADD (A4*7),0xc0181658,A0` -> `"ALKALI"\0` (`0xc0181658`), `"Ni-MH"\0\0` (`0xc018165f`).
  - `c016320c` (`ECO`): `CMPGTU 2,A4,A0; ADDAW 0xc0181800,A4,A0` -> `"OFF"\0` (`0xc0181800`), `"ON"\0\0` (`0xc0181804`).
  - `c01631d4` (`BACKLIGHT`): `CMPGTU 4,A4,A0; ADD (A4*7),0xc0180ff8,A0` -> 7-byte stride at `0xc0180ff8`: `"OFF"`, `"ON"`, `"15s"`, `"30s"`.
  - `c0159198` (`CALIB`): `ADD (A4*7),0xc017f8f0,A4` -> 7-byte stride at `0xc017f8f0` (`"435Hz"`..`"445Hz"`).
  - `c0159160` (`FLAT`): `ADD (A4*7),0xc0181018,A0` (when `c016ef20()` != 0) or `"---"` (`0xc0180927`) -> 7-byte stride at `0xc0181018` (`" x0"`, `" x1"`, `" x2"`, `" x3"`).


## A2. Draw Routine(s) and Task/Caller Chain

### 1. Caller Chain from `UpdateUI` (`c013c754`) to Menu Page Renderers (Confirmed)
```
UpdateUI task loop (c013c754)
 ├─ Event_pend(*+B14[139], 0, 0xff, -1)             [c013c76c CALLP.S2 0xc0144580,B3]
 └─ Bit 0 redraw / post-event handler: c013c6f8(A4) [c013c8d8 CALLP.S2 0xc013c6f8,B3]
     ├─ Clear ctx 0 framebuffer: c011f8d8(0, 1)     [c013c714 CALLP.S2 0xc011f8d8,B3]
     ├─ Get top-level UI mode: c0156e80() -> 7      [c013c720 CALLP.S2 0xc0156e80,B3]
     ├─ Locked UI dispatch: c013c0c8(A11, ui_mode)  [c013c724 CALLP.S2 0xc013c0c8,B3]
     │   ├─ Lock *+B14[155]: c0150b20               [c013c0d0 CALLP.S2 0xc0150b20,B3]
     │   ├─ Table dispatcher: c013c060(A4, B4, 0)   [c013c0da CALLP.S2 0xc013c060,B3]
     │   │   └─ .switch 0xc018439c[B4] (B4=4 or 7)  [c013c08c LDW *B5[B4],B0; BNOP B0,5]
     │   │       └─ c013c090 -> c013bfe0(A10)       [c013c090 CALLP.S2 0xc013bfe0,B3]
     │   │           └─ Active screen draw: c0149a68[c013bfe4 CALLP.S2 0xc0149a68,B3]
     │   │               └─ desc = *+B14[120]; desc->w6(A4) [c0149a7a LDW *B4[6],B0; B.S2 B0]
     │   └─ Unlock *+B14[155]: c01628e0             [c013c0e8 CALLP.S2 0xc01628e0,B3]
     ├─ Status/overlay pass: c013c0f4()             [c013c72a CALLP.S2 0xc013c0f4,B3]
     ├─ LCD SPI flush under GateMutex *+B14[149]:
     │   ├─ GateMutex_enter: c0161200(*+B14[149])   [c013c72c CALLP.S2 0xc0161200,B3]
     │   ├─ Flush ctx 0: c016df00(0)                [c013c740 CALLP.S2 0xc016df00,B3]
     │   └─ GateMutex_leave: c016d880(*+B14[149])   [c013c744 CALLP.S2 0xc016d880,B3]
     └─ Post-render poll: c013c4e4()                [c013c74e CALLP.S2 0xc013c4e4,B3]
         └─ If c0156e80()==7: c0149724() -> desc->w7() [c013c530 CALLP.S2 0xc0149724,B3]
```
- **Relation to `c01595e4` (`ONDEVICE_UI_RECON_REPORT.md`)**: In `c013c060`, jump table `0xc018439c` has 8 entries (`B4 = 0..7`, `c013c074 CMPLTU.L2 0x7,B10,B0`):
  - `B4 = 1` (`0xc01843a0 -> c013c0b2 -> c013c02c`) calls `c01595e4(0)` (the PC MODE / full-screen selector).
  - `B4 = 4` (`0xc01843ac`, TUNER UI mode) and `B4 = 7` (`0xc01843b8`, SETTINGS/MENU UI mode) both jump to `c013c090 -> c013bfe0 -> c0149a68`, which dispatches through the active 9-word screen descriptor at `*+B14[120]`.
- **Secondary callers of `c013c060`**:
  - `c013c54c` (`c013c568 CALLP.S2 0xc013c0c8,B3`): full clear + draw + flush helper called on mode transitions.
  - `c013c948` (`c013c950 CALLP.S2 0xc013c060,B3`): called during `SETTING` top-menu icon selection animation (`c0157a64 CALLP.S2 0xc013c948,B3`).

### 2. Menu Page Draw Routines (`c0154564` -> `c0154338` + `c013a7b4`, Confirmed)
- **Per-page `w6` (`draw`) wrappers** call `c0154564(A4=num_items, B4=item_table, A6=x_table, B6=title_str, A8=label_font_sel, B8=val_font_sel)`:
  - `SETUP` (`c01671f6`): `c0154564(4, 0xc0182bb0, 0xc0181558, 0xc01806b4 /*"SETUP"*/, 0, 1)` (`c0167210 CALLP.S2 0xc0154564,B3`)
  - `PWR/LCD` (`c01632b2`): `c0154564(4, 0xc0182c60, 0xc0181568, 0xc01806dd /*"PWR/LCD"*/, 0, 1)` (`c01632cc CALLP.S2 0xc0154564,B3`)
  - `TUNER` (`c0159234`): `c0154564(4, 0xc0182d10, 0xc01814e8, 0xc018092b /*"TUNER"*/, 0, 1)` (`c0159254 CALLP.S2 0xc0154564,B3`), followed by tuner meter/pitch rendering (`c015926c..c0159350`).
  - `OUTPUT` (`c016a97a`): `c0154564(4, 0xc0182b00, 0xc0181548, 0xc01810e3 /*"OUTPUT"*/, 1, 1)` (`c016a998 CALLP.S2 0xc0154564,B3`).
- **`c0154564` (`c0154564..c0154580`)**:
  1. Calls **`c0154338(A4=num_items, B4=item_table, A6=x_table, B6=A8, A8=B8)`** (`c0154570 CALLP.S2 0xc0154338,B3`).
  2. Calls **`c013a7b4(A4=0, B4=title_str)`** (`c0154574 CALLP.S2 0xc013a7b4,B3`), which draws `title_str` centered at `(x=64, y=0)` via `c013a710` and inverts the top title bar `(0,0)..(127,6)` via `c011cb64(0, 0, 0, 127, 6)` (`c013a7c8`).
- **`c0154338` (`c0154338..c0154560`, 4-Column Item Loop)**:
  - Queries active screen ID via `c01497f4()` into `A14` (`c0154350`).
  - Loops `A12 = num_items` times (`c0154360..c0154554`), stepping `A10 += 44` (`0x2c`, `c015453a MVK.S1 44,A0`) and `A11 += 4` (`c0154540 ADD.S1 4,A1,A0`).
  - **Horizontal centering helper `c01542f0(A4=str, B4=pitch_minus_1, A6=center_x)`**: computes `strlen(str)` (`c0154304 SPLOOPW 6`), returns `A4 = center_x - ((len * (B4 + 1) - 1) >> 1)`.
  - **Item label rendering (`c0154360..c0154432`)**:
    - If `B10 == 0` (`SETUP`, `PWR/LCD`, `TUNER`): uses **3x5 font primitive `c011e700(ctx=0, B4=str, A6=x, B6=y)`** (`pitch=4`, `B4=3` to `c01542f0`):
      - Single-line (`w4 == 0`): draws `w3` at `y = 11` if `A14 == 9` (`TUNER`, `c0154398..c01543a4 MVK.L2 11,B6`), else at `y = 13` (`c0154388..c0154390 MVK.L2 13,B6`).
      - Two-line (`w4 != 0`): centers on `w4` (`c01543ac`), draws `w3` at `y = 9` (`c01543b8..c01543c6`) and `w4` at `y = 15` (`c01543cc..c01543d4`).
    - If `B10 != 0` (`OUTPUT`): uses **5x7 font primitive `c011d4d8(ctx=0, B4=str, A6=x, B6=y)`** (`pitch=6`, `B4=5` to `c01542f0`), drawing single-line at `y = 12` (`c01543f4..c0154402`) or two-line at `y = 7` and `y = 15` (`c0154414..c0154430`).
  - **Item value rendering (`c0154432..c0154534`)**:
    - Loads `w8` (`*A10[8]`, `get_val`); if `NULL`, skips value (`c0154440` / `c01544c2`).
    - Calls `w8()` -> `A4 = raw_val`.
    - If `w7` (`*A10[7]`, `val_to_str`) is `NULL`: formats `c016a100(sp+16, 20, "%d" /*0xc018178c*/, raw_val)` (`c0154468` / `c01544e8`).
    - If `w7` is non-NULL: calls `w7(raw_val)` -> `str_ptr`, formats `c016a100(sp+16, 20, "%s" /*0xc018178f*/, str_ptr)` (`c0154494` / `c0154514`).
    - When `A15 != 0` (`B8 = 1`, true for all 4 menu pages): centers `sp+16` with `c01542f0(sp+16, 5, center_x)` (`c0154524`) and draws at **`y = 24`** with **`c011d4d8(0, sp+16, x, 24)`** (`c015452c CALLP.S2 0xc011d4d8,B3`). (If `A15 == 0`, draws at `y = 24` with 3x5 font `c011e700` at `c01544ac`.)


## A3. Item Current Value Storage (Global Struct / Offsets)

## A4. Free / Unused Room and Repurposing Candidates

## Cross-Findings (B1-B4 Notes Discovered Along the Way)
