/* mna_ss.h - linear RC networks with controlled sources as capacitor-state
 * state space, derived in float at control rate, run per sample in delta form.
 *
 * Why: the desktop amp models (Comet Flower HiwattDR103Processor) solve each
 * network as an N-node MNA recursion in double, with stray capacitors added so
 * the C matrix is full rank. On the G1 the same networks run as K-state systems
 * with only the real capacitors as states (K <= 5, against N <= 11 nodes):
 * the strays cost <= 0.15 dB near 20 kHz, the trapezoidal discretisation
 * matches the analog response within 0.03 dB below 5 kHz at 4x, and the
 * float recursion in delta form stays within -108 dB of double
 * (scratch study 2026-10-05; tests/host/mna_ss_test.cpp checks the C code).
 *
 * Units inside: conductances in uS, currents in uA, capacitors in nF; that
 * keeps the float Gauss solves well scaled (<= 0.005 dB vs double).
 *
 * Derivation, with E the capacitor incidence (+1 at ci, -1 at cj):
 *   G v + E i = B u,  E^T v = x  (x = capacitor voltages, i = their currents)
 *   Zx = G^-1 E, Zu = G^-1 B, S = E^T Zx, T = E^T Zu
 *   i = S^-1 (T u - x),  dx/dt = D i  (D = 1/C)
 *   y = w^T v = (w^T Zx S^-1) x + (w^T Zu - w^T Zx S^-1 T) u
 * Trapezoidal (bilinear), delta form with h = T/2:
 *   x[n] = x[n-1] + dA x[n-1] + dB (u[n] + u[n-1]),  y[n] = cy x[n] + dy u[n]
 *   (I - hA) [dA | dB] = [2hA | hB]
 * G must be invertible: every node needs a DC path (true for the Hiwatt nets).
 * Layout: one shared array for the net and the scratch (see MnaNet), and a
 * packed output, so that the derivation fits a small stack frame.
 */
#ifndef MNA_SS_H
#define MNA_SS_H

/* Scratch sizes; a build that derives only smaller nets may lower them
 * (the DR103 kernel: 10 nodes, 1 input, to keep its stack frame small). */
#ifndef MNA_MAXN
#define MNA_MAXN 11
#endif
#define MNA_MAXK 5
#ifndef MNA_MAXU
#define MNA_MAXU 2
#endif
#define MNA_W    (MNA_MAXN + MNA_MAXK + MNA_MAXU)   /* row: [G | E | B] */

/* The net and all derivation scratch share one array, to keep the audio
 * kernel's stack frame within the stock G1 precedent (<= 1.5 KB):
 * columns 0..N-1 hold G (destroyed by the solve), N..N+K-1 the capacitor
 * incidence E, N+K.. the inputs B; after the solve those columns hold
 * [Zx | Zu], and rows 0..4 / 5..9 of the dead G area hold S and [S^-1 | S^-1 T]. */
typedef struct {
    float a[MNA_MAXN][MNA_W];
    float c[MNA_MAXK];                  /* nF */
    signed char ci[MNA_MAXK], cj[MNA_MAXK];
    int n, k, nu;
} MnaNet;

/* Packed discrete system of k states, nu inputs (mna_derive writes it):
 *   [dA k*k][dB k*nu][cy k][dy nu] */
#define MNA_SS_SIZE(k, nu)   ((k) * (k) + (k) * (nu) + (k) + (nu))
#define MNA_DA(p, k, nu, i, j) ((p)[(i) * (k) + (j)])
#define MNA_DB(p, k, nu, i, u) ((p)[(k) * (k) + (i) * (nu) + (u)])
#define MNA_CY(p, k, nu, i)    ((p)[(k) * (k) + (k) * (nu) + (i)])
#define MNA_DY(p, k, nu, u)    ((p)[(k) * (k) + (k) * (nu) + (k) + (u)])

#ifndef MNA_INLINE
#  if defined(__TI_COMPILER_VERSION__) || defined(__GNUC__)
     /* always inline: stomphacks rejects any CALL in the audio kernel */
#    define MNA_INLINE static inline __attribute__((always_inline))
#  elif defined(_MSC_VER)
#    define MNA_INLINE static __inline
#  else
#    define MNA_INLINE static
#  endif
#endif

MNA_INLINE void mna_init(MnaNet *m, int n, int nu)
{
    int i, j;
    for (i = 0; i < MNA_MAXN; ++i)
        for (j = 0; j < MNA_W; ++j) m->a[i][j] = 0.0f;
    m->n = n; m->k = 0; m->nu = nu;
}

/* 1/x without a library call (C6x float division is an RTS call; DIY kernels
 * must stay leaf): RCPSP seed + two Newton steps, full float precision. */
#if defined(__TI_COMPILER_VERSION__)
#include <c6x.h>
MNA_INLINE float mna_rcp(float x)
{
    float r = _rcpsp(x);
    r = r * (2.0f - x * r);
    return r * (2.0f - x * r);
}
#else
MNA_INLINE float mna_rcp(float x) { return 1.0f / x; }
#endif

/* resistor between nodes i and j (-1 = ground), ohms */
MNA_INLINE void mna_r(MnaNet *m, int i, int j, float ohms)
{
    float g = 1.0e6f * mna_rcp(ohms);
    if (i >= 0) m->a[i][i] += g;
    if (j >= 0) m->a[j][j] += g;
    if (i >= 0 && j >= 0) { m->a[i][j] -= g; m->a[j][i] -= g; }
}

/* raw conductance-matrix entry (controlled sources), siemens */
MNA_INLINE void mna_g(MnaNet *m, int row, int col, float siemens)
{
    m->a[row][col] += siemens * 1.0e6f;
}

/* input column: current siemens * u injected into node */
MNA_INLINE void mna_b(MnaNet *m, int node, int col, float siemens)
{
    m->a[node][MNA_MAXN + MNA_MAXK + col] += siemens * 1.0e6f;
}

/* capacitor (a state) between nodes i and j (-1 = ground), farads */
MNA_INLINE void mna_c(MnaNet *m, int i, int j, float farads)
{
    if (i >= 0) m->a[i][MNA_MAXN + m->k] = 1.0f;
    if (j >= 0) m->a[j][MNA_MAXN + m->k] = -1.0f;
    m->ci[m->k] = (signed char)i;
    m->cj[m->k] = (signed char)j;
    m->c[m->k] = farads * 1.0e9f;
    m->k++;
}

/* Solve A X = R in place (A n x n, R n x nr, row strides la / lr), partial
 * pivoting. A is destroyed; X replaces R. */
MNA_INLINE void mna_gauss(float *a, int la, float *r, int lr, int n, int nr)
{
    int i, j, k, p;
    for (k = 0; k < n; ++k) {
        float amax = a[k * la + k] < 0.0f ? -a[k * la + k] : a[k * la + k], inv;
        p = k;
        for (i = k + 1; i < n; ++i) {
            float v = a[i * la + k] < 0.0f ? -a[i * la + k] : a[i * la + k];
            if (v > amax) { amax = v; p = i; }
        }
        if (p != k) {
            for (j = 0; j < n; ++j) { float t = a[k * la + j]; a[k * la + j] = a[p * la + j]; a[p * la + j] = t; }
            for (j = 0; j < nr; ++j) { float t = r[k * lr + j]; r[k * lr + j] = r[p * lr + j]; r[p * lr + j] = t; }
        }
        inv = mna_rcp(a[k * la + k]);
        for (i = k + 1; i < n; ++i) {
            float f = a[i * la + k] * inv;
            for (j = k; j < n; ++j) a[i * la + j] -= f * a[k * la + j];
            for (j = 0; j < nr; ++j) r[i * lr + j] -= f * r[k * lr + j];
        }
    }
    for (k = n - 1; k >= 0; --k) {
        float inv = mna_rcp(a[k * la + k]);
        for (j = 0; j < nr; ++j) {
            float acc = r[k * lr + j];
            for (i = k + 1; i < n; ++i) acc -= a[k * la + i] * r[i * lr + j];
            r[k * lr + j] = acc * inv;
        }
    }
}

/* Derive the packed discrete system (MNA_SS_SIZE(k, nu) floats) at sample
 * rate fs. w = output weights per node (y = sum w[n] v[n]). m is destroyed. */
MNA_INLINE void mna_derive(MnaNet *m, const float *w, float fs, float *out)
{
#define Z(i, j)  m->a[i][MNA_MAXN + (j)]          /* [Zx | Zu], Zu at j >= MAXK */
#define SM(i, j) m->a[i][j]                       /* S, then I - hA */
#define Q(i, j)  m->a[5 + (i)][j]                 /* [S^-1 | S^-1 T], then [dA | dB] */
    float wz[MNA_MAXK + MNA_MAXU];
    float h = 0.5f * mna_rcp(fs);
    int n = m->n, k = m->k, nu = m->nu, i, j, l;
    const int R = MNA_MAXK + MNA_MAXU;            /* rhs width: E (padded) + B */

    /* three solves through one mna_gauss site (code size: one inlined copy):
     * pass 0: G [Zx | Zu] = [E | B]; pass 1: S [S^-1 | S^-1 T] = [I | T];
     * pass 2: (I - hA) [dA | dB] = [2hA | hB] */
    int pass;
    for (pass = 0; pass < 3; ++pass) {
        if (pass == 1) {
            for (j = 0; j < R; ++j) {             /* w^T [Zx | Zu], before G area reuse */
                float acc = 0.0f;
                for (i = 0; i < n; ++i) acc += w[i] * Z(i, j);
                wz[j] = acc;
            }
            /* S = E^T Zx, T = E^T Zu; Q starts as [I | T]. Rows 0..4 / 5..9 of
             * the G area are dead after the solve (n >= 10 whenever k = 5; the
             * V1 net, k = 2, n = 5, uses rows 0..1 / 5..6, inside a[MAXN]). */
            for (i = 0; i < k; ++i) {
                int ca = m->ci[i], cb = m->cj[i];
                for (j = 0; j < k; ++j) {
                    SM(i, j) = (ca >= 0 ? Z(ca, j) : 0.0f) - (cb >= 0 ? Z(cb, j) : 0.0f);
                    Q(i, j) = (i == j) ? 1.0f : 0.0f;
                }
                for (j = 0; j < nu; ++j)
                    Q(i, k + j) = (ca >= 0 ? Z(ca, MNA_MAXK + j) : 0.0f)
                                - (cb >= 0 ? Z(cb, MNA_MAXK + j) : 0.0f);
            }
        } else if (pass == 2) {
            for (j = 0; j < k; ++j) {             /* cy = w^T Zx S^-1 */
                float acc = 0.0f;
                for (l = 0; l < k; ++l) acc += wz[l] * Q(l, j);
                MNA_CY(out, k, nu, j) = acc;
            }
            for (j = 0; j < nu; ++j) {            /* dy = w^T Zu - w^T Zx S^-1 T */
                float acc = wz[MNA_MAXK + j];
                for (l = 0; l < k; ++l) acc -= wz[l] * Q(l, k + j);
                MNA_DY(out, k, nu, j) = acc;
            }
            /* A = -D S^-1, B = D S^-1 T, D = 1e3/C[nF] (uA/nF -> V/s) */
            for (i = 0; i < k; ++i) {
                float hd = h * 1.0e3f * mna_rcp(m->c[i]);
                for (j = 0; j < k; ++j) {
                    float ha = -hd * Q(i, j);
                    SM(i, j) = (i == j ? 1.0f : 0.0f) - ha;
                    Q(i, j) = 2.0f * ha;
                }
                for (j = 0; j < nu; ++j) Q(i, k + j) *= hd;
            }
        }
        if (pass == 0)
            mna_gauss(&m->a[0][0], MNA_W, &m->a[0][MNA_MAXN], MNA_W, n, R);
        else
            mna_gauss(&SM(0, 0), MNA_W, &Q(0, 0), MNA_W, k, k + nu);
    }
    for (i = 0; i < k; ++i) {
        for (j = 0; j < k; ++j) MNA_DA(out, k, nu, i, j) = Q(i, j);
        for (j = 0; j < nu; ++j) MNA_DB(out, k, nu, i, j) = Q(i, k + j);
    }
#undef Z
#undef SM
#undef Q
}

#endif /* MNA_SS_H */
