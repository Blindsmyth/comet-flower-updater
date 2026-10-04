#include "NYCMuffProcessor.h"

// Ripped from NYC_MUFF.ZD2 @ Offset 0x1814
const float NYCMuffProcessor::gainTable[23] = { 
    0.017733f, 0.089600f, 0.168000f, 0.219333f, 0.289333f, 
    0.430108f, 0.526882f, 0.697849f, 0.890323f, 0.967742f, 
    0.967742f, 0.562341f, 0.630957f, 0.707946f, 0.794328f, 
    0.891251f, 1.000000f, 1.258925f, 1.584893f, 1.995262f, 
    2.511886f, 4.466836f, 4.466836f 
};

// Ripped from NYC_MUFF.ZD2 @ Offset 0x18a4
const float NYCMuffProcessor::mixTable[10] = { 
    0.543988f, 0.857263f, 1.103487f, 1.306694f, 1.477373f, 
    1.735552f, 1.996876f, 2.262329f, 2.532558f, 2.808000f 
};

NYCMuffProcessor::NYCMuffProcessor() :
    oversampler(2, 2, juce::dsp::Oversampling<float>::filterHalfBandPolyphaseIIR)
{
    lpf.setType(juce::dsp::StateVariableTPTFilterType::lowpass);
    hpf.setType(juce::dsp::StateVariableTPTFilterType::highpass);
}

void NYCMuffProcessor::prepare(const juce::dsp::ProcessSpec& spec)
{
    sampleRate = spec.sampleRate;

    oversampler.initProcessing(spec.maximumBlockSize);
    
    juce::dsp::ProcessSpec oversampledSpec = spec;
    oversampledSpec.sampleRate = spec.sampleRate * oversampler.getOversamplingFactor();

    lpf.prepare(oversampledSpec);
    hpf.prepare(oversampledSpec);

    // Big Muff tone stack frequencies
    lpf.setCutoffFrequency(450.0f);
    hpf.setCutoffFrequency(1100.0f);
}

void NYCMuffProcessor::reset()
{
    lpf.reset();
    hpf.reset();
    oversampler.reset();
}

void NYCMuffProcessor::process(juce::AudioBuffer<float>& buffer)
{
    juce::dsp::AudioBlock<float> block(buffer);
    
    // 1. Upsample to prevent aliasing (Pro requirement for high-gain distortion)
    auto oversampledBlock = oversampler.processSamplesUp(block);
    
    const int numSamples = (int)oversampledBlock.getNumSamples();
    const int numChannels = (int)oversampledBlock.getNumChannels();

    // Mapping sustain 0-1 to gainTable
    int gainIdx = juce::jlimit(0, 22, (int)(sustain.load() * 22.0f));
    float gainFactor = gainTable[gainIdx] * 10.0f; // Scale for tanh

    for (int i = 0; i < numSamples; ++i)
    {
        for (int ch = 0; ch < numChannels; ++ch)
        {
            float* samples = oversampledBlock.getChannelPointer(ch);
            float dry = samples[i];

            // 2. Distortion Stage
            float distorted = std::tanh(dry * gainFactor);

            // 3. Parallel Tone Stack
            float low = lpf.processSample(ch, distorted);
            float high = hpf.processSample(ch, distorted);

            // Mix using Tone parameter
            float mixed = (low * (1.0f - tone.load())) + (high * tone.load());

            // 4. Dry/Wet Balance & Output Gain
            samples[i] = (dry * (1.0f - balance.load())) + (mixed * balance.load() * outputGain.load());
        }
    }

    // 5. Downsample
    oversampler.processSamplesDown(block);
}
