# Drums & Looper Isolated Signal Analysis (2026-10-17)

## 1. Writer Chain of 11f03730 / 11f03770 in One Audio Block

In one 16-sample audio block (`g_Swi_AudioProcess` at `11818ba0`..`11818c84`), `11f03730` (L, 16 × int32, 64 bytes) and `11f03770` (R, 16 × int32, 64 bytes) are written at **four distinct points** in Swi order (`confirmed`):

1. **Swi Step 3 — `11818bb0` `CALLP 0x11818b20` (RX unpack, `confirmed`):**
   - Reads the inactive McASP0 RX ping-pong DMA half (`11f03530` or `11f035b0`), unpacks 16 stereo frames (`LDNDW *A5++[1],A7:A6` at `11818b50`), scales by `0x80000000` (`SMPY32` at `11818b70`/`11818b74`), and stores planar int32 dry ADC samples into `11f03730` (`*B6++[1]` at `11818b90`, where `B6 = 11f03770 - 0x40 = 11f03730`) and `11f03770` (`*A8++[1]` at `11818b94`, `A8 = 11f03770`).

2. **Swi Step 4 — `11818bb4` `CALLP 0x11816f60` (Input conditioning / DI capture, `confirmed`):**
   - `A28` is initialized to `11f03770` (`11816f74`/`11816f84`). Reads `*-A28[16..10]` (`11f03730`..`11f03748`, L channel) and `*+A28[0..6]` (`11f03770`..`11f03788`, R channel), runs a saturating fixed-point filter, and **copies the unconditioned/filtered L channel (`*-A28[16]`) and R channel (`*A28++[1]`) identically** via paired stores (`118172b4`/`118172cc`, `11817360`/`11817378`, `118173ec`/`11817400`, `1181744c`/`1181745c`, `11817494`/`118174a0`, `118174d0`/`118174d4`, `118174e4`/`118174e8`), turning `11f03730` and `11f03770` into dual-mono conditioned guitar input before `11818360` converts both to float (`11f037b0`/`11f037f0`) at Step 5 (`11818bb8`).
   - Note on `11f03930` (USB ch 7-8 clean guitar DI): `118183d0` (Step 7, `11818bc8`) copies the fresh float guitar input from `11f037b0` into `11f03928`/`11f03968` (overlapping `11f03930`/`11f03970`), which is why `11f03930`/`11f03970` hold clean guitar DI (`confirmed`).

3. **Swi Step 6 or Step 14 — `11818bc0` (`A4=0`) or `11818c50` (`A4=1`) `CALLP 0x11818e60` -> `118164c0` (Looper engine, `confirmed`):**
   - `11818e60` dispatches through the 2-entry function pointer table at `11f03ed0` (`11818e64`..`11818e70`).
   - `c016a8e0` (`main.dis` lines 126777-126796) initializes both `11f03ed0[0]` and `11f03ed0[1]` to `c016d180` (no-op `BNOP B3,5`), and then writes **`118164c0`** into `11f03ed0[A4]` (`c016a904`..`c016a90e`), where `A4` (`0` = Pre / slot 0, `1` = Post / after effect chain) is the Looper position setting (`confirmed`).
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

## 2. The Add of Drums and Looper (Candidate Buffers & Producers)

(in progress)

## 3. Separability of Drums and Looper

(in progress)

## 4. Tap Proposal

(in progress)

STATUS: in_progress
