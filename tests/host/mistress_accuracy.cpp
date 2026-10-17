// CF Mistress accuracy bench. Writes float32 outputs of the reference and the
// candidate core (effects/common/mistress_g1.h) for a grid of tests;
// tests/host/mistress_accuracy.py scores them.
//
// Reference: Comet Flower's FlangerProcessor signal chain (Source/
// FlangerProcessor.{h,cpp}, EHX Electric Mistress V2 model), in double
// precision AT THE PEDAL'S OWN 44.1 kHz (per this kit's brief: "Reference =
// ... at 44.1 kHz, mono" -- the desktop plugin internally runs this chain at
// 4x (176.4 kHz) through a JUCE FIR-equiripple oversampler for extra alias
// headroom, but every formula in it (LFO phase increment, delay-in-samples,
// CTI cutoff, filter cutoffs) is already written in terms of "the rate this
// runs at" and is well-defined at 44.1 kHz directly; running the reference at
// 4x would also force the candidate to match the FIR oversampler's exact
// group delay to avoid comparing misaligned samples, which the pedal gains
// nothing from). Signal chain (FlangerProcessor.cpp lines 189-319): pre-BBD
// coupling-cap HPF (80 Hz, split to dry+wet) -> LFO phase accumulator
// (deterministic start phase 0) -> two-segment exponential-triangle LFO
// shape (mistressLfoShape, or a static delay in Matrix mode) -> pre-BBD
// anti-alias LPF cascade (12 kHz 1st order + 12 kHz Q 0.707 2nd order) ->
// feedback sum with an 18V op-amp ADAA tanh clip in the loop -> BBD delay
// (Lagrange 3rd-order fractional read, JUCE dsp::DelayLine<Lagrange3rd>) ->
// CTI one-pole LP (cutoff sweeps 8 kHz at short delay to 2.5 kHz at long) ->
// post-BBD DC-block HPF (5 Hz) + reconstruction LPF cascade (8 kHz 1st order
// + 8 kHz Q 0.707 + 8.5 kHz Q 0.5) -> dry/wet mix. Knobs fixed per test (no
// smoothing); LFO phase starts at 0 on reset, matching the desktop's channel
// 0 (the G1 is mono, so there is no second-channel phase offset to model).
// Written by Claude; do not edit as part of the model work.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
extern "C" {
#include "../../effects/common/mistress_g1.h"
}

static const double PI = 3.14159265358979323846;
static const int SR = 44100;

// JUCE makeFirstOrderHighPass/LowPass == TPT one-pole (established by the CF
// RAT bench's HP1 struct comment).
struct OnePoleTPT {
    double g = 0, s = 0;
    void set(double fs, double fc) { double t = std::tan(PI * fc / fs); g = t / (1 + t); }
    double lp(double x) { double v = (x - s) * g, y = v + s; s = y + v; return y; }
    double hp(double x) { return x - lp(x); }
};

// RBJ Audio EQ Cookbook 2nd-order low-pass, Direct-Form-II-Transposed.
struct Biquad {
    double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0, v1 = 0, v2 = 0;
    void setLowPass(double fs, double fc, double Q)
    {
        double w0 = 2 * PI * fc / fs, c = std::cos(w0), s = std::sin(w0), alpha = s / (2 * Q);
        double a0 = 1 + alpha;
        b0 = ((1 - c) / 2) / a0; b1 = (1 - c) / a0; b2 = ((1 - c) / 2) / a0;
        a1 = (-2 * c) / a0; a2 = (1 - alpha) / a0;
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

// 4-point (cubic) Lagrange fractional-delay read on a ring buffer, matching
// JUCE's dsp::DelayLineInterpolationTypes::Lagrange3rd (the unique cubic
// through the 4 points surrounding the fractional read position).
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

// Two-segment exponential-triangle LFO (FlangerProcessor.cpp lines 43-68).
static double mistressLfoShape(double phi)
{
    const double riseK = 2.0, fallK = 1.8, riseFrac = 0.5;
    static const double invRise = 1.0 / (std::exp(riseK) - 1.0);
    static const double invFall = 1.0 / (1.0 - std::exp(-fallK));
    if (phi < riseFrac) {
        double p = phi / riseFrac;
        return (std::exp(riseK * p) - 1.0) * invRise;
    } else {
        double p = (phi - riseFrac) / (1.0 - riseFrac);
        return 1.0 - (1.0 - std::exp(-fallK * p)) * invFall;
    }
}

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

static std::vector<float> reference(const std::vector<double>& in, double rate, double depth,
                                    double feedback, bool matrixMode, double mix)
{
    const double fs = SR;
    OnePoleTPT preHP; preHP.set(fs, 80.0);
    OnePoleTPT preA; preA.set(fs, 12000.0);
    Biquad preB; preB.setLowPass(fs, 12000.0, 0.70710678118654752);
    OnePoleTPT postDc; postDc.set(fs, 5.0);
    OnePoleTPT postA; postA.set(fs, 8000.0);
    Biquad postB; postB.setLowPass(fs, 8000.0, 0.70710678118654752);
    Biquad postC; postC.setLowPass(fs, 8500.0, 0.5);
    ADAA adaa;
    DelayL3 delay; delay.init(600);

    const double kMinDelayMs = 0.64, kMaxDelayMs = 6.4, kRangeMs = kMaxDelayMs - kMinDelayMs;
    double lfoPhase = 0.0, ctiState = 0.0, feedbackState = 0.0;
    double feedbackGain = feedback * 0.94;
    double phaseInc = rate / fs;

    std::vector<float> out(in.size());
    for (size_t n = 0; n < in.size(); ++n) {
        double x = in[n];
        double drySample = preHP.hp(x);

        lfoPhase += phaseInc; if (lfoPhase >= 1.0) lfoPhase -= 1.0;
        double delayMs;
        if (matrixMode) delayMs = kMinDelayMs + depth * kRangeMs;
        else delayMs = kMinDelayMs + mistressLfoShape(lfoPhase) * depth * kRangeMs;
        double delayInSamples = delayMs * fs / 1000.0;
        double ctiCutoff = 8000.0 + (delayMs - kMinDelayMs) / kRangeMs * (2500.0 - 8000.0);
        double ctiAlpha = 1.0 - std::exp(-2 * PI * ctiCutoff / fs);

        double preFiltered = preA.lp(drySample);
        preFiltered = preB.process(preFiltered);

        double fbSignal = adaa.process(feedbackState, [](double v) { return std::tanh(v); },
                                                        [](double v) { return lnCosh(v); });

        double bbdIn = preFiltered + fbSignal * feedbackGain;
        delay.push(bbdIn);
        double wetSample = delay.read(delayInSamples);

        ctiState += ctiAlpha * (wetSample - ctiState);
        wetSample = ctiState;
        feedbackState = wetSample;

        double postFiltered = postDc.hp(wetSample);
        postFiltered = postA.lp(postFiltered);
        postFiltered = postB.process(postFiltered);
        postFiltered = postC.process(postFiltered);

        out[n] = (float)(drySample * (1.0 - mix * 0.5) + postFiltered * (mix * 0.5));
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

    const double rates[] = { 0.15, 1.0, 4.0 };
    const double depths[] = { 0.3, 1.0 };
    const double feedbacks[] = { 0.0, 0.4, 0.9 };
    const double mix = 0.4;

    for (const Test& t : tests) for (double rate : rates) for (double depth : depths) for (double fb : feedbacks) {
        char tag[128];
        std::snprintf(tag, sizeof tag, "%s_r%03d_d%02d_f%02d", t.tag.c_str(), (int)(rate * 10),
                      (int)(depth * 10), (int)(fb * 10));
        if (!skipRef) write(dir + "/ref_" + tag + ".f32", reference(t.in, rate, depth, fb, false, mix));
        MistressState s = {};
        MistressCoeffs k;
        mistress_coeffs(&k, (float)rate, (float)depth, (float)fb, 0.0f, (float)mix);
        std::vector<float> o(t.in.size());
        for (size_t n = 0; n < t.in.size(); ++n)
            o[n] = mistress_process(&s, &k, (float)t.in[n]);
        write(dir + "/cand_" + tag + ".f32", o);
    }

    // Matrix mode: LFO bypassed, depth sets a static delay directly.
    const double mdepths[] = { 0.0, 0.5, 1.0 };
    for (double depth : mdepths) for (double fb : feedbacks) {
        char tag[128];
        std::snprintf(tag, sizeof tag, "matrix_d%02d_f%02d", (int)(depth * 10), (int)(fb * 10));
        if (!skipRef) write(dir + "/ref_" + tag + ".f32", reference(tests[0].in, 0.15, depth, fb, true, mix));
        MistressState s = {};
        MistressCoeffs k;
        mistress_coeffs(&k, 0.15f, (float)depth, (float)fb, 1.0f, (float)mix);
        std::vector<float> o(tests[0].in.size());
        for (size_t n = 0; n < tests[0].in.size(); ++n)
            o[n] = mistress_process(&s, &k, (float)tests[0].in[n]);
        write(dir + "/cand_" + tag + ".f32", o);
    }

    std::printf("done\n");
    return 0;
}
