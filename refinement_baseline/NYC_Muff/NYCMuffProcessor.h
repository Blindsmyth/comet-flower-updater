#pragma once

#include <JuceHeader.h>

/**
    Professional-grade NYC Muff (Big Muff Pi) DSP class based on Zoom NYC_MUFF.ZD2.
    Audited for thread-safety, performance, and hardware accuracy.
*/
class NYCMuffProcessor
{
public:
    NYCMuffProcessor();
    ~NYCMuffProcessor() = default;

    void prepare(const juce::dsp::ProcessSpec& spec);
    void reset();

    void process(juce::AudioBuffer<float>& buffer);

    // Parameters (Atomic for thread-safety)
    std::atomic<float> sustain { 0.5f };
    std::atomic<float> tone { 0.5f };
    std::atomic<float> balance { 1.0f };
    std::atomic<float> outputGain { 0.7f };

private:
    // Ripped Math Tables (Constants)
    static const float gainTable[23];
    static const float mixTable[10];

    // DSP Components
    juce::dsp::StateVariableTPTFilter<float> lpf, hpf;
    juce::dsp::Oversampling<float> oversampler;

    double sampleRate = 44100.0;
};
