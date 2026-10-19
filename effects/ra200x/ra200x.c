/* ra200x.c - "CF RA200": Alembic F-2B preamp into a Yamaha RA-200 pair (effects/common/ra200_g1.h) as a
 * G1 effect. Mono in (channel A), stereo out (L = cabinet 1, R = cabinet 2); bypass crossfade per channel.
 * The core state, its derived networks and the knob key live in the slot's work buffer (instance[3] ->
 * {base, end, size}, 0x81330 B, as CF CE-2 / CF Delay); the first block after each load zeroes our part of
 * it (the small slot state, zeroed by the loader, carries the primed flag). The networks are derived only
 * when a knob has moved (mna_derive, ~8 nodes). Guard prologue and output clamp as muffx.c.
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#endif
#include "sh_params.h"
#define MNA_MAXN 10             /* >= 10: mna_derive keeps scratch in rows 5..9 (the F-2B nets: 8 and 3 nodes) */
#define MNA_MAXU 1
#include "ra200_g1.h"

typedef struct {
    float vol, tre, mid, bas, spd;  /* knobs smoothed per block */
    float primed;
} KernelState;

typedef char ra200x_state_fits[(sizeof(KernelState) <= SH_STATE_BYTES) ? 1 : -1];

typedef struct {
    float key[5];                   /* vol tre mid bas bright the networks were derived from */
    RaCoeffs k;
    RaState s;
} RaWork;

#define KNOB_SMOOTH 0.1f

TS_INLINE RaWork *work_state(void **instance)
{
    const uint32_t *wb = (const uint32_t *)instance[3];
    if (!wb)
        return 0;
    if ((wb[0] & 7u) || wb[0] == 0u || wb[1] - wb[0] != wb[2] || wb[2] < sizeof(RaWork))
        return 0;
    return (RaWork *)wb[0];
}

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *HW_RESTRICT eff = (float *)ctx[1];   /* only this pointer touches the bus here */
    KernelState *s    = (KernelState *)instance[2];
    RaWork *m         = work_state(instance);
    float outL[SH_FRAMES], outR[SH_FRAMES];
    int i, bright, rotor, fresh;

    unsigned ok = m != 0;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float kv = coef[SH_PARAM_VOLUME], kt = coef[SH_PARAM_TREBLE], km = coef[SH_PARAM_MIDDLE];
    float kb = coef[SH_PARAM_BASS], kr = coef[SH_PARAM_BRIGHT], ks = coef[SH_PARAM_SPEED];
    float kz = coef[SH_PARAM_ROTOR];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(kv >= 0.0f && kv <= 1.0f)) ok = 0;
    if (!(kt >= 0.0f && kt <= 1.0f)) ok = 0;
    if (!(km >= 0.0f && km <= 1.0f)) ok = 0;
    if (!(kb >= 0.0f && kb <= 1.0f)) ok = 0;
    if (!(kr >= 0.0f && kr <= 1.0f)) ok = 0;
    if (!(ks >= 0.0f && ks <= 1.0f)) ok = 0;
    if (!(kz >= 0.0f && kz <= 1.0f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }
    bright = kr >= 0.5f;
    rotor = kz < 0.25f ? 0 : (kz < 0.75f ? 1 : 2);   /* Rotor 0..2 -> coefficient 0, 0.5, 1 */

    fresh = s->primed != 1.0f;
    if (fresh) {
        volatile uint32_t *w = (volatile uint32_t *)m;   /* no memset call */
        unsigned n;
        for (n = 0; n < sizeof(RaWork) / 4u; n++)
            w[n] = 0u;
        s->vol = kv; s->tre = kt; s->mid = km; s->bas = kb; s->spd = ks;
        m->k.gx = rotor == 0 ? 1.0f : 0.0f;
        m->k.out = 1.0f;
        s->primed = 1.0f;
    } else {
        s->vol += KNOB_SMOOTH * (kv - s->vol);
        s->tre += KNOB_SMOOTH * (kt - s->tre);
        s->mid += KNOB_SMOOTH * (km - s->mid);
        s->bas += KNOB_SMOOTH * (kb - s->bas);
        s->spd += KNOB_SMOOTH * (ks - s->spd);
    }
    if (fresh || m->key[0] != s->vol || m->key[1] != s->tre || m->key[2] != s->mid || m->key[3] != s->bas ||
        m->key[4] != (float)bright) {
        ra_derive(m->k.n1, m->k.n2, fresh ? 3 : 1, s->vol, s->tre, s->mid, s->bas, bright);
        m->key[0] = s->vol; m->key[1] = s->tre; m->key[2] = s->mid; m->key[3] = s->bas;
        m->key[4] = (float)bright;
    }
    ra_rotor_coeffs(&m->k, &m->s, s->spd, rotor);

    ra_block(&m->s, &m->k, eff, outL, outR);

    for (i = 0; i < SH_FRAMES; i++) {
        float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
        float wl = outL[i], wr = outR[i], a, b;
        if (!(wl > -8.0f && wl < 8.0f)) wl = 0.0f;
        if (!(wr > -8.0f && wr < 8.0f)) wr = 0.0f;
        a = da + fade * (wl - da);
        b = db + fade * (wr - db);
        if (!(a > -8.0f && a < 8.0f)) a = 0.0f;
        if (!(b > -8.0f && b < 8.0f)) b = 0.0f;
        eff[i] = a;
        eff[i + SH_CH_B_OFFSET] = b;
    }
}
