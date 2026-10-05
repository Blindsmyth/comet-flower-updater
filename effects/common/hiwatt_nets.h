/* hiwatt_nets.h - the Hiwatt DR103 (1971, #2130) linear networks for the G1,
 * as mna_ss.h capacitor-state systems.
 *
 * Netlists and values are Comet Flower's HiwattDR103Processor.cpp
 * (buildV1Net / buildStackNet / buildBackHalf, sources [HUSS]/[AB]/[RCA]/
 * [DS81] cited there), unchanged except that the stray capacitors the desktop
 * adds to make its MNA C matrix full rank are left out: here only the real
 * capacitors are states, so no strays are needed. Host check against the
 * desktop builders: tests/host/hiwatt_nets_test.cpp.
 *
 * Inputs and outputs (all volts):
 *   V1 net:    u = mu * V1 grid            -> V2 grid           (2 states)
 *   stack:     u = mu * V2 grid            -> master wiper      (5 states)
 *   back half: u0 = V3a grid, u1 = NFB residual -> PI grid a - grid b (5 states)
 * The back half closes the linear NFB loop implicitly (controlled source on
 * node N), exactly as the desktop does.
 */
#ifndef HIWATT_NETS_H
#define HIWATT_NETS_H

#include "mna_ss.h"

#define HW_MU3    100.0f
#define HW_RA3    62.5e3f
#define HW_GM3    (HW_MU3 / HW_RA3)
#define HW_MU4    60.0f
#define HW_RA4    10.9e3f
#define HW_RWIPR  20.0f
/* small-signal 16-ohm tap volts per PI diff-grid volt (LTP inverts grid a) */
#define HW_KTAPLIN (-56.57f * 48.5f / (2.0f * 38.0f))
#define HW_KLOOP   (-HW_KTAPLIN)                    /* POL_NFB (-1) * KTAPLIN */

/* 470k-A / 220k-A audio taper, the desktop's model: (81^x - 1) / 80,
 * 10 % of the track at half rotation. exp by (Taylor of e^(y/16))^16. */
MNA_INLINE float hw_atap(float x)
{
    float y, e;
    x = x < 0.0f ? 0.0f : (x > 1.0f ? 1.0f : x);
    y = x * (4.394449155f / 16.0f);                 /* ln 81 / 16 */
    e = 1.0f + y * (1.0f + y * (0.5f + y * (1.0f / 6 + y * (1.0f / 24
        + y * (1.0f / 120 + y * (1.0f / 720 + y * (1.0f / 5040)))))));
    e = e * e; e = e * e; e = e * e; e = e * e;
    return (e - 1.0f) * (1.0f / 80.0f);
}

MNA_INLINE float hw_maxf(float a, float b) { return a > b ? a : b; }

/* V1 stage: plate source ra + (mu+1)(2k2 || 47n), 220k load, 22n coupling,
 * 470k-A volume, 470k mixer and idle-channel leg. Output: V2 grid. */
MNA_INLINE void hw_v1net(MnaNet *m, float *w, float vol01)
{
    enum { P = 0, T, W, G2, M };
    float a = hw_atap(vol01);
    int i;
    mna_init(m, 5, 1);
    mna_r(m, M, -1, HW_RA3);
    mna_b(m, M, 0, 1.0f / HW_RA3);
    mna_r(m, M, P, (HW_MU3 + 1.0f) * 2.2e3f);
    mna_c(m, M, P, 47e-9f / (HW_MU3 + 1.0f));
    mna_r(m, P, -1, 220e3f);
    mna_c(m, P, T, 22e-9f);
    mna_r(m, T, W, hw_maxf((1.0f - a) * 470e3f, HW_RWIPR));
    mna_r(m, W, -1, hw_maxf(a * 470e3f, HW_RWIPR));
    mna_r(m, W, G2, 470e3f);
    mna_r(m, G2, -1, 470e3f);
    for (i = 0; i < MNA_MAXN; ++i) w[i] = 0.0f;
    w[G2] = 1.0f;
}

/* Tone stack + master. t, m, b, mv in 0..1 (treble/middle LIN, bass/master
 * audio taper). Output: master wiper. */
MNA_INLINE void hw_stack(MnaNet *n, float *w, float t, float mid, float b, float mv)
{
    enum { IN = 0, A, B_, D, Cn, E, OUT, F, Gn, K };
    float lo = hw_atap(mv);
    int i;
    mna_init(n, 10, 1);
    mna_r(n, IN, -1, HW_RA3 + (HW_MU3 + 1.0f) * 2.2e3f);
    mna_b(n, IN, 0, 1.0f / (HW_RA3 + (HW_MU3 + 1.0f) * 2.2e3f));
    mna_r(n, IN, -1, 220e3f);
    mna_c(n, IN, A, 1e-9f);
    mna_c(n, A, B_, 220e-12f);
    mna_r(n, A, Cn, 220e3f);
    mna_r(n, B_, D, hw_maxf((1.0f - t) * 220e3f, HW_RWIPR));
    mna_r(n, D, Cn, hw_maxf(t * 220e3f, HW_RWIPR));
    mna_r(n, D, E, 22e3f);
    mna_r(n, E, OUT, hw_maxf((1.0f - lo) * 220e3f, HW_RWIPR));
    mna_r(n, OUT, -1, hw_maxf(lo * 220e3f, HW_RWIPR));
    mna_r(n, Cn, F, 22e3f);
    mna_r(n, F, Gn, hw_maxf(mid * 100e3f, HW_RWIPR));
    mna_c(n, F, Gn, 1e-9f);
    mna_r(n, Gn, -1, hw_maxf(hw_atap(b) * 470e3f, HW_RWIPR));
    mna_r(n, IN, K, 100e3f);
    mna_c(n, K, Gn, 47e-9f);
    mna_c(n, K, -1, 47e-9f);
    for (i = 0; i < MNA_MAXN; ++i) w[i] = 0.0f;
    w[OUT] = 1.0f;
}

/* V3a + cathode follower + presence + NFB divider + PI cathode folds, with
 * the linear NFB loop closed in the network. Output: PI grid a - grid b. */
MNA_INLINE void hw_backhalf(MnaNet *n, float *w, float pres01)
{
    enum { K3 = 0, P3, GB3, KB3, P1, W, P2, N, X, M, KT };
    const float gra = 1.0f / HW_RA3;
    float x = pres01 < 0.0f ? 0.0f : (pres01 > 1.0f ? 1.0f : pres01);
    int i;
    mna_init(n, 11, 2);
    /* V3a: plate current gm (u0 - vK3) + (vP3 - vK3)/ra */
    mna_b(n, P3, 0, -HW_GM3);
    mna_b(n, K3, 0, HW_GM3);
    mna_g(n, P3, K3, -HW_GM3);
    mna_g(n, P3, K3, -gra);
    mna_g(n, P3, P3, gra);
    mna_g(n, K3, K3, HW_GM3);
    mna_g(n, K3, P3, -gra);
    mna_g(n, K3, K3, gra);
    mna_r(n, K3, -1, 2.2e3f);
    mna_c(n, K3, -1, 47e-9f);
    mna_r(n, P3, -1, 100e3f);
    /* 22n || 1M8 to the CF grid, 1M grid leak */
    mna_c(n, P3, GB3, 22e-9f);
    mna_r(n, P3, GB3, 1.8e6f);
    mna_r(n, GB3, -1, 1.0e6f);
    /* V3b cathode follower */
    mna_g(n, KB3, GB3, -HW_GM3);
    mna_g(n, KB3, KB3, HW_GM3 + gra);
    mna_r(n, KB3, -1, 100e3f);
    /* presence: plate -1n- P1, 100k LIN P1..W..P2, wiper -100R- gnd, P2 -47n- N */
    mna_c(n, P3, P1, 1e-9f);
    mna_r(n, P1, W, hw_maxf(x * 100e3f, 1.0f));
    mna_r(n, W, P2, hw_maxf((1.0f - x) * 100e3f, 1.0f));
    mna_r(n, W, -1, 100.0f);
    mna_c(n, P2, N, 47e-9f);
    /* NFB node: tap through 10k (u1 = residual), 470R + 10n shelf, 2k2 to M */
    mna_r(n, N, -1, 10e3f);
    mna_b(n, N, 1, 1.0f / 10e3f);
    mna_r(n, N, X, 470.0f);
    mna_c(n, X, -1, 10e-9f);
    mna_r(n, N, M, 2.2e3f);
    mna_r(n, M, KT, 22e3f);
    mna_r(n, KB3, KT, 1.0e6f);
    /* PI cathode folds (V4a grid = KB3, V4b grid = M), ECC81 */
    mna_g(n, KT, KT, (HW_MU4 + 1.0f) / (HW_RA4 + 82e3f));
    mna_g(n, KT, KB3, -HW_MU4 / (HW_RA4 + 82e3f));
    mna_g(n, KT, KT, (HW_MU4 + 1.0f) / (HW_RA4 + 91e3f));
    mna_g(n, KT, M, -HW_MU4 / (HW_RA4 + 91e3f));
    /* implicit linear NFB: u_lin = KLOOP (vKB3 - vM) through the 10k */
    mna_g(n, N, KB3, -HW_KLOOP / 10e3f);
    mna_g(n, N, M, HW_KLOOP / 10e3f);
    for (i = 0; i < MNA_MAXN; ++i) w[i] = 0.0f;
    w[KB3] = 1.0f;
    w[M] = -1.0f;
}

#endif /* HIWATT_NETS_H */
