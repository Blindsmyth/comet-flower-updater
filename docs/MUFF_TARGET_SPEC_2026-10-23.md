# Big Muff Target Specification: 1974 "Violet" Ram's Head vs. NYC Reissue (2026-10-23)

## 1. Circuit identification

### 1.1 CF Muff: 1974 "Violet" Ram's Head Big Muff Pi (V2)
- **Pedal Identity:** Electro-Harmonix Big Muff Pi Version 2 (V2), "Ram's Head" enclosure, specifically the **1974 "Violet" circuit variant** (Kit Rae designation: "Version 2, fifth variant" / "second version" of Violet).
- **Production Era:** Circa 1973–1975 (specifically 1974 for the 560 pF feedback cap and 39k tone resistor revision).
- **Physical Characteristics:** Folded aluminum chassis with distinctive violet/purple silk-screened ink graphics and the circular "Ram's Head" caricature face logo.
- **Transistor Topology & Count:** 4-transistor discrete silicon NPN design (common emitter topology):
  - Q1: Input booster stage with asymmetric collector biasing.
  - Q2: First clipping amplifier stage (feedback diode pair).
  - Q3: Second clipping amplifier stage (feedback diode pair).
  - Q4: Output recovery / makeup gain stage.
- **Transistor Part Types:** Historically populated with **FS36999** (Fairchild house part number for the **2N5133**, typically $h_{FE} \approx 100\text{--}300$), or 2N5133, BC239C, or SE4010. Modern clones typically use BC547B, BC549C, or 2N5088.
- **Key Circuit Distinctions from other Muffs:**
  - **560 pF feedback capacitors** ($C_{10}, C_{11}, C_{12}$ in Kit Rae numbering; C2, C5, C8 in Aion numbering) across Q1, Q2, and Q3, rolling off harsh top-end and yielding fatter, smoother low-end saturation than standard 470 pF versions.
  - **Tone stack resistors enlarged to 39 kΩ** ($R_5, R_8$ in Kit Rae; R18, R19 in Aion) paired with a 4 nF high-pass capacitor and a 12 nF low-pass capacitor, tuning the passive mid-scoop center down to **~780–860 Hz** (preserving vital 1–2 kHz guitar midrange compared to later Muffs).
  - **Low emitter degeneration (100 Ω)** on clipping stages ($R_{10}, R_{21}$), maintaining very high open-loop stage gain ($|A_v| \approx 95$ / 39.5 dB) into the diode clamping network.
  - Coupling capacitors throughout are **0.1 µF (100 nF)** film capacitors.
- **Citations & URLs:**
  - Kit Rae, *The Big Muff Pi Page: Evolution of the Big Muff Pi Circuit - Part 1 (1969–1974)*: [http://www.bigmuffpage.com/Big_Muff_Pi_versions_schematics_part1.html](http://www.bigmuffpage.com/Big_Muff_Pi_versions_schematics_part1.html)
  - Kit Rae, *1973 V2 Violet Schematic (2nd Version, 1974)*: [http://www.bigmuffpage.com/images/KR_1973_V2_Violet_Schematic_2nd_version.jpg](http://www.bigmuffpage.com/images/KR_1973_V2_Violet_Schematic_2nd_version.jpg)
  - Kit Rae, *Big Muff Guts & Circuit Components*: [http://www.kitrae.net/music/big_muff_guts.html](http://www.kitrae.net/music/big_muff_guts.html)
  - Aion FX, *Big Muff Versions Historical Compilation Spreadsheet*: [https://docs.google.com/spreadsheets/d/1w3P91n2c6XolAe49RRIlzV8doR-R-MnS5foYAaRC8VA/](https://docs.google.com/spreadsheets/d/1w3P91n2c6XolAe49RRIlzV8doR-R-MnS5foYAaRC8VA/)
- **Confidence:** **Confirmed** (Primary vintage schematic trace and manufacturer documentation verified against Comet Flower manifest specification in `effects/muffx/manifest.json`).

---

### 1.2 Zoom NYC_MUFF: Electro-Harmonix NYC Reissue (V9, EC3003 / EC3003-A)
- **Pedal Identity:** Electro-Harmonix Big Muff Pi Version 9 (V9), "NYC Reissue" (PCB revisions **EC3003** / **EC3003-A**).
- **Production Era:** Introduced in **2000**; manufactured by New Wave Musical Products / EHX in Long Island City, Queens, New York. Designed originally by Bob Myer, with the V9 re-engineering handled by EHX chief engineer Fran Blanche.
- **Physical Characteristics:** Large classic folded-steel USA chassis with black/red graphics, red LED, power switch, 1/8" (3.5 mm) tip-positive power jack, and a plastic slide door for the 9V battery compartment on the bottom plate.
- **Zoom Firmware / Manual Identification:**
  - Zoom's official documentation (*G1 FOUR / G1X FOUR Effect Types and Parameters*, p. 5, `E_G1FOUR_FX-list.pdf`):
    > **"NYC Muff - Models an Electro-Harmonix Big Muff Pi. An added parameter allows you to adjust the balance of the original sound and the distortion."**
  - Effect module internal symbol: `NYC_MUFF` (effect ID `0x03000f84` family).
  - The "NYC" prefix specifically denotes the 2000 USA NYC Reissue (differentiating it from Russian Sovtek Muffs, Op-Amp Muffs, or vintage Triangle/Ram's Head units).
- **Transistor Topology & Count:** 4-transistor discrete silicon NPN design (same 4-stage block architecture as vintage Muffs), but with modern high-gain transistors:
  - Transistors: **2N5088** ($h_{FE} \approx 500\text{--}900$), later switched to BC550C in 2007 EC3003-B/C revisions.
- **Key Circuit Distinctions from Vintage / Violet Muffs:**
  - **Clipping stage emitter resistors increased to 390 Ω** ($R_{10}, R_{21}$ in Kit Rae numbering; R11, R16 in Aion numbering), borrowed from the Sovtek Russian Big Muff era. This drastically increases local negative feedback, reducing clipping open-loop stage gain from ~95 down to ~24 (a ~12 dB reduction per stage), rounding the clipping threshold.
  - **Tone stack tuned for deep modern mid-scoop:** High-pass and low-pass branch resistors are **22 kΩ** ($R_5 = R_8 = 22\text{ k}\Omega$) with $C_{HP} = 3.9\text{ nF}$ and $C_{LP} = 10\text{ nF}$. This pushes the notch frequency up into the **1.4–1.6 kHz** range with a deep -11 to -15 dB dip, creating the hollowed-out modern scooped character.
  - **Coupling capacitors increased to 1.0 µF electrolytics** (throughout all interstage coupling positions C1, C3, C4, C6, C7, C9, C12, C13), shifting sub-bass passbands down into the single-digit Hertz region.
  - **470 pF feedback capacitors** ($C_{10}, C_{11}, C_{12}$), brighter than the 560 pF Violet specification.
  - **Clipping diodes:** Early 2000 EC3003 production used **1N6263 Silicon Schottky diodes** ($V_F \approx 0.38\text{ V}$), introducing lower clipping thresholds and higher compression, before returning to standard **1N4148 silicon diodes** ($V_F \approx 0.65\text{ V}$) in 2001 EC3003-A.
- **Citations & URLs:**
  - Zoom Corporation, *G1 FOUR / G1X FOUR Effect Types and Parameters* (p. 5): [https://zoomcorp.com/media/documents/E_G1FOUR_FX-list.pdf](https://zoomcorp.com/media/documents/E_G1FOUR_FX-list.pdf)
  - Kit Rae, *The Big Muff Pi Page: Version 9 NYC Reissue (2000–Present)*: [http://www.kitrae.net/music/music_big_muff.html](http://www.kitrae.net/music/music_big_muff.html)
  - Kit Rae, *V9 NYC Reissue Big Muff Schematic (1st version, 2000)*: [http://www.bigmuffpage.com/images/schematics/V9%20NYC%20REISSUE%20BIG%20MUFF%20SCHEMATIC_1st%20version.jpg](http://www.bigmuffpage.com/images/schematics/V9%20NYC%20REISSUE%20BIG%20MUFF%20SCHEMATIC_1st%20version.jpg)
  - ElectroSmash, *Big Muff Pi Analysis*: [https://www.electrosmash.com/big-muff-pi-analysis](https://www.electrosmash.com/big-muff-pi-analysis)
  - Static firmware characterization: `recon/11_stock_drives.md` (lines 544–585).
- **Confidence:** **Confirmed** (Zoom's manual explicitly states Big Muff Pi model; the "NYC" moniker, stock parameter set, and firmware table corners align with the V9 EC3003 specification).

## 2. Component values

The acoustic signature of a Big Muff Pi is dictated almost entirely by two sub-circuits:
1. **The Clipping Stages (Stages 2 & 3):** Diode chemistry ($V_F$), emitter degeneration resistance ($R_E$, controlling open-loop gain and clipping knee hardness), and the collector-base feedback capacitors ($C_f$, setting high-frequency roll-off during clipping).
2. **The Passive Tone Stack (Stage 4):** The bridge RC filter network consisting of $R_{LP}, C_{LP}, R_{HP}, C_{HP}$ and the 100k blend potentiometer, which sets the notch center frequency, notch depth (mid-scoop), and boundary shelving slopes.

Below are the exact component values for both target circuits, cross-referencing Kit Rae's vintage PCB schematics and modern standardized parts numbering (Aion FX).

---

### 2.1 1974 "Violet" Ram's Head Component Values (CF Muff Target)
*Sources:* Kit Rae Schematic `KR_1973_V2_Violet_Schematic_2nd_version.jpg` ([URL](http://www.bigmuffpage.com/images/KR_1973_V2_Violet_Schematic_2nd_version.jpg)) and Aion FX Compilation ([URL](https://docs.google.com/spreadsheets/d/1w3P91n2c6XolAe49RRIlzV8doR-R-MnS5foYAaRC8VA/)).

#### A. Clipping Stages (Stage 2: Q2 & Stage 3: Q3)
- **Clipping Diodes:** 4x Silicon planar switching diodes (D1, D2 across Q2; D3, D4 across Q3), original vintage parts marked **1N4148** or **1N914** (or Fairchild house code).
  - Forward voltage drop: $V_F \approx 0.65\text{ V}$ at 1 mA (threshold onset $\approx 0.55\text{ V}$, saturation $\approx 0.72\text{ V}$).
  - Diode orientation: Symmetrical back-to-back anti-parallel pairs.
- **Diode DC Blocking Capacitors ($C_{block}$):** **0.1 µF (100 nF)** film capacitor in series with each diode pair ($C_5, C_{13}$ in Kit Rae; C4, C7 in Aion).
- **Feedback Capacitors ($C_f$):** **560 pF** ceramic disk ($C_{11}, C_{12}$ in Kit Rae; C5, C8 in Aion).
  - *Function:* Placed directly in parallel with the clipping diode feedback loop across collector and base. Rolls off treble frequencies with an initial corner around 1.2–1.5 kHz, producing the distinctive warm, fat, singing violin sustain of the '74 Violet.
- **Emitter Degeneration Resistors ($R_E$):** **100 Ω** ($R_{10}, R_{21}$ in Kit Rae; R11, R16 in Aion).
  - *Sonic Impact:* Minimal local feedback; yields very high open-loop gain ($|A_v| \approx \frac{R_C}{r_e + R_E} \approx \frac{12000}{26 + 100} \approx 95 \approx 39.5\text{ dB}$). Signal clips hard and abruptly against the diode threshold.
- **Collector Resistors ($R_C$):** $R_{18} = 10\text{ k}\Omega$ (Q2), $R_{11} = 15\text{ k}\Omega$ (Q3).
- **Input Series Resistors ($R_{in}$):** $R_{19} = 8.2\text{ k}\Omega$ (into Q2), $R_{12} = 8.2\text{ k}\Omega$ (into Q3).
- **Transistors:** 4x **FS36999** / **2N5133** NPN Silicon ($h_{FE} \approx 100\text{--}300$).

#### B. Passive Tone Stack (Stage 4)
- **Topology:** Single-knob bridged low-pass / high-pass passive mixer into high-impedance recovery stage.
- **Low-Pass Branch:**
  - Series Resistor ($R_{LP}$ / $R_8$ Kit Rae / R19 Aion): **39 kΩ** (0.25W carbon film/comp).
  - Shunt Capacitor to GND ($C_{LP}$ / $C_8$ Kit Rae / C11 Aion): **12 nF (0.012 µF)** Mylar film.
  - Cutoff frequency of isolated LPF: $f_{c, LP} = \frac{1}{2\pi \cdot 39\text{k}\Omega \cdot 12\text{nF}} \approx 340\text{ Hz}$.
- **High-Pass Branch:**
  - Series Capacitor ($C_{HP}$ / $C_9$ Kit Rae / C10 Aion): **4.0 nF (0.004 µF)** ceramic/film.
  - Shunt Resistor to GND ($R_{HP}$ / $R_5$ Kit Rae / R18 Aion): **39 kΩ**.
  - Cutoff frequency of isolated HPF: $f_{c, HP} = \frac{1}{2\pi \cdot 39\text{k}\Omega \cdot 4\text{nF}} \approx 1020\text{ Hz}$.
- **Tone Potentiometer:** **100 kΩ Linear** ($R_{pot} = 100\text{k}\Omega$, CTS/Bourns B100k).
  - Pin 1 (CCW / Bass): Connected to LPF junction ($V_{LP}$).
  - Pin 3 (CW / Treble): Connected to HPF junction ($V_{HP}$).
  - Pin 2 (Wiper): Blends between $V_{LP}$ and $V_{HP}$ and drives Q4 recovery stage via 0.1 µF coupling cap.

---

### 2.2 2000 NYC Reissue Component Values (Zoom NYC_MUFF Target)
*Sources:* Kit Rae Schematic `V9 NYC REISSUE BIG MUFF SCHEMATIC_1st version.jpg` ([URL](http://www.bigmuffpage.com/images/schematics/V9%20NYC%20REISSUE%20BIG%20MUFF%20SCHEMATIC_1st%20version.jpg)), ElectroSmash Analysis ([URL](https://www.electrosmash.com/big-muff-pi-analysis)), and Aion FX Compilation ([URL](https://docs.google.com/spreadsheets/d/1w3P91n2c6XolAe49RRIlzV8doR-R-MnS5foYAaRC8VA/)).

#### A. Clipping Stages (Stage 2: Q2 & Stage 3: Q3)
- **Clipping Diodes:**
  - *EC3003 (Initial 2000 run):* 4x **1N6263 Silicon Schottky diodes** ($V_F \approx 0.38\text{ V}$ at 1 mA, threshold onset $\approx 0.28\text{ V}$).
  - *EC3003-A (2001+ standard USA run):* 4x **1N4148 Silicon switching diodes** ($V_F \approx 0.65\text{ V}$ at 1 mA).
- **Diode DC Blocking Capacitors ($C_{block}$):** **1.0 µF** 50V radial electrolytic ($C_5, C_{13}$ in Kit Rae; C4, C7 in Aion). (10x larger than vintage Violet; extends clipping bandwidth down to sub-bass DC).
- **Feedback Capacitors ($C_f$):** **470 pF** ceramic disk ($C_{11}, C_{12}$ in Kit Rae; C5, C8 in Aion).
  - *Sonic Impact:* Allows more upper-mid sizzle through before feedback clipping roll-off occurs.
- **Emitter Degeneration Resistors ($R_E$):** **390 Ω** ($R_{10}, R_{21}$ in Kit Rae; R11, R16 in Aion).
  - *Sonic Impact:* **Substantial difference.** Higher negative feedback drops open-loop gain to $|A_v| \approx \frac{10000}{26 + 390} \approx 24 \approx 27.6\text{ dB}$ (a **~12 dB loss of gain per stage** compared to Violet). Causes a much softer clipping transition with less high-order harmonic spray and reduced total compression.
- **Collector Resistors ($R_C$):** $R_{18} = 10\text{ k}\Omega$ (Q2), $R_{11} = 10\text{ k}\Omega$ (Q3).
- **Input Series Resistors ($R_{in}$):** $R_{19} = 10\text{ k}\Omega$ (into Q2), $R_{12} = 10\text{ k}\Omega$ (into Q3).
- **Transistors:** 4x **2N5088** NPN Silicon ($h_{FE} \approx 500\text{--}900$).

#### B. Passive Tone Stack (Stage 4)
- **Topology:** Same bridged RC network topology, but with radically altered component values.
- **Low-Pass Branch:**
  - Series Resistor ($R_{LP}$ / $R_8$ Kit Rae / R19 Aion): **22 kΩ** (vs 39 kΩ in Violet).
  - Shunt Capacitor to GND ($C_{LP}$ / $C_8$ Kit Rae / C11 Aion): **10 nF (0.01 µF)**.
  - Cutoff frequency of isolated LPF: $f_{c, LP} = \frac{1}{2\pi \cdot 22\text{k}\Omega \cdot 10\text{nF}} \approx 723\text{ Hz}$ (more than an octave higher than Violet's 340 Hz).
- **High-Pass Branch:**
  - Series Capacitor ($C_{HP}$ / $C_9$ Kit Rae / C10 Aion): **3.9 nF (0.0039 µF)** film.
  - Shunt Resistor to GND ($R_{HP}$ / $R_5$ Kit Rae / R18 Aion): **22 kΩ** (vs 39 kΩ in Violet).
  - Cutoff frequency of isolated HPF: $f_{c, HP} = \frac{1}{2\pi \cdot 22\text{k}\Omega \cdot 3.9\text{nF}} \approx 1855\text{ Hz}$.
- **Tone Potentiometer:** **100 kΩ Linear** ($R_{pot} = 100\text{k}\Omega$, B100k).
  - Blends between the shifted 723 Hz LPF and 1855 Hz HPF branches, pushing the mid-scoop notch to **~1.4–1.6 kHz** and scooping the core guitar body frequencies.

---

### 2.3 Stage-by-Stage Component Bill of Materials Cross-Reference

| Circuit Stage | Component Function | 1974 Violet Ram's Head (CF Muff) | 2000 NYC Reissue V9 (Zoom NYC_MUFF) |
|---|---|---|---|
| **Stage 1 (Booster)** | Input Series Resistor | 39 kΩ | 39 kΩ |
| | Input Coupling Cap | 0.1 µF (film) | 1.0 µF (electrolytic) |
| | Base Pull-down / Bias | 100 kΩ | 100 kΩ |
| | Collector-Base Feedback | 470 kΩ | 510 kΩ |
| | Collector Load $R_C$ | 15 kΩ | 10 kΩ |
| | Emitter Resistor $R_E$ | 100 Ω | 100 Ω |
| | Miller Feedback Cap $C_f$ | 560 pF | 470 pF |
| | Stage 1 Coupling Out | 0.1 µF (film) | 1.0 µF (electrolytic) |
| | Sustain Potentiometer | 100 kΩ Linear | 100 kΩ Linear |
| | Sustain Ground Resistor | 1.0 kΩ | 1.8 kΩ |
| **Stage 2 (Clipper 1)** | Series Input Resistor | 8.2 kΩ | 10 kΩ |
| | Base Bias to GND | 100 kΩ | 100 kΩ |
| | Collector-Base Feedback | 470 kΩ | 470 kΩ |
| | Collector Load $R_C$ | 10 kΩ | 10 kΩ |
| | **Emitter Resistor $R_E$** | **100 Ω** (high gain) | **390 Ω** (degenerated) |
| | **Clipping Diodes** | **1N4148** ($V_F \approx 0.65\text{ V}$) | **1N6263** (0.38V) / **1N4148** |
| | Diode DC Block Cap | 0.1 µF (film) | 1.0 µF (electrolytic) |
| | **Feedback Cap $C_f$** | **560 pF** (warm) | **470 pF** (bright) |
| | Stage 2 Coupling Out | 0.1 µF (film) | 1.0 µF (electrolytic) |
| **Stage 3 (Clipper 2)** | Series Input Resistor | 8.2 kΩ | 10 kΩ |
| | Base Bias to GND | 100 kΩ | 100 kΩ |
| | Collector-Base Feedback | 470 kΩ | 470 kΩ |
| | Collector Load $R_C$ | 15 kΩ | 10 kΩ |
| | **Emitter Resistor $R_E$** | **100 Ω** (high gain) | **390 Ω** (degenerated) |
| | **Clipping Diodes** | **1N4148** ($V_F \approx 0.65\text{ V}$) | **1N6263** (0.38V) / **1N4148** |
| | Diode DC Block Cap | 0.1 µF (film) | 1.0 µF (electrolytic) |
| | **Feedback Cap $C_f$** | **560 pF** (warm) | **470 pF** (bright) |
| | Stage 3 Coupling Out | 0.1 µF (film) | 1.0 µF (electrolytic) |
| **Stage 4 (Tone Stack)** | **LPF Resistor $R_{LP}$** | **39 kΩ** | **22 kΩ** |
| | **LPF Cap $C_{LP}$** | **12 nF (0.012 µF)** | **10 nF (0.01 µF)** |
| | **HPF Cap $C_{HP}$** | **4.0 nF (0.004 µF)** | **3.9 nF (0.0039 µF)** |
| | **HPF Resistor $R_{HP}$** | **39 kΩ** | **22 kΩ** |
| | Tone Potentiometer | 100 kΩ Linear | 100 kΩ Linear |
| **Stage 5 (Recovery)** | Input Coupling Cap | 0.1 µF (film) | 1.0 µF (electrolytic) |
| | Base Bias to GND | 100 kΩ | 100 kΩ |
| | Collector-Base Feedback | 390 kΩ | 470 kΩ |
| | Collector Load $R_C$ | 10 kΩ | 10 kΩ |
| | Emitter Resistor $R_E$ | 2.7 kΩ | 2.0 kΩ |
| | Output Coupling Cap | 0.1 µF (film) | 1.0 µF (electrolytic) |
| | Volume Potentiometer | 100 kΩ Log | 100 kΩ Log |

## 3. Measured or simulated frequency response / transfer characteristic

## 4. Comparison table

## 5. Open questions
