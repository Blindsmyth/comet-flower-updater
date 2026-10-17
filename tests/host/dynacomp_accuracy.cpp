// CF Dyna Comp accuracy bench. Writes float32 outputs of the reference, the
// input stimulus and the candidate core (effects/common/dynacomp_g1.h) for a
// grid of tests; tests/host/dynacomp_accuracy.py scores them.
//
// Reference: Comet Flower's DynaCompProcessor signal chain (Source/
// DynaCompProcessor.cpp, MXR Dyna Comp model), in double precision at the
// pedal's own 44.1 kHz (the desktop never oversamples this pedal either), with
// the same filter types (JUCE first-order bilinear high/low-pass = TPT
// one-pole, per the established CF RAT precedent in rat_accuracy.cpp; JUCE
// 2nd-order shelf/low-pass = the RBJ Audio EQ Cookbook biquad, Direct-Form-II
// Transposed, which is how juce::dsp::IIR::Filter realises a Coefficients
// object -- NOTE this project could not re-derive that topology against the
// live JUCE source on this machine (no JUCE/modules checkout was found); it
// is the well-documented public JUCE/cookbook formula and is flagged here as
// an assumption rather than a measurement. It affects only how closely this
// reference matches the desktop plugin, not the pedal port's bench, which is
// graded against THIS file), the shared CompressorMath gain law (DynaCompProcessor.cpp
// lines 110-221: CA3080 pre/de-emphasis shelf pair, 8:1/6dB-knee gain
// reduction with reference-level-preserving makeup, ADAA tanh(x/1.2) OTA
// clip, 80 Hz output high-pass, output trim), solved exactly every sample.
// Knobs fixed per test (no smoothing, matching the RAT precedent).
// Written by Claude; do not edit as part of the model work.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
extern "C" {
#include "../../effects/common/dynacomp_g1.h"
}

static const double PI = 3.14159265358979323846;
static const int SR = 44100;

// JUCE makeFirstOrderHighPass/LowPass == TPT one-pole (established by the CF
// RAT bench's HP1 struct comment; re-used here for DynaComp's 80 Hz output HPF).
struct OnePoleTPT {
    double g = 0, s = 0;
    void set(double fs, double fc) { double t = std::tan(PI * fc / fs); g = t / (1 + t); }
    double lp(double x) { double v = (x - s) * g, y = v + s; s = y + v; return y; }
    double hp(double x) { return x - lp(x); }
};

// RBJ Audio EQ Cookbook biquad, Direct-Form-II-Transposed (matches
// juce::dsp::IIR::Filter<float>::processSample's v1/v2 recursion).
struct Biquad {
    double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0, v1 = 0, v2 = 0;
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

struct ADAA {   // first-order ADAA, double state (ADAAProcessor.h)
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

// CompressorMath.h, ported verbatim (double).
static double gainReductionDb(double overDb, double ratio, double kneeDb)
{
    double slope = 1.0 / std::max(1.0, ratio) - 1.0;
    if (kneeDb > 0.0) {
        double half = kneeDb * 0.5;
        if (overDb <= -half) return 0.0;
        if (overDb < half) { double t = overDb + half; return slope * t * t / (2.0 * kneeDb); }
    } else if (overDb <= 0.0) return 0.0;
    return slope * overDb;
}
static double autoMakeupDb(double thresholdDb, double ratio, double kneeDb, double referenceDb = -12.0)
{
    return -gainReductionDb(referenceDb - thresholdDb, ratio, kneeDb);
}
static double gainFor(double envelope, double threshold, double ratio, double kneeDb)
{
    if (envelope <= 1.0e-9 || threshold <= 1.0e-9) return 1.0;
    double overDb = 20.0 * std::log10(envelope / threshold);
    double gr = gainReductionDb(overDb, ratio, kneeDb);
    return gr >= 0.0 ? 1.0 : std::exp(gr * (2.302585093 / 20.0));
}

// --- test signals ----------------------------------------------------------
static std::vector<double> sineSignal(double f0, double amp, double secs)
{
    int N = (int)(secs * SR);
    std::vector<double> x(N);
    for (int n = 0; n < N; ++n) x[n] = amp * std::sin(2 * PI * f0 * n / SR);
    return x;
}
// A guitar-like pluck: fast attack, exponential decay, fundamental + 2 harmonics.
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
// A loud/quiet/loud step, to see the compressor's attack and release.
static std::vector<double> stepSignal(double f0, double loAmp, double hiAmp, double secs)
{
    int N = (int)(secs * SR);
    std::vector<double> x(N);
    for (int n = 0; n < N; ++n) {
        double t = (double)n / SR;
        double amp = (t < secs / 3.0) ? loAmp : (t < 2 * secs / 3.0 ? hiAmp : loAmp);
        x[n] = amp * std::sin(2 * PI * f0 * n / SR);
    }
    return x;
}

static std::vector<float> reference(const std::vector<double>& in, double sustain, double outputDb)
{
    Biquad preEmph, deEmph;
    preEmph.setHighShelf(SR, 2000.0, 0.70710678118654752, 1.5);
    deEmph.setHighShelf(SR, 2000.0, 0.70710678118654752, 1.0 / 1.5);
    OnePoleTPT outHp; outHp.set(SR, 80.0);
    ADAA adaa;
    const double attackCoeff = std::exp(-1.0 / (0.005 * SR));
    const double releaseCoeff = std::exp(-1.0 / (0.300 * SR));
    double s = std::clamp(sustain, 0.0, 10.0) / 10.0;
    double sc = (1.0 - s) * (1.0 - s);
    double threshold = 0.80 * sc + 0.005;
    double thresholdDb = 20.0 * std::log10(std::max(threshold, 1.0e-9));
    double autoMakeup = std::pow(10.0, autoMakeupDb(thresholdDb, 8.0, 6.0) / 20.0);
    double outTrim = std::pow(10.0, std::clamp(outputDb, -60.0, 24.0) / 20.0);
    double envelope = 0.0;

    std::vector<float> out(in.size());
    for (size_t n = 0; n < in.size(); ++n) {
        double x = in[n];
        double maxAbs = std::fabs(x);   // mono: the stereo-link peak collapses to |x|
        if (maxAbs > envelope) envelope = attackCoeff * (envelope - maxAbs) + maxAbs;
        else { envelope = releaseCoeff * envelope; if (envelope < 1.0e-9) envelope = 0.0; }
        double gr = gainFor(envelope, threshold, 8.0, 6.0);

        double v = preEmph.process(x);
        v *= gr;
        v *= autoMakeup;
        v = adaa.process(v, [](double t) { return std::tanh(t / 1.2); },
                             [](double t) { return 1.2 * lnCosh(t / 1.2); }) * 1.2;
        v = deEmph.process(v);
        v = outHp.hp(v);
        v *= outTrim;
        out[n] = (float)v;
    }
    return out;
}

static void write(const std::string& path, const std::vector<float>& v)
{
    FILE* f = std::fopen(path.c_str(), "wb"); std::fwrite(v.data(), 4, v.size(), f); std::fclose(f);
}
static std::vector<float> toF32(const std::vector<double>& v)
{
    std::vector<float> o(v.size());
    for (size_t i = 0; i < v.size(); ++i) o[i] = (float)v[i];
    return o;
}

int main(int argc, char** argv)
{
    std::string dir = argc > 1 ? argv[1] : ".";
    bool skipRef = argc > 2 && std::string(argv[2]) == "--skip-ref";

    // sustain x output(dB) x signal. Sustain 0/5/10 spans barely-compressing to
    // heavy limiting; output dB -6 (house default) and +12 (near the ADAA's
    // domain edge) exercise the OTA clip at different headroom.
    const double sustains[] = { 0.0, 5.0, 10.0 };
    const double outDbs[] = { -6.0, 12.0 };

    struct Test { std::string tag; std::vector<double> in; };
    std::vector<Test> tests;
    const double freqs[] = { 110.0, 440.0, 2000.0 };
    const double amps[] = { 0.05, 0.3, 0.9 };
    for (double f0 : freqs) for (double amp : amps) {
        char tag[64];
        std::snprintf(tag, sizeof tag, "sine_f%d_a%03d", (int)f0, (int)(amp * 100));
        tests.push_back({ tag, sineSignal(f0, amp, 1.0) });
    }
    const double pluckFreqs[] = { 220.0, 880.0 };
    for (double f0 : pluckFreqs) {
        char tag[64];
        std::snprintf(tag, sizeof tag, "pluck_f%d", (int)f0);
        tests.push_back({ tag, pluckSignal(f0, 0.8, 1.2, 0.35) });
    }
    tests.push_back({ "step", stepSignal(440.0, 0.04, 0.8, 1.2) });

    for (const Test& t : tests) for (double sustain : sustains) for (double outDb : outDbs) {
        char tag[96];
        std::snprintf(tag, sizeof tag, "%s_s%02d_o%03d", t.tag.c_str(), (int)sustain, (int)(outDb + 60));
        if (!skipRef) {
            write(dir + "/ref_" + tag + ".f32", reference(t.in, sustain, outDb));
            write(dir + "/in_" + tag + ".f32", toF32(t.in));
        }
        DynaCompState s = {};
        DynaCompCoeffs k;
        dynacomp_coeffs(&k, (float)sustain, (float)outDb);
        std::vector<float> o(t.in.size());
        for (size_t n = 0; n < t.in.size(); ++n)
            o[n] = dynacomp_process(&s, &k, (float)t.in[n]);
        write(dir + "/cand_" + tag + ".f32", o);
    }
    std::printf("done\n");
    return 0;
}
