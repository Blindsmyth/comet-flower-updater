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
  32 KB L1P, **256 KB L2** (corrected 2026-10-25 against the real TI datasheet —
  see "TI datasheet facts" below; the 64 KB figure above was a guess that was
  never actually checked, and was wrong by 4x).
  Lookup tables of a few KB stay cache-resident; 256 KB is also enough room to
  reconsider keeping bigger per-effect tables L2-resident instead of external.

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

USB (CORRECTED 2026-10-07, recon/15): the firmware drives the C6745's own
integrated USB0 controller at 0x01e00000; no external USB chip is needed.
The earlier reasoning below was wrong. Original note: no USB controller chip
is visible in these photos. The C6745 has no
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

### What the parts imply (2026-10-06, to be confirmed where marked)
- **Clock (likely):** the speed grade in "C6745DPTP3" reads as the 375 MHz
  part (4 = 456 MHz). At 375 MHz one 16-sample block at 44.1 kHz is
  ≈136k cycles. With effects freezing the UI at ≈96k, the firmware's own
  work is ≈40k per block. That fits the recon/06 numbers.
- **Codec TLV320AIC3101:** stereo ADC and DAC, sample rates up to 96 kHz,
  analog input gain (PGA) and output volume set over I2C by the firmware,
  plus built-in digital filters on the DAC path (per its datasheet). Open
  ideas: input headroom and gain staging are firmware settings; the codec's
  filters could do fixed EQ at zero DSP cost; a higher sample rate is
  possible in hardware but would change the whole firmware's timing.
- **The second ADC channel:** the input is mono, so one codec input
  channel may be unused, or used for something else. Unknown.
- **8 MB SDRAM:** ≈47 s of mono float32 audio at 44.1 kHz; long delays,
  reverbs and cabinet IRs fit, at the cost of slower external memory.

## TI datasheet facts (confirmed 2026-10-25, SPRS377F)

Prompted by a direct board photo re-confirming IC1 = `TMS320C6745DPTP3` and IC2 =
`EtronTech EM638165TSD-7G` (matching this doc's existing "confirmed" rows exactly — nothing
new there). Question raised: are we using all *directly available* information, rather than
guessing where an official source would just answer it? Checked — one guess above (L2 size)
turned out to be wrong by 4x, and one real open RE question turned out to have an answer
sitting in the datasheet's own peripheral table. Source: TI's own datasheet, literature number
**SPRS377F** ("TMS320C6745, TMS320C6747 Fixed- and Floating-Point Digital Signal Processor",
Sept 2008, rev. June 2014), pulled directly from ti.com and read with `pypdf` (text layer is
clean; `WebFetch`'s small model and most PDF mirrors choke on it or 403, `pdftoppm` isn't
installed locally for the Read tool's page-render path — local `pip install pypdf` + a plain
text dump was the fastest path that actually worked). Companion docs it cites for anything
below the top-level memory map: **TMS320C674x DSP Megamodule TRM (SPRUFK5x / later folded into
SPRUH91)** for per-peripheral register bits, **TMS320C674x/OMAP-L1x Processor Peripherals
Overview Reference Guide (SPRUFK9x)**.

**On-chip RAM (Table 3-1), corrected:** 32 KB L1P + 32 KB L1D + **256 KB L2** = 320 KB total on
the C6745 (the C6747 adds another 128 KB "additional memory" for 448 KB — don't conflate the
two parts' numbers, several web summaries do).

**The C6745 is missing peripherals the C6747 has — confirmed by its own dedicated memory map
(Table 3-5, distinct from the C6747's Table 3-4), not just the feature-comparison table:**
at the *same address* the C6747 map lists `0x01E1 3000` as "LCD Controller", the **C6745 map
lists that address as "Memory Protection Unit 1 (MPU1)" instead — the LCD Controller block
is absent from the C6745's address space entirely, not just disabled.** Also absent on C6745
(present on C6747): RTC, UHPI, USB1 (OHCI host), and a 3rd McASP (McASP2) — the C6745 table
jumps straight from McASP1 Data to UART1 where C6747 has McASP2's three register blocks.
**This directly bears on the open "LCD edit screen unlocated" question (FW R&D 2026-10-22,
[[project-fw-rnd-2026-10-22]]): there is no dedicated LCD-controller peripheral to find on this
chip.** Whatever drives the pedal's screen, it is not a TI LCDC block at a fixed address —
it's either bit-banged over GPIO/SPI, or the "LCD Controller" peripheral name in any firmware
symbol/string is leftover naming from Zoom's shared C6747-based codebase and doesn't map to
real hardware here. Stop searching for an LCDC MMIO region; look for GPIO/SPI bit-banging
instead.

**EMIFA vs EMIFB — which bus the SDRAM is actually on:** Table 3-1 says C6745's EMIFA is
*asynchronous only* (RAM/Flash/NOR/NAND, 8-bit bus, no SDRAM support) — only the C6747's EMIFA
can do SDRAM. C6745's own Table 3-5 confirms this structurally: `0x4000 0000–0x5FFF FFFF`
(EMIFA SDRAM CS0 on the C6747 map) is blank/reserved on the C6745 map. The 8 MB EM638165
SDRAM must therefore be wired through **EMIFB** (`0xC000 0000–0xCFFF FFFF`, 256 MB window,
`0xB000 0000` control registers; EMIFB supports SDRAM up to 152 MHz). EMIFA on this chip is
free for async flash/peripheral access only (`0x6000 0000`–`0x6800 0000`, CS2–CS5, 32 MB each,
8-bit).

**C6745 peripheral register base addresses (Table 3-5), the ones relevant to this project:**
`0x01C2 0000`/`1000` Timer64P0/1, `0x01C2 2000` I2C0, `0x01C4 1000` SPI0, `0x01C4 2000` UART0,
`0x01D0 0000`/`4000` McASP0/1 Control, `0x01D0 C000`/`D000` UART1/UART2, `0x01E0 0000` USB0,
`0x01E1 2000` SPI1, `0x01E2 5000`/`6000`/`8000` GPIO/`I2C1`/etc area (watch the address shift
here vs the C6747 map — USB1 doesn't exist on C6745 so everything after it shifts down 0x3000),
`0x0180 0000` DSP interrupt controller, `0x0181 1000`/`2000` Security ID / Revision ID
registers. Useful for cross-checking any peripheral-base constant already hardcoded in the
firmware disassembly against ground truth rather than inferring it from access patterns alone.

**Silicon revision, for free if ever useful:** `DEVIDR0` (CPU ID + Rev register) reads
`0x0B7D F02F` on silicon rev 1.0, `0x8B7D F02F` on rev 1.1, `0x9B7D F02F` on revs 2.0/2.1/3.0.
A register dump (if ever reachable via JTAG or a debug path) identifies the exact die rev for
free.

**Clock, confirmed not just inferred:** the "3" in `DPTP3`'s device-nomenclature legend
(Section 7.1.2, Figure 7-1) is "375 MHz (Revision B)" — matches this doc's 2026-10-06 guess
above exactly. Commercial temp grade (0–90°C), confirmed by the orderable-parts table
(`TMS320C6745DPTP3`, `Op temp (°C): 0 to 90`).

**CN5 (7-pin, next to the DSP, "possibly JTAG... unconfirmed" above):** standard TI JTAG on a
C674x part is exactly TMS, TCK, TDI, TDO, TRST + VCC + GND = 7 signals — the pin count match is
not a coincidence. Strengthens the JTAG hypothesis; still not confirmed by continuity.

Not pulled yet (next time this doc needs more than the above): exact GPIO bank electrical
specs, eHRPWM/eCAP pinout (unlikely relevant — this project doesn't use those), full EMIFA
async timing tables (only relevant if driving raw NOR/NAND directly, which this project
doesn't do — the SPI flash is driven over SPI0, not EMIFA).
