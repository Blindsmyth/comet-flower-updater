// cfmaster_test.cpp - Host 32-bit test for the CF Master kernel
// (David Gilmour's 1979 Comfortably Numb studio rig).
// Verifies memory bounds, bypass transparency, audio integrity,
// stereo imaging, loud-input stability, and failure handling.
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <vector>

#define SH_PARAMS_H
#include "cfm_sh_params.h"

extern "C" {
#include "hw_blob.h"
#include "cfmaster.c"
}

static int fails = 0;
static void check(bool ok, const char* what) {
    std::printf("  %-66s %s\n", what, ok ? "ok" : "FAIL");
    fails += !ok;
}

int main()
{
    std::printf("CF Master host test (C6745 1979 Comfortably Numb Rig)\n");

    // 1. Memory and Layout Audits
    std::printf("  KernelState: %zu bytes (budget: %d B)\n", sizeof(CfmKernelState), SH_STATE_BYTES);
    std::printf("  WorkBuffer:  %zu bytes (budget: %u B)\n", sizeof(CfmWorkBuffer), 0x81330u);
    check(sizeof(CfmKernelState) <= SH_STATE_BYTES, "KernelState fits within slot state limit (<= 392 B)");
    check(sizeof(CfmWorkBuffer) <= 0x81330u, "WorkBuffer fits within slot work buffer (<= 529,200 B)");

    // 2. Setup mock DSP instance and context
    float coef[16];
    std::memset(coef, 0, sizeof(coef));
    coef[SH_COEFF_BYPASS]      = 1.0f; // Active
    coef[SH_PARAM_MUFF_SUST]   = 0.75f;
    coef[SH_PARAM_MUFF_TONE]   = 0.50f;
    coef[SH_PARAM_MUFF_VOL]    = 0.70f;
    coef[SH_PARAM_MIST_RATE]   = 0.35f;
    coef[SH_PARAM_MIST_COLR]   = 0.65f;
    coef[SH_PARAM_DLY_TIME]    = 0.48f; // 480 ms
    coef[SH_PARAM_DLY_MIX]     = 0.30f;
    coef[SH_PARAM_AMP_DRIVE]   = 0.60f;
    coef[SH_PARAM_AMP_MSTR]    = 0.80f;
    coef[SH_PARAM_ROTOR]       = 0.50f; // Slow rotor
    coef[SH_PARAM_ROT_SPEED]   = 0.50f;
    coef[SH_PARAM_RIG_BLEND]   = 0.50f;

    uint8_t state_mem[SH_STATE_BYTES];
    std::memset(state_mem, 0, sizeof(state_mem));
    ((uint32_t *)state_mem)[SH_STATE_GUARD_WORD] = SH_STATE_GUARD;

    std::vector<uint8_t> work_mem(sizeof(CfmWorkBuffer) + 64, 0);
    uintptr_t raw_ptr = (uintptr_t)work_mem.data();
    uintptr_t aligned_ptr = (raw_ptr + 7u) & ~((uintptr_t)7u);
    uint32_t wb[3] = {
        (uint32_t)aligned_ptr,
        (uint32_t)(aligned_ptr + sizeof(CfmWorkBuffer)),
        (uint32_t)sizeof(CfmWorkBuffer)
    };

    void *instance[4] = {
        nullptr,            // [0]
        coef,               // [1] parameters
        state_mem,          // [2] small state
        wb                  // [3] work buffer descriptor
    };

    float eff[32];
    void *ctx[4] = { nullptr, eff, nullptr, nullptr };

    // 3. Check Bypass Transparency (fade == 0.0)
    {
        coef[SH_COEFF_BYPASS] = 0.0f;
        for (int i = 0; i < 16; ++i) {
            eff[i] = 0.123f + 0.01f * (float)i;
            eff[i + 16] = -0.456f + 0.02f * (float)i;
        }
        float expected_a[16], expected_b[16];
        std::memcpy(expected_a, &eff[0], 16 * sizeof(float));
        std::memcpy(expected_b, &eff[16], 16 * sizeof(float));

        SH_AUDIO_FN(instance, ctx);

        bool bypass_clean = true;
        for (int i = 0; i < 16; ++i) {
            if (eff[i] != expected_a[i] || eff[i + 16] != expected_b[i])
                bypass_clean = false;
        }
        check(bypass_clean, "Bypass mode (fade=0) passes audio exactly bit-identical");
    }

    // 4. Active Rig Processing & Audio Integrity
    coef[SH_COEFF_BYPASS] = 1.0f;
    const int num_blocks = 200; // ~72 ms
    bool bounded = true;
    bool stereo_active = false;
    float peak = 0.0f;

    for (int b = 0; b < num_blocks; ++b) {
        // Feed 1 kHz sine wave
        for (int i = 0; i < 16; ++i) {
            float t = (float)(b * 16 + i) / 44100.0f;
            eff[i] = 0.25f * std::sin(2.0f * 3.14159265f * 1000.0f * t);
            eff[i + 16] = eff[i];
        }

        SH_AUDIO_FN(instance, ctx);

        for (int i = 0; i < 16; ++i) {
            float yl = eff[i];
            float yr = eff[i + 16];
            if (std::isnan(yl) || std::isnan(yr) || std::isinf(yl) || std::isinf(yr))
                bounded = false;
            if (std::abs(yl) > 8.0f || std::abs(yr) > 8.0f)
                bounded = false;
            if (std::abs(yl) > peak) peak = std::abs(yl);
            if (std::abs(yr) > peak) peak = std::abs(yr);
            if (std::abs(yl - yr) > 1e-4f)
                stereo_active = true;
        }
    }
    std::printf("  (Peak level after full rig: %.3f V)\n", peak);
    check(bounded, "Output remains finite, non-NaN, and strictly within [-8V, 8V]");
    check(stereo_active, "Stereo imaging active (Yamaha RA-200 miked cabinet divergence)");
    check(peak > 0.05f, "Rig audio produces valid non-zero tone");

    // 5. Overload / Extreme Signal Handling (+40V burst)
    {
        bool overload_safe = true;
        for (int i = 0; i < 16; ++i) {
            eff[i] = 40.0f;
            eff[i + 16] = -40.0f;
        }
        SH_AUDIO_FN(instance, ctx);
        for (int i = 0; i < 32; ++i) {
            if (std::isnan(eff[i]) || std::isinf(eff[i]) || std::abs(eff[i]) > 8.0f)
                overload_safe = false;
        }
        check(overload_safe, "Massive overload input (+40V) remains clamped and stable");
    }

    // 6. Security & Guard Verifications
    {
        // Bad state guard must mute
        ((uint32_t *)state_mem)[SH_STATE_GUARD_WORD] = 0xBADF00Du;
        for (int i = 0; i < 32; ++i) eff[i] = 1.0f;
        SH_AUDIO_FN(instance, ctx);
        bool muted = true;
        for (int i = 0; i < 32; ++i) if (eff[i] != 0.0f) muted = false;
        check(muted, "Corrupt state guard word causes immediate silent mute");
        ((uint32_t *)state_mem)[SH_STATE_GUARD_WORD] = SH_STATE_GUARD;
    }

    {
        // Null work buffer must mute
        void *bad_instance[4] = { nullptr, coef, state_mem, nullptr };
        for (int i = 0; i < 32; ++i) eff[i] = 1.0f;
        SH_AUDIO_FN(bad_instance, ctx);
        bool muted = true;
        for (int i = 0; i < 32; ++i) if (eff[i] != 0.0f) muted = false;
        check(muted, "Missing or unallocated work buffer descriptor causes silent mute");
    }

    std::printf("\nCF Master Test Summary: %d failures\n", fails);
    return fails ? 1 : 0;
}
