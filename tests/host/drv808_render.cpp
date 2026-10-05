// Render effects/common/ts808_core.h over a raw float32 mono file.
// usage: drv808_render in.f32 out.f32 drive(0..10) tone(0..1) gain
#include <cstdio>
#include <cstdlib>
#include <vector>
extern "C" {
#include "../../effects/common/ts808_core.h"
}
int main(int argc, char** argv)
{
    if (argc != 6) return 2;
    FILE* f = std::fopen(argv[1], "rb"); if (!f) return 1;
    std::vector<float> x; float v;
    while (std::fread(&v, 4, 1, f) == 1) x.push_back(v);
    std::fclose(f);
    Ts808State st = {}; Ts808Coeffs k;
    ts808_coeffs(&k, (float)std::atof(argv[3]), (float)std::atof(argv[4]), (float)std::atof(argv[5]));
    for (auto& s : x) s = ts808_process(&st, &k, s);
    f = std::fopen(argv[2], "wb"); std::fwrite(x.data(), 4, x.size(), f); std::fclose(f);
    return 0;
}
