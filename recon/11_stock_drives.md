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

> **Second-pass update (Codex):** The [verified-numbers section below](#second-pass-codex-verified-numbers) supersedes the first-pass numerical claims for the six priority effects. It corrects clipper/table interpretations and distinguishes verified filter data from unresolved NYC_MUFF tap ordering. Earlier CF cost and quality verdicts remain unverified projections.

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


## Second pass (Codex): verified numbers

> **Review by Claude (2026-10-06).** Independently re-checked with
> pyelftools + numpy: the 24-byte `OVS_COE_bn` / 20-byte `OVS_COE_an` tables
> are byte-identical in TS_DRIVE, GOLD_DRV, ZEN_DRV, DIST_1 and SQUEAK, and
> with the stored feedback coefficients negated (y = Σb·x − Σa·y form) the
> response gives −3 dB at 0.1194 and −60 dB at 0.2557 of the oversampled
> rate, matching the numbers below. At 4x (176.4 kHz) that is −3 dB at
> ≈21.1 kHz and −60 dB at ≈45.1 kHz. Codex hit its usage cap at the end of
> this run (resets 19:22); the eight remaining drives are not done.


2026-10-06. This section supersedes the numerical and architectural claims in
the first pass above. Priority effects covered: TS_DRIVE, GOLD_DRV, ZEN_DRV,
DIST_1, NYC_MUFF, SQUEAK. **This is an offline static analysis, not a sound
comparison or measured CPU load.** Remaining work is explicitly listed below.

Reproduction and provenance:

- Fresh DATA/PRME blocks came from `backup/2026-10-04/files/<NAME>.ZD2`, group 3.
  Because the brief also prohibited executables other than dis6x, the extraction
  used `build/codex2/decode.ps1`, a PowerShell implementation of the repository's
  tagged-block reader. No zd2/Python executable was run. The installed CLI takes
  `extract FILE --out-dir DIR` and appends the effect name itself; the positional
  output-directory syntax in the brief does not match this checkout.
- All six extracted ELFs hash-identically to the prior extraction. Fresh UTF-8
  `DATA.dis` listings were generated with the specified TI dis6x. `symbols.json`
  records symbol, section, section-relative offset, file offset, size and decoded
  values. ELF addressing used **section.file_offset + symbol.value - section.addr**.
  All tables reported below are little-endian float32. LDW/LDNDW/LDDW loads feed
  MPYSP/ADDSP; doubleword loads here pack two float32 values, not a float64.
  The clipper's SPDP/ABSDP/MPYSPDP operations do not change the table element type.
- Helpers/results are under `build/codex2/`: `decode.ps1`, `measure.ps1`,
  `clippers.ps1`, `cost.ps1`, `report.ps1`, plus per-effect data/listings.
  No pedal connection, firmware execution, commit or effect-source change occurred.

| Effect | Verified OS factor | Filter corners f/fs_OS (-3 / -60 dB) | Clipper asymmetry | Estimated cycles/16-frame block | Confidence |
|---|---:|---|---|---:|---|
| TS_DRIVE | 4x | 0.1194015 / 0.2557143 | One symmetric core, one +0.925/-0.486842 core | ~10.8k | High tables/rate; medium static cost |
| GOLD_DRV | 4x | 0.1194015 / 0.2557143 | Unequal knees and offsets; sloping outer segments | ~15.4k | High tables/rate; medium core/cost |
| ZEN_DRV | 4x | 0.1194015 / 0.2557143 | Two inline polynomial cores; both asymmetric | ~13.4k | High tables/rate; medium core/cost |
| DIST_1 | 4x | 0.1194015 / 0.2557143 | First core +0.1125/-0.675; second symmetric | ~10.9k | High tables/rate/Comp; medium cost |
| NYC_MUFF | 4x | UP table polynomial: 0.0456515 / 0.1516549; complete resampler response unresolved | Inline polynomial; unequal knees/offsets | ~10.2k | High table bytes/rate; low filter chronology; medium cost |
| SQUEAK | 4x | 0.1194015 / 0.2557143 | Static polynomial core symmetric +/-0.8; surrounding bias path exists | ~8.5k | High tables/rate; medium whole-core interpretation/cost |

**Common IIR, verified in five effects.** TS_DRIVE, GOLD_DRV, ZEN_DRV, DIST_1 and
SQUEAK have byte-identical 24-byte `OVS_COE_bn` and 20-byte `OVS_COE_an` tables:

```text
b = [0.00088655448, 0.0037563879, 0.0069437949,
     0.0069437949, 0.0037563879, 0.00088655448]
c = [3.6121943, -5.7276168, 4.8891115, -2.2320604, 0.43519804]
y[n] = sum(b[k]*x[n-k], k=0..5) + sum(c[k-1]*y[n-k], k=1..5)
H(z) = B(z) / (1 - sum(c[k-1]*z^-k, k=1..5))
```

Order 5. The stored feedback signs must be negated when forming a conventional
denominator array `[1, -c...]`. Direct complex-frequency evaluation from the full
decoded float32 values gives |H(0)|=1.000004853; first downward crossings relative
to DC are -3 dB at 0.1194014992 fs and -60 dB at 0.2557142656 fs. At 0.25 fs the
response is -58.16324 dB. At 4x44.1 kHz, these crossings are about 21.06 and 45.11
kHz. These are **single-filter** responses, not a measured alias rejection figure
and not the product of the interpolation and decimation filters.

**Table convention.** Numeric vectors below list all stored values, rounded to
seven significant figures; `symbols.json` retains the full decoded precision.
Ordinary 11-row tables map knob 0,10,...,100, with linear interpolation between
rows. Twelve-row tables add a duplicated endpoint guard at row 11. TS/Gold/Muff
editors explicitly divide/remainder by 10; the TBL_TO_VAL implementations use
101 control positions and 11 rows (e.g. Gold 0x33e4, Squeak 0x1de4). A pair or
four-tuple is **one row**, not consecutive knob positions. Seven-value Comp
tables are parameter blocks, not seven knob positions. All four continuous
PRME parameters use 0..100; TS Boost and DIST_1 Comp use 0..1.

**Shared clipper math.** Let C(v)=min(1,max(-1,v)). For p=(p0,...,p7), define

```text
u = p0*x
(k,m,v) = (p7,p5,p6) if x<0, otherwise (p4,p2,p3)
a = C(k*u); b = C(p1*u); c = C(m*u+v)
F_p(x) = a*c + b*abs(a-1)
```

This is piecewise quadratic, with additional clamp boundaries; it is not a
diode equation. TS and Gold's named KAWAOD routines at 0x0000..0x00bf implement
this directly. Matching inline multiply/clamp/absolute-value sequences also
occur in the other four effects. Predicated instructions selecting positive or
negative parameters are not taken/not-taken control-flow branches.

Parameter vectors below are the **initial coefficient blob values**, with their
zero-based coefficient indices. They are not guaranteed to be the post-editor
values for the PRME default setting. Editors can overwrite gains; tables and
surrounding filters also alter the signal presented to each core. The y(x)
samples describe each core separately, not a full-effect transfer curve.

**Cycle method and limits.** `tools/c6x_cycles.py` does not parse raw dis6x labels:
its label regex expects the name at column zero, while dis6x starts with a hex
address. Feeding it these files directly would miss the DSP blocks. The helper
instead strips addresses/encodings, excludes `.fphead`, counts execute packets
and NOP durations, and keeps parallel instructions in one packet. It counts
SPLOOP pipeline body cycles L and uses S=ceil(L/ii), then the requested estimate
`ii*(N+S-1)`. This rounds partial final stages; SPKERNEL operands are **not** the
number of pipeline stages. At all observed ii>=4, SPLOOPD N=ILC+1, per
[TI's SPLOOP training, slides 9-10](https://e2e.ti.com/cfs-file/__key/communityserver-discussions-components-files/343/2746.sploop_5F00_details.pdf).

The totals also include non-SPLOOP instructions and fixed-count BDEC loops,
including five branch-delay cycles, with nested outer loops multiplied 16 times.
The exact arithmetic and manually traced branch counts are in `cost.txt` and
`cost.ps1`; those inputs are part of the estimate, not a cycle-accurate emulator.
Memory/cache stalls, interrupts, firmware smoothing/service overhead and parameter
edits are excluded. Main-kernel branches examined here are fixed counters;
parameter-editor branches do not imply signal-dependent audio-kernel cost.
The totals must not be converted into measured dspload or a rebuild budget.
### TS_DRIVE

PRME/defaults: Gain 74, Boost 0, Tone 57, VOL 82.
OVS symbols: `.const+0x588` (b), `+0x5a0` (c); file offsets 0x1f48/0x1f60.
The outer loop starts at 0x4b4, with count 16 stored at stack word 102
(0x1a0/0x1ac), and ends at 0x11e0. An explicit first oversampled value is
clipped around 0x724..0x8a0; SPLOOPD 14 at 0xac6 has ILC=2 and handles the
remaining three. Each value goes through two parallel polynomial calculations:
4x, not 3x or 8x. Coefficient pointers at 0x474..0x498 select Coe+160 and
Coe+128, resolving the two parameter blocks below. The earlier recon/05 core
comparison modeled only the asymmetric block and omitted this second core.

Gain's second column starts at **1.111896**, not 1.0. The editor at 0x1568
interpolates the two columns, with Boost doubling the first result at 0x1620.
The first result is written at coefficient offset 120 (Coe[30]); the trim is
sign-flipped and written at offset 200 (Coe[50]). This is not evidence that the
whole effect is simply the recon/05 single-clipper chain.

Decoded knob/parameter tables (.const offsets; rows in knob order):

| Symbol / offset | PRME mapping and units | All values |
|---|---|---|
| `TS_Drive_Tone_tbl` +0x3c8 | Tone; (Hz, shelf gain dB) | (3450, -20); (5400, -20); (6450, -20); (7000, -20); (7500, -20); (7800, -20); (9200, -20); (12400, -20); (14400, -20); (20000, -19.6); (20000, -13); (20000, -13) |
| `TS_Drive_tbl` +0x428 | Gain; (linear drive, linear trim) | (1.332514, 1.111896); (1.515553, 1.099464); (1.740797, 1.062165); (2.046577, 1.024866); (2.554789, 1); (3.114133, 1); (3.85869, 1); (4.724075, 1); (6.259302, 0.963637); (9.456255, 0.78237); (9.891251, 0.809968); (9.891251, 0.809968) |
| `TS_Drive_Level_tbl` +0x530 | VOL; linear output gain | 0.005; 0.170043; 0.869005; 1.56167; 2.090614; 2.783279; 3.387787; 4.017482; 4.571614; 5.14; 5.75; 5.75 |

Clipper parameters and samples (x = -2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2):

```text
Coe[32..39], p = [1, 23.93151, 0, 0.225, 106.3622, 0, -0.225, -106.3622]
y = [-0.225, -0.225, -0.225, -0.225, 0, 0.225, 0.225, 0.225, 0.225]
```

```text
Coe[40..47], p = [1, 1.330363, 0, 0.925, 1.43823, 0, -0.4868421, -2.732636]
y = [-0.4868421, -0.4868421, -0.4868421, -0.4379689, 0, 0.5455958, 0.8520208, 0.925, 0.925]
```

SPLOOP contribution (all audio-kernel SPLOOPs, not string/editor helpers):

| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| 0x00000ac6 | 14 | 3 | 4 | 16 | 1344 |

SPLOOP subtotal: **1344 cycles**. The summary's full estimate additionally counts
setup, non-SPLOOP filters, branch-delay packets and fixed-count outer loops.

### GOLD_DRV

PRME/defaults: Gain 69, Bass 50, Treble 56, VOL 43.
OVS: `.const+0x7a8/0x7c0`, file 0x3e88/0x3ea0.
Outer count 16 is loaded at 0x588; audio loop 0x914..0x1b60. One explicit
clipper evaluation around 0xc00..0xc90 precedes the remaining three in SPLOOPD
10 at 0xf00 (B31=2 at 0xe90): 4x. The runtime coefficient block at +128 supplies
the eight KAWAOD parameters. The clean and drive tables are separate linear
controls, not complementary weights constrained to add to 1.

`CentaGold_TREBLE_Fre` has no `_tbl` suffix but is used as a two-column table
by the Treble editor (0x1bf0), so it is included. DriveGain endpoints are about
14.9 and 52 dB; the numeric table is linear amplitude, not dB. APF values are
dimensionless controls, not a frequency curve. Gain also selects additional
branches in its editor, so the tables alone do not specify the complete clean
blend or EQ response.

Decoded knob/parameter tables (.const offsets; rows in knob order):

| Symbol / offset | PRME mapping and units | All values |
|---|---|---|
| `Centaur_GainTotalEQ_1_tbl` +0x488 | Gain; EQ rows (Hz, gain dB, Q, trim dB); last-column role provisional | (1600, 0, 1.4, 0); (1600, 1, 1.4, 0); (1600, 7, 1, 0); (1600, 5, 2, 0); (1600, 3.5, 0.78, 0); (300, 0, 1.4, -0.7); (300, 3, 1.4, -1); (300, 3, 1.4, -1); (300, 2, 1.4, -2); (300, 3, 1.4, -3); (300, 3, 1.4, -3); (300, 3, 1.4, -3) |
| `CentaGold_TREBLE_Fre` +0x548 | Treble; (Hz, shelf gain dB) | (1400, -10); (1400, -10); (1200, -7.4); (1000, -4.8); (1000, -2.7); (1000, 0); (1000, 2.7); (1267, 5.4); (1667, 9); (2667, 13); (2667, 13); (2667, 13) |
| `CentaGold_OUTPUT_tbl` +0x690 | VOL; linear output gain | 0.002526388; 0.02776515; 0.8147043; 1.470618; 2.030019; 2.60016; 3.228494; 3.810658; 4.528976; 5.296635; 5.308845; 5.308845 |
| `Centaur_APF_Tbl` +0x6c0 | Gain; dimensionless APF control coefficient (not Hz) | 0; 0; 0.549; 0.555; 0.555; 0; 0; 0; 0; 0; 0; 0 |
| `Centaur_CleanAtt_Tbl` +0x6f0 | Gain; linear clean-path attenuation | 1; 1; 0.398107; 0.398107; 0.251189; 0.125893; 0.079433; 0.0631; 0.0631; 0.0631; 0.063096; 0.063096 |
| `Centaur_DriveGain_Tbl` +0x720 | Gain; linear drive-path gain | 5.559043; 5.559043; 15.84893; 25.11886; 31.62278; 50.11872; 63.09573; 79.43282; 177.8279; 316.2278; 398.1072; 398.1072 |
| `Fx_DRV_CentaGold_Bass_Gain_tbl` +0x750 | Bass; EQ gain dB | -17; -13.6; -10.2; -6.8; -3.4; 0; 3.4; 6.8; 10.2; 13.6; 17 |

Clipper parameters and samples (x = -2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2):

```text
Coe[32..39], p = [1, 0.8555437, 0.18, 0.57, 1.185164, 0.18, -0.4384615, -1.540714]
y = [-0.7984616, -0.6184615, -0.5053389, -0.3177206, 0, 0.3327325, 0.5653861, 0.75, 0.93]
```

SPLOOP contribution (all audio-kernel SPLOOPs, not string/editor helpers):

| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| 0x00000f00 | 10 | 3 | 5 | 16 | 1120 |

SPLOOP subtotal: **1120 cycles**. The summary's full estimate additionally counts
setup, non-SPLOOP filters, branch-delay packets and fixed-count outer loops.

### ZEN_DRV

PRME/defaults: Gain 70, Tone 60, Voice 80, VOL 70.
OVS: `.const+0x730/0x748`, file 0x2fb0/0x2fc8.
The core loop 0x9b0..0x1714 runs over 16 input frames; both SPLOOPD 14 at
0xf9c and SPLOOPD 13 at 0x11d4 have ILC=3. The first contains two inline
polynomial calculations (Coe[20..27] and Coe[28..35], direct loads visible at
0xff0..0x1064); the latter also contains filtering. Four values per frame
establish 4x. A lack of a named KAWAOD function does not mean table waveshaping:
the `_Gain_Clip_*` arrays control gains of these arithmetic clippers.

Voice genuinely changes a stored frequency control, 65..3000 Hz; Tone's
separate frequency control is 800..5000 Hz. The first core's stored input gain
is 53.698982, so its knees lie very close to zero in the x convention below.
Its initialized limits are +0.5/-0.2777778. The second has unequal positive/
negative outer slopes (0.17/0.20); equal final +/-1 saturation does not make it
an odd-symmetric transfer function.

Decoded knob/parameter tables (.const offsets; rows in knob order):

| Symbol / offset | PRME mapping and units | All values |
|---|---|---|
| `Z_Drive_Gain_Clip_1_Gain_dB_adjust_tbl` +0x4d8 | Gain; gain/trim dB | -15; -12; -9; -9; -9; -9; -9; -9; -9; -9; -9 |
| `Z_Drive_Gain_Clip_1_Gain_dB_tbl` +0x508 | Gain; gain/trim dB | 5.82838; 31.24456; 38.09192; 40.83825; 42.80626; 43.59932; 44.59711; 45.38784; 45.99459; 46.49892; 46.42337 |
| `Z_Drive_Gain_Clip_2_Gain_dB_tbl` +0x538 | Gain; gain/trim dB | -6; -3; -1.5; 0; 0; 0; 0; 0; 0; 0; 0 |
| `Z_Drive_Gain_DWN_ATT_dB_tbl` +0x568 | Gain; gain/trim dB | 1.2; 0.4; 0; 0; 0; 0; 0; 0; 0; 0; 0 |
| `Z_Drive_Gain_OVS_2Pole_0_Freq_tbl` +0x598 | Gain; frequency Hz | 1000; 1200; 1300; 2000; 2000; 2000; 2000; 2000; 2000; 2000; 2000 |
| `Z_Drive_Gain_OVS_2Pole_1_Q_tbl` +0x5c8 | Gain; Q | 0.2; 0.25; 0.3; 0.35; 0.4; 0.45; 0.5; 0.55; 0.6; 0.65; 0.7 |
| `Z_Drive_Gain_OVS_2Pole_2_Freq_tbl` +0x5f8 | Gain; frequency Hz | 10; 10; 9; 7; 6; 5; 5; 5; 5; 5; 5 |
| `Z_Drive_Gain_OVS_2Pole_2_Gain_tbl` +0x628 | Gain; gain/trim dB | -46; -28; -30.43837; -32.59742; -32.63385; -32.2168; -32.11924; -33.0606; -31.3059; -30.90066; -31.51794 |
| `Z_Drive_Tone_DistPost_0_Freq_tbl` +0x658 | Tone; frequency Hz | 800; 900; 1000; 1300; 1500; 1800; 2000; 2500; 3000; 4000; 5000 |
| `Z_Drive_Voice_OVS_2Pole_3_Freq_tbl` +0x688 | Voice; frequency Hz | 65; 72; 79; 86; 93; 100; 200; 400; 850; 2200; 3000 |
| `Z_Drive_Vol_dB_tbl` +0x6b8 | VOL; gain/trim dB | -120.5233; -26.78551; -18.54645; -14.68203; -12.07536; -10.26369; -8.498895; -6.773502; -4.996703; -3.249064; -2.6 |

Clipper parameters and samples (x = -2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2):

```text
Coe[20..27], p = [53.69898, 1.857676, 0, 0.5, 3.715352, 0, -0.2777778, -6.687634]
y = [-0.2777778, -0.2777778, -0.2777778, -0.2777778, 0, 0.5, 0.5, 0.5, 0.5]
```

```text
Coe[28..35], p = [1, 0.9202949, 0.17, 0.775, 0.9294128, 0.2, -0.775, -0.9294128]
y = [-1, -0.9711385, -0.6529321, -0.3683067, 0, 0.3665641, 0.6459615, 0.9432561, 1]
```

SPLOOP contribution (all audio-kernel SPLOOPs, not string/editor helpers):

| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| 0x00000024 | 6 | 8 | 4 | 1 | 66 |
| 0x000004f4 | 13 | 16 | 2 | 1 | 221 |
| 0x00000f9c | 14 | 4 | 4 | 16 | 1568 |
| 0x000011d4 | 13 | 4 | 4 | 16 | 1456 |

SPLOOP subtotal: **3311 cycles**. The summary's full estimate additionally counts
setup, non-SPLOOP filters, branch-delay packets and fixed-count outer loops.

### DIST_1

PRME/defaults: Gain 61, Tone 41, VOL 100, Comp 0.
OVS: `.const+0x7f0/0x808`, file 0x27d0/0x27e8.
The 16-frame outer loop is 0x394..0xa60. ILC=3 at 0x4ca, 0x616 and 0x72e
gives four values through the clip/filter/clip stages: 4x. Inline clamp and
quadratic math replaces the first pass's unsupported "hard clipping tables."

Comp's editor (0x1968..0x1a54) copies two 28-byte blocks. Both CLIP_1 variants
are byte-identical; CLIP_2 changes its positive/negative ceilings from +/-0.7
to +/-0.925 and reciprocal knee parameters from +/-42.06026 to +/-31.82939.
Thus it changes the second core, not the first core's asymmetry. These are p1..p7;
p0 is the preceding runtime word. The first core's initialized p1 differs from
the copied table by a few float32 ULPs, which is preserved in the artifacts.

Gain's dB table is nonmonotonic (9 at knob 50, 7.2 at 60). The VOL editor
changes several EQ controls, not merely a final scalar level. The Gain editor
at 0x190c passes its table result through the dB-conversion service at offset
144 before storing Coe[24]. Nothing here establishes a physical DS-1 or Big
Muff tone-stack topology.

Decoded knob/parameter tables (.const offsets; rows in knob order):

| Symbol / offset | PRME mapping and units | All values |
|---|---|---|
| `DIST_1_Gain_Dist_Gain_tbl` +0x4a8 | Gain; gain/trim dB | 0; 0.5; 1.5; 2.5; 4; 9; 7.2; 10; 14; 19.5; 22 |
| `DIST_1_Tone_Tone_1Pole_0_Freq_tbl` +0x4d8 | Tone; frequency Hz | 330; 330; 1000; 1000; 1000; 1000; 1000; 1050; 1050; 1050; 1050 |
| `DIST_1_Tone_Tone_1Pole_0_Mix_tbl` +0x508 | Tone; linear mix gain | 0.05; 0.07; 0.19; 0.39; 0.48; 0.7; 0.8; 0.99; 1.1; 1.3; 1.3 |
| `DIST_1_Tone_Tone_1Pole_1_Freq_tbl` +0x538 | Tone; frequency Hz | 320; 330; 320; 316; 316; 310; 310; 308; 290; 260; 260 |
| `DIST_1_Tone_Tone_1Pole_1_Mix_tbl` +0x568 | Tone; linear mix gain | 0.95; 0.9; 0.85; 0.78; 0.7; 0.61; 0.52; 0.45; 0.39; 0.31; 0.3 |
| `DIST_1_VOL_VOL_1Pole_0_Freq_tbl` +0x598 | VOL; frequency Hz | 2000; 1000; 300; 300; 300; 300; 300; 300; 300; 300; 300 |
| `DIST_1_VOL_VOL_1Pole_0_Gain_tbl` +0x5c8 | VOL; gain/trim dB | -32.1; -27; -10.9; -6.9; -4.8; -3.4; -2.5; -1.1; -0.5; -0.2; 0 |
| `DIST_1_VOL_VOL_1Pole_0_trim_tbl` +0x5f8 | VOL; gain/trim dB | -8.7; -8.5; -6.9; -5.5; -4.2; -3.1; -2; -1.8; -1; -0.2; 0 |
| `DIST_1_VOL_VOL_2Pole_0_Freq_tbl` +0x628 | VOL; frequency Hz | 1500; 1500; 450; 450; 450; 450; 450; 450; 450; 450; 450 |
| `DIST_1_VOL_VOL_2Pole_0_Gain_tbl` +0x658 | VOL; gain/trim dB | -3; -3; -4; -1; -1; -1; -0.5; -0.5; -0.2; -0.1; 0 |
| `DIST_1_VOL_VOL_2Pole_0_Q_tbl` +0x688 | VOL; Q | 0.6; 0.6; 1; 1; 1; 1; 1; 1; 1; 1; 1 |
| `DIST_1_VOL_VOL_2Pole_1_Freq_tbl` +0x6b8 | VOL; frequency Hz | 300; 300; 300; 300; 300; 300; 300; 300; 300; 300; 300 |
| `DIST_1_VOL_VOL_2Pole_1_Gain_tbl` +0x6e8 | VOL; gain/trim dB | 10; 10; 5; 1; 0; 0; 0; 0; 0; 0; 0 |
| `DIST_1_VOL_VOL_2Pole_1_Q_tbl` +0x718 | VOL; Q | 0.7; 0.7; 0.7; 0.7; 0.7; 0.7; 0.7; 0.7; 0.7; 0.7; 0.7 |
| `DIST_1_CLIP_1_MOD_ON_tbl` +0x770 | Comp; seven fixed polynomial parameters p1..p7 (not knob samples) | 0.756781; 0; 0.1125; 6.726939; 0; -0.675; -1.121156 |
| `DIST_1_CLIP_1_MOD_off_tbl` +0x790 | Comp; seven fixed polynomial parameters p1..p7 (not knob samples) | 0.756781; 0; 0.1125; 6.726939; 0; -0.675; -1.121156 |
| `DIST_1_CLIP_2_MOD_ON_tbl` +0x7b0 | Comp; seven fixed polynomial parameters p1..p7 (not knob samples) | 29.44218; 0; 0.925; 31.82939; 0; -0.925; -31.82939 |
| `DIST_1_CLIP_2_MOD_off_tbl` +0x7d0 | Comp; seven fixed polynomial parameters p1..p7 (not knob samples) | 29.44218; 0; 0.7; 42.06026; 0; -0.7; -42.06026 |

Clipper parameters and samples (x = -2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2):

```text
Coe[25..32], p = [1, 0.7567806, 0, 0.1125, 6.726939, 0, -0.675, -1.121156]
y = [-0.675, -0.675, -0.5446633, -0.325361, 0, 0.1125, 0.1125, 0.1125, 0.1125]
```

```text
Coe[49..56], p = [1, 29.44218, 0, 0.7, 42.06026, 0, -0.7, -42.06026]
y = [-0.7, -0.7, -0.7, -0.7, 0, 0.7, 0.7, 0.7, 0.7]
```

SPLOOP contribution (all audio-kernel SPLOOPs, not string/editor helpers):

| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| 0x00000028 | 6 | 8 | 4 | 1 | 66 |
| 0x00000108 | 9 | 16 | 4 | 1 | 171 |
| 0x000001d6 | 6 | 16 | 2 | 1 | 102 |
| 0x000004c8 | 9 | 4 | 5 | 16 | 1152 |
| 0x0000064c | 13 | 4 | 4 | 16 | 1456 |
| 0x00000790 | 12 | 4 | 4 | 16 | 1344 |

SPLOOP subtotal: **4291 cycles**. The summary's full estimate additionally counts
setup, non-SPLOOP filters, branch-delay packets and fixed-count outer loops.

### NYC_MUFF

PRME/defaults: SUSTN 70, Tone 55, BAL 100, VOL 58.
There are **no** `*_OVS_COE_bn/an` symbols. UP is `.const+0x570` (64 bytes;
file 0x17d0), DOWN `.const+0x518` (84 bytes; file 0x1778). Both feed float32
multiply/add instructions. SPLOOPD 7 at 0x498 forms four interpolation phases,
ILC=3 (0x420); SPLOOPD 9 at 0x578 evaluates the inline polynomial four times,
ILC=3 (0x558). The outer loop 0x2f0..0xa00 runs 16 times: 4x is verified.

The UP loop uses coefficient indices j,4+j,8+j,12+j for j=0..3, with four
history contributions. Its 16 stored float32 coefficients, interpreted as the
interleaved FIR prototype, give order 15, |DC|=0.87604952, first -3 dB crossing
0.04565149 fs and first -60 dB crossing 0.15165489 fs. The -60 crossing is a
first crossing, not a guarantee that all subsequent sidelobes remain below it.
These polynomial numbers are retained as a **conditional FIR reconstruction**:
the full history-shift/phase chronology still needs an impulse reconstruction.

The DOWN loop at 0x688 accumulates one scalar plus ten coefficient pairs
(ILC=9), i.e. 21 products. Clipper outputs are written with stride five
(0x640), so the stored array cannot safely be assumed chronological FIR taps.
**DOWN order/corners and the complete resampler response remain unresolved.**
Applying freqz to the raw 21-word order and calling it verified would be wrong.
This effect does not justify the first pass's blanket "same 4x IIR" claim.

BAL has no named knob table; its editor is 0xde8. SUSTN changes both pre-level
and post attenuation, and separately computes the clipper input gain at Coe[132]
(0xbc8..0xc28). Therefore the initialized p0=649.052246 below is not a constant
valid at every SUSTN setting. The transfer characterization of the entire
effect also requires those gain edits and surrounding filters; only the inline
static clipping calculation is tabulated here.

Decoded knob/parameter tables (.const offsets; rows in knob order):

| Symbol / offset | PRME mapping and units | All values |
|---|---|---|
| `Muff_Level_Tbl` +0x5b0 | VOL; linear output gain | 0; 0.017733; 0.0896; 0.168; 0.219333; 0.289333; 0.430108; 0.526882; 0.697849; 0.890323; 0.967742; 0.967742 |
| `Muff_Pre_lvl_tbl` +0x5e0 | SUSTN; linear pre-gain | 0.562341; 0.630957; 0.707946; 0.794328; 0.891251; 1; 1.258925; 1.584893; 1.995262; 2.511886; 4.466836; 4.466836 |
| `Muff_Sustain_Dwn_Att_tbl` +0x610 | SUSTN; linear post attenuation | 0.7943282; 0.7585776; 0.724436; 0.691831; 0.6606935; 0.6309574; 0.6309574; 0.6309574; 0.6309574; 0.6309574; 0.6309574; 0.6309574 |
| `Muff_Tone_HPF_Mix_tbl` +0x640 | Tone; linear branch mix gain (can exceed unity) | 0; 0.543988; 0.857263; 1.103487; 1.306694; 1.477373; 1.735552; 1.996876; 2.262329; 2.532558; 2.808; 2.808 |
| `Muff_Tone_LPF_Ftbl` +0x670 | Tone; LPF frequency Hz | 1200; 1363.432; 1403.432; 1443.432; 1483.432; 1523.432; 1563.432; 1603.432; 1643.432; 1683.432; 1723.432; 1723.432 |
| `Muff_Tone_LPF_Mix_tbl` +0x6a0 | Tone; linear branch mix gain (can exceed unity) | 2.584037; 1.999211; 1.727014; 1.483511; 1.261284; 1.056866; 0.92933; 0.795232; 0.654267; 0.506233; 0.351; 0.351 |

Clipper parameters and samples (x = -2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2):

```text
Coe[132..139], p = [649.0522, 1.267354, 0.08, 0.4133333, 2.872632, 0.08, -0.62, -1.915088]
y = [-1, -1, -1, -1, 0, 1, 1, 1, 1]
```

Raw resampler storage (phase ordering caveat above):

`OVS_UP_COE` = [-0.003082752, -0.009674072, -0.02181733, -0.03969836, -0.06173861, -0.08448637, -0.1033863, -0.114141, -0.114141, -0.1033863, -0.08448637, -0.06173861, -0.03969836, -0.02181733, -0.009674072, -0.003082752]

`OVS_DOWN_COE` = [-0.0008193254, 0.006272316, 0.01015115, 0.001641989, -0.0009168386, -0.0009239912, 0.003905654, 0.01080167, 0.003905654, -0.0009239912, -0.0009168386, 0.001641989, 0.01015115, 0.006272316, -0.0008193254, -0.0005506277, 0.0001692772, 0.008616686, 0.008616686, 0.0001692772, -0.0005506277]

SPLOOP contribution (all audio-kernel SPLOOPs, not string/editor helpers):

| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| 0x0000031a | 9 | 6 | 4 | 16 | 1296 |
| 0x00000498 | 7 | 4 | 4 | 16 | 784 |
| 0x00000578 | 9 | 4 | 5 | 16 | 1152 |
| 0x00000688 | 4 | 10 | 3 | 16 | 768 |
| 0x000007d0 | 9 | 7 | 4 | 16 | 1440 |

SPLOOP subtotal: **5440 cycles**. The summary's full estimate additionally counts
setup, non-SPLOOP filters, branch-delay packets and fixed-count outer loops.

### SQUEAK

PRME/defaults: Gain 47, FLTR 60, VOL 79, DryMx 0.
OVS: `.const+0x818/0x830`, file 0x2778/0x2790.
The outer nonlinear loop 0xa1c..0xe60 runs over 16 frames; SPLOOPD 12 at
0xb56 uses ILC=3 (B4=3 at 0xb30): four clipper values per input, hence 4x.
The inline core uses Coe[33..40] and has an odd-symmetric static transfer
with +/-0.8 saturation. Gain-controlled bias/CV processing surrounds it; this
does not establish odd symmetry of the complete effect under dynamic input.

**FLTR is not a swept frequency table:** its 11 frequency entries are all
15000 Hz. The varying table is gain, 0..-29.23 dB, with a small trim
0..-0.59 dB. The filter editor 0x1904..0x1a10 reads all three and constructs
the filter using the frequency and gain arguments; the raw table claim is
stronger evidence than the first pass's "famous LM308 filter" inference.
Gain maps to multiple pre/post EQs, a 2-pole Q of 0.1..1, and bias controls.
No verified slew-rate-limiter equation has been recovered here.

Decoded knob/parameter tables (.const offsets; rows in knob order):

| Symbol / offset | PRME mapping and units | All values |
|---|---|---|
| `Fx_DRV_Squeak_DryMix_tbl` +0x4c0 | DryMx; linear mix gain | 0; 0.1; 0.2; 0.3; 0.4; 0.5; 0.6; 0.7; 0.8; 0.9; 1 |
| `Squeak_Filter_Post_1Pole_0_freq_tbl` +0x4f0 | FLTR; frequency Hz | 15000; 15000; 15000; 15000; 15000; 15000; 15000; 15000; 15000; 15000; 15000 |
| `Squeak_Filter_Post_1Pole_0_gain_tbl` +0x520 | FLTR; gain/trim dB | 0; -0.27; -1.76; -5.12; -9.09; -11.11; -13.01; -18.07; -24.13; -27.57; -29.23 |
| `Squeak_Filter_Post_1Pole_0_trim_tbl` +0x550 | FLTR; gain/trim dB | 0; 0.01; 0; -0.02; -0.05; -0.06; -0.08; -0.17; -0.36; -0.51; -0.59 |
| `Squeak_Level_dB_tbl` +0x580 | VOL; gain/trim dB | -75.42; -52.67; -39.34; -28.42; -24; -20.87; -18.27; -13.29; -6.95; -1.82; 0 |
| `Squeak_gain_Bias_CV_Gain_dB_tbl` +0x5b0 | Gain; gain/trim dB | 12; 13.6; 15.2; 16.8; 18.4; 20; 20; 22; 24.8; 26; 28 |
| `Squeak_gain_Bias_Gain_H_dB_tbl` +0x5e0 | Gain; gain/trim dB | 0; 0; 0; 0; 0; 0; -2.5; -12; -24; -24; -24 |
| `Squeak_gain_Gain_1Pole_0_gain_tbl` +0x610 | Gain; gain/trim dB | 0; -6; -5; -2; 0; 0; 0; 0; 0; 0; 0 |
| `Squeak_gain_Gain_1Pole_1_gain_tbl` +0x640 | Gain; gain/trim dB | 1; 1; 4; 4; 4; 5; 6; 7; 8; 8; 8 |
| `Squeak_gain_Gain_2Pole_0_Q_tbl` +0x670 | Gain; Q | 0.1; 0.1; 0.3; 0.5; 0.6; 0.7; 0.8; 0.95; 1; 1; 1 |
| `Squeak_gain_Gain_2Pole_0_freq_tbl` +0x6a0 | Gain; frequency Hz | 5153.56; 9977.43; 4331.16; 2398.25; 2086.86; 1753.84; 1473.96; 1000; 1000; 1000; 1000 |
| `Squeak_gain_Gain_2Pole_0_gain_tbl` +0x6d0 | Gain; gain/trim dB | 1.07; 11.94; 27.57; 34.83; 39.19; 42.43; 44.89; 50.81; 54.77; 56.2; 56.71 |
| `Squeak_gain_Gain_Dist_Gain_dB_tbl` +0x700 | Gain; gain/trim dB | 0; 9; 11; 8; 7.5; 7.2; 6; 6; 5; 5; 5 |
| `Squeak_gain_Post_1Pole_1_gain_tbl` +0x730 | Gain; gain/trim dB | 2; 2; 2; 2; 2; 2; 2; 2; 1; 0; 0 |
| `Squeak_gain_Post_2Pole_1_gain_tbl` +0x760 | Gain; gain/trim dB | 3; 3; 3; 3; 3; 3; 3; 2.1; 1.2; 1.2; 1.2 |
| `Squeak_gain_Pre_1Pole_0_gain_tbl` +0x790 | Gain; gain/trim dB | 0; 0; -4; -4.5; -4.5; -4.5; -4.5; -4.5; -4.5; -4.5; -4.5 |
| `Squeak_gain_Pre_2Pole_0_gain_tbl` +0x7c0 | Gain; gain/trim dB | 0; 0; 0; 1; 2; 3.5; 3.5; 3.5; 3.5; 3.5; 3.5 |

Clipper parameters and samples (x = -2, -1, -0.5, -0.25, 0, 0.25, 0.5, 1, 2):

```text
Coe[33..40], p = [1, 1.581139, 0, 0.8, 1.976424, 0, -0.8, -1.976424]
y = [-0.8, -0.8, -0.7998888, -0.5952569, 0, 0.5952569, 0.7998888, 0.8, 0.8]
```

SPLOOP contribution (all audio-kernel SPLOOPs, not string/editor helpers):

| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| 0x00000026 | 6 | 8 | 4 | 1 | 66 |
| 0x000004d4 | 9 | 16 | 4 | 1 | 171 |
| 0x000005ec | 13 | 16 | 4 | 1 | 247 |
| 0x0000072e | 9 | 16 | 4 | 1 | 171 |
| 0x0000080e | 13 | 16 | 2 | 1 | 221 |
| 0x00000b56 | 12 | 4 | 4 | 16 | 1344 |
| 0x00000ed4 | 9 | 16 | 6 | 1 | 189 |

SPLOOP subtotal: **2409 cycles**. The summary's full estimate additionally counts
setup, non-SPLOOP filters, branch-delay packets and fixed-count outer loops.

### Corrections to the first pass and remaining work

- The first pass's rebuild costs and sound-quality verdicts are projections,
  not binary-derived facts. The numbers above estimate the **stock kernels**.
  dspload is bookkeeping, not measured cycles; no CF cost is established here.
- "No SPLOOP means envelope-follower branching" is not valid. A loop may be
  unrolled or use BDEC; signal-dependent predication is not a conditional branch.
  TS's SPLOOPW 6 belongs to GetString_ON_OFF, not its audio kernel.
- Same coefficient bytes are verified for five priority effects, not all drives.
  NYC_MUFF uses a distinct four-phase multiply/accumulate resampler.
- ZEN_DRV and DIST_1 have arithmetic polynomial clippers. Their knob and Comp
  tables are not waveform lookup tables. TS Drive has two cores, so recon/05's
  single-core THD/aliasing numbers must not be described as whole-effect results.
- Equal ultimate ceilings need not imply symmetry (ZEN core 2), and a sloping
  outer segment is not a fixed plateau (Gold). The numeric static core in Squeak
  is symmetric, but its complete bias-dependent signal path has not been modeled.
- The Squeak FLTR mapping is a fixed 15 kHz frequency control with varying gain,
  not the asserted frequency sweep. Table names do not prove physical component
  identities, exact pedal circuits, slew rate, or audible superiority.

**Unfinished:** NYC_MUFF's complete resampler impulse response/tap chronology and
verified DOWN corners; full post-editor parameter equations and whole-effect
transfer chains (especially Gold's extra Gain branches and Squeak bias dynamics).
Knob-table bytes are fully decoded for all six priority effects, but the last
column of Gold GainTotalEQ remains a provisional semantic interpretation.
The other eight effects (SWEETDRV, TB_MK15, RCBOOST, REDCRUNC, BGTHRTTL,
DISTPLUS, VIOLETDS, ACOSIM), including ToneBender's `_TR` transfer function,
have not received a numeric second pass in this run. No on-pedal measurements
were attempted or implied.
