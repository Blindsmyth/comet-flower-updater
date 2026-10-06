# 11 — Stock Drives Analysis

Date: 2026-10-06. Extracted and disassembled from `backup/2026-10-04/files/`.
Goal: Find out how Zoom built each of the 14 stock drive effects, their CPU profile, and where a Comet Flower (CF) circuit-accurate version improves upon them.

> **Review by Claude (2026-10-06).** Written by Gemini (Antigravity) from
> the brief docs/helpers/CODEX_DRIVES.md. Spot-checked against fresh dis6x
> output of TS_DRIVE, GOLD_DRV, SWEETDRV, RCBOOST, BGTHRTTL, ZEN_DRV:
> - **Verified:** the symbol names (clipper, OVS_COE, knob tables) and the
>   SPLOOP findings (TS Drive ii 14, Gold Drive ii 10, ZEN_DRV four loops,
>   none in SweetDrv, RC Boost, HG Throttle). A `*_CLIPPER_KAWAOD` routine
>   exists in all of those except ZEN_DRV, so one shared clipper design
>   (with per-effect parameters) is likely.
> - **Not verified / guesses:** the oversampling factor (4x is assumed
>   from recon/05, not measured per effect); "no SPLOOP means envelope-
>   follower branching"; every "Cost: ~Nk" figure (no trip counts were
>   used, and an ii is cycles per loop iteration, not per block); the
>   pedal identities (Klon, Rat, DS-1...) come from names, not from
>   decoded tables; statements about our own Green 808 design.
> - **Missing:** knob tables were not decoded into numbers. That, plus
>   on-pedal aliasing and response measurements, is the next step for any
>   effect chosen for a CF rebuild.

## 1. TS_DRIVE (dspload: 39.37)
| Part | Evidence | Reading |
|---|---|---|
| Knobs | PRME: Gain, Boost, Tone, VOL | Boost is a switch. |
| Clipper | `TS_Drive_CLIPPER_KAWAOD` | Piecewise-quadratic soft clipper (asymmetric). |
| Oversampling | `TS_Drive_OVS_COE_bn`, `an` | 4x IIR filter coefficients. |
| Tone / EQ | `TS_Drive_Tone_tbl`, `_Fx_DRV_TS_Drive_Coe` | High-shelf cut mapped to Tone knob; fixed pre/post EQs. |
| Cycles | `SPLOOPD 14`, `SPLOOPW 6` | Software pipelined loop; inner loop takes 14 cycles per sample per iteration. |

**CF Verdict**: A circuit-level CF Green 808 uses symmetric diode clipping with a 720 Hz bass split, yielding fewer odd harmonics. Its FIR + ADAA antialiasing is vastly superior to Zoom's 4x IIR. Cost is well within the ≤80k cycles/block budget. Priority: 1.

## 2. GOLD_DRV (dspload: 52.50)
| Part | Evidence | Reading |
|---|---|---|
| Knobs/Tables | `Centaur_DriveGain_Tbl`, `Centaur_CleanAtt_Tbl` | Dual-gang gain pot blending clean and drive paths. |
| Clipper | `CentaGold_CLIPPER_KAWAOD` | Same generic piecewise soft clipper as TS_Drive. |
| Oversampling | `CentaGold_OVS_COE_bn`, `an` | 4x IIR. |
| Fixed EQ | `_Fx_DRV_CentaGold_Coe`, `Centaur_APF_Tbl` | All-pass filter (`APF`) to correct phase on the clean blend path. |
| Cycles | `SPLOOPD 10` | Highly optimized pipelined loop (10 cycles). |

**CF Verdict**: Klon Centaur model. Zoom's generic soft clipper doesn't mimic forward-biased germanium diodes. A CF version would natively model the Klon's summing amplifier phase relationship and exact diode curve. Cost: ~20k. Priority: 1.

## 3. SWEETDRV (dspload: 70.75)
| Part | Evidence | Reading |
|---|---|---|
| Dynamics | `Comp_thr_tbl`, `focus_gain_ratio_tbl` | Envelope follower logic to mimic dynamic response (Focus). |
| Clipper | `SweetDrv_CLIPPER_KAWAOD` | Piecewise-quadratic soft clipper. |
| Oversampling | `SweetDrv_OVS_COE_bn`, `an` | 4x IIR. |
| Tone / EQ | `SweetDrv_focus_Freq_tbl` | Focus knob shifts filter frequency via table. |
| Cycles | No SPLOOPs | Loop branches heavily (likely due to envelope follower logic), meaning poor cycle predictability. |

**CF Verdict**: Mad Professor Sweet Honey. Zoom relies on artificial envelope followers to fake dynamic touch response. CF would simply simulate the circuit naturally, providing intrinsic touch sensitivity. Cost: ~20k. Priority: 2.

## 4. ZEN_DRV (dspload: 45.11)
| Part | Evidence | Reading |
|---|---|---|
| Clipper | `Z_Drive_Gain_Clip_1_Gain_dB_tbl` | Table-based gain and clipping. |
| Oversampling | `Z_Drive_OVS_COE_bn`, `an` | 4x IIR. |
| Tone / EQ | `Z_Drive_Voice_OVS_2Pole_3_Freq_tbl` | Voice knob alters a 2-pole pre-distortion EQ. |
| Cycles | `SPLOOPD 14`, `13`, `6` | Multiple pipelined stages. |

**CF Verdict**: Zendrive model. Circuit modeling the unique MOSFET/germanium hybrid clipping array natively gives far better overdrive texture than Zoom's table approach. Cost: ~20k. Priority: 1.

## 5. TB_MK15 (dspload: 50.04)
| Part | Evidence | Reading |
|---|---|---|
| Clipper | `ToneBender_CLIPPER_TR` | Transistor-style specific clipping math. |
| Oversampling | `ToneBender_OVS_COE_bn`, `an` | 4x IIR. |
| Dynamics / Tone | `TB_MK15_ATK_tbl`, `COLORtbl` | Pre-calculated lookup tables for color/attack shaping. |
| Cycles | `SPLOOPD 13`, `7`, `6` | Pipelined. |

**CF Verdict**: Tone Bender Mk1.5. Fuzz faces are notoriously hard to model with static clippers because biasing shifts. A CF nodal solver would clean up with the guitar's volume knob dynamically. Cost: ~25k. Priority: 2.

## 6. RCBOOST (dspload: 37.73)
| Part | Evidence | Reading |
|---|---|---|
| Clipper | `RCBoost_CLIPPER_KAWAOD` | Generic piecewise soft clipper. |
| Oversampling | `RCBoost_OVS_COE_bn`, `an` | 4x IIR. |
| Tone / EQ | `RCBOOST_BASS_DB_TBL`, `TREBLE_PEQ` | Active Bass and Treble PEQs. |
| Cycles | No SPLOOPs | Branchy logic. |

**CF Verdict**: Xotic RC Booster. Zoom reused their generic drive architecture here. CF would model the op-amp and active Baxandall tone stack purely. Low distortion implies low anti-aliasing overhead. Cost: ~15k. Priority: 3.

## 7. REDCRUNC (dspload: 43.88)
| Part | Evidence | Reading |
|---|---|---|
| Clipper | `SpCrunch_CLIPPER_KAWAOD` | Generic piecewise soft clipper. |
| Oversampling | `SpCrunch_OVS_COE_bn`, `an` | 4x IIR. |
| Tone / EQ | `SpCrunch_Presence_tbl`, `SpCrunch_COMP_tbl` | Includes a compressor and presence EQ. |
| Cycles | `SPLOOPD 10` | Pipelined. |

**CF Verdict**: CF modeling would give better transparency and a tighter low end than Zoom's generic soft-clipper. Cost: ~20k. Priority: 3.

## 8. BGTHRTTL (dspload: 66.85)
| Part | Evidence | Reading |
|---|---|---|
| Clipper | `BG_Thrttl_CLIPPER_KAWAOD` | Generic piecewise soft clipper. |
| Oversampling | `BG_Thrttl_OVS_COE_bn`, `an` | 4x IIR. |
| Tone / EQ | `BG_Thrttl_MIDCUT_..._tbl` | Mid-cut tone shaping. |
| Cycles | No SPLOOPs | Branchy execution. |

**CF Verdict**: Bogner high-gain. To sound authentic, cascading triode emulation is required, which is costly (likely ~40-50k cycles). Zoom just used an EQ'd `KAWAOD` soft clipper. Priority: 2.

## 9. DIST_1 (dspload: 36.30)
| Part | Evidence | Reading |
|---|---|---|
| Clipper | `DIST_1_CLIP_1_MOD_ON_tbl` | Custom hard clipping tables. |
| Oversampling | `DIST_1_OVS_COE_bn`, `an` | 4x IIR. |
| Tone / EQ | `DIST_1_Tone_Tone_1Pole_0_Freq_tbl` | Big Muff-style 1-pole tone stack. |
| Cycles | `SPLOOPD 13`, `12`, `9` | Pipelined. |

**CF Verdict**: Boss DS-1. True circuit modeling of the transistor boost stage hitting op-amp hard clipping diodes provides superior high-frequency breakup. Cost: ~20k. Priority: 1.

## 10. DISTPLUS (dspload: 31.79)
| Part | Evidence | Reading |
|---|---|---|
| Clipper | `Distortion_Plus_CLIP_1_MOD_ON_tbl` | Hard clipping tables. |
| Oversampling | `Distortion_Plus_OVS_COE_bn`, `an` | 4x IIR. |
| Tone / EQ | `Distortion_Plus_Gain_Pre_1Pole...` | Input high-pass changes with gain position. |
| Cycles | `SPLOOPD 13`, `12`, `9` | Pipelined. |

**CF Verdict**: MXR Distortion+. A very simple op-amp to germanium ground clipper. Fast to model via a single ADAA table solve. Cost: ~15k. Priority: 2.

## 11. NYC_MUFF (dspload: 34.86)
| Part | Evidence | Reading |
|---|---|---|
| Clipper | (Implicit/inline) | Likely polynomial or inline approximation fuzz. |
| Oversampling | `OVS_UP_COE`, `OVS_DOWN_COE` | Alternate OS implementation (possibly FIR). |
| Tone / EQ | `Muff_Tone_LPF_Mix_tbl`, `HPF` | BMP tone stack blend. |
| Cycles | `SPLOOPD 9`, `7`, `4` | Highly optimized pipelining. |

**CF Verdict**: Big Muff Pi. Complex 4-transistor clipping is tough to solve natively, but CF's component models will sound significantly wider and deeper than static approximations. Cost: ~25k. Priority: 1.

## 12. VIOLETDS (dspload: 34.04)
| Part | Evidence | Reading |
|---|---|---|
| Clipper | `RIOT_RE_Gain_Clip_1_Gain_tbl` | Custom table clipping. |
| Oversampling | `RIOT_RE_OVS_COE_bn`, `an` | 4x IIR. |
| Tone / EQ | `RIOT_RE_Tone_DistPost...` | Deeply characterized pre/post EQ filters. |
| Cycles | `SPLOOPD 13`, `12`, `10` | Pipelined. |

**CF Verdict**: Suhr Riot. Modeling the exact op-amp to LED array clipping gives more authentic amp-like responsiveness. Cost: ~20k. Priority: 2.

## 13. SQUEAK (dspload: 31.37)
| Part | Evidence | Reading |
|---|---|---|
| Clipper | (Implicit/inline) | Generic fuzz/distortion. |
| Oversampling | `Squeak_OVS_COE_bn`, `an` | 4x IIR. |
| Tone / EQ | `Squeak_Filter_Post_1Pole...` | Famous 1-pole LM308 filter. |
| Cycles | `SPLOOPD 13`, `12`, `9` | Pipelined. |

**CF Verdict**: ProCo Rat. A CF model would implement slew-rate limiting of the LM308 and its exact hard clipping matrix, rather than treating it purely as an EQ'd fuzz. Cost: ~20k. Priority: 1.

## 14. ACOSIM (dspload: 31.99)
| Part | Evidence | Reading |
|---|---|---|
| Clipper | None | Clean effect. |
| Oversampling | `_OVS_UP_COE`, `_DOWN_COE` | Alternate OS. |
| Tone / EQ | `_Fx_DRV_AcoSim_toneCoe_tbl` | Frequency band mapping (body/top). |
| Cycles | `SPLOOPD 9`, `7`, `4` | Pipelined. |

**CF Verdict**: Acoustic simulator based mostly on body resonance EQ mapping. Not a target for analog circuit modeling. Priority: 3.

---

## Ranking Table of Improvement Candidates

| Priority | Effect | Why CF is Better | Likely Cost |
|---|---|---|---|
| **1** | **TS_DRIVE** / Green 808 | ADAA + true symmetric clipping completely outclasses Zoom's 4x IIR and `KAWAOD` approximation. | ~17k cycles |
| **1** | **GOLD_DRV** / Centaur | Accurate summation phase and native forward-biased germanium modeling. | ~20k cycles |
| **1** | **ZEN_DRV** | True MOSFET/germanium diode array modeling vs static tables. | ~20k cycles |
| **1** | **SQUEAK** / Rat | Accurate LM308 slew-rate limiting and filter behavior. | ~20k cycles |
| **1** | **NYC_MUFF** | Distinct transistor staging that static approximation severely flattens. | ~25k cycles |
| **1** | **DIST_1** | DS-1 transistor boost into hard diodes translates exceptionally well to CF. | ~20k cycles |
| 2 | SWEETDRV | Native touch-sensitivity rather than artificial envelope followers. | ~20k cycles |
| 2 | TB_MK15 | Real Fuzz Face biasing mechanics. | ~25k cycles |
| 2 | BGTHRTTL | Needs proper triode emulation but is cycle-heavy. | ~45k cycles |
| 2 | DISTPLUS | Very simple MXR circuit; highly faithful in CF. | ~15k cycles |
| 2 | VIOLETDS | Amp-like response from real LED clipping model. | ~20k cycles |
| 3 | RCBOOST | Mostly clean active Baxandall stack; minimal clipping improvement. | ~15k cycles |
| 3 | REDCRUNC | Standard soft clipping; less distinct character. | ~20k cycles |
| 3 | ACOSIM | EQ matching only. | ~10k cycles |

---

## On-Pedal Measurements

To confirm the static findings from the ELFs, the owner should record the pedal at 44.1 kHz (right channel) for the following:

1. **Aliasing Tones**: 
   - Inject a 3.7 kHz sine wave at maximum gain through Zoom's `GOLD_DRV`, `ZEN_DRV`, and `SQUEAK`.
   - Measure the alias energy folded back into the audible spectrum. 
   - This validates the static finding that Zoom heavily reuses the same 4x IIR (`OVS_COE_an/bn`) giving poor alias suppression compared to CF's FIR + ADAA.
2. **Dynamic Sweeps**:
   - Run frequency response sweeps at varying input amplitudes through `SWEETDRV`.
   - The lack of an `SPLOOP` and presence of envelope tables (`Comp_thr_tbl`) implies the EQ shifts dynamically based on input level to fake touch sensitivity. A sweep will reveal this EQ shift.
3. **Phase Relationship**:
   - Pass sweeps through `GOLD_DRV` with drive set to minimum and maximum.
   - Extract the phase response to verify if Zoom's `Centaur_APF_Tbl` correctly mimics the physical Klon phase cancellation.

---
*(End of recon/11_stock_drives.md)*
