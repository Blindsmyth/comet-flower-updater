/* ce2_g1.h - CF CE-2 core for the G1X Four (Boss CE-2 chorus, MN3007 BBD,
 * port of Comet Flower's ChorusProcessor). Shared by the pedal kernel (an
 * effects/<name>/<name>.c this kit does not include) and the PC bench
 * (tests/host/ce2_accuracy.cpp).
 *
 * CONTRACT (the bench depends on exactly this; do not change):
 *   typedef struct { ... } Ce2State;    zero-initialised = silent start,
 *         LFO phase 0 -- matches the desktop's channel-0 reset phase
 *   typedef struct { ... } Ce2Coeffs;
 *   void  ce2_coeffs(Ce2Coeffs *k, float rate, float depth, float mix);
 *         rate  0.1..8.0  (Comet Flower "Rate", APVTS knob units; maps
 *               LINEARLY to an LFO frequency of 0.1..3.5 Hz, matching the
 *               desktop's jmap -- do this mapping inside ce2_coeffs, not
 *               in the caller)
 *         depth 0..1      (Comet Flower "Depth"); sweep width = 5 ms * depth
 *         mix   0..1      (Comet Flower "Mix"); wet weight = 0.5 * mix,
 *               dry weight always 0.5 (the CE-2's hardwired summing amp)
 *         Called once per 16-sample block; may be costly-ish but no loops
 *         over more than a few dozen items.
 *   float ce2_process(Ce2State *s, const Ce2Coeffs *k, float x);
 *         one 44.1 kHz input sample -> one output sample. Mono, no added
 *         latency: the bench compares candidate and reference sample for
 *         sample, so any internal oversampling you add must stay sample-
 *         synchronous (zero or exactly-compensated group delay).
 *
 * Reference: Comet Flower's ChorusProcessor signal chain (Source/
 * ChorusProcessor.cpp lines 120-220, Boss CE-2 model): pre-emphasis +15 dB
 * high shelf (979 Hz, Q 0.707) -> anti-alias HPF (48 Hz) + LPF cascade
 * (6.6 kHz 1st order + 6.6 kHz Q 0.707) -> MN3007 BBD soft saturation (ADAA
 * tanh(0.7x)/0.7) -> BBD delay (Lagrange 3rd-order fractional read, center
 * 12.8 ms, +-5 ms * Depth, triangle LFO smoothed by a 72 Hz one-pole) -> CTI
 * one-pole low-pass (cutoff sweeps with delay time, against FIXED 7.8/17.8 ms
 * reference bounds regardless of Depth -- the desktop hardcodes those two
 * numbers, do not re-derive them from Depth) -> reconstruction HPF (14.6 Hz)
 * + LPF cascade (6.9 kHz 1st order + 6.9 kHz Q 0.707) -> de-emphasis (exact
 * inverse shelf) -> 50/50 dry/wet mix (wet scaled by Mix). The full double-
 * precision restatement of this chain is tests/host/ce2_accuracy.cpp,
 * function reference() -- THAT is the specification to match, not this
 * placeholder.
 */
#ifndef CE2_G1_H
#define CE2_G1_H

#include "ts808_core.h"         /* TS_INLINE, ts_clamp, ts_rcp */

typedef struct {
    /* PLACEHOLDER fields; replace freely. The real implementation needs a
     * fractional-delay ring buffer covering >= 17.8 ms at 44.1 kHz (about
     * 785 samples, ~3.1 KB as float) -- bigger than the 392 B per-instance
     * state budget in docs/DSP_RULES.md section 3, same open question as
     * the CF Mistress kit raises; see docs/helpers/AGY_CE2.md section 3. */
    float unused;
} Ce2State;

typedef struct {
    float mix;
} Ce2Coeffs;

TS_INLINE void ce2_coeffs(Ce2Coeffs *k, float rate, float depth, float mix)
{
    (void)rate;
    (void)depth;
    /* PLACEHOLDER: ignores rate and depth entirely. */
    k->mix = mix;
}

TS_INLINE float ce2_process(Ce2State *s, const Ce2Coeffs *k, float x)
{
    (void)s;
    (void)k;
    /* PLACEHOLDER pass-through: replace with the real DSP (pre/de-emphasis
     * shelves, AA/reconstruction filters, BBD saturation, Lagrange delay,
     * triangle LFO, CTI filter). This deliberately does nothing so the
     * bench FAILs until real work lands -- see
     * docs/helpers/AGY_CE2.md section 2. */
    return x;
}

#endif
