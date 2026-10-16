# Zoom G1X Four Extra Settings Pages RE — Argon Report (2026-10-16)

## Summary
- **P1 (Alternate Chooser `ID 1` & `OUTPUT` `ID 5`)**: `c0149664` has 10 call sites; none ever pass `A4 = 1`. Screen ID `1` (`0xc0183400`, List B `{5,9,3,8,12}`) and Screen ID `5` (`0xc0183740`, `OUTPUT`) are completely dormant in stock firmware. Both `c0157c0c` (draw) and `c0157ae8` (slot release) select List B iff `c01497f4() == 1`.
- **P2 (Unused Chooser Inputs)**: `c0157bac` ignores all events outside `6..20` (`c0157bb4 CMPLTU 0xe,A0,A0`). **`<`/`>` Arrow buttons (`21..24`)**, **Knobs `1..4` (`25..28`)**, and **Footswitches (`0..4`)** return `0` with zero side effects in `ui_mode == 4` (avoid Event `9`, caught by `c0134ba8`).
- **P3 (Page Stepper `c0149a90`)**: Called only once (`c0164870`, Knob 1 on legacy `TEMPO` `ID 2`); clamps `screen_id +/- 1` to `[2, 12]`. Do not use for chooser flipping; call `c0149664(target_id)` directly.
- **P4 (`ID >= 15` & `.cinit` RAM Shortcuts)**: `c01495c0` bounds-checks `A4 > 14` against `.switch` table `0xc018413c`; its calls inside `c0149664` (`f61b`) and `c0149ad4` (`b01b`) are 16-bit compact. However, descriptors `0` (`0xc01833dc`), `1` (`0xc0183400`), and `5` (`0xc0183740`) live in **writable `.fardata` RAM**, and the chooser's icon/transition calls (`c0157a00: 1fe41a93`, `c0157b24: 1fe36893`) are 32-bit `CALLP`s!
- **P5 (`OUTPUT` `0xc0183740` & `c0154564`)**: `w4, w5, w7` can be `0`; `w6` calls `c0154564(4, recs, 0xc0181548, title, label_font, val_font)`. Catch: `OUTPUT`'s stock `w8` (`c016a95a`) hardcodes EQ (`c012f900`), so point `0xc0183740->w8` (`0xc0183760`) to `c0149948(4, ev, 0xc0182b00)`. `w7` strings `<= 5` chars (`"FX"`, `"MIDI"`, `"USB"`) fit `y=24` cleanly.

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

### 1. Complete Event ID Producer & Physical Control Map (Confirmed for Code/GPIOs; Panel Legends Tagged)
Events are popped in `MainApp` (`c0134dd0: 103ce993 CALLP.S2 0xc015350c,B3`) into a 16-byte struct `ev` at `B15+4`: `{w0: event_id, w1: prev_event_id, w2: param_or_delta, w3: extra}`.

| Event ID (`w0`) | Producer Routine | `ev->w2` (`*B4[2]`) Unpacked by `c015350c` | Physical Control (Confidence) | Stock Role in Stomp (`c01308e4`) / Menu |
|---|---|---|---|---|
| `0`, `1` | `11807858` (`11807968..79a0`, `c0157034 -> c016f340(0)`) | `1` on press (`0`), `0` on release (`1`) (`c015366c`, `c0153654`) | Footswitch A (GPIO 3; confirmed GPIO, side unverified) | Stomp patch/effect footswitch |
| `2`, `3` | `11807858` (`11807968..79a0`, `c0157060 -> c016f340(1)`) | `1` on press (`2`), `0` on release (`3`) (`c015366c`, `c0153654`) | Footswitch B (GPIO 5; confirmed GPIO, side unverified) | Stomp patch/effect footswitch |
| `4` | `11807858` (`11807a22..7a30`, `\|\|t0 - t1\|\| <= 100` ms) | `1` (`c0153722`) | Both Footswitches together (confirmed) | Enters Tuner/Bypass (`c01307b8`) |
| `5`, `6` | `118076c0 -> c0156f00` bit 0 (`c016f1d0`, GPIO 4) | `1` on `5` (press), `0` on `6` (release) (`c01536e0`, `c01536d4`) | **`SETTINGS` (Menu) button** (confirmed by `c0130748` -> `ui_mode=4`) | Enters/exits `SETTING` menu on `6` |
| `7`, `8` | `118076c0 -> c0156f00` bit 1 (`c016f1c0`, GPIO 2) | `1` on `7` (press), `0` on `8` (release) (`c01536e0`, `c01536d4`) | **Memory / Stomp button** (likely legend; confirmed `ui_mode` `0<->1` toggle at `c01306ec`/`c0148fd6`) | Exits `SETTING` chooser on `7` (`c0157b44`) |
| `9`, `10` | `118076c0 -> c0156f00` bit 2 (`c016f1b0`, GPIO 6) | `1` on `9` (press), `0` on `10` (release) (`c01536e0`, `c01536d4`) | **Rhythm / Looper button** (likely; intercepted globally after screen dispatch at `c0134ba8`) | Post-dispatch `c0134a58 -> c014ada8` |
| `11`, `12` | `118076c0 -> c0156f00` bit 3 (`c016f1a0(0)`, GPIO 27) | `0` (Slot index 0, `c0153716`) | **Effect Slot 1 button** (confirmed, `x=2`) | Chooser Slot 0 (`CHAIN` / `OUTPUT`) |
| `13`, `14` | `118076c0 -> c0156f00` bit 4 (`c016f1a0(1)`, GPIO 24) | `1` (Slot index 1, `c015370c`) | **Effect Slot 2 button** (confirmed, `x=27`) | Chooser Slot 1 (`PATCH` / `TUNER`) |
| `15`, `16` | `118076c0 -> c0156f00` bit 5 (`c016f1a0(2)`, GPIO 26) | `2` (Slot index 2, `c0153702`) | **Effect Slot 3 button** (confirmed, `x=53`) | Chooser Slot 2 (`SAVE` / `ID 3`) |
| `17`, `18` | `118076c0 -> c0156f00` bit 6 (`c016f1a0(3)`, GPIO 37) | `3` (Slot index 3, `c01536f4`) | **Effect Slot 4 button** (confirmed, `x=77`) | Chooser Slot 3 (`SETUP` / `SWAP`) |
| `19`, `20` | `118076c0 -> c0156f00` bit 7 (`c016f1a0(4)`, GPIO 38) | `4` (Slot index 4, `c01536ea`) | **Effect Slot 5 button** (confirmed, `x=102`) | Chooser Slot 4 (`PWR/LCD` / `VERSION`) |
| `21`, `22` | `118076c0 -> c0156f00` bit 8 (`c016f1a0(5)`, GPIO 86) | `1` on `21` (press), `0` on `22` (release) (`c018404c..050`) | **`<` (Left Arrow) button** (confirmed by `c01305d0 -> c012fbe0(0)`) | Scrolls effect chain left in Stomp mode |
| `23`, `24` | `118076c0 -> c0156f00` bit 9 (`c016f1a0(6)`, GPIO 0) | `1` on `23` (press), `0` on `24` (release) (`c0184054..058`) | **`>` (Right Arrow) / boot-hold button** (confirmed by `c01305b8 -> c012fbe0(1)`) | Scrolls effect chain right in Stomp mode |
| `25`..`28` | `11807774 -> c0169520` (`ADD A4,0x19,A4`) | Signed encoder delta from `0x11813430[0..3]` (`c0153634 CALLP 0xc0169554`) | **Knobs 1..4** (confirmed) | Edits 4 menu columns via `c0149948` |
| `29`..`32` | `11809d40` (`11809eb4 ADD A0,0x1d,A4`) | `0` on `29,31`, `1` on `30,32` (`c018405c..068`) | Key-repeat events (`31,32` = `<`/`>` repeat in `c0139414`, `c0130918`) | Auto-repeat when holding `<` / `>` |
| `33`..`44` | `11809d40` / `1180a838` / `c01537ba` | `0` or `1` (`c0153690..6b4`) | Repeats (`33..38`), timer/sys (`39..40`), redraw (`41`), expr/null (`42`), battery (`43`) | System / background events |

### 2. What `c0149840` and `c0157bac` Handle vs. Ignore in the `SETTING` Chooser (Confirmed)
1. **Generic Menu Event Dispatcher (`c0149840`, called from `MainApp` `c0134b44` for `ui_mode` `4` and `7`)**:
   - If `c0156e80() == 7` (`c0149850`): filters slot-button presses `11,13,15,17,19` (sets `0xc01152e0[slot] = 1` at `c01498b4`) and releases `12,14,16,18,20` (requires `0xc01152e0[slot] != 0` at `c0149896`, else drops event). When `c0156e80() == 4`, jumps straight to `c01498b8`.
   - Tracks `SETTINGS` button press (`ev->w0 == 5` sets `*+B14[23] = 1` at `c01498e8`) so the initial release of `SETTINGS` (`ev->w0 == 6` with `*+B14[23] == 0` after `c01496d0` cleared `*+B14[23]` at `c0149714`) is swallowed at `c01498d8`.
   - Calls `c014980c(ev)` (`ev->w0 == 6 || ev->w0 == 7`): if true, calls `c0149820()`, which checks `c01497f4()` (`screen_id`). **For Screen IDs `0`, `1`, and `9`, `c0149820()` returns `0`** (`c0149824 CMPLTU.L1 1,A4,A0; c014982c CMPEQ.L1 9,A1,A0`), so `c0149840` does **not** intercept `6`/`7` and instead forwards **every event** to `(*+B14[120])->w8(ev)` at `c0149910`!
2. **Chooser Event Handler `c0157bac` (used by Screen ID `0` and Screen ID `1`)**:
   ```
   c0157bae       001c           LDW.D1T1      *A4[0],A1
   c0157bb2       4c80           ADD.L1        A1,-6,A0
   c0157bb4   0001cbd8           CMPLTU.L1     0xe,A0,A0       ; (ev->w0 - 6) > 14 ?
   c0157bb8   c01ca120    [ A0]  BNOP.S1       0xc0157bd8,5    ; outside 6..20 -> return 0!
   ```
   Via jump table `0xc0184178..0xc01841b0` (`15` words for `ev->w0 = 6..20`):
   - **Handled (`return 1` or transition)**:
     - `ev->w0 == 6` (`SETTINGS` release): `0xc0184178 -> c0157be8 -> c0157b6c` (exits menu to previous mode via `c0156e8c`).
     - `ev->w0 == 7` (`Memory/Stomp` press): `0xc018417c -> c0157be4 -> c0157b44` (exits menu to previous mode via `c0156e8c`).
     - `ev->w0 == 12, 14, 16, 18, 20` (Effect Slot 1..5 button releases): `0xc0184190..41b0 -> c0157be0 -> c0157ae8` (opens `ListA[slot]` or `ListB[slot]`).
   - **Ignored inside `c0157bac` (`return 0` at `c0157bd8`, no side effects in `MainApp`)**:
     1. **Left / Right Arrow Buttons (`<` / `>`)**: **`ev->w0 == 21` (Left `<` press), `22` (Left `<` release), `23` (Right `>` press), `24` (Right `>` release)**, and repeats **`31, 32`**.
     2. **Knobs 1..4**: **`ev->w0 == 25, 26, 27, 28`** (`ev->w2` = signed encoder delta `< 0` or `> 0`).
     3. **Footswitches**: **`ev->w0 == 0, 1, 2, 3, 4`**.
     4. **Effect Slot 1..5 button presses**: **`ev->w0 == 11, 13, 15, 17, 19`** (only used to arm `0xc01152e0[slot]` when `ui_mode == 7`).
     5. **Event `8` (`Memory/Stomp` release) and Event `10` (`Rhythm` release)**. (Note: Event `9` `Rhythm` press is ignored by `c0157bac`, and `MainApp` `c0134ba8 -> c0134a58 -> c014ada8` checks `c014ad4c`, which returns `1` when `ui_mode == 4` and `screen_id` is not `7, 8, 14` (`c014ad6a..ad8e`), triggering Rhythm exit/toggle! So **do not** use Event `9` in the chooser.)
   - **Best candidates for "next/previous settings page" in the chooser**:
     - **`<` / `>` Arrow buttons (`ev->w0 == 21` for prev, `ev->w0 == 23` for next)**, or **Knob 1..4 rotation (`ev->w0 == 25..28`, `ev->w2 < 0` for prev, `ev->w2 > 0` for next)**, or **Footswitches (`ev->w0 == 0` / `2`)**. All three are 100% dead/ignored in the `SETTING` chooser and in `MainApp`'s post-dispatch when `ui_mode == 4`.


## P3. Page Stepping (`c0149a90`)

### 1. Complete Disassembly & Behavior of `c0149a90` (Confirmed)
```
c0149a90       31f7           STW.D2T2      B3,*B15--[2]
c0149a92       2246           MV.L1         A4,A1             ; A1 = step direction arg (signed int)
c0149a94   1fffae92           CALLP.S2      0xc01497f4,B3     ; A4 = current screen_id (or 0x0fff if NULL)
c0149a98   0007ffa8           MVK.S1        0x0fff,A0
c0149a9c   0c6e               NOP           1
c0149aa0       8468           CMPEQ.L1      A4,A0,A0          ; current screen_id == 0x0fff ?
c0149aa2       a56a    [ A0]  BNOP.S1       0xc0149aca,5      ; if no active screen, return 0
c0149aa4       10a6           CMPLT.L1      0,A1,A0           ; A0 = (0 < A1) ? 1 : 0
c0149aa6       632a    [!A0]  BNOP.S1       0xc0149aac,3      ; if A1 <= 0, branch to -1
c0149aa8       2426           MVK.L1        1,A0              ; A1 > 0 -> step = +1
c0149aaa       200b           BNOP.S1       0xc0149aae,1
c0149aac       fc26           MVK.L1        -1,A0             ; A1 <= 0 -> step = -1
c0149aae       0240           ADD.L1        A0,A4,A4          ; A4 = screen_id +/- 1
c0149ab0   001048d8           CMPGT.L1      2,A4,A0           ; 2 > A4 ? (i.e. A4 < 2)
c0149ab4       a33a    [!A0]  BNOP.S1       0xc0149ab8,5
c0149ab6       4626           MVK.L1        2,A4              ; clamp lower bound to 2 (TEMPO)
c0149ab8   00118ad8           CMPLT.L1      12,A4,A0          ; 12 < A4 ? (i.e. A4 > 12)
c0149abc   0c6e               NOP           1
c0149ac0       a0ba    [!A0]  BNOP.S1       0xc0149ac4,5
c0149ac2       8e26           MVK.L1        12,A4             ; clamp upper bound to 12 (VERSION)
c0149ac4       ba5b           CALLP.S2      0xc0149664,B3     ; transition to screen_id A4 (2..12)
c0149ac6       2246           MV.L1         A4,A1
c0149ac8       2426           MVK.L1        1,A0              ; return 1
c0149aca       0020           MV.L1         A0,A4
c0149acc       3177           LDW.D2T2      *++B15[2],B3
c0149ace       6c6e           NOP           4
c0149ad0       a1ef           BNOP.S2       B3,5
```

### 2. Every Caller of `c0149a90` (Confirmed: Exactly 1 Caller)
- Across the entire firmware (`build/fw/map/main.dis`), `c0149a90` is called from **only one site**:
  - **`c0164870: 1fca4613 CALLP.S2 0xc0149a90,B3`** (`c0164874: 404c || LDW.D1T1 *A4[2],A4`) inside **`c0164850`**, which is `w8` (`on_event`) of **Screen ID `2` (`TEMPO`, descriptor `0xc01836b0`)**:
    ```
    c0164850       31f7           STW.D2T2      B3,*B15--[2]
    c0164852       001c           LDW.D1T1      *A4[0],A1         ; A1 = ev->w0
    c0164854       3812           MVK.S1        25,A0             ; Event 25 = Knob 1
    c0164856       0c6e           NOP           1
    c0164858       2468           CMPEQ.L1      A1,A0,A0          ; ev->w0 == 25 ?
    c016485a       a62a    [ A0]  BNOP.S1       0xc0164870,5      ; Knob 1 -> call c0149a90(ev->w2)
    c016485c       3a12           MVK.S1        26,A0             ; Event 26 = Knob 2
    ...
    c0164870   1fca4613           CALLP.S2      0xc0149a90,B3
    c0164874       404c ||        LDW.D1T1      *A4[2],A4         ; A4 = ev->w2 (Knob 1 signed delta)
    ```
- **Context**: Screen ID `2` (`TEMPO`) is an unreferenced debug/legacy screen (initialized at boot via `c01496b4 -> c0149664(2)`, before `ui_mode` enters Stomp/Memory, and its draw function `c01648fa` draws a `1..11` page indicator via `c0164920: 1fdbe292 CALLP.S2 0xc01542c8,B3` using `w0 - 1`). On that legacy `TEMPO` screen, turning Knob 1 stepped sequentially through Screen IDs `2..12`.

### 3. Can `c0149a90` Serve Page Flipping for Us? (Confirmed: Better to Call `c0149664` Directly)
- `c0149a90` cannot flip between Chooser List A (`0`) and List B (`1`), nor can it reach IDs `>= 15`, because it hard-clamps `A4` to `[2, 12]` (`c0149ab0..c0149ac2`). Moreover, stepping sequentially across `2..12` walks right through `SAVE` (`7`), `SWAP` (`8`), `TUNER` (`9`), and `CHAIN` (`4`).
- Instead, our C handler should call **`c0149664(target_screen_id)`** directly (which is a single function call to `0xc0149664` and takes any arbitrary target screen ID).


## P4. Adding Screen IDs >= 15 (`c01495c0` and Screen-ID Assumptions)

### 1. Disassembly of `c01495c0` & Switch Table `0xc018413c` (Confirmed)
```
c01495c0   01bc54f6           STW.D2T2      B3,*B15--[2]
c01495c4   0011cbd8           CMPLTU.L1     0xe,A4,A0          ; 14 < (uint32_t)screen_id ?
c01495c8   c010a120    [ A0]  BNOP.S1       0xc01495e0,5       ; if screen_id > 14 -> return NULL (0)
c01495cc   02a09e28           MVK.S1        0x413c,A5
c01495d0   02e00c68           MVKH.S1       0xc0180000,A5      ; A5 = 0xc018413c (15-word .switch table)
c01495d4       854c           LDW.D1T1      *A5[A4],A0         ; A0 = switch_table[screen_id]
c01495d6       6c6e           NOP           4
c01495d8       116b           BNOP.S1       A0,5               ; branch to case handler
c01495da       0c6e           NOP           1
c01495dc   0c6e               NOP           1
c01495e0       0626           MVK.L1        0,A4               ; out-of-range (> 14) -> A4 = NULL
c01495e2       3177           LDW.D2T2      *++B15[2],B3
c01495e4       6c6e           NOP           4
c01495e6       a1ef           BNOP.S2       B3,5
```
- **The 15-entry `.switch` table at `0xc018413c..0xc0184174` (in `.switch:sc0184000`, read-only flash)**:
  - `0xc018413c` (`ID 0`): `0xc0149658` -> `CALLP 0xc0157c38` -> `0xc01833dc` (`SETTING` Chooser List A)
  - `0xc0184140` (`ID 1`): `0xc0149650` -> `CALLP 0xc0157c44` -> `0xc0183400` (`SETTING` Chooser List B)
  - `0xc0184144` (`ID 2`): `0xc0149648` -> `CALLP 0xc0164934` -> `0xc01836b0` (`TEMPO`)
  - `0xc0184148` (`ID 3`): `0xc0149640` -> `CALLP 0xc01658e4` -> `0xc01836f8` (Custom `c016578c` screen)
  - `0xc018414c` (`ID 4`): `0xc0149638` -> `CALLP 0xc01511c4` -> `0xc01833b8` (`CHAIN`)
  - `0xc0184150` (`ID 5`): `0xc0149630` -> `CALLP 0xc016a9ac` -> `0xc0183740` (`OUTPUT`)
  - `0xc0184154` (`ID 6`): `0xc0149628` -> `CALLP 0xc0142f2c` -> `0xc0183394` (`PATCH`)
  - `0xc0184158` (`ID 7`): `0xc0149620` -> `CALLP 0xc0139540` -> `0xc018326c` (`SAVE`)
  - `0xc018415c` (`ID 8`): `0xc0149618` -> `CALLP 0xc0139534` -> `0xc0183248` (`SWAP`)
  - `0xc0184160` (`ID 9`): `0xc0149610` -> `CALLP 0xc0159264` -> `0xc0183424` (`TUNER`)
  - `0xc0184164` (`ID 10`): `0xc0149608` -> `CALLP 0xc016724c` -> `0xc0183764` (`SETUP`)
  - `0xc0184168` (`ID 11`): `0xc0149600` -> `CALLP 0xc01632c8` -> `0xc018368c` (`PWR/LCD`)
  - `0xc018416c` (`ID 12`): `0xc01495f8` -> `CALLP 0xc016ab44` -> `0xc01837f4` (`VERSION`)
  - `0xc0184170` (`ID 13`): `0xc01495f0` -> `CALLP 0xc0157934` -> `0xc018371c` (`EDITED! SAVE?`)
  - `0xc0184174` (`ID 14`): `0xc01495e8` -> `CALLP 0xc0139528` -> `0xc0183224` (`SAVE` from `EDITED! SAVE?`)

### 2. Every Call Site of `c01495c0` in the Firmware (Confirmed: 5 Sites)
| # | Address & Instruction Word | Form / Parallel Bit | Caller Function | `A4` Passed | Role |
|---:|---|---|---|---|---|
| 1 | `c0149668: f61b CALLP.S2 0xc01495c0,B3` | **16-bit compact** (`f61b`, paired with `c014966a: 4646 MV.L1 A4,A10`, `.fphead c0149660`) | `c0149664` (screen transition) | `screen_id` | Looks up new descriptor for `*+B14[120]` |
| 2 | `c0149758: 1fffd012 \|\| CALLP.S2 0xc01495c0,B3` | 32-bit `CALLP`, **parallel bit = `0`** (parallel with `c0149756: 2e26 MVK.L1 9,A4`, `.fphead c014975c`) | `c0149750` (Tuner `w8` wrapper) | Hardcoded `9` | Calls `c01495c0(9)->w8(ev)` |
| 3 | `c0149776: e61b CALLP.S2 0xc01495c0,B3` | **16-bit compact** (`c0149778: 2e26 \|\| MVK.L1 9,A4`) | `c0149770` (Tuner `w4` wrapper) | Hardcoded `9` | Calls `c01495c0(9)->w4()` |
| 4 | `c0149796: e41b CALLP.S2 0xc01495c0,B3` | **16-bit compact** (`c0149798: 2e26 \|\| MVK.L1 9,A4`) | `c0149794` (Tuner `w6` wrapper) | Hardcoded `9` | Calls `c01495c0(9)->w6(1)` |
| 5 | `c0149ada: b01b CALLP.S2 0xc01495c0,B3` | **16-bit compact** (`b01b`, paired with `c0149adc: 8247 MV.L2 B4,B0`, `.fphead c0149ae0`) | `c0149ad4` (icon bitmap selector `w1..w3`) | `screen_id` | Looks up descriptor to return `w1` (`B4==0`), `w2` (`B4==1`), or `w3` (`B4==2`) |

### 3. Every Table Indexed by `screen_id` & Every Check on `c01497f4()` / `(*+B14[120])->w0` (Confirmed)
- **Tables indexed by `screen_id`**:
  - **Only `0xc018413c..0xc0184174` inside `c01495c0`!** No other array, bitmap table, or jump table in the entire firmware is indexed by `screen_id`.
- **All 9 Callers of `c01497f4()` + 2 Direct Readers of `(*+B14[120])->w0`**:
  1. `c01497b0` (`c01497c0: 0004 LDW.D2T2 *B4[0],B0; c01497c6: 836a CMPEQ.L2 6,B0,B0`): checks `w0 == 6` (`PATCH`). Safe for `>= 15`.
  2. `c01497d0` (`c01497e0: 0004 LDW.D2T2 *B4[0],B0; c01497e6: 836a CMPEQ.L2 6,B0,B0`): checks `w0 == 6` (`PATCH`). Safe for `>= 15`.
  3. **`c0149820`** (`c0149822 CALLP 0xc01497f4; c0149824: 00103bd8 CMPLTU.L1 1,A4,A0; c014982c: 00049a58 CMPEQ.L1 9,A1,A0`):
     - Returns `0` for `w0` in `{0, 1, 9}` (chooser or tuner) and **`1` for all other IDs (including `>= 15`)**.
     - In `c0149840`, when `c0149820()` returns `1`, pressing `SETTINGS` (`ev->w0 == 6`) or `Memory` (`ev->w0 == 7`) automatically calls `c01498f8 -> c0149924 -> c0156e8c` to exit the subpage! Thus **any subpage with `w0 >= 15` (or `w0 = 5`) automatically gets stock `SETTINGS`/`Memory` exit behavior for free!**
  4. `c0149a0c` (`c0149a0e: 1fff7b12 CALLP.S2 0xc01497f4,B3`): saves `w0` into `*0xc010ad0c` before `EDITED! SAVE?`. Safe for `< 15`; if `>= 15`, `c0157954 -> c0149664` restores via `c0149664`.
  5. `c0149a90` (`c0149a94: 1fffae92 CALLP.S2 0xc01497f4,B3`): only called on Screen ID `2`.
  6. `c014ad4c` (`c014ad78: 1ffb5392 CALLP.S2 0xc01497f4,B3`): checks `w0` in `{7, 8, 14}` (`SAVE`/`SWAP`); returns `1` for all other IDs. Safe for `>= 15`.
  7. `c0154338` (`c0154350: 1feaa292 CALLP.S2 0xc01497f4,B3; c0154398: 00393a58 CMPEQ.L1 9,A14,A0`): checks `w0 == 9` (`TUNER` label `y=11` vs standard `y=13`). Safe for `>= 15` (uses `y=13`).
  8. `c0157ae8` (`c0157af0: 1fe3a292 CALLP.S2 0xc01497f4,B3`) & `c0157b2c` (`1fe39392 CALLP.S2 0xc01497f4,B3`): checks `w0 == 1` and new `w0 == 7`. Safe for `>= 15`.
  9. `c0157b6c` (`c0157b70: 1fe39292 CALLP.S2 0xc01497f4,B3`): ignores return value. Safe.
  10. `c0157c0c` (`c0157c10: 1fe37e92 CALLP.S2 0xc01497f4,B3`): checks `w0 == 1`. Safe.
- **Screen Redraw (`UpdateUI`: `c013c754 -> c013c0c8 -> c013c060 -> c013bfe0 -> c0149a68`)**:
  - `c0149a68` (`c0149a70: 0000786e LDW.D2T2 *+B14[120],B0; c0149a7a: c084 LDW.D2T2 *B4[6],B0; c0149a80: 00000062 B.S2 B0`) **never inspects `w0` (`screen_id`) at all** — it simply calls `(*+B14[120])->w6(1)`!

### 4. How to Add Custom Pages (Both `< 15` and `>= 15`) (Confirmed)
- **Important instruction-encoding catch**: Inside `c0149664` (`c0149668: f61b`) and `c0149ad4` (`c0149ada: b01b`), the `CALLP.S2 0xc01495c0,B3` instructions are **16-bit compact instructions**, not 32-bit `CALLP` words.
- We have two clean, verified ways to add custom pages without ever touching a 16-bit instruction:
  1. **Zero-Extension Route (Reuse Existing Screen IDs `1` and `5`, or `2, 3, 8, 12`)**:
     - Screen ID `1` (`0xc0183400`, Chooser List B) and Screen ID `5` (`0xc0183740`, `OUTPUT` 4-item page) are already `< 15`, already in `0xc018413c`, and **both descriptors (`0xc0183400` and `0xc0183740`) reside in writable `.cinit` RAM**!
     - Even better: if we want **every slot (`0..4`) of Screen ID `1`** to open our own custom pages (up to 5 custom pages on Chooser Page 2, or unlimited pages by paging!), we can either overwrite `w6`/`w8` of the target descriptors in RAM (`0xc0183740` for Slot 0 `ID 5`, `0xc01836f8` for Slot 2 `ID 3`, etc.) **or** hook the single 32-bit `CALLP` in `c0157ae8` (`c0157b24: 1fe36893 CALLP.S2 0xc0149664,B3`, parallel bit = `1`) and the single 32-bit `CALLP` in `c01579cc` (`c0157a00: 1fe41a93 CALLP.S2 0xc0149ad4,B3`, parallel bit = `1`).
  2. **Unlimited Screen IDs `>= 15` Route (via C Transition Helper + `*+B14[120]`)**:
     - What `c0149664(id)` actually does (`c0149664..c01496ae`) is just 10 lines of logic:
       1. Look up `new_desc` (for `id < 15`, `c01495c0(id)`; for `id >= 15`, `our_desc_table[id - 15]`).
       2. If `old_desc = *(screen_desc_t **)(B14 + 0x1e0)` (`*+B14[120]`) is non-NULL and `old_desc->w5` is non-NULL, call `old_desc->w5()`.
       3. Write `*(screen_desc_t **)(B14 + 0x1e0) = new_desc`.
       4. If `new_desc != NULL`: if `new_desc->w4 != NULL`, call `new_desc->w4()`; then call `c0139fd8(1)` (request UI redraw).
     - And for chooser icons (`c0149ad4`), its **only caller in the entire firmware** is the 32-bit `CALLP` at **`c0157a00: 1fe41a93 CALLP.S2 0xc0149ad4,B3`** (parallel bit = `1`).


## P5. Our Own 4-Item Page (Constructor `c0154564`, Descriptor, Formatter `w7`, OUTPUT Example)

### 1. Screen Descriptor Layout (`w0..w8`, 36 Bytes) — Worked Example: `OUTPUT` (`0xc0183740`) (Confirmed)
`c016a9ac` returns `0xc0183740` (initialized from `.cinit` `0xc01865eb` into writable `.fardata` RAM):

| Word / Offset | Value in `OUTPUT` (`0xc0183740`) | Can Be `0` (`NULL`)? | Verification & Role |
|---|---|---|---|
| `w0` (`+0x00`) | `0x00000005` (`5`) | Any int (`!= 0, 1, 9` for subpage) | `screen_id`. For any value not in `{0, 1, 9}`, `c0149820()` returns `1` so `SETTINGS` (`6`) and `Memory` (`7`) automatically exit the page (`c01498f8 -> c0149924`). |
| `w1` (`+0x04`) | `0xc017ea88` | Non-NULL if shown in chooser | 24x30 icon bitmap type `0` (normal), returned by `c0149ad4(id, 0)` (`c0149af0`). |
| `w2` (`+0x08`) | `0xc017e788` | Non-NULL if shown in chooser | 24x30 icon bitmap type `1` (inverted/pressed), returned by `c0149ad4(id, 1)` (`c0149afc`). |
| `w3` (`+0x0c`) | `0xc017e488` | Non-NULL if shown in chooser | 24x30 icon bitmap type `2` (frame), returned by `c0149ad4(id, 2)` (`c0149b08`). |
| `w4` (`+0x10`) | `0xc016a978` (`a1ef BNOP.S2 B3,5`) | **Yes (`0` allowed, confirmed)** | `on_enter()` callback. `c01496a4: 204c LDW.D1T1 *A4[4],A0; c01496aa: a2ba [!A0] BNOP.S1 0xc01496b0,5` skips call if `0` (already `0` in descriptors `0, 1, 2`). |
| `w5` (`+0x14`) | `0x00000000` | **Yes (`0` allowed, confirmed)** | `on_exit()` callback. `c0149686: a004 LDW.D2T2 *B4[5],B0; c014968c: a33b [!B0] BNOP.S1 0xc0149694,5` skips call if `0` (`0` in `OUTPUT`, `SETUP`, `PWR/LCD`). |
| `w6` (`+0x18`) | `0xc016a97a` | **No (must be non-NULL)** | `draw(int flag)` callback (`A4=1`), called unconditionally by `c0149a68` (`c0149a7a: c084 LDW.D2T2 *B4[6],B0; c0149a80: B.S2 B0`). |
| `w7` (`+0x1c`) | `0xc016a940` (`CALLP 0xc0160e74`, no-op) | **Yes (`0` allowed, confirmed)** | `on_poll()` callback. `c0149732: e004 LDW.D2T2 *B4[7],B0; c0149738: c011a120 [!B0] BNOP.S1 0xc014974c,5` skips call if `0` (already `0` in descriptor `2`). |
| `w8` (`+0x20`) | `0xc016a95a` | **Yes (`0` allowed, non-NULL for knobs)** | `on_event(event_t *ev)` callback (`c0149904: 0004 LDW.D2T2 *B4[8],B0; [!B0] skip`). **Crucial catch on `OUTPUT`'s stock `w8` (`c016a95a`)**: see Section 2 below! |

### 2. Crucial Catch on `OUTPUT` (`0xc0183740`) `w8` vs. `SETUP`/`PWR/LCD` `w8` (Confirmed)
- In **`SETUP`** (`0xc0183764`, `w8 = c01671ac`) and **`PWR/LCD`** (`0xc018368c`, `w8 = c0163268`), `w8` delegates directly to the generic table-driven 4-knob event handler **`c0149948(int count /*A4*/, event_t *ev /*B4*/, const item_rec_t *records /*A6*/)`**:
  ```
  c01671ac   01bc54f6           STW.D2T2      B3,*B15--[2]
  c01671b0   03152a28           MVK.S1        0x2a54,A6
  c01671b4   03600c68           MVKH.S1       0xc0180000,A6      ; A6 = 0xc0182a54 (SETUP 4-item records)
  c01671b8   1fc4f293           CALLP.S2      0xc0149948,B3      ; generic 4-knob editor!
  c01671bc       8347 ||        MV.L2X        A4,B4              ; B4 = ev
  c01671be       8626 ||        MVK.L1        4,A4               ; A4 = 4 items
  ```
- By contrast, **`OUTPUT`'s stock `w8` (`c016a95a`) does NOT call `c0149948`!** Instead, `c016a95a` checks `25 <= ev->w0 <= 28` and calls `c016a94c(ev->w0 - 25, ev->w2) -> c012fb00 -> c012f900` (which hardcodes `Lo/MID/Hi/MVOL` via jump table `0xc0184504`), ignoring `0xc0182b00[i].w9` (`setter`) and `w8` (`getter`) on knob turns!
- **Fix**: When repurposing `OUTPUT` (`0xc0183740`) or creating any custom 4-item page, set `desc->w8` (`*(uint32_t *)0xc0183760`) to a 3-line C wrapper that calls **`c0149948(4, ev, records_ptr)`**. Then `c0149948` automatically:
  1. Checks `25 <= ev->w0 < 25 + count` (`col = ev->w0 - 25`).
  2. Checks `records[col].w0 == 1` (`enabled`) and `records[col].w9 != NULL` (`setter`) and `records[col].w8 != NULL` (`getter`).
  3. Computes `new_val = records[col].w8() + ev->w2`, clamps `new_val` to `[records[col].w1, records[col].w2]`, calls `records[col].w9(new_val)`, and calls `c0139fd8(1)` to redraw if changed!

### 3. Constructor `c0154564` Signature & Exact Arguments (`OUTPUT` `c016a97a` vs `SETUP` `c01671cc`) (Confirmed)
```
; OUTPUT draw callback w6 = c016a97a:
c016a97a       31f7           STW.D2T2      B3,*B15--[2]
c016a97c   0c6e               NOP           1
c016a980   030871aa           MVK.S2        0x10e3,B6
c016a984   0215802a ||        MVK.S2        0x2b00,B4
c016a988   0400005b ||        MVK.L2        1,B8
c016a98c   03600c6a           MVKH.S2       0xc0180000,B6        ; B6 = 0xc01810e3 ("OUTPUT")
c016a990   030aa429 ||        MVK.S1        0x1548,A6
c016a994   02600c6a ||        MVKH.S2       0xc0180000,B4        ; B4 = 0xc0182b00 (4 item records)
c016a998   1fd37c93           CALLP.S2      0xc0154564,B3        ; 32-bit CALLP, parallel bit = 1
c016a99c   042001f0 ||        MV.D1X        B8,A8                ; A8 = 1 (5x7 label font)
c016a9a0   03600c68 ||        MVKH.S1       0xc0180000,A6        ; A6 = 0xc0181548 (col center X[4])
c016a9a4       8626 ||        MVK.L1        4,A4                 ; A4 = 4 (item count)
```
- **Exact C Prototype of `c0154564`**:
  ```c
  void page_draw_4items(
      int              count,          // A4: number of columns (4)
      const item_rec_t *records,       // B4: array of `count` 44-byte (0x2c) item_rec_t structs
      const int32_t    *col_center_x,  // A6: 0xc0181548 -> {17, 48, 79, 110} (0x11, 0x30, 0x4f, 0x6e)
      const char       *title,         // B6: inverted top-bar title string (e.g. 0xc01810e3 "OUTPUT")
      int              label_font_sel, // A8: 0 = 3x5 font c011e700 (4 px pitch, supports 2-line w3+w4),
                                       //     1 = 5x7 font c011d4d8 (6 px pitch, single-line w3 at y=13)
      int              val_font_sel    // B8: 1 = 5x7 font c011d4d8 at y=24, 0 = 3x5 font c011e700 at y=24
  );
  ```
- **44-Byte (`0x2c`, 11-word) `item_rec_t` Layout (verified across `0xc0182b00..0xc0182bab` for `OUTPUT`, `0xc0182a54` for `SETUP`, `0xc018287c` for `PWR/LCD`)**:
  - `w0` (`+0x00`): `1` = enabled (active), `0` = blank/disabled column (`c015436e`, `c0149982`).
  - `w1` (`+0x04`): `int32_t min_val` (for `OUTPUT`: `0`; for enum `0..2`: `0`).
  - `w2` (`+0x08`): `int32_t max_val` (for `OUTPUT` `Lo/MID/Hi`: `0x1e` = `30`; `MVOL`: `0x64` = `100`; for 3-way enum: `2`).
  - `w3` (`+0x0c`): `const char *label_line1` (drawn at `y=13` if single-line, or `y=9` if `w4 != NULL` and `A8 == 0`).
  - `w4` (`+0x10`): `const char *label_line2` (`NULL` for single-line; drawn at `y=15` in 3x5 font when `A8 == 0`).
  - `w5` (`+0x14`): `0` (special flag: `1` only for Contrast icon `c01828b4`).
  - `w6` (`+0x18`): `0` (special flag: `1` only for Contrast/Eco `c01828d0/fc`).
  - `w7` (`+0x1c`): `const char *(*val_to_str)(int val)` (value string formatter).
  - `w8` (`+0x20`): `int (*getter)(void)` (returns current integer parameter value in `A4`).
  - `w9` (`+0x24`): `void (*setter)(int new_val)` (applies new clamped integer value in `A4`).
  - `w10` (`+0x28`): `const char *unit_suffix` (`NULL` for none; `"Hz"` on `TUNER` `0xc0181be4`).

### 4. Formatter `w7` Contract & Maximum String Length at `y = 24` (Confirmed)
- **How `c0154338` (`c0154474..c0154530`) calls `w7` and renders the value**:
  1. Calls `val = rec->w8()` (`c01544cc: 1094 LDW.D1T2 *A2[8],B0; c01544d4: CALLP B0,B3`).
  2. Calls `str = rec->w7(val)` (`c01544dc: f094 LDW.D1T2 *A2[7],B0; c01544fc: 01800062 ADDKPC.S2 0xc0154500,B3,0; B.S2 B0`).
  3. Checks `if (str != NULL)` (`c0154500: 2146 MV.L1 A4,A0; [!A0] skip`).
  4. Copies `str` into a **20-byte stack buffer at `B15 + 16`** via `c016a100(B15 + 16, 20, "%s", str)` (`c015450c: 1fd6fb93 CALLP.S2 0xc016a100,B3`, `B4 = 0x14 = 20`).
  5. Computes centered X coordinate via `c01542f0(B15 + 16, 5, col_center_x[i])` (`c0154518: 1ffff612 CALLP.S2 0xc01542f0,B3`):
     - `c01542f0` measures `len = strlen(buf)` (`c016be60`), computes `pixel_width = len * (5 + 1) - 1 = 6 * len - 1`, and returns `x = col_center_x[i] - (pixel_width >> 1)`.
  6. Draws `B15 + 16` at `(x, y = 24)` (`c0154524: 03000c2b MVK.S2 24,B6`) using 5x7 font `c011d4d8` (`c015452c: 1f924292 CALLP.S2 0xc011d4d8,B3`).
- **Return buffer requirement for our `w7`**:
  - Because `c015450c` immediately copies the returned `const char *` into its own stack buffer `B15 + 16`, our `w7(int val)` can return either a pointer to a static string literal (`"FX"`, `"MIDI"`, `"USB"`, `"OFF"`, `"ON"`) or a tiny static `char buf[8]` formatted by `c016a100` (`snprintf`, the same helper used by `OUTPUT`'s formatter `c015425c` with `0xc0183670`).
- **Maximum characters that fit cleanly at `y = 24`**:
  - Column centers are at `x = {17, 48, 79, 110}` (31 px center-to-center spacing; inner column frame is ~30 px wide).
  - With the 5x7 font (`c011d4d8`, 5 px glyph + 1 px spacing = 6 px/char):
    - **1..4 chars** (`5..23` px wide, e.g. `"FX"` = 11 px, `"USB"` = 17 px, `"MIDI"` = 23 px): **fits with 4..10 px margin per side**.
    - **5 chars** (`29` px wide): **maximum clean width** without touching column borders.
    - **6 chars** (`35` px wide, e.g. `"ALKALI"` in `SETUP` col 0 at `x=18`): slightly overhangs a 31 px cell by 2 px per side.
  - And for labels (`w3` at `y = 13`): if `A8 = 1` (5x7 font, like `OUTPUT`), keep `w3` `<= 5` chars; if `A8 = 0` (3x5 font `c011e700`, 4 px pitch, like `SETUP`), `w3` (and optional second line `w4`) can be up to **7 chars** (`7 * 4 - 1 = 27` px) per line!


## Recommended Design (Entry Control + Hook List)

### 1. Recommended Physical Control to Flip Chooser Pages
- **Primary recommendation**: **Left / Right Arrow buttons (`<` = `ev->w0 == 21`, `>` = `ev->w0 == 23`)** AND/OR **any Knob 1..4 turn (`ev->w0 == 25..28`, `ev->w2 < 0` vs `ev->w2 > 0`)** while on the `SETTING` chooser (`Screen ID 0` or `Screen ID 1`).
  - Both `<` / `>` (`21, 23`) and Knobs `1..4` (`25..28`) are **100% ignored** in `c0157bac` (`(ev->w0 - 6) > 14 -> return 0` at `c0157bb8`) and have zero side effects in `MainApp` when `ui_mode == 4`.
  - Supporting both `<` / `>` button presses and Knob 1..4 rotation in our chooser event wrapper takes 6 lines of C and feels completely natural on hardware (press `SETTINGS`, then press `>` or turn a knob to flip to the second chooser page, or press Slot 1..5 to open a page).

### 2. Minimal-Footprint Architecture: Reuse Dormant `.cinit` Descriptors (`ID 1` & `ID 5`) + Single 32-Bit `CALLP` Hook
Because the 36-byte Screen Descriptors for **Screen ID `0` (`0xc01833dc`)**, **Screen ID `1` (`0xc0183400`, Chooser List B)**, and **Screen ID `5` (`0xc0183740`, `OUTPUT` 4-item page)** (as well as `0xc0182b00`, `OUTPUT`'s 4x44-byte item record array) all reside in **writable `.fardata` RAM**, we do **not** need to patch any 16-bit instructions or relocate `.switch` tables:

| Component | Exact Address / Word in `main.dis` | Parallel Bit | Action in Our Patch |
|---|---|---|---|
| **Option A Hook (Menu Entry)** | `c0156de0: 1fe51e12 CALLP.S2 0xc01496d0,B3` | `0` (standalone) | Replace with `CALLP.S2 our_menu_enter_hook, B3`. Inside `our_menu_enter_hook()`: patch writable RAM tables (`0xc01833dc->w8`, `0xc0183400->w8`, `0xc0183740->w6/w8`, `0xc0182b00`) idempotently, then call stock `0xc01496d0()`. *(Alternatively, hook `c0134b44: 1029a013 CALLP.S2 0xc0149840,B3`, parallel bit `1`, or `c016a998: 1fd37c93 CALLP.S2 0xc0154564,B3`, parallel bit `1`.)* |
| **Chooser List A & B Event Pointer (`w8`)** | `*(uint32_t *)0xc01833fc` (`ID 0` `w8`) and `*(uint32_t *)0xc0183420` (`ID 1` `w8`) | Writable RAM | Point both to `our_chooser_on_event(event_t *ev)`: if `ev->w0 == 23` (`>`) or (`25..28` with `ev->w2 > 0`), call `c0149664(1)`; if `ev->w0 == 21` (`<`) or (`25..28` with `ev->w2 < 0`), call `c0149664(0)`; otherwise tail-call stock `c0157bac(ev)`. |
| **Custom 4-Item Page (`ID 5`, Slot 0 of List B)** | `0xc0183740` (`OUTPUT` descriptor in RAM) + `0xc0182b00` (`4 x 44B` records in RAM) | Writable RAM | Overwrite `0xc0182b00[0..3]` in RAM with our 4 custom items (`min`, `max`, `label`, `w7=val_to_str`, `w8=getter`, `w9=setter`), overwrite `*(uint32_t *)0xc0183758` (`w6`) if custom title/font is desired (calling `c0154564(4, 0xc0182b00, 0xc0181548, title, 0, 1)`), and overwrite `*(uint32_t *)0xc0183760` (`w8`) with `our_page5_on_event(ev)` calling `c0149948(4, ev, 0xc0182b00)`. |
| **Optional: Up to 5 Custom Pages on List B (or N Pages)** | `c0157a00: 1fe41a93 CALLP.S2 0xc0149ad4,B3` (p-bit `1`) & `c0157b24: 1fe36893 CALLP.S2 0xc0149664,B3` (p-bit `1`) | `1` (both) | If we ever want to customize all 5 slots of List B (or add `ID >= 15` pages), these two 32-bit `CALLP` sites are the only places where the chooser resolves a slot's `screen_id` to an icon (`c0149ad4`) or transitions to a subpage (`c0149664`). |

