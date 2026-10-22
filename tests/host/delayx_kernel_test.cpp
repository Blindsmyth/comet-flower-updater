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

static void old_kernel_audio_fn(void **instance, void **ctx)
{
    const float *coef = (const float *)instance[1];
    float *eff = (float *)ctx[1];
    KernelState *s    = (KernelState *)instance[2];
    DelayState *d     = work_state(instance);
    DelayCoeffs k;
    float wl_b[SH_FRAMES], wr_b[SH_FRAMES];
    int i;

    unsigned ok = d != 0;
#ifdef SH_STATE_GUARD
    if (((const uint32_t *)instance[2])[SH_STATE_GUARD_WORD] != SH_STATE_GUARD)
        ok = 0;
#endif
    float fade = coef[SH_COEFF_BYPASS];
    float kt   = coef[SH_PARAM_TIME];
    float kr   = coef[SH_PARAM_REGEN];
    float km   = coef[SH_PARAM_MIX];
    if (!(fade >= 0.0f && fade <= 1.0f)) ok = 0;
    if (!(kt >= 0.0f && kt <= 1.0f)) ok = 0;
    if (!(kr >= 0.0f && kr <= 1.0f)) ok = 0;
    if (!(km >= 0.0f && km <= 1.0f)) ok = 0;
    if (!ok) {
        for (i = 0; i < SH_FRAMES; i++) {
            eff[i] = 0.0f;
            eff[i + SH_CH_B_OFFSET] = 0.0f;
        }
        return;
    }

    if (s->primed != 1.0f) {
        s->fb = kr; s->mix = km;
    } else {
        s->fb  += KNOB_SMOOTH * (kr - s->fb);
        s->mix += KNOB_SMOOTH * (km - s->mix);
    }
    delay_coeffs(&k, 2000.0f * kt, 0.92f * s->fb, s->mix);
    if (s->primed != 1.0f) {
        d->wp = 0; d->written = 0; d->lp = 0.0f; d->x1 = 0.0f;
        delay_snap(d, &k);
        s->primed = 1.0f;
    }

    delay_block(d, &k, eff, wl_b, wr_b, SH_FRAMES);

    for (i = 0; i < SH_FRAMES; i++) {
        float da = eff[i], db = eff[i + SH_CH_B_OFFSET];
        float wl = wl_b[i], wr = wr_b[i], a, b;
        if (!(wl > -8.0f && wl < 8.0f)) wl = 0.0f;
        if (!(wr > -8.0f && wr < 8.0f)) wr = 0.0f;
        a = da + fade * (wl - da);
        b = db + fade * (wr - db);
        if (!(a > -8.0f && a < 8.0f)) a = 0.0f;
        if (!(b > -8.0f && b < 8.0f)) b = 0.0f;
        eff[i] = a;
        eff[i + SH_CH_B_OFFSET] = b;
    }
}

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
    auto knobs = [&](float t_ms, float regen, float mix, float tail = 1.0f) {
        coef[SH_PARAM_TIME] = t_ms / 2000.0f;
        coef[SH_PARAM_REGEN] = regen / 92.0f;
        coef[SH_PARAM_MIX] = mix / 100.0f;
        coef[SH_PARAM_TAIL] = tail;
    };
    setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("CF Delay kernel host test (state %u B, work buffer need %u B of %u)\n",
                (unsigned)sizeof(KernelState), (unsigned)sizeof(DelayState), 0x81330u);

    // 1. impulse: echo at 420 ms on L, 440 ms on R; second echo scaled by regen (through LP + tanh)
    std::memset(wbuf, 0x7f, sizeof wbuf);          // garbage in the buffer: must never be heard
    reset(); coef[SH_COEFF_BYPASS] = 1.0f; knobs(420, 50, 50);
    const long N = 44100 * 2 / 16 * 16;          // whole blocks: 88200 overran L and R by 8 samples
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
    reset(); knobs(420, 30, 30, 1.5f); // out-of-range tail
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    mute = true; for (int i = 0; i < 32; ++i) mute &= bus[i] == 0.0f;
    check(mute, "out-of-range tail coefficient mutes");
    reset(); knobs(420, 30, 30); inst[3] = nullptr;
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    mute = true; for (int i = 0; i < 32; ++i) mute &= bus[i] == 0.0f;
    check(mute, "no work buffer mutes");

    // Restore inst[3]
    inst[3] = desc;

    // 5. Tail 0 bit-identical proof against the old kernel reference
    static uint32_t state_ref[64];
    static uint8_t wbuf_ref[0x81330 + 8];
    uint32_t base_ref = ((uint32_t)(uintptr_t)wbuf_ref + 7u) & ~7u;
    uint32_t desc_ref[3] = { base_ref, base_ref + 0x81330u, 0x81330u };
    float coef_ref[16] = {};
    float bus_ref[32];
    void* inst_ref[4] = { nullptr, coef_ref, state_ref, desc_ref };
    void* ctx_ref[8] = { nullptr, bus_ref };

    reset();
    std::memset(state_ref, 0, sizeof state_ref);
    state_ref[SH_STATE_GUARD_WORD] = SH_STATE_GUARD;
    std::memset(wbuf, 0x5a, sizeof wbuf);
    std::memset(wbuf_ref, 0x5a, sizeof wbuf_ref);

    knobs(420, 60, 50, 0.0f); // Tail = 0
    coef_ref[SH_PARAM_TIME] = 420.0f / 2000.0f;
    coef_ref[SH_PARAM_REGEN] = 60.0f / 92.0f;
    coef_ref[SH_PARAM_MIX] = 50.0f / 100.0f;
    coef[SH_COEFF_BYPASS] = coef_ref[SH_COEFF_BYPASS] = 1.0f;

    bool bit_identical = true;
    for (long b = 0; b < 44100 * 2; b += 16) {
        float f = (b < 20000) ? 1.0f : (b < 30000) ? 0.4f : 0.0f;
        coef[SH_COEFF_BYPASS] = coef_ref[SH_COEFF_BYPASS] = f;
        for (int i = 0; i < 16; ++i) {
            float s = (b + i == 0) ? 1.0f : 0.3f * std::sin(0.02f * (b + i));
            bus[i] = bus_ref[i] = s;
            bus[i + 16] = bus_ref[i + 16] = 0.5f * s;
        }
        SH_AUDIO_FN(inst, ctx);
        old_kernel_audio_fn(inst_ref, ctx_ref);
        for (int i = 0; i < 32; ++i) {
            if (std::memcmp(&bus[i], &bus_ref[i], sizeof(float)) != 0)
                bit_identical = false;
        }
    }
    check(bit_identical, "Tail 0 output is bit-identical to old kernel reference");

    // 6. Tail 1: with fade 0 from the start, nothing enters the line (output == input)
    reset();
    knobs(420, 60, 50, 1.0f);
    coef[SH_COEFF_BYPASS] = 0.0f;
    bool pass_thru = true;
    for (long b = 0; b < 44100; b += 16) {
        float in_a[16], in_b[16];
        for (int i = 0; i < 16; ++i) {
            in_a[i] = std::sin(0.03f * (b + i));
            in_b[i] = 0.7f * std::cos(0.04f * (b + i));
            bus[i] = in_a[i];
            bus[i + 16] = in_b[i];
        }
        SH_AUDIO_FN(inst, ctx);
        for (int i = 0; i < 16; ++i) {
            if (bus[i] != in_a[i] || bus[i + 16] != in_b[i])
                pass_thru = false;
        }
    }
    check(pass_thru, "Tail 1 with fade 0 from start: output == input");

    // 7. Tail 1: feed a burst then set fade 0: repeats keep decaying, energy after 1s > 0, after 30s near 0, no NaN
    reset();
    knobs(420, 50, 50, 1.0f);
    coef[SH_COEFF_BYPASS] = 1.0f;
    const long BURST_LEN = 4410; // 100 ms burst
    const long TOTAL_LEN = 44100 * 32 / 16 * 16; // 32 seconds
    double energy_1s = 0;
    double energy_30s = 0;
    bool all_finite = true;

    for (long b = 0; b < TOTAL_LEN; b += 16) {
        for (int i = 0; i < 16; ++i) {
            long t = b + i;
            bus[i] = (t < BURST_LEN) ? 0.8f * std::sin(0.05f * t) : 0.0f;
            bus[i + 16] = (t < BURST_LEN) ? 0.8f * std::cos(0.05f * t) : 0.0f;
        }
        // At 100 ms, effect is switched OFF (fade = 0)
        coef[SH_COEFF_BYPASS] = (b < BURST_LEN) ? 1.0f : 0.0f;
        SH_AUDIO_FN(inst, ctx);
        for (int i = 0; i < 32; ++i) {
            all_finite &= std::isfinite(bus[i]);
            long t = b + (i % 16);
            if (t >= 44100 && t < 44100 * 2) {
                energy_1s += (double)bus[i] * bus[i];
            }
            if (t >= 44100 * 30 && t < 44100 * 31) {
                energy_30s += (double)bus[i] * bus[i];
            }
        }
    }
    check(all_finite, "Tail 1 with fade 0: no NaN or Inf during 32 s ringout");
    check(energy_1s > 0.01, "Tail 1 with fade 0: energy after 1 s > 0 (repeats ring out)");
    check(energy_30s < 1e-6, "Tail 1 with fade 0: energy after 30 s near 0 (decayed)");
    std::printf("  (energy after 1 s = %.6f, energy after 30 s = %.10f)\n", energy_1s, energy_30s);

    std::printf(fails ? "FAILED (%d)\n" : "all passed\n", fails);
    return fails ? 1 : 0;
}
