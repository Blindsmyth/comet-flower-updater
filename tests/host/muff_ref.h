// muff_ref.h - reference model for the CF Muff bench: Comet Flower's
// '74 Violet Ram's Head (MobileDsp::FuzzMobileCore, VirtualPedalBoardEngine
// commit 2fdb120, the lean mirror of the desktop OCMuffProcessor with solver
// v2), stage for stage, using the SAME component classes and constants
// (MobilePrimitives OnePoleTPT / Biquad, WaveshaperFunctions::
// DiodeCapFeedbackStage, ToneStackMath::muffTone, VioletSpecs), with three
// changes that make it a reference rather than a shipping core:
//   - runs directly at a high rate (no oversampler of its own);
//   - the Q1 rail limiter is the exact tanh pair, not a 1024-cell table;
//   - the clip-stage tables have `cells` cells (65536 here, 2048 on mobile);
//   - the linear filters run in DOUBLE precision (same TPT one-pole and
//     same muffTone biquad coefficients): at 32x/64x the float versions lose
//     precision (4 Hz corners at 2.8 MHz), which the 32x-vs-64x convergence
//     check exposed.
// Written by Claude; do not edit as part of the model work.
#pragma once
#include <cmath>
#include "MobilePrimitives.h"
#include "ADAAWaveshaper.h"
#include "ToneStackMath.h"
#include "MuffCircuit.h"

struct OnePoleD {                     // TPT one-pole, double (MobileDsp::OnePoleTPT form)
    double g = 0, s = 0;
    void setCutoff(double fs, double fc) { double t = std::tan(3.14159265358979323846 * fc / fs); g = t / (1 + t); }
    void reset() { s = 0; }
    double processLP(double x) { double v = (x - s) * g, y = v + s; s = y + v; return y; }
    double processHP(double x) { return x - processLP(x); }
};
struct BiquadD {                      // transposed direct form II, double
    double b0 = 1, b1 = 0, b2 = 0, a1 = 0, a2 = 0, z1 = 0, z2 = 0;
    void setCoeffs(double B0, double B1, double B2, double A1, double A2) { b0 = B0; b1 = B1; b2 = B2; a1 = A1; a2 = A2; }
    void reset() { z1 = z2 = 0; }
    double process(double x) { double y = b0 * x + z1; z1 = b1 * x - a1 * y + z2; z2 = b2 * x - a2 * y; return y; }
};

struct RefMuff
{
    OnePoleD inputHP, inputMiller, clip1HP, clip2HP, recoveryHP;
    WaveshaperFunctions::DiodeCapFeedbackStage clip1, clip2;
    BiquadD toneStack;
    double rate = 0.0;
    float stage1Gain = 1.0f, drive = 1.0f, stage3Gain = 1.0f, outGain = 1.0f;

    void prepare(double fs, int cells, float sustain, float tone, float volume)
    {
        using namespace VioletSpecs;
        rate = fs;
        inputHP.setCutoff(fs, 4.0f);
        inputMiller.setCutoff(fs, 1200.0f);
        clip2HP.setCutoff(fs, 94.0f);
        recoveryHP.setCutoff(fs, 4.0f);
        clip1.build(RF_Q2, CF, DIODE_IS, DIODE_NVT, fs, kInputMaxQ2, cells, kOpenLoopA, kRhoQ2);
        clip2.build(RF_Q3, CF, DIODE_IS, DIODE_NVT, fs, kInputMaxQ3, cells, kOpenLoopA, kRhoQ3);
        stage1Gain = std::pow(10.0f, 16.7f * 0.05f);
        stage3Gain = (float) kRhoQ3;
        const float s = sustain;
        drive = (0.05f + 0.95f * s) * (float) kRhoQ2;
        const float rThev = s * (1.0f - s) * 100.0e3f;
        clip1HP.setCutoff(fs, 1.0 / (6.283185307179586 * 0.1e-6 * (rThev + 29.0e3)));
        const auto c = ToneStackMath::muffTone(R14, R15, C10, C11, R_POT, RL_Q4, (double) tone, fs);
        toneStack.setCoeffs(c.b0, c.b1, c.b2, c.a1, c.a2);
        outGain = volume;
        inputHP.reset(); inputMiller.reset(); clip1HP.reset(); clip2HP.reset();
        recoveryHP.reset(); clip1.reset(); clip2.reset(); toneStack.reset();
    }

    float process(float v)
    {
        double x = inputMiller.processLP(inputHP.processHP(v)) * stage1Gain;
        x = (x >= 0.0) ? 2.0 * std::tanh(x * 0.5) : 7.0 * std::tanh(x * (1.0 / 7.0));
        x = clip1.process((float) (clip1HP.processHP(x) * drive));
        x = clip2.process((float) (clip2HP.processHP(x) * stage3Gain));
        x = toneStack.process(x);
        return (float) (recoveryHP.processHP(x) * 4.5 * outGain);
    }
};
