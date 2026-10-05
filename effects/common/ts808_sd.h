/* ts808_sd.h - TS808 clipping stage with a real diode pair, for the Zoom G1 Four.
 *
 * Same circuit as ts808_core.h (Comet Flower DriveMobileCore), with the
 * clipping stage solved from the component physics instead of a fixed
 * piecewise clipper:
 *
 *   feedback node:  v/Rf + C4 dv/dt + 2 Is sinh(v / (n Vt)) = i_g
 *   ground leg:     i_g = current through R4 + C3 (the 720 Hz split)
 *   output:         Vout = Vin + v
 *
 * D1/D2: 1N4148/MA150-class silicon, Is = 2.52 nA, n = 1.752 (SPICE 1N4148).
 * Rf = R6 + P1 = 51k + 500k * wiper^2 (audio taper, as in the original).
 *
 * Two solvers:
 *   SD_MODE_ADAA  memoryless diode stage (C4 as a following softening pole,
 *                 exactly like ts808_core.h) with first-order ADAA. The
 *                 antiderivative is exact once v(u) is solved:
 *                   F(u) = u v - v^2/2 - 2 Is Rf nVt cosh(v / nVt)
 *   SD_MODE_FULL  C4 inside the implicit equation (trapezoidal companion),
 *                 no ADAA; relies on oversampling.
 *
 * Call-free: exp via range reduction and bit assembly, reciprocals via
 * ts_rcp() (RCPSP seed + Newton) from ts808_core.h.
 */
#ifndef TS808_SD_H
#define TS808_SD_H

#include "ts808_core.h"

#define SD_IS    2.52e-9f
#define SD_NVT   (1.752f * 0.025852f)          /* n * Vt at ~27 C */
#define SD_INVNVT (1.0f / (1.752f * 0.025852f))
#define SD_C4    51.0e-12f
#define SD_R4    4700.0f
#define SD_C3    47.0e-9f

/* exp(x) for x in about [-80, 80], float, no calls. */
TS_INLINE float sd_expf(float x)
{
    union { float f; unsigned u; } s;
    float kf, r, p;
    int k;
    if (x > 80.0f) x = 80.0f;
    if (x < -80.0f) x = -80.0f;
    kf = x * 1.44269504f;
    k = (int)(kf + (kf >= 0.0f ? 0.5f : -0.5f));
    r = x - (float)k * 0.693145752f - (float)k * 1.42860677e-06f;
    p = 1.0f + r * (1.0f + r * (0.5f + r * (1.0f/6 + r * (1.0f/24
        + r * (1.0f/120 + r * (1.0f/720 + r * (1.0f/5040)))))));
    s.u = (unsigned)(k + 127) << 23;
    return p * s.f;
}

/* Solve v + a * sinh(v * b) = u for v, warm-started at v0.
 * a = 2 Is Rf (or 2 Is / g for the full form), b = 1/nVt.
 * Fixed iteration count (deterministic CPU), step limited for robustness. */
#ifndef SD_ITERS
#define SD_ITERS 4
#endif
TS_INLINE float sd_solve(float u, float a, float b, float v0, float lin)
{
    float v = v0;
    int it;
    for (it = 0; it < SD_ITERS; ++it) {
        float e = sd_expf(v * b), ei = sd_expf(-v * b);
        float f = lin * v + a * 0.5f * (e - ei) - u;
        float df = lin + a * b * 0.5f * (e + ei);
        float step = f * ts_rcp(df);
        if (step > 0.1f) step = 0.1f;
        if (step < -0.1f) step = -0.1f;
        v -= step;
    }
    return v;
}

#endif /* TS808_SD_H */
