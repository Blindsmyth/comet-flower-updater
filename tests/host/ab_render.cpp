// Host render of the pedal kernels for tools/ua_ab.py (offline A/B, same code as the pedal):
//   cftone_render.exe <seconds> <out.f32>        CF Tone program (effects/cftone/cftone.c)
//   hiwatt_render_os{4,2}.exe <in.f32> <out.f32>  CF Watt at HW_OS 4 / 2, default knobs, cab on
// Built by build_ab_render.bat; raw little-endian float32 mono, 44.1 kHz.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <vector>
extern "C" {
#ifdef AB_TONE
#include "cftone.c"
#else
#include "hiwatt.c"
#endif
}

int main(int argc, char** argv)
{
    static uint32_t state[128];
    static uint32_t wbuf[1024];
    uint32_t desc[3] = { (uint32_t)(uintptr_t)wbuf, (uint32_t)(uintptr_t)wbuf + sizeof wbuf, sizeof wbuf };
    float coef[16] = {};
    float bus[32];
    void* inst[4] = { nullptr, coef, state, sizeof(void*) == 4 ? (void*)desc : nullptr };
    void* ctx[8] = { nullptr, bus };
    state[SH_STATE_GUARD_WORD] = SH_STATE_GUARD;
    coef[SH_COEFF_BYPASS] = 1.0f;
#ifdef AB_TONE
    if (argc < 3) return 2;
    long n = (long)(atof(argv[1]) * 44100) / 16 * 16;
    coef[SH_PARAM_LEVEL] = 0.25f;
    std::vector<float> out(n);
    for (long b = 0; b < n; b += 16) {
        std::memset(bus, 0, sizeof bus);
        SH_AUDIO_FN(inst, ctx);
        std::memcpy(&out[b], bus, 16 * sizeof(float));
    }
    FILE* f = std::fopen(argv[2], "wb"); std::fwrite(out.data(), 4, n, f); std::fclose(f);
#else
    if (argc < 3) return 2;
    coef[SH_PARAM_VOLUME] = coef[SH_PARAM_TREBLE] = coef[SH_PARAM_MIDDLE] = 0.5f;
    coef[SH_PARAM_BASS] = coef[SH_PARAM_PRESENCE] = coef[SH_PARAM_MASTER] = 0.5f;
    coef[SH_PARAM_CAB] = 1.0f;
    if (argc >= 9) {                   // optional knobs 0..100: Volume Treble Middle Bass Presence Master
        coef[SH_PARAM_VOLUME] = atof(argv[3]) / 100; coef[SH_PARAM_TREBLE] = atof(argv[4]) / 100;
        coef[SH_PARAM_MIDDLE] = atof(argv[5]) / 100; coef[SH_PARAM_BASS] = atof(argv[6]) / 100;
        coef[SH_PARAM_PRESENCE] = atof(argv[7]) / 100; coef[SH_PARAM_MASTER] = atof(argv[8]) / 100;
    }
    if (const char* l = std::getenv("AB_LOAD")) {
        FILE* g = std::fopen(l, "rb"); std::fread(wbuf, 1, sizeof wbuf, g);
        uint32_t old[128]; std::fread(old, 1, sizeof old, g); std::fclose(g);
        if (std::getenv("AB_LOAD_STATE")) std::memcpy(state, old, sizeof state);   // state not zeroed
    }
    FILE* f = std::fopen(argv[1], "rb"); std::vector<float> x;
    float v; while (std::fread(&v, 4, 1, f) == 1) x.push_back(v); std::fclose(f);
    long n = (long)x.size() / 16 * 16;
    for (long b = 0; b < n; b += 16) {
        for (int i = 0; i < 16; ++i) bus[i] = bus[i + 16] = x[b + i];
        SH_AUDIO_FN(inst, ctx);
        for (int i = 0; i < 16; ++i) x[b + i] = bus[i];
    }
    f = std::fopen(argv[2], "wb"); std::fwrite(x.data(), 4, n, f); std::fclose(f);
    // Experiment hooks: AB_DUMP=<file> saves the work buffer + slot state after the run;
    // AB_LOAD=<file> (set before the run, see below) starts from them, as when a slot's
    // previous effect left its work buffer and state behind.
    if (const char* d = std::getenv("AB_DUMP")) {
        FILE* g = std::fopen(d, "wb"); std::fwrite(wbuf, 1, sizeof wbuf, g); std::fwrite(state, 1, sizeof state, g); std::fclose(g);
    }
#endif
    return 0;
}
