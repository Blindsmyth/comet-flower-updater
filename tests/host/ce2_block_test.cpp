// ce2_block_test.cpp - the C6745 block form of the CF CE-2 core (ce2_block,
// effects/common/ce2_g1.h) must equal the per-sample form (ce2_process) bit
// for bit: output and state, over sweeps, noise, silence, overload and knobs
// changing every block. Build/run: tests/host/build_ce2_block_test.bat
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>

#include "ce2_g1.h"

static uint32_t rng = 12345u;
static float frand() { rng = rng * 1664525u + 1013904223u; return (float)(rng >> 8) / 8388608.0f - 1.0f; }

int main()
{
    static Ce2State a, b;
    std::memset(&a, 0, sizeof a);
    std::memset(&b, 0, sizeof b);
    const int blocks = 44100 * 6 / 16;
    long mismatches = 0, total = 0;
    double phase = 0.0;
    for (int blk = 0; blk < blocks; ++blk) {
        double t = blk * 16.0 / 44100.0;
        // knobs move every block, sweeping all ranges
        float sus = 0.5f + 0.5f * (float)std::sin(t * 1.3), tone = 0.5f + 0.5f * (float)std::sin(t * 0.7 + 1.0);
        float vol = 0.5f + 0.5f * (float)std::sin(t * 2.1 + 2.0);
        Ce2Coeffs k;
        ce2_coeffs(&k, 0.1f + 7.9f * sus, tone, vol);
        float in[16], outa[16], outb[16];
        int seg = (int)(t / 1.0);    // one-second segments: sweep, noise, silence, overload, chord, quiet
        for (int i = 0; i < 16; ++i) {
            double f = 80.0 * std::pow(2.0, 7.0 * std::fmod(t, 1.0));
            phase += 2.0 * 3.14159265358979 * f / 44100.0;
            float x;
            switch (seg) {
            case 0: x = 0.5f * (float)std::sin(phase); break;
            case 1: x = 0.3f * frand(); break;
            case 2: x = 0.0f; break;
            case 3: x = 40.0f * (float)std::sin(phase) + 5.0f * frand(); break;
            case 4: x = 0.2f * (float)(std::sin(phase) + std::sin(phase * 1.26) + std::sin(phase * 1.5)); break;
            default: x = 1e-3f * frand(); break;
            }
            in[i] = x;
        }
        for (int i = 0; i < 16; ++i) outa[i] = ce2_process(&a, &k, in[i]);
        ce2_block(&b, &k, in, outb, 16);
        for (int i = 0; i < 16; ++i, ++total)
            if (std::memcmp(&outa[i], &outb[i], 4) != 0) {
                if (mismatches < 5)
                    std::printf("mismatch block %d sample %d: %.9g vs %.9g\n", blk, i, outa[i], outb[i]);
                ++mismatches;
            }
        if (std::memcmp(&a, &b, sizeof a) != 0) {
            std::printf("FAIL: state differs after block %d\n", blk);
            return 1;
        }
    }
    std::printf("%ld samples, %ld mismatches\n", total, mismatches);
    std::printf(mismatches ? "FAIL\n" : "PASS: ce2_block == ce2_process bit for bit\n");
    return mismatches ? 1 : 0;
}
