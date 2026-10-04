# Case Study: NYC Muff (Big Muff Pi Clone)

## DSP Analysis Results

### 1. Oversampling
The module uses 4x oversampling to prevent aliasing from high-gain distortion.
- **Symbol**: `OVS_UP_COE`
- **Logic**: Upsample -> Distort -> Downsample (`OVS_DOWN_COE`).

### 2. Distortion Clipping
- **Physical**: Silicon diodes in feedback loops.
- **DSP**: Modeled via a non-linear transfer function (likely `tanh` or a specific table `Muff_Sustain_Dwn_Att_tbl`).

### 3. Parallel Tone Stack
The "math" of the tone knob is a parallel mix of two filters:
- **LPF Path**: `Muff_Tone_LPF_Mix_tbl` (at ~400Hz)
- **HPF Path**: `Muff_Tone_HPF_Mix_tbl` (at ~1200Hz)
- **Mixing**: `(LPF * (1-Tone)) + (HPF * Tone)`. This creates the mid-scoop at 50%.

### 4. Impulse Responses / Tables
Look-up tables are used for parameter scaling:
- `Muff_Level_Tbl`: Volume curve.
- `Muff_Tone_LPF_Ftbl`: Cutoff frequency scaling.
