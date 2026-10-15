// Checks the generated straight-line network derivations
// (effects/common/hiwatt_netgen.h, tools/gen_hw_nets.py) against a
// double-precision mna_derive of the hiwatt_nets.h builders, and reports the
// float mna_derive they replace on the same metrics: H of each input of the
// discrete systems, 20 Hz..20 kHz, at 4x of 44.1 kHz.
//   tone stack: a knob grid with the pot ends (20-ohm wiper floor)
//   V1 net, back half: every G1 knob position 0..100, plus smoothing fractions
//
// Pass, per network: in band (within 20 dB of the response peak) |dH| <
// 0.01 dB, and complex error re peak < -70 dB (the float mna_derive reaches
// -60 dB on the stack). A dB error far below the peak is not a criterion: at
// bass 0 the 20-ohm floor puts the stack's two 47n caps nearly in parallel,
// and its deep 20 Hz cut carries float noise in either derivation.
// The double build of the generated code (algebra check) must agree within
// -100 dB re peak (its constants are float literals). Exit 1 on failure.
#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdio>
#include <vector>
extern "C" {
#define MNA_MAXN 11
#define MNA_MAXU 2
#include "../../effects/common/hiwatt_netgen.h"
}

// double builds (hiwatt_netgen_dbl.cpp, /Dfloat=double): net 0 stack, 1 V1, 2 back half
void net_ref_d(int net, const double* kn, double fs, double* out);
void net_gen_d(int net, const double* kn, double fs, double* out);

using cd = std::complex<double>;
static const double PI = 3.14159265358979323846;
static const double FS = 4 * 44100.0;
static const int KS[3] = { 5, 2, 5 }, NUS[3] = { 1, 1, 2 };

template <class R>
static cd resp(const R* p, int k, int nu, int u, double f)
{
    cd z = std::polar(1.0, 2 * PI * f / FS), a[MNA_MAXK][MNA_MAXK + 1];
    for (int i = 0; i < k; ++i) {
        for (int j = 0; j < k; ++j)
            a[i][j] = (i == j ? z : cd(0)) - ((i == j ? 1.0 : 0.0) + (double)MNA_DA(p, k, nu, i, j));
        a[i][k] = (double)MNA_DB(p, k, nu, i, u) * (z + 1.0);
    }
    for (int c = 0; c < k; ++c) {
        int piv = c;
        for (int i = c + 1; i < k; ++i) if (std::abs(a[i][c]) > std::abs(a[piv][c])) piv = i;
        for (int j = 0; j <= k; ++j) std::swap(a[c][j], a[piv][j]);
        for (int i = c + 1; i < k; ++i) {
            cd fct = a[i][c] / a[c][c];
            for (int j = c; j <= k; ++j) a[i][j] -= fct * a[c][j];
        }
    }
    cd x[MNA_MAXK];
    for (int c = k - 1; c >= 0; --c) {
        cd acc = a[c][k];
        for (int j = c + 1; j < k; ++j) acc -= a[c][j] * x[j];
        x[c] = acc / a[c][c];
    }
    cd y = (double)MNA_DY(p, k, nu, u);
    for (int i = 0; i < k; ++i) y += (double)MNA_CY(p, k, nu, i) * x[i];
    return y;
}

static double db(double r) { return 20 * std::log10(r + 1e-30); }

static void derive_float(int net, const float* kn, bool generated, float* out)
{
    if (generated) {
        if (net == 0) hw_stack_derive(kn[0], kn[1], kn[2], kn[3], (float)FS, out);
        else if (net == 1) hw_v1_derive(kn[0], (float)FS, out);
        else hw_bh_derive(kn[0], (float)FS, out);
        return;
    }
    MnaNet n;
    float w[MNA_MAXN];
    if (net == 0) hw_stack(&n, w, kn[0], kn[1], kn[2], kn[3]);
    else if (net == 1) hw_v1net(&n, w, kn[0]);
    else hw_backhalf(&n, w, kn[0]);
    mna_derive(&n, w, (float)FS, out);
}

struct Score { double inG = 0, inR = 0, absG = 0, absR = 0, alg = 0; int sets = 0; };

static void score(int net, const float* kn, Score& s)
{
    const int k = KS[net], nu = NUS[net], sz = MNA_SS_SIZE(k, nu);
    float pg[64], pr[64];
    double pd[64], pgd[64], knd[4];
    for (int i = 0; i < 4; ++i) knd[i] = kn[i];
    derive_float(net, kn, true, pg);
    derive_float(net, kn, false, pr);
    net_ref_d(net, knd, FS, pd);
    net_gen_d(net, knd, FS, pgd);
    (void)sz;
    ++s.sets;
    for (int u = 0; u < nu; ++u) {
        double peak = 0;
        for (double f = 20; f <= 20000; f *= 1.05) peak = std::max(peak, std::abs(resp(pd, k, nu, u, f)));
        if (peak < 1e-6) continue;                 // master at 0: below -120 dB
        for (double f = 20; f <= 20000; f *= 1.05) {
            const cd hd = resp(pd, k, nu, u, f), hg = resp(pg, k, nu, u, f);
            const cd hr = resp(pr, k, nu, u, f), hgd = resp(pgd, k, nu, u, f);
            const double ad = std::abs(hd);
            s.alg = std::max(s.alg, std::abs(hgd - hd) / peak);
            s.absG = std::max(s.absG, std::abs(hg - hd) / peak);
            s.absR = std::max(s.absR, std::abs(hr - hd) / peak);
            if (ad > 0.1 * peak) {
                s.inG = std::max(s.inG, std::fabs(db(std::abs(hg) / ad)));
                s.inR = std::max(s.inR, std::fabs(db(std::abs(hr) / ad)));
            }
        }
    }
}

int main()
{
    const char* names[3] = { "tone stack", "V1 net", "back half" };
    Score sc[3];
    const float g[] = { 0.0f, 0.01f, 0.1f, 0.25f, 0.5f, 0.75f, 0.9f, 0.99f, 1.0f };
    for (float t : g) for (float m : g) for (float b : g)
        for (int iv = 0; iv < 9; iv += 2) {
            const float kn[4] = { t, m, b, g[iv] };
            score(0, kn, sc[0]);
        }
    for (int net = 1; net < 3; ++net) {
        for (int p = 0; p <= 100; ++p) {
            const float kn[4] = { p * 0.01f, 0, 0, 0 };
            score(net, kn, sc[net]);
        }
        for (float x : { 0.005f, 0.0137f, 0.333f, 0.987f, 0.995f, 0.9999f }) {
            const float kn[4] = { x, 0, 0, 0 };
            score(net, kn, sc[net]);
        }
    }
    bool ok = true;
    std::printf("vs double mna_derive at 4x (in band |dH| dB / complex error dB re peak):\n");
    for (int net = 0; net < 3; ++net) {
        const Score& s = sc[net];
        const bool pass = s.inG < 0.01 && s.absG < 3.16e-4 && s.alg < 1e-5;
        ok = ok && pass;
        std::printf("  %-10s %4d sets: generated %.5f / %6.1f   mna_derive float %.5f / %6.1f   algebra %6.1f  %s\n",
                    names[net], s.sets, s.inG, db(s.absG), s.inR, db(s.absR), db(s.alg), pass ? "ok" : "FAIL");
    }
    std::printf("%s\n", ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
}
