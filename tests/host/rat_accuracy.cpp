// CF RAT accuracy bench. Writes float32 outputs of the reference and of the
// candidate core (effects/common/rat_g1.h) for a grid of sine tests;
// tests/host/rat_accuracy.py scores them.
//
// Reference: Comet Flower's RatProcessor signal chain (Source/RatProcessor.cpp,
// 2026-07-17 de-guess pass), in double precision at 32x, with the same
// filter types (JUCE first-order bilinear high-passes = TPT one-pole HP;
// JUCE StateVariableTPTFilter low-passes, resonance 1/sqrt2), the 0.3 V/us
// slew limit, the +-4 V rail clamp, and the 1N914 shunt pair
// (u = vo + Rs*2*Is*sinh(vo/nVt), Rs 68, Is 2.52 nA, nVt 45.3 mV) solved
// exactly every sample instead of the desktop's LUT + ADAA. Knobs fixed per
// test (no smoothing). The reference is rendered at 32x and 64x: where the two
// disagree (deep slew limiting, e.g. Distortion 10 with a loud 3.7 kHz input,
// where a sampled slew limiter's turnaround jitter keeps moving even at 64x),
// the scorer does not hold the candidate to the reference's exact harmonics.
// Written by Claude; do not edit as part of the model work.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
extern "C" {
#include "../../effects/common/rat_g1.h"
}

static const double PI = 3.14159265358979323846;
static const int SR = 44100;

struct HP1 {                       // JUCE makeFirstOrderHighPass == TPT one-pole HP
    double g = 0, s = 0;
    void set(double fs, double fc) { double t = std::tan(PI * fc / fs); g = t / (1 + t); }
    double p(double x) { double v = (x - s) * g, lp = v + s; s = lp + v; return x - lp; }
};
struct SVF {                       // JUCE StateVariableTPTFilter, low-pass output
    double g = 0, R2 = std::sqrt(2.0), h = 0, s1 = 0, s2 = 0;
    void set(double fs, double fc) { g = std::tan(PI * fc / fs); h = 1.0 / (1.0 + R2 * g + g * g); }
    double p(double x) {
        double hp = h * (x - s1 * (g + R2) - s2);
        double bp = hp * g + s1; s1 = hp * g + bp;
        double lp = bp * g + s2; s2 = bp * g + lp;
        return lp;
    }
};

static double shunt(double u, double& vo)   // exact 1N914 pair, odd, warm start
{
    const double K = 68.0 * 2.0 * 2.52e-9, nVt = 0.0453;
    const double au = std::fabs(u);
    double v = std::min(std::fabs(vo), au);
    for (int it = 0; it < 80; ++it) {
        double s = std::sinh(v / nVt), c = std::cosh(v / nVt);
        double g = v + K * s - au, gp = 1.0 + (K / nVt) * c;
        double step = std::clamp(g / gp, -4 * nVt, 4 * nVt);
        v = std::clamp(v - step, 0.0, au);
        if (std::fabs(step) < 1e-14) break;
    }
    vo = v;
    return u < 0 ? -v : v;
}

static std::vector<float> reference(double f0, double amp, double dist, double filter,
                                    double secs, int os)
{
    const double fs = SR * (double)os;
    const int N = (int)(secs * fs);
    std::vector<float> out(N);
    const double gTop = std::pow(10.0, (dist / 10.0 * 66.5) / 20.0);
    const double Rf = 47.0 * (gTop - 1.0);
    const double toneMax = std::min(32000.0, 0.45 * fs);
    const double cutoff = 475.0 * std::pow(toneMax / 475.0, filter);
    const double effBW = std::max(400.0, std::min(1.0e6 / std::max(gTop, 1.0), 20000.0));
    const double fc100 = Rf > 100.0 ? std::min(1.0 / (2 * PI * Rf * 100e-12), 0.45 * fs) : 0.45 * fs;
    const double maxDelta = 0.3 * (1.0e6 / fs);
    HP1 ac, legHi, legLo; ac.set(fs, 10.0); legHi.set(fs, 1539.0); legLo.set(fs, 60.5);
    SVF fb, opa, tone; fb.set(fs, fc100); opa.set(fs, effBW); tone.set(fs, cutoff);
    double slew = 0, vo = 0;
    for (int n = 0; n < N; ++n) {
        double x = ac.p(amp * std::sin(2 * PI * f0 * n / fs));
        double boost = Rf * ((1.0 / 47.0) * legHi.p(x) + (1.0 / 560.0) * legLo.p(x));
        x += fb.p(boost);
        double d = x - slew;
        if (d > maxDelta) x = slew + maxDelta; else if (d < -maxDelta) x = slew - maxDelta;
        slew = x;
        x = opa.p(x);
        x = std::clamp(x, -4.0, 4.0);
        x = shunt(x, vo);
        x = tone.p(x);
        out[n] = (float)(x * 1.67);
    }
    return out;
}

static void write(const std::string& path, const std::vector<float>& v)
{
    FILE* f = std::fopen(path.c_str(), "wb"); std::fwrite(v.data(), 4, v.size(), f); std::fclose(f);
}

int main(int argc, char** argv)
{
    std::string dir = argc > 1 ? argv[1] : ".";
    bool skipRef = argc > 2 && std::string(argv[2]) == "--skip-ref";
    const double secs = 1.0;
    const double freqs[] = { 220.0, 1000.0, 3700.0 }, amps[] = { 0.05, 0.25, 0.7 };
    const double dists[] = { 0.0, 5.0, 10.0 }, filters[] = { 0.3, 0.8 };
    for (double f0 : freqs) for (double amp : amps) for (double dist : dists) for (double flt : filters) {
        char tag[80];
        std::snprintf(tag, sizeof tag, "f%d_a%03d_d%02d_t%02d", (int)f0, (int)(amp * 100),
                      (int)dist, (int)(flt * 10));
        if (!skipRef) {
            write(dir + "/ref_" + tag + ".f32", reference(f0, amp, dist, flt, secs, 32));
            write(dir + "/ref64_" + tag + ".f32", reference(f0, amp, dist, flt, secs, 64));
        }
        const int N = (int)(secs * SR);
        RatState s = {};
        RatCoeffs k;
        rat_coeffs(&k, (float)dist, (float)flt, 1.0f);
        std::vector<float> o(N);
        for (int n = 0; n < N; ++n)
            o[n] = rat_process(&s, &k, (float)(amp * std::sin(2 * PI * f0 * n / SR)));
        write(dir + "/cand_" + tag + ".f32", o);
    }
    std::printf("done\n");
    return 0;
}
