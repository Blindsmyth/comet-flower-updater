# Zoom G1X Four Extra Settings Pages RE — Argon Report (2026-10-16)

## Summary
*(Work in progress — offline analysis only.)*

## P1. Entry to the Alternate Chooser (Screen ID 1 vs ID 0)

### 1. Every Code Path Calling `c0149664` or `c01496d0` (Confirmed)
`c0149664(int screen_id)` is the sole function that writes the active screen descriptor pointer `*+B14[120]` (`c0149698: 0000787c STW.D2T1 A0,*+B14[120]`). Across the entire firmware (`build/fw/map/main.dis`), `c0149664` has **10 call sites** in 8 functions, and `c01496d0` has **1 call site**:

| # | Call Site & Instruction Word | Caller Function | `A4` (`screen_id`) Passed | Target Screen / Role |
|---:|---|---|---|---|
| 1 | `c0138c74: 10214092 CALLP.S2 0xc0149664,B3` | `c0138c34` (called from `SAVE`/`SWAP` event handler `c0139404` at `c0139458` on Knob 1 `ev->w0 == 25`) | `7` (`c0138c70: 021ca358 MVK.L1 7,A4`) or `8` (`c0138c6e: 0e26 MVK.L1 8,A4`) | Toggles between `7` (`SAVE`) and `8` (`SWAP`) when turning Knob 1 |
| 2 | `c01496b6: fc5b CALLP.S2 0xc0149664,B3` | `c01496b4` (called only from `c0156e4c: 1fe50e92 CALLP.S2 0xc01496b4,B3` at boot/UI init `c0156e08`) | `2` (`c01496b8: 4626 \|\| MVK.L1 2,A4`) | Initializes `*+B14[120]` to `2` (`TEMPO`) at boot |
| 3 | `c01496d2: fa5b CALLP.S2 0xc0149664,B3` | `c01496d0` (called only from `c0156de0: 1fe51e12 CALLP.S2 0xc01496d0,B3`, case `4` of `c0156d68` at `0xc018436c`) | `0x0fff` (`c01496d4: 0207ffa8 \|\| MVK.S1 0x0fff,A4`) | Clears `*+B14[120]` to `NULL` (runs old `w5` exit callback if any) |
| 4 | `c01496d8: fa5b CALLP.S2 0xc0149664,B3` | `c01496d0` (immediately after `c01496d2` when entering `ui_mode = 4`) | `0` (`c01496da: 0626 \|\| MVK.L1 0,A4`) | Enters **Screen ID `0`** (`SETTING` Chooser List A, `0xc01833dc`) |
| 5 | `c0149a34: c45b \|\| CALLP.S2 0xc0149664,B3` | `c0149a0c` (called only from `c0156dc4: 1fe58992 CALLP.S2 0xc0149a0c,B3`, case `7` of `c0156d68` at `0xc0184378`) | `0x0fff` (`c0149a30: 0207ffa9 MVK.S1 0x0fff,A4`) | Saves previous screen ID to `*0xc010ad0c` (`c0149a10`), clears `*+B14[120]` |
| 6 | `c0149a36: c45b CALLP.S2 0xc0149664,B3` | `c0149a0c` (immediately after `c0149a34` when entering `ui_mode = 7`) | `13` (`c0149a38: ae26 \|\| MVK.L1 13,A4`) | Enters **Screen ID `13`** (`EDITED! SAVE?` dialog, `0xc018371c`) |
| 7 | `c0149ac4: ba5b CALLP.S2 0xc0149664,B3` | `c0149a90` (page stepper, called only from `c0164870`) | Computed `2..12` (`c0149ab0 CMPGT.L1 2,A4,A0` .. `c0149ab8 CMPLT.L1 12,A4,A0`) | Steps screen ID by `+1`/`-1`, clamped to `[2, 12]` (never `0` or `1`) |
| 8 | `c01577f8: 1fe3d093 CALLP.S2 0xc0149664,B3` | `c01577c8` (called from `EDITED! SAVE?` event handler `c0157838` at `c015786c`) | `14` (`c0157800: ce26 \|\| MVK.L1 14,A4`) | Enters **Screen ID `14`** (`SAVE` confirmation variant, `0xc0183224`) |
| 9 | `c0157964: 1fe3a093 CALLP.S2 0xc0149664,B3` | `c0157954` (called only from `c0156cf8: 10018e92 CALLP.S2 0xc0157954,B3` when leaving `ui_mode = 7`) | `*0xc010ad0c` (`c0157968: 004c \|\| LDW.D1T1 *A4[0],A4`) | Restores screen ID saved by `c0149a0c -> c0157944` before `EDITED! SAVE?` |
| 10 | `c0157b24: 1fe36893 CALLP.S2 0xc0149664,B3` | `c0157ae8` (called from chooser `c0157bac` at `c0157be0` on slot button release) | `*+A5[A4]` (`c0157b28: 02148a64 \|\| LDW.D1T1 *+A5[A4],A4`) | Enters `ListA[0..4] = {4,6,7,10,11}` or `ListB[0..4] = {5,9,3,8,12}` |

### 2. Is Screen ID 1 Ever Reachable in Stock Firmware? (Confirmed: No)
- Although `c01495c0(1)` dispatches via `0xc0184140` (`c0149650: 101cc092 CALLP.S2 0xc0157c44,B3`) to return Screen Descriptor `1` (`0xc0183400`), **no code path in `main.elf` ever passes `A4 = 1` to `c0149664`** or writes `0xc0183400` to `*+B14[120]`.
- Consequently, **Screen ID `1` (`0xc0183400`, List B chooser) and Screen ID `5` (`0xc0183740`, `OUTPUT` 4-item page, which only appears in List B `0xc0181368[0]`) are completely unreachable in stock firmware.**

### 3. How `c0157c0c` and `c0157bac` Pick List A vs List B, and Adding a Third List (Confirmed)
- Both the chooser draw routine **`c0157c0c`** and the chooser button-release handler **`c0157ae8`** (called by `c0157bac`) query the active screen ID by calling **`c01497f4()`** (which reads `w0` of `*+B14[120]`: `c01497f4 LDW.D2T1 *+B14[120],A0; c0149802 LDW.D2T1 *B4[0],A0`) and compare it against `1`:
  - **In `c0157c0c` (draw)**:
    ```
    c0157c10   1fe37e92           CALLP.S2      0xc01497f4,B3
    c0157c14   00103a5a           CMPEQ.L2X     1,A4,B0
    c0157c1a       7446           MV.L1X        B0,A11
    c0157c24       dadb           CALLP.S2      0xc01579cc,B3   ; A4=slot(0..4), B4=A11(is_id_1), A6=0
    ```
    Inside `c01579cc`:
    ```
    c01579d2       0247 ||        MV.L2         B4,B0
    c01579d4   00002a5a           CMPEQ.L2      1,B0,B0
    c01579d8   3018a120    [!B0]  BNOP.S1       0xc01579f0,5
    c01579e4   0209b428           MVK.S1        0x1368,A4       ; B4 == 1 -> List B (0xc0181368)
    ...
    c01579f0   0209a828           MVK.S1        0x1350,A4       ; B4 != 1 -> List A (0xc0181350)
    ```
  - **In `c0157ae8` (slot button release)**:
    ```
    c0157af0   1fe3a292           CALLP.S2      0xc01497f4,B3
    c0157af4   00103a5a           CMPEQ.L2X     1,A4,B0
    c0157af8   200aa120    [ B0]  BNOP.S1       0xc0157b08,5
    c0157b00   0509a828           MVK.S1        0x1350,A10      ; A4 != 1 -> List A (0xc0181350)
    ...
    c0157b08   0509b428           MVK.S1        0x1368,A10      ; A4 == 1 -> List B (0xc0181368)
    ```
    `c0157ae8` then calls `c0157a38(slot, B0)` (`c0157b12`, which animates the pressed icon via `c01579cc`) and `c0149664(A10[slot])` (`c0157b24`).
- **Could a third list be added the same way?**
  - Because `c01579cc` and `c0157ae8` hardcode a boolean `CMPEQ 1` check in flash, a new descriptor with `w0 = 2` or `w0 = 15` that merely points `w6 = c0157c0c` and `w8 = c0157bac` would take the `!= 1` branch and display List A (`0xc0181350`).
  - However, **Screen ID `1`'s descriptor (`0xc0183400`) is in writable `.cinit` RAM**, and if we want either a customized List B or N lists:
    - Since `0xc0181368` (`List B`) is in `.const` flash (`sc016f780`), Screen ID `1` as-is already gives us **Slot 0 -> Screen ID `5` (`OUTPUT`)**!
    - Or, if we ever want custom 5-icon chooser lists beyond List A, a custom chooser descriptor (or overwriting `0xc0183400->w6` and `w8` in RAM) can provide tiny C wrappers that draw 5 icons via `c0149ad4` + `c011c508` + `c0157bf0` and dispatch `c0149664(custom_list[ev->w2])`.


## P2. Unused Input in the SETTING Chooser (`c0157bac` & `c0149840`)

## P3. Page Stepping (`c0149a90`)

## P4. Adding Screen IDs >= 15 (`c01495c0` and Screen-ID Assumptions)

## P5. Our Own 4-Item Page (Constructor `c0154564`, Descriptor, Formatter `w7`, OUTPUT Example)

## Recommended Design (Entry Control + Hook List)
