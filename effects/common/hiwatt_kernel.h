/* hiwatt_kernel.h - the DR103 audio kernel, shared by effects/hiwatt
 * (the effect) and effects/dr103diag (HW_DIAG 1: same processing, timed with
 * the C674x TSCL cycle counter; the output becomes test tones whose pitch in
 * Hz is cycles / 100, so the cost can be read from a recording). Only
 * kernel-level timings are reliable: ordinary code moves across the volatile
 * TSCL reads, so sections inside the sample loops cannot be timed.
 *
 * Mono DSP on channel A, written to both channels; bypass crossfade per
 * channel. Guard prologue and output clamp as in stomphacks gain.c.
 * Per block: knobs smoothed, the three networks derived (hiwatt_netgen.h),
 * then hw_block. The derived networks (HwCoeffs, 372 B) are cached in the
 * slot's work buffer (instance[3] -> {base, end, size}, 0x81330 B, as CF
 * Mistrss / CE2; docs/helpers/DELAY_MEM_SONNET_2026-10-17.md) with the six
 * smoothed knob values they came from, and re-derived only when one of those
 * changes or on the first block after a load (bench 2026-10-18: ~5k of the
 * 39.7k cycles per block). hw_coeffs is a pure function of the knobs, so the
 * output is bit-identical. Without a valid work buffer: derived every block.
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#endif
#include "sh_params.h"
#if defined(HW_DIAG) && HW_DIAG && !defined(__TI_COMPILER_VERSION__)
static unsigned TSCL;                /* host build: a counter that never moves */
#endif
/* the pedal derives the networks with hiwatt_netgen.h; the generic
 * mna_derive is not compiled in, small scratch sizes only for its headers */
#define MNA_MAXN 10
#define MNA_MAXU 1
#include "hiwatt_amp.h"

typedef struct {
    HwState dsp;                     /* 292 B */
    float vol, tre, mid, bas, mas, pre;   /* knobs smoothed per block */
    float primed;
#if HW_DIAG
    float cyc[3];                    /* smoothed cycles per block, per slot */
    float phase, nblk;               /* test tone, block counter */
#endif
} KernelState;                       /* 320 B (340 B with HW_DIAG) = state_bytes */

#ifndef HW_DIAG
#define HW_DIAG 0
#endif



#define KNOB_SMOOTH 0.1f

typedef struct {
    float key[6];                    /* vol tre mid bas mas pre the cache was derived from */
    float fs;                        /* HW_FS_OS it was derived at: the work buffer outlives the
                                      * slot's effect, and the 2x and 4x builds share this layout */
    HwCoeffs k;
} HwCoeffCache;

TS_INLINE HwCoeffCache *hw_cache(void **instance)
{
    const uint32_t *wb = (const uint32_t *)instance[3];
    if (!wb)
        return 0;
    if ((wb[0] & 7u) || wb[0] == 0u || wb[1] - wb[0] != wb[2] || wb[2] < sizeof(HwCoeffCache))
        return 0;
    return (HwCoeffCache *)wb[0];
}

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff        = (float *)ctx[1];
    KernelState *s    = (KernelState *)instance[2];
    HwCoeffs k;
    int i, cab;
#if HW_DIAG
    unsigned t0, t1, t2;
#endif

    unsigned ok = 1;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float kv = coef[SH_PARAM_VOLUME], kt = coef[SH_PARAM_TREBLE];
    float km = coef[SH_PARAM_MIDDLE], kb = coef[SH_PARAM_BASS];
    float kp = coef[SH_PARAM_PRESENCE], ks = coef[SH_PARAM_MASTER];
    float kc = coef[SH_PARAM_CAB];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(kv >= 0.0f && kv <= 1.0f)) ok = 0;
    if (!(kt >= 0.0f && kt <= 1.0f)) ok = 0;
    if (!(km >= 0.0f && km <= 1.0f)) ok = 0;
    if (!(kb >= 0.0f && kb <= 1.0f)) ok = 0;
    if (!(kp >= 0.0f && kp <= 1.0f)) ok = 0;
    if (!(ks >= 0.0f && ks <= 1.0f)) ok = 0;
    if (!(kc >= 0.0f && kc <= 1.0f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    unsigned fresh = s->primed != 1.0f;  /* first block after a load: never trust the cache */
    if (fresh) {
        s->vol = kv; s->tre = kt; s->mid = km; s->bas = kb; s->mas = ks; s->pre = kp;
        s->primed = 1.0f;
    } else {
        s->vol += KNOB_SMOOTH * (kv - s->vol);
        s->tre += KNOB_SMOOTH * (kt - s->tre);
        s->mid += KNOB_SMOOTH * (km - s->mid);
        s->bas += KNOB_SMOOTH * (kb - s->bas);
        s->mas += KNOB_SMOOTH * (ks - s->mas);
        s->pre += KNOB_SMOOTH * (kp - s->pre);
    }
#if HW_DIAG
    t0 = TSCL;                       /* read only: if the firmware never started
                                      * the counter, the tone reads 0 Hz */
#endif
    {
        /* one hw_coeffs call site: it is force-inlined and ~7 KB of .text */
        HwCoeffCache *c = hw_cache(instance);
        HwCoeffs *dst = c ? &c->k : &k;
        if (!c || fresh || c->fs != HW_FS_OS || c->key[0] != s->vol || c->key[1] != s->tre || c->key[2] != s->mid ||
            c->key[3] != s->bas || c->key[4] != s->mas || c->key[5] != s->pre) {
            hw_coeffs(dst, s->vol, s->tre, s->mid, s->bas, s->mas, s->pre);
            if (c) {
                c->key[0] = s->vol; c->key[1] = s->tre; c->key[2] = s->mid;
                c->key[3] = s->bas; c->key[4] = s->mas; c->key[5] = s->pre;
                c->fs = HW_FS_OS;
            }
        }
        if (c) {                     /* to the stack: the sample loops read it as before;
                                      * volatile so cl6x keeps a loop, not a memcpy call */
            const volatile uint32_t *src = (const volatile uint32_t *)&c->k;
            uint32_t *out = (uint32_t *)&k;
            unsigned w;
            for (w = 0; w < sizeof(HwCoeffs) / 4u; w++)
                out[w] = src[w];
        }
    }
    cab = kc > 0.5f;
#if HW_DIAG
    t1 = TSCL;
#endif

    {
        float wetb[SH_FRAMES];
        for (i = 0; i < SH_FRAMES; i++) wetb[i] = eff[i];
        hw_block(&s->dsp, &k, wetb, cab);
    for (i = 0; i < SH_FRAMES; i++) {
        float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
        float wet = wetb[i];
        float a, b;
        if (!(wet > -8.0f && wet < 8.0f)) wet = 0.0f;
        a = da + fade * (wet - da);
        b = db + fade * (wet - db);
        if (!(a > -8.0f && a < 8.0f)) a = 0.0f;
        if (!(b > -8.0f && b < 8.0f)) b = 0.0f;
        eff[i] = a;
        eff[i + SH_CH_B_OFFSET] = b;
    }
    }
#if HW_DIAG
    /* Replace the output with a triangle whose pitch is cycles / 100 Hz,
     * 0.5 s per slot: 0 silence (marker), 1 whole block, 2 network setup. */
    t2 = TSCL;
    s->cyc[1] += 0.02f * ((float)(t2 - t0) - s->cyc[1]);
    s->cyc[2] += 0.02f * ((float)(t1 - t0) - s->cyc[2]);
    s->cyc[0] = 0.0f;
    s->nblk += 1.0f;
    if (s->nblk >= 3.0f * 1378.0f) s->nblk = 0.0f;
    {
        int slot = (int)(s->nblk * (1.0f / 1378.0f));
        float f = s->cyc[slot] * (0.01f / 44100.0f), amp = slot == 0 ? 0.0f : 0.3f;
        if (f > 0.45f) f = 0.45f;
        for (i = 0; i < SH_FRAMES; i++) {
            float tri;
            s->phase += f;
            if (s->phase >= 1.0f) s->phase -= 1.0f;
            tri = 4.0f * (s->phase < 0.5f ? s->phase : 1.0f - s->phase) - 1.0f;
            eff[i] = amp * tri;
            eff[i + SH_CH_B_OFFSET] = amp * tri;
        }
    }
#endif
}
