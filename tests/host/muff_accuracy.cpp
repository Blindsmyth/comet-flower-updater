// CF Muff accuracy bench. Writes float32 outputs for a grid of sine tests:
//   ref_*   reference (muff_ref.h) at 32x, ideal decimation done by the scorer
//   ref64_* the same at 64x (convergence check)
//   mob_*   Comet Flower's shipping mobile core (FuzzMobileCore, 4x, 2048
//           cells) at 44.1 kHz: the fairness check of the pass criteria
//   cand_*  the candidate G1 core (effects/common/muff_g1.h) at 44.1 kHz
// tests/host/muff_accuracy.py scores them. Written by Claude; do not edit as
// part of the model work.
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
#include "muff_ref.h"
#include "FuzzMobileCore.h"
extern "C" {
#include "../../effects/common/muff_g1.h"
}

static const double PI = 3.14159265358979323846;
static const int SR = 44100;

static void write(const std::string& path, const std::vector<float>& v)
{
    FILE* f = std::fopen(path.c_str(), "wb"); std::fwrite(v.data(), 4, v.size(), f); std::fclose(f);
}

static std::vector<float> render_ref(double f0, double amp, float sus, float tone, int os, int cells)
{
    RefMuff m; m.prepare((double) SR * os, cells, sus, tone, 1.0f);
    const int N = SR * os;
    std::vector<float> o(N);
    for (int n = 0; n < N; ++n) o[n] = m.process((float) (amp * std::sin(2 * PI * f0 * n / (SR * (double) os))));
    return o;
}

int main(int argc, char** argv)
{
    std::string dir = argc > 1 ? argv[1] : ".";
    bool skipRef = argc > 2 && std::string(argv[2]) == "--skip-ref";
    const double freqs[] = { 220.0, 1000.0, 3700.0 }, amps[] = { 0.05, 0.25, 0.7 };
    const float sus[] = { 0.0f, 0.5f, 1.0f }, tones[] = { 0.3f, 0.8f };
    for (double f0 : freqs) for (double amp : amps) for (float s : sus) for (float t : tones) {
        char tag[80];
        std::snprintf(tag, sizeof tag, "f%d_a%03d_s%02d_t%02d", (int) f0, (int) (amp * 100),
                      (int) (s * 10), (int) (t * 10));
        if (!skipRef) {
            write(dir + "/ref_" + tag + ".f32", render_ref(f0, amp, s, t, 32, 65536));
            write(dir + "/ref64_" + tag + ".f32", render_ref(f0, amp, s, t, 64, 65536));
            MobileDsp::FuzzMobileCore mob; mob.prepare(SR, 4);
            MobileDsp::FuzzMobileCore::Params p; p.sustain = s; p.tone = t; p.volume = 1.0f;
            mob.setParams(p);
            std::vector<float> o(SR);
            for (int n = 0; n < SR; ++n) o[n] = mob.processSample((float) (amp * std::sin(2 * PI * f0 * n / SR)));
            write(dir + "/mob_" + tag + ".f32", o);
        }
        MuffState st = {};
        MuffCoeffs k;
        muff_coeffs(&k, s, t, 1.0f);
        std::vector<float> o(SR);
        for (int n = 0; n < SR; ++n) o[n] = muff_process(&st, &k, (float) (amp * std::sin(2 * PI * f0 * n / SR)));
        write(dir + "/cand_" + tag + ".f32", o);
    }
    std::printf("done\n");
    return 0;
}
