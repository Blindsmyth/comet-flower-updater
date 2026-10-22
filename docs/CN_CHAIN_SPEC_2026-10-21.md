# Comfortably Numb chain: "lazy" spec (2026-10-21)

Status: **design only, no code yet.** Defaults are proposed starting voicings, not verified Kit Rae numbers. Tune by ear.

## Approach
Six separate effects in one patch, in signal order. Each effect uses the pedal's native on/off, so there are no internal On params. Each stage is one page of at most 3 params, with the other internals frozen at the Comfortably Numb voicing. Until the firmware work (Thursday) the 5-slot single effect is parked.

## Signal order and controls
| # | Effect | Role | Exposed params (one page) | Frozen internals |
|---|---|---|---|---|
| 1 | `DYNACX` | CS-2 style, light compression | Sust, Level | none |
| 2 | `MUFFX` | Ram's Head Big Muff | Sust, Tone, Vol | none |
| 3 | `MISTRX` (or `CE2X`) | Electric Mistress (or CE-2) | Rate, Range | Color, Matrix |
| 4 | `DLYX` | Delay, about 370 ms | Time, Regen, Mix | none |
| 5 | `DR103` | Hiwatt DR103, one-knob | Gain, Level | Treble, Middle, Bass, Presence, Master, Cab |
| 6 | `RA200X` | RA-200 rotary | Speed, Rotor | EQ, Bright |

About 12 params, one page per stage.

## Rules for every stage
1. Unity gain at default settings. Final level is set by the amp `Level` knob or the patch level.
2. Labels short, about 5 characters (`Sust`, `Tone`, `Vol`, `Rate`, `Rang`). Real on-screen limit still to be confirmed with the owner.
3. Native bypass. The delay should keep its tail when bypassed (to verify).
4. Amp `Gain` moves Volume and Master together along one curve through the existing model, so the Muff-into-amp interaction is preserved.

## Proposed defaults (to tune)
- Dyna: Sust about 35 (light), Level unity.
- Muff: Sust about 85, Tone about 40 (around 11 o'clock), Vol set to match unity with Muff off.
- Mistress: Rate about 30, Range about 60. Subtle.
- Delay: Time 370 ms, Regen about 25, Mix about 25.
- Amp: clean-ish, Gain about 40, Level unity.
- RA200: Speed slow, Rotor 1.

## Cycle budget (static estimate, dspload sum must stay under 230)
Dyna 30 + Muff 51 + Mistress 27 + Delay 20 + Watt 69 = 197 without the RA200; 227 with it (30). These loads are old estimates, so they need bench numbers.

## Open checks before coding
1. Real slot count of each effect (`g1_slots` is blank for all but the probes and CF Master). Does the DR103 take 2?
2. Whether 6 effects fit in one patch on the pedal.
3. Display label limit on the pedal.
4. Whether the delay keeps its tail when bypassed.
5. Bench cycle numbers for Dyna, Muff, Mistress, Delay (Updater 25 is flashed).

## Later, after the firmware work (Thursday)
Per-stage knobs restored, a cheaper fixed-voicing amp core, a 5-slot or sub-menu CF Master, and the cycle-saving amp replacement (fit biquad cascade plus soft clip against the full model with the host harnesses).

## Check results (2026-10-21)
- A patch has **5 slots** (`tools/patch_g1.py`, `g1presets.py`), and the pedal refuses a patch whose declared dspload sum reaches 230.
- Header byte 0x58 (slots used) from the built ZD2s: `DYNACX`, `MUFFX`, `MISTRX`, `CE2X`, `DLYX`, `DR103`, `RA200X`, `RATX`, `DRV808X` = **1** each; `CFMPRE` = **2**; `CFM2P` = 2; `CFM5P` = 5.
- So the six-effect chain above needs 6 slots and **does not fit**. Two fitting options:
  - **A (5 separate effects):** drop one stage. `DYNACX` + `MUFFX` + `MISTRX` + `DLYX` + `DR103` = 5 slots, load 197. The RA-200 is left out.
  - **B (everything, 5 slots):** `CFMPRE` (Dyna + Muff + Mistress, 2 slots) + `DLYX` (1) + `DR103` (1) + `RA200X` (1) = **5 slots**. Declared loads 35 + 20 + 69 + 30 = 154. `CFMPRE`'s declared load is a placeholder; its static estimate is about 28.5k cycles, which on Zoom's scale `7 + 3 x kcycles` is about 92, giving roughly 211. That is under 230 but not by much, so bench it.
  - Option B needs the `CFMPRE` pages fixed first so each page is one stage (see the page layout discussion).
- Still to check on the pedal: label length, delay tail on bypass, and whether one patch with these 5 slots loads and plays.
