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


## Owner's board photos (2026-10-06) — confirmed parts
Photos: `backup/photos/2026-10-06/` (gitignored), board PCB-0993-02, date
code 200114 on side B.

| Ref | Marking | Part | Notes |
|---|---|---|---|
| IC1 | TMS320 C6745DPTP3 | TI C6745 DSP, 176-pin | confirmed |
| IC2 | EtronTech EM638165TSD-7G | 64 Mbit SDRAM, 4M × 16 = **8 MB** | confirms the MS-50G inference |
| IC3 | IS25LP032 (ISSI, date 1918) | 32 Mbit SPI NOR flash = **4 MB** | not the MX25L3233F w1ne reported: a second source, same size |
| IC12 | AC3101I / TI 93I | **TI TLV320AIC3101** stereo audio codec (ADC + DAC, I2C control, QFN-32) | replaces the WM8782 + PCM5101A guess; fits the firmware's `g_Semaphore_SetI2C0` |
| X1 | crystal | DSP clock | frequency not legible |
| IC4, IC5, IC6 (X01DJ), IC10, IC13 | small SOT/SOIC parts | regulators / support | not identified |

Connectors worth knowing:
- **CN2, 7 pins, right next to the flash (IC3)**: its traces run to IC3.
  Very likely a factory **SPI flash programming header**. If confirmed (meter
  continuity CN2 → IC3 pins: CS 1, SO 2, WP 3, GND 4, SI 5, SCK 6, HOLD 7,
  VCC 8), a cheap 3.3 V SPI programmer could read and write the whole 4 MB
  flash, boot program included: a complete backup and a recovery path that
  does not depend on update mode. Read-only first; never 5 V.
- **CN5, 7 pins, next to the DSP**: possibly JTAG (TMS, TCK, TDI, TDO, TRST,
  VCC, GND is exactly 7) or a debug UART. Unconfirmed.

USB: no USB controller chip is visible in these photos. The C6745 has no
USB device port, and the firmware drives USB through SPI semaphores and a
USB software interrupt, so a separate controller should sit near the USB
socket. A photo of side A around the USB socket would settle the USB-audio
question (recon/10).

**The owner's USB repair (2026-10-06):** the pedal's USB socket broke
earlier; a USB cable is soldered straight onto the board (the hot-glued
wires on side B, top edge near TP41/D340). It carries power and data and is
how every PC connection in this project has been made. Consequences:
- The original socket's footprint shows where the USB lines enter the
  board; the USB controller should be close to it on side A.
- Hand-soldered, untwisted D+/D- wires can cause marginal USB signalling.
  That is a plausible contributor to the 2026-10-05 transfer stall that
  bricked the pedal (DR103 replace), alongside the file-system theory.
  Another reason to install only through update-mode images, which survive
  a failed transfer, and to keep the cable short and the joints sound.
