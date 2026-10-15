// Checks the generated straight-line tone-stack derivation
// (effects/common/hiwatt_stackgen.h, tools/gen_hw_stack.py) against the
// generic derivation mna_derive(hw_stack(...)) it replaces, both against a
// double-precision mna_derive: H of the discrete systems, 20 Hz..20 kHz, at 4x
// of 44.1 kHz, over a knob grid that includes the pot ends (20-ohm wiper floor).
//
// Pass: in band (within 20 dB of the response peak) |dH| < 0.01 dB, and the
// complex error relative to the peak < -70 dB everywhere (the float
// mna_derive it replaces reaches -60 dB). A dB error
// far below the peak is not a criterion: at bass 0 the 20-ohm floor puts the
// two 47n caps nearly in parallel (a sub-microsecond mode), and the deep
// 20 Hz cut there carries float noise at -90 dB re peak in either derivation.
// HW_SG_LIST=1 lists knob sets whose worst dB error anywhere exceeds 0.01 dB.
// Exit 1 on failure.
#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdio>
#include <cstdlib>
extern "C" {
#define MNA_MAXN 10
#define MNA_MAXU 1
#include "../../effects/common/hiwatt_stackgen.h"
}

void stack_ref_d(double t, double m, double b, double v, double fs, double* out);
void stack_gen_d(double t, double m, double b, double v, double fs, double* out);

using cd = std::complex<double>;
static const double PI = 3.14159265358979323846;
static const int K = 5;

// H(z) of the packed delta-form system: x[n] = (I + dA) x[n-1] + dB (u[n] + u[n-1])
template <class R>
static cd resp(const R* p, double f, double fs)
{
    cd z = std::polar(1.0, 2 * PI * f / fs), a[K][K + 1];
    for (int i = 0; i < K; ++i) {
        for (int j = 0; j < K; ++j)
            a[i][j] = (i == j ? z : cd(0)) - ((i == j ? 1.0 : 0.0) + (double)MNA_DA(p, K, 1, i, j));
        a[i][K] = (double)MNA_DB(p, K, 1, i, 0) * (z + 1.0);
    }
    for (int k = 0; k < K; ++k) {                      // complex Gauss, partial pivoting
        int piv = k;
        for (int i = k + 1; i < K; ++i) if (std::abs(a[i][k]) > std::abs(a[piv][k])) piv = i;
        for (int j = 0; j <= K; ++j) std::swap(a[k][j], a[piv][j]);
        for (int i = k + 1; i < K; ++i) {
            cd fct = a[i][k] / a[k][k];
            for (int j = k; j <= K; ++j) a[i][j] -= fct * a[k][j];
        }
    }
    cd x[K];
    for (int k = K - 1; k >= 0; --k) {
        cd acc = a[k][K];
        for (int j = k + 1; j < K; ++j) acc -= a[k][j] * x[j];
        x[k] = acc / a[k][k];
    }
    cd y = (double)MNA_DY(p, K, 1, 0);
    for (int i = 0; i < K; ++i) y += (double)MNA_CY(p, K, 1, i) * x[i];
    return y;
}

static double db(double r) { return 20 * std::log10(r + 1e-30); }

int main()
{
    const double fs = 4 * 44100.0;
    const float g[] = { 0.0f, 0.01f, 0.1f, 0.25f, 0.5f, 0.75f, 0.9f, 0.99f, 1.0f };
    const int ng = sizeof g / sizeof g[0];
    const bool list = std::getenv("HW_SG_LIST") != nullptr;
    double genD = 0, inG = 0, inR = 0, absG = 0, absR = 0;
    int n = 0;
    for (int it = 0; it < ng; ++it)
        for (int im = 0; im < ng; ++im)
            for (int ib = 0; ib < ng; ++ib)
                for (int iv = 0; iv < ng; iv += 2) {
                    const float t = g[it], m = g[im], b = g[ib], v = g[iv];
                    float pr[MNA_SS_SIZE(5, 1)], pg[MNA_SS_SIZE(5, 1)];
                    double pd[MNA_SS_SIZE(5, 1)], pgd[MNA_SS_SIZE(5, 1)];
                    MnaNet net;
                    float w[MNA_MAXN];
                    hw_stack(&net, w, t, m, b, v);
                    mna_derive(&net, w, (float)fs, pr);
                    hw_stack_derive(t, m, b, v, (float)fs, pg);
                    stack_ref_d(t, m, b, v, fs, pd);
                    stack_gen_d(t, m, b, v, fs, pgd);
                    double peak = 0, anyG = 0;
                    for (double f = 20; f <= 20000; f *= 1.05) peak = std::max(peak, std::abs(resp(pd, f, fs)));
                    ++n;
                    if (peak < 1e-6) continue;             // master at 0: below -120 dB
                    for (double f = 20; f <= 20000; f *= 1.05) {
                        const cd hd = resp(pd, f, fs), hg = resp(pg, f, fs), hr = resp(pr, f, fs);
                        const cd hgd = resp(pgd, f, fs);
                        const double ad = std::abs(hd);
                        genD = std::max(genD, std::abs(hgd - hd) / peak);
                        absG = std::max(absG, std::abs(hg - hd) / peak);
                        absR = std::max(absR, std::abs(hr - hd) / peak);
                        const double dg = std::fabs(db(std::abs(hg) / ad)), dr = std::fabs(db(std::abs(hr) / ad));
                        anyG = std::max(anyG, dg);
                        if (ad > 0.1 * peak) {
                            inG = std::max(inG, dg);
                            inR = std::max(inR, dr);
                        }
                    }
                    if (list && anyG > 0.01)
                        std::printf("  t %.2f m %.2f b %.2f v %.2f: %.4f dB\n", t, m, b, v, anyG);
                }
    std::printf("stack derivations vs double mna_derive, %d knob sets, 4x:\n", n);
    std::printf("  generated, double: complex error %.1f dB re peak (algebra check)\n", db(genD));
    std::printf("  generated, float:  in band %.5f dB, complex error %.1f dB re peak\n", inG, db(absG));
    std::printf("  mna_derive, float: in band %.5f dB, complex error %.1f dB re peak\n", inR, db(absR));
    const bool ok = genD < 1e-6 && inG < 0.01 && absG < 3.16e-4;   // -70 dB; mna_derive float: -60
    std::printf("%s\n", ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
}
