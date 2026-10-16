# USB-Audio Mode Button & Switch Analysis (2026-10-16)

## Summary
*(To be completed at the end, <= 15 lines)*

## A2. Switch Scan & Bit-to-GPIO Mapping (`c0156f00` and helpers)

### 1. Low-Level GPIO Pin Reader (`0x11809484`) — **Confirmed**
- `0x11809484` validates `0 <= pin < 128`, loads the GPIO MMIO base pointer from `*(u32 *)0x11813214` (`0x01e26000`), computes bank `b = pin >> 5`, bank offset `b * 40` (`0x28`), and bit `pin & 0x1f`, then reads `IN_DATA` at `*(base + b * 0x28 + 0x20)` (`118094b2 LDW.D1T1 *A5[8],A0`) and returns `(IN_DATA >> (pin & 0x1f)) & 1` (1 = released/high, 0 = pressed/low):
  ```text
  11809494   02990a28           MVK.S1        0x3214,A5
  11809498   0288c0e8           MVKH.S1       0x11810000,A5
  118094a0       008c           LDW.D1T1      *A5[0],A0
  118094a2       be0b ||        SHR.S2X       A4,0x5,B0
  118094a4       a41b           SHL.S2        B0,0x5,B1
  118094a6       6403           SHL.S2        B0,0x3,B0
  118094a8   0000207a           ADD.L2        B1,B0,B0
  118094ac   00937b08           EXTU.S1       A4,27,27,A1
  118094b0       1050           ADD.L1X       A0,B0,A5
  118094b2       088c           LDW.D1T1      *A5[8],A0
  118094b6       3462           SHRU.S1       A0,A1,A0
  118094b8       f802           EXTU.S1       A0,31,31,A0
  ```

### 2. Ten-Button Bitmap Reader `READ_SWITCHES` (`0xc0156f00`) & Footswitch Reader (`0xc0157034`) — **Confirmed**
- `0xc0156f00(u32 *out)` zeros `*out` (`c0156f08 STW.D1T2 B0,*+A4[0]`) and populates bits `0..9` (active-low: `1` = released, `0` = pressed) via veneers `0xc016f1d0` (`-> 0x11809530`), `0xc016f1c0` (`-> 0x11809540`), `0xc016f1b0` (`-> 0x11809524`), and `0xc016f1a0(0..6)` (`-> 0x118094c4`):
  ```text
  c0156f0c   10305a12           CALLP.S2      0xc016f1d0,B3   ; bit 0 <- 11809530 (GPIO 4)
  c0156f2c   10305412           CALLP.S2      0xc016f1c0,B3   ; bit 1 <- 11809540 (GPIO 2)
  c0156f48   10304e12           CALLP.S2      0xc016f1b0,B3   ; bit 2 <- 11809524 (GPIO 6)
  c0156f64   10304813           CALLP.S2      0xc016f1a0,B3   ; bit 3 <- 118094c4(0) (GPIO 27)
  c0156f84   10304413           CALLP.S2      0xc016f1a0,B3   ; bit 4 <- 118094c4(1) (GPIO 24)
  c0156fa0   10304013           CALLP.S2      0xc016f1a0,B3   ; bit 5 <- 118094c4(2) (GPIO 26)
  c0156fc0   10303c12 ||        CALLP.S2      0xc016f1a0,B3   ; bit 6 <- 118094c4(3) (GPIO 37)
  c0156fd8   10303c13           CALLP.S2      0xc016f1a0,B3   ; bit 7 <- 118094c4(4) (GPIO 38)
  c0156ff8   10303812 ||        CALLP.S2      0xc016f1a0,B3   ; bit 8 <- 118094c4(5) (GPIO 86)
  c0157014   10303413           CALLP.S2      0xc016f1a0,B3   ; bit 9 <- 118094c4(6) (GPIO 0)
  ```
- `0x118094c4(int idx)` maps `idx = 0..6` to GPIO pin numbers `{27, 24, 26, 37, 38, 86, 0}`:
  ```text
  118094c8   9021a120    [!A1]  BNOP.S1       0x11809502,5    ; idx 0 -> MVK 27,A4 (11809502)
  118094d2       1812           MVK.S1        24,A0           ; idx 1 -> 24
  118094da       5812           MVK.S1        26,A0           ; idx 2 -> 26
  118094e6       a032           MVK.S1        37,A0           ; idx 3 -> 37
  118094ee       c032           MVK.S1        38,A0           ; idx 4 -> 38
  118094f6       d052           MVK.S1        86,A0           ; idx 5 -> 86
  118094f8       0426           MVK.L1        0,A0            ; idx 6 (default) -> 0
  ```
- `0xc0157034(u32 *out)` reads the 2 footswitches into bits `0..1` via veneer `0xc016f340(0..1)` (`-> 0x1180954c`), which selects GPIO **3** (`A4 == 0`) and GPIO **5** (`A4 != 0`).
- Scanner task `0x118076c0` polls `0xc0156f00` every 16 ms (`118076f8 CALLP 0x1180b700`), debounces into `0x1181330c`, and for each changed bit `b` (`0..9`) posts raw event `5 + 2*b` on press (`bit == 0`) or `6 + 2*b` on release (`bit == 1`) (`11807734..11807750`). Footswitch scanner `0x11807858` polls `0xc0157034` (`118078a4 CALLP 0x1180b6b0`) and posts `2*f` (press) / `2*f + 1` (release) for `f = 0..1` (`11807968..118079a0`).
- Event normalizer `0xc015350c` populates the 4-word event struct `ev[0..3]` (`ev[0] = id`, `ev[1] = prev_id`, `ev[2] = param`, `ev[3] = 0`). Notably, for events `11..20` (bits `3..7`), `0xc015355a..0xc015358a` sets `ev[2] = (id - 11) >> 1` (`0..4`, the effect slot index `0..4`), whereas for bits `0..2` (`5..10`) and bits `8..9` (`21..24`), `ev[2]` is `1` on press and `0` on release (`0xc0184034..0xc0184058`).

| Control Group | Bitmap / Index | Veneer -> L2 Reader | GPIO Pin # | C6748 Bank/Pin | Press Event | Release Event | `ev[2]` (`c015350c`) |
|---|---|---|---|---|---|---|---|
| Footswitch 0 | FS bit 0 (`0x001`) | `c016f340(0)` -> `1180954c` | **GPIO 3** | `GP0[3]` | **0** | **1** | `0` (FS index 0) |
| Footswitch 1 | FS bit 1 (`0x002`) | `c016f340(1)` -> `1180954c` | **GPIO 5** | `GP0[5]` | **2** | **3** | `1` (FS index 1) |
| Button bit 0 (B1) | SW bit 0 (`0x001`) | `c016f1d0` -> `11809530` | **GPIO 4** | `GP0[4]` | **5** | **6** | `1` (press) / `0` (rel) |
| Button bit 1 (B2) | SW bit 1 (`0x002`) | `c016f1c0` -> `11809540` | **GPIO 2** | `GP0[2]` | **7** | **8** | `1` (press) / `0` (rel) |
| Button bit 2 (B3) | SW bit 2 (`0x004`) | `c016f1b0` -> `11809524` | **GPIO 6** | `GP0[6]` | **9** | **10** | `1` (press) / `0` (rel) |
| Button bit 3 (B4) | SW bit 3 (`0x008`) | `c016f1a0(0)` -> `118094c4` | **GPIO 27** | `GP1[11]` | **11** | **12** | `0` (Slot 1 index) |
| Button bit 4 (B5) | SW bit 4 (`0x010`) | `c016f1a0(1)` -> `118094c4` | **GPIO 24** | `GP1[8]` | **13** | **14** | `1` (Slot 2 index) |
| Button bit 5 (B6) | SW bit 5 (`0x020`) | `c016f1a0(2)` -> `118094c4` | **GPIO 26** | `GP1[10]` | **15** | **16** | `2` (Slot 3 index) |
| Button bit 6 (B7) | SW bit 6 (`0x040`) | `c016f1a0(3)` -> `118094c4` | **GPIO 37** | `GP2[5]` | **17** | **18** | `3` (Slot 4 index) |
| Button bit 7 (B8) | SW bit 7 (`0x080`) | `c016f1a0(4)` -> `118094c4` | **GPIO 38** | `GP2[6]` | **19** | **20** | `4` (Slot 5 index) |
| Button bit 8 (B9) | SW bit 8 (`0x100`) | `c016f1a0(5)` -> `118094c4` | **GPIO 86** | `GP5[6]` | **21** | **22** | `1` (press) / `0` (rel) |
| Button bit 9 (B10) | SW bit 9 (`0x200`) | `c016f1a0(6)` -> `118094c4` | **GPIO 0** | `GP0[0]` | **23** | **24** | `1` (press) / `0` (rel) |

## A1. Stock Main-Screen Button Event Actions (Events 0..28) & Power-Up Combo Safety

### 1. Power-Up Button Combination Checks (`res5` `0xc020a4d0` & Main Firmware `0xc0140c8c`) — **Confirmed**
- **Bootloader / `res5` (`0xc020a4d0`, `recon/25_boot_safety.md`)**:
  - Enters USB Firmware Update Mode (`0xc0201404`) **only** when both footswitches (GPIO 5 and GPIO 3) read low (`0`, pressed) **and** all 10 buttons (GPIOs `{0, 27, 24, 26, 37, 38, 86, 2, 4, 6}`) read high (`1`, released). Holding any single panel button at power-up (with footswitches released) goes straight to normal boot (`0xc020a568 -> 0xc022ba40`).
- **Main Firmware Startup Check (`0xc0140c8c`, called at `0xc013420c` inside `MainApp` init `0xc01341e4` *before* `0xc0134e14`)**:
  - `0xc0140c8c` assembles a **12-bit** active-low bitmap `A7` (`0x0fff` when all 12 controls are released; note that its bit order differs from `READ_SWITCHES` at bits 5..11 because `c016f1a0(6)` is placed at bit 5 before `c016f1a0(0..5)` at bits 6..11):
    - `A7` bit 0 (`0x001`): FS 0 (`c016f340(0)`, GPIO 3)
    - `A7` bit 1 (`0x002`): FS 1 (`c016f340(1)`, GPIO 5)
    - `A7` bit 2 (`0x004`): SW bit 0 (`c016f1d0`, GPIO 4, events 5/6)
    - `A7` bit 3 (`0x008`): SW bit 1 (`c016f1c0`, GPIO 2, events 7/8)
    - `A7` bit 4 (`0x010`): SW bit 2 (`c016f1b0`, GPIO 6, events 9/10)
    - `A7` bit 5 (`0x020`): SW bit 9 (`c016f1a0(6)`, GPIO 0 = Rhythm, events 23/24)
    - `A7` bit 6..10 (`0x040..0x400`): SW bits 3..7 (`c016f1a0(0..4)`, GPIOs 27, 24, 26, 37, 38 = Effect Slots 1..5, events 11..20)
    - `A7` bit 11 (`0x800`): SW bit 8 (`c016f1a0(5)`, GPIO 86, events 21/22)
  - `0xc0140dc0..0xc0140e10` searches the 6-entry `{handler, mask}` table at `0xc0180570..0xc018059c` for an exact `A7 == mask` match:
    ```text
    c0180570   c01406a0  00000aff   ; ~0x500 (A7 bits 8,10 = SW bits 5+7, Slots 3+5) -> "Off Mode entrance"
    c0180578   c0140740  00000d7f   ; ~0x280 (A7 bits 7,9  = SW bits 4+6, Slots 2+4) -> "Switch to OFF mode."
    c0180580   c0140a30  00000ff7   ; ~0x008 (A7 bit 3     = SW bit 1, GPIO 2 ALONE) -> "ALL INITIALIZE" (Factory Reset!)
    c0180588   c014cef4  00000ffb   ; ~0x004 (A7 bit 2     = SW bit 0, GPIO 4 ALONE) -> factory/test task c014d138 (if *0x1181348c != 0)
    c0180590   c01408cc  000003ff   ; ~0xc00 (A7 bits 10,11= SW bits 7+8, Slot 5 + bit 8) -> "CheckSum" screen
    c0180598   c01407b0  00000fdf   ; ~0x020 (A7 bit 5     = SW bit 9, GPIO 0 Rhythm ALONE) -> "VERSION" screen (waits for FSW)
    ```
  - **Power-up safety consequences**:
    - **SW bit 1 (GPIO 2, events 7/8) is UNSAFE**: holding it alone at power-up (`0x0ff7`) triggers `0xc0140a30` (`"ALL INITIALIZE / Are you sure? / FSW:ENTER"`), blocking normal boot in the factory reset prompt.
    - **SW bit 0 (GPIO 4, events 5/6) has a stock entry (`0x0ffb -> 0xc014cef4`)**: gated on `0xc016f730()` (`*(u32 *)0x1181348c != 0`); best avoided if completely clean buttons exist.
    - **SW bit 9 (GPIO 0, Rhythm, events 23/24) is already used by MIDI mode AND triggers `0xc01407b0` (`"VERSION"` screen)** at `0xc013420c` (requiring a footswitch press before `MainApp` reaches `0xc0134e14`).
    - **Completely free of any single-button power-up action in both `res5` and `0xc0140c8c`**:
      - **SW bit 2 (GPIO 6, events 9/10)**: not in `0xc0180570` at all (neither single nor combo).
      - **SW bits 3..7 (GPIOs 27, 24, 26, 37, 38, events 11..20, Effect Slot 1..5 buttons)**: only appear in 2-button combos in `0xc0180570`, never as a single button.
      - **SW bit 8 (GPIO 86, events 21/22)**: only appears in the 2-button combo `SW bit 7 + SW bit 8` (`0x03ff`), never as a single button.

