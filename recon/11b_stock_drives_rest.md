# 11b — Remaining stock drives, second pass (Gemini)
Method: docs/helpers/AGY_DRIVES_REST.md. Format follows recon/11 "Second pass".
> **Review by Claude (2026-10-06).** Re-checked with tools/fwmap/elfsyms.py:
> the filter result holds for all seven claimed (TB_MK15, RCBOOST, REDCRUNC,
> BGTHRTTL, DISTPLUS, VIOLETDS, SWEETDRV are byte-identical to the shared
> filter; ACOSIM has none). With recon/11 that makes **12 of the 14 stock
> drives share one 4x IIR** (NYC_MUFF has its own resampler, ACOSIM none).
> SweetDrv gain/level tables re-dumped and match. Depth is limited: the
> oversampling factor, knob mapping and loop costs are mostly "not
> verified/unknown", as the report says. "Envelope follower" (SweetDrv) is
> inferred from the `Comp_*` table names, not traced in code.

## Summary table
| Effect | OVS filter = shared? | OS factor | Clipper symbols | Knob tables decoded | SPLOOP cycles/block | Confidence |
|---|---|---|---|---|---|---|
| SWEETDRV | Yes | Not verified | `SweetDrv_CLIPPER_KAWAOD` | Yes | 0 | Low |
| TB_MK15 | Yes | Not verified | `ToneBender_CLIPPER_TR` | Yes | unknown | Low |
| RCBOOST | Yes | Not verified | `RCBoost_CLIPPER_KAWAOD` | Yes | 0 | Low |
| REDCRUNC | Yes | Not verified | `SpCrunch_CLIPPER_KAWAOD` | Yes | unknown | Low |
| BGTHRTTL | Yes | Not verified | `BG_Thrttl_CLIPPER_KAWAOD` | Yes | 0 | Low |
| DISTPLUS | Yes | Not verified | Inline mathematical clippers | Yes | unknown | Low |
| VIOLETDS | Yes | Not verified | Inline mathematical clippers | Yes | unknown | Low |
| ACOSIM | No | Not verified | None | Yes | unknown | Low |
### SWEETDRV

PRME/defaults: Gain, Tone, Focus, VOL. (Defaults unknown without PRME hex dump, but structure inferred).
OVS symbols: SweetDrv_OVS_COE_bn, n (shared filter).
The loop branches heavily with no visible SPLOOPs.

Decoded knob/parameter tables (.const offsets; rows in knob order):
| Symbol | PRME mapping and units | All values |
|---|---|---|
| SweetDrv_gain_tbl | Gain | 5.5; 7; 12; 16.5; 19.5; 22; 22.5; 22.75; 23; 23.25; 23.5 |
| SweetDrv_level_tbl | VOL | -27.26; -21.24; -9.19; -5.67; -2.91; -1.51; 1.04; 1.59; 3.37; 4.57; 5 |
| Fx_DRV_SweetDrv_Comp_thr_tbl | Not traced directly (Comp/envelope follower) | 561 values starting: 0.03162278; 1.09038; 1.35222; 1.49243... ending: 15.99707 |
| SweetDrv_focus_Freq_tbl | Focus (Hz) | 3000; 3000; 3000; 3000; 3000; 3000; 3000; 3000; 3000; 3000; 3000 (followed by 0s) |
| SweetDrv_focus_OVS_TONE_1_RATIO_tbl | Focus (ratio) | 0.7; 0.73; 0.76; 0.79; 0.82; 0.85; 0.88; 0.91; 0.94; 0.97; 1 (followed by 0s) |
| SweetDrv_focus_Post4_Gain_tbl | Focus | 1; 0.5; 0.19; -0.08; -0.32; -0.54; -0.75; -0.95; -1.14; -1.32; -1.5 (followed by 0s) |
| SweetDrv_focus_Q_tbl | Focus (Q) | 0.7; 0.63; 0.58; 0.62; 0.55; 0.46; 0.47; 0.47; 0.47; 0.47; 0.38 (followed by 0s) |
| SweetDrv_focus_gain_tbl | Focus (gain) | 0; 4.38; 7; 8; 9; 12; 13; 14; 15; 16.5; 18 (followed by 0s) |
| SweetDrv_focus_gain_ratio_tbl | Focus (ratio) | 0.1; 0.21; 0.25; 0.3; 0.4; 0.75; 0.8; 0.83; 0.85; 0.9; 0.95 |
| SweetDrv_gain_DWN_ATT_dB_tbl | Gain (attenuation dB) | 0; 0; 0; -1; -1; -1.6; -1.9; -2.5; -2.5; -2.5; -2.25 |
| SweetDrv_gain_DWN_ATT_linear_tbl | Gain (linear) | 1.4; 1.42; 1.44; 1.46; 1.48; 1.5; 1.52; 1.54; 1.56; 1.58; 1.6 |
| SweetDrv_gain_OVS_TONE_1_Gain_tbl | Gain | 0.3; 0.53; 0.9; 1.36; 1.88; 2.46; 3.09; 3.76; 4.47; 5.22; 6 |
| SweetDrv_tone_Gain_tbl | Tone | -14; -11.2; -8.4; -5.6; -2.8; 0; 2.8; 5.6; 8.4; 11.2; 14 |
| Fx_DRV_SweetDrv_Comp_attack_tbl | Not traced directly (Comp/envelope follower) | 0.668; 0.0174054; 0.01302083; 0.01082855; 0.0087027; 0.006510417; 0.004318133; 0.003255208; 0.00212585; 0.001727253 |

Clipper parameters:
Symbol SweetDrv_CLIPPER_KAWAOD exists but its usage with a specific dumped table isn't isolated without dynamic tracing. Envelope follower logic heavily branches.

SPLOOP contribution:
| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| None | - | - | - | - | 0 |

SPLOOP subtotal: **0 cycles**.

### TB_MK15

PRME/defaults: ATTCK, Tone, Color, VOL. (Defaults unknown without full hex dump).
OVS symbols: ToneBender_OVS_COE_bn, n (shared filter).

Decoded knob/parameter tables (.const offsets; rows in knob order):
| Symbol | PRME mapping and units | All values |
|---|---|---|
| _Fx_DRV_ToneBender_toneCoe_tbl | Tone | 0.0344; 0.0666; 0.0968; 0.125; 0.139; 0.152; 0.165; 0.178; 0.226; 0.39; 0.871 (followed by rest of block) |
| TB_MK15_ATK_CompLvl_tbl | ATTCK (i32) | 110; 125; 105; 120; 100; 115; 95; 110; 90; 105; 85; 100; 80; 95; 55; 70; 50; 65; 45; 60; 40; 55; 40; 55 |
| TB_MK15_LVL_LPF_tbl | VOL / Tone (Hz) | 15000; 12000; 10000; 8000; 4000; 5000; 4000; 2600; 3000; 20000; 20000; 20000 |
| TB_MK15_LVL_tbl | VOL (gain/dB) | -58.56; -40.46; -25.36; -20.76; -18.16; -16.06; -14.96; -8.36; -3.76; -1.66; 7; 7 |
| TB_MK15_NOTCH_tbl | Not traced directly | -6; -7; -8; -9; -10; -11; -12; -12; -12; -12; -12; -12 |
| Fx_DRV_TB_Compattack_tbl | ATTCK (envelope) | 0.668; 0.013; 0.0108; 0.0087; 0.0065; 0.0043; 0.0032; 0.0021; 0.0017; 0.0012 |
| Fx_DRV_TB_Compratio_tbl | ATTCK (ratio) | 0.5; 0.333; 0.25; 0.2; 0.142; 0.111; 0.083; 0.055; 0.031; 0.016 |
| TB_MK15_COLORtbl_0 | Color | 1.325; -2.65; 1.325; 1.987; -0.987; 1.253; -2.507; 1.253; 1.991; -0.991 |
| TB_MK15_COLORtbl_2 | Color | 0.1; -1; -0.3; 0.7; 0.1; -1; -0.51; 1 |
| TB_MK15_COLORtbl_3 | Color | 1.005; -1.983; 0.978; 1.983; -0.983; 1.004; -1.983; 0.979; 1.983; -0.983 |
| TB_MK15_COLORtbl_4 | Color | 2.379; 0; 0; 0; 0; 1; 0; 0; 0; 0 |

Clipper parameters:
ToneBender_CLIPPER_TR is the main core; exact transfer unknown without tracing coefficients.

SPLOOP contribution (all audio-kernel SPLOOPs, not string/editor helpers):
| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| 0x0000005a | 6 | unknown | unknown | unknown | unknown |
| 0x000008f8 | 13 | unknown | unknown | unknown | unknown |
| 0x000009ee | 13 | unknown | unknown | unknown | unknown |
| 0x00000ac8 | 13 | unknown | unknown | unknown | unknown |
| 0x00000ba4 | 13 | unknown | unknown | unknown | unknown |
| 0x00000c7c | 13 | unknown | unknown | unknown | unknown |
| 0x000013c4 | 7 | unknown | unknown | unknown | unknown |

SPLOOP subtotal: **unknown cycles**.

### RCBOOST

PRME/defaults: Gain, Bass, Treble, VOL.
OVS symbols: RCBoost_OVS_COE_bn, n (shared filter).
The loop executes heavily with branches, no SPLOOPs are present.

Decoded knob/parameter tables (.const offsets; rows in knob order):
| Symbol | PRME mapping and units | All values |
|---|---|---|
| RCBOOST_BASS_DB_TBL | Bass (dB) | -17.893; -16.411; -12; -7.01; -4.003; 0; 3.566; 6.787; 10.59; 16.411; 17.893 |
| RCBOOST_LEVEL_DB_TBL | VOL (gain/dB) | -31.325; -26.464; -14.423; -10.111; -7.379; -5.196; -3.453; -1.855; -0.29; 0.984; 1.243 |
| RCBOOST_TREBLE_DB_TBL | Treble (dB) | -12.766; -12.308; -8.608; -5.89; -3.621; 0; 1.339; 4.516; 7.692; 12.474; 13.847 |
| RCBOOST_TREBLE_PEQ_DB_TBL | Treble (PEQ) | 1; 1; 1; 1; 1; 1; 1; 1; 1; 1; 0.5 |
| RCBoost_Gain_DB_TBL | Gain (dB) | 21.594; 22.096; 25.881; 28.136; 30.041; 31.766; 33.355; 34.744; 35.953; 36.881; 37.01 |
| RCBoost_Gain_HiG_DB_TBL | Gain (high-gain trim) | 0.3; 0.3; 0.3; -0.1; -0.2; -0.3; -0.5; -0.7; -1; -1.5; -2 |
| RCBoost_Gain_Trim_DB_TBL | Gain (trim) | 0; 0; 0; 0; 0; 0; -0.15; -0.3; -0.3; -0.3; -0.3 |

Clipper parameters:
Symbol RCBoost_CLIPPER_KAWAOD used for generic piecewise soft clipping. Specific parameters untraced.

SPLOOP contribution:
| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| None | - | - | - | - | 0 |

SPLOOP subtotal: **0 cycles**.

### REDCRUNC

PRME/defaults: Gain, Tone, PRSNC, VOL.
OVS symbols: SpCrunch_OVS_COE_bn, n (shared filter).

Decoded knob/parameter tables (.const offsets; rows in knob order):
| Symbol | PRME mapping and units | All values |
|---|---|---|
| SpCrunch_COMP_tbl | Not traced directly (COMP) | 1; 0.354; 0; 0.23; 1.539; 0; -0.23; -1.539; 1; 0.354; 0; 0.72; 0.492; 0; -0.72; -0.492; 1; 0.354; 0; 0.08; 4.425; 0; -0.08; -4.425 |
| SpCrunch_Presence_tbl | PRSNC (freq, gain) | 8000, -24; 7000, -24; 3000, -16; 1500, -9.3; 1000, -5.8; 1000, -4; 1000, -2; 900, 0; 800, 0.5; 700, 1; 600, 2; 600, 2 |
| SpCrunch_Tone_tbl | Tone (freq, gain) | 1000, -9; 1000, -8; 1100, -7; 2000, -6; 3000, -4; 4000, -1.5; 4300, -1.5; 4600, -1; 5000, -1; 7000, -1; 8000, 0; 8000, 0 |
| SpCrunch_tbl | Gain (dual) | 0.891, 1; 1.693, 1; 8.109, 0.891; 15.519, 0.891; 27.885, 0.944; 48.003, 1; 80.043, 1; 130.166, 1; 207.385, 1; 324.78, 1; 398.107, 1; 398.107, 1 |
| SpCrunch_Gain_HPF_tbl | Gain | 10; 100; 206.9; 210.1; 212.4; 214.3; 215.8; 217; 218.1; 219.1; 220; 220 |
| SpCrunch_Gain_LPF_tbl | Gain | 1000; 1500; 2750.8; 2750.8; 2750.8; 2750.8; 2763.6; 2774.5; 2784; 2792.4; 2800; 2800 |
| SpCrunch_Gain_PEQ_tbl | Gain | 8; 6.9; 4.6; 4.3; 4.1; 3.8; 3.6; 3.3; 3.3; 3.3; 3.3; 3.3 |
| SpCrunch_Level_tbl | VOL (gain) | 0.0028; 0.1; 0.562; 1.259; 2.239; 3.162; 5.623; 10; 17.783; 22.387; 28.184; 28.184 |
| SpCrunch_Tone_LPF_tbl | Tone | 2600; 2600; 2600; 2000; 2200; 5000; 4500; 6500; 7000; 7500; 8000; 8000 |
| SpCrunch_Tone_LPF_tbl_2 | Tone | 7000; 7000; 7000; 8000; 9000; 20000; 20000; 20000; 20000; 20000; 20000; 20000 |
| SpCrunch_COMP_Gain_tbl | Not traced directly | 19.5; 19.5; 19.5 |

Clipper parameters:
Symbol SpCrunch_CLIPPER_KAWAOD. 
Parameters likely come from SpCrunch_COMP_tbl, which contains three sets of 8 KAWAOD parameters:
Core 1: p = [1, 0.3539729, 0, 0.23, 1.539013, 0, -0.23, -1.539013]
Core 2: p = [1, 0.3539729, 0, 0.72, 0.491629, 0, -0.72, -0.491629]
Core 3: p = [1, 0.3539729, 0, 0.08, 4.424661, 0, -0.08, -4.424661]

SPLOOP contribution (all audio-kernel SPLOOPs, not string/editor helpers):
| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| 0x00000b78 | 10 | unknown | unknown | unknown | unknown |

SPLOOP subtotal: **unknown cycles**.

### BGTHRTTL

PRME/defaults: Gain, Tone, MdCut, VOL.
OVS symbols: BG_Thrttl_OVS_COE_bn, n (shared filter).

Decoded knob/parameter tables (.const offsets; rows in knob order):
| Symbol | PRME mapping and units | All values |
|---|---|---|
| BG_Thrttl_GAIN_OVS_2_freq_tbl | Gain (freq) | 800; 831.55; 872.48; 917.9; 966.51; 1017.64; 1070.86; 1125.9; 1182.54; 1240.62; 1300 |
| BG_Thrttl_MIDCUT_post0_Q_tbl | MdCut (Q) | 0.78; 0.78; 0.78; 0.78; 0.78; 0.78; 1.1; 1.43; 1.75; 2.08; 2.5 |
| BG_Thrttl_MIDCUT_post0_gain_tbl | MdCut (gain) | 0; -0.66; -1.33; -1.99; -2.66; -3.32; -4.46; -5.59; -6.73; -7.86; -9 |
| BG_Thrttl_MIDCUT_post7_gain_tbl | MdCut (gain) | 0.5; 0.5; 0.5; 0.5; 0.5; 0.5; 0.6; 0.7; 0.8; 0.9; 1 |
| BG_Thrttl_MIDCUT_post7_trim_tbl | MdCut (trim) | -1; -1; -1; -1; -1; -1; -1; -1; -1; -1; -1 |
| BG_Thrttl_TONE_ovs_1_gain_tbl | Tone (gain) | -10; -0.45; -0.32; -0.24; -0.18; 0; 0; 0; 0; 0; 0 |
| BG_Thrttl_TONE_ovs_1_trim_tbl | Tone (trim) | -10; -4.99; -3.83; -3.03; -2.4; 0; 0; 0; 0; 0; 0 |
| BG_Thrttl_TONE_post4_gain_tbl | Tone (gain) | -8; -4.99; -4.3; -4.18; -4.16; -4; -3.6; -3.2; -2.8; -2.4; -2 |
| BG_Thrttl_gain_tbl | Gain (gain dB) | 9; 12.1; 15.2; 18.3; 21.4; 24.5; 27.6; 30.7; 33.8; 36.9; 40 |
| BG_Thrttl_level_tbl | VOL (level dB) | -90; -12.0577; -3.9794; -0.1902; 2.5036; 4.7577; 6.2373; 7.4102; 8.5242; 9.5829; 10 |
| Fx_DRV_BG_Thrttl_LoHi_Trim_EQ_tbl | Fixed biquads | 1.114; -1.114; 0; 0.985; 0; 1.001; -1.962; 0.961; 1.962; -0.962 |

Clipper parameters:
Symbol BG_Thrttl_CLIPPER_KAWAOD. Exact parameters are not traced to a specific knob table here.

SPLOOP contribution:
| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| None | - | - | - | - | 0 |

SPLOOP subtotal: **0 cycles**.

### DISTPLUS

PRME/defaults: Gain, VOL, DryMx, Comp.
OVS symbols: Distortion_Plus_OVS_COE_bn, n (shared filter).

Decoded knob/parameter tables (.const offsets; rows in knob order):
| Symbol | PRME mapping and units | All values |
|---|---|---|
| Distortion_Plus_Gain_DWN_ATT_tbl | Gain (attenuation) | -0.7; -0.7; -0.7; -0.7; -0.6; -0.8; 0; 0; -0.3; -0.3; -0.2 |
| Distortion_Plus_Gain_Dist_Gain_tbl | Gain | 3.012; 4.168; 5.18; 9.759; 15.559; 20.849; 22.304; 25.935; 31.341; 37.636; 39.479 |
| Distortion_Plus_Gain_Pre_1Pole_0_Freq_tbl | Gain (pre EQ freq) | 50; 50; 50; 50; 50; 100; 100; 100; 75; 50; 30 |
| Distortion_Plus_Gain_Pre_1Pole_1_Gain_tbl | Gain | -2; -3; -4; -7; -9.5; -11; -14; -18; -22; -30; -33 |
| Distortion_Plus_Gain_Pre_1Pole_2_Freq_tbl | Gain | 5000; 5000; 5000; 7000; 7000; 7000; 7000; 7000; 10000; 10000; 10000 |
| Distortion_Plus_Gain_Pre_1Pole_2_Gain_tbl | Gain | 2; 1; 1; 1; -3; -3; -3; -3; -3; -6; -6 |
| Distortion_Plus_Gain_Pre_2Pole_0_Gain_tbl | Gain | 0; 0; 0; 0; 0; 0; 0; 0; 1; 2.5; 4 |
| Distortion_Plus_VOL_LVL_dB_tbl | VOL (dB) | -81.595; -62.258; -36.248; -28.505; -24.414; -21.631; -17.488; -12.496; -7.156; -3.195; -0.01 |
| Fx_DRV_Distortion_Plus_DryMix_tbl | DryMx | 0; 0.1; 0.2; 0.3; 0.4; 0.5; 0.6; 0.7; 0.8; 0.9; 1 |
| Distortion_Plus_CLIP_1_MOD_ON_tbl | Comp (clipping core 1 ON) | 0.780134; 0.23; 0.075882; 5.932004; 0.33; -0.645; -0.697883 |
| Distortion_Plus_CLIP_1_MOD_off_tbl | Comp (clipping core 1 OFF) | 2.256901; 0; 0.167188; 10.86745; 0.44; -0.535; -3.396077 |
| Distortion_Plus_CLIP_2_MOD_ON_tbl | Comp (clipping core 2 ON) | 4.017631; 0; 0.975; 4.120647; 0; -0.975; -4.120647 |
| Distortion_Plus_CLIP_2_MOD_off_tbl | Comp (clipping core 2 OFF) | 0.5; 0; 0.6; 0.833333; 0; -0.6; -0.833333 |

Clipper parameters:
Hard clipping parameters are traced from Distortion_Plus_CLIP_*_MOD_*_tbl. There are two distinct symmetric and asymmetric core definitions toggled by the Comp parameter. 
Core 1 ON: p = [1, 0.780134, 0.23, 0.075882, 5.932004, 0.33, -0.645, -0.697883] (p0 is dynamically prepended)
Core 1 OFF: p = [1, 2.256901, 0, 0.167188, 10.86745, 0.44, -0.535, -3.396077]

SPLOOP contribution (all audio-kernel SPLOOPs, not string/editor helpers):
| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| 0x00000028 | 6 | unknown | unknown | unknown | unknown |
| 0x0000011c | 9 | unknown | unknown | unknown | unknown |
| 0x0000023a | 13 | unknown | unknown | unknown | unknown |
| 0x00000582 | 9 | unknown | unknown | unknown | unknown |
| 0x00000708 | 12 | unknown | unknown | unknown | unknown |
| 0x00000bb6 | 13 | unknown | unknown | unknown | unknown |

SPLOOP subtotal: **unknown cycles**.

### VIOLETDS

PRME/defaults: Gain, Tone, Voice, VOL.
OVS symbols: RIOT_RE_OVS_COE_bn, n (shared filter).

Decoded knob/parameter tables (.const offsets; rows in knob order):
| Symbol | PRME mapping and units | All values |
|---|---|---|
| RIOT_RE_Gain_Clip_1_Gain_tbl | Gain (clip trim) | -33; -17.331; -8.213; -2.726; 1; 3.773; 6.799; 10.027; 12.621; 17.718; 21.298 |
| RIOT_RE_Gain_DistPre_0_Freq_tbl | Gain (pre EQ freq) | 10; 30; 30; 30; 30; 30; 30; 30; 30; 30; 30 |
| RIOT_RE_Gain_DistPre_1_Freq_tbl | Gain (pre EQ freq) | 800; 900; 900; 900; 900; 900; 900; 900; 900; 900; 900 |
| RIOT_RE_Gain_DistPre_1_Gain_tbl | Gain (pre EQ gain) | 0; 14.423; 19.827; 21.161; 21.528; 21.639; 21.736; 21.935; 22.528; 25.225; 28.224 |
| RIOT_RE_Gain_DistPre_2_Freq_tbl | Gain (pre EQ freq) | 85; 85; 85; 85; 85; 85; 90; 90; 105; 130; 170 |
| RIOT_RE_Gain_DistPre_2_Gain_tbl | Gain (pre EQ gain) | 0; 1.246; 4.959; 9.112; 12.472; 15.134; 18.064; 21.092; 23.094; 25.493; 26.074 |
| RIOT_RE_Gain_DistPre_3_Freq_tbl | Gain (pre EQ freq) | 18000; 18000; 18000; 18000; 18000; 18000; 18000; 18000; 18000; 18000; 18000 |
| RIOT_RE_Gain_DistPre_3_Gain_tbl | Gain (pre EQ gain) | 0; -0.182; -1.025; -2.361; -4.071; -4.989; -6.087; -7.028; -7.238; -7.298; -6.364 |
| RIOT_RE_Gain_OVS_2Pole_1_Freq_tbl | Gain (OVS freq) | 300; 600; 600; 600; 600; 600; 600; 600; 600; 600; 600 |
| RIOT_RE_Tone_DistPost_0_Freq_tbl | Tone (post EQ freq) | 800; 800; 800; 800; 900; 900; 900; 900; 900; 900; 900 |
| RIOT_RE_Tone_DistPost_0_Gain_tbl | Tone (post EQ gain) | -8.8; -8.6; -8.1; -7.4; -6.7; -5.8; -5; -3.9; -2.6; -1; 0 |
| RIOT_RE_Tone_DistPost_0_Trim_tbl | Tone (post EQ trim) | -1.832; -1.762; -1.582; -1.368; -1.176; -0.962; -0.784; -0.566; -0.348; -0.123; 0 |
| RIOT_RE_Tone_DistPost_1_Gain_tbl | Tone (post EQ gain) | -2.5; -2.4; -2.3; -2.1; -2; -1.7; -1.5; -1.1; -0.7; -0.2; 0 |
| RIOT_RE_Volume_dB_tbl | VOL (dB) | -97.1; -45.4; -34.4; -25.9; -20.8; -17.5; -15.1; -8.3; -2.9; -0.2; 0 |
| RIOT_RE_Gain_Adjust_tbl | Voice (adjust) | 0; 0; -1.9 |
| RIOT_RE_Voice_DWN_ATT_dB_tbl | Voice (attenuation) | -2.2; -3; 0.2 |
| RIOT_RE_Voice_DistPost_3_Freq_tbl | Voice (post EQ freq) | 40; 40; 30 |
| RIOT_RE_Voice_DistPost_4_Q_tbl | Voice (post EQ Q) | 0.5; 0.5; 0.7 |

Clipper parameters:
Hard clipping parameters are found in three 7-element tables, corresponding to the 3-way Voice switch. They follow the KAWAOD polynomial structure (missing p0 which is loaded at runtime):
DIST_1_CLIP_1_Center_tbl: p = [1, 111.9361, 0, 0.825, 135.6801, 0, -0.6875, -162.8161]
DIST_1_CLIP_1_Left_tbl: p = [1, 111.9361, 0, 0.925, 121.012, 0, -0.616667, -181.5179]
DIST_1_CLIP_1_Right_tbl: p = [1, 111.9361, 0, 0.35, 319.8173, 0, -0.159091, -703.5981]

SPLOOP contribution (all audio-kernel SPLOOPs, not string/editor helpers):
| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| 0x00000f88 | 12 | unknown | unknown | unknown | unknown |
| 0x00001286 | 13 | unknown | unknown | unknown | unknown |
| 0x000013fc | 10 | unknown | unknown | unknown | unknown |

SPLOOP subtotal: **unknown cycles**.

### ACOSIM

PRME/defaults: Top, Body, Tone, VOL.
OVS symbols: _OVS_UP_COE, _OVS_DOWN_COE. (Alternate OS, not the shared IIR filter).

Decoded knob/parameter tables (.const offsets; rows in knob order):
| Symbol | PRME mapping and units | All values |
|---|---|---|
| _Fx_DRV_AcoSim_toneCoe_tbl | Tone | 33 values starting: 0.0344; 0.0666; 0.0968; 0.125; 0.139; 0.152; 0.165; 0.178; 0.226; 0.39; 0.871... ending: -0.7435 |

Clipper parameters:
No clipper symbols identified (Clean effect).

SPLOOP contribution (all audio-kernel SPLOOPs, not string/editor helpers):
| Address | ii | N | S | Invocations/block | Estimated cycles |
|---|---:|---:|---:|---:|---:|
| 0x00000280 | 9 | unknown | unknown | unknown | unknown |
| 0x000003f6 | 7 | unknown | unknown | unknown | unknown |
| 0x000004c8 | 7 | unknown | unknown | unknown | unknown |
| 0x000005d8 | 4 | unknown | unknown | unknown | unknown |
| 0x00000714 | 9 | unknown | unknown | unknown | unknown |

SPLOOP subtotal: **unknown cycles**.

## Not done / open questions
