# CF Master: Design Document & Architecture (2026-10-19)

Target: David Gilmour's 1979 *Comfortably Numb* studio rig (Kit Rae) implemented on the Zoom G1X Four's
TMS320C6745 DSP. Designed from first principles to the C6745 architecture rules (`docs/C6745_DESIGN.md`).

---

## 1. The Target: 1979 *Comfortably Numb* Studio Rig

Historical research (Kit Rae, *The Wall* recording sessions at Super Bear / Britannia Row, 1979):
The studio lead tone was produced by running the pedalboard into a split amplifier setup:

```
[ Guitar (Stratocaster bridge pickup) ]
                |
                v
      [ (CF DynaComp) ]                  (optional studio leveling)
                |
                v
     [ '74 Ram's Head Big Muff ]         (CF Muff: sustain, tone, volume)
                |
                v
     [ 1978 Electric Mistress ]          (CF Mistress: rate, range, color, matrix)
                |
                v
     [ MXR Digital Delay System 1 ]      (CF Delay: 480 ms, low feedback, wet mix)
                |
                +---------------------------------------+
                |                                       |
                v                                       v
      [ Hiwatt DR103 (100W) ]                 [ Alembic F-2B Preamp ]
                |                                       |
                v                                       v
      [ WEM 4x12 (Fane Crescendo) ]          [ 2x Yamaha RA-200 Rotary Cabinets ]
                |                                       |
                v (Mono / Center)                       v (Stereo Miked L / R)
                +-------------------+-------------------+
                                    |
                                    v
                           [ Stereo Main Mix ]
```

### Sonic Roles
1. **CF Muff**: Aggressive harmonic fuzz and sustained compression with mid-scoop (or tuned flat mid).
2. **CF Mistress**: Subtle metallic comb-filtering sweep, brightening upper harmonics.
3. **CF Delay**: ~480 ms slapback/echo adding depth without cluttering the fast runs.
4. **CF Watt (DR103 + WEM)**: Clean headroom with high-voltage punch, tight low-end, and power-stage compression.
5. **CF RA200 (Alembic F-2B + Yamaha RA-200)**: Warm Fender-style tube front end driving three rotating speakers at 120 degrees, producing complex spatial chorus/tremolo sidebands at 3x the rotor rate.

---

## 2. C6745 Architectural Execution Strategy

### 2.1 The Feedback Bottleneck & Idle Functional Units
On the TMS320C6745 (8 functional units per cycle: .L1 .S1 .M1 .D1 / .L2 .S2 .M2 .D2, 4-cycle float latency):
- **CF Watt's NFB loop is serial**: The loop (phase inverter -> EL34 power tubes -> output tap -> residual feedback) has a strict dependency chain taking ~200 cycles of latency per sample.
- At 2x oversampling (32 samples per block), this NFB recurrence takes ~8.2k cycles per block.
- During these ~200 cycles per sample, **the majority of the DSP's execution units sit completely idle**.

### 2.2 Co-Scheduling Parallel Paths
Because the Alembic F-2B + Yamaha RA-200 rotary path does not depend on the Hiwatt power stage, its computations can run **concurrently within the idle execution slots of the Watt NFB loop**:
- The RA-200 fractional delay reads (6 Lagrange reads per sample for 3 speakers x 2 cabinets).
- The directivity weighting `(1 + beta * cos(a))`.
- The crossover and speaker EQ biquad updates.
- The rotor phasor updates.

**Result**: The entire rotary cabinet simulation (~4k cycles/block) is co-scheduled inside the idle execution packets of the NFB loop, executing at near-zero marginal cycle cost.

### 2.3 Oversampling Strategy
- **Nonlinear Stages**: CF Muff (diode solvers) and CF Watt (12AX7 triodes, LTP phase inverter, EL34 power tubes) generate high-frequency distortion harmonics and require oversampling to avoid digital aliasing.
- **Linear / Delay Stages**: CF Mistress, CF Delay, and the RA-200 rotary delay line operate cleanly at 1x base rate (44.1 kHz).
- **Domain Layout Options**:
  - **Option A (Unified Front-of-Amp 2x Domain)**:
    Muff runs at 2x. Decimate to 1x for Mistress & Delay. Upsample to 2x for Watt and run F-2B/RA-200 in parallel.
    *Advantage*: Retains authentic pedal order (flanger and delay hitting the cranked amp inputs). The 1x->2x halfband IIR filters (`hbi1`) cost only ~100 cycles per block.
  - **Option B (Single Monolithic 2x Region)**:
    Input (1x) -> Upsample 2x -> Muff (2x) -> Watt (2x) -> Downsample 1x -> Mistress (1x) -> Delay (1x) -> RA-200.
    *Advantage*: Single upsample/downsample pair.
    *Trade-off*: Modulation and delay sit post-amp (studio FX-loop style).

The CF Master skeleton supports both routing modes and allows stage-by-stage bypass.

---

## 3. Packaging & Memory Strategy: The Two Variants

The exact packaging depends on the results of the `CFM5` and `CFM2` probes (`docs/CF_MASTER_PROBE_2026-10-19.md`) currently awaiting test on the pedal. Both variants are fully planned:

### Variant 1: Monolithic 5-Slot Kernel (`CFM5`)
*Condition: If the pedal loads header `0x58 = 5` and provides unified patch control.*
- **Slot Usage**: Claims all 5 slots (header 0x58 = 5, `g1_slots: 5`).
- **Code Size**: Must fit within the 40 KiB slot heap limit (`tools/check_slot_mem.py`) unless the probe proves multi-slot ELF allocations are merged. Code sharing between Watt and F-2B triode solvers (`hw_tube_fast`, `hw_tube_adaa`) keeps `.text` well within budget (~28-32 KB).
- **Memory Buffer**:
  - Slot 0 work buffer `instance[3]` provides 0x81330 B (529,200 bytes ≈ 516.8 KiB).
  - Allocation map:
    - `0x000000 - 0x000350`: Master kernel state & cached coefficients (~850 B).
    - `0x000350 - 0x000B50`: Mistress BBD state & delay line (~2.1 KB).
    - `0x000B50 - 0x001000`: RA-200 rotor state, 128-sample line & filters (~1.2 KB).
    - `0x001000 - 0x055000`: MXR DDS-1 480 ms delay buffer (21,168 float32 samples = 84.7 KB; or up to 2.0 s line = 352.8 KB).
    - Remaining: > 150 KB free headroom.
- **Control**: 12 parameters (stomphacks maximum) across 3 or 4 pages.

### Variant 2: Split Multi-Slot Rig (`CFM_PRE` 2-Slot + `CFM_AMP` 3-Slot)
*Condition: If the pedal enforces a 2-slot maximum, or if 12 knobs are insufficient to control all 5 effects.*
- **Unit 1: `CFM_PRE` (Patch Slots 1-2, 2 Slots)**:
  - Modules: DynaComp + Ram's Head Muff + Electric Mistress.
  - Dedicated 40 KiB slot heap.
  - 12 Knobs:
    - Page 1 (Dyna & Muff): Dyna Sens, Dyna Level, Muff Sustain, Muff Tone.
    - Page 2 (Muff & Mistress): Muff Volume, Mistress Rate, Mistress Range, Mistress Color.
    - Page 3 (Switches): Mistress Matrix, Muff Mid-Flat, Preamp Master Level, Dry/Wet.
- **Unit 2: `CFM_AMP` (Patch Slots 3-5, 3 Slots)**:
  - Modules: MXR Delay + Hiwatt DR103 + WEM Cab + Alembic F-2B + Yamaha RA-200.
  - Dedicated 40 KiB slot heap.
  - Work buffer: 529 KB for delay buffer and rotary state.
  - 12 Knobs:
    - Page 1 (Hiwatt): Drive/Vol, Treble, Middle, Bass.
    - Page 2 (Hiwatt & Delay): Presence, Master, Delay Time (480ms), Delay Mix.
    - Page 3 (RA-200 Rotary): Rotor (Off/Slow/Fast), Rotor Speed, RA-200 Mix, Stereo Width.

---

## 4. Parameter Mapping Plan

### Variant 1 (12 Knobs on 1x5-Slot Effect)
Curated specifically for the *Comfortably Numb* tone so that all crucial tonal variables are accessible:

| Knob | Parameter | Range | Default | Function |
|---|---|---|---|---|
| **1** | `Muff Sust` | 0 - 100 | 75 | Ram's Head fuzz sustain / gain |
| **2** | `Muff Tone` | 0 - 100 | 50 | Big Muff tone control (counter-clockwise dark, clockwise bright) |
| **3** | `Muff Vol`  | 0 - 100 | 70 | Fuzz output level into flanger / amp |
| **4** | `Mist Rate` | 0 - 100 | 35 | Flanger LFO rate (0.05 to 10 Hz) |
| **5** | `Mist Colr` | 0 - 100 | 65 | Flanger feedback / comb depth |
| **6** | `Dly Time`  | 0 - 1000| 480 | Delay time in ms (default: 480 ms DDS-1 setting) |
| **7** | `Dly Mix`   | 0 - 100 | 30 | Delay wet level (echo volume) |
| **8** | `Amp Drive` | 0 - 100 | 60 | Hiwatt DR103 normal/brilliant channel volume |
| **9** | `Amp Mstr`  | 0 - 100 | 80 | Hiwatt master volume (power tube saturation & sag) |
| **10**| `Rotor`     | 0 - 2   | 1  | RA-200 Rotor mode: 0 = Off, 1 = Slow (chorus), 2 = Fast |
| **11**| `Rot Speed` | 0 - 100 | 50 | RA-200 slow rotor speed trim (0.4 - 3.0 Hz) |
| **12**| `Rig Blend` | 0 - 100 | 50 | Balance between Hiwatt/WEM (0) and Alembic/RA-200 (100) |

---

## 5. Stage-Off Profiling Architecture

For bench verification (`tools/ua_bench.py`) and on-hardware timing checks, the kernel includes compile-time isolation switches:

```c
#define CFM_STAGE_OFF_MUFF   0   /* Set to 1 to bypass Muff DSP */
#define CFM_STAGE_OFF_MISTRX 0   /* Set to 1 to bypass Mistress DSP */
#define CFM_STAGE_OFF_DELAY  0   /* Set to 1 to bypass Delay DSP */
#define CFM_STAGE_OFF_WATT   0   /* Set to 1 to bypass Hiwatt/WEM DSP */
#define CFM_STAGE_OFF_RA200  0   /* Set to 1 to bypass Alembic/RA-200 DSP */
```

Each stage-off switch replaces that module with a unity-gain wire while leaving all memory addressing and scheduling untouched. This allows measuring the exact cycle contribution of each module directly on the pedal.

---

## 6. Verification Plan

1. **Host Integration Test (`tests/host/cfmaster_test.cpp`)**:
   - Compiles real `cfmaster_kernel.h` with MSVC 32-bit.
   - Tests audio passing through all 5 stages active.
   - Verifies stage-off configurations.
   - Tests parameter smoothing, bypass crossfades, and bounds safety (finite, no NaN, within ±8.0 V).
   - Validates memory buffer alignment and offsets.
2. **TI C6000 Pipeline & Loop Report (`tools/build_g1.sh cfmaster`)**:
   - Software pipelining verification for all loops via `tools/c6x_loop_report.py`.
   - Resource and dependency bounds check (`build/CFMASTER.LOOPS.md`).
3. **Slot Memory Heap Audit**:
   - Verifies that `.text`, `.const`, `.bss`, and `.data` strictly satisfy the ≤ 40 KiB slot heap limit via `tools/check_slot_mem.py`.
