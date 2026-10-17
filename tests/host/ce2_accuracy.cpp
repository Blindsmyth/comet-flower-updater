// CF CE-2 accuracy bench. Writes float32 outputs of the reference and the
// candidate core (effects/common/ce2_g1.h) for a grid of tests;
// tests/host/ce2_accuracy.py scores them.
//
// Reference: Comet Flower's ChorusProcessor signal chain (Source/
// ChorusProcessor.{h,cpp}, Boss CE-2 model, MN3007 BBD), in double precision
// AT THE PEDAL'S OWN 44.1 kHz -- the desktop plugin never oversamples this
// pedal either (no juce::dsp::Oversampling member in ChorusProcessor.h), so
// this reference's rate matches the desktop exactly, unlike the Mistress kit.
// Mono: the desktop stereo-links the LFO with a 90-degree channel offset
// (lfoPhase[0]=0, lfoPhase[1]=0.25); the G1 is mono, so only channel 0's
// phase (0) applies here -- see this kit's brief section 1.
//
// Signal chain (ChorusProcessor.cpp lines 120-220): pre-emphasis +15 dB high
// shelf (979 Hz, Q 0.707) -> anti-alias HPF (48 Hz) + LPF cascade (6.6 kHz
// 1st order + 6.6 kHz Q 0.707) -> MN3007 BBD soft saturation (ADAA
// tanh(0.7x)/0.7) -> BBD delay (Lagrange 3rd-order read, center 12.8 ms,
// +-5 ms * Depth) -> CTI one-pole low-pass (cutoff sweeps with delay, fixed
// 7.8/17.8 ms reference bounds regardless of Depth, exactly as the desktop
// hardcodes them) -> reconstruction HPF (14.6 Hz) + LPF cascade (6.9 kHz 1st
// order + 6.9 kHz Q 0.707) -> de-emphasis (exact inverse shelf) -> 50/50
// dry/wet mix (wet scaled by Mix). Knobs fixed per test (no smoothing); LFO
// phase starts at 0 on reset.
// Written by Claude; do not edit as part of the model work.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
extern "C" {
#include "../../effects/common/ce2_g1.h"
}

static const double PI = 3.14159265358979323846;
static const int SR = 44100;

struct OnePoleTPT {
    double g = 0, s = 0;
    void set(double fs, double fc) { double t = std::tan(PI * fc / fs); g = t / (1 + t); }
    double lp(double x) { double v = (x - s) * g, y = v + s; s = y + v; return y; }
    double hp(double x) { return x - lp(x); }
};

struct Biquad {
    double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0, v1 = 0, v2 = 0;
    void setLowPass(double fs, double fc, double Q)
    {
        double w0 = 2 * PI * fc / fs, c = std::cos(w0), s = std::sin(w0), alpha = s / (2 * Q);
        double a0 = 1 + alpha;
        b0 = ((1 - c) / 2) / a0; b1 = (1 - c) / a0; b2 = ((1 - c) / 2) / a0;
        a1 = (-2 * c) / a0; a2 = (1 - alpha) / a0;
    }
    void setHighShelf(double fs, double fc, double Q, double gain)
    {
        double A = std::sqrt(gain), w0 = 2 * PI * fc / fs, c = std::cos(w0), s = std::sin(w0);
        double beta = s * std::sqrt(A) / Q;
        double ap1 = A + 1, am1 = A - 1, amc = am1 * c;
        double b0_ = A * (ap1 + amc + beta), b1_ = -2 * A * (am1 + ap1 * c), b2_ = A * (ap1 + amc - beta);
        double a0_ = ap1 - amc + beta, a1_ = 2 * (am1 - ap1 * c), a2_ = ap1 - amc - beta;
        b0 = b0_ / a0_; b1 = b1_ / a0_; b2 = b2_ / a0_; a1 = a1_ / a0_; a2 = a2_ / a0_;
    }
    double process(double x)
    {
        double y = b0 * x + v1;
        v1 = b1 * x - a1 * y + v2;
        v2 = b2 * x - a2 * y;
        return y;
    }
};

struct ADAA {
    double x1 = 0, ad1 = 0;
    template <typename F, typename Fa>
    double process(double x, F f, Fa Fn)
    {
        double ad0 = Fn(x), diff = x - x1;
        double out = (std::fabs(diff) > 1.0e-5) ? (ad0 - ad1) / diff : f(0.5 * (x + x1));
        x1 = x; ad1 = ad0;
        return out;
    }
};
static inline double lnCosh(double z) { double a = std::fabs(z); return a + std::log1p(std::exp(-2 * a)) - std::log(2.0); }

// Cubic (Lagrange 3rd-order) fractional-delay read -- see mistress_accuracy.cpp
// for the derivation; identical structure, independent implementation here.
struct DelayL3 {
    std::vector<double> buf;
    int wp = 0;
    void init(int n) { buf.assign((size_t)n, 0.0); wp = 0; }
    void push(double x) { buf[wp] = x; wp = (wp + 1) % (int)buf.size(); }
    double at(int k) const { int L = (int)buf.size(); int idx = ((wp - 1 - k) % L + L) % L; return buf[idx]; }
    double read(double delaySamples) const
    {
        int M = (int)std::floor(delaySamples);
        double mu = delaySamples - M;
        double pm1 = at(M - 1), p0 = at(M), p1 = at(M + 1), p2 = at(M + 2);
        double Lm1 = -mu * (mu - 1) * (mu - 2) / 6.0;
        double L0 = (mu + 1) * (mu - 1) * (mu - 2) / 2.0;
        double L1 = -(mu + 1) * mu * (mu - 2) / 2.0;
        double L2 = (mu + 1) * mu * (mu - 1) / 6.0;
        return Lm1 * pm1 + L0 * p0 + L1 * p1 + L2 * p2;
    }
};

// --- test signals ------------------------------------------------------------
static std::vector<double> sineSignal(double f0, double amp, double secs)
{
    int N = (int)(secs * SR);
    std::vector<double> x(N);
    for (int n = 0; n < N; ++n) x[n] = amp * std::sin(2 * PI * f0 * n / SR);
    return x;
}
static std::vector<double> pluckSignal(double f0, double amp, double secs, double tau)
{
    int N = (int)(secs * SR);
    std::vector<double> x(N);
    double attackN = 0.002 * SR;
    for (int n = 0; n < N; ++n) {
        double t = (double)n / SR;
        double env = std::exp(-t / tau);
        double a = (n < attackN) ? (n / attackN) : 1.0;
        double s = std::sin(2 * PI * f0 * t) + 0.3 * std::sin(2 * PI * 2 * f0 * t)
                  + 0.15 * std::sin(2 * PI * 3 * f0 * t);
        x[n] = amp * a * env * s;
    }
    return x;
}
static std::vector<double> chirpSignal(double f0, double f1, double amp, double secs)
{
    int N = (int)(secs * SR);
    std::vector<double> x(N);
    double k = (f1 - f0) / secs;
    for (int n = 0; n < N; ++n) {
        double t = (double)n / SR;
        x[n] = amp * std::sin(2 * PI * (f0 * t + 0.5 * k * t * t));
    }
    return x;
}

static std::vector<float> reference(const std::vector<double>& in, double rateKnob, double depth, double mix)
{
    const double fs = SR;
    Biquad preEmph, deEmph;
    const double preEmphGain = std::pow(10.0, 15.0 / 20.0);
    preEmph.setHighShelf(fs, 979.0, 0.70710678118654752, preEmphGain);
    deEmph.setHighShelf(fs, 979.0, 0.70710678118654752, 1.0 / preEmphGain);
    OnePoleTPT aaHp; aaHp.set(fs, 48.0);
    OnePoleTPT aaLp1; aaLp1.set(fs, 6600.0);
    Biquad aaLp2; aaLp2.setLowPass(fs, 6600.0, 0.70710678118654752);
    OnePoleTPT reconHp; reconHp.set(fs, 14.6);
    OnePoleTPT reconLp1; reconLp1.set(fs, 6900.0);
    Biquad reconLp2; reconLp2.setLowPass(fs, 6900.0, 0.70710678118654752);
    ADAA satADAA;
    DelayL3 delay; delay.init(900);

    const double centerDelayMs = 12.8, maxSweepMs = 5.0;
    const double minRateHz = 0.1, maxRateHz = 3.5, rateKnobMin = 0.1, rateKnobMax = 8.0;
    double rateHz = minRateHz + (rateKnob - rateKnobMin) / (rateKnobMax - rateKnobMin) * (maxRateHz - minRateHz);
    double phaseInc = rateHz / fs;
    double lfoPhase = 0.0, lfoSmoothed = 0.0, ctiState = 0.0;
    double lfoSmoothCoeff = 1.0 - std::exp(-2.0 * PI * 72.0 / fs);
    double sweepMs = maxSweepMs * depth;
    double wetGain = 0.5 * mix, dryGain = 0.5;

    std::vector<float> out(in.size());
    for (size_t n = 0; n < in.size(); ++n) {
        double dry = in[n];

        double bbdIn = preEmph.process(dry);
        bbdIn = aaHp.hp(bbdIn);
        bbdIn = aaLp1.lp(bbdIn);
        bbdIn = aaLp2.process(bbdIn);
        bbdIn = satADAA.process(bbdIn, [](double v) { return std::tanh(v * 0.7); },
                                        [](double v) { return lnCosh(v * 0.7) / 0.7; }) * (1.0 / 0.7);
        delay.push(bbdIn);

        double phi = lfoPhase;
        double lfoTri = (phi < 0.5) ? (phi * 2.0) : (2.0 - phi * 2.0);
        double lfoRaw = lfoTri * 2.0 - 1.0;
        lfoSmoothed += lfoSmoothCoeff * (lfoRaw - lfoSmoothed);
        double lfoMod = lfoSmoothed;

        double delayMs = centerDelayMs + lfoMod * sweepMs;
        double delaySamples = delayMs * fs / 1000.0;
        double wet = delay.read(delaySamples);

        double bbdClockNorm = std::clamp((17.8 - delayMs) / (17.8 - 7.8), 0.0, 1.0);
        double ctiFc = 3000.0 + bbdClockNorm * 4000.0;
        double ctiCoeff = 1.0 - std::exp(-2.0 * PI * ctiFc / fs);
        ctiState += ctiCoeff * (wet - ctiState);
        wet = ctiState;

        wet = reconHp.hp(wet);
        wet = reconLp1.lp(wet);
        wet = reconLp2.process(wet);
        wet = deEmph.process(wet);

        out[n] = (float)(dry * dryGain + wet * wetGain);

        lfoPhase += phaseInc; if (lfoPhase >= 1.0) lfoPhase -= 1.0;
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

    struct Test { std::string tag; std::vector<double> in; };
    std::vector<Test> tests;
    tests.push_back({ "sine440", sineSignal(440.0, 0.5, 1.2) });
    tests.push_back({ "sine8000", sineSignal(8000.0, 0.5, 1.2) });
    tests.push_back({ "pluck220", pluckSignal(220.0, 0.8, 1.2, 0.5) });
    tests.push_back({ "chirp", chirpSignal(200.0, 3000.0, 0.5, 1.0) });

    const double rates[] = { 0.1, 1.0, 8.0 };   // APVTS knob units, 0.1-8
    const double depths[] = { 0.3, 0.6, 1.0 };
    const double mixes[] = { 0.5, 1.0 };

    for (const Test& t : tests) for (double rate : rates) for (double depth : depths) for (double mix : mixes) {
        char tag[128];
        std::snprintf(tag, sizeof tag, "%s_r%03d_d%02d_m%02d", t.tag.c_str(), (int)(rate * 10),
                      (int)(depth * 10), (int)(mix * 10));
        if (!skipRef) write(dir + "/ref_" + tag + ".f32", reference(t.in, rate, depth, mix));
        Ce2State s = {};
        Ce2Coeffs k;
        ce2_coeffs(&k, (float)rate, (float)depth, (float)mix);
        std::vector<float> o(t.in.size());
        for (size_t n = 0; n < t.in.size(); ++n)
            o[n] = ce2_process(&s, &k, (float)t.in[n]);
        write(dir + "/cand_" + tag + ".f32", o);
    }

    std::printf("done\n");
    return 0;
}
