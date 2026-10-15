/* clkt.c - "CF ClkT": clock and block-budget diagnostic (OFFLINE design,
 * docs/CYCLE_BUDGET_2026-10-15.md). Mutes the guitar; reports by tone code
 * (mp_fsk.h, tools/decode_memprobe.py). Never save it in a patch.
 *
 * Question: CF MuffT saw 50.6k TSCL counts between block calls, but the PLL
 * header implies 364.8 MHz = 132.4k cycles per block. Stock sets PDCCMD =
 * 0x1FFFF at boot (c015d414, GEMPD = 1), so IDLE may gate the CPU clock and
 * with it TSCL. This effect reads, per block call:
 *   TSCL            CPU cycle counter
 *   TIMER64P0 TIM12 (01c20010) clocked by AUXCLK = the 19.2 MHz oscillator
 *                   (stock TCR CLKSRC12 = 0, c0169850); it runs through IDLE
 * TIM12 per block must be 19.2e6 * 16 / 44100 = 6966. TSCL per TIM12 count
 * is the clock while busy; with Load > 0, TSCL per block rising by the load
 * cost proves TSCL stops in IDLE (a free-running TSCL cannot change per block).
 *
 * Frame words (magic 0xCF0071ED, tag 'CLKT'):
 *   2 deltas summed   3 sum TSCL delta   4 sum TIM12 delta
 *   5 PLLM            6 PREDIV | POSTDIV<<8 | PLLDIV1<<16 | PLLCTL<<24
 *                       (each divider: ratio bits 4:0, enable bit 15 -> bit 7)
 *   7 PDCCMD          8 sum TSCL cycles of the load loop alone
 *   9 TIM12 wrap (PRD12 + 1, or 0 = 2^32)   10 load iterations per block
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#define CLKT_REG(a) (*(volatile uint32_t *)(a))
#else
static unsigned TSCL;
static uint32_t clkt_host_regs[16];
#define CLKT_REG(a) (clkt_host_regs[((a) >> 2) & 15])
#endif
#include "sh_params.h"
#include "mp_fsk.h"

#define CLKT_TIM12   0x01c20010u
#define CLKT_PRD12   0x01c20018u
#define CLKT_PRD34   0x01c2001cu
#define CLKT_PLLCTL  0x01c11100u
#define CLKT_PLLM    0x01c11110u
#define CLKT_PREDIV  0x01c11114u
#define CLKT_PLLDIV1 0x01c11118u
#define CLKT_POSTDIV 0x01c11128u
#define CLKT_PDCCMD  0x01810000u
#define CLKT_DIV(r)  (((r) & 0x1fu) | (((r) >> 8) & 0x80u))

typedef struct {
    MpFsk fsk;                       /* 64 B */
    float acc;
    uint32_t last_t, last_c, wrap;
    uint32_t n, st, sc, sl;
} ClktState;                         /* 100 B */

typedef char clkt_state_fits[(sizeof(ClktState) <= SH_STATE_BYTES) ? 1 : -1];

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff        = (float *)ctx[1];
    ClktState *s      = (ClktState *)instance[2];
    float fade = coef[SH_COEFF_BYPASS];
    float kl   = coef[SH_PARAM_LOAD];
    float lvl  = coef[SH_PARAM_LEVEL] * 0.5f;
    uint32_t t, c, dt, dc, l0, l1;
    int i, j, iters;

#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD) {
        for (i = 0; i < SH_FRAMES; i++) { eff[i] = 0.0f; eff[i + SH_CH_B_OFFSET] = 0.0f; }
        return;
    }
#endif
    t = TSCL;
    c = CLKT_REG(CLKT_TIM12);
    if (!(fade >= 0.0f && fade <= 1.0f)) fade = 0.0f;
    if (!(kl >= 0.0f && kl <= 1.0f)) kl = 0.0f;
    if (!(lvl >= 0.0f && lvl <= 0.5f)) lvl = 0.0f;
    iters = (int)(kl * 20000.0f + 0.5f);

    /* Counter delta modulo the period (64-bit mode: PRD34:PRD12; only a
       zero PRD34 wraps inside 32 bits; s->wrap = 0 means 2^32 and is set at
       each frame start, the first call included). Gaps > ~3 blocks are not
       counted. */
    dc = c - s->last_c;
    if (s->wrap != 0 && c < s->last_c)
        dc = c + (s->wrap - s->last_c);
    dt = t - s->last_t;
    if (s->last_t != 0 && dt < 1000000u && dc < 20000u) {
        s->n++; s->st += dt; s->sc += dc;
    }
    s->last_t = t;
    s->last_c = c;

    l0 = TSCL;
    {
        float acc = s->acc;
        for (j = 0; j < iters; j++)
            acc = acc * 0.9999f + 1.0e-6f;
        if (!(acc > -1.0f && acc < 1.0f)) acc = 0.0f;
        s->acc = acc;
    }
    l1 = TSCL;
    s->sl += l1 - l0;

    if (MP_FSK_FRAME_START(&s->fsk)) {
        uint32_t prd34 = CLKT_REG(CLKT_PRD34);
        s->wrap = prd34 ? 0u : CLKT_REG(CLKT_PRD12) + 1u;
        s->fsk.w[0] = 0xCF0071EDu;
        s->fsk.w[1] = 0x434c4b54u;   /* 'CLKT' */
        s->fsk.w[2] = s->n;
        s->fsk.w[3] = s->st;
        s->fsk.w[4] = s->sc;
        s->fsk.w[5] = CLKT_REG(CLKT_PLLM);
        s->fsk.w[6] = CLKT_DIV(CLKT_REG(CLKT_PREDIV)) |
                      CLKT_DIV(CLKT_REG(CLKT_POSTDIV)) << 8 |
                      CLKT_DIV(CLKT_REG(CLKT_PLLDIV1)) << 16 |
                      (CLKT_REG(CLKT_PLLCTL) & 0xffu) << 24;
        s->fsk.w[7] = CLKT_REG(CLKT_PDCCMD);
        s->fsk.w[8] = s->sl;
        s->fsk.w[9] = s->wrap;
        s->fsk.w[10] = (uint32_t)iters;
        MP_FSK_SEAL(&s->fsk);
        s->n = 0; s->st = 0; s->sc = 0; s->sl = 0;
    }
    MP_FSK_BLOCK(&s->fsk, eff, lvl, fade);
}
