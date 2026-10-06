// Hiwatt DR103 accuracy bench: the G1 chain (effects/common/hiwatt_amp.h,
// float, 44.1 kHz in, 4x inside) against the desktop circuit model.
//
// Reference: Comet Flower's HiwattDR103Processor::process per-sample chain,
// mirrored in double at 16x (705.6 kHz), with the desktop's own MNA builders
// and discretisation (tools/dsp_validate/cases/hiwatt.h: strays included),
// the desktop's double ADAA tube stages (AmpStages.h), DC guard, sag, preamp
// ceiling and the implicit-NFB + delayed residual, as shipped. Amp only (the
// cab is the desktop's biquads by construction, hiwatt_cab.h).
// Writes float32 files; tests/host/hiwatt_accuracy.py scores them.
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
#include "cases/hiwatt.h"
extern "C" {
#include "../../effects/common/hiwatt_amp.h"
}

static const double PI = 3.14159265358979323846;
static const int SR = 44100;

struct Knobs { double vol, tre, mid, bas, mas, pre; const char* name; };

static double tubeD(double x, double bias, double asym, double ceiling)
{
    double u = x + bias;
    if (u > ceiling) u = ceiling + (u - ceiling) * 0.08;
    double y = std::tanh(u);
    if (y < 0) y *= (1.0 - asym * 0.15);
    double idle = std::tanh(bias);
    if (idle < 0) idle *= (1.0 - asym * 0.15);
    return y - idle;
}

// desktop AmpStages::lnCosh / tubeStageF / ADAATubeStage (double), mirrored
static double lnCoshD(double v) { v = std::fabs(v); return v + std::log1p(std::exp(-2.0 * v)) - 0.6931471805599453; }
static double tubeF(double x, double bias, double asym, double ceiling)
{
    const double u = x + bias, k = 1.0 - asym * 0.15, a = 0.08;
    if (u < 0.0) return k * lnCoshD(u);
    if (u <= ceiling) return lnCoshD(u);
    return lnCoshD(a * u + ceiling * (1.0 - a)) / a + lnCoshD(ceiling) * (1.0 - 1.0 / a);
}
struct Adaa {
    double x1 = 0;
    double operator()(double x, double bias, double asym, double ceiling) {
        double idle = std::tanh(bias);
        if (idle < 0) idle *= (1.0 - asym * 0.15);
        const double dx = x - x1;
        double y;
        if (std::fabs(dx) > 1e-7) y = (tubeF(x, bias, asym, ceiling) - tubeF(x1, bias, asym, ceiling)) / dx - idle;
        else y = tubeD(0.5 * (x + x1), bias, asym, ceiling);
        x1 = x;
        return y;
    }
};

template <int N, int NIN>
struct DNet {
    double P[N][N], W[N][NIN], v[N] = {}, up[NIN] = {};
    void step(const double* u) {
        double nv[N];
        for (int i = 0; i < N; ++i) {
            double a = 0;
            for (int c = 0; c < NIN; ++c) a += W[i][c] * (u[c] + up[c]);
            for (int j = 0; j < N; ++j) a += P[i][j] * v[j];
            nv[i] = a;
        }
        for (int i = 0; i < N; ++i) v[i] = nv[i];
        for (int c = 0; c < NIN; ++c) up[c] = u[c];
    }
};

static std::vector<float> reference(double f0, double amp, const Knobs& kn, double secs, int os,
                                    bool adaa)
{
    Adaa ad[5];
    auto tube = [&](int i, double x, double b, double a, double c) {
        return adaa ? ad[i](x, b, a, c) : tubeD(x, b, a, c);
    };
    using namespace hiwatt_case;
    const double fs = (double)SR * os;
    DNet<5, 1> v1; DNet<10, 1> st; DNet<11, 2> bh;
    buildV1Net(kn.vol).discretize(fs, v1.P, v1.W);
    buildStackNet(kn.tre, kn.mid, kn.bas, kn.mas).discretize(fs, st.P, st.W);
    buildBackHalf(kn.pre).discretize(fs, bh.P, bh.W);
    const double dcR = 1.0 - 2 * PI * 5.0 / fs;
    const double att = 1.0 - std::exp(-1.0 / (0.005 * fs)), rel = 1.0 - std::exp(-1.0 / (0.020 * fs));
    const double ra = 1.0 - std::exp(-2 * PI * 30000.0 / fs);
    double px = 0, pz = 0, sag = 0, rail = 1, resid = 0;
    const int N = (int)(secs * fs);
    std::vector<float> out(N);
    for (int n = 0; n < N; ++n) {
        const double pre = 1.0 - (1.0 - rail) * 0.3;
        double vj = amp * std::sin(2 * PI * f0 * n / fs) * 2.0 * IN_DIV;
        double dcb = vj - px + dcR * pz; px = vj; pz = dcb;
        double y1 = tube(0, dcb / 2.4, 0.03, 0.15, pre);
        double u = MU3 * 2.4 * y1; v1.step(&u);
        double y2 = tube(1, v1.v[vG2] / 3.8, -0.02, 0.1, pre);
        u = MU3 * 3.8 * y2; st.step(&u);
        double y3 = tube(2, st.v[sOUT] / 2.4, 0.02, 0.12, pre);
        double ub[2] = { 2.4 * y3, -resid }; bh.step(ub);
        double d = bh.v[bKB3] - bh.v[bM];
        double ypi = tube(3, d / 0.96, -0.05, 0.08, pre);
        double qd = -ypi * 48.5 * 0.96;
        double r = std::fabs(ypi);
        sag += (r - sag) * (r > sag ? att : rel);
        rail = 1.0 - sag * 0.15;
        double yp = tube(4, qd / (2.0 * 38.0), -0.08, 0.02, rail);
        double tap = 56.57 * yp;
        resid += ra * ((tap - KTAPLIN * d) - resid);
        out[n] = (float)(tap / 62.0);
    }
    return out;
}

static void write(const std::string& p, const std::vector<float>& v)
{
    FILE* f = std::fopen(p.c_str(), "wb"); std::fwrite(v.data(), 4, v.size(), f); std::fclose(f);
}

int main(int argc, char** argv)
{
    std::string dir = argc > 1 ? argv[1] : ".";
    const bool variants = argc > 2 && std::string(argv[2]) == "variants";
    const Knobs knobs[] = {
        { 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, "noon" },
        { 1.0, 0.5, 0.5, 0.5, 1.0, 0.5, "cranked" },
        { 0.5, 0.95, 0.5, 0.5, 0.5, 1.0, "bright" },
        { 0.7, 0.1, 0.2, 1.0, 0.7, 0.2, "dark" },
    };
    const double secs = 1.5;   // the scorer uses the last exact second
    for (const auto& kn : knobs)
        for (double f0 : { 110.0, 440.0, 1760.0 })
            for (double amp : { 0.05, 0.25, 0.7 }) {
                char tag[64];
                std::snprintf(tag, sizeof tag, "%s_f%d_a%03d", kn.name, (int)f0, (int)(amp * 100));
                write(dir + "/ref_" + tag + ".f32", reference(f0, amp, kn, secs, 16, true));
                if (variants) {   // the same double chain at 4x / 8x: what each rate can reach
                    write(dir + "/R4_" + tag + ".f32", reference(f0, amp, kn, secs, 4, false));
                    write(dir + "/R4A_" + tag + ".f32", reference(f0, amp, kn, secs, 4, true));
                    write(dir + "/R8_" + tag + ".f32", reference(f0, amp, kn, secs, 8, false));
                }
                HwState s = {}; HwCoeffs k;
                hw_coeffs(&k, (float)kn.vol, (float)kn.tre, (float)kn.mid, (float)kn.bas,
                          (float)kn.mas, (float)kn.pre);
                const int N = (int)(secs * SR);
                std::vector<float> o(N);
                for (int n = 0; n < N; n += 16) {
                    float io[16];
                    for (int i = 0; i < 16; ++i)
                        io[i] = n + i < N ? (float)(amp * std::sin(2 * PI * f0 * (n + i) / SR)) : 0.0f;
                    hw_block(&s, &k, io, 0);
                    for (int i = 0; i < 16 && n + i < N; ++i) o[n + i] = io[i];
                }
                {
                    char pre[16];
                    std::snprintf(pre, sizeof pre, "G");
                    write(dir + "/" + pre + "_" + tag + ".f32", o);
                }
            }
    std::printf("done\n");
    return 0;
}
