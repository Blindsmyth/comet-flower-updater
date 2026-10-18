// CF Delay accuracy bench: effects/common/delay_g1.h (float, the pedal core) against Comet Flower's
// own DelayMobileCore (VirtualPedalBoardEngine/Source/MobileDsp, compiled as is: double ADAA, 1024-cell
// table) at 44.1 kHz, sample for sample on both outputs. Knobs set per 16-sample block, as on the pedal.
// Pass: every test's residual (both channels) below -60 dB re the reference's RMS.
// Written by Claude.
#include <cmath>
#include <cstdio>
#include <cstring>
#include <memory>
#include <vector>
#include "DelayMobileCore.h"
extern "C" {
#include "../../effects/common/delay_g1.h"
}

static const double PI = 3.14159265358979323846;

struct Test { const char* name; float amp; float t0, t1; float fb, mix; int kind; double secs; };

static float input(int kind, float amp, long n)
{
    double t = n / 44100.0;
    if (kind == 1) return (float)(amp * std::sin(2 * PI * 440 * t));
    // plucks: a decaying harmonic tone every 0.75 s (A2, E3, A3 cycle)
    static const double f0s[3] = { 110.0, 164.81, 220.0 };
    double tp = std::fmod(t, 0.75); int k = (int)(t / 0.75) % 3;
    double s = 0;
    for (int h = 1; h <= 8; ++h) s += std::sin(2 * PI * f0s[k] * h * tp) / h;
    return (float)(amp * 0.6 * s * std::exp(-tp * 4.0));
}

int main()
{
    const Test tests[] = {
        { "defaults_plucks",      0.5f, 420, 420, 0.30f, 0.30f, 0, 4 },
        { "regen092_loud",        0.9f, 300, 300, 0.92f, 0.50f, 0, 6 },
        { "regen092_sine",        0.5f, 250, 250, 0.92f, 0.50f, 1, 4 },
        { "quiet_plucks",         0.01f, 420, 420, 0.50f, 0.40f, 0, 4 },
        { "sine_fb06",            0.5f, 375, 375, 0.60f, 0.50f, 1, 3 },
        { "time_sweep_200_800",   0.5f, 200, 800, 0.40f, 0.40f, 0, 5 },
        { "max_2000ms",           0.5f, 2000, 2000, 0.50f, 0.50f, 0, 6 },
    };
    static DelayState st;
    int fails = 0;
    for (const auto& T : tests) {
        auto ref = std::make_unique<MobileDsp::DelayMobileCore>();
        ref->prepare(44100.0);
        std::memset(&st, 0, sizeof st);
        long N = (long)(T.secs * 44100) / 16 * 16;
        double e2L = 0, e2R = 0, r2L = 0, r2R = 0, emax = 0;
        bool first = true;
        for (long b = 0; b < N; b += 16) {
            float tms = (b < N / 2) ? T.t0 : T.t1;
            MobileDsp::DelayMobileCore::Params p; p.timeMs = tms; p.feedback = T.fb; p.mix = T.mix;
            ref->setParams(p);
            DelayCoeffs k; delay_coeffs(&k, tms, T.fb, T.mix);
            if (first) { delay_snap(&st, &k); first = false; }
            for (int i = 0; i < 16; ++i) {
                float x = input(T.kind, T.amp, b + i), rl, rr, cl, cr;
                ref->processSample(x, rl, rr);
                delay_process(&st, &k, x, &cl, &cr);
                e2L += (double)(cl - rl) * (cl - rl); e2R += (double)(cr - rr) * (cr - rr);
                r2L += (double)rl * rl; r2R += (double)rr * rr;
                emax = std::fmax(emax, std::fabs((double)cl - rl));
            }
        }
        double dl = 10 * std::log10(e2L / r2L + 1e-30), dr = 10 * std::log10(e2R / r2R + 1e-30);
        bool ok = dl < -60 && dr < -60;
        fails += !ok;
        std::printf("%-22s residual L %7.1f dB  R %7.1f dB  max|diff| %.2e  %s\n", T.name, dl, dr, emax, ok ? "ok" : "FAIL");
    }
    std::printf(fails ? "ACCURACY: FAIL (%d)\n" : "ACCURACY: PASS\n", fails);
    return fails ? 1 : 0;
}
