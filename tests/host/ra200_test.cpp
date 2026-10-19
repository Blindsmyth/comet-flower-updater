// ra200_test.cpp - CF RA200 (effects/ra200x/ra200x.c, core effects/common/ra200_g1.h) on the host, 32-bit
// (the work-buffer descriptor holds 32-bit addresses, as on the pedal). Checks:
//  1. the AB763 stack topology of ra_net1: nodal analysis of the stack alone (ideal source, open output),
//     written here independently in double complex, against Yeh & Smith's closed form for the Fender tone
//     stack (DAFx 2006);
//  2. the discretised network 1 (mna_derive at 44.1 kHz, delta form) against the same circuit's analog
//     response with the plate source and the volume pot, several knob settings;
//  3. the kernel: guards mute, bypass passes exactly, loud input stays bounded and finite, the preamp's
//     level at noon, and the rotor: sideband spacing around a 3 kHz tone = 3 x the rotor rate (three
//     identical speakers at 120 degrees), slow and fast, after spin-up.
// Build/run: tests/host/build_ra200_test.bat (needs the stomphacks build's sh_params.h).
#include <cmath>
#include <complex>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <vector>
extern "C" {
#include "hw_blob.h"
#include "ra200x.c"
}
typedef std::complex<double> cd;
static int fails = 0;
static void check(bool ok, const char* what) { std::printf("  %-66s %s\n", what, ok ? "ok" : "FAIL"); fails += !ok; }

// ---- 1 + 2: independent nodal analysis (double complex) --------------------------------------------------
struct Net {
    int n; std::vector<cd> Y, I;
    explicit Net(int nodes) : n(nodes), Y(nodes * nodes), I(nodes) {}
    void y(int i, int j, cd g) {                 // admittance between i and j (-1 = ground)
        if (i >= 0) Y[i * n + i] += g;
        if (j >= 0) Y[j * n + j] += g;
        if (i >= 0 && j >= 0) { Y[i * n + j] -= g; Y[j * n + i] -= g; }
    }
    std::vector<cd> solve() {                    // Gauss with partial pivoting
        std::vector<cd> a = Y, b = I;
        for (int c = 0; c < n; ++c) {
            int p = c;
            for (int r = c + 1; r < n; ++r) if (std::abs(a[r * n + c]) > std::abs(a[p * n + c])) p = r;
            for (int k = 0; k < n; ++k) std::swap(a[c * n + k], a[p * n + k]);
            std::swap(b[c], b[p]);
            for (int r = c + 1; r < n; ++r) {
                cd f = a[r * n + c] / a[c * n + c];
                for (int k = c; k < n; ++k) a[r * n + k] -= f * a[c * n + k];
                b[r] -= f * b[c];
            }
        }
        std::vector<cd> x(n);
        for (int c = n - 1; c >= 0; --c) {
            cd s = b[c];
            for (int k = c + 1; k < n; ++k) s -= a[c * n + k] * x[k];
            x[c] = s / a[c * n + c];
        }
        return x;
    }
};
static const double C1 = 250e-12, C2 = 0.1e-6, C3 = 0.047e-6, R1 = 250e3, R2 = 250e3, R3 = 10e3, R4 = 100e3;
static double wip(double r) { return r < 20.0 ? 20.0 : r; }

// the stack alone: ideal source at P, output = treble wiper, open; t, l, m = pot fractions (Yeh's convention:
// t = treble wiper position from the bottom, l = bass in circuit, m = mid in circuit).
// divider = Yeh & Smith's wiring of the mid pot (bass pot to its top, mid cap to its wiper); otherwise the
// F-2B as R.G. Keen draws it and ra_net1 builds it (mid cap and bass pot at the top of the mid rheostat).
static cd stack_nodal(double f, double t, double l, double m, bool divider)
{
    enum { A = 0, W, B, X, MD, P, MW };
    Net net(7);
    cd s(0, 2 * M_PI * f);
    const double G = 1e6;                        // the ideal source: P tied to 1 V through a huge conductance
    net.y(P, -1, G); net.I[P] = G;
    net.y(P, A, s * C1);
    net.y(A, W, 1.0 / wip((1 - t) * R1));
    net.y(W, B, 1.0 / wip(t * R1));
    net.y(P, X, 1.0 / R4);
    net.y(X, B, s * C2);
    net.y(B, MD, 1.0 / wip(l * R2));
    if (divider) {
        net.y(MD, MW, 1.0 / wip((1 - m) * R3));
        net.y(MW, -1, 1.0 / wip(m * R3));
        net.y(X, MW, s * C3);
    } else {
        net.y(X, MD, s * C3);
        net.y(MD, -1, 1.0 / wip(m * R3));
        net.y(MW, -1, 1.0);                      // unused node
    }
    return net.solve()[W];
}

// Yeh & Smith (DAFx 2006), Fender tone stack: H(s) = (b1 s + b2 s^2 + b3 s^3) / (1 + a1 s + a2 s^2 + a3 s^3)
static cd stack_yeh(double f, double t, double l, double m)
{
    cd s(0, 2 * M_PI * f);
    double b1 = t * C1 * R1 + m * C3 * R3 + l * (C1 * R2 + C2 * R2) + (C1 * R3 + C2 * R3);
    double b2 = t * (C1 * C2 * R1 * R4 + C1 * C3 * R1 * R4) - m * m * (C1 * C3 * R3 * R3 + C2 * C3 * R3 * R3)
              + m * (C1 * C3 * R1 * R3 + C1 * C3 * R3 * R3 + C2 * C3 * R3 * R3)
              + l * (C1 * C2 * R1 * R2 + C1 * C2 * R2 * R4 + C1 * C3 * R2 * R4)
              + l * m * (C1 * C3 * R2 * R3 + C2 * C3 * R2 * R3)
              + (C1 * C2 * R1 * R3 + C1 * C2 * R3 * R4 + C1 * C3 * R3 * R4);
    double b3 = l * m * (C1 * C2 * C3 * R1 * R2 * R3 + C1 * C2 * C3 * R2 * R3 * R4)
              - m * m * (C1 * C2 * C3 * R1 * R3 * R3 + C1 * C2 * C3 * R3 * R3 * R4)
              + m * (C1 * C2 * C3 * R1 * R3 * R3 + C1 * C2 * C3 * R3 * R3 * R4)
              + t * C1 * C2 * C3 * R1 * R3 * R4 - t * m * C1 * C2 * C3 * R1 * R3 * R4
              + t * l * C1 * C2 * C3 * R1 * R2 * R4;
    double a1 = (C1 * R1 + C1 * R3 + C2 * R3 + C2 * R4 + C3 * R4) + m * C3 * R3 + l * (C1 * R2 + C2 * R2);
    double a2 = m * (C1 * C3 * R1 * R3 - C2 * C3 * R3 * R4 + C1 * C3 * R3 * R3 + C2 * C3 * R3 * R3)
              + l * m * (C1 * C3 * R2 * R3 + C2 * C3 * R2 * R3) - m * m * (C1 * C3 * R3 * R3 + C2 * C3 * R3 * R3)
              + l * (C1 * C2 * R2 * R4 + C1 * C2 * R1 * R2 + C1 * C3 * R2 * R4 + C2 * C3 * R2 * R4)
              + (C1 * C2 * R1 * R4 + C1 * C3 * R1 * R4 + C1 * C2 * R3 * R4 + C1 * C2 * R1 * R3 + C1 * C3 * R3 * R4
                 + C2 * C3 * R3 * R4);
    double a3 = l * m * (C1 * C2 * C3 * R1 * R2 * R3 + C1 * C2 * C3 * R2 * R3 * R4)
              - m * m * (C1 * C2 * C3 * R1 * R3 * R3 + C1 * C2 * C3 * R3 * R3 * R4)
              + m * (C1 * C2 * C3 * R3 * R3 * R4 + C1 * C2 * C3 * R1 * R3 * R3 - C1 * C2 * C3 * R1 * R3 * R4)
              + l * C1 * C2 * C3 * R1 * R2 * R4 + C1 * C2 * C3 * R1 * R3 * R4;
    return (b1 * s + b2 * s * s + b3 * s * s * s) / (1.0 + a1 * s + a2 * s * s + a3 * s * s * s);
}

// network 1 in full (as ra_net1): u = mu * grid -> volume wiper; knobs 0..1 through the same tapers
static double atap(double x) { return (std::pow(81.0, x) - 1.0) / 80.0; }
static cd net1_nodal(double f, double vol, double tre, double mid, double bas, bool bright)
{
    enum { M = 0, P, A, W, B, X, MD, V };
    Net net(8);
    cd s(0, 2 * M_PI * f);
    const double mu = 100.0, ra = 62.5e3, rk = 1.5e3, ck = 50e-6;
    double t = atap(tre), l = atap(bas), m = atap(mid), v = atap(vol);
    net.y(M, -1, 1.0 / ra); net.I[M] = 1.0 / ra;  // u = 1 V behind ra
    net.y(M, P, 1.0 / ((mu + 1) * rk) + s * (ck / (mu + 1)));
    net.y(P, -1, 1.0 / 100e3);
    net.y(P, A, s * C1);
    net.y(A, W, 1.0 / wip((1 - t) * R1));
    net.y(W, B, 1.0 / wip(t * R1));
    net.y(P, X, 1.0 / R4);
    net.y(X, B, s * C2);
    net.y(X, MD, s * C3);
    net.y(B, MD, 1.0 / wip(l * R2));
    net.y(MD, -1, 1.0 / wip(m * R3));
    net.y(W, V, 1.0 / wip((1 - v) * 1e6));
    net.y(V, -1, 1.0 / wip(v * 1e6));
    if (bright) net.y(W, V, s * 120e-12);
    return net.solve()[V];
}

// amplitude of the discretised network 1 for a sine at f (after settling)
static double net1_sim(double f, float vol, float tre, float mid, float bas, int bright)
{
    float n1[RA_N1_SZ], n2[RA_N2_SZ], xs[5] = {}, up = 0, in[RA_NB], out[RA_NB];
    ra_derive(n1, n2, 3, vol, tre, mid, bas, bright);
    double acc_c = 0, acc_s = 0;
    const long N = 44100 / RA_NB * RA_NB, settle = 44100 / RA_NB * RA_NB;
    for (long b = 0; b < settle + N; b += RA_NB) {
        for (int i = 0; i < RA_NB; ++i) in[i] = (float)std::sin(2 * M_PI * f * (b + i) / 44100.0);
        ra_net5_block(n1, xs, &up, in, 1.0f, out);
        if (b >= settle)
            for (int i = 0; i < RA_NB; ++i) {
                double ph = 2 * M_PI * f * (b + i) / 44100.0;
                acc_c += out[i] * std::cos(ph); acc_s += out[i] * std::sin(ph);
            }
    }
    return 2.0 * std::sqrt(acc_c * acc_c + acc_s * acc_s) / N;
}

// ---- 3: the kernel -----------------------------------------------------------------------------------
static uint32_t state[64];
static uint8_t wbuf[sizeof(RaWork) + 16];
static float coef[16], bus[32];
static uint32_t desc[3];
static void* inst[4];
static void* ctx[8];
static void reset() { std::memset(state, 0, sizeof state); state[SH_STATE_GUARD_WORD] = SH_STATE_GUARD; }
static void knobs(float vol, float tre, float mid, float bas, int bright, float speed, int rotor)
{
    coef[SH_PARAM_VOLUME] = vol; coef[SH_PARAM_TREBLE] = tre; coef[SH_PARAM_MIDDLE] = mid;
    coef[SH_PARAM_BASS] = bas; coef[SH_PARAM_BRIGHT] = (float)bright; coef[SH_PARAM_SPEED] = speed;
    coef[SH_PARAM_ROTOR] = rotor * 0.5f;
}

int main()
{
    setvbuf(stdout, nullptr, _IONBF, 0);
    std::printf("CF RA200 host test (state %u B, work buffer %u B)\n", (unsigned)sizeof(KernelState), (unsigned)sizeof(RaWork));

    // 1. stack topology: the nodal solver with Yeh & Smith's wiring must reproduce their closed form (checks
    //    the solver and the rest of the topology); the F-2B's rheostat mid differs from it by a little
    double worst = 0, wiring = 0;
    const double kn[][3] = { {0.5, 0.5, 0.5}, {0.1, 0.9, 0.3}, {0.9, 0.1, 0.8}, {0.4, 1.0, 0.1}, {0.99, 0.01, 0.99} };
    for (auto& k : kn)
        for (double f = 20; f < 20000; f *= 1.25) {
            cd ours = stack_nodal(f, k[0], k[1], k[2], false), yeh_w = stack_nodal(f, k[0], k[1], k[2], true);
            double d = 20 * std::log10(std::abs(yeh_w) / std::abs(stack_yeh(f, k[0], k[1], k[2])));
            double e = 20 * std::log10(std::abs(ours) / std::abs(yeh_w));
            if (!std::isfinite(d)) d = 1e9;
            worst = std::fmax(worst, std::fabs(d));
            wiring = std::fmax(wiring, std::fabs(e));
        }
    std::printf("  (stack: nodal with Yeh's wiring vs their closed form %.6f dB; the F-2B's rheostat mid vs\n"
                "   Yeh's divider mid: up to %.2f dB, low frequencies, mid below full)\n", worst, wiring);
    check(worst < 0.001, "Fender stack: nodal analysis reproduces Yeh & Smith's closed form");
    check(wiring < 0.5, "F-2B mid wiring within 0.5 dB of the Yeh & Smith (Bassman) wiring");

    // 2. discretised network 1 vs its analog response
    struct { float v, t, m, b; int br; } set[] = { {0.5f, 0.6f, 0.5f, 0.4f, 0}, {1.0f, 1.0f, 0.0f, 1.0f, 1}, {0.3f, 0.2f, 1.0f, 0.7f, 1} };
    double w5 = 0, w10 = 0;
    for (auto& k : set)
        for (double f : { 50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0 }) {
            double a = net1_sim(f, k.v, k.t, k.m, k.b, k.br);
            double r = std::abs(net1_nodal(f, k.v, k.t, k.m, k.b, k.br != 0));
            double d = std::fabs(20 * std::log10(a / r));
            if (!std::isfinite(d)) d = 1e9;   /* NaN or silence must fail, not vanish in fmax */
            if (f <= 5000) w5 = std::fmax(w5, d); else w10 = std::fmax(w10, d);
        }
    std::printf("  (network 1: discrete vs analog, worst %.3f dB to 5 kHz, %.3f dB at 10 kHz: bilinear warping\n"
                "   at 1x; the speakers roll off from 4.5 / 7 kHz)\n", w5, w10);
    check(w5 < 0.4, "network 1 (V1b + stack + volume + bright) within 0.4 dB to 5 kHz");
    check(w10 < 2.0, "network 1 within 2 dB at 10 kHz");

    // 3. the kernel
    uint32_t base = ((uint32_t)(uintptr_t)wbuf + 7u) & ~7u;
    desc[0] = base; desc[1] = base + (uint32_t)sizeof(RaWork); desc[2] = (uint32_t)sizeof(RaWork);
    inst[1] = coef; inst[2] = state; inst[3] = desc; ctx[1] = bus;

    // level at noon, rotor off: 0.1 V 1 kHz in
    reset(); coef[SH_COEFF_BYPASS] = 1.0f; knobs(0.5f, 0.5f, 0.5f, 0.5f, 0, 0.4f, 0);
    double pin = 0, pout = 0;
    bool finite = true;
    for (long b = 0; b < 44100 * 2; b += 16) {
        for (int i = 0; i < 16; ++i) bus[i] = bus[i + 16] = 0.1f * (float)std::sin(2 * M_PI * 1000.0 * (b + i) / 44100.0);
        float x[16]; std::memcpy(x, bus, sizeof x);
        SH_AUDIO_FN(inst, ctx);
        if (b > 44100) for (int i = 0; i < 16; ++i) { pin += x[i] * x[i]; pout += bus[i] * bus[i]; finite &= std::isfinite(bus[i]); }
    }
    double gain_db = 10 * std::log10(pout / pin);
    std::printf("  (level at noon, rotor off, 0.1 V 1 kHz: %+.1f dB)\n", gain_db);
    check(finite && std::fabs(gain_db) < 6.0, "preamp level at noon within 6 dB of unity");

    // aliasing of the 1x triodes (report): rotor off, Volume full, a hot 3.1 kHz tone; energy of the in-band
    // non-harmonic DFT bins (< 15 kHz) against the harmonics
    for (float lvl : { 0.1f, 0.5f }) {
        reset(); coef[SH_COEFF_BYPASS] = 1.0f; knobs(1.0f, 0.6f, 0.5f, 0.5f, 0, 0.4f, 0);
        const double f0 = 44100.0 * 289 / 4096;  // 3111.6 Hz, on a bin of the 4096-point window
        std::vector<double> y;
        for (long b = 0; b < 44100 + 4096; b += 16) {
            for (int i = 0; i < 16; ++i) bus[i] = bus[i + 16] = lvl * (float)std::sin(2 * M_PI * f0 * (b + i) / 44100.0);
            SH_AUDIO_FN(inst, ctx);
            if (b >= 44100) for (int i = 0; i < 16; ++i) y.push_back(bus[i]);
        }
        double harm = 0, other = 0;
        for (int k = 1; k < 4096 * 15000 / 44100; ++k) {
            double c = 0, sn = 0;
            for (int n = 0; n < 4096; ++n) { double ph = 2 * M_PI * k * n / 4096.0; c += y[n] * std::cos(ph); sn += y[n] * std::sin(ph); }
            double pw = c * c + sn * sn;
            if (k % 289 == 0) harm += pw; else other += pw;
        }
        std::printf("  (1x triodes, %.1f V at 3.1 kHz, Volume full: non-harmonic energy %.1f dB below the harmonics)\n",
                    lvl, 10 * std::log10(harm / (other + 1e-30)));
    }

    // bypass exact
    reset(); coef[SH_COEFF_BYPASS] = 0.0f; knobs(0.5f, 0.5f, 0.5f, 0.5f, 1, 0.5f, 2);
    bool exact = true;
    for (long b = 0; b < 44100; b += 16) {
        float xa[16], xb[16];
        for (int i = 0; i < 16; ++i) { xa[i] = std::sin(0.01f * (b + i)); xb[i] = 0.3f * std::cos(0.02f * (b + i)); bus[i] = xa[i]; bus[i + 16] = xb[i]; }
        SH_AUDIO_FN(inst, ctx);
        for (int i = 0; i < 16; ++i) exact &= bus[i] == xa[i] && bus[i + 16] == xb[i];
    }
    check(exact, "bypass (fade 0) passes the dry signal exactly");

    // loud input, everything up: bounded and finite
    reset(); coef[SH_COEFF_BYPASS] = 1.0f; knobs(1.0f, 1.0f, 1.0f, 1.0f, 1, 1.0f, 2);
    float peak = 0; finite = true;
    for (long b = 0; b < 44100 * 3; b += 16) {
        for (int i = 0; i < 16; ++i) bus[i] = bus[i + 16] = 2.0f * (float)std::sin(0.07 * (b + i));
        SH_AUDIO_FN(inst, ctx);
        for (int i = 0; i < 32; ++i) { peak = std::fmax(peak, std::fabs(bus[i])); finite &= std::isfinite(bus[i]); }
    }
    std::printf("  (loud input, all knobs up: peak %.2f)\n", peak);
    check(finite && peak < 8.0f, "loud input with all knobs up stays finite and bounded");

    // rotor: sidebands of a 3 kHz tone at multiples of 3 x the rotor rate
    for (int rotor = 1; rotor <= 2; ++rotor) {
        reset(); coef[SH_COEFF_BYPASS] = 1.0f; knobs(0.5f, 0.5f, 0.5f, 0.5f, 0, 0.5f, rotor);
        const long N = 44100 * 4 / 16 * 16, skip = 44100 * 8 / 16 * 16;   // 8 s spin-up, 4 s analysed
        std::vector<float> L(N);
        for (long b = 0; b < skip + N; b += 16) {
            for (int i = 0; i < 16; ++i) bus[i] = bus[i + 16] = 0.05f * (float)std::sin(2 * M_PI * 3000.0 * (b + i) / 44100.0);
            SH_AUDIO_FN(inst, ctx);
            if (b >= skip) for (int i = 0; i < 16; ++i) L[b - skip + i] = bus[i];
        }
        double rate = rotor == 2 ? RA_FAST : RA_SLOW_LO + (RA_SLOW_HI - RA_SLOW_LO) * 0.5;
        // strongest sideband between 3000 + 0.5*3r and 3000 + 1.5*3r, 0.05 Hz steps (DFT on the 4 s)
        double best = 0, fbest = 0;
        for (double f = 3000 + 1.5 * rate; f <= 3000 + 4.5 * rate; f += 0.05) {
            double c = 0, s = 0;
            for (long n = 0; n < N; ++n) { double ph = 2 * M_PI * f * n / 44100.0; c += L[n] * std::cos(ph); s += L[n] * std::sin(ph); }
            double p = c * c + s * s;
            if (p > best) { best = p; fbest = f; }
        }
        double spacing = fbest - 3000, expect = 3 * rate;
        char what[96];
        std::snprintf(what, sizeof what, "rotor %s: first sideband at +%.2f Hz = 3 x %.2f Hz rotor (+-3 %%)",
                      rotor == 2 ? "fast" : "slow", spacing, rate);
        check(std::fabs(spacing / expect - 1) < 0.03, what);
    }

    // guards
    reset(); state[SH_STATE_GUARD_WORD] = 0; coef[SH_COEFF_BYPASS] = 1.0f; knobs(0.5f, 0.5f, 0.5f, 0.5f, 0, 0.5f, 1);
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    bool mute = true; for (int i = 0; i < 32; ++i) mute &= bus[i] == 0.0f;
    check(mute, "bad state guard mutes");
    reset(); coef[SH_PARAM_ROTOR] = 1.5f;
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    mute = true; for (int i = 0; i < 32; ++i) mute &= bus[i] == 0.0f;
    check(mute, "out-of-range coefficient mutes");
    reset(); knobs(0.5f, 0.5f, 0.5f, 0.5f, 0, 0.5f, 1); inst[3] = nullptr;
    for (int i = 0; i < 32; ++i) bus[i] = 0.5f;
    SH_AUDIO_FN(inst, ctx);
    mute = true; for (int i = 0; i < 32; ++i) mute &= bus[i] == 0.0f;
    check(mute, "no work buffer mutes");

    std::printf(fails ? "FAILED (%d)\n" : "all passed\n", fails);
    return fails ? 1 : 0;
}
