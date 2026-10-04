#include "TheVibeProcessor.h"

// Ripped from THEVIBE.ZD2 @ Offset 0x0f78
const float TheVibeProcessor::vibeCoeffs[20] = { 
    -0.200000f, 1.000000f, 1.000000f, 1.000000f, 0.250000f, 
    -1.473461f, -1.473461f, -0.059953f, -0.059953f, 0.952696f, 
    0.952696f, 0.997429f, 0.997429f, 0.968276f, 0.997804f, 
    0.999286f, 0.902303f, -0.181673f, 0.355274f, 1.000000f 
};

TheVibeProcessor::TheVibeProcessor()
{
    for (int i = 0; i < 4; ++i)
        apfs[i].setType(juce::dsp::StateVariableTPTFilterType::allpass);

    lfo.initialise([](float x) { return std::sin(x); });
}

void TheVibeProcessor::prepare(const juce::dsp::ProcessSpec& spec)
{
    sampleRate = spec.sampleRate;

    for (int i = 0; i < 4; ++i)
        apfs[i].prepare(spec);

    lfo.prepare(spec);
    
    smoothedDepth.reset(sampleRate, 0.05);
    smoothedGain.reset(sampleRate, 0.05);
}

void TheVibeProcessor::reset()
{
    for (int i = 0; i < 4; ++i)
        apfs[i].reset();

    lfo.reset();
}

void TheVibeProcessor::process(juce::AudioBuffer<float>& buffer)
{
    const int numSamples = buffer.getNumSamples();
    const int numChannels = buffer.getNumChannels();

    // Update LFO frequency (Speed mapping)
    lfo.setFrequency(speed.load() * 10.0f); // 0-10Hz range

    // Process sample by sample to allow per-sample modulation
    for (int i = 0; i < numSamples; ++i)
    {
        // 1. Calculate Modulation
        float lfoVal = lfo.processSample(0.0f); // Generate raw LFO
        float modulation = (lfoVal * depth.load() * 0.5f) + 0.5f;

        // 2. Update Filters (Staggered all-pass filters)
        // Frequency ratios inspired by hardware analysis
        const float baseFreqs[4] = { 400.0f, 650.0f, 1050.0f, 1600.0f };
        for (int stage = 0; stage < 4; ++stage)
        {
            // Modulation shifts frequencies by roughly 2 octaves
            float freq = baseFreqs[stage] * std::pow(2.0f, modulation * 2.0f);
            apfs[stage].setCutoffFrequency(juce::jmin(freq, (float)sampleRate * 0.45f));
        }

        // 3. Process Channels
        for (int ch = 0; ch < numChannels; ++ch)
        {
            float dry = buffer.getSample(ch, i);
            float wet = dry;

            // Cascade through 4 all-pass stages
            for (int stage = 0; stage < 4; ++stage)
                wet = apfs[stage].processSample(ch, wet);

            // 4. Output Mixing (Chorus vs Vibrato)
            float output = isChorus.load() ? (dry + wet) * 0.5f : wet;
            buffer.setSample(ch, i, output * outputGain.load());
        }
    }
}
