// Compare the G1 port (effects/drv808/ts808_core.h) against the Comet Flower
// original (MobileDsp::DriveMobileCore) on identical input and settings.
// Build: tests/host/build_drv808_compare.bat (needs the Comet Flower source).
#include <cmath>
#include <cstdio>
#include <vector>
#include "MobileDsp/DriveMobileCore.h"
extern "C" {
#include "../../effects/drv808/ts808_core.h"
}

static std::vector<float> testSignal(int sr)
{
    // plucked notes (decaying harmonic stacks) at guitar-like level, then a
    // log sine sweep 40 Hz..10 kHz, then silence
    std::vector<float> x;
    const double notes[] = { 82.41, 110.0, 146.83, 196.0, 246.94, 329.63 };
    for (double f0 : notes)
        for (int n = 0; n < sr / 2; ++n) {
            double t = (double)n / sr, env = std::exp(-t * 4.0), s = 0;
            for (int h = 1; h <= 8; ++h) s += std::sin(2 * M_PI * f0 * h * t) / h;
            x.push_back((float)(0.45 * env * s));
        }
    const int ns = sr * 2;
    for (int n = 0; n < ns; ++n) {
        double t = (double)n / sr, T = 2.0;
        double ph = 2 * M_PI * 40.0 * T / std::log(250.0) * (std::exp(t / T * std::log(250.0)) - 1);
        x.push_back((float)(0.5 * std::sin(ph)));
    }
    x.resize(x.size() + sr / 4, 0.0f);
    return x;
}

int main()
{
    const int sr = 44100, block = 16;
    std::vector<float> in = testSignal(sr);
    const float drives[] = { 0.0f, 4.5f, 10.0f }, tones[] = { 0.0f, 0.6f, 1.0f };
    double worst = -1000;
    for (float d : drives) for (float t : tones) {
        MobileDsp::DriveMobileCore ref;
        ref.prepare(sr);
        MobileDsp::DriveMobileCore::Params p; p.drive = d; p.tone = t; p.level = -6.0f;
        ref.setParams(p);
        Ts808State st = {}; Ts808Coeffs k;
        double e2 = 0, s2 = 0, emax = 0, peak = 0;
        for (size_t n = 0; n < in.size(); n += block) {
            ref.setParams(p);
            ts808_coeffs(&k, d, t, std::pow(10.0f, -6.0f * 0.05f));
            for (size_t i = n; i < n + block && i < in.size(); ++i) {
                float a = ref.processSample(in[i]);
                float b = ts808_process(&st, &k, in[i]);
                double e = (double)a - b;
                e2 += e * e; s2 += (double)a * a;
                if (std::fabs(e) > emax) emax = std::fabs(e);
                if (std::fabs(a) > peak) peak = std::fabs(a);
            }
        }
        double rel = 10 * std::log10(e2 / s2);
        if (rel > worst) worst = rel;
        std::printf("drive %4.1f tone %.1f : error %7.1f dB rel  (max |err| %.2e, ref peak %.3f)\n",
                    d, t, rel, emax, peak);
    }
    std::printf("worst case: %.1f dB\n", worst);
    return worst < -80.0 ? 0 : 1;
}
