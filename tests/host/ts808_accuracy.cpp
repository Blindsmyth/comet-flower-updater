// TS808 clipping-stage accuracy bench.
// Writes float32 outputs for the reference and each candidate model, for a
// set of sine tests; tests/host/ts808_accuracy.py analyses them.
//
// Reference: double precision at 32x, C3/R4 and C4 as trapezoidal companions,
// diode pair (Shockley) solved to convergence every sample, followed by the
// same linear post stages as the models (723 Hz R7/C5 pole, pole-zero tone,
// 5 Hz output coupling), all bilinear at 32x.
#include <cmath>
#include <cstdio>
#include <string>
#include <vector>
extern "C" {
#include "../../effects/common/ts808_exact.h"
}

static const double PI = 3.14159265358979323846;
static const double IS = 2.52e-9, NVT = 1.752 * 0.025852;
static const int SR = 44100;

static double rdrive(double knob) { double w = knob * knob; return 51000.0 + w * 500000.0; }

// ---------- linear helpers (double, any rate) ---------------------------
struct OnePoleD {                       // TPT one-pole, matches OnePoleTPT
    double g = 0, s = 0;
    void set(double sr, double fc) { double t = std::tan(PI * fc / sr); g = t / (1 + t); }
    double lp(double x) { double v = (x - s) * g, y = v + s; s = y + v; return y; }
    double hp(double x) { return x - lp(x); }
};
struct ToneD {                          // the core's pole-zero tone, at rate sr
    double b0 = 1, b1 = 0, a1 = 0, z = 0;
    void set(double sr, double t) {
        double fz = 723.0 * std::pow(33000.0 / 723.0, 1.0 - t), k = 2 * sr;
        fz = std::min(fz, 0.45 * sr);
        double wz = 2 * PI * fz, wp = 2 * PI * 3290.0, a0 = 1 + k / wp;
        b0 = (1 + k / wz) / a0; b1 = (1 - k / wz) / a0; a1 = (1 - k / wp) / a0;
    }
    double p(double x) { double y = b0 * x + z; z = b1 * x - a1 * y; return y; }
};

// ---------- reference ------------------------------------------------------
static std::vector<float> reference(double f0, double amp, double knob, double tone,
                                    double secs, int os)
{
    const double fs = SR * (double)os, T = 1.0 / fs, Rf = rdrive(knob);
    const int N = (int)(secs * fs);
    std::vector<float> out(N);
    double vc3 = 0, ig_prev = 0, v = 0, ic4 = 0;
    const double kC3 = T / (2 * 47e-9), gC4 = 2 * 51e-12 / T;
    OnePoleD post, dc, in1, in2; post.set(fs, 723.0); dc.set(fs, 5.0);
    in1.set(fs, 1 / (2 * PI * 510e3 * 0.02e-6)); in2.set(fs, 1 / (2 * PI * 10e3 * 1e-6));
    ToneD tn; tn.set(fs, tone);
    for (int n = 0; n < N; ++n) {
        double x = in2.hp(in1.hp(amp * std::sin(2 * PI * f0 * n * T)));
        double ig = (x - vc3 - kC3 * ig_prev) / (4700.0 + kC3);
        vc3 += kC3 * (ig + ig_prev); ig_prev = ig;
        double rhs = ig + gC4 * v + ic4, vn = v;
        for (int it = 0; it < 60; ++it) {
            double e = std::exp(vn / NVT), ei = 1 / e;
            double f = vn / Rf + gC4 * vn + IS * (e - ei) - rhs;
            double d = 1 / Rf + gC4 + IS / NVT * (e + ei);
            double st = f / d; vn -= st;
            if (std::fabs(st) < 1e-14) break;
        }
        ic4 = gC4 * (vn - v) - ic4; v = vn;
        double y = post.lp(x + v);
        out[n] = (float)dc.hp(tn.p(y) * 0.5);
    }
    return out;
}

// ---------- half-band 2x stage (as Oversampler2x(6)) -----------------------
struct HB {
    float xh[12] = {}, eh[7] = {}, oh[13] = {};
    void up(float x, float& a, float& b) {
        for (int i = 11; i > 0; --i) xh[i] = xh[i - 1]; xh[0] = x;
        a = xh[6];
        b = 2.0f * (OS_C0 * (xh[6] + xh[5]) + OS_C1 * (xh[7] + xh[4]) + OS_C2 * (xh[8] + xh[3])
                  + OS_C3 * (xh[9] + xh[2]) + OS_C4 * (xh[10] + xh[1]) + OS_C5 * (xh[11] + xh[0]));
    }
    float down(float a, float b) {
        for (int i = 6; i > 0; --i) eh[i] = eh[i - 1]; eh[0] = a;
        for (int i = 12; i > 0; --i) oh[i] = oh[i - 1]; oh[0] = b;
        return 0.5f * eh[6] + OS_C0 * (oh[7] + oh[6]) + OS_C1 * (oh[8] + oh[5]) + OS_C2 * (oh[9] + oh[4])
             + OS_C3 * (oh[10] + oh[3]) + OS_C4 * (oh[11] + oh[2]) + OS_C5 * (oh[12] + oh[1]);
    }
};

// ---------- model B: Shockley memoryless + ADAA, 2x ------------------------
struct ModelB {
    HB os; float sfb = 0, ssoft = 0, spost = 0, zt = 0, sdc = 0, x1 = 0, v1 = 0;
    Ts808Coeffs k; float a;
    ModelB(double knob, double tone) {
        ts808_coeffs(&k, (float)(knob * 10), (float)tone, 0.5f);
        a = (float)(2 * IS * rdrive(knob));
    }
    double Fv(double u, float v) {                // antiderivative of v(u)
        double c = 0.5 * ((double)sd_expf(v * SD_INVNVT) + (double)sd_expf(-v * SD_INVNVT));
        return u * v - 0.5 * (double)v * v - (double)a * SD_NVT * c;
    }
    float stage(float x) {
        float hp = x - ts_onepole_lp(&sfb, TS_G_FB, x), lp = x - hp;
        float g = k.gm1, u = g * hp, u1 = g * x1;
        float v = sd_solve(u, a, SD_INVNVT, v1, 1.0f);
        float vprev = sd_solve(u1, a, SD_INVNVT, v1, 1.0f);   // F(x1) recomputed
        double F0 = 0.5 * (double)hp * hp + Fv(u, v) / g;
        double F1 = 0.5 * (double)x1 * x1 + Fv(u1, vprev) / g;
        double d = (double)hp - x1; float y;
        if (std::fabs(d) > 1e-4) y = (float)(F0 - F1) * ts_rcp((float)d);
        else { float m = 0.5f * (hp + x1); y = m + sd_solve(g * m, a, SD_INVNVT, v, 1.0f); }
        x1 = hp; v1 = v;
        y = ts_onepole_lp(&ssoft, k.g_soft, y);
        y = ts_onepole_lp(&spost, TS_G_POST, y + lp);
        float o = k.b0 * y + zt; zt = k.b1 * y - TS_TONE_A1 * o; return o;
    }
    float process(float x) {
        float a0, b0; os.up(x, a0, b0);
        float y = os.down(stage(a0), stage(b0));
        y = y - ts_onepole_lp(&sdc, TS_G_DC, y); return y * k.gain;
    }
};

// ---------- model C: full implicit (C4 inside), 2^L x oversampling ---------
struct ModelC {
    int L; HB st[3]; double fs; float vc3 = 0, igp = 0, v = 0, ic4 = 0, spost = 0, zt = 0, sdc = 0;
    float kC3, gC4Rf, a, Rf, gpost, b0, b1, a1;
    ModelC(int levels, double knob, double tone) : L(levels) {
        fs = SR * (double)(1 << L);
        double T = 1 / fs; Rf = (float)rdrive(knob);
        kC3 = (float)(T / (2 * 47e-9)); gC4Rf = (float)(2 * 51e-12 / T * Rf);
        a = (float)(2 * IS * Rf);
        OnePoleD p; p.set(fs, 723.0); gpost = (float)p.g;
        ToneD t; t.set(fs, tone); b0 = (float)t.b0; b1 = (float)t.b1; a1 = (float)t.a1;
    }
    float stage(float x) {
        float ig = (x - vc3 - kC3 * igp) * ts_rcp(4700.0f + kC3);
        vc3 += kC3 * (ig + igp); igp = ig;
        float rhs = Rf * ig + gC4Rf * v + Rf * ic4;
        float vn = sd_solve(rhs, a, SD_INVNVT, v, 1.0f + gC4Rf);
        ic4 = gC4Rf / Rf * (vn - v) - ic4; v = vn;
        float y = ts_onepole_lp(&spost, gpost, x + v);
        float o = b0 * y + zt; zt = b1 * y - a1 * o; return o;
    }
    float run(float x, int lvl) {
        if (lvl == L) return stage(x);
        float a0, b0_; st[lvl].up(x, a0, b0_);
        float ya = run(a0, lvl + 1), yb = run(b0_, lvl + 1);
        return st[lvl].down(ya, yb);
    }
    float process(float x) {
        float y = run(x, 0);
        y = y - ts_onepole_lp(&sdc, TS_G_DC, y); return y * 0.5f;
    }
};

static void write(const std::string& path, const std::vector<float>& v)
{
    FILE* f = std::fopen(path.c_str(), "wb"); std::fwrite(v.data(), 4, v.size(), f); std::fclose(f);
}

int main(int argc, char** argv)
{
    std::string dir = argc > 1 ? argv[1] : ".";
    const double secs = 1.0, tone = 0.6;
    const double freqs[] = { 220.0, 1000.0, 3700.0 }, amps[] = { 0.05, 0.25, 0.7 }, knobs[] = { 0.0, 0.5, 1.0 };
    for (double f0 : freqs) for (double amp : amps) for (double kn : knobs) {
        char tag[64]; std::snprintf(tag, sizeof tag, "f%d_a%03d_k%03d", (int)f0, (int)(amp * 100), (int)(kn * 100));
        write(dir + "/ref_" + tag + ".f32", reference(f0, amp, kn, tone, secs, 32));
        const int N = (int)(secs * SR);
        std::vector<float> in(N); for (int n = 0; n < N; ++n) in[n] = (float)(amp * std::sin(2 * PI * f0 * n / SR));
        { Ts808State s = {}; Ts808Coeffs k; ts808_coeffs(&k, (float)(kn * 10), (float)tone, 0.5f);
          std::vector<float> o(N); for (int n = 0; n < N; ++n) o[n] = ts808_process(&s, &k, in[n]);
          write(dir + "/A_" + tag + ".f32", o); }
        { ModelB m(kn, tone); std::vector<float> o(N); for (int n = 0; n < N; ++n) o[n] = m.process(in[n]);
          write(dir + "/B_" + tag + ".f32", o); }
        { TsxState s = {}; TsxCoeffs k; tsx_coeffs(&k, (float)(kn * 10), (float)tone, 0.5f);
          std::vector<float> o(N); for (int n = 0; n < N; ++n) o[n] = tsx_process(&s, &k, in[n]);
          write(dir + "/X_" + tag + ".f32", o); }
        for (int L : { 2, 3 }) {
            ModelC m(L, kn, tone); std::vector<float> o(N); for (int n = 0; n < N; ++n) o[n] = m.process(in[n]);
            write(dir + "/C" + std::to_string(1 << L) + "_" + tag + ".f32", o);
        }
    }
    std::printf("done\n");
    return 0;
}
