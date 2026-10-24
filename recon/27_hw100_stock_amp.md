# Recon 27: Zoom's stock HW100 (Hiwatt Custom 100) — architecture and decoded tables

Date: 2026-10-24. Extracted and disassembled `build/bench/stock/HW100_1U.ZD2` (the same
extracted-stock-effect convention as `recon/11_stock_drives.md`, but AMP group, never
previously analysed — recon/11 only covers the 14 DRIVE-group effects). Method: `zd2 extract`
-> `DATA.elf` -> `dis6x.exe` (same toolchain and the ELF's symbol table survives, same as
recon/11 found for the drives). Goal: is Zoom's HW100 built the same way CF Watt is (a real
circuit model of the physical Hiwatt DR103/Custom 100), or an approximation — and if so, what
kind.

## 1. Top-level structure (confirmed — symbol names read directly from the disassembly)

```
HW100_EQ_Calc                          entry 0x0 — the core EQ/coefficient-build routine
Fx_AMP_HW100_output_edit               0x2e4c
Fx_AMP_HW100_onf                       0x2f10  (on/off)
Fx_AMP_HW100_AdjustPre_edit            0x2f68
Fx_AMP_HW100_Input_edit                0x3100  (Normal/Brill input select)
Fx_AMP_HW100_Gain_edit                 0x33e4
Fx_AMP_HW100_Presence_edit             0x3584
Fx_AMP_HW100_ToneStack_3_edit          0x37b4  (calls HW100_EQ_Calc; "_3" = 3-band)
Fx_AMP_HW100_Knob_edit                 0x3938  (dispatches Bass/MID/Treble/PRSNC/Gain/VOL)
Fx_AMP_HW100_init                      0x3a64
HW100_CLIPPER_Dynamic                  0x3b40  (the preamp nonlinearity)
Fx_AMP_HW100                           0x3b68  (per-sample process entry)
```
Knob set (from `PRME`, matches `zd2 inspect`): Input (Normal/Brill), Bass, MID, Treble, PRSNC,
Gain, VOL — same seven the Zoom manual lists for HW100 (`docs page 11`: "Input, Bass, MID,
Treble, PRSNC, Gain, VOL").

## 2. Decoded tables (confirmed — read directly from `.rodata`, not inferred)

All `_tbl` symbols kept their names in the ELF. Table entries are 11 real values + 1 padding
word to a 12-word/24-byte-aligned boundary, except the four tone-stack tables which are
float64 (11 values, 22 words); everything else is float32. Script:
`build/host/hw100_extract` (gitignored scratch) decoded every table by reading consecutive
`.word` directives after each `_tbl:` symbol until the next symbol, auto-picking float32 vs
float64 by which interpretation gives physically plausible magnitudes (the wrong precision
choice produces obvious garbage like `1.29e+29` — unambiguous once you see both).

### 2a. Tone stack (Bass/MID/Treble/VOL — 3-band, `HW100_EQ_Calc`)
| Table | 11 points (knob 0..100 in steps of 10) |
|---|---|
| `HW100_bass_tbl` (f64) | 0.0002, 0.018, 0.043, 0.096, 0.147, 0.200, 0.173, 0.381, 0.739, 0.948, 0.973 |
| `HW100_middle_tbl` (f64) | 0.00001, 0.004, 0.106, 0.262, 0.389, 0.511, 0.635, 0.768, 0.888, 0.997, 1.000 |
| `HW100_treble_tbl` (f64) | 0.00001, 0.004, 0.106, 0.262, 0.330, 0.434, 0.540, 0.653, 0.888, 0.948, 0.950 |
| `HW100_Master_tbl` (f64, VOL) | 0.00000, 0.022, 0.052, 0.127, 0.214, 0.304, 0.397, 0.527, 0.706, 0.864, 0.922 |

**Reading (likely, not yet confirmed from the per-sample math):** all four are normalized
0..~1 knob-position-to-gain-coefficient curves, not frequency-response shapes themselves —
they almost certainly feed per-band gain multipliers into whatever filter `HW100_EQ_Calc`
builds, the same role Comet Flower's `pot_sections`/A-taper law functions play in the real
circuit math (`REF_HiwattDR103_Deriv_ToneStack.md` §3), except here they are *measured/fit
curves* (not derived from a taper law + real pot value) and there are only 4 independent bands
instead of one coupled 10-node passive network. Middle and treble are identical through the
first 4 points (knob 0-30) then diverge — consistent with two separate filters that only start
differing once their respective bands' gain ranges separate.

### 2b. "Presence" — three cascaded parametric peaking stages, one knob (`HW100_Presence_edit`)
| Table | 11 points (PRSNC knob 0..100) |
|---|---|
| `HW100_Presence_EQ1_Freq_tbl` (Hz) | 8000, 8000, 8000, 6500, 6000, 5000, 4800, 4500, 4000, 3800, 4500 |
| `HW100_Presence_EQ1_Gain_tbl` | 0, 0.1, 0.5, 1.2, 1.4, 1.7, 2.0, 2.3, 2.6, 3.0, 5.8 |
| `HW100_Presence_EQ1_Q_tbl` | 0.5, 0.5, 0.5, 0.5, 0.5, 0.55, 0.55, 0.6, 0.65, 0.72, 0.6 |
| `HW100_Presence_EQ2_Freq_tbl` (Hz) | 14000, 14000, 10000, 10000, 9000, 8000, 8000, 8000, 8000, 8000, 4500 |
| `HW100_Presence_EQ2_Gain_tbl` | 0, 0.6, 1.8, 2.1, 2.1, 2.2, 2.2, 2.4, 2.6, 2.0, 12.4 |
| `HW100_Presence_EQ3_Gain_tbl` | 0, 0, 0, 0, 0, 0, 0, 0, 0, -0.9, 0 |

**Reading:** a single PRSNC knob drives (at least) two real parametric peaking filters whose
*center frequency moves downward* as gain rises (EQ1: 8kHz->~4kHz, EQ2: 14kHz->~8kHz) — a
"more presence = lower, bigger boost" voicing, not a fixed-frequency shelf. `Gain_tbl` units
are not yet confirmed (dB or linear ratio — the EQ2 jump to 12.4 at the last point reads more
like dB). EQ3 is nearly inert (one -0.9 blip near full PRSNC) — possibly a small trim/notch
companion rather than a third independent presence band. The real Hiwatt's presence control is
a single RC network reacting with the NFB loop (`REF_HiwattDR103_Deriv_NFB_Presence.md`,
one knob, one physical network) — Zoom's version is at minimum 2, probably 3, independently
knob-mapped filters, a materially different (and functionally richer/more "produced") design
than the real amp's one-knob NFB interaction.

### 2c. Input-mode-dependent pre-EQ and gain taper (`Normal` vs `Bright`, GAIN + Input knobs)
| Table | 11 points (GAIN knob 0..100) |
|---|---|
| `HW100_Normal_Gain_tbl` (dB) | -114, -33.3, -26.0, -18.4, -14.1, -11.2, -9.0, -6.6, -3.9, -1.8, -1.0 |
| `HW100_Bright_Gain_tbl` (dB) | -114, -33.4, -26.0, -18.4, -14.2, -11.3, -9.1, -6.7, -4.0, -1.9, -1.2 |
| `HW100_NORMAL_ADJUST_PRE_EQ1_Freq_tbl` (Hz) | 400, 400, 250×8 |
| `HW100_NORMAL_ADJUST_PRE_EQ1_Gain_tbl` | -3.5, -3.5, 5×8 |
| `HW100_BRIGHT_ADJUST_PRE_EQ1_Freq_tbl` (Hz) | 400, 400, 240×8 |
| `HW100_BRIGHT_ADJUST_PRE_EQ1_Gain_tbl` | -3.5, -3.5, 5×8 |
| `HW100_Normal_Gain_EQ_Gain_tbl` | -4, -4, -4, -0.45×8 |
| `HW100_ADJUST_PRE_EQ2_Gain_tbl` | 8.2, 8.2, 0×10 |
| `HW100_Normal_Presence_Convert_tbl` | 1, 1, 1, 0.98, 0.96, 0.94, 0.91, 0.9, 0.9, 0.9, 0.9 |
| `HW100_Bright_Presence_Convert_tbl` | 1, 1, 1, 0.97, 0.93, 0.92, 0.91, 0.9, 0.9, 0.9, 0.9 |

**Reading:** Normal and Bright channels are nearly identical (240 Hz vs 250 Hz pre-EQ center,
otherwise matching step shape) — a much smaller Normal/Bright difference than the real DR103,
where the two inputs are wired to genuinely different gain-stage topologies
(`REF_HiwattDR103_Deriv_ToneStack.md` §0: vintage single-triode vs reissue shared-plate mixer,
a *structural* circuit difference, not a small EQ tweak). The -114 dB floor at GAIN=0 and the
compressed top end (only -1 to -1.2 dB from GAIN=90 to 100) describes a steep, non-linear knob
law — almost certainly audio-taper gain shaping rather than the amp's real gain-stage transfer
curve. `Normal/Bright_Presence_Convert_tbl` (1.0 -> 0.9) looks like a small cross-coupling
factor scaling the presence effect down slightly as GAIN rises, not a frequency-domain
component.

## 3. What this does and doesn't tell us yet

**Confirmed:** HW100 is built from a bank of independently knob-mapped filter/gain tables
(3-band tone stack + up to 3 presence peaking filters + input-mode pre-EQ + an audio-taper
gain law), not a physically-modeled circuit. This is architecturally the same strategy as
`NYC_MUFF`'s decoupled LPF/HPF blend tables (`recon/11_stock_drives.md` §11,
`docs/MUFF_TARGET_SPEC_2026-10-23.md` §3.1.C) — Zoom fits curves to the *sound*, Comet Flower
derives the *circuit*. The presence section in particular (independently frequency-sweeping
parametric filters) is a materially more elaborate "sounds right" design than a literal RC
network would need.

**Not yet done (the actual next step, same gap recon/11 left open for the drives):**
- `HW100_EQ_Calc`'s exact math was not read instruction-by-instruction — the filter *type*
  each table feeds (RBJ-cookbook peaking/shelving biquad is the standard assumption for
  Freq/Gain/Q-parameterized EQ, but not confirmed here) and how the 3-band tone stack's
  normalized 0..1 coefficients become an actual transfer function are both open.
- No frequency-response curve was computed for HW100 (unlike the Muff work, where the
  compiled biquad coefficients gave an exact, closed-form answer). Doing that here needs the
  filter-type confirmation above first.
- `HW100_CLIPPER_Dynamic` (the preamp nonlinearity) and `HW100_OVS_COE_bn`/`_an`
  (oversampling filter) were located but not read.
- Units on the `*_Gain_tbl` presence/pre-EQ values (dB vs. linear) are inferred from
  magnitude, not confirmed from the code that consumes them.

Comet Flower's own CF Watt side of this comparison is already independently, rigorously
verified (`tests/host/hiwatt_nets_test.cpp`, `hiwatt_netgen_test.cpp`, both passing against
the real schematic-cross-checked circuit model — see the project memory note on this session's
DSP verification work). This doc is the Zoom-side counterpart; closing the gap above would let
the two be plotted against each other the way Muff's were.

## 4. Presence control — comparable, and the result is a real mechanism difference

`HW100_EQ_Calc`'s own math was not fully read (3160 lines; no named frequency/Q tables are
referenced inside it beyond the four scalar knob lookups passed in by the caller, so the
tone-stack bands' exact filter shape remains unconfirmed per §3 — see the method note below).
The **presence** control turned out to be directly comparable without that gap, because both
sides already have real, sourced numbers:

- **Zoom (computed here):** cascading `Presence_EQ1` and `Presence_EQ2` as standard RBJ-cookbook
  peaking biquads, fed the real decoded `Freq`/`Gain`/`Q` tables (§2b), **assuming** the gain
  table units are dB (not confirmed from the code) and EQ2's unlisted Q = 1.0 (no Q table was
  found for EQ2, a guess), at `fs = 44100` (also unconfirmed — HW100 may run this stage
  oversampled, but these are low-signal-relative-to-Nyquist frequencies where the bilinear
  warp difference is small either way): a genuine **forward boost of up to ~17 dB at 5 kHz**
  at full presence, rising roughly monotonically with the knob.
- **Comet Flower / the real amp (already derived, not computed here):**
  `VirtualPedalBoardEngine/documents/REF_HiwattDR103_Deriv_NFB_Presence.md` §4 gives
  `β(f,presence)` (the global negative-feedback loop's return factor) from a full MNA solve of
  the real back-half network, cross-checked against the schematic — **confirmed, not a guess**.
  The presence pot does not add a forward boost at all; it **shunts high-frequency content out
  of the feedback-summing node**, so turning it up *reduces* negative feedback at HF (β's HF
  content drops an extra ~8-25 dB as presence goes 0→1 — table below), which lets more of the
  amplifier's own open-loop HF gain through. The doc explicitly refutes (§5, with numbers 60-70
  dB apart) an earlier "forward injection" theory of how this control works.

| f/Hz | Zoom boost, pres=0 -> 1 (dB) | Real amp's β HF-rolloff, pres=0 -> 1 (dB, re each curve's own 100 Hz) |
|---|---|---|
| 300 | 0.00 -> 0.03 | -0.15 -> -2.17 |
| 1000 | 0.00 -> 1.53 | -1.04 -> -9.54 |
| 5000 | 0.00 -> 17.29 | -8.64 -> -22.97 |
| 10000 | 0.00 -> 4.58 | -13.92 -> -28.70 |

**These two columns are not the same physical quantity** (forward output-gain boost vs. a
feedback-factor's own HF rolloff) and must not be read as directly subtractable — converting
the real amp's β-change into an equivalent output-dB boost needs the power-stage's open-loop
gain, which `REF_HiwattDR103_Deriv_NFB_Presence.md` §9 flags as its single biggest open
uncertainty (`A_pwr`, recommended default 1.5x, "the task's single biggest uncertainty").
**The finding that survives that uncertainty: Zoom's presence is a direct forward EQ boost;
Comet Flower's (and the real amp's) presence is a feedback-depth control with no forward boost
at all** — two different control topologies that both make the amp sound brighter, verified
from real sourced data on both sides, not assumed to work the same way because they share a
knob label.

Chart: https://claude.ai/artifact/QVzz7shQSxNc7Qowun3gWW (presence comparison, dataviz-skill
build, palette-validated).

**Still open (the tone-stack half of §2a/§3):** `HW100_EQ_Calc`'s own filter math was not read
to the depth the presence derivation got for free from an already-existing source. Attempting
it means finding where the 3-band tone stack's implicit center frequencies live (no `_tbl`
symbol carries them, and `HW100_EQ_Calc` builds no `0x8000xxxx`-range data address itself —
either the frequencies are plain immediate constants buried in ~3000 lines of mostly `MPYDP`/
`ADDDP`/`SUBDP` double-precision arithmetic with no `SIN`/`COS`/`RCPSP` special ops visible
from a quick scan, consistent with an inlined polynomial trig approximation rather than a
library call, or the tone-stack topology doesn't use per-band center frequencies the way a
parametric EQ does at all. Left as `guess`, not attempted further this pass.
