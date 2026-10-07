## Status
Gemini (agy) run STOPPED by Claude Code at low system memory before the build
and cost phase. Work in place: effects/common/muff_g1.h, the blob generator
(tools/gen_muff_blob.cpp, uses Comet Flower's real DiodeCapFeedbackStage::build()
at 176.4 kHz, 256 cells), effects/common/muff_blob.h, effects/muffx/blob.bin
(2573 words, 10 KB), manifest state_bytes 212 + const_blob. Stray files it left
in the repository root were moved to build/agy4/ by Claude.

## Scores (re-run by Claude, 2026-10-07)
worst: H1 0.08 dB, harmonics 0.61 dB, alias -60.2 dB (mobile core: 0.07 / 3.34 / -37.6)
better than the mobile core (harmonics AND alias) on 31 of 54 tests
STRETCH: 54 of 54 tests within 1.5 dB harmonics and -50 dB alias
ACCURACY: PASS
Why better than the mobile core: same circuit maths and tables, but the G1's
elliptic polyphase half-bands (os_hbiir.h, >100 dB image rejection) instead of
the mobile Oversampler2x.

## Cost (Claude)
NOT within budget yet. Static count (cl6x -k + c6x_cycles): per input sample
~165 + 1640 + 5 cycles (four inlined stage copies), i.e. ~29k cycles per block
(budget 15k, hard limit 20k). Each clip stage's rhs depends on its previous
output (trapezoidal ODE + ADAA quotient), a serial chain of table load + float
latency that the C674x cannot overlap: ~400 cycles per stage call at 4x.

## Design
Faithful port of FuzzMobileCore::stage() at 4x (os_hbiir up/down x2);
256-cell (v, w, V) tables per clip stage; knob tables for the Sustain HP
corner and the tone biquad (128 points); tanh table for the rails;
ADAA quotient via ts_rcp instead of a division.

## Problems / next
1. Pedal build fails: .text 22,368 B > 17,632 cap (four inlined stage copies).
   Process the four oversampled samples in a loop.
2. Cost ~29k: interleave the two clip stages across consecutive samples
   (stage 1 of sample n+1 alongside stage 2 of sample n) so the dependency
   chains overlap; consider fewer selects in the lookup; measure warm/cold on
   the pedal with a CF MUFFT timing diagnostic (mp_timing.h).
