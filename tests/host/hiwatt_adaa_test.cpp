// Float ADAA tube stage (effects/common/hiwatt_amp.h hw_tube_adaa) against
// the exact mean of the desktop transfer over each step (AmpStages.h tubeStage /
// tubeStageF, mirrored here; Simpson for steps < 1e-3) on random walks with step sizes from 1e-6 to 2, all five stage bias/asym settings and
// ceilings 0.85..1. Prints the worst absolute error per step scale.
#include <cmath>
#include <cstdio>
#include <random>
#include <cstdlib>
extern "C" {
#include "../../effects/common/hiwatt_amp.h"
}

static double lnCosh(double v) { v = std::fabs(v); return v + std::log1p(std::exp(-2.0 * v)) - 0.6931471805599453; }
static double tubeD(double x, double b, double as, double c)
{
    double u = x + b; if (u > c) u = c + (u - c) * 0.08;
    double y = std::tanh(u); if (y < 0) y *= 1.0 - as * 0.15; return y;
}
static double tubeF(double x, double b, double as, double c)
{
    const double u = x + b, k = 1.0 - as * 0.15, a = 0.08;
    if (u < 0.0) return k * lnCosh(u);
    if (u <= c) return lnCosh(u);
    return lnCosh(a * u + c * (1.0 - a)) / a + lnCosh(c) * (1.0 - 1.0 / a);
}

// mean of the transfer over [xa, xb]: exact F quotient for big steps, Simpson
// split at the kinks (u = 0, u = c) for small ones, where even double F
// differences cancel (the desktop's 1e-7 threshold hides that)
static double meanF(double xa, double xb, double b, double as, double c)
{
    const double dx = xb - xa;
    if (std::fabs(dx) > 1e-3) return (tubeF(xb, b, as, c) - tubeF(xa, b, as, c)) / dx;
    double lo = std::min(xa, xb), hi = std::max(xa, xb), cuts[4] = {lo, 0, 0, hi};
    int n = 1;
    for (double k : {-b, c - b}) if (k > lo && k < hi) cuts[n++] = k;
    cuts[n] = hi;
    if (n == 3 && cuts[1] > cuts[2]) std::swap(cuts[1], cuts[2]);
    double acc = 0;
    for (int i = 0; i < n; ++i) {
        const double a = cuts[i], e = cuts[i + 1], h = (e - a) / 64;
        double sum = tubeD(a, b, as, c) + tubeD(e, b, as, c);
        for (int j = 1; j < 64; ++j) sum += tubeD(a + j * h, b, as, c) * (j % 2 ? 4 : 2);
        acc += sum * h / 3;
    }
    return hi > lo ? acc / (hi - lo) : tubeD(lo, b, as, c);
}

int main()
{
    const double bias[5] = {0.03, -0.02, 0.02, -0.05, -0.08}, asym[5] = {0.15, 0.1, 0.12, 0.08, 0.02};
    std::mt19937 rng(7);
    std::printf("step scale   worst |float ADAA - exact step mean|\n");
    for (double scale : {1e-6, 1e-5, 1e-4, 1e-3, 1e-2, 0.1, 0.5, 2.0}) {
        double worst = 0;
        for (int st = 0; st < 5; ++st) {
            const double k = 1.0 - asym[st] * 0.15;
            double idle = std::tanh(bias[st]); if (idle < 0) idle *= k;
            std::normal_distribution<double> step(0.0, scale);
            std::uniform_real_distribution<double> cdist(0.85, 1.0), start(-4.0, 4.0);
            for (int run = 0; run < 200; ++run) {
                const double c = cdist(rng);
                double x = start(rng), x1d = x;
                float x1f = (float)x;
                for (int n = 0; n < 500; ++n) {
                    x += step(rng);
                    if (x > 40) x = 40; if (x < -40) x = -40;
                    const double dx = x - x1d;
                    double ref = meanF(x1d, (double)(float)x, bias[st], asym[st], c);
                    ref -= idle;
                    x1d = (double)(float)x;     // the float stage sees float inputs
                    float y = hw_tube_adaa((float)x, &x1f, (float)bias[st], (float)k, (float)c, (float)idle);
                    if (std::fabs(dx) > 1e-12 && std::fabs(y - ref) > worst) {
                        worst = std::fabs(y - ref);
                        if (worst > 2e-5 && getenv("DBG"))
                            std::printf("  st %d c %.3f x1 %.9g x %.9g float %.6f double %.6f\n",
                                        st, c, x - dx, x, y, ref);
                    }
                }
            }
        }
        std::printf("%9.0e    %.2e  (%.1f dB re 1)\n", scale, worst, 20 * std::log10(worst + 1e-30));
    }
    return 0;
}
