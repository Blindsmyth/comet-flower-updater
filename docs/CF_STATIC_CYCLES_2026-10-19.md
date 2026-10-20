# CF Static Cycles & Loop Pipelining Report (2026-10-19)

Compiler: TI CGT C6000 LTS 8.5.0 (`cl6x -mv6740 -O3 -k --src_interlist`)  
Target Architecture: TI TMS320C6745 (375 MHz, 132,354 cycle budget per 16-sample audio block at 44.1 kHz).

---

## 1. Summary of Optimizations & Static Estimates

| Effect | ZD2 File | Group / Slots | Declared dspload | Measured (10-18) | Static Estimate (cycles/block) | Pipelined Loops |
|---|---|---|---|---|---|---|
| **CF RAT** | `RATX.ZD2` | DRIVE / 1 | 55 | 16.0k | **~10.5k** | 26 / 26 (100%) |
| **CF 808** | `DRV808X.ZD2` | DRIVE / 1 | 56 | 16.2k | **~11.8k** | 13 / 13 (100%) |
| **CF Watt (2x)** | `DR103.ZD2` | AMP / 1 | 69 | 20.6k (default) / 25.1k (cranked) | **~19.2k** | 26 / 30 (preamp audio 100%) |
| **CF RA200** | `RA200X.ZD2` | MOD / 1 | 30 | (new effect) | **~4.0k** (+ derivation on turn) | All audio loops pipelined |
| **CF Master** | `CFMAST.ZD2` | EXT / 5 | 80 | - | **~48k** | (monolithic > 40 KiB slot limit) |
| **CFM Pre** | `CFMPRE.ZD2` | EXT / 2 | 35 | - | **~24k** | 35 / 36 |
| **CFM Amp** | `CFMAMP.ZD2` | EXT / 3 | 45 | - | **~26k** | Audio loops pipelined |

---

## 2. Detailed Loop Analysis

### A. CF RAT (`rat_g1.h`)
Stage-major block decomposition eliminated scalar overhead and recurrence penalties:
- **Pass 1 (Input Leg)**: line 225, 128 trips, ii 28 (3 in parallel).
- **Pass 2 (Op-amp stage & LM308 slew)**: line 273, 128 trips, ii 28 (3 in parallel).
- **Pass 3 (Diode table lookup)**: line 302, 128 trips, **ii 5** (hardware resource bound, **10 iterations in parallel**!).
- **Pass 4 (Filter Tone SVF)**: line 336, 128 trips, ii 28 (2 in parallel).
- **Audio Crossfade**: `ratx.c:69`, 16 trips, **ii 5** (8 in parallel).
- **Total**: 26 loops, **0 disqualified / 0 unpipelined**.

### B. CF 808 (`ts808_exact.h`)
Continuous block vectorization eliminated per-sample function call overhead:
- **Diode Circuit Stage**: line 235, 128 trips, **ii 57** (2 in parallel, continuous execution over 128 trips without 16-frame sub-block restarts).
- **Tone Network**: line 268, 128 trips, **ii 16** (3 in parallel).
- **Audio Crossfade**: `drv808x.c:68`, 16 trips, **ii 5** (8 in parallel).
- **Total**: 13 loops, **0 disqualified / 0 unpipelined**.

### C. CF Watt / DR103 (`hiwatt_amp.h`)
2-pass tube block split removed register pressure from 25 concurrent tube constants:
- **Preamp Pass 1 (Geometry, Region Select, Tanh)**: line 332, 32 trips (2x oversampled), ii 16 (6 in parallel).
- **Preamp Pass 2 (Polynomial Mean Tanh)**: line 350, 32 trips, **ii 9** (10 in parallel!).
- **Unpipelined Loops (4)**:
  - `hiwatt_netgen.h:56` and `:73`: Nodal derivation matrix solver, executed only when knobs turn.
  - `hiwatt_amp.h:248` (2 loops): Non-linear Newton convergence check control code.

---

## 3. dspload Calibration Mapping

Zoom uses the formula `dspload = 7 + 3 × kcycles` (where `kcycles` is thousands of cycles per 16-sample block).
The hardware threshold for `Process Overflow` (DSP mute) is cumulative `dspload ≥ 270` across the patch chain.

- RATX: 55 raw (calibrated for 16.0k worst-case measured).
- DRV808X: 56 raw (calibrated for 16.2k worst-case measured).
- DR103: 69 raw (calibrated for 20.6k default, 25.1k cranked).
- RA200X: 30 raw (calibrated for ~4.0k static).
