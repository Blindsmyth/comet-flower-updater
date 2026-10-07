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

## Codex optimisation (2026-10-07)

Started optimisation run. Measurements and cycle arithmetic will be recorded here after each measurement.

### Variant 1: fixed four-sample loop (2026-10-07T04:55:18)
worst: H1 0.08 dB, harmonics 0.61 dB, alias -60.2 dB (mobile core: 0.07 / 3.34 / -37.6)
better than the mobile core (harmonics AND alias) on 31 of 54 tests
STRETCH: 54 of 54 tests within 1.5 dB harmonics and -50 dB alias
ACCURACY: PASS

Variant 1 static cycles: normal path upper bound setup 33+8+16+4+5+129, sample loop 16*(130+4*337+172), return 17 = 26,712 cycles/block. No software pipeline on audio loops. Cycle-counter output: build/codex4/loop-cycles.txt. Size measurement pending build completion.

Variant 1 pedal build: CF Muff ready; .text measurement:
- sections: ['.const', '.text']; .text 5664 B

### Variant 2: algebraic recurrence and single rail lookup
worst: H1 0.08 dB, harmonics 0.61 dB, alias -60.2 dB (mobile core: 0.07 / 3.34 / -37.6)
better than the mobile core (harmonics AND alias) on 31 of 54 tests
STRETCH: 54 of 54 tests within 1.5 dB harmonics and -50 dB alias
ACCURACY: PASS

Variant 2 raw cycle blocks (arithmetic pending):
Fx_SFX_CFMuff      29  -> $C$L4
Fx_SFX_CFMuff+      7  -> $C$L1
Fx_SFX_CFMuff++     16  -> $C$L1
Fx_SFX_CFMuff+++      3  
$C$L1             110  
$C$L2             128  
$C$L3             296  -> $C$L3
$C$L3+            166  -> $C$L2
$C$L3++            17  
$C$L4               1  PIPED LOOP PROLOG
$C$L5               3  PIPED LOOP KERNEL
$C$L6              12  PIPED LOOP EPILOG

Variant 2 build: CF Muff ready; - sections: ['.const', '.text']; .text 5056 B

### Variant 3: overlap clip stages with one oversample delay (216 B state allocation)
worst: H1 0.08 dB, harmonics 0.61 dB, alias -60.2 dB (mobile core: 0.07 / 3.34 / -37.6)
better than the mobile core (harmonics AND alias) on 31 of 54 tests
STRETCH: 54 of 54 tests within 1.5 dB harmonics and -50 dB alias
ACCURACY: PASS

Variant 3 raw cycle blocks:
Fx_SFX_CFMuff      31  -> $C$L4
Fx_SFX_CFMuff+      7  -> $C$L1
Fx_SFX_CFMuff++     17  -> $C$L1
Fx_SFX_CFMuff+++      4  
$C$L1             107  
$C$L2             129  
$C$L3             205  -> $C$L3
$C$L3+            166  -> $C$L2
$C$L3++            14  
$C$L4               1  PIPED LOOP PROLOG
$C$L5               3  PIPED LOOP KERNEL
$C$L6              12  PIPED LOOP EPILOG

Variant 3 build: CF Muff ready; - sections: ['.const', '.text']; .text 5152 B

### Variant 4: also overlap input filtering, two oversamples total latency (220 B state allocation)
worst: H1 0.08 dB, harmonics 0.61 dB, alias -60.2 dB (mobile core: 0.07 / 3.34 / -37.6)
better than the mobile core (harmonics AND alias) on 31 of 54 tests
STRETCH: 54 of 54 tests within 1.5 dB harmonics and -50 dB alias
ACCURACY: PASS

front raw cycle blocks:
Fx_SFX_CFMuff      54  -> $C$L5
Fx_SFX_CFMuff+      6  -> $C$L1
Fx_SFX_CFMuff++     17  -> $C$L2
Fx_SFX_CFMuff+++      4  
$C$L1               3  
$C$L2             109  
$C$L3             133  
$C$L4             143  -> $C$L4
$C$L4+            175  -> $C$L3
$C$L4++            17  
$C$L5               1  PIPED LOOP PROLOG
$C$L6               3  PIPED LOOP KERNEL
$C$L7              12  PIPED LOOP EPILOG

Variant 4 build: CF Muff ready; - sections: ['.const', '.text']; .text 5184 B

### Final measured result (2026-10-07)

Variant 4 retained. ACCURACY: PASS; STRETCH: 54 of 54.
Worst: H1 0.08 dB, harmonics 0.61 dB, alias -60.2 dB.
Offline pedal build ends with **CF Muff ready**.
- sections: ['.const', '.text']; .text 5184 B

Static cycle audit, including branch delay slots:
- The audio loop is NOT compiler software-pipelined. Explicit pipeline state
  lets the ordinary scheduler overlap input work at n, clip 1 at n-1, and
  clip 2/tone/recovery at n-2. Four fixed iterations per base-rate sample.
- Raw blocks are in build/codex4/front-cycles.txt; assembly in front.asm.
- Inner loop L4 = 143 cycles through its branch + 5 following delay slots.
  Those five slots are reported inside L4+ by c6x_cycles.py.
- Outer sample: L3 133 + 4*(143+5) + (175-5) + 5 outer delay slots
  = 900 cycles/sample; 16*900 = 14,400 cycles/block.
- Setup, primed path: 54+6+17+4+109 = 190 counted cycles. BNOP L2,1
  has one embedded NOP not counted by c6x_cycles.py, so use 191.
- Return: L4++ 17 minus its five outer-loop delay slots = 12.
- Total normal primed path: **191 + 16*900 + 12 = 14,603 cycles/block**.
  Conservatively including the mutually exclusive L1 block adds 3:
  **14,606 cycles/block upper bound**. Both are below 15,000.
- The only compiler PIPED LOOP is the invalid-control zero-output path,
  not the audio path. It is unrolled 2x: 8 trips, 2 stages, hence kernel
  repetitions = 8-2+1 = 7. It does not enter the audio cycle total.
- Static counts exclude cache refill and framework overhead; no pedal was
  accessed and no hardware timing is claimed.

Correction/completion of earlier intermediate cycle arithmetic:
The first provisional variant-1 arithmetic omitted repeated branch delay
slots. Conservative totals (include mutually exclusive setup blocks and
one BNOP embedded NOP where present) are:
- V1: (33+8+16+4+5+129+1) + 16*(130+4*(337+5)+(172-5)+5)
  + (17-5) = 26,928 cycles/block.
- V2: (29+7+16+3+110+1) + 16*(128+4*(296+5)+(166-5)+5)
  + (17-5) = 24,146 cycles/block.
- V3: (31+7+17+4+107+1) + 16*(129+4*(205+5)+(166-5)+5)
  + (14-5) = 18,336 cycles/block.
These are conservative bounds, not exact startup-path counts.

Implementation and tradeoffs:
- Fixed four-sample loop with MUST_ITERATE(4,4,4), UNROLL(1): one stage
  body instead of four inlined copies.
- One tanh table read pair after choosing positive/negative rail scaling.
- From v*(1+c*g)+c*w=rhs, the next RHS can be written
  2*previous_v-previous_rhs+c*(u+previous_u). This eliminates the w
  dependency without changing the mathematical trapezoidal solver.
  Tabulation/float rounding differs; the unchanged accuracy bench passes.
- input_pending and clip1_pending insert two oversampled delays: 2/176400 s
  = 11.34 microseconds (half a base-rate sample). At fixed knobs the chain
  is retimed; parameter changes also encounter these pipeline boundaries.
  This is an explicit latency tradeoff, not bit-identical output.
- Original tables, blob generator, const_blob layout, and ADAA reciprocal
  (two Newton refinements) remain unchanged. The unused w stores are gone;
  original w state slots/table fields remain reserved.
- MuffState is 204 B; with the kernel's 16 B, manifest state_bytes = 220 B,
  below the 388 B limit.

Next: if further margin is needed, compact the unused w table fields and
precompute per-cell slopes (including an extrapolation sentinel) to shorten
lookup scheduling. Retest accuracy/size/cycles for that separate change.
No commits, pushes, MIDI, or pedal operations were performed.

Final verification: compiler debug metadata gives MuffState 0xcc = 204 B. Assembly has no CALL instructions; audio branches are only the fixed four-oversample and sixteen-frame loops. Comments were added after measurement; token comparison confirms no functional change from the measured header. Final .text = 5,184 B (cap 17,632 B).

## Review by Claude (2026-10-07)
Re-run independently: bench ACCURACY PASS, STRETCH 54/54, numbers unchanged
from Gemini's version (H1 0.08, harmonics 0.61, alias -60.2 dB). Pedal build
"CF Muff ready", .text 5,184 B. Static cycles per input sample 133 (up) +
4 x 143 (stage loop) + 175 = 880 -> ~14.3k per block with setup (Codex: 14.6k
bound). Budget met (15k). Added latency 2 oversamples = 11.3 us. Not yet on
the pedal: next a real-cost check (Load test, or a CF MUFFT timing diagnostic)
and the owner's A/B against Zoom's NYC Muff.
