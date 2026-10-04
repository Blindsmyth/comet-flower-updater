#pragma once

#include <JuceHeader.h>

/**
    Professional-grade Uni-Vibe DSP class based on Zoom THEVIBE.ZD2 reverse-engineering.
    Audited for thread-safety, performance, and hardware accuracy.
*/
class TheVibeProcessor
{
public:
    TheVibeProcessor();
    ~TheVibeProcessor() = default;

    void prepare(const juce::dsp::ProcessSpec& spec);
    void reset();

    void process(juce::AudioBuffer<float>& buffer);

    // Parameters (Atomic for thread-safety)
    std::atomic<float> speed { 0.2f };
    std::atomic<float> depth { 0.5f };
    std::atomic<bool>  isChorus { true };
    std::atomic<float> outputGain { 0.8f };

private:
    void updateFilters(float modulation);

    // Ripped Math Tables (Constants)
    static const float vibeCoeffs[20];

    // DSP Components
    juce::dsp::StateVariableTPTFilter<float> apfs[4];
    juce::dsp::Oscillator<float> lfo;
    
    // Smoothed Values for parameter changes
    juce::LinearSmoothedValue<float> smoothedDepth;
    juce::LinearSmoothedValue<float> smoothedGain;

    double sampleRate = 44100.0;
};
