# Rules for building a G1X Four effect that is safe on the pedal

Collected from what we have measured and what has gone wrong (2026-10-04..06).
Each rule says where it comes from. "Proven" means it happened on the pedal.
Break a rule only on purpose, with a measurement plan and the owner's OK.

## 1. What actually went wrong with DR103 (two separate problems)

1. **Too heavy (proven).** The first DR103 build measured ≈224k TSCL cycles per
   16-sample block, exceeding the observed processing window. The pedal ran
   the effect only about every second block, which you hear as a digital
   glitch. The static estimate had said 50–70k: the branchy per-sample ADAA
   chain cost ≈3100 cycles per 4x sample (recon/04, 2026-10-05).
2. **The brick (proven effect, cause unproven).** It came from the
   *install*, not from the DSP: a MIDI `replace` of a 56 KB file stalled after
   the file close, and the pedal then hung at boot. The likely cause is the
   file-system directory filling up (127 slots, 105 used by the factory
   image, deleted files keep their slot). The pedal reads every file at boot,
   so a half-finished directory update stops it from starting
   (HANDOFF_2026-10-06 §3, docs/RECOVERY_G1.md).

The pedal's USB connection is a hand-soldered repair (recon/07). A
marginal USB link is another possible cause of the stalled transfer.

So: a bad DSP effect makes noise or freezes the screen until a power cycle; a
bad install can brick. Both are guarded below.

## 1b. Design goal (owner, 2026-10-06)

**The cheapest version that sounds the same wins.** A CF effect should be able
to share a full 5-slot patch whenever the sound allows it, like Zoom's own
drives (≈9–15k cycles/block, recon/11). Spend extra CPU only where it is
audible (aliasing, circuit response), and prove it with an on-pedal A/B,
not by analysis alone. Solo-only effects are the exception, not the aim.

## 2. Installing

- **Install through update-mode images only** (`tools/make_g1_image.py` +
  `tools/make_fs_restore_updater.py --image`). They rebuild the whole file
  system in one go, with a fresh directory. Proven on the pedal 2026-10-06.
- **Do not use MIDI `install`/`replace`/`uninstall` any more** unless there
  is a specific reason. They are the path that bricked.
- Keep the file count well under 127 and effect files small (the largest so
  far that installed fine: CF 808X, 38.5 KB).
- The owner runs every installer by hand. Recovery if the pedal does not
  start: docs/RECOVERY_G1.md (file system) or Zoom's v2.00 updater (main
  firmware).

## 3. Build limits (enforced or checked by `tools/build_g1.sh`)

| Limit | Value | Source |
|---|---|---|
| Per-instance state | ≤ 392 B undeclared | stock drives use 392 B (recon/06) |
| Slot heap (all PT_LOAD + symbols + loader overhead) | **≤ 40 KiB, enforced** by `tools/check_slot_mem.py` | fixed 0xa000 per slot, no spill (recon/14); T808 has ~0.5 KiB left |
| Code (`.text`) | 18 KB default budget | DR103 needed `ZD2_TEXT_EXTRA`; keep under 18 KB when possible |
| Stack frame | ≤ 1536 B | stock maximum (DR103 used 1428 B) |
| Constant tables | in the const blob; 27 KB proven | CF 808X diode table |
| No function calls in the kernel | stomphacks rule | no libm, no helper calls |
| No C `switch` | emits a `.switch` section the loader rejects | hit on DR103 |
| No division | no hardware divide: reciprocal + refinement | |
| Watch inlining | it blew `.text` past budget on DR103 | |
| Slot picture | ELF image 0 must be drawn, or the slot shows "BYPASS"/blank | proven 2026-10-05 |
| Bigger memory (delay lines, buffers) | no verified extra per-effect allocation service; entry fields [5]–[8] are callbacks | recon/14; design and test any separate allocation explicitly |

## 4. CPU budget

- Audio: 16 frames × 2 channels, float32, in place, 44.1 kHz (proven).
- The **true per-block cycle budget is unresolved**. Probe freeze points were
  interpreted as 96–102k cycles, but the later CF MuffT measurement found a
  50,611–50,642 TSCL-cycle block period; those interpretations conflict
  (recon/04, 2026-10-08). Use measured kernel timing and leave substantial
  margin until the clock/period relationship and full five-slot load are
  measured. The old 80k target is not a verified safe limit.
- What happens over budget: either the screen freezes and only a power cycle
  helps (probes), or the effect runs every other block and glitches (DR103).
  Neither damages anything, but neither is acceptable.
- **Process Overflow rule (found 2026-10-18):** the firmware sums the declared `dspload` of the 5 slots
  and refuses the patch unless the sum is **below 230.0** (main firmware c0141ad8..c0141b60: ADDSP over
  slots 0..4, `MVKH 0x43660000` = 230.0f, `CMPLTSP`). Declare CF effects on Zoom's own scale, fitted to
  the 2026-10-18 bench: **dspload = 7 + 3 x measured kcycles** (HW100 21.9k -> 72.7 vs 71.16 declared;
  TS Drive 10.3k -> 37.9 vs 39.37; COMP 2.3k -> 13.9 vs 13.94). Change a released effect's number with
  `tools/zd2_set_dspload.py` (only the float and the CRC change), never by rebuilding its code.
- The declared `dspload` is bookkeeping for "Process Overflow"; it does not
  reserve or limit real CPU.
- **Static cycle counts (`tools/c6x_cycles.py`) are trustworthy only for
  branch-free loops.** They matched the old 808X (74k) and were 3–4x low on
  DR103. Rule: per-sample loops without data-dependent branches (use tables,
  `fminf/fmaxf`-style selects, fixed iteration counts).
- **Every new effect gets measured on the pedal before it is played in
  earnest** with a TSCL profiler and an audible output check. Probe 10's
  freeze Load can expose failure, but its old cost formula is withdrawn:
  it disagreed with independently measured CF Muff kernel timing (recon/04).

## 5. Order of work for a new effect

1. Host bench: accuracy against the reference and aliasing (tests/host).
2. Build: all `build_g1.sh` checks pass; `.text`, state and stack within §3.
3. Static cycle count; any data-dependent branch in the sample loop is a
   red flag.
4. Image: the effect in the clean test environment, installed from update
   mode.
5. Pedal, AUTO SAVE off, effect alone in an empty patch: does it pass audio
   (check with the output audible), then the cost test.
6. Only then: pair it with other effects, set its real `dspload`, play it.
   Never save a patch holding an effect that has not passed step 5.
