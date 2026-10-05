# 05 — Zoom "TS Drive" vs our "Green 808" (static analysis)

Date: 2026-10-04. Zoom: `TS_DRIVE.ZD2` v1.x (id 03000010, dspload 39.37) from the
owner's backup, read with `dis6x` plus its symbol table. Ours: `effects/drv808`
(Comet Flower DriveMobileCore port, dspload declared 40, unmeasured).
Analysis for comparison only; nothing of Zoom's code is reused.

## Zoom TS Drive: what the binary shows
| Part | Evidence | Reading |
|---|---|---|
| Knobs | PRME: Gain, **Boost** (on/off), Tone, VOL | Boost is a switch we do not have |
| Clipper | `TS_Drive_CLIPPER_KAWAOD`, 192 B | `u=p0·x; a=clamp(u·(x<0?p7:p4)); b=clamp(p1·u); c=clamp(u·(x<0?p5:p2)+(x<0?p6:p3)); y=a·c+b·|a−1|`: a piecewise-quadratic soft clipper with **separate negative-side parameters** (asymmetric). Not a circuit model. |
| Oversampling | `OVS_COE_bn` (6) / `OVS_COE_an` (5) | 5th-order IIR low-pass, −3 dB at 0.12·fs, −58 dB at 0.25·fs, so **4x** (corner ≈ 21 kHz at 176.4 kHz). |
| Drive | `TS_Drive_tbl`: 12 pairs, gain 1.33 → 9.89, second value 1.0 → 0.81 | Knob position → linear pre-clip gain (max ~10x) + trim |
| Tone | `TS_Drive_Tone_tbl`: 12 pairs, 3450 → 20000 Hz, −20 → −13 dB | Tone sweeps a **high-shelf cut** |
| Level | `TS_Drive_Level_tbl`: 0.005 → 5.75 | Knob → output gain |
| Fixed EQ | `_Fx_DRV_TS_Drive_Coe` defaults: several biquads (e.g. `1.2632, −1.5203, 0.3677 / 1.5203, −0.6310`) and first-order high-passes | Fixed pre/post voicing filters |
| Anti-aliasing beyond OS | none seen | No ADAA |

## Side by side
| | Zoom TS Drive | Green 808 (ours) |
|---|---|---|
| Model | Voiced: gain table → soft clipper → shelf tone + fixed EQ | Circuit: TS808 component values (R4/C3, R6+P1, 51 pF, R7/C5, R8/C6) |
| Clean bass | Fixed EQ (no frequency-split gain) | 720 Hz split: below 720 Hz bypasses the clipper, as in the circuit |
| Max drive | ~10x linear into the clipper | G = 1 + (51k + 500k·wiper²)/4.7k, up to ~118 |
| Clipper | Piecewise quadratic, asymmetric | Diode curve (MA150, Vf 0.6, knee 0.08) inside the op-amp loop, symmetric |
| Drive-dependent HF | via tables | 51 pF softening pole tracks drive (61 kHz → 5.6 kHz) |
| Tone | High-shelf corner 3.45–20 kHz | TS pole-zero network, zero 723 Hz → 33 kHz, pole 3.29 kHz |
| Aliasing control | 4x OS, IIR (non-linear phase) | 2x OS, linear-phase FIR + first-order ADAA |
| Extras | Boost switch | none |
| Load | 39.37 declared | 40 declared, real cost unmeasured |

## Open
- Signal flow inside `Fx_DRV_TS_Drive` (4.4 KB of hand-scheduled SPLOOP code): order
  of the fixed EQ stages and where Boost acts. Needs deeper disassembly.
- Clipper parameter values p0..p7 at run time (passed by pointer; probably in the
  coefficient table near `12.72, 1.0, 1.0, 23.93, 0, 0.225, 106.36…`).
- A sound comparison needs either a reamp (PC out → pedal in, record USB out) or a
  full Python re-implementation of Zoom's chain.
