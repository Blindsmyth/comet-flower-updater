// Prints the exact tone-stage biquad coefficients CF Muff's shipped lookup table
// (MUFF_TONE, effects/common/muff_blob.h) produces at a grid of Tone knob positions.
// muff_out() in effects/common/muff_g1.h applies these directly: this is the real
// coefficient table, not a reimplementation. Sustain/volume don't affect the tone
// stage, so any value works for them.
#include <cstdio>
extern "C" {
#include "../../effects/common/muff_g1.h"
}

int main()
{
    for (int i = 0; i <= 40; ++i) {
        float t = (float)i / 40.0f;
        MuffCoeffs k;
        muff_coeffs(&k, 0.6f, t, 1.0f);
        std::printf("%.6f %.10f %.10f %.10f %.10f %.10f\n",
                    t, k.t_b0, k.t_b1, k.t_b2, k.t_a1, k.t_a2);
    }
    return 0;
}
