// How coarse may the DR103 knob tables be? The V1 network (Volume) and the
// back half (Presence) are stored as discrete systems per knob position; the
// G1 knobs only take the integer positions 0..100. For a table step s, every
// position is linearly interpolated from the stored ones (0, s, 2s, .., 100)
// and its response compared with the exactly derived system: in band (within
// 20 dB of the peak) |dH| in dB and the complex error re peak, per input.
//   build_hiwatt_tables_test.bat [steps...]   (default: 1 2 4 5)
#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
extern "C" {
#include "../../effects/common/hiwatt_nets.h"
}

using cd = std::complex<double>;
static const double PI = 3.14159265358979323846;
static const double FS = 4 * 44100.0;

// H(z) from input u of the packed delta-form system (k states, nu inputs)
static cd resp(const float* p, int k, int nu, int u, double f)
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

static std::vector<float> derive(int net, int pos, int& k, int& nu)
{
    MnaNet n;
    float w[MNA_MAXN];
    const float x = pos * 0.01f;
    if (net == 0) hw_v1net(&n, w, x); else hw_backhalf(&n, w, x);
    k = n.k; nu = n.nu;
    std::vector<float> p(MNA_SS_SIZE(k, nu));
    mna_derive(&n, w, (float)FS, p.data());
    return p;
}

static double db(double r) { return 20 * std::log10(r + 1e-30); }

// worst in-band dB and complex error re peak of position p interpolated
// linearly between stored positions a < p < b
struct Err { double inband, cplx; };
static Err interp_err(const std::vector<std::vector<float>>& ex, int k, int nu, int a, int b, int p)
{
    const int sz = MNA_SS_SIZE(k, nu);
    const float fr = (p - a) / (float)(b - a);
    std::vector<float> q(sz);
    for (int j = 0; j < sz; ++j) q[j] = ex[a][j] + fr * (ex[b][j] - ex[a][j]);
    Err e = { 0, 0 };
    for (int u = 0; u < nu; ++u) {
        double peak = 0;
        for (double f = 20; f <= 20000; f *= 1.05) peak = std::max(peak, std::abs(resp(ex[p].data(), k, nu, u, f)));
        for (double f = 20; f <= 20000; f *= 1.05) {
            const cd he = resp(ex[p].data(), k, nu, u, f), hq = resp(q.data(), k, nu, u, f);
            e.cplx = std::max(e.cplx, std::abs(hq - he) / peak);
            if (std::abs(he) > 0.1 * peak)
                e.inband = std::max(e.inband, std::fabs(db(std::abs(hq) / std::abs(he))));
        }
    }
    return e;
}

// Greedy non-uniform table: start from all 101 positions and keep removing
// the stored position whose removal costs least, while every integer
// position between its neighbours stays within tol_db in band and tol_c re peak.
static std::vector<int> greedy(const std::vector<std::vector<float>>& ex, int k, int nu,
                               double tol_db, double tol_c, Err& worst)
{
    std::vector<int> keep;
    for (int p = 0; p <= 100; ++p) keep.push_back(p);
    for (;;) {
        int best = -1;
        double bestScore = 1e30;
        for (size_t i = 1; i + 1 < keep.size(); ++i) {
            const int a = keep[i - 1], b = keep[i + 1];
            double score = 0;
            bool ok = true;
            for (int p = a + 1; p < b && ok; ++p) {
                Err e = interp_err(ex, k, nu, a, b, p);
                if (e.inband > tol_db || e.cplx > tol_c) ok = false;
                score = std::max(score, e.inband / tol_db + e.cplx / tol_c);
            }
            if (ok && score < bestScore) { bestScore = score; best = (int)i; }
        }
        if (best < 0) break;
        keep.erase(keep.begin() + best);
    }
    worst = { 0, 0 };
    for (size_t i = 0; i + 1 < keep.size(); ++i)
        for (int p = keep[i] + 1; p < keep[i + 1]; ++p) {
            Err e = interp_err(ex, k, nu, keep[i], keep[i + 1], p);
            worst.inband = std::max(worst.inband, e.inband);
            worst.cplx = std::max(worst.cplx, e.cplx);
        }
    return keep;
}

int main(int argc, char** argv)
{
    if (argc > 1 && std::string(argv[1]) == "greedy") {   // greedy <tol dB> <tol complex dB>
        const double tdb = argc > 2 ? std::atof(argv[2]) : 0.02;
        const double tc = std::pow(10.0, (argc > 3 ? std::atof(argv[3]) : -60.0) / 20);
        const char* names[] = { "V1 net (Volume)", "back half (Presence)" };
        for (int net = 0; net < 2; ++net) {
            int k = 0, nu = 0;
            std::vector<std::vector<float>> ex;
            for (int p = 0; p <= 100; ++p) ex.push_back(derive(net, p, k, nu));
            Err w;
            std::vector<int> keep = greedy(ex, k, nu, tdb, tc, w);
            std::printf("%s: %zu positions (%zu B), worst in band %.4f dB, complex %.1f dB re peak\n  {",
                        names[net], keep.size(), keep.size() * MNA_SS_SIZE(k, nu) * 4, w.inband, db(w.cplx));
            for (size_t i = 0; i < keep.size(); ++i) std::printf("%s%d", i ? ", " : " ", keep[i]);
            std::printf(" }\n");
        }
        return 0;
    }
    std::vector<int> steps;
    for (int i = 1; i < argc; ++i) steps.push_back(std::atoi(argv[i]));
    if (steps.empty()) steps = { 1, 2, 4, 5 };
    const char* names[] = { "V1 net (Volume)", "back half (Presence)" };
    for (int net = 0; net < 2; ++net) {
        int k = 0, nu = 0;
        std::vector<std::vector<float>> exact;
        for (int p = 0; p <= 100; ++p) exact.push_back(derive(net, p, k, nu));
        const int sz = MNA_SS_SIZE(k, nu);
        for (int s : steps) {
            if (100 % s) continue;
            double inband = 0, cplx = 0;
            const bool per = std::getenv("HW_TAB_PER") != nullptr;
            for (int p = 0; p <= 100; ++p) {
                double pin = 0;
                const int i0 = std::min(p / s, 100 / s - 1);
                const float fr = (p - i0 * s) / (float)s;
                const std::vector<float>& a = exact[i0 * s];
                const std::vector<float>& b = exact[i0 * s + s];
                std::vector<float> q(sz);
                for (int j = 0; j < sz; ++j) q[j] = a[j] + fr * (b[j] - a[j]);   // = hw_tabsys
                for (int u = 0; u < nu; ++u) {
                    double peak = 0;
                    for (double f = 20; f <= 20000; f *= 1.05) peak = std::max(peak, std::abs(resp(exact[p].data(), k, nu, u, f)));
                    for (double f = 20; f <= 20000; f *= 1.05) {
                        const cd he = resp(exact[p].data(), k, nu, u, f), hq = resp(q.data(), k, nu, u, f);
                        cplx = std::max(cplx, std::abs(hq - he) / peak);
                        if (std::abs(he) > 0.1 * peak)
                            pin = std::max(pin, std::fabs(db(std::abs(hq) / std::abs(he))));
                    }
                }
                inband = std::max(inband, pin);
                if (per && pin > 0.01) std::printf("    %s step %d pos %d: %.3f dB\n", names[net], s, p, pin);
            }
            std::printf("%-22s step %d (%3d entries, %5d B): in band %.4f dB, complex %.1f dB re peak\n",
                        names[net], s, 100 / s + 1, (100 / s + 1) * sz * 4, inband, db(cplx));
        }
    }
    return 0;
}
