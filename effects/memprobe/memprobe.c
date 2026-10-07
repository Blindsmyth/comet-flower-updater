/* memprobe.c - "CF MEMPRB": reports, as a tone code, where the G1X Four
 * firmware placed this effect and how fast its constant table reads.
 * Diagnostic only: the input is muted while it plays. Never save it in a patch.
 *
 * Frame (repeats): 150 ms sync tone (3 kHz), then MP_WORDS 32-bit words, MSB
 * first, 20 ms per bit: 1 kHz = 0, 2 kHz = 1. Decoder: tools/decode_memprobe.py.
 * Words:
 *   0 magic 0xCF00A55A          6 address of a stack local
 *   1 address of this function   7 instance pointer (void **instance)
 *   2 address of mp_blob (.const const_blob, 8 KB)
 *   3 instance[2] (state)        8 cycles, 128 reads over mp_blob, first call
 *   4 instance[1] (knob table)   9 cycles, same reads, at this frame's start
 *   5 ctx[1] (audio buffer)     10 cycles, 128 consecutive reads of a 512 B stack array
 *                               11 XOR of words 0..10 (check)
 * Table reads are 64 bytes apart (one per L1D line), stack reads consecutive,
 * all through a volatile pointer.
 * Cycles come from TSCL (running on the G1; it timed DR103D).
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#else
static unsigned TSCL;                /* host build: a counter that never moves */
#endif
#include "sh_params.h"

extern const float mp_blob[];

#define MP_WORDS   12
#define MP_SYNC    6615              /* 150 ms */
#define MP_BIT     882               /* 20 ms */
#define MP_FRAME   (MP_SYNC + MP_WORDS * 32 * MP_BIT)

/* cos/sin of 2 pi f / 44100 */
#define C1K 0.98987144f
#define S1K 0.14196397f
#define C2K 0.95969262f
#define S2K 0.28100373f
#define C3K 0.90944054f
#define S3K 0.41582338f

typedef struct {
    uint32_t w[MP_WORDS];            /* 48 B */
    uint32_t pos;                    /* sample position in the symbol */
    uint32_t sym;                    /* 0 = sync, 1 + n = bit n of the frame */
    uint32_t cold;                   /* first-call blob timing, 0 = not yet */
    float c, s;                      /* oscillator phasor */
} KernelState;                       /* 68 B */

typedef char mp_state_fits[(sizeof(KernelState) <= SH_STATE_BYTES) ? 1 : -1];

/* time 128 reads, 64 B apart, from p: a macro, because the kernel may not
 * make calls and cl6x would not inline a function here */
#define TIME_READS(dst, p, stride) do { \
    const volatile float *q_ = (p); uint32_t t0_, t1_; float a_ = 0.0f; int j_; \
    t0_ = TSCL; \
    for (j_ = 0; j_ < 128; j_++) a_ += q_[j_ * (stride)]; \
    t1_ = TSCL; \
    sink += a_; (dst) = t1_ - t0_; \
} while (0)

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff        = (float *)ctx[1];
    KernelState *s    = (KernelState *)instance[2];
    float fade = coef[SH_COEFF_BYPASS];
    float lvl  = coef[SH_PARAM_LEVEL] * 0.5f;
    float sink = 0.0f;
    float local[128];
    int i, k;

#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD) {
        for (i = 0; i < SH_FRAMES; i++) { eff[i] = 0.0f; eff[i + SH_CH_B_OFFSET] = 0.0f; }
        return;
    }
#endif
    if (!(fade >= 0.0f && fade <= 1.0f)) fade = 0.0f;
    if (!(lvl >= 0.0f && lvl <= 0.8f)) lvl = 0.0f;

    if (s->cold == 0) {
        TIME_READS(s->cold, mp_blob, 16);
        s->cold |= 0x80000000u;
        s->pos = 0;
        s->sym = 0;
    }
    if (s->sym == 0 && s->pos == 0) {        /* capture a new frame */
        for (i = 0; i < 128; i++) local[i] = (float)i;
        s->w[0] = 0xCF00A55Au;
        s->w[1] = (uint32_t)(uintptr_t)&SH_AUDIO_FN;
        s->w[2] = (uint32_t)(uintptr_t)mp_blob;
        s->w[3] = (uint32_t)(uintptr_t)instance[2];
        s->w[4] = (uint32_t)(uintptr_t)instance[1];
        s->w[5] = (uint32_t)(uintptr_t)ctx[1];
        s->w[6] = (uint32_t)(uintptr_t)&local[0];
        s->w[7] = (uint32_t)(uintptr_t)instance;
        s->w[8] = s->cold & 0x7fffffffu;
        TIME_READS(s->w[9], mp_blob, 16);
        TIME_READS(s->w[10], local, 1);   /* in bounds: 128 floats */
        s->w[11] = 0;
        for (k = 0; k < 11; k++) s->w[11] ^= s->w[k];
        if (sink == 1.0e30f) s->w[11] ^= 1u;  /* keep the reads alive */
    }

    for (i = 0; i < SH_FRAMES; i++) {
        float cw, sw, nc, tone;
        if (s->pos == 0) { s->c = 1.0f; s->s = 0.0f; }   /* symbol start */
        if (s->sym == 0) {
            cw = C3K; sw = S3K;
        } else {
            uint32_t bit = s->sym - 1;
            uint32_t b = (s->w[bit >> 5] >> (31 - (bit & 31))) & 1u;
            cw = b ? C2K : C1K; sw = b ? S2K : S1K;
        }
        nc   = s->c * cw - s->s * sw;
        s->s = s->c * sw + s->s * cw;
        s->c = nc;
        tone = lvl * s->s;
        eff[i] = fade * tone;
        eff[i + SH_CH_B_OFFSET] = fade * tone;
        s->pos++;
        if (s->pos >= (s->sym == 0 ? (uint32_t)MP_SYNC : (uint32_t)MP_BIT)) {
            s->pos = 0;
            s->sym = (s->sym >= MP_WORDS * 32) ? 0 : s->sym + 1;
        }
    }
}
