/* mp_fsk.h - the CF diagnostics' tone-code transmitter (FSK), shared by
 * CF MEMPRB and the timing effects. Decoder: tools/decode_memprobe.py.
 * Frame: 150 ms sync tone (3 kHz), then MP_WORDS 32-bit words MSB first,
 * 20 ms per bit, 1 kHz = 0, 2 kHz = 1. Word 0 is a magic number naming the
 * diagnostic; word MP_WORDS-1 is the XOR of the others.
 * The block writer is a macro: effect kernels may not make calls, and cl6x
 * does not always inline functions. */
#ifndef MP_FSK_H
#define MP_FSK_H
#include <stdint.h>

#define MP_WORDS   12
#define MP_SYNC    6624              /* 150.2 ms: frame = 345312 samples = 21582 blocks, so
                                      * every frame starts on a block boundary */
#define MP_BIT     882               /* 20 ms */

/* cos/sin of 2 pi f / 44100 */
#define MP_C1K 0.98987144f
#define MP_S1K 0.14196397f
#define MP_C2K 0.95969262f
#define MP_S2K 0.28100373f
#define MP_C3K 0.90944054f
#define MP_S3K 0.41582338f

typedef struct {
    uint32_t w[MP_WORDS];            /* 48 B */
    uint32_t pos;                    /* sample position in the symbol */
    uint32_t sym;                    /* 0 = sync, 1 + n = bit n of the frame */
    float c, s;                      /* oscillator phasor */
} MpFsk;                             /* 64 B */

/* true at the first sample of a frame: the moment to fill f->w */
#define MP_FSK_FRAME_START(f) ((f)->sym == 0 && (f)->pos == 0)

/* set the check word after filling words 0..MP_WORDS-2 */
#define MP_FSK_SEAL(f) do { int k_; (f)->w[MP_WORDS - 1] = 0; \
    for (k_ = 0; k_ < MP_WORDS - 1; k_++) (f)->w[MP_WORDS - 1] ^= (f)->w[k_]; } while (0)

/* write SH_FRAMES samples of the code, scaled by lvl, crossfaded by fade,
 * to channels A and B of eff */
#define MP_FSK_BLOCK(f, eff, lvl, fade) do { int i_; \
    for (i_ = 0; i_ < SH_FRAMES; i_++) { \
        float cw_, sw_, nc_, t_; \
        if ((f)->pos == 0) { (f)->c = 1.0f; (f)->s = 0.0f; } \
        if ((f)->sym == 0) { cw_ = MP_C3K; sw_ = MP_S3K; } \
        else { uint32_t bit_ = (f)->sym - 1; \
               uint32_t b_ = ((f)->w[bit_ >> 5] >> (31 - (bit_ & 31))) & 1u; \
               cw_ = b_ ? MP_C2K : MP_C1K; sw_ = b_ ? MP_S2K : MP_S1K; } \
        nc_ = (f)->c * cw_ - (f)->s * sw_; \
        (f)->s = (f)->c * sw_ + (f)->s * cw_; \
        (f)->c = nc_; \
        t_ = (lvl) * (f)->s; \
        (eff)[i_] = (fade) * t_; \
        (eff)[i_ + SH_CH_B_OFFSET] = (fade) * t_; \
        (f)->pos++; \
        if ((f)->pos >= ((f)->sym == 0 ? (uint32_t)MP_SYNC : (uint32_t)MP_BIT)) { \
            (f)->pos = 0; \
            (f)->sym = ((f)->sym >= MP_WORDS * 32) ? 0 : (f)->sym + 1; } \
    } } while (0)

#endif
