// rotx_test.cpp - runs the real CF Rotary kernel (effects/rotx/rotx.c) on the host with the
// pedal's calling layout (instance[1] coefficients, [2] state + guard word, [3] -> {base, end,
// size} work buffer; ctx[1] the 16-frame A/B bus), same harness style as
// tests/host/delayx_kernel_test.cpp. 32-bit build: the descriptor holds 32-bit addresses, as on
// the pedal. Build/run: tests/host/build_rotx_test.bat
//
// Checks (docs/helpers/FW_RND_BRIEF2_2026-10-22.md, job S6):
//  1. finite output (no NaN/Inf) for silence, full-scale sine and noise, at every corner of
//     Speed/Depth/Ramp/Mix, over 10 s each.
//  2. the Speed ramp reaches its target (worst case: Ramp 100, the slowest glide).
//  3. output level within 3 dB of input at Mix 100, Depth 0 (the crossover's horn+drum==x
//     identity should keep this at unity gain; see rotx.c's design comment).
//  4. the same guard behaviour CE2X/DLYX have: bad state guard, out-of-range coefficient, and a
//     missing work buffer all mute to silence rather than doing anything undefined.
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdint>

extern "C" {
#include "rotx.c"
}

static int fails = 0;
static void check(bool ok, const char *what) { std::printf("  %-62s %s\n", what, ok ? "ok" : "FAIL"); fails += !ok; }

static uint32_t rng = 54321u;
static float frand() { rng = rng * 1664525u + 1013904223u; return (float)(rng >> 8) / 8388608.0f - 1.0f; }

int main()
{
    static uint32_t state[64];
    static uint8_t wbuf[sizeof(RotLine) + 64];
    uint32_t base = ((uint32_t)(uintptr_t)wbuf + 7u) & ~7u;
    uint32_t desc[3] = { base, base + (uint32_t)sizeof(RotLine), (uint32_t)sizeof(RotLine) };
    float coef[16] = {};
    float bus[32];
    void *inst[4] = { nullptr, coef, state, desc };
    void *ctx[8] = { nullptr, bus };
    auto reset = [&] { std::memset(state, 0, sizeof state); state[SH_STATE_GUARD_WORD] = SH_STATE_GUARD; };
    auto knobs = [&](float speed, float depth, float ramp, float mix) {
        coef[SH_PARAM_SPEED] = speed; coef[SH_PARAM_DEPTH] = depth / 100.0f;
        coef[SH_PARAM_RAMP] = ramp / 100.0f; coef[SH_PARAM_MIX] = mix / 100.0f;
    };
    setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("CF Rotary kernel host test (state %u B, work buffer need %u B)\n",
                (unsigned)sizeof(KernelState), (unsigned)sizeof(RotLine));

    // 1. finite output: silence / full-scale sine / noise, at every Speed/Depth/Ramp/Mix
    //    corner, 10 s each (2^4 corners x 3 signals x 10 s = 480 s of simulated audio).
    bool finite_ok = true;
    const long N10 = 44100L * 10 / 16 * 16;
    const float speeds[2] = { 0.0f, 1.0f };
    for (int si = 0; si < 2; ++si)
    for (int di = 0; di < 2; ++di)
    for (int ri = 0; ri < 2; ++ri)
    for (int mi = 0; mi < 2; ++mi)
    for (int sig = 0; sig < 3; ++sig) {          // 0 silence, 1 full-scale sine, 2 noise
        reset(); coef[SH_COEFF_BYPASS] = 1.0f;
        knobs(speeds[si], di ? 100.0f : 0.0f, ri ? 100.0f : 0.0f, mi ? 100.0f : 0.0f);
        double phase = 0.0;
        for (long b = 0; b < N10; b += 16) {
            for (int i = 0; i < 16; ++i) {
                float x;
                if (sig == 0) x = 0.0f;
                else if (sig == 1) { phase += 2.0 * 3.14159265358979 * 440.0 / 44100.0; x = (float)std::sin(phase); }
                else x = frand();
                bus[i] = bus[i + 16] = x;
            }
            SH_AUDIO_FN(inst, ctx);
            for (int i = 0; i < 32; ++i) finite_ok &= (bool)std::isfinite(bus[i]);
        }
    }
    check(finite_ok, "finite output: silence/full-scale sine/noise, all 16 param corners, 10 s each");

    // 2. the Speed ramp reaches its target: settle slow, flip to fast at the slowest glide
    //    (Ramp 100), run 6 s (worst-case drum glide time chosen in rotx.c is ~4.4 s).
    reset(); coef[SH_COEFF_BYPASS] = 1.0f; knobs(0.0f, 50.0f, 100.0f, 50.0f);
    for (long b = 0; b < 44100L; b += 16) {
        for (int i = 0; i < 16; ++i) bus[i] = bus[i + 16] = 0.1f * frand();
        SH_AUDIO_FN(inst, ctx);
    }
    knobs(1.0f, 50.0f, 100.0f, 50.0f);           // flip Speed to fast, Ramp stays at its slowest
    const long N6 = 44100L * 6 / 16 * 16;
    for (long b = 0; b < N6; b += 16) {
        for (int i = 0; i < 16; ++i) bus[i] = bus[i + 16] = 0.1f * frand();
        SH_AUDIO_FN(inst, ctx);
    }
    KernelState *ks = (KernelState *)state;
    std::printf("  (after 6 s at Ramp=100: freq_h %.3f Hz (target %.1f), freq_d %.3f Hz (target %.1f))\n",
                ks->freq_h, ROT_HORN_FAST_HZ, ks->freq_d, ROT_DRUM_FAST_HZ);
    check(std::fabs(ks->freq_h - ROT_HORN_FAST_HZ) < 0.05f, "horn speed ramp reaches its target (Ramp=100, 6 s)");
    check(std::fabs(ks->freq_d - ROT_DRUM_FAST_HZ) < 0.05f, "drum speed ramp reaches its target (Ramp=100, 6 s)");

    // 3. output level within 3 dB of input at Mix 100, Depth 0 (1 s settle, then measure 1 s)
    reset(); coef[SH_COEFF_BYPASS] = 1.0f; knobs(1.0f, 0.0f, 50.0f, 100.0f);
    for (long b = 0; b < 44100L; b += 16) {
        for (int i = 0; i < 16; ++i) {
            double t = (b + i) / 44100.0;
            bus[i] = bus[i + 16] = 0.8f * (float)std::sin(2.0 * 3.14159265358979 * 440.0 * t);
        }
        SH_AUDIO_FN(inst, ctx);
    }
    double inRMS = 0.0, outRMS = 0.0; long cnt = 0;
    for (long b = 0; b < 44100L; b += 16) {
        float xa[16];
        for (int i = 0; i < 16; ++i) {
            double t = (44100.0 + b + i) / 44100.0;
            xa[i] = 0.8f * (float)std::sin(2.0 * 3.14159265358979 * 440.0 * t);
            bus[i] = bus[i + 16] = xa[i];
        }
        SH_AUDIO_FN(inst, ctx);
        for (int i = 0; i < 16; ++i) { inRMS += (double)xa[i] * xa[i]; outRMS += (double)bus[i] * bus[i]; ++cnt; }
    }
    inRMS = std::sqrt(inRMS / cnt); outRMS = std::sqrt(outRMS / cnt);
    double dB = 20.0 * std::log10(outRMS / inRMS);
    std::printf("  (Mix 100 / Depth 0: in RMS %.5f, out RMS %.5f, %.2f dB)\n", inRMS, outRMS, dB);
    check(std::fabs(dB) < 3.0, "output level within 3 dB of input at Mix 100, Depth 0");

    // 4. guards: same fail-closed-to-silence convention as CE2X/DLYX
    reset(); state[SH_STATE_GUARD_WORD] = 0; coef[SH_COEFF_BYPASS] = 1.0f; knobs(0.0f, 50.0f, 50.0f, 50.0f);
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    { bool mute = true; for (int i = 0; i < 32; ++i) mute &= bus[i] == 0.0f; check(mute, "bad state guard mutes"); }

    reset(); coef[SH_COEFF_BYPASS] = 1.0f; knobs(0.0f, 50.0f, 50.0f, 50.0f); coef[SH_PARAM_DEPTH] = 1.5f;
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    { bool mute = true; for (int i = 0; i < 32; ++i) mute &= bus[i] == 0.0f; check(mute, "out-of-range coefficient mutes"); }

    reset(); coef[SH_COEFF_BYPASS] = 1.0f; knobs(0.0f, 50.0f, 50.0f, 50.0f); inst[3] = nullptr;
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    { bool mute = true; for (int i = 0; i < 32; ++i) mute &= bus[i] == 0.0f; check(mute, "no work buffer mutes"); }

    std::printf(fails ? "FAILED (%d)\n" : "all passed\n", fails);
    return fails ? 1 : 0;
}
