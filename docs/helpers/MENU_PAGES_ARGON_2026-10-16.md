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

## P5. Our Own 4-Item Page (Constructor `c0154564`, Descriptor, Formatter `w7`, OUTPUT Example)

## Recommended Design (Entry Control + Hook List)
