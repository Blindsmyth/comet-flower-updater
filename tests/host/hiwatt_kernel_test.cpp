// Runs the real G1 kernel (effects/hiwatt/hiwatt.c, with the sh_params.h the
// stomphacks build generated) on the host with the pedal's calling layout:
// instance[1] = coefficients, instance[2] = state (+ guard word), ctx[1] =
// in-place 16-frame A/B bus. Checks: output finite and bounded over knob
// sweeps, bypass (fade 0) passes the dry signal, a bad guard or an
// out-of-range coefficient mutes, matches hw_block for the same knobs.
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>
extern "C" {
#include "hiwatt.c"
}

static int fails = 0;
static void check(bool ok, const char* what) { std::printf("  %-52s %s\n", what, ok ? "ok" : "FAIL"); fails += !ok; }

int main()
{
    static uint32_t state[96];
    float coef[16] = {};
    float bus[32];
    void* inst[3] = { nullptr, coef, state };
    void* ctx[8] = { nullptr, bus };
    auto reset = [&] { std::memset(state, 0, sizeof state); state[SH_STATE_GUARD_WORD] = SH_STATE_GUARD; };
    auto knobs = [&](float v, float t, float m, float b, float p, float s, float cab) {
        coef[SH_PARAM_VOLUME] = v; coef[SH_PARAM_TREBLE] = t; coef[SH_PARAM_MIDDLE] = m;
        coef[SH_PARAM_BASS] = b; coef[SH_PARAM_PRESENCE] = p; coef[SH_PARAM_MASTER] = s;
        coef[SH_PARAM_CAB] = cab;
    };
    const double PI = 3.14159265358979323846;

    // 1. knob sweep, loud input: finite, bounded, not silent
    reset(); coef[SH_COEFF_BYPASS] = 1.0f;
    double peak = 0, e2 = 0; bool finite = true; long n = 0;
    for (int blk = 0; blk < 44100 * 6 / 16; ++blk) {
        float ph = (float)(blk % 2000) / 2000.0f;
        knobs(ph, 1 - ph, ph, 0.5f, ph, 0.3f + 0.7f * ph, blk % 3000 < 1500 ? 1.0f : 0.0f);
        for (int i = 0; i < 16; ++i) {
            float x = 0.9f * (float)std::sin(2 * PI * 196.0 * n / 44100.0) * (float)std::sin(PI * n / 30000.0);
            bus[i] = x; bus[i + 16] = x; ++n;
        }
        SH_AUDIO_FN(inst, ctx);
        for (int i = 0; i < 32; ++i) {
            finite = finite && std::isfinite(bus[i]);
            peak = std::max(peak, (double)std::fabs(bus[i]));
            e2 += bus[i] * bus[i];
        }
    }
    double rms = std::sqrt(e2 / (n * 2));
    std::printf("  sweep: peak %.3f, rms %.4f (%.1f dBFS)\n", peak, rms, 20 * std::log10(rms));
    check(finite && peak < 4.0 && rms > 1e-3, "knob sweep: finite, bounded, audible");
    check(std::fabs(bus[0] - bus[16]) < 1e-6f, "both channels carry the wet signal");

    // 2. bypass: fade 0 passes the dry signal on both channels
    coef[SH_COEFF_BYPASS] = 0.0f; knobs(0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 1.0f);
    bool dry = true;
    for (int i = 0; i < 16; ++i) { bus[i] = 0.1f * i; bus[i + 16] = -0.05f * i; }
    SH_AUDIO_FN(inst, ctx);
    for (int i = 0; i < 16; ++i) dry = dry && bus[i] == 0.1f * i && bus[i + 16] == -0.05f * i;
    check(dry, "bypass (fade 0) is exact dry, per channel");

    // 3. guard broken -> silence; coefficient out of range -> silence
    coef[SH_COEFF_BYPASS] = 1.0f;
    state[SH_STATE_GUARD_WORD] = 0;
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    bool mute = true; for (int i = 0; i < 32; ++i) mute = mute && bus[i] == 0.0f;
    check(mute, "bad state guard mutes");
    reset(); coef[SH_PARAM_MASTER] = 1.5f;
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    mute = true; for (int i = 0; i < 32; ++i) mute = mute && bus[i] == 0.0f;
    check(mute, "out-of-range coefficient mutes");

    // 4. steady knobs: the kernel equals hw_block with the same (settled) knobs
    reset(); knobs(0.6f, 0.4f, 0.7f, 0.3f, 0.8f, 0.5f, 1.0f); coef[SH_COEFF_BYPASS] = 1.0f;
    HwState ref = {}; HwCoeffs k;
    hw_coeffs(&k, 0.6f, 0.4f, 0.7f, 0.3f, 0.5f, 0.8f);
    double maxd = 0; n = 0;
    for (int blk = 0; blk < 2000; ++blk) {
        for (int i = 0; i < 16; ++i) { float x = 0.3f * (float)std::sin(2 * PI * 330.0 * n / 44100.0); bus[i] = bus[i + 16] = x; ++n; }
        float in[16]; std::memcpy(in, bus, sizeof in);
        SH_AUDIO_FN(inst, ctx);
        hw_block(&ref, &k, in, 1);
        for (int i = 0; i < 16; ++i) maxd = std::max(maxd, (double)std::fabs(bus[i] - in[i]));
    }
    std::printf("  kernel vs hw_block: max |diff| %.2e\n", maxd);
    check(maxd < 1e-6, "kernel == hw_block for steady knobs");

    std::printf(fails ? "FAILED (%d)\n" : "all passed\n", fails);
    return fails ? 1 : 0;
}
