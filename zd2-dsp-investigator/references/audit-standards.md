# JUCE Engineering Standards (Pro 3.1)

Any code generated for the JUCE framework MUST adhere to these standards to ensure hardware fidelity and stability.

## 1. Architectural Separation
- **Header (.h)**: Definitions and atomic parameters only.
- **Source (.cpp)**: Implementation of `prepare` and `process`.
- **Reasoning**: This is the industry standard for JUCE development and ensures faster compilation.

## 2. Thread Safety
- **Parameters**: All user-facing parameters (Speed, Depth, etc.) MUST use `std::atomic<float>`.
- **Real-time Safety**: NEVER allocate memory (`new`, `malloc`) or log to console (`std::cout`, `DBG`) inside the `process` block.

## 3. Hardware Fidelity (Scaling)
- **Table Indexing**: Do NOT just look at the values. You MUST implement the indexing logic:
  ```cpp
  int idx = juce::jlimit(0, tableSize - 1, (int)(param.load() * (tableSize - 1)));
  float gain = hardwareTable[idx];
  ```
- **Oversampling**: If the effect involves high-gain distortion (Group 3/Drive), **Oversampling is Mandatory** (at least 2x).

## 4. Performance
- **LFOs**: Prefer `juce::dsp::Oscillator` over `std::sin` in the sample loop.
- **Filters**: Use `juce::dsp::StateVariableTPTFilter` for "analog-style" parameter modulation without artifacts.
