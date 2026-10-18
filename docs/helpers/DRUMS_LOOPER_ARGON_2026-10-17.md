# Drums & Looper Isolated Signal Analysis (2026-10-17)

## 1. Writer Chain of 11f03730 / 11f03770 in One Audio Block

In one 16-sample audio block (`g_Swi_AudioProcess` at `11818ba0`..`11818c84`), `11f03730` (L, 16 × int32, 64 bytes) and `11f03770` (R, 16 × int32, 64 bytes) are written at **four distinct points** in Swi order (`confirmed`):

1. **Swi Step 3 — `11818bb0` `CALLP 0x11818b20` (RX unpack, `confirmed`):**
   - Reads the inactive McASP0 RX ping-pong DMA half (`11f03530` or `11f035b0`), unpacks 16 stereo frames (`LDNDW *A5++[1],A7:A6` at `11818b50`), scales by `0x80000000` (`SMPY32` at `11818b70`/`11818b74`), and stores planar int32 dry ADC samples into `11f03730` (`*B6++[1]` at `11818b90`, where `B6 = 11f03770 - 0x40 = 11f03730`) and `11f03770` (`*A8++[1]` at `11818b94`, `A8 = 11f03770`).

2. **Swi Step 4 — `11818bb4` `CALLP 0x11816f60` (Input conditioning / DI capture, `confirmed`):**
   - `A28` is initialized to `11f03770` (`11816f74`/`11816f84`). Reads `*-A28[16..10]` (`11f03730`..`11f03748`, L channel) and `*+A28[0..6]` (`11f03770`..`11f03788`, R channel), runs a saturating fixed-point filter, and **copies the conditioned mono guitar signal into both `11f03730` (`*-A28[16]`) and `11f03770` (`*A28++[1]`) identically** via paired stores (`118172b4`/`118172cc`, `11817360`/`11817378`, `118173ec`/`11817400`, `1181744c`/`1181745c`, `11817494`/`118174a0`, `118174d0`/`118174d4`, `118174e4`/`118174e8`), turning `11f03730` and `11f03770` into dual-mono conditioned guitar input before `11818360` converts both to float (`11f037b0`/`11f037f0`) at Step 5 (`11818bb8`).
   - Note on `11f03930` (USB ch 7-8 clean guitar DI): `118183d0` (Step 7, `11818bc8`) copies the fresh float guitar input from `11f037b0`/`11f037f0` into `11f03928`/`11f03968` (overlapping `11f03930`/`11f03970`), which is why `11f03930`/`11f03970` hold clean guitar DI (`confirmed`).

3. **Swi Step 6 or Step 14 — `11818bc0` (`A4=0`) or `11818c50` (`A4=1`) `CALLP 0x11818e60` -> `118164c0` (Looper engine, `confirmed`):**
   - `11818e60` dispatches through the 2-entry function pointer table at `11f03ed0` (`11818e64`..`11818e70`).
   - `c016a8e0` (`main.dis` lines 126777-126796) initializes both `11f03ed0[0]` and `11f03ed0[1]` to `c016d180` (no-op `BNOP B3,5`), and then writes **`118164c0`** into `11f03ed0[A4]` (`c016a904`..`c016a90e`), where `A4` (`0` = Pre / before effect chain, `1` = Post / after effect chain) is the Looper position setting (`confirmed`).
   - When `118164c0` runs (unless bypassed by `*(11f03c58) == 0` at `11816516`/`1181652c`), its first loop (`118165c4`..`11816676`, outer counter `A2 = 2` for L then R) reads float samples from `11f037b0`/`11f037f0` (`B8`), clamps to `[-1.0, +1.0)`, multiplies by `0x4f000000` (`2.14748365e9f` at `1181650c`/`11816618`), converts to 32-bit int (`SPTRUNC.L1 A17,A16` at `11816634`), and **stores the int32 result into `11f03730` and `11f03770`** (`STW.D1T1 A16,*A7++[1]` at `11816644`, with `A19/A7` starting at `11f03730` (`118164d4`/`11816504`) and advancing by `+64` bytes (`ADDK.S1 64,A19` at `11816658`) to `11f03770` for the second pass).
   - It then uses `(11f03730[i] >> 1) + (11f03770[i] >> 1)` (`118166d4`..`118166f4`) as the mono recording input to the SDRAM looper buffer (`c011aca8` = `c04abff0`), and in its final loop (`11816d40`..`11816f54`) converts the looper playback integer samples (`*A16++[1]` on stack `B15+8`) back to float (`INTSP` at `11816d70`/`11816d90`, scaled by `2^-31` in `A18`) and **adds them into `11f037b0` and `11f037f0`** (`ADDSP.L2X B9,A7,B16` at `11816db8`, `MPYSP`, `STW B4,*B8++[1]` at `11816e1c`).

4. **Swi Step 16 — `11818c58` `CALLP 0x11818428` (Final float-to-int32 conversion, `confirmed`):**
   - **This is the step that turns `11f03730` / `11f03770` into the full mix heard on USB ch 3-4.**
   - Before Step 16, **Swi Step 15 (`11818c54` `CALLP 0x11818d60`)** immediately calls **`11817640`** (`11818d64 CALLP.S2 0x11817640,B3`), which is the **Drum Machine (Rhythm) sample mixer** (`confirmed`). `11817640` reads 9 drum voice channels of 16-bit PCM samples, applies per-voice pan/level and master rhythm gain, converts to float (`INTSP.L2` at `11817838`/`11817860`), and **adds the stereo drum mix directly into `11f037b0` (L) and `11f037f0` (R)** (`ADDSP.L2 B6,B5,B5` at `11817878` -> `STW B5,*+B10[0]` at `11817888` for L; `ADDSP.L2 B4,B5,B4` at `11817898` -> `STW B4,*+B10[16]` at `118178a0` for R, where `B10` steps through `11f037ac + 4*(1..16)` = `11f037b0`..`11f037ec` and `+16` words = `11f037f0`..`11f0382c`).
   - Then the remainder of `11818d60` (`11818d68`..`11818dd4`) multiplies `11f037b0` (L) and `11f037f0` (R) in place by the float master/output gain at `11f03e34`.
   - Next, **Step 16 (`11818428`)** runs two 16-sample `SPLOOPD` passes (`A4 = 2` at `11818434`, `B8 = 11f037b0` at `1181842c` advancing by `+64` bytes to `11f037f0` at `118184f4`). It clamps `11f037b0`/`11f037f0` to `[-1.0, +1.0)`, scales by `0x4f000000` (`2.14748365e9f` at `11818490`/`118184d4`), truncates to 32-bit signed integers (`SPTRUNC.L1 A17,A16` at `118184e4`), and **writes the full mix (effects + looper + drums, post-`11f03e34`) into `11f03730` (pass 1) and `11f03770` (pass 2)**:
     ```
     11818464   099b9828 ||^       MVK.S1        0x3730,A19
     1181846c   0988f869 ||^       MVKH.S1       0x11f00000,A19
     ...
     118184e4   08440179 ||        SPTRUNC.L1    A17,A16
     118184e8       25d6 ||^       MV.D1         A19,A9
     118184f0   08243674 ||        STW.D1T1      A16,*A9++[1]
     ...
     11818504   09802050           ADDK.S1       64,A19
     ```
   - Finally, **Step 17 (`11818c60` `CALLP 0x118186e0`)** reads `11f03730` and `11f03770` (`A8 = 11f03730` at `118186f8`, `+64` at `118187d8`), applies the final output filter/mute (`11f03eb4` with `SSHL ..., 2` at `11818790` giving a 4× / +12 dB shift), and writes the result to `11f038b0` / `11f038f0` (`B21 = 11f038b0` at `11818798`, `+64` at `11818818`), leaving `11f03730` / `11f03770` untouched with the quieter pre-Step-17 full mix when TX pack (`11818c64`) runs (`confirmed`).

---

## 2. The Add of Drums and Looper (Candidate Buffers & Producers)

Neither the Looper nor the Drum Machine uses `11f03830` or `11f03930`. Both run **inside the audio Swi (`11818ba0`)** and sum their outputs directly into the main float stereo bus `11f037b0` (L) / `11f037f0` (R) at different stages (`confirmed`).

### A. Looper Signal (`118164c0`, called via `11818e60` at Step 6 `11818bc0` or Step 14 `11818c50`)

1. **Dispatcher & Producer (`confirmed`):**
   - `11818e60` loads function pointer `11f03ed0[A4]` (`11818e6c LDW *+A5[A4],A0`) and branches to it (`11818e70 B.S2X A0`).
   - `c016a8e0` fills `11f03ed0[0..1]` with `c016d180` (no-op return) and sets `11f03ed0[A4] = 0x118164c0` (`c016a904`..`c016a90e`). Thus `118164c0` is executed either at Step 6 (`A4=0`, Pre-effects) or Step 14 (`A4=1`, Post-effects, after `11817a90` patch-level gain).
2. **Long-Term Storage Buffer (`c04abff0`, `confirmed`):**
   - Setup function `c0139ae0`..`c0139b6c` reads `*(c01834ac) = 0xc04abff0` (`c0139ae8`) and initializes the Looper SDRAM arena globals:
     - `c011aca8` = `0xc04abff0` (primary loop base, `c0139af6`)
     - `c011acac` = `0xc04abff0 + 0x2b110` (`c0139b08`)
     - `c011acb0` = `0x0002b110` (loop capacity offset, `c0139b0e`)
     - `c011acb4` = `0xc04abff0 + 0x2b110` (`c0139b18`)
     - `c011acc0` = undo/secondary loop base (`c0139b50`)
   - Inside `118164c0`, the per-sample loop (`118166d0`..`11816d24`, 16 iterations via `A13 = 16` at `11816694`, `SUB A13,1,A13` at `11816c14`, `B 0x118166d0` at `11816cf8`) reads 16-bit signed loop samples from SDRAM (`LDH.D1T1 *+A3[0],A3` at `118167dc`, `118168a4`, `11816a66`, `11816a70`, `11816b84`, `11816c50`) and writes recorded/overdubbed 16-bit samples (`STH` at `1181677c`, `11816bb4`, `11816d24`), advancing byte offsets by `+2` per sample (`ADD 2,A18,A3` at `11816720`, `ADD 2,B25,B6` at `11816c6c`).
3. **Per-Block Isolated Looper Buffer (`B15 + 8`, 16 × int32 mono, `confirmed`):**
   - During the 16-sample SDRAM loop (`118166d0`..`11816d24`), `B12` is initialized to `B15 + 8` (`118166b0 ADD.S2 8,B15,B12`, after `11816528 ADDK.S2 -136,B15`).
   - Each iteration computes the 32-bit signed playback sample `B7` (`11816ce0 SMPY32.M2X B26,A5,B7`) and stores it sequentially into the stack buffer at `B15 + 8 .. B15 + 68`:
     ```
     11816d18   03b036f7           STW.D2T2      B7,*B12++[1]
     ```
   - After all 16 samples are generated (`!A2` at `11816cf0`), `A16` is set to `B15 + 8` (`11816cf0 ADD.L1X 8,B15,A16`).
   - In the final mixing loop (`11816d40`..`11816f54`, outer loop `B0 = 2` for L and R channels of `11f037b0`/`11f037f0`), the 16 int32 looper playback samples are read from `*A16++[1]` (`11816d2c`, `11816d3c`, `11816da0`, `11816de0`, `11816e20`), converted to float (`INTSP.L1`), multiplied by `A18 = 0x30000000` (`2^-31 = 4.65661287e-10f`, formed by `MVK 0,A18; SET A18,28,29,A18` at `11816d44`/`11816d60`), **written as 16 floats to stack buffer `B15 + 72` (`A17 = B15 + 18*4` at `11816d50`, `STW.D1T1 A7,*A17++[1]` at `11816db0`, `11816dec`, `11816e28`, `11816e88`, `11816ed0`)**, and simultaneously added into `11f037b0` (pass 1) and `11f037f0` (pass 2, where `A16` and `A17` reset to `B15+8` and `B15+72` at `11816e34`/`11816ef4`):
     ```
     11816db8   081d321b           ADDSP.L2X     B9,A7,B16
     ...
     11816dd0   028cde02 ||        MPYSP.M2X     B6,A3,B5
     ...
     11816de4   082002f7           STW.D2T2      B16,*+B8[0]
     11816df0   02160e03           MPYSP.M2      B16,B5,B4
     ...
     11816e1c   022036f7           STW.D2T2      B4,*B8++[1]
     ```
   - **Gain cells (`confirmed`):** Inside `118166d0`..`11816d24`, the looper playback sample is scaled by playback level ramp `*++B13[1]` (`118166c4`/`11816cbc`, where `B13 = 11f03e38 - 4`, smoothed from `11f03c64`/`11f03cd8`). When `118164c0` is bypassed (`*(11f03c58) == 0` at `11816516`), it jumps over the SDRAM/mix loops and exits at `118165ba`.

### B. Drum Machine / Rhythm Signal (`11817640`, called from `11818d60` at Step 15 `11818c54`)

1. **Caller & Producer (`confirmed`):**
   - At Swi Step 15 (`11818c54 CALLP 0x11818d60`), the very first instruction of `11818d60` is `11818d64 CALLP.S2 0x11817640,B3`.
   - `11817640` checks the Rhythm enable flag `*(11f03d54)` (`11817644 MVK 0x3d54,B20`, `1181766c LDW *+B20[0],B0`; set to `1` by `c0158d98` and `0` by `c0158dac`).
   - If `B0 == 0` (Rhythm off), `11817640` runs a short `SPLOOPD` (`118176a8`..`118176d2`) and returns at `118176d8` without touching `11f037b0`/`11f037f0` (`confirmed`).
   - If `B0 != 0` (Rhythm on), `11817690`/`11817694` executes a call-by-branch to **`11817520`** (`11817690 [B0] B.S1 0x118176e4`, `11817694 [B0] B.S1 0x11817520`, `118176e4 ADDKPC.S2 0x118176e8,B3,0`), where `11817520` is the **9-voice drum PCM sample fetcher** and `118176e8`..`11817934` is the **9-voice stereo panner and mixer** (`confirmed`).
2. **Drum Voice PCM Fetcher (`11817520` -> `11f039b0`, `confirmed`):**
   - `11817520` (`main.dis` lines 16620-16695) loops over **9 drum voices** (`B18 = 0..8`, `B17 = 0..0x100` in steps of `32` bytes, exit test `11817614 MVK 0x120,A3; CMPGT A3,B17,A0`).
   - For each voice `v` (`0..8`), it checks trigger/active state `11f03d58[v]` (`B19 = 11f03d58`, `LDW *+B19[B18],B1` at `11817550`) and current sample pointer `c0183840[v]` (`B9 = c0183840 + 4*v` at `11817558`) against the voice's sample start/length table at `c0183424 + 8*v` (`B7 = c018341c`, `*++B7[2]` = start address in `c075d0f0` sample ROM, `*+B7[1]` = byte length; initialized by `c015f4b8`..`c015f5e0`).
   - In a 16-iteration `SPLOOPD` (`ILC = 15` at `11817560`/`1181756c`), it reads 16 signed 16-bit PCM samples (`118175ac [B1] LDH.D2T2 *+B16[0],B5`), advances the voice read pointer by `+2` bytes per sample (`1181758c ADD.S2 2,B16,B5`, `118175a4 [B1] STW B5,*+B9[0]` — advancing by 32 bytes = 16 samples per block!), and writes 16 `int16_t` samples (or `0` if inactive) into **`11f039b0 + 32*v`** (`1181752c MVK 0x39b0,A3`, `118175b8 [B1] STH B5,*-B4[1]`, `118175c0 [!B1] STH A4,*-A3[1]`, or unrolled zero-fill `118175cc`..`11817608`).
   - Thus **`11f039b0`..`11f03acf` (288 bytes = 9 voices × 16 samples × 2 bytes)** holds the 9 isolated drum voice blocks (`int16_t[9][16]`, planar by voice) every audio block (`confirmed`).
3. **Drum Stereo Panner & Mixer (`118176e8`..`11817934`, `confirmed`):**
   - Loops 16 times (`A0 = 16` at `1181774c`, `SUB A0,1,A0` at `118178c8`, `B 0x11817760` at `118178cc`, with `A23` starting at `11f039ae` and pre-incrementing by `+2` bytes per sample via `1181776c LDH *++A23[1],A5`).
   - For each sample `i` (`0..15`), it loads the 9 voices from `11f039b0` at stride 16 halfwords (32 bytes):
     - Voice 0: `*+A23[0]` (`1181776c`)
     - Voice 1: `*+A3[0]` = `A23 + 32` (`11817774`)
     - Voice 2: `*+A3[16]` = `A23 + 64` (`11817778`)
     - Voice 3: `*+A6[0]` = `A23 + 96` (`118177a0`)
     - Voice 4: `*+A6[16]` = `A23 + 128` (`118177a4`)
     - Voice 5: `*+A9[0]` = `A23 + 160` (`118177ac`)
     - Voice 6: `*+A9[16]` = `A23 + 192` (`118177b0`)
     - Voice 7: `*+A17[0]` = `A23 + 224` (`118177bc`)
     - Voice 8: `*+A17[16]` = `A23 + 256` (`118177c4`)
   - Multiplies each voice by its per-voice gain/pan coefficients in `11f03d24`..`11f03d50` (`B16 = B25 = 11f03d54 - 0x48 = 11f03d0c`), sums into stereo accumulators (`SADD.L2`), scales by master rhythm gain cells at `11f03d0c` (`B25[0]`), `11f03d14` (`B17[0]`), and `11f03d20` (`B18[0]`), converts L and R drum samples to float (`INTSP.L2` at `11817838` and `11817860`, multiplied by `B11 = 0x30000000 = 2^-31`), and **adds them directly in place into `11f037b0[i]` (L) and `11f037f0[i]` (R)**:
     ```
     11817864   02a832e6           LDW.D2T2      *++B10[1],B5      ; B5 = 11f037b0[i] (L)
     11817868   0318ee02           MPYSP.M2      B7,B6,B6          ; B6 = drum_L[i] (float)
     ...
     11817878   0294c21a           ADDSP.L2      B6,B5,B5          ; B5 = drum_L[i] + 11f037b0[i]
     ...
     11817888   02a802f6           STW.D2T2      B5,*+B10[0]       ; 11f037b0[i] = sum_L
     1181788c   02aa02e6           LDW.D2T2      *+B10[16],B5      ; B5 = 11f037f0[i] (R)
     11817890   0210ce02           MPYSP.M2      B6,B4,B4          ; B4 = drum_R[i] (float)
     ...
     11817898   0214821a           ADDSP.L2      B4,B5,B4          ; B4 = drum_R[i] + 11f037f0[i]
     ...
     118178a0   022a02f6           STW.D2T2      B4,*+B10[16]      ; 11f037f0[i] = sum_R
     ```
   - Note: `11817640` does **not** write the stereo float drum mix to a separate buffer before adding `B6` (drum L) and `B4` (drum R) into `11f037b0[i]` / `11f037f0[i]`.

---

## 3. Separability of Drums and Looper

**Yes — Drums and Looper are completely separable and are added at two distinct stages of the audio Swi (`confirmed`):**

1. **They are never summed together before hitting `11f037b0`/`11f037f0` (`confirmed`):**
   - **Looper (`118164c0`)** runs at **Swi Step 6 (`11818bc0`, Pre-effects)** or **Swi Step 14 (`11818c50`, Post-effects)** via dispatcher `11818e60` (`11f03ed0[0..1]`). It always finishes before Step 15 (`11818c54`).
   - **Drums (`11817640`)** runs inside **Swi Step 15 (`11818c54` -> `11818d60` -> `11817640`)**, after Step 14 (`11818c50`) has already completed and before `11818d60` applies the master output volume `11f03e34`.
   - Furthermore, the Looper (`118164c0`) runs *before* Drums (`11817640`), which explains why the Looper never records the Drum Machine!

2. **Where each signal exists alone before being summed into `11f037b0`/`11f037f0` (`confirmed`):**
   - **Looper alone:**
     - **Stack buffer `B15 + 8` (`64` bytes, `int32_t[16]` mono)** and **`B15 + 72` (`64` bytes, `float[16]` mono)** inside `118164c0` (`11816d18`..`11816f28`, where `B15` was decremented by `136` at `11816528`).
     - Specifically, at `11816cf0` (`[!A2] ADD.L1X 8,B15,A16`), all 16 signed 32-bit integer looper playback samples (already scaled by the looper playback volume ramp) sit contiguously at `B15 + 8 .. B15 + 71`. And by the end of pass 1 (`11816ee4`), all 16 float looper playback samples sit at `B15 + 72 .. B15 + 135`.
     - Alternatively, by **algebraic difference on `11f037b0`/`11f037f0`**: when Looper is in Post mode (`11f03ed0[1] = 118164c0`, Step 14 at `11818c50`), `11f037b0`/`11f037f0` holds `Effects` before `11818c50` and `Effects + Looper` immediately after `11818c50` (when `*(11f03c58) != 0` and fade-out multiplier `*+B17[0]` at `11f03c54` is `1.0f`).
   - **Drums alone:**
     - **Raw 9-voice PCM buffer at `11f039b0`..`11f03acf` (`288` bytes, `int16_t[9][16]`)**: populated by `11817520` (called at `11817694`) and **still intact at TX pack time (`11818c64`)** because nothing after `11817640` writes to `11f039b0`. However, `11f039b0` is 9 unmixed 16-bit voices before per-voice pan/level (`11f03d24`..`11f03d50`) and rhythm master volume (`11f03d0c`/`11f03d14`/`11f03d20`).
     - **Mixed stereo float Drums (`drum_L`, `drum_R`)**: inside `11817640`'s sample loop (`11817760`..`118178f8`), `B6` holds `drum_L[i]` at `11817868` (`MPYSP.M2 B7,B6,B6`) and `B4` holds `drum_R[i]` at `11817890` (`MPYSP.M2 B6,B4,B4`) right before `ADDSP` adds `11f037b0[i]` (`11817878`) and `11f037f0[i]` (`11817898`).
     - Even simpler, **`11817640` is a standalone `CALLP` at `11818d64` (`CALLP.S2 0x11817640,B3`)** whose only effect on the audio stream is:
       $$\text{buf\_11f037b0}[i] \leftarrow (\text{buf\_11f037b0}[i] + \text{drum\_L}[i]) \times \text{mute\_11f03d08}$$
       $$\text{buf\_11f037f0}[i] \leftarrow (\text{buf\_11f037f0}[i] + \text{drum\_R}[i]) \times \text{mute\_11f03d08}$$
       where `*(11f03d08)` (`*+A18[0]` at `118178a4`/`118178bc`) is `1.0f`. Thus if `11f037b0`/`11f037f0` is zeroed before `11817640` (or saved before `11817640` and subtracted after `11817640`), `11817640` writes **pure stereo Drums alone** directly into `11f037b0`/`11f037f0`!

---

## 4. Tap Proposal

### Are Drums-alone and Looper-alone intact in static buffers at TX pack time (`11818c64`)?
- **No for stereo mixed Drums (`confirmed`)**: `11817640` adds `drum_L` (`B6`) and `drum_R` (`B4`) directly into `11f037b0`/`11f037f0` (`11817878`/`11817898`) without storing the mixed stereo drum signal to a dedicated buffer. Only the raw unmixed 9-voice `int16_t[9][16]` array at **`11f039b0`..`11f03acf`** is still intact in static L1D memory at `11818c64`.
- **No for Looper-alone in named static L1D (`confirmed`), though its stack buffer is untouched if no ISR preempts**: `118164c0` writes the 16 isolated mono looper playback samples (`int32_t[16]` at `B15 + 8` and `float[16]` at `B15 + 72`, where `B15 = SP_entry - 136`) on the stack before reclaiming the 136-byte frame (`11816f28 ADDK.S2 136,B15`). Because subsequent Swi calls (`11818d60`, `11818428`, `118186e0`, `11818aa0`) use at most 16 bytes of stack frame (`B15 - 16`), `B15 - 136 + 8` (`int32_t[16]`) and `B15 - 136 + 72` (`float[16]`) lie below their stack frames, **unless** a hardware interrupt (Hwi) preempts the Swi between Step 14 (`11818c50`) and Step 18 (`11818c64`) and overwrites the stack below `B15`. Thus relying on dead stack space at `11818c64` is unsafe against Hwi preemption, and a hook before/around Step 14/15 is cleanly deterministic (`confirmed`).

### Recommended Concrete Hook Points

#### Option A — Single Wrapper Hook Replacing `11818c54` (`CALLP.S2 0x11818d60,B3`) + Dispatcher Hook at `11818e60` (or Combined `11818c50`/`11818c54` Hook) (`confirmed`)

Because `11818c50` (`CALLP.S2 0x11818e60,B3`, Step 14) and `11818c54` (`CALLP.S2 0x11818d60,B3`, Step 15) are adjacent 32-bit instructions in the audio Swi (`main.dis` lines 18339-18340):
```
11818c4e       2626           MVK.L1        1,A4
11818c50   10004412 ||        CALLP.S2      0x11818e60,B3
11818c54   10002412           CALLP.S2      0x11818d60,B3
```
and `11f03830` (L, 64B) / `11f03870` (R, 64B) is **confirmed unused after `11817a90` (Step 12, `11818c44`)** (and was 100% zeros in the owner's listening test!), `11f03830` and `11f03870` can be used as free 16-sample staging buffers from Step 13 (`11818c48`) all the way through TX pack (`11818c64`)!

1. **Capturing Looper Alone (16 samples, mono `int32_t` or `float`, Works in both Pre and Post modes):**
   - **Hook point:** Inside `11818e60` (`11818e60`..`11818e80` has 7 trailing `NOP` words at `11818e84`..`11818e9c`, or hook `11816f28` at the epilogue of `118164c0`).
   - **Earliest code point where Looper exists alone:**
     - **As `int32_t[16]` mono (Q31 scale, post-looper-volume):** At **`11816cf0`** (or at epilogue **`11816f28`** before `ADDK.S2 136,B15`), buffer **`B15 + 8`** (`64` bytes, `16 × int32_t`) holds the exact 16 mono looper playback samples (`B7` stored via `11816d18 STW.D2T2 B7,*B12++[1]`).
     - **As `float[16]` mono (`[-1.0, +1.0)` scale, post-looper-volume):** At **`11816e34`** (end of pass 1) or **`11816f28`** (epilogue of `118164c0`), buffer **`B15 + 72`** (`64` bytes, `16 × float`) holds the exact 16 mono float looper playback samples (`A7` stored via `STW.D1T1 A7,*A17++[1]`).
     - Note: When Looper is bypassed (`*(11f03c58) == 0` at `11816516`), `118164c0` takes the early exit at `1181652c -> 118165a8`, so a hook at `11818e60` (or `118164c0`) should zero the staging buffer (`11f03830`) when `*(11f03c58) == 0`, and copy `B15 + 72` (or `B15 + 8`) to `11f03830` (`64` bytes) when `*(11f03c58) != 0`.
   - **Alternative zero-patch-inside-`118164c0` method (if Looper is in Post mode, `A4=1`):**
     - Hook `11818c54` (`CALLP 0x11818d60`): snapshot `11f037b0` before `11818c50` (`CALLP 0x11818e60`) and subtract it from `11f037b0` after `11818c50`:
       $$\text{Looper\_L}[i] = \text{buf\_11f037b0}_{\text{after } 11818c50}[i] - \text{buf\_11f037b0}_{\text{before } 11818c50}[i]$$
     - (Hooking `11816f28` or `11818e60` to copy `B15 + 8` / `B15 + 72` is even better because it works in **both Pre and Post** looper modes!)

2. **Capturing Drums Alone (16 samples, stereo `float[2][16]`):**
   - **Earliest code point where mixed stereo Drums exist alone:** Inside `11818d60` right after `11818d64` (`CALLP.S2 0x11817640,B3`) returns at **`11818d68`**.
   - **How to capture without touching `11817640`'s pipelined loop:**
     - Replace `11818c54` (`CALLP.S2 0x11818d60,B3`) with a `CALLP` to a small veneer:
       1. Save the pre-drum `11f037b0` (L, 64B) and `11f037f0` (R, 64B) into a 128-byte scratch buffer (or zero `11f037b0`/`11f037f0` after saving them).
       2. Call `11817640` (the drum mixer).
       3. If `11f037b0`/`11f037f0` was zeroed in step 1: `11f037b0` (L) and `11f037f0` (R) now contain **pure stereo float Drums alone** (`drum_L[0..15]`, `drum_R[0..15]`)! Copy them to the USB drum staging buffer (or `11f03870`), then add the saved pre-drum `11f037b0`/`11f037f0` back into `11f037b0`/`11f037f0` (if `*(11f03d54) != 0` and `*(11f03d08) != 0`).
       4. Equivalently (without zeroing): let `11817640` run normally on `11f037b0`/`11f037f0`, then compute:
          $$\text{drum\_L}[i] = \text{buf\_11f037b0}_{\text{after } 11817640}[i] - \text{buf\_11f037b0}_{\text{before } 11817640}[i]$$
          $$\text{drum\_R}[i] = \text{buf\_11f037f0}_{\text{after } 11817640}[i] - \text{buf\_11f037f0}_{\text{before } 11817640}[i]$$
       5. Continue with the rest of `11818d60` (`11818d68`..`11818dd4`) so the pedal's main output is 100% bit-identical to stock.

### Summary Table of Tap Signals

| Signal | Producer Function | Earliest Isolated Point | Buffer / Location | Format | Intact at `11818c64` without 2nd hook? |
|---|---|---|---|---|---|
| **Looper alone** | `118164c0` (via `11818e60` / `11f03ed0[0..1]`) | `11816cf0` (int32) / `11816e34`..`11816f28` (float) | Stack `B15 + 8` (`int32_t[16]`) & `B15 + 72` (`float[16]`) inside `118164c0` (`*(11f03c58) != 0`) | Mono, 16 samples (`int32` Q31 or `float`) | **No** (stack frame reclaimed at `11816f28`; copy to `11f03830` at `11816f28`) |
| **Drums alone (raw voices)** | `11817520` (called by `11817640` at `11817694`) | `11817630` (return of `11817520`) | `11f039b0`..`11f03acf` (288 B) | 9 voices × 16 samples, `int16_t[9][16]` planar | **Yes** (`11f039b0` is untouched after `11817520`), but unmixed/unpanned |
| **Drums alone (stereo mix)** | `11817640` (called by `11818d60` at `11818d64`) | `11817868` (`B6` L) & `11817890` (`B4` R) per sample; or `11818d68` (return of `11817640`) | In-place delta on `11f037b0` (L) / `11f037f0` (R) across `11818d64 CALLP 0x11817640` | Stereo planar `float[2][16]` (64 B L + 64 B R) | **No** (requires hook at `11818c54` / `11818d64` before `11818d68` scales by master vol `11f03e34`) |

STATUS: done
