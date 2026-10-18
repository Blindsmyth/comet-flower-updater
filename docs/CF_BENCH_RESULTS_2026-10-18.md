# CPU bench results, first runs (owner, 2026-10-17/18)

Bench firmware `GUITAR AUDIO 12` (docs/CF_BENCH_2026-10-17.md), manual runs via the desktop launcher
(`build/bench/manual.{json,md}`). Block = 132,354 cycles (SYSCLK1 364.8 MHz, 16 frames). Cost = slot median minus
the empty-slot median (~500 cycles; slot 5 baseline 3,293 = output EQ + patch level). 11,018 blocks per run, 0 lost.

| Effect | CF cycles (% block) | Stock cycles (% block) | ratio |
|---|---|---|---|
| Comp | CF Dyna 7.8k (5.9) | COMP 2.3k (1.7) | 3.4 |
| Overdrive | CF 808 16.2k (12.3) | TS_DRIVE 10.3k (7.8) | 1.6 |
| Fuzz | CF Muff 14.5k (11.0) | NYC_MUFF 8.8k (6.6) | 1.6 |
| Distortion | CF RAT 16.0k (12.1) | SQUEAK 8.1k (6.1) | 2.0 |
| Amp | CF Watt 39.7k (30.0) | HW100_1U 21.9k (16.6) | 1.8 |
| Flanger | CF Mistrss 6.6k (5.0) | VINFLNGR 2.2k (1.7) | 3.0 |
| Chorus | CF CE2 4.1k (3.1) | STEREOCH 2.9k (2.2) | 1.4 |
| Delay | (no CF delay yet) | ANDLY_3S 1.9k (1.4) | - |

Chains (CPU load = mean active cycles / block; peak = worst block):
- empty patch: Swi busy 8.8k, CPU 21 %, peak 45-47 %.
- CF Dyna, CF 808, CF Muff, CF Mistrss (+ CF Watt refused by the pedal: slot 5 at baseline): Swi 55.8k, CPU 58 %, peak 89 %.
- COMP, TS_DRIVE, NYC_MUFF, SQUEAK, HW100: Swi 61.8k, CPU 66 %, peak 100.9 % (one block over budget, audio OK).
- VINFLNGR, STEREOCH, CF RAT, ANDLY_3S: Swi 32.8k, CPU 41 %, peak 76 %.
- CF Watt alone: Swi 49k, CPU 53.5 %, peak 81-86 %.

Findings: CF Muff is ~14.5k, not the 50.6k assumed earlier (that was a misread block period). CF Watt is the
5-slot blocker; target ~22k (HW100 parity). Static estimates were low by 1.1-2x for the new kits (Dyna 4k est
vs 7.8k, Mistrss 6k vs 6.6k, CE2 4.3k vs 4.1k).
