# 5-Slot Effect Loop Analysis for Per-Slot USB Taps (2026-10-17)

## 1. Per-Slot Call Contract

### A. The 5-Slot Loop (`11818bd4`..`11818c40`) and the Two Per-Slot Helpers (`c014ff44` & `c01502cc`)

In `g_Swi_AudioProcess` (`11818ba0`..`11818c84`), the 5-slot effect loop spans `11818bd4`..`11818c40` (`main.dis` lines 18285-18315). A cycle-accurate trace of the branch delay slots reveals **two** veneer calls per slot iteration (`11818ec0` -> `c014ff44` and `11818eb0` -> `c01502cc`), followed by the indirect slot callback `BNOP.S2 B5,0` (`confirmed`):

```
11818bd4   0180a359           MVK.L1        0,A3
11818bd8   0000656e ||        LDW.D2T2      *+B14[101],B0       ; B0 = *(0xc0184e00 + 101*4 = 0xc0184f94)
11818bdc   0500a35a           MVK.L2        0,B10               ; B10 = slot = 0
11818be0   0219f02a           MVK.S2        0x33e0,B4
11818be4   0208c0ea           MVKH.S2       0x11810000,B4       ; B4 = 0x118133e0
11818be8   05900fda           MV.L2         B4,B11              ; B11 = 0x118133e0 (slot fn table)
11818bec   2032a120    [ B0]  BNOP.S1       0x11818c44,5        ; if B0 != 0, skip all 5 slots
11818bf0   00005c10           B.S1          0x11818ec0          ; branch to veneer 11818ec0 (lands after 11818c00)
11818bf4   0180667c           STW.D2T1      A3,*+B14[102]       ; [delay 1] *(0xc0184e00 + 102*4 = 0xc0184f98) = 0
11818bf8       9506           MV.L1X        B10,A4              ; [delay 2] A4 = B10 (slot index 0)
11818bfa       2c6e           NOP           2                   ; [delay 3..4]
11818c00   01810162           ADDKPC.S2     0x11818c04,B3,0     ; [delay 5] B3 = 0x11818c04 -> lands at 11818ec0!
11818c04   10005613           CALLP.S2      0x11818eb0,B3       ; call veneer 11818eb0 -> c01502cc()
11818c08   05100fd8 ||        MV.L1         A4,A10              ; A10 = return value of c014ff44(slot)
11818c0c   02ad4ae6           LDW.D2T2      *+B11[B10],B5       ; B5 = *(0x118133e0 + 4*slot)
11818c10       9247           MV.L2X        A4,B4               ; B4 = return value of c01502cc() = 0x11f03b48
11818c12       8506           MV.L1         A10,A4              ; A4 = A10 = &instance[slot]
11818c14       2c6e           NOP           2
11818c16       02ef           BNOP.S2       B5,0                ; indirect call to slot callback B5
11818c18   01888162           ADDKPC.S2     0x11818c20,B3,4     ; B3 = 0x11818c20 (4 delay cycles)
11818c20   0200666e           LDW.D2T2      *+B14[102],B4       ; B4 = *(0xc0184f98) = slot
11818c24   0510205a           ADD.L2        1,B4,B10            ; B10 = slot + 1
11818c28   0028a8da           CMPGT.L2      5,B10,B0            ; B0 = (5 > B10)
11818c2c   2ffffc10    [ B0]  B.S1          0x11818c00          ; [loop branch 1] lands at 11818c00 after 5 cycles
11818c30   20005410    [ B0]  B.S1          0x11818ec0          ; [loop branch 2] lands at 11818ec0 1 cycle after 11818c00!
11818c34   0500667e           STW.D2T2      B10,*+B14[102]      ; *(0xc0184f98) = B10 (0..4 during loop, 5 on exit)
11818c38   22281fd8    [ B0]  MV.L1X        B10,A4              ; A4 = B10 (next slot index 1..4)
11818c40   00002000           NOP           2
```

1. **First per-slot call — `11818ec0` -> `c014ff44(slot)` (`confirmed`):**
   - Veneer `11818ec0` (`11818ec0 MVK.S2 0xffffff44,B31; 11818ec4 MVKH.S2 0xc0140000,B31; 11818ec8 B.S2 B31`) jumps to **`c014ff44`**.
   - On iteration `0`, `11818bf0 B.S1 0x11818ec0` executes 5 delay cycles (`11818bf4`, `11818bf8`, `11818bfa NOP 2`, and `11818c00 ADDKPC.S2 0x11818c04,B3,0`) before landing at `11818ec0` with `A4 = B10 = 0` and `B3 = 0x11818c04`.
   - On iterations `1..4`, the overlapping two-branch C6000 idiom at `11818c2c` (`[B0] B.S1 0x11818c00`) and `11818c30` (`[B0] B.S1 0x11818ec0`) executes `11818c34`, `11818c38` (`A4 = B10`), and `11818c40` (`NOP 2`), lands at `11818c00` (`ADDKPC 0x11818c04,B3,0`) for 1 cycle, and immediately lands at `11818ec0` (`c014ff44`) with `A4 = B10` (`1..4`) and `B3 = 0x11818c04` (`confirmed`).
   - **`c014ff44` (`main.dis` lines 92882-92887, `confirmed`):**
     ```
     c014ff44   001d682a           MVK.S2        0x3ad0,B0
     c014ff48   0008f86b           MVKH.S2       0x11f00000,B0       ; B0 = 0x11f03ad0
     c014ff4c   00108ca0 ||        SHL.S1        A4,0x4,A0           ; A0 = 16 * slot
     c014ff50   00009c40           ADDAW.D1      A0,A4,A0            ; A0 = 16*slot + 4*slot = 20 * slot (0x14 * slot)
     c014ff54       1040           ADD.L1X       A0,B0,A4            ; A4 = 0x11f03ad0 + 20 * slot
     c014ff56       a1ef           BNOP.S2       B3,5
     ```
     `c014ff44(slot)` returns the pointer to slot `n`'s 20-byte `instance` struct in L1D RAM:
     - Slot 0: `0x11f03ad0 + 0 * 0x14 = 0x11f03ad0`
     - Slot 1: `0x11f03ad0 + 1 * 0x14 = 0x11f03ae4`
     - Slot 2: `0x11f03ad0 + 2 * 0x14 = 0x11f03af8`
     - Slot 3: `0x11f03ad0 + 3 * 0x14 = 0x11f03b0c`
     - Slot 4: `0x11f03ad0 + 4 * 0x14 = 0x11f03b20`

2. **Second per-slot call — `11818eb0` -> `c01502cc()` (`confirmed`):**
   - When `c014ff44(slot)` returns to `11818c04`, the fetch packet `11818c04 CALLP.S2 0x11818eb0,B3 || 11818c08 MV.L1 A4,A10` saves `c014ff44`'s return value (`&instance[slot]`) into `A10` while calling veneer `11818eb0`.
   - Veneer `11818eb0` (`11818eb0 MVK.S2 0x02cc,B31; 11818eb4 MVKH.S2 0xc0150000,B31; 11818eb8 B.S2 B31`) jumps to **`c01502cc`**.
   - **`c01502cc` (`main.dis` lines 93170-93172, `confirmed`):**
     ```
     c01502cc   021da428           MVK.S1        0x3b48,A4
     c01502d0   0208f868           MVKH.S1       0x11f00000,A4
     c01502d4   008ca362           BNOP.S2       B3,5
     ```
     `c01502cc` is a 3-instruction constant getter that ignores `A4` and unconditionally returns **`A4 = 0x11f03b48`** (the base address of the 63-word shared service/audio context table `ctx` in L1D RAM, initialized once at boot by `c014ff58`..`c01502c8`). *(Note: `c01502e0` is a separate function after `c01502d4 BNOP.S2 B3,5`; `RHYTHM_LOOPER_TAP_2026-10-17.md` R1 step 11 mistakenly read past `c01502d4` into `c01502e0`.)*

3. **Register setup for the indirect slot call `11818c16 BNOP.S2 B5,0` (`confirmed`):**
   - `11818c0c LDW.D2T2 *+B11[B10],B5`: loads `B5 = *(0x118133e0 + 4 * slot)`.
   - `11818c10 MV.L2X A4,B4`: moves `c01502cc()`'s return value (`0x11f03b48`) into **`B4`** (2nd argument, `void **ctx`).
   - `11818c12 MV.L1 A10,A4`: moves `c014ff44(slot)`'s saved return value (`0x11f03ad0 + 20 * slot`) into **`A4`** (1st argument, `void **instance`).
   - `11818c16 BNOP.S2 B5,0` + `11818c18 ADDKPC.S2 0x11818c20,B3,4`: calls `B5(A4 = &instance[slot], B4 = 0x11f03b48)` with return address `B3 = 0x11818c20`.
   - Also throughout slot `n`'s execution:
     - `B10` holds `n` (`0..4`), and `*(0xc0184e00 + 102*4 = 0xc0184f98)` (`*+B14[102]`, written at `11818bf4` and `11818c34`) holds `n` (`0..4`), reloaded at `11818c20` (`LDW *+B14[102],B4`).
     - `B11` holds `0x118133e0` (callee-saved register across standard C6000 calls).

---

### B. What the Table `118133e0` Holds and All Writers to `118133e0`

`0x118133e0` (`0x118133e0`..`0x118133f3`, 5 × 32-bit words in L2 SRAM) is the runtime per-slot audio callback pointer table (`confirmed`). Exhaustive search of `refs.txt` and `main.dis` shows **five writers** (and two readers: the audio Swi at `11818be0`/`11818c0c` and the background service loop at `c0167530`/`c016753a`) (`confirmed`):

| Writer function | Store instruction | Value written to `0x118133e0 + 4*slot` | When it runs / Purpose | Confidence |
|---|---|---|---|---|
| `c0165e98` (`c0165ea8`..`c0165f18`) | `c0165f04 STW B0,*B4++[1]` (5-iter loop) | `0xc016d180` (`BNOP.S2 B3,5` no-op) | Called once at boot (`c016bef4`); zeroes all 5 `instance[1]` (`0x348` B) and `instance[2]` (`0x2a0` B) buffers and initializes `118133e0[0..4]` to `c016d180`. | `confirmed` |
| `c0143794` (`c0143794`..`c01437b2`) | `c01437ae STW A0,*A4++[1]` (`SPLOOPD 1`, `ILC=1` -> 5 words) | `0xc016d180` (`BNOP.S2 B3,5` no-op) | Resets all 5 `118133e0[0..4]` entries to no-op `c016d180`. | `confirmed` |
| `1180afc0` (via veneer `c016f660`) | `1180afd4 STW B0,*+A5[A4]` (`slot = instance[0]`) | `0xc016d184` (zeroes `11f037b0`/`11f037f0`) | Called before effect unload/reload (`c0132df0`, `c01332b4`, `c013fa34`, `c01434b0`, `c01437d4`, etc.) to substitute the silence routine `c016d184` while a slot's ELF is being replaced. | `confirmed` |
| `c0165f20` (`c0165f20`..`c0165f48`) | `c0165f46 STW A0,*A5[A4]` (`slot = instance[0]`) | `*(entry[1] + 0x58)` (`word[22]` of slot's param table) | Called after slot load (`c0133084`) and during patch/slot activation (`c014350c` when `c012ee10(slot) == 0`). Installs the slot's active audio callback from `entry[1] + 88` (`0x58`):<br>• Loaded `.ZD2` effect (`id >= 2`): relocated `Fx_<Name>` in `0xc01f4000 + slot*0xa000` (or `0x11820000` for Slot 0 residency patch).<br>• Empty slot (`id == 0`, built-in `Dll` `c016d150`, table `c017de30`): `*(0xc017de30 + 0x58 = 0xc017de88) = 0x11818de0`.<br>• 2-slot companion (`id == 1`, built-in `Dll` `c016d110`, table `c017dea0`): `*(0xc017dea0 + 0x58 = 0xc017def8) = 0x11818e4c` (`BNOP.S2 B3,5`). | `confirmed` |
| `c0165e80` (`c0165e80`..`c0165e96`) | `c0165e94 STW B0,*A5[A4]` (`slot = instance[0]`) | `0x11818de0` (built-in `"BYPASS"` pass-through) | Called at `c0143558` when `c012ee10(slot) != 0` (slot force-bypassed via bitmasks `118118e0`..`118118f0`); installs `11818de0` instead of `*(entry[1] + 0x58)`. | `confirmed` |

---

### C. What Each Slot Effect Reads and Writes (In-Place Processing on `11f037b0` / `11f037f0`)

Every slot callback `B5` receives `A4 = &instance[slot]` (`0x11f03ad0 + 0x14 * slot`) and `B4 = ctx` (`0x11f03b48`).
- In `c014ff58`..`c014ffda` (`main.dis` lines 92888-92928), the shared `ctx` table at `0x11f03b48` is initialized with (`confirmed`):
  - `ctx[0]` (`*(0x11f03b48 + 0x00 = 0x11f03b48)`) = `0x11f03970` (`c014ff6c`)
  - **`ctx[1]` (`*(0x11f03b48 + 0x04 = 0x11f03b4c)`) = `0x11f037b0`** (`c014ff7a`)
  - `ctx[2]` (`*(0x11f03b48 + 0x08 = 0x11f03b50)`) = `0x11f03830` (`c014ff8a`)
  - `ctx[3]` (`*(0x11f03b48 + 0x0c = 0x11f03b54)`) = `0x1180a2a8` (ramp helper, `c014ff96`)
  - `ctx[4]` (`*(0x11f03b48 + 0x10 = 0x11f03b58)`) = `0x1180a220` (ramp helper, `c014ffa6`)
  - `ctx[7]` (`*(0x11f03b48 + 0x1c = 0x11f03b64)`) = `0x11f03e20` (active ramp target pointer cell, `c014ffce`)
  - `ctx[8]` (`*(0x11f03b48 + 0x20 = 0x11f03b68)`) = `0x11f03de0` (16-float per-sample ramp curve buffer, `c014ffda`)
- **Every slot processes `ctx[1]` (`0x11f037b0` L / `0x11f037f0` R) strictly IN PLACE; there is NO ping-ponging between buffers across slots (`confirmed`):**
  - Cross-checked across all 17 disassembled stock effects (`TS_DRIVE`, `GOLD_DRV`, `ZEN_DRV`, `DIST_1`, `NYC_MUFF`, `SQUEAK`, `ACOSIM`, `BGTHRTTL`, `DISTPLUS`, `RCBOOST`, `REDCRUNC`, `SWEETDRV`, `TB_MK15`, `VIOLETDS`, `DELAY_3S`, `ANDLY_3S`, `HALL`), the built-in empty/bypass callback `11818de0`, the silence callback `c016d184`, and our custom effects (`effects/g1gain/gain.c`):
    - Each effect loads the audio bus base pointer from `ctx[1]` (`*+B4[1]` or `*+A8[1]`, which is always **`0x11f037b0`**).
    - **Left channel (16 × `float32`, 64 bytes)**: `0x11f037b0 + 0x00 = 0x11f037b0`..`0x11f037ef` (accessed as `bus[0..15]`).
    - **Right channel (16 × `float32`, 64 bytes)**: `0x11f037b0 + 0x40 = 0x11f037f0`..`0x11f0382f` (accessed as `bus[16..31]`, i.e. `*+reg[16]` word offset = `+64` bytes).
    - None of the effects read or write `ctx[0]` (`0x11f03970`) or `ctx[2]` (`0x11f03830`).
- **Exact buffer addresses for Slot `n` (`n = 0..4`) (`confirmed`):**
  - **Slot `n` Input (L / R):** `0x11f037b0` (L, 16 floats) / `0x11f037f0` (R, 16 floats) at `11818c16` (`BNOP.S2 B5,0`), containing the output of Slot `n - 1` (or for Slot `0`, the dry guitar float bus after `11818360`, pre-Looper `11818bc0`, and `11817940`).
  - **Slot `n` Output (L / R):** `0x11f037b0` (L, 16 floats) / `0x11f037f0` (R, 16 floats) at `11818c20` (immediately upon return from `BNOP.S2 B5,0`), overwriting the input in place.

## 2. Mono / Stereo Bus Topology Across Slots

## 3. Bypassed and Empty Slots

## 4. Concrete Hook Proposal for Per-Slot & Wet-Only USB Taps

