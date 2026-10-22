/* rotx.c - "CF Rotary": a simple mono Leslie-style rotary speaker for the G1X Four,
 * replacing RA200X (gives no audio and crashes USB audio when effects follow it,
 * docs/helpers/FW_RND_S4_FAULT_2026-10-22.md). Mono in (channel A); the processed
 * signal is written to both channels, as CE2X and DLYX do: both read channel A
 * only (ctx[1] = eff, index i) and duplicate their single result to channel B at
 * eff[i + SH_CH_B_OFFSET] (effects/ce2x/ce2x.c, effects/delayx/delayx.c). Bypass
 * crossfade per channel and the same (-8,8) output clamp, same convention.
 *
 * Model: a fixed 1-pole crossover at ~800 Hz splits the dry signal into a horn
 * band (highpass) and a drum band (lowpass). A true 1-pole split is exact:
 * hp = x - lp, so horn + drum == x identically -- at Depth 0 the two bands
 * recombine to the input with no coloration, which is what keeps Mix 100 / Depth
 * 0 at unity gain (the host test's level check). The horn band gets a short
 * modulated (fractional, linear-interpolated) delay for Doppler plus amplitude
 * modulation from the same rotation; the drum band gets amplitude modulation
 * only. Horn and drum spin at different fixed rates (0.8..6.7 Hz horn, 0.6..5.5
 * Hz drum, both brief-specified) and glide to a new Speed at independent rates
 * (the Ramp knob sets the glide time; the drum's glide is slower at both ends,
 * matching its larger physical rotor's inertia).
 *
 * The LFO "sine" is a triangle wave shaped by a fixed cubic
 * (tri*(1.5 - 0.5*tri*tri), the standard parabolic sine-shaper), so there is no
 * sinf() call anywhere -- no libm, no division, no switch, no calls in the
 * audio function, fixed trip count (SH_FRAMES = 16) in the only loop.
 *
 * State: LFO phases/rates, the crossover filter state and the smoothed knobs
 * live in the declared per-instance state (SH_STATE_BYTES, zeroed by the
 * loader, state guard as sh_params.h describes). The short Doppler delay line
 * (128 floats, <= 2.9 ms, 516 B) lives in the slot's work buffer (instance[3]
 * -> {base, end, size}), the same mechanism CE2X/DLYX use for their much larger
 * buffers, same guard check (work_line() below mirrors their work_state()). If
 * the work buffer is absent or too small, the kernel fails closed to silence --
 * the same fallback CE2X and DLYX use when their own guard checks fail (ok = 0
 * mutes both channels); this effect follows that existing convention rather
 * than inventing a new one. Whether the loader actually grants effect id
 * 06000f8a a work buffer is unverified (no pedal access, hard rule); see the
 * report's open-leads section.
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#endif
#include "sh_params.h"
#include "ts808_core.h"   /* TS_INLINE, ts_onepole_lp (no other use: no libm, no divide) */

/* plain C99 "restrict" is not a C++ keyword; the host kernel test includes
 * this file from a .cpp, so guard it exactly as delay_g1.h's DL_RESTRICT does */
#if defined(__TI_COMPILER_VERSION__)
#define ROT_RESTRICT restrict
#else
#define ROT_RESTRICT __restrict
#endif

typedef struct {
    float lp_s;                 /* crossover 1-pole state */
    float phase_h, phase_d;     /* LFO phases, 0..1 */
    float freq_h, freq_d;       /* current (ramped) LFO rates, Hz */
    float dp, rp, mp;           /* smoothed Depth, Ramp, Mix (0..1) */
    float primed;
} KernelState;

typedef char rotx_state_fits[(sizeof(KernelState) <= SH_STATE_BYTES) ? 1 : -1];

/* the short delay lines: live in the slot work buffer, cleared only at (re)init,
 * like CE2X's manual zero loop (no memset call in the kernel). Two lines, one per
 * band, pushed together from the SAME write pointer: the horn line is read back
 * with a modulated (Doppler) offset, the drum line with that same offset held
 * fixed (no modulation). Reading both bands at the same past index reconstructs
 * x exactly at Depth 0 (the crossover identity horn+drum==x holds at every
 * sample, so it still holds after an equal delay) -- a single shared baseline
 * delay, not an unmatched one, is what keeps Mix 100 / Depth 0 at unity gain. */
#define ROT_LINE_LEN   128u             /* 2.9 ms at 44.1 kHz, power of two */
#define ROT_LINE_MASK  ((int)ROT_LINE_LEN - 1)
typedef struct {
    float buf_h[ROT_LINE_LEN];      /* horn band: Doppler-modulated read */
    float buf_d[ROT_LINE_LEN];      /* drum band: fixed read, same baseline */
    uint32_t wp;
} RotLine;

#define KNOB_SMOOTH 0.1f

/* fixed 1-pole crossover at ~800 Hz, 44.1 kHz TPT g: tan(pi*800/44100)/(1+tan(.)) */
#define ROT_XOVER_G 0.05397285676224857f

/* horn/drum rotation rates, Hz (brief: horn 0.8/6.7 slow/fast, drum a bit slower) */
#define ROT_HORN_SLOW_HZ 0.8f
#define ROT_HORN_FAST_HZ 6.7f
#define ROT_DRUM_SLOW_HZ 0.6f
#define ROT_DRUM_FAST_HZ 5.5f

/* per-block frequency step at the fastest (Ramp=0) / slowest (Ramp=100) glide;
 * drum's steps are smaller at both ends: its glide is slower/longer than the
 * horn's, as specified. (16-sample block period 16/44100 s.) */
#define ROT_STEP_H_FAST 0.0200f   /* horn: full 5.9 Hz swing in ~0.1 s */
#define ROT_STEP_H_SLOW 0.0008f   /* horn: full swing in ~2.7 s */
#define ROT_STEP_D_FAST 0.0150f   /* drum: full 4.9 Hz swing in ~0.12 s */
#define ROT_STEP_D_SLOW 0.0004f   /* drum: full swing in ~4.4 s */

/* Doppler: base read offset and max swing, in samples (both << ROT_LINE_LEN,
 * so the fractional linear read never catches this block's own writes).
 * ROT_DOP_BASE is an exact integer: the drum line's fixed read needs no
 * fractional interpolation. */
#define ROT_DOP_BASE   64.0f
#define ROT_DOP_BASE_I 64
#define ROT_DOP_SWING  48.0f

TS_INLINE RotLine *work_line(void **instance)
{
    const uint32_t *wb = (const uint32_t *)instance[3];
    if (!wb)
        return 0;
    if ((wb[0] & 7u) || wb[0] == 0u || wb[1] - wb[0] != wb[2] || wb[2] < sizeof(RotLine))
        return 0;
    return (RotLine *)wb[0];
}

/* triangle wave from phase (0..1) shaped to a cheap approximate sine (no
 * sinf): tri in [-1,1], y = tri*(1.5 - 0.5*tri*tri), the parabolic shaper */
TS_INLINE float rot_lfo(float phase)
{
    float tri = (phase < 0.5f) ? (phase * 4.0f - 1.0f) : (3.0f - phase * 4.0f);
    return tri * (1.5f - 0.5f * tri * tri);
}

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *ROT_RESTRICT eff = (float *)ctx[1];   /* only this pointer touches the bus here */
    KernelState *s = (KernelState *)instance[2];
    RotLine *rl = work_line(instance);
    int i;

    unsigned ok = rl != 0;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float ksp  = coef[SH_PARAM_SPEED];
    float kdp  = coef[SH_PARAM_DEPTH];
    float krp  = coef[SH_PARAM_RAMP];
    float kmp  = coef[SH_PARAM_MIX];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(ksp  >= 0.0f && ksp  <= 1.0f)) ok = 0;
    if (!(kdp  >= 0.0f && kdp  <= 1.0f)) ok = 0;
    if (!(krp  >= 0.0f && krp  <= 1.0f)) ok = 0;
    if (!(kmp  >= 0.0f && kmp  <= 1.0f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    if (s->primed != 1.0f) {
        volatile uint32_t *w = (volatile uint32_t *)rl;    /* no memset call */
        unsigned n;
        for (n = 0; n < sizeof(RotLine) / 4u; n++)
            w[n] = 0u;
        s->lp_s = 0.0f; s->phase_h = 0.0f; s->phase_d = 0.0f;
        s->freq_h = ROT_HORN_SLOW_HZ; s->freq_d = ROT_DRUM_SLOW_HZ;
        s->dp = kdp; s->rp = krp; s->mp = kmp;
        s->primed = 1.0f;
    } else {
        s->dp += KNOB_SMOOTH * (kdp - s->dp);
        s->rp += KNOB_SMOOTH * (krp - s->rp);
        s->mp += KNOB_SMOOTH * (kmp - s->mp);
    }

    /* per-block: glide the horn/drum rates toward the Speed target; step size
     * from the smoothed Ramp knob, separate targets and steps per the brief */
    {
        float target_h = ROT_HORN_SLOW_HZ + ksp * (ROT_HORN_FAST_HZ - ROT_HORN_SLOW_HZ);
        float target_d = ROT_DRUM_SLOW_HZ + ksp * (ROT_DRUM_FAST_HZ - ROT_DRUM_SLOW_HZ);
        float step_h = ROT_STEP_H_FAST - s->rp * (ROT_STEP_H_FAST - ROT_STEP_H_SLOW);
        float step_d = ROT_STEP_D_FAST - s->rp * (ROT_STEP_D_FAST - ROT_STEP_D_SLOW);
        float fh = s->freq_h, fd = s->freq_d;
        fh = (fh < target_h) ? ((fh + step_h < target_h) ? fh + step_h : target_h)
                              : ((fh - step_h > target_h) ? fh - step_h : target_h);
        fd = (fd < target_d) ? ((fd + step_d < target_d) ? fd + step_d : target_d)
                              : ((fd - step_d > target_d) ? fd - step_d : target_d);
        s->freq_h = fh; s->freq_d = fd;
    }

    {
        float lp = s->lp_s;
        float ph_h = s->phase_h, ph_d = s->phase_d;
        float inc_h = s->freq_h * (1.0f / SH_SAMPLE_RATE);
        float inc_d = s->freq_d * (1.0f / SH_SAMPLE_RATE);
        float depth_amp = 0.5f * s->dp;           /* +-depth_amp amplitude swing */
        float dop_swing = ROT_DOP_SWING * s->dp;  /* Doppler swing, samples */
        float mix = s->mp;
        int wp = (int)rl->wp;
        float *ROT_RESTRICT buf_h = rl->buf_h;
        float *ROT_RESTRICT buf_d = rl->buf_d;

        _Pragma("MUST_ITERATE(16,16)")
        for (i = 0; i < SH_FRAMES; i++) {
            float x = eff[i];
            float y = ts_onepole_lp(&lp, ROT_XOVER_G, x);  /* drum band (LP) */
            float horn = x - y;                            /* horn band (HP) */
            float drum = y;
            float sine_h, sine_d, delaySamples, mu, a, b, dop, drumDelayed, ampH, ampD, wet;
            int M, idx0, idx1, idxD;

            buf_h[wp] = horn;
            buf_d[wp] = drum;
            wp = (wp + 1) & ROT_LINE_MASK;

            ph_h += inc_h; ph_h -= (ph_h >= 1.0f) ? 1.0f : 0.0f;
            ph_d += inc_d; ph_d -= (ph_d >= 1.0f) ? 1.0f : 0.0f;
            sine_h = rot_lfo(ph_h);
            sine_d = rot_lfo(ph_d);

            /* horn: the same baseline offset, Doppler-modulated, fractional */
            delaySamples = ROT_DOP_BASE + dop_swing * sine_h;
            M = (int)delaySamples;
            mu = delaySamples - (float)M;
            idx0 = (wp - 1 - M + 2 * (int)ROT_LINE_LEN) & ROT_LINE_MASK;
            idx1 = (idx0 - 1 + (int)ROT_LINE_LEN) & ROT_LINE_MASK;
            a = buf_h[idx0]; b = buf_h[idx1];
            dop = a + (b - a) * mu;

            /* drum: the SAME baseline offset, held fixed (no Doppler, no
             * interpolation needed: ROT_DOP_BASE_I is an exact integer) */
            idxD = (wp - 1 - ROT_DOP_BASE_I + 2 * (int)ROT_LINE_LEN) & ROT_LINE_MASK;
            drumDelayed = buf_d[idxD];

            ampH = 1.0f + depth_amp * sine_h;
            ampD = 1.0f + depth_amp * sine_d;
            /* dry from the same baseline delay as the wet bands: an undelayed
             * dry against the 64-sample wet would comb-filter at partial Mix */
            wet = (buf_h[idxD] + drumDelayed) * (1.0f - mix) + (dop * ampH + drumDelayed * ampD) * mix;
            if (!(wet > -8.0f && wet < 8.0f)) wet = 0.0f;

            {
                float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
                float oa = da + fade * (wet - da);
                float ob = db + fade * (wet - db);
                if (!(oa > -8.0f && oa < 8.0f)) oa = 0.0f;
                if (!(ob > -8.0f && ob < 8.0f)) ob = 0.0f;
                eff[i] = oa;
                eff[i + SH_CH_B_OFFSET] = ob;
            }
        }
        s->lp_s = lp; s->phase_h = ph_h; s->phase_d = ph_d;
        rl->wp = (uint32_t)wp;
    }
}
