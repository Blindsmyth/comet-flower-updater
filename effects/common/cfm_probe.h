/* cfm_probe.h - CF Master loader probe (docs/C6745_DESIGN.md, CF Master step 3).
 * One kernel for the multi-slot test effects CF M5 (header 0x58 = 5) and CF M2 (= 2).
 * Questions: does a multi-slot effect load and pass audio; how many knobs and pages
 * does the pedal show and pass to the DSP; how is it called and where does it live;
 * which slot work buffers does anyone else touch while it is loaded.
 *
 * Mode 0: audio passes, scaled by Gain (0..2x): test A.
 * Mode 1: mutes the guitar and sends tone-code frames (mp_fsk.h,
 *         tools/decode_memprobe.py), alternating two pages:
 *   page 0 'CFM0': 2 calls  3 sum TIM12 delta (calls per block = w2 / (w3 / 6966))
 *                  4 calls whose instance differed from the first one seen
 *                  5 instance  6 instance[1] (coef)  7 instance[2] (state)
 *                  8 work base (instance[3] -> {base, end, size})  9 work size
 *                  10 code address (the audio function)
 *   page 1 'CFM1': 2 bit k = slot k's work buffer changed since the previous
 *                    page 1 (checksum of its first 4 KB; k = 0..4)
 *                  3 bit k = that 4 KB is all zero
 *                  4..6 knobs 1-12 x 100 (coef, rounded), 8 bits each, knob 1 in
 *                    the top byte of word 4
 *                  7..10 checksums of the first 4 KB of slot work buffers 0..3
 * Only reads the work buffers: never writes outside its own state.
 * Never save it in a patch.
 */
#include <stdint.h>
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
#define CFM_REG(a) (*(volatile uint32_t *)(a))
#define CFM_MEM(a) ((const volatile uint32_t *)(a))
#else
static uint32_t cfm_host_regs[16];
static uint32_t cfm_host_mem[1024];
#define CFM_REG(a) (cfm_host_regs[((a) >> 2) & 15])
#define CFM_MEM(a) ((const volatile uint32_t *)cfm_host_mem)
#endif
#include "sh_params.h"
#include "mp_fsk.h"

#define CFM_TIM12    0x01c20010u
#define CFM_WB0      0xc0226000u     /* slot 0 work buffer; stride 0x81330 (recon/14) */
#define CFM_WB_STEP  0x81330u
#define CFM_SUM_WORDS 1024u          /* 4 KB per buffer */

typedef struct {
    MpFsk fsk;                       /* 64 B */
    uint32_t last_c, n, sc, other;
    uint32_t first_inst, page;
    uint32_t sum[5];
} CfmState;                          /* 108 B */

typedef char cfm_state_fits[(sizeof(CfmState) <= SH_STATE_BYTES) ? 1 : -1];

/* through int: float -> unsigned would call __c6xabi_fixfu */
#define CFM_KNOB(c, p) ((uint32_t)(int)((c)[p] * 100.0f + 0.5f) & 0xffu)

void SH_AUDIO_FN(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff        = (float *)ctx[1];
    CfmState *s       = (CfmState *)instance[2];
    float fade = coef[SH_COEFF_BYPASS];
    uint32_t c, dc;
    int i;

#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        return;                      /* not initialised yet: leave the audio alone */
#endif
    if (!(fade >= 0.0f && fade <= 1.0f)) fade = 0.0f;

    c = CFM_REG(CFM_TIM12);
    dc = c - s->last_c;
    if (s->last_c != 0 && dc < 20000u) { s->n++; s->sc += dc; }
    s->last_c = c;
    if (s->first_inst == 0) s->first_inst = (uint32_t)instance;
    else if (s->first_inst != (uint32_t)instance) s->other++;

    if (coef[SH_PARAM_MODE] < 0.5f) {
        float g = 1.0f + fade * (2.0f * coef[SH_PARAM_GAIN] - 1.0f);
        for (i = 0; i < 2 * SH_FRAMES; i++) {
            float y = eff[i] * g;
            if (!(y > -8.0f && y < 8.0f)) y = 0.0f;
            eff[i] = y;
        }
        return;
    }

    if (MP_FSK_FRAME_START(&s->fsk)) {
        uint32_t *w = s->fsk.w;
        const uint32_t *wb = (const uint32_t *)instance[3];
        w[0] = 0xCF0071EDu;
        if ((s->page & 1u) == 0) {
            w[1] = 0x43464d30u;      /* 'CFM0' */
            w[2] = s->n; w[3] = s->sc; w[4] = s->other;
            w[5] = (uint32_t)instance;
            w[6] = (uint32_t)instance[1];
            w[7] = (uint32_t)instance[2];
            w[8] = wb ? wb[0] : 0u;
            w[9] = wb ? wb[2] : 0u;
            w[10] = (uint32_t)&SH_AUDIO_FN;
            s->n = 0; s->sc = 0; s->other = 0;
        } else {
            uint32_t changed = 0, zero = 0, k, j;
            for (k = 0; k < 5; k++) {
                const volatile uint32_t *p = CFM_MEM(CFM_WB0 + k * CFM_WB_STEP);
                uint32_t sum = 0, any = 0;
                for (j = 0; j < CFM_SUM_WORDS; j++) {
                    uint32_t v = p[j];
                    sum = (sum << 1 | sum >> 31) ^ v;
                    any |= v;
                }
                if (s->page > 1 && sum != s->sum[k]) changed |= 1u << k;
                if (!any) zero |= 1u << k;
                s->sum[k] = sum;
            }
            w[1] = 0x43464d31u;      /* 'CFM1' */
            w[2] = changed; w[3] = zero;
            w[4] = CFM_KNOB(coef, SH_PARAM_MODE) << 24 | CFM_KNOB(coef, SH_PARAM_GAIN) << 16 |
                   CFM_KNOB(coef, SH_PARAM_P3) << 8 | CFM_KNOB(coef, SH_PARAM_P4);
            w[5] = CFM_KNOB(coef, SH_PARAM_P5) << 24 | CFM_KNOB(coef, SH_PARAM_P6) << 16 |
                   CFM_KNOB(coef, SH_PARAM_P7) << 8 | CFM_KNOB(coef, SH_PARAM_P8);
            w[6] = CFM_KNOB(coef, SH_PARAM_P9) << 24 | CFM_KNOB(coef, SH_PARAM_P10) << 16 |
                   CFM_KNOB(coef, SH_PARAM_P11) << 8 | CFM_KNOB(coef, SH_PARAM_P12);
            w[7] = s->sum[0]; w[8] = s->sum[1]; w[9] = s->sum[2]; w[10] = s->sum[3];
        }
        s->page++;
        MP_FSK_SEAL(&s->fsk);
    }
    MP_FSK_BLOCK(&s->fsk, eff, 0.25f, fade);
}
