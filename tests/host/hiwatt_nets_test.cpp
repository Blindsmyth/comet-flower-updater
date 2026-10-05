// Checks effects/common/hiwatt_nets.h + mna_ss.h (float, stray-free,
// capacitor-state) against the desktop builders in Comet Flower's
// tools/dsp_validate/cases/hiwatt.h (double, strays, full MNA):
//   [1] |H| vs the desktop analog circuit, 20 Hz..20 kHz and below 5 kHz
//   [2] |H| vs the desktop's own bilinear recursion at the same rate
//   [3] stability (all discrete poles inside the unit circle) on a knob grid
//   [4] float32 delta-form run vs the double response (sine, steady state)
// at the rates the G1 port can use (4x and 8x of 44.1 kHz).
#include <cmath>
#include <complex>
#include <cstdio>
#include <vector>
#include "cases/hiwatt.h"            // desktop builders (include path set by the .bat)
extern "C" {
#include "../../effects/common/hiwatt_nets.h"
}

using cd = std::complex<double>;
static const double PI = 3.14159265358979323846;

// unpacked view of mna_derive's packed output
struct MnaSS {
    float da[MNA_MAXK][MNA_MAXK], db[MNA_MAXK][MNA_MAXU], cy[MNA_MAXK], dy[MNA_MAXU];
};
static MnaSS derive(MnaNet& net, const float* wv, double fs)
{
    float p[MNA_SS_SIZE(MNA_MAXK, MNA_MAXU)];
    const int k = net.k, nu = net.nu;
    mna_derive(&net, wv, (float)fs, p);
    MnaSS s = {};
    for (int i = 0; i < k; ++i) {
        for (int j = 0; j < k; ++j) s.da[i][j] = MNA_DA(p, k, nu, i, j);
        for (int u = 0; u < nu; ++u) s.db[i][u] = MNA_DB(p, k, nu, i, u);
        s.cy[i] = MNA_CY(p, k, nu, i);
    }
    for (int u = 0; u < nu; ++u) s.dy[u] = MNA_DY(p, k, nu, u);
    return s;
}

// digital response of our system: z x = x + dA x + dB (z+1) u, y = cy x + dy u
static cd ourH(const MnaSS& s, int k, int col, double f, double fs)
{
    const cd z = std::polar(1.0, 2 * PI * f / fs);
    cd A[MNA_MAXK][MNA_MAXK], x[MNA_MAXK];
    for (int i = 0; i < k; ++i) {
        for (int j = 0; j < k; ++j) A[i][j] = (i == j ? z - 1.0 : cd(0)) - (double)s.da[i][j];
        x[i] = (double)s.db[i][col] * (z + 1.0);
    }
    for (int c = 0; c < k; ++c) {
        int p = c;
        for (int i = c + 1; i < k; ++i) if (std::abs(A[i][c]) > std::abs(A[p][c])) p = i;
        for (int j = 0; j < k; ++j) std::swap(A[c][j], A[p][j]);
        std::swap(x[c], x[p]);
        for (int i = c + 1; i < k; ++i) {
            cd f2 = A[i][c] / A[c][c];
            for (int j = c; j < k; ++j) A[i][j] -= f2 * A[c][j];
            x[i] -= f2 * x[c];
        }
    }
    for (int c = k - 1; c >= 0; --c) {
        for (int j = c + 1; j < k; ++j) x[c] -= A[c][j] * x[j];
        x[c] /= A[c][c];
    }
    cd y = (double)s.dy[col];
    for (int i = 0; i < k; ++i) y += (double)s.cy[i] * x[i];
    return y;
}

// spectral radius of (I + dA) by power iteration on a long impulse run (double)
static bool stable(const MnaSS& s, int k)
{
    double x[MNA_MAXK] = {1, 0.7, -0.3, 0.2, 0.5}, early = 0, late = 0;
    for (int n = 0; n < 2000000; ++n) {
        double nx[MNA_MAXK];
        for (int i = 0; i < k; ++i) {
            double a = x[i];
            for (int j = 0; j < k; ++j) a += s.da[i][j] * x[j];
            nx[i] = a;
        }
        double m = 0;
        for (int i = 0; i < k; ++i) { x[i] = nx[i]; m = std::max(m, std::fabs(x[i])); }
        if (!std::isfinite(m) || m > 1e9) return false;
        if (n < 1000) early = std::max(early, m);
        if (n > 1990000) late = std::max(late, m);
    }
    return late < early * 1e-3;
}

// float32 run of a sine through the system; error vs the double response, dB
static double floatRunErr(const MnaSS& s, int k, int col, double f, double fs)
{
    float x[MNA_MAXK] = {}, u1 = 0;
    const int N = (int)(fs * 0.6);
    const cd H = ourH(s, k, col, f, fs);
    double e2 = 0, r2 = 0;
    for (int n = 0; n < N; ++n) {
        float u = (float)std::sin(2 * PI * f * n / fs), dx[MNA_MAXK];
        for (int i = 0; i < k; ++i) {
            float a = s.db[i][col] * (u + u1);
            for (int j = 0; j < k; ++j) a += s.da[i][j] * x[j];
            dx[i] = a;
        }
        for (int i = 0; i < k; ++i) x[i] += dx[i];
        u1 = u;
        float y = s.dy[col] * u;
        for (int i = 0; i < k; ++i) y += s.cy[i] * x[i];
        if (n > N / 2) {
            double yr = std::imag(H * std::polar(1.0, 2 * PI * f * n / fs));
            e2 += (y - yr) * (y - yr); r2 += yr * yr;
        }
    }
    return 10 * std::log10(e2 / r2);
}

struct Worst { double an = 0, an5 = 0, dg = 0, fl = -999; int unstable = 0, cases = 0; };

template <int N, int NIN, class Ref>
static void check(Worst& w, MnaNet& net, const float* wv, const Ref& ref, int refOut2,
                  int refOut, int col, double fs, bool diff)
{
    int k = net.k;
    MnaSS s = derive(net, wv, fs);
    double P[N][N], W[N][NIN];
    ref.discretize(fs, P, W);
    for (double f = 20; f <= 20000; f *= 1.06) {
        cd ha = ref.analog(f, refOut, col);
        if (diff) ha -= ref.analog(f, refOut2, col);
        double our = std::abs(ourH(s, k, col, f, fs));
        double e = std::fabs(20 * std::log10(our / std::abs(ha)));
        w.an = std::max(w.an, e);
        if (f < 5000) w.an5 = std::max(w.an5, e);
        // desktop digital: dB of node (or node difference) response
        double dd;
        if (!diff) dd = hiwatt_case::digitalDb<N, NIN>(P, W, f, fs, refOut, col);
        else {
            // difference node: evaluate both nodes complex via a tiny re-solve
            const cd z1 = std::polar(1.0, -2 * PI * f / fs);
            cd A[N][N], x[N];
            for (int i = 0; i < N; ++i) {
                for (int j = 0; j < N; ++j) A[i][j] = (i == j ? cd(1) : cd(0)) - z1 * P[i][j];
                x[i] = W[i][col] * (1.0 + z1);
            }
            for (int c = 0; c < N; ++c) {
                int p = c;
                for (int i = c + 1; i < N; ++i) if (std::abs(A[i][c]) > std::abs(A[p][c])) p = i;
                for (int j = 0; j < N; ++j) std::swap(A[c][j], A[p][j]);
                std::swap(x[c], x[p]);
                for (int i = c + 1; i < N; ++i) {
                    cd f2 = A[i][c] / A[c][c];
                    for (int j = c; j < N; ++j) A[i][j] -= f2 * A[c][j];
                    x[i] -= f2 * x[c];
                }
            }
            for (int c = N - 1; c >= 0; --c) {
                for (int j = c + 1; j < N; ++j) x[c] -= A[c][j] * x[j];
                x[c] /= A[c][c];
            }
            dd = 20 * std::log10(std::abs(x[refOut] - x[refOut2]));
        }
        w.dg = std::max(w.dg, std::fabs(20 * std::log10(our) - dd));
    }
    for (double f : {100.0, 1000.0, 5000.0})
        w.fl = std::max(w.fl, floatRunErr(s, k, col, f, fs));
    w.unstable += stable(s, k) ? 0 : 1;
    w.cases++;
}

static void report(const char* name, double fs, const Worst& w)
{
    std::printf("%-9s %6.1fk  vs analog %.3f dB (<5k %.3f)  vs desktop digital %.3f dB  "
                "float run %.1f dB  unstable %d/%d\n",
                name, fs / 1000, w.an, w.an5, w.dg, w.fl, w.unstable, w.cases);
}

int main()
{
    using namespace hiwatt_case;
    const double grid[] = {0.0, 0.25, 0.5, 0.75, 1.0};
    for (double fs : {176400.0, 352800.0}) {
        Worst wv1, wst, wb0, wb1;
        for (double v : grid) {
            MnaNet n; float w[MNA_MAXN];
            hw_v1net(&n, w, (float)v);
            check<5, 1>(wv1, n, w, buildV1Net(v), 0, vG2, 0, fs, false);
        }
        for (double t : grid) for (double m : grid) for (double b : grid) for (double mv : {0.05, 0.5, 1.0}) {
            MnaNet n; float w[MNA_MAXN];
            hw_stack(&n, w, (float)t, (float)m, (float)b, (float)mv);
            check<10, 1>(wst, n, w, buildStackNet(t, m, b, mv), 0, sOUT, 0, fs, false);
        }
        for (double p : grid) {
            MnaNet n; float w[MNA_MAXN];
            hw_backhalf(&n, w, (float)p);
            check<11, 2>(wb0, n, w, buildBackHalf(p), bM, bKB3, 0, fs, true);
            hw_backhalf(&n, w, (float)p);
            check<11, 2>(wb1, n, w, buildBackHalf(p), bM, bKB3, 1, fs, true);
        }
        report("V1", fs, wv1);
        report("stack", fs, wst);
        report("back u0", fs, wb0);
        report("back u1", fs, wb1);
    }
    return 0;
}
