# Review of the first Flash ports (Claude, 2026-10-17)

All three benches PASS (re-run by Claude): Dyna Comp -60.6 dB, Mistress -110.6 dB, CE-2 INTERP -57.3 / LOOSE -27.2 dB.
Pedal-rule problems the ports must fix (docs/DSP_RULES.md: no data-dependent `if` per sample, fixed loop
counts, no slow types). These branchy per-sample paths are what made CF Muff overrun on the pedal.

Rule for the fix: **the per-sample path (`*_process` and every helper it calls) has no `if`, no early
`return`, no loop with a data-dependent count.** Compute both candidates and select with a ternary of plain
values (`r = c ? a : b;`, both arms side-effect free), `fminf`/`fmaxf`, or `ts_clamp`. Clamp inputs instead of
returning early (e.g. clamp exp's argument to [-80, 80] and let the polynomial run). For small-|x| special
cases (ADAA `if (|diff| < eps)`), compute both the ADAA quotient (with a safe denominator, e.g.
`diff + (ad < eps ? eps : 0)`) and the fallback, then select. `if` is fine in `*_coeffs` (called per block).

- **dynacomp_g1.h**: lines 76-77 (exp clamp/early return), 100 (log range split), 130/134/145-146 (ln cosh /
  tanh range branches). Ternaries at 67, 79, 150, 158-159, 184-185 are fine as long as both arms are plain values.
- **mistress_g1.h**: `double lfoPhase`/`phaseInc` (64, 79, 162, 181-182) -> float, wrap with
  `p -= (p >= 1.0f) ? 1.0f : 0.0f;`; lines 96 (LFO half select), 110, 132, 148 (ADAA small-diff branches),
  182, 188 (`if (k->matrixMode)`: per-sample branch on a parameter: compute both or move to coeffs as a
  0/1 float weight).
- **ce2_g1.h**: 107, 120 (saturation table range branch), 157 (ADAA small-diff), 226 (phase wrap).
  `ce2_sat_table.h` (new file) is accepted.

After the change the bench must still print `ACCURACY: PASS`; report the new worst numbers. A float LFO
phase will lower Mistress's -110 dB match; anything inside the gates is fine.
