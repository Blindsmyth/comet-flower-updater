/* cftone.c - "CF Tone": a deterministic test program in place of the guitar, so two patches
 * (e.g. CF Watt vs CF Watt2x after it) get the identical input; tools/ua_ab.py records both
 * over USB and finds the program by its leading silence. Program (44.1 kHz samples):
 *   0.5 s silence | 82.41 110 220 440 880 1760 3520 Hz, 1 s each | 0.5 s silence |
 *   4 s exponential sweep 40 Hz -> 16 kHz          = 12 s, repeating.
 * Sine: phase in cycles, folded to |a| <= pi/2, odd polynomial to a^13 (error < 1e-7).
 * Same value on both channels. Bypass passes the guitar. */
#include <stdint.h>
#include "sh_params.h"

#define FS        44100
#define SIL       (FS / 2)
#define TONE      FS
#define NTONES    7
#define SWEEP     (4 * FS)
#define PERIOD    (SIL + NTONES * TONE + SIL + SWEEP)
#define F0_SWEEP  40.0f
/* per-sample increment ratio of the sweep: (16000/40)^(1/SWEEP) */
#define SWEEP_R   1.0000339658f

typedef struct {
    uint32_t n;                     /* sample index in the program */
    float phase, inc;
} KernelState;

typedef char cftone_state_fits[(sizeof(KernelState) <= SH_STATE_BYTES) ? 1 : -1];

static const float tones[NTONES] = { 82.40689f, 110.0f, 220.0f, 440.0f, 880.0f, 1760.0f, 3520.0f };

static inline float sin_cycles(float p)          /* p in [0, 1) */
{
    float t = p < 0.5f ? p : p - 1.0f;          /* [-0.5, 0.5) */
    float a = 6.283185307f * t;                 /* [-pi, pi) */
    float x, x2;
    if (a > 1.570796327f) a = 3.141592654f - a;
    if (a < -1.570796327f) a = -3.141592654f - a;
    x = a; x2 = x * x;
    return x * (1.0f + x2 * (-1.6666667e-1f + x2 * (8.3333333e-3f + x2 * (-1.9841270e-4f
             + x2 * (2.7557319e-6f + x2 * (-2.5052108e-8f + x2 * 1.6059044e-10f))))));
}

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff        = (float *)ctx[1];
    KernelState *s    = (KernelState *)instance[2];
    int i;

    unsigned ok = 1;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float kl   = coef[SH_PARAM_LEVEL];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(kl >= 0.0f && kl <= 1.0f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }
    {
        float amp = 0.5f * kl;
        for (i = 0; i < SH_FRAMES; i++) {
            uint32_t n = s->n;
            float y = 0.0f;
            if (n >= SIL && n < SIL + NTONES * TONE) {
                uint32_t k = (n - SIL) / TONE;
                if ((n - SIL) % TONE == 0) { s->phase = 0.0f; s->inc = tones[k] * (1.0f / FS); }
                y = amp * sin_cycles(s->phase);
            } else if (n >= 2 * SIL + NTONES * TONE) {
                if (n == 2 * SIL + NTONES * TONE) { s->phase = 0.0f; s->inc = F0_SWEEP * (1.0f / FS); }
                y = amp * sin_cycles(s->phase);
                s->inc *= SWEEP_R;
            }
            s->phase += s->inc;
            if (s->phase >= 1.0f) s->phase -= 1.0f;
            s->n = n + 1 >= PERIOD ? 0 : n + 1;
            {
                float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
                eff[i] = da + fade * (y - da);
                eff[i + SH_CH_B_OFFSET] = db + fade * (y - db);
            }
        }
    }
}
