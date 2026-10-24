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

## 3. Measured or simulated frequency response / transfer characteristic

## 4. Comparison table

## 5. Open questions
