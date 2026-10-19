// delay_block_test.cpp - the C6745 block form of the CF Delay core (delay_block,
// effects/common/delay_g1.h) must equal the per-sample form (delay_process) bit
// for bit: both outputs and the whole state (line included), with Time swept
// through 0 (the per-sample fallback below 17 samples) up to 2 s, feedback and
// mix moving every block, and overload. Build/run: tests/host/build_delay_block_test.bat
#include <cmath>
#include <cstdio>
#include <cstdint>
#include <cstring>

#include "delay_g1.h"

static DelayState a, b;
static uint32_t rng = 777u;
static float frand() { rng = rng * 1664525u + 1013904223u; return (float)(rng >> 8) / 8388608.0f - 1.0f; }

int main()
{
    std::memset(&a, 0, sizeof a);
    std::memset(&b, 0, sizeof b);
    const int blocks = 44100 * 12 / 16;
    long mismatches = 0, total = 0, fallback_blocks = 0;
    double phase = 0.0;
    for (int blk = 0; blk < blocks; ++blk) {
        double t = blk * 16.0 / 44100.0;
        // Time: 0 for the first 2 s (fallback), a jump to 2 s, then a slow sweep through 0 and back
        float kt = t < 2.0 ? 0.0f : t < 4.0 ? 1.0f : (float)(0.5 + 0.5 * std::cos(t * 0.9));
        float fb = 0.5f + 0.5f * (float)std::sin(t * 1.7), mix = 0.5f + 0.5f * (float)std::sin(t * 0.6 + 1.0);
        DelayCoeffs k;
        delay_coeffs(&k, 2000.0f * kt, 0.92f * fb, mix);
        if (blk == 0) { delay_snap(&a, &k); delay_snap(&b, &k); }
        fallback_blocks += !(b.cur >= 17.0f && k.target >= 17.0f);
        float in[16], la[16], ra[16], lb[16], rb[16];
        for (int i = 0; i < 16; ++i) {
            phase += 2.0 * 3.14159265358979 * 220.0 / 44100.0;
            float env = (float)std::exp(-4.0 * std::fmod(t, 0.5));
            in[i] = ((int)t % 5 == 3) ? 6.0f * frand() : 0.6f * env * (float)std::sin(phase) + 0.01f * frand();
        }
        for (int i = 0; i < 16; ++i) delay_process(&a, &k, in[i], &la[i], &ra[i]);
        delay_block(&b, &k, in, lb, rb, 16);
        for (int i = 0; i < 16; ++i, ++total)
            if (std::memcmp(&la[i], &lb[i], 4) || std::memcmp(&ra[i], &rb[i], 4)) {
                if (mismatches < 5)
                    std::printf("mismatch block %d sample %d: %.9g/%.9g vs %.9g/%.9g\n", blk, i, la[i], ra[i], lb[i], rb[i]);
                ++mismatches;
            }
        if (std::memcmp(&a, &b, sizeof a) != 0) {
            std::printf("FAIL: state differs after block %d\n", blk);
            return 1;
        }
    }
    std::printf("%ld samples, %ld mismatches (%ld blocks on the per-sample fallback)\n", total, mismatches, fallback_blocks);
    std::printf(mismatches || !fallback_blocks ? "FAIL\n" : "PASS: delay_block == delay_process bit for bit\n");
    return mismatches || !fallback_blocks ? 1 : 0;
}
