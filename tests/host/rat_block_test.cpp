#include <cstdio>
#include <cmath>
#include <cstring>
#include <vector>
#include <random>

extern "C" {
#include "../../effects/common/rat_g1.h"
}

int main()
{
    printf("Running RAT block vs process bit-identity tests...\n");

    const int NUM_BLOCKS = 500;
    const int N = NUM_BLOCKS * 16;
    std::vector<float> in(N);
    std::vector<float> out_proc(N);
    std::vector<float> out_blk(N);

    // Test across several knob settings
    float dists[] = { 0.0f, 3.0f, 7.0f, 10.0f };
    float flts[]  = { 0.1f, 0.5f, 0.9f };
    float vols[]  = { 0.5f, 1.0f };

    std::mt19937 rng(42);
    std::uniform_real_distribution<float> dist_noise(-1.5f, 1.5f);

    int test_idx = 0;
    int failures = 0;

    for (float d : dists) {
        for (float f : flts) {
            for (float v : vols) {
                // Generate signal: mix of sines + noise bursts
                for (int i = 0; i < N; ++i) {
                    float t = (float)i / 44100.0f;
                    in[i] = 0.5f * std::sin(2.0f * 3.14159265f * 440.0f * t)
                          + 0.3f * std::sin(2.0f * 3.14159265f * 1250.0f * t)
                          + 0.2f * dist_noise(rng);
                }

                RatState s1 = {};
                RatState s2 = {};
                RatCoeffs k1, k2;
                rat_coeffs(&k1, d, f, v);
                rat_coeffs(&k2, d, f, v);

                // Run sample-by-sample
                for (int i = 0; i < N; ++i) {
                    out_proc[i] = rat_process(&s1, &k1, in[i]);
                }

                // Run block-by-block
                rat_block(&s2, &k2, in.data(), out_blk.data(), N);

                // Compare bit-identity
                int diff_count = 0;
                float max_diff = 0.0f;
                for (int i = 0; i < N; ++i) {
                    float diff = std::fabs(out_proc[i] - out_blk[i]);
                    if (diff > max_diff) max_diff = diff;
                    uint32_t u1, u2;
                    std::memcpy(&u1, &out_proc[i], 4);
                    std::memcpy(&u2, &out_blk[i], 4);
                    if (u1 != u2) {
                        diff_count++;
                    }
                }

                test_idx++;
                if (diff_count > 0 || max_diff > 0.0f) {
                    printf("  Test %2d (d=%.1f, f=%.1f, v=%.1f): FAIL - %d bit diffs, max diff: %e\n",
                           test_idx, d, f, v, diff_count, max_diff);
                    failures++;
                } else {
                    printf("  Test %2d (d=%.1f, f=%.1f, v=%.1f): PASS - exact bit identity\n",
                           test_idx, d, f, v);
                }
            }
        }
    }

    if (failures == 0) {
        printf("ALL %d TESTS PASSED - 100%% BIT IDENTICAL\n", test_idx);
        return 0;
    } else {
        printf("%d FAILURES DETECTED\n", failures);
        return 1;
    }
}
