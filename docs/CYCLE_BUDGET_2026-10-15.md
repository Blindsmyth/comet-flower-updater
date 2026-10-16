# Cycle budget: the 50.6k vs 132k discrepancy (2026-10-15, static + CLKT design)

Queue item 3 (Phase D blocker). **Result:** the block budget is very likely
**≈132.4k CPU cycles** (364.8 MHz). The 50.6k "block period" that CF MuffT
measured is the CPU's **busy** cycles per block, because TSCL stops while the
CPU idles. A new diagnostic, **CF ClkT**, settles this in one recording.

## What is fixed

- **Block period: 16 / 44100 = 362.812 µs (2756.25 blocks/s). Confirmed.** The
  codec PLL gives exactly 44100.0 Hz from 19.2 MHz (recon/16). Probe 10's tone,
  advanced 16 samples per call, measured 439.98 Hz, so the slot callback runs
  once per block.
- **Core clock (static).** The AIS PLL header sets PLLM = 0x12 (×19), so
  19.2 MHz × 19 = 364.8 MHz and **132,354 cycles per block** (recon/16 C5). The
  part is the 375 MHz grade. No later PLL rewrite has been found. CF ClkT reads
  PLLM at run time to close this.

## Why TSCL shows 50.6k

- 50.6k counts × 2756.25 = 139.5 M counts/s. That is 7.27 × 19.2 MHz, which is
  not a PLL setting, and it is 38 % of 364.8 MHz.
- **Stock gates the CPU clock in IDLE (confirmed write):** `c0134e14 CALLP
  c015d428` → `c015d430 CALLP c015d414`:
  ```text
  c015d414 MVK 0,A4 || MVK 0,B0
  c015d418 MVKH 0x1810000,A4        ; PDCCMD 0x01810000
  c015d420 SET B0,0,16,B0           ; 0x0001FFFF: GEMPD (bit 16) + all memory PD enables
  c015d424 STW B0,*A4[0]
  ```
  Stock also has an `IDLE; BNOP B3,5` function at `1180a8e4`. Its address is
  data at `c0181730`, but the idle-loop caller has not been traced (likely).
  With GEMPD = 1, IDLE powers down the megamodule clock, and TSCL is a CPU-clock
  counter. Whether TSCL stops during that power-down is the one fact still to
  measure.

### The existing data decides between the two readings

| Reading | DR103 (224k kernel, ran every 2nd block, recon/04) | Probe 10 Load 60 = 96k (tone stayed clean) | Verdict |
|---|---|---|---|
| H2: TSCL continuous, core 139.5 MHz, budget 50.6k | 224/50.6 = 4.4, so it would run every ~5th block | 1.9 blocks of work: audio would break | **rejected** |
| H1: TSCL stops in IDLE, core 364.8 MHz, budget 132.4k | 224/132.4 = 1.7, so every 2nd block ✓ | 96–102k + ~23k baseline ≈ 119–125k: the UI starves first (the freeze was a UI hang with clean audio) ✓ | **fits** |

The baseline of about 23k is MuffT's 50.6k minus its two timed passes
(14.1k + 13.5k). It covers the stock Swi work, Probe 10 at Load 0 and interrupts.

**Still unexplained under H1:** adding CF Muff (14k) did not lower Probe 10's
freeze point (60–61, recon/04 2026-10-08). H1 predicts about 9 Load steps
lower. CF ClkT's load sweep tests this directly.

### Consequences (provisional until CF ClkT runs)

- Budget per block ≈ 132.4k minus the stock busy baseline (≈ 20–25k) minus a
  reserve for the UI task (the freeze shows the UI needs some). That leaves
  roughly **95–100k cycles for five slots**, not 50k.
- The TSCL delta between calls is a **load meter**: busy cycles per block for the
  whole system. That is more useful than a period.
- Kernel-level TSCL numbers (MuffT 14.1k, RAT, 808, DR103 224k) stay valid, since no IDLE
  happens inside a kernel.

## The measurement: CF ClkT (`effects/clkt/`, built `build/CLKT.ZD2`, id 07000f88)

Per block call, it reads TSCL and **TIMER64P0 TIM12**. Stock puts that timer in
64-bit mode clocked from AUXCLK, the 19.2 MHz oscillator (`c0169840..`, TCR
CLKSRC12 cleared; BIOS reads TIM12 at `11809f2e`), and it runs through IDLE.
The Load knob runs `knob × 200` iterations of an 8-cycle dependent loop
(verified in the disassembly: MPYSP, SUB, BNOP 1, ADDSP, NOP 3), timed by its
own TSCL pair. Once per frame it reads PLLM, PREDIV, POSTDIV, PLLDIV1, PLLCTL and
PDCCMD (reads only). The report is a tone code; decode it with
`tools/decode_memprobe.py <wav>`, which prints SYSCLK1, the budget, TIM12 per
block and TSCL per block.

Expected values under H1: TIM12/block = **6966**; SYSCLK1 = 364.8 MHz; budget
132,354; GEMPD 1. **TSCL/block at Load 50 − TSCL/block at Load 0 ≈ 80,000**
(the load cycles). Under a free-running TSCL that difference would be 0. This is
the one unambiguous number.

### Owner procedure (after the B1/diag run; DO_NOT_FLASH applies until then)

1. Install CF ClkT through the usual ask-gated updater path. Put it alone in a
   patch, in slot 0, with the other slots empty. Guitar unplugged, Level 50.
2. Record the dry output with VPE for 20 s at **Load 0**, then 20 s at **Load 25**,
   then 20 s at **Load 50**. **Do not go above 50**: Load 60 froze the pedal before.
3. Optional: repeat Load 0 with CF Muff added in slot 1. That gives Muff's real
   system cost, and with it the answer to the Muff anomaly.
4. Run `tools/decode_memprobe.py` on each take. Each 7.8 s frame covers 21,582 blocks.

From the Load 0 take: busy baseline = TSCL/block − CF ClkT's own cost (a few hundred cycles).
Five-slot budget = SYSCLK1 / 2756.25 − baseline − UI reserve. The UI reserve is
then found by stepping Load up towards the old freeze point in a later run.

## Result on hardware (2026-10-16, owner run, CF ClkT alone in slot 0)

Takes in `C:\Users\z\Documents\VPBE_Takes\` (`load 50.wav` is the **Load 0** take; `25.wav`, `50.wav`),
decoded with `tools/decode_memprobe.py`; 12 of 13 frames decode, frames within a take agree to ~1%.

| Load | load loop (TSCL, own pair) | TSCL per block | other busy work (TSCL − loop) |
|---|---|---|---|
| 0 | 0 | 64.4–65.5k | ~65k |
| 25 | 40.3k (5000 it, 8.06 cyc/it) | 104.2–105.3k | ~65k |
| 50 | 80.6k (10000 it) | 103.5k | ~23k |

- **Clock confirmed:** PLLM 18 (×19), PLL on → SYSCLK1 **364.8 MHz**, **132,354 cycles per block**;
  TIM12 = 6966.0 per block exactly; PDCCMD 0x00015555 (GEMPD 1).
- **H1 confirmed:** from Load 0 to 25, TSCL per block rose by the load cycles (+39.9k vs 40.3k), so
  TSCL stops in IDLE and TSCL per block is busy time.
- **New: ~42k of the Load-0 busy time is elastic.** At Load 50 the non-load work shrank from ~65k to
  ~23k (the fixed baseline, matching the MuffT-derived 23k). Some lower-priority work (most likely the
  UI/background tasks polling) fills free time and gives it up under load. This explains the CF Muff
  anomaly (adding 14k did not move the freeze point) and why the old freeze was a UI hang.
- **Busy time plateaus at ~104–105k per block (≈79% of 132k)** at Load 25 and 50; the reason for the
  ~28k that never shows as busy is open (time the core waits on audio DMA/IRQ with TSCL stopped is the
  likely candidate).

### Budget for effects

- **Proven safe:** 80.6k cycles of slot work per block (Load 50, audio clean, UI alive).
- **Ceiling:** below 96.7k (Load 60 froze the UI before). Fixed baseline ~23k.
- **Design budget for a 5-slot patch: ~80k cycles per block total (~16k per slot average)**, keeping
  the measured-safe point as the limit. CF Muff 14.1k, CF RAT 13.9–17.2k, CF 808 13.0–17.4k fit this.
- Optional follow-up: Load 55 (88.6k) to narrow the ceiling; DR103 (redesign) cost with a timing build.
