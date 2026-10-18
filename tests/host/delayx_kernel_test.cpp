// Runs the real CF Delay kernel (effects/delayx/delayx.c) on the host with the pedal's calling layout
// (instance[1] coefficients, [2] state + guard word, [3] -> {base, end, size} work buffer; ctx[1]
// the 16-frame A/B bus). 32-bit build: the descriptor holds 32-bit addresses, as on the pedal.
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <vector>
extern "C" {
/* the saturation table as a static array: on the pedal the same 1024 floats come from the
   effect's const_blob (effects/delayx/blob.bin, written from this header) */
#include "ce2_sat_table.h"
#include "delayx.c"
}
static int fails = 0;
static void check(bool ok, const char* what) { std::printf("  %-58s %s\n", what, ok ? "ok" : "FAIL"); fails += !ok; }

int main()
{
    static uint32_t state[64];
    static uint8_t wbuf[0x81330 + 8];
    uint32_t base = ((uint32_t)(uintptr_t)wbuf + 7u) & ~7u;
    uint32_t desc[3] = { base, base + 0x81330u, 0x81330u };
    float coef[16] = {};
    float bus[32];
    void* inst[4] = { nullptr, coef, state, desc };
    void* ctx[8] = { nullptr, bus };
    auto reset = [&] { std::memset(state, 0, sizeof state); state[SH_STATE_GUARD_WORD] = SH_STATE_GUARD; };
    auto knobs = [&](float t_ms, float regen, float mix) {
        coef[SH_PARAM_TIME] = t_ms / 2000.0f; coef[SH_PARAM_REGEN] = regen / 92.0f; coef[SH_PARAM_MIX] = mix / 100.0f;
    };
    setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("CF Delay kernel host test (state %u B, work buffer need %u B of %u)\n",
                (unsigned)sizeof(KernelState), (unsigned)sizeof(DelayState), 0x81330u);

    // 1. impulse: echo at 420 ms on L, 440 ms on R; second echo scaled by regen (through LP + tanh)
    std::memset(wbuf, 0x7f, sizeof wbuf);          // garbage in the buffer: must never be heard
    reset(); coef[SH_COEFF_BYPASS] = 1.0f; knobs(420, 50, 50);
    const long N = 44100 * 2;
    std::vector<float> L(N), R(N);
    bool finite = true;
    for (long b = 0; b < N; b += 16) {
        for (int i = 0; i < 16; ++i) bus[i] = bus[i + 16] = (b + i == 0) ? 1.0f : 0.0f;
        SH_AUDIO_FN(inst, ctx);
        for (int i = 0; i < 16; ++i) { L[b + i] = bus[i]; R[b + i] = bus[i + 16]; finite &= std::isfinite(bus[i]) && std::isfinite(bus[i + 16]); }
    }
    auto argmax = [&](const std::vector<float>& v, long a, long e) { long m = a; for (long i = a; i < e; ++i) if (std::fabs(v[i]) > std::fabs(v[m])) m = i; return m; };
    long eL = argmax(L, 100, 30000), eR = argmax(R, 100, 30000), e2 = argmax(L, 30000, 60000);
    check(finite, "output finite");
    check(std::fabs(L[0] - 0.5f) < 1e-6f && std::fabs(R[0] - 0.5f) < 1e-6f, "dry = 1 - Mix at the impulse");
    check(std::labs(eL - 18522) <= 1, "first echo on L at 420 ms (18522 samples)");
    check(std::labs(eR - (18522 + 882)) <= 1, "first echo on R 20 ms later");
    std::printf("  (echo 1 at %ld amp %.4f, echo 2 at %ld amp %.4f)\n", eL, L[eL], e2, L[e2]);
    // the feedback one-pole (3.5 kHz) and the ADAA half-sample smear the impulse: peak a few samples late
    check(std::labs(e2 - 2 * 18522) <= 8 && std::fabs(L[e2]) < std::fabs(L[eL]) * 0.6f, "second echo at 840 ms (+-8 samples), quieter (regen 0.5)");
    double pre = 0; for (long i = 1; i < 18000; ++i) pre = std::fmax(pre, std::fabs(L[i]) + std::fabs(R[i]));
    check(pre < 1e-6, "silence before the first echo (garbage in the buffer never read)");

    // 2. bypass: exact dry per channel
    reset(); coef[SH_COEFF_BYPASS] = 0.0f; knobs(300, 80, 100);
    bool exact = true;
    for (long b = 0; b < 44100; b += 16) {
        float xa[16], xb[16];
        for (int i = 0; i < 16; ++i) { xa[i] = std::sin(0.01f * (b + i)); xb[i] = 0.3f * std::cos(0.02f * (b + i)); bus[i] = xa[i]; bus[i + 16] = xb[i]; }
        SH_AUDIO_FN(inst, ctx);
        for (int i = 0; i < 16; ++i) exact &= bus[i] == xa[i] && bus[i + 16] == xb[i];
    }
    check(exact, "bypass (fade 0) passes the dry signal exactly");

    // 3. regen at max with a loud input stays bounded
    reset(); coef[SH_COEFF_BYPASS] = 1.0f; knobs(150, 92, 100);
    float peak = 0;
    for (long b = 0; b < 44100 * 8; b += 16) {
        for (int i = 0; i < 16; ++i) bus[i] = bus[i + 16] = (b < 44100) ? 0.9f * std::sin(0.05f * (b + i)) : 0.0f;
        SH_AUDIO_FN(inst, ctx);
        for (int i = 0; i < 32; ++i) peak = std::fmax(peak, std::fabs(bus[i]));
    }
    check(peak < 2.0f, "regen 92 + loud input: bounded (tanh at the write node)");

    // 4. guards
    reset(); state[SH_STATE_GUARD_WORD] = 0; coef[SH_COEFF_BYPASS] = 1.0f; knobs(420, 30, 30);
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    bool mute = true; for (int i = 0; i < 32; ++i) mute &= bus[i] == 0.0f;
    check(mute, "bad state guard mutes");
    reset(); coef[SH_PARAM_REGEN] = 1.5f;
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    mute = true; for (int i = 0; i < 32; ++i) mute &= bus[i] == 0.0f;
    check(mute, "out-of-range coefficient mutes");
    reset(); knobs(420, 30, 30); inst[3] = nullptr;
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    mute = true; for (int i = 0; i < 32; ++i) mute &= bus[i] == 0.0f;
    check(mute, "no work buffer mutes");

    std::printf(fails ? "FAILED (%d)\n" : "all passed\n", fails);
    return fails ? 1 : 0;
}
