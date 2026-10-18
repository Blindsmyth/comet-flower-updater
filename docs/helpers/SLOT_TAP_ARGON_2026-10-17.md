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

### A. Pre-Loop Initialization (`11818bb4`..`11818bd0`): Entering Slot 0 as Identical Dual-Mono (`L[i] == R[i]`)

Before the 5-slot loop begins at `11818bd4`, five functions prepare the floating-point effect bus at `0x11f037b0` (Left, 16 floats) and `0x11f037f0` (Right, 16 floats) (`confirmed`):

1. **Step 4 — `11818bb4 CALLP 0x11816f60` (ADC input DC-block + biquad filter, `main.dis` lines 16216-16351):**
   - Reads the 16 raw mono guitar ADC `int32` samples from `0x11f038b0`, converts to `float32`, applies the input high-pass and biquad stages, converts back to `int32`, and writes **identical** `int32` samples to both `0x11f03730` (Left `int32[16]`, `118170fe STW A3,*+B7[1]`) and `0x11f03770` (Right `int32[16]`, `11817104 STW A3,*+B7[17]`, where `B7` marches across `0x11f0372c`..`0x11f03768` and `17 * 4 = 68 = 0x44`, `0x11f0372c + 0x44 = 0x11f03770`).

2. **Step 5 — `11818bb8 CALLP 0x11818360` (`int32` -> `float32` input bus conversion, `main.dis` lines 17637-17671):**
   - Sets source `A6 = 0x11f03728 + 8 = 0x11f03730` (`11818360`..`11818368`, reading **only** Left `int32[16]`) and destination base `B4 = 0x11f037a8` (`11818364`..`1181836c`).
   - Computes destination pointers (`11818372`..`1181837e`):
     - Left even/odd: `B4 = 0x11f037a8 + 8 = 0x11f037b0` (`ADD.L2 8,B4,B4`), `A4 = 0x11f037a8 + 12 = 0x11f037b4` (`ADD.L1X 12,B4,A4`).
     - Right even/odd: `B6 = 0x11f037a8 + 72 = 0x11f037f0` (`ADD.S2 72,B4,B6`, `72 = 0x48`), `A3 = 0x11f037a8 + 76 = 0x11f037f4` (`ADD.D1X B4,76,A3`, `76 = 0x4c`).
   - Loops 8 times (`B0 = 7..0`), converting 2 `int32` samples per iteration via `INTSP` × `2^-31` (`0x30000000` in `B5`) and writing **identical float values** to both Left (`118183c4 STW B7,*B4++[2]`, `118183cc STW A5,*A4++[2]`) and Right (`118183c2 STW B7,*B6++[2]`, `118183c8 STW A5,*A3++[2]`).

3. **Step 6 — `11818bc0 CALLP 0x11818e60` (`A4 = 0`, Pre-Looper hook, `main.dis` lines 18480-18499):**
   - Calls `*(0x11f03ed0 + 0) = 0x118164c0` when Looper is active with `Pre/Post = Pre` (otherwise `0x11816c5c` no-op).
   - As proven in `118164c0` (`11816c2c`..`11816c40`), Looper records `0x11f037b0` (Left only) into SDRAM and mixes its mono playback sample identically into both `0x11f037b0` (`*B31[0]`) and `0x11f037f0` (`*+B31[16]`). Thus `L[i] == R[i]` still holds after Step 6.

4. **Step 7 — `11818bc8 CALLP 0x118183d0` (Clean DI / sidechain copy, `main.dis` lines 17672-17700):**
   - Reads the 16 floats from `0x11f037b0` (`A6 = 0x11f037a8 + 8 = 0x11f037b0`) and writes identical copies into `0x11f03928 + 8 = 0x11f03930` (`B4`/`A4`) and `0x11f03968 + 8 = 0x11f03970` (`B5`/`A3`, which is `ctx[0]`, used as the sidechain/key input by noise gates like `ZNR` when `Detct = GtrIn`). Does not modify `0x11f037b0` or `0x11f037f0`.

5. **Step 9 — `11818bd0 CALLP 0x11817940` (Input mute/trim ramp + `ctx[2]` clear, `main.dis` lines 16912-17010):**
   - Sets source `A6 = 0x11f037a8 + 8 = 0x11f037b0` (`11817960`..`11817966`, reading Left `float[16]`) and destination pointer `A7 = A6 - 8 = 0x11f037a8` (`11817968 SUB.L1 A6,8,A7`).
   - Multiplies each of the 16 samples by the input mute/trim scalar `*(0xc011acdc + 8 = 0xc011ace4)` (which ramps between `0.0f` and `1.0f` when `*(0xc0184f98)` input-mute flag changes) and writes the scaled sample **identically to both Left and Right** (8 iterations of 2 samples):
     - Sample `2k`: `11817988` / `118179f0 STW.D1T1 A5,*++A7[2]` (writes `0x11f037b0 + 8*k`, advancing `A7` to `0x11f037b0 + 8*k`) and `1181798c` / `118179f4 STW.D1T1 A5,*+A7[16]` (writes `A7 + 16*4 = 0x11f037f0 + 8*k`).
     - Sample `2k+1`: `118179b4` / `11817a0a STW.D1T1 A3,*+A7[1]` (writes `0x11f037b4 + 8*k`) and `118179bc` / `11817a0c STW.D1T1 A3,*+A7[17]` (writes `A7 + 17*4 = 0x11f037f4 + 8*k`).
     - *(Correction to `RHYTHM_LOOPER_TAP_2026-10-17.md`: `11817940` updates both Left `0x11f037b0` and Right `0x11f037f0`, not Left only.)*
   - Finally, `118179c8`..`11817a88` zeroes the 128-byte stereo buffer at `0x11f03828 + 8 = 0x11f03830` (`0x11f03830`..`0x11f0386f` L and `0x11f03870`..`0x11f038af` R, which is `ctx[2]`) using `ZERO.L1 A5:A4` + 16 `STDW` stores (`confirmed`).

**Result entering Slot 0 (`11818bd4`):** The effect bus is a **2-channel planar stereo buffer (`float[2][16]`)** at `0x11f037b0` (L) and `0x11f037f0` (R), initialized with **bit-identical dual-mono samples (`L[i] == R[i]` for `i = 0..15`)** (`confirmed`).

---

### B. How Mono vs. Stereo Effects Propagate `L` (`11f037b0`) and `R` (`11f037f0`) Across Slots `0..4`

The Zoom G1X Four framework has **no fixed mono-to-stereo transition slot** (`confirmed`). Every slot `0..4` receives the same 2-channel planar pointer `ctx[1] = 0x11f037b0` (`L = bus[0..15]`, `R = bus[16..31]`), and whether `L` and `R` are identical (`dual-mono`) or distinct (`true stereo`) after Slot `k` depends solely on the effect callbacks that have executed in Slots `0..k`:

| Slot State / Effect Type | How It Reads `L` (`11f037b0`) & `R` (`11f037f0`) | How It Writes `L` (`11f037b0`) & `R` (`11f037f0`) | Effect on Bus Stereo Image | Status |
|---|---|---|---|---|
| **Empty slot (`id == 0`, `11818de0`)** or **2-slot companion (`id == 1`, `11818e4c`)** | `11818de0` reads `L[i]` (`*B6[0]`) and `R[i]` (`*+B6[16]`) independently; `11818e4c` does not touch memory. | `11818de0` writes `L[i] * coef[4]` (`1.0f` in steady state) to `*B6[0]` and `R[i] * coef[4]` to `*+B6[16]`. | **Preserves stereo (`L != R` stays `L != R`; `L == R` stays `L == R`).** | `confirmed` |
| **Active mono effect (`coef[0] == 1.0f`)**<br>*(e.g., `TS_DRIVE`, `GOLD_DRV`, `ZEN_DRV`, `DIST_1`, `NYC_MUFF`, `SQUEAK`, `ACOSIM`, `BGTHRTTL`, `DISTPLUS`, `RCBOOST`, `REDCRUNC`, `SWEETDRV`, `TB_MK15`, `VIOLETDS`, amps/cabs, mono delays)* | Sums Left and Right to mono at the top of the 16-sample loop via **`mono_in[i] = 0.5f * (L[i] + R[i])`**:<br>• `NYC_MUFF.ZD2` (`.text+0x2f8`..`0x310`): `LDW *+B27[0],B4; LDW *+B27[16],A3; ADDSP A3,B4,A3; MPYSPDP A3,0.5`.<br>• `DELAY_3S.ZD2` (`.text+0x648`..`0x690`): `LDW *A17++[1],A16; LDW *B7++[1],B9; ADDSP A16,B9,A16; MPYSP 0.5f,A16,A16`.<br>• `SQUEAK.ZD2` (`.text+0x024`..`0x080`): reads `L` and `R` (`LDNDW` from `ctx[1]` and `ctx[1]+64`), averages `0.5f * (L[i] + R[i])` into the 4× oversampler input buffer while saving separate `dry_L[16]` (`SP+78*4`) and `dry_R[16]` (`SP+94*4`) on the stack. | Evaluates the wet/dry crossfade separately against `dry_L[i]` and `dry_R[i]`:<br>• `L_out[i] = coef[4] * ((1 - coef[0]) * dry_L[i] + g_wet * wet_mono[i])` -> `*+bus[0]`<br>• `R_out[i] = coef[4] * ((1 - coef[0]) * dry_R[i] + g_wet * wet_mono[i])` -> `*+bus[16]`<br>When active (`coef[0] == 1.0f`, `1 - coef[0] == 0.0f`), `(1 - coef[0]) * dry` vanishes, so both `L_out[i]` and `R_out[i]` receive the **exact same `coef[4] * wet_mono[i]`**. | **Collapses stereo to dual-mono (`L_out[i] == R_out[i]`)** when active (`coef[0] == 1.0f`). | `confirmed` |
| **Bypassed mono effect (`coef[0] == 0.0f`, footswitch OFF)** | Same as above: keeps `dry_L[i]` (`*+bus[0]`) and `dry_R[i]` (`*+bus[16]`) distinct up until the final crossfade store. | In `NYC_MUFF` (`.text+0x920`..`0xa0c`), `SQUEAK` (`.text+0x1306`..`0x136c`), `TS_DRIVE`, etc., when `coef[0] == 0.0f` and `coef[4] == 1.0f`:<br>• `L_out[i] = 1.0f * (1.0f * dry_L[i] + 0.0f * wet_mono[i]) = dry_L[i]`<br>• `R_out[i] = 1.0f * (1.0f * dry_R[i] + 0.0f * wet_mono[i]) = dry_R[i]` | **Preserves stereo even though the effect DSP is mono!** A bypassed mono drive/amp placed after a stereo effect does **not** collapse `L` and `R`. | `confirmed` |
| **Active stereo effect (`coef[0] == 1.0f`)**<br>*(e.g., `HALL.ZD2`, `DELAY_3S.ZD2` in ping-pong mode, `STEREOCH.ZD2`, `CHORUS.ZD2`)* | Either sums `0.5f * (L[i] + R[i])` into a stereo generator (`DELAY_3S` `.text+0x648`..`0x690`) or reads `L[i]` and `R[i]` into stereo tank/delay lines (`HALL` `.text+0x1b0`..`0x270`). | Writes **distinct** Left and Right wet mixes to `0x11f037b0` and `0x11f037f0`:<br>• `HALL.ZD2`: `STW B10,*+B18[0]` (`.text+0x3f8`, Left) and `STW B4,*+B18[16]` (`.text+0x590`, Right).<br>• `DELAY_3S.ZD2`: `STW A3,*+A23[0]` (`.text+0x990`, Left) and `STW B5,*+A23[16]` (`.text+0x9f4`, Right). | **Produces true stereo (`L_out[i] != R_out[i]`)** on `0x11f037b0` (L) and `0x11f037f0` (R). | `confirmed` |

**Summary for USB Tap Design (`confirmed`):**
- Both `0x11f037b0` (Left, 16 floats) and `0x11f037f0` (Right, 16 floats) are **always valid, populated, and safe to tap after any slot `0..4`**.
- `R` (`0x11f037f0`) is bit-identical to `L` (`0x11f037b0`) entering Slot 0 and remains identical through active mono effects; it diverges into true stereo (`L != R`) at the first active stereo effect in the chain (and stays stereo through subsequent bypassed mono effects, empty slots, or stereo effects, unless collapsed by a downstream *active* mono effect).

## 3. Bypassed and Empty Slots

Every iteration `B10 = 0..4` of the slot loop (`11818bf4`..`11818c32`) unconditionally invokes `B5 = *(0x118133e0 + 4 * B10)` via `11818c16 BNOP.S2 B5,0` (`confirmed`). There is no per-slot branch around `BNOP.S2 B5,0` inside `11818bf4`..`11818c32`. Instead, empty, companion, bypassed, and transitioning slots are handled through five distinct mechanisms (`confirmed`):

### A. Case 1 — Empty Slot (`effect_id == 0`): Built-in `"BYPASS"` Callback `0x11818de0`

1. **Installation path (`c01297a0` -> `c016d150` -> `c0165f20`, `confirmed`):**
   - When `c01297a0(slot, effect_id)` (`main.dis` line 55259) is called with `effect_id == 0`, `c0129800 CMPEQ.L1 0,A3,A0; [!A0] BNOP 0xc0129cd0,5` skips ELF loading and installs the built-in empty-slot `Dll` constructor **`0xc016d150`** (`c0129d6c MVKL 0xc016d150,A5; c0129d70 MVKH 0xc016d150,A5; c0129d76 STW A5,*+A4[15]`).
   - Calling `0xc016d150(entry)` (`main.dis` lines 122179-122191) populates the 24-byte `Fx_tbl` descriptor at `0x11813400 + 24 * slot`:
     - `entry[0]` = `2` (`c016d150 MVK 2,B4; c016d160 STW B4,*+A4[0]`)
     - `entry[1]` = **`0xc017de30`** (`c016d152 MVKL 0xc017de30,B5; c016d15a MVKH 0xc017de30,B5; c016d166 STW B5,*+A4[1]`, built-in `"OnOff"` + `"BYPASS"` parameter table)
     - `entry[2]` = `0`, `entry[4]` = `0`, `entry[5]` = `0` (`zeroed`)
     - `entry[3]` = `0xc017ae4c` (`c016d156 MVKL 0xc017ae4c,A3; c016d162 MVKH 0xc017ae4c,A3; c016d16c STW A3,*+A4[3]`, 5-float coefficient template `{1.0f, 0.0f, 0.0f, 0.0f, 1.0f}`)
   - `c0165f20(instance)` (`main.dis` lines 115219-115235) then loads `*(entry[1] + 0x58) = *(0xc017de30 + 0x58 = 0xc017de88) = 0x11818de0` and writes **`0x11818de0`** to `0x118133e0 + 4 * slot`.

2. **Exact behavior of `0x11818de0` (`main.dis` lines 18445-18474, `confirmed`):**
   - Receives `A4 = &instance[slot]` (`0x11f03ad0 + 0x14 * slot`) and `B4 = 0x11f03b48` (`ctx`).
   - Materializes the ramp and bus addresses directly (`11818de0`..`11818e00`):
     - `B5 = 0x11f03e20` (`MVK 0x3e20,B5; MVKH 0x11f00000,B5`, active ramp target pointer cell `ctx[7]`)
     - `A4 = 0x11f03de0` (`MVK 0x3de0,A4; MVKH 0x11f00000,A4`, 16-float ramp curve buffer `ctx[8]`)
     - `B6 = 0x11f037ac` (`MVK 0x37ac,B6; MVKH 0x11f00000,B6`, one word before `0x11f037b0` for pre-increment `*++B6[1]`)
     - `B7 = instance[1]` (`11818dec MV.L1 A4,A3` parallel with `MVK 0x37ac,B6` copies entry `A4 = &instance[slot]` to `A3`; `11818df4 LDW.D1T2 *+A3[1],B7` loads `instance[1]`, the slot's coefficient array pointer)
   - Loops 16 times (`A0 = 15..0`, `11818e04`..`11818e44`):
     - Advances the active parameter ramp: `*( *(0x11f03e20) ) = 0x11f03de0[i]` (`11818e08 LDW *+B5[0],B8; 11818e0c LDW *A4++[1],A3; 11818e14 STW A3,*+B8[0]`).
     - Loads `B8 = instance[1][4]` (`coef[4]` at `instance[1] + 4*4 = instance[1] + 0x10`, the per-slot reload fade-in multiplier ramped to `1.0f` by `1180a9e0`): `11818e18 LDW.D2T2 *+B7[4],B8`.
     - Scales Left `0x11f037b0[i]` in place by `B8`: `11818e10 LDW.D2T2 *++B6[1],B4` (`0x11f037ac + 4*(i+1) = 0x11f037b0 + 4*i`), `11818e24 MPYSP.M2 B8,B4,B4`, `11818e2a STW.D2T2 B4,*B6[0]`.
     - Scales Right `0x11f037f0[i]` in place by `B8`: `11818e2c LDW.D2T2 *+B6[16],B4` (`B6 + 64 = 0x11f037f0 + 4*i`), `11818e38 MPYSP.M2 B8,B4,B4`, `11818e44 STW.D2T2 B4,*+B6[16]`.
   - **Impact on bus:** In steady state (`coef[4] == 1.0f`, `0x3f800000`), `0x11818de0` multiplies each sample in `0x11f037b0` and `0x11f037f0` by `1.0f` in place, leaving all normal/zero audio floats **bit-identical (`out[i] == in[i]`, so `out[i] - in[i] == 0.0f`)**.

---

### B. Case 2 — Companion Slot of a 2-Slot Effect (`effect_id == 1`): No-Op Callback `0x11818e4c`

- When a 2-slot (1U) effect occupies Slot `k`, its companion slot receives `effect_id == 1` (`c0129808 CMPEQ.L2X 1,A3,B0; [B0] BNOP 0xc0129c28,5`).
- `c0129cc0`..`c0129cca` installs built-in `Dll` constructor **`0xc016d110`**, which sets `entry[1] = 0xc017dea0` (`c016d112`..`c016d126`).
- `c0165f20` reads `*(0xc017dea0 + 0x58 = 0xc017def8) = 0x11818e4c` and stores **`0x11818e4c`** into `0x118133e0 + 4 * slot` (`confirmed`).
- `0x11818e4c` (`main.dis` line 18475) is a single instruction:
  ```
  11818e4c    008ca362            BNOP.S2       B3,5
  ```
- **Impact on bus:** Does not read or write memory; `0x11f037b0` and `0x11f037f0` are **100% untouched (`out[i] == in[i]`)** (`confirmed`).

---

### C. Case 3 — User-Bypassed Loaded Effect (`OnOff == 0` via Footswitch / Patch State)

There are two sub-cases depending on whether the slot is normally bypassed via its `OnOff` parameter (`0`) or force-bypassed by firmware bitmasks (`c012ee10(slot) != 0`) (`confirmed`):

1. **Standard Footswitch / Parameter Bypass (`OnOff == 0`, `c012ee10(slot) == 0`):**
   - **`0x118133e0 + 4 * slot` continues to hold the loaded effect's own `Fx_<Name>` function pointer**, and `Fx_<Name>` continues to execute every 16-sample block (`confirmed`).
   - Toggling the effect OFF invokes its `OnOff` parameter setter (`*(entry[1] + 0x1c)`, e.g. `Fx_DRV_TS_Drive_onf` at `TS_DRIVE.ZD2` `.text+0x0d0` or `Fx_DRV_Squeak_onf` at `SQUEAK.ZD2` `.text+0x1398`), which calls `ctx[3]` (`0x1180a2a8`) to ramp `coef[0]` (`instance[1][0]`) to `0.0f` over `705.6f` samples (`0x44306666`, ~16 ms at 44.1 kHz).
   - While bypassed (`coef[0] == 0.0f`, `coef[4] == 1.0f`):
     - **Standard effects (drives, amps, cabs, EQs, compressors, modulations):** `Fx_<Name>` still runs its internal filters/oversamplers on the input so state stays warm (clickless re-engagement), then applies the wet/dry crossfade `(1.0f - coef[0]) * dry + g_wet(coef[0]) * wet` at the end of the loop:
       - Since `coef[0] == 0.0f` and `g_wet(0.0f) == 0.0f`, the effect writes `1.0f * (1.0f * dry_L[i] + 0.0f) = dry_L[i]` to `0x11f037b0[i]` and `dry_R[i]` to `0x11f037f0[i]`.
       - Thus in steady-state bypass, **output equals input (`out[i] == in[i]`), and `wet_only = out[i] - in[i] == 0.0f`** (`confirmed`).
     - **Spillover / Trails effects (e.g. `DELAY_3S.ZD2`, `HALL.ZD2`):**
       - In `DELAY_3S.ZD2`, `Fx_DLY_Delay_onf` (`.text+0x354`..`0x390`) ramps `coef[0]` (`instance[1][0]`), which scales the **input send** into the delay line (`MPYSP B5,A16,B7` at `.text+0x6b0`), while the delay line readback and wet output mix (`coef[2]` / `coef[3]`) continue to add decaying echoes onto the dry signal (`ADDSP A3,A4,A3` at `.text+0x988` / `ADDSP B4,B5,B5` at `.text+0x9e8`).
       - Similarly, in `HALL.ZD2`, `Fx_REV_Hall_onf` (`.text+0x07c`..`0x0ac`) ramps `coef[0]` (`instance[1][0]`), which gates the tank input send while the reverb tank tail continues to sum with the dry path (`ADDSP B16,B10,B10` at `.text+0x3ec` / `ADDSP B8,B4,B4` at `.text+0x588`).
       - **Bonus of `out[i] - in[i]`:** For trails/spillover delays and reverbs bypassed mid-phrase, `out[i] - in[i]` automatically captures the exact decaying wet tail during spillover and decays to `0.0f` once the tail finishes!

2. **Force-Bypassed Slot (`c012ee10(slot) != 0` at `c0143500`..`c014355c`):**
   - If any of the slot force-bypass masks at `0x118118e0`, `0x118118e4`, `0x118118e8`, or `0x118118f0` has bit `slot` set (`c012ee10`..`c012ee7c`, `main.dis` lines 59751-59784), `c0143558 CALLP 0xc0165e80` overwrites `0x118133e0 + 4 * slot` with **`0x11818de0`** (the same built-in `"BYPASS"` callback used by empty slots).

---

### D. Case 4 — Slot Reload Silence (`0xc016d184`), Boot No-Op (`0xc016d180`), and Whole-Chain Bypass (`11818bec`)

| Condition | Mechanism & Address | Effect on `0x11f037b0` (L) / `0x11f037f0` (R) | Status |
|---|---|---|---|
| **Slot ELF unload/reload in progress** | `1180afc0` (via `c016f660`) writes **`0xc016d184`** to `0x118133e0 + 4 * slot`. | `c016d184` (`main.dis` lines 122197-122215) zeroes `0x11f037b0`..`0x11f037ef` and `0x11f037f0`..`0x11f0382f` while the slot's code/state is being replaced. | `confirmed` |
| **Early boot / chain reset** | `c0165e98` (`c0165eb4`) or `c0143794` (`c01437b8`) writes **`0xc016d180`** to `0x118133e0[0..4]`. | `c016d180` (`BNOP.S2 B3,5`) returns immediately without touching `0x11f037b0` / `0x11f037f0`. | `confirmed` |
| **Whole-chain mute (`*(0xc0184f94) != 0`, e.g. Tuner mute)** | At `11818bd8 LDW *+B14[101],B0; 11818bec [B0] BNOP 0x11818c44,5`, the entire 5-slot loop (`11818bf0`..`11818c40`) is **skipped**. | None of `slots[0..4]` run; `0x11f037b0` / `0x11f037f0` retain the pre-loop guitar float bus (which is then muted downstream by `11817a90` / `118186e0`). Any per-slot tap hook placed *inside* `11818bf0`..`11818c38` will not execute while `*(0xc0184f94) != 0` unless handled (see Section 4). | `confirmed` |

## 4. Concrete Hook Proposal for Per-Slot & Wet-Only USB Taps

### A. Slots and Audio Stages That Run OUTSIDE the 5-Slot Loop (`11818bd4`..`11818c40`)

Before choosing the hook site, note every DSP processing stage in `g_Swi_AudioProcess` (`11818ba0`) that operates on `0x11f037b0` (L) / `0x11f037f0` (R) **outside** the 5-slot loop (`confirmed`):

1. **Hidden "Slot 5" — Global Master Output EQ (`G_OUT_EQ.BDL` / `B_OUT_EQ.BDL`) at Step 13 (`11818c48`):**
   - Immediately after the 5-slot loop and `11817a90` (`11818c44`), `11818c48 CALLP.S2 0x11818ea0,B3 || MVK.L1 0,A4` calls `0xc014f594(0)` (`main.dis` lines 92049-92071).
   - `0xc014f594(0)` executes the exact same per-slot calling convention as the 5-slot loop, but for **index `5 = 0 + 5`** (`c014f5a4 ADD.L1 5,A0,A4`):
     - `c014f5a0 CALLP 0xc014ff44(5)` returns `&instance[5]` = `0x11f03ad0 + 5 * 20 = 0x11f03ad0 + 0x64 = 0x11f03b34` (`0x11f03b34`..`0x11f03b47`, immediately preceding `ctx` at `0x11f03b48`).
     - `c014f5a8 CALLP 0xc01502cc()` returns `ctx = 0x11f03b48` (`B4`).
     - `c014f5b0`..`c014f5cc` loads `A0 = *(0x11813490 + 4 * 0) = *(0x11813490)` and branches to `A0(A4 = 0x11f03b34, B4 = 0x11f03b48)`.
   - `*(0x11813490)` is written by `c014f1c4` (`c014f238`..`c014f248`, `main.dis` lines 91753-91758) with `*(entry[1] + 0x58)` of **`G_OUT_EQ.BDL`** (loaded by `c014f300` -> `c014f284` into the 40 KiB pool at `0xc00d2800`, descriptor at `0xc00ae610`).
   - Thus, the G1X Four actually has **5 user patch slots (`0..4`, table `0x118133e0[0..4]`, instances `0x11f03ad0`..`0x11f03b33`) plus 1 hidden post-chain Master Output EQ slot (`slot 5`, pointer `0x11813490`, instance `0x11f03b34`)** (`confirmed`).

2. **Secondary Stereo Return Bus `ctx[2]` (`0x11f03830` L / `0x11f03870` R) at Step 12 (`11818c44 CALLP 0x11817a90`):**
   - `0x11f03830` (L, 16 floats) and `0x11f03870` (R, 16 floats) are zeroed before the slot loop in `11817940` (`118179c8`..`11817a88`), exposed to effects via `ctx[2]` (`*(0x11f03b48 + 8) = 0x11f03830`), and summed into `0x11f037b0`/`0x11f037f0` after the slot loop in `11817a90` (`11817aa0`..`11817ca8`).
   - On the G1X Four, there is no split/parallel chain routing and none of the 17 disassembled stock effects touch `ctx[2]`.
   - **Critical warning for tap staging:** Do **not** use `0x11f03830`..`0x11f038af` as a scratch buffer *during* the 5-slot loop, because `11817a90` at Step 12 will sum whatever is in `0x11f03830`/`0x11f03870` into the pedal's main speaker/headphone bus! Instead, place the tap staging buffers in our `0xc01a8xxx` USB tap region (`confirmed`).

3. **Pre/Post Looper (`11818bc0` / `11818c50`) and Rhythm (`11818c54`):**
   - **Pre-Looper** (`11818bc0 CALLP 0x11818e60` with `A4 = 0` -> `*(0x11f03ed0)`) runs at Step 6, **before** Slot 0 (so if Looper is in `Pre` mode, its playback is included in the input to Slot 0).
   - **Post-Looper** (`11818c50 CALLP 0x11818e60` with `A4 = 1` -> `*(0x11f03ed4)`) runs at Step 14, **after** Slot 4 and Master Output EQ (`G_OUT_EQ.BDL`).
   - **Rhythm / Drums** (`11818c54 CALLP 0x11818d60` -> `11817640`) runs at Step 15, **after** Post-Looper.

---

### B. Comparison of Candidate Hook Mechanisms

| Approach | Patch Site & Size | Pros | Cons / Risks | Verdict |
|---|---|---|---|---|
| **Option 1 (Recommended): Hijack the `0x11818eb0` 4-word veneer (`c01502cc` trampoline)** | `0x11818eb0`..`0x11818ebc` (4 × 32-bit words in L2 SRAM, outside any `.fphead` compact packet) | • **Zero edits inside `11818ba0` or any `.fphead` compact fetch packet.**<br>• Intercepts **before** `B5` on slot `N`, can call `B5 = B11[B10]` directly when `B10 == N`, and intercepts **immediately after** `B5` returns before branching to `0x11818c20`.<br>• Single hook handles **both** `"bus after slot N"` and `"slot N wet-only (after - before)"` for any runtime `N = 0..4` (plus `N = -1` dry DI before Slot 0).<br>• Immune to `0x118133e0` table reloads. | None (`0xc01502cc` is a 3-instruction leaf `A4 = 0x11f03b48; BNOP B3,5`). | **Best / Cheapest (`confirmed`)** |
| **Option 2: Patch `11818c18 ADDKPC 0x11818c20,B3,4` to return via dead padding `11818ed0`..`11818edc`** | `0x11818c18` (1 word inside `.fphead` packet `11818c00`..`11818c1c`) + `0x11818ed0`..`0x11818edc` (4 zero words after `11818ecc`) | • `11818c18` is a 32-bit instruction in the delay slot of `11818c16 BNOP.S2 B5,0`; changing its target from `0x11818c20` to `0x11818ed0` redirects `B3` (where `B5` returns) to `0x11818ed0`. | • Only intercepts *after* `B5` returns (cannot capture Slot `0`'s input for `wet_only` without a second hook before `B5`).<br>• Modifies a word inside a compact `.fphead` fetch packet. | Inferior to Option 1 |
| **Option 3: Wrap function pointers in `0x118133e0[0..4]`** | Data table `0x118133e0`..`0x118133f3` | • No code patches in `11818ba0`. | • **Fragile / racy:** 5 different functions (`c0165f20`, `c0165e80`, `1180afc0`, `c0143794`, `c0165e98`) overwrite `0x118133e0[slot]` on patch change, effect load, and bypass toggle. | Do not use |

---

### C. Detailed Design of Option 1: Single-Veneer Hook at `0x11818eb0`

#### 1. Why `0x11818eb0` Is the Ideal Hook Point (`confirmed`)
Look at the per-slot loop body at `11818c00`..`11818c20` (`main.dis` lines 18297-18307) and the veneer at `11818eb0`..`11818ebc` (`main.dis` lines 18501-18504):
```
11818c00   01810162           ADDKPC.S2     0x11818c04,B3,0
11818c04   10005613           CALLP.S2      0x11818eb0,B3
11818c08   05100fd8 ||        MV.L1         A4,A10
11818c0c   02ad4ae6           LDW.D2T2      *+B11[B10],B5
11818c10       9247           MV.L2X        A4,B4
11818c12       8506           MV.L1         A10,A4
11818c14       2c6e           NOP           2
11818c16       02ef           BNOP.S2       B5,0
11818c18   01888162           ADDKPC.S2     0x11818c20,B3,4
11818c1c   e6000000           .fphead       n, l, W, BU, nobr, nosat, 0110000b
11818c20   0200666e           LDW.D2T2      *+B14[102],B4
```
And at `0x11818eb0`..`0x11818ebc` (standard 32-bit instructions, no `.fphead`):
```
11818eb0   0f81662a           MVK.S2        0x02cc,B31
11818eb4   0fe00aea           MVKH.S2       0xc0150000,B31
11818eb8   007c0362           B.S2          B31
11818ebc   00008000           NOP           5
```
When `11818c04 CALLP.S2 0x11818eb0,B3 || MV.L1 A4,A10` reaches `0x11818eb0`:
- No branches are in flight (`CALLP` completes its 5 delay slots before branching).
- Live registers at `0x11818eb0`:
  - `B10` = current slot index `k` (`0, 1, 2, 3, 4`), also stored at `*+B14[102]` (`0x11818298 + 408 = 0x11818430`? Note: `B14 = 0xc0184e00`, so `0xc0184e00 + 102 * 4 = 0xc0184e00 + 0x198 = 0xc0184f98` — wait: `101 * 4 = 0x194 -> 0xc0184f94`, `102 * 4 = 0x198 -> 0xc0184f98`).
  - `A10` = `&instance[k]` (`0x11f03ad0 + 0x14 * k`, returned by `c014ff44(k)`).
  - `B11` = `0x118133e0` (base of the 5-slot callback table).
  - `B3` = `0x11818c0c` (return address into the loop body).
  - `0x11f037b0` (L, 16 floats) and `0x11f037f0` (R, 16 floats) hold the **exact input to Slot `k`**.

#### 2. Patching `0x11818eb0`..`0x11818ebc` (16 Bytes)
Overwrite the 4 words at `0x11818eb0`..`0x11818ebc` to jump to `slot_tap_dispatch` in `0xc01a8xxx`:
```
11818eb0:  MVKL.S2  slot_tap_dispatch, B31
11818eb4:  MVKH.S2  slot_tap_dispatch, B31
11818eb8:  B.S2     B31
11818ebc:  NOP      5
```

#### 3. Exact Logic of `slot_tap_dispatch` (in `0xc01a8xxx`)
Let runtime state in `0xc01a8xxx` consist of:
- `g_tap_slot` (`int32`, runtime-chosen slot index: `0..4` for Slots `0..4`, or `-1` for pre-Slot-0 dry guitar DI).
- `g_tap_mode` (`int32`: `0` = **After Slot `N`** cumulative bus; `1` = **Slot `N` Wet-Only** = `after - before`).
- `g_slot_in_L[16]` and `g_slot_in_R[16]` (128 bytes total, `float32[2][16]`, 8-byte aligned in `0xc01a8xxx`).
- `g_tap_out_L[16]` and `g_tap_out_R[16]` (128 bytes total, `float32[2][16]` or `int32[2][16]`, 8-byte aligned in `0xc01a8xxx`, read by the USB TX packer hook).

Inside `slot_tap_dispatch`:
1. **Non-target slot fast path (`B10 != g_tap_slot`):**
   - If `g_tap_slot == -1` and `B10 == 0`: copy `0x11f037b0`..`0x11f0382f` (32 floats) to `g_tap_out_L`/`g_tap_out_R` (pre-Slot-0 dry DI tap).
   - Otherwise, execute the original `0xc01502cc` body and return to `B3` (`0x11818c0c`):
     ```
     MVKL.S1  0x11f03b48, A4
     MVKH.S1  0x11f03b48, A4
     BNOP.S2  B3, 5            ; returns to 0x11818c0c, which runs B11[B10] normally
     ```
2. **Target slot path (`B10 == g_tap_slot`, for `N` in `0..4`):**
   - **Step 2a — Capture Slot `N` Input (only when `g_tap_mode == 1` [Wet-Only]):**
     - Copy 16 floats from `0x11f037b0`..`0x11f037ef` -> `g_slot_in_L[0..15]` and 16 floats from `0x11f037f0`..`0x11f0382f` -> `g_slot_in_R[0..15]` using 16 `LDDW`/`STDW` pairs (~20 cycles).
   - **Step 2b — Call Slot `N`'s Effect Callback `B5 = B11[B10]` Directly:**
     - Load `B5 = *+B11[B10]` (`*(0x118133e0 + 4 * N)`).
     - Set `A4 = A10` (`&instance[N]`) and `B4 = 0x11f03b48` (`ctx`).
     - Call `B5` (`BNOP.S2 B5,0` + `ADDKPC.S2 after_slot_N,B3,4`).
     - *(By the TI C6000 ABI, `B5` preserves `A10..A15` and `B10..B15`, so `B10`, `B11`, `B14`, `B15` remain intact upon return to `after_slot_N`.)*
   - **Step 2c — Capture Slot `N` Output at `after_slot_N`:**
     - **If `g_tap_mode == 0` (Bus After Slot `N`):**
       - Copy the 32 floats from `0x11f037b0`..`0x11f037ef` (L) and `0x11f037f0`..`0x11f0382f` (R) into `g_tap_out_L[0..15]` and `g_tap_out_R[0..15]` (or convert via `MPYSP` by `2147483648.0f` (`0x4f000000`) + `SPTRUNC` directly to `int32`, matching `11818428`).
     - **If `g_tap_mode == 1` (Slot `N` Wet-Only = `after - before`):**
       - Loop `i = 0..15`:
         - `wet_L[i] = SUBSP( *(0x11f037b0 + 4*i), g_slot_in_L[i] )` -> store to `g_tap_out_L[i]`
         - `wet_R[i] = SUBSP( *(0x11f037f0 + 4*i), g_slot_in_R[i] )` -> store to `g_tap_out_R[i]`
       - *(Note on mono drives/amps in Wet-Only mode: since an active mono effect overwrites `0x11f037b0`/`0x11f037f0` with `wet_mono[i]`, `after - before` yields `wet_mono[i] - dry[i]`, i.e. the exact nonlinear distortion/filter delta added by Slot `N`. For parallel-mix effects like `DELAY_3S` and `HALL`, where the effect outputs `dry[i] + wet_tail[i]`, `after - before` cancels `dry[i]` exactly and isolates the pure `wet_tail[i]` delay/reverb signal!)*
   - **Step 2d — Resume `g_Swi_AudioProcess` at `0x11818c20`:**
     - Branch directly to `0x11818c20` (`MVKL.S2 0x11818c20,B31; MVKH.S2 0x11818c20,B31; BNOP.S2 B31,5`), skipping `11818c0c`..`11818c18` (since `B5` has already been called!) and landing on `11818c20 LDW.D2T2 *+B14[102],B4` to advance `B10` to `N + 1`.

#### 4. Handling Whole-Chain Mute (`*(0xc0184f94) != 0` at `11818bec`) and Optional Slot 5 (`G_OUT_EQ.BDL`)
- **Whole-chain mute (`*(0xc0184f94) != 0`):** When `*(0xc0184f94) != 0` (`*+B14[101]`), `11818bec [B0] BNOP 0x11818c44,5` skips the 5-slot loop completely. In the USB TX consumer hook (at the end of `g_Swi_AudioProcess`), check `*(0xc0184f94) != 0`; if nonzero, zero the tapped USB channel pair for that block so stale samples from before the mute are never repeated (`confirmed`).
- **Optional Slot 5 (`G_OUT_EQ.BDL`) tap:** If tapping after the Master Output EQ (`N == 5`) is also desired, the adjacent 4-word veneer at `0x11818ea0`..`0x11818eac` (`main.dis` lines 18497-18500, called at `11818c48`) can be pointed to a tiny wrapper that calls `0xc014f594(0)` and then copies `0x11f037b0`..`0x11f0382f` into `g_tap_out_L`/`g_tap_out_R`.

STATUS: done

---
## Claude review (2026-10-17)
Checked against main.dis: `11818eb0` has exactly one caller (11818c04, the slot loop); its target `c01502cc`
is `MVK/MVKH 0x11f03b48 -> A4; BNOP B3,5` (changes only A4); `c014ff44` = `0x11f03ad0 + 20 x slot`;
B14 = c0184e00 (recon/16: B14[101] = c0184f94), so the slot index cell is c0184f98, written 0 at 11818bf4 and
k+1 at 11818c34 before each next call. No scratch register is live across the 11818c04 CALLP (A10/B10/B11/B14
callee-saved). So a hook in place of the 11818eb0 veneer sees the bus = input of slot k and must return
A4 = 0x11f03b48. "After slot k" = input of slot k+1 (slot 4: the bus at 11818c44, before patch level). Wet-only
of slot k = input(k+1) - input(k). The slot loop is skipped while c0184f94 != 0 (tuner mute): a tap must not
send stale captures then. Not checked: the section-2 claim that 11816f60 reads 11f038b0 (it contradicts the RX
unpack at 11818b20 writing 11f03730); irrelevant to the hook.
