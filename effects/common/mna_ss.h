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
 */
#ifndef MNA_SS_H
#define MNA_SS_H

#define MNA_MAXN 11
#define MNA_MAXK 5
#define MNA_MAXU 2

typedef struct {
    float g[MNA_MAXN][MNA_MAXN];        /* uS */
    float b[MNA_MAXN][MNA_MAXU];        /* uS (input volts -> injected uA) */
    float c[MNA_MAXK];                  /* nF */
    signed char ci[MNA_MAXK], cj[MNA_MAXK];
    int n, k, nu;
} MnaNet;

typedef struct {
    float da[MNA_MAXK][MNA_MAXK];
    float db[MNA_MAXK][MNA_MAXU];
    float cy[MNA_MAXK];
    float dy[MNA_MAXU];
} MnaSS;

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
    for (i = 0; i < MNA_MAXN; ++i) {
        for (j = 0; j < MNA_MAXN; ++j) m->g[i][j] = 0.0f;
        for (j = 0; j < MNA_MAXU; ++j) m->b[i][j] = 0.0f;
    }
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
    if (i >= 0) m->g[i][i] += g;
    if (j >= 0) m->g[j][j] += g;
    if (i >= 0 && j >= 0) { m->g[i][j] -= g; m->g[j][i] -= g; }
}

/* raw conductance-matrix entry (controlled sources), siemens */
MNA_INLINE void mna_g(MnaNet *m, int row, int col, float siemens)
{
    m->g[row][col] += siemens * 1.0e6f;
}

/* input column: current siemens * u injected into node */
MNA_INLINE void mna_b(MnaNet *m, int node, int col, float siemens)
{
    m->b[node][col] += siemens * 1.0e6f;
}

/* capacitor (a state) between nodes i and j (-1 = ground), farads */
MNA_INLINE void mna_c(MnaNet *m, int i, int j, float farads)
{
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

/* Derive the discrete system at sample rate fs. w = output weights per node
 * (y = sum w[n] v[n]). m->g is destroyed. */
MNA_INLINE void mna_derive(MnaNet *m, const float *w, float fs, MnaSS *s)
{
    float z[MNA_MAXN][MNA_MAXK + MNA_MAXU];   /* [Zx | Zu] */
    float sm[MNA_MAXK][MNA_MAXK];             /* S, then I - hA */
    float q[MNA_MAXK][MNA_MAXK + MNA_MAXU];   /* [S^-1 | S^-1 T], then [dA | dB] */
    float wz[MNA_MAXK + MNA_MAXU];            /* w^T [Zx | Zu] */
    float h = 0.5f * mna_rcp(fs);
    int n = m->n, k = m->k, nu = m->nu, i, j, l;

    for (i = 0; i < n; ++i) {
        for (j = 0; j < k; ++j)
            z[i][j] = (m->ci[j] == i ? 1.0f : 0.0f) - (m->cj[j] == i ? 1.0f : 0.0f);
        for (j = 0; j < nu; ++j) z[i][k + j] = m->b[i][j];
    }
    mna_gauss(&m->g[0][0], MNA_MAXN, &z[0][0], MNA_MAXK + MNA_MAXU, n, k + nu);

    /* [S | T] = E^T [Zx | Zu]; q starts as [I | T] */
    for (i = 0; i < k; ++i) {
        int a = m->ci[i], c = m->cj[i];
        for (j = 0; j < k + nu; ++j) {
            float v = (a >= 0 ? z[a][j] : 0.0f) - (c >= 0 ? z[c][j] : 0.0f);
            if (j < k) { sm[i][j] = v; q[i][j] = (i == j) ? 1.0f : 0.0f; }
            else q[i][j] = v;
        }
    }
    mna_gauss(&sm[0][0], MNA_MAXK, &q[0][0], MNA_MAXK + MNA_MAXU, k, k + nu);

    for (j = 0; j < k + nu; ++j) {
        float acc = 0.0f;
        for (i = 0; i < n; ++i) acc += w[i] * z[i][j];
        wz[j] = acc;
    }
    for (j = 0; j < k; ++j) {               /* cy = w^T Zx S^-1 */
        float acc = 0.0f;
        for (l = 0; l < k; ++l) acc += wz[l] * q[l][j];
        s->cy[j] = acc;
    }
    for (j = 0; j < nu; ++j) {              /* dy = w^T Zu - w^T Zx S^-1 T */
        float acc = wz[k + j];
        for (l = 0; l < k; ++l) acc -= wz[l] * q[l][k + j];
        s->dy[j] = acc;
    }

    /* A = -D S^-1, B = D S^-1 T with D = 1e3/C[nF] (uA/nF -> V/s);
     * then (I - hA) [dA | dB] = [2hA | hB] */
    for (i = 0; i < k; ++i) {
        float hd = h * 1.0e3f * mna_rcp(m->c[i]);
        for (j = 0; j < k; ++j) {
            float ha = -hd * q[i][j];
            sm[i][j] = (i == j ? 1.0f : 0.0f) - ha;
            q[i][j] = 2.0f * ha;
        }
        for (j = 0; j < nu; ++j) q[i][k + j] *= hd;
    }
    mna_gauss(&sm[0][0], MNA_MAXK, &q[0][0], MNA_MAXK + MNA_MAXU, k, k + nu);
    for (i = 0; i < k; ++i) {
        for (j = 0; j < k; ++j) s->da[i][j] = q[i][j];
        for (j = 0; j < nu; ++j) s->db[i][j] = q[i][k + j];
    }
}

#endif /* MNA_SS_H */
