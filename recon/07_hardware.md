# 07 — G1X Four hardware: what is confirmed, what is inferred

Date: 2026-10-05. Web research; no G1 Four teardown with chip markings was
found. The closest public data is the MS-50G teardown, which has the same DSP
and flash as the G1 Four.

| Part | G1 Four (PCB-0993-02) | MS-50G (kanengomibako teardown) | Status for G1 Four |
|---|---|---|---|
| DSP | TMS320C6745DPTP3 | TMS320C6745 (marked "ZOOM ZFX-IV") | **confirmed** (w1ne) |
| Flash | MX25L3233F, 4 MB | MX25L3233 | **confirmed** (w1ne) |
| SDRAM | ? | EM638165TS-7G (Etron, 4M x 16 = 8 MB, 16-bit) | inferred |
| ADC | ? | WM8782 (24-bit stereo) | inferred |
| DAC | ? | PCM5101A (built-in charge pump) | inferred |
| Power | ? | RT9971 | inferred |

MS-50G measured: input impedance 390 kOhm, latency about 1.2 ms.

Not the G1 Four (do not use): the old G1/G1X boards (D175, PCB-0169/0180)
use Zoom's ZFX-3 DSP, a WM8734 codec and 2 MB Etron SDRAM.

Consequences, if the G1 Four matches the MS-50G:
- About 8 MB of external RAM on a 16-bit bus. Big buffers (delay, reverb,
  cab IR) fit, but random access to them is slow next to on-chip memory.
- The C6745's fast memory is the real limit for the inner loop: 32 KB L1D,
  32 KB L1P, 64 KB L2 (from memory; check against the datasheet).
  Lookup tables of a few KB stay cache-resident.

To confirm: a photo of an opened G1 Four / G1X Four board with legible
markings on the TSOP RAM chip and the small converter chips near the jacks.

Sources:
- https://github.com/w1ne/zoom-g1four
- https://kanengomibako.github.io/pages/00339.html (MS-50G teardown)
- https://www.manualslib.com/manual/2613703/Zoom-G1x.html?page=22 (old G1X)
- https://hackcorrelation.blogspot.com/2013/10/zoom-g1-guitar-effects-pedal-repair.html (old G1)
