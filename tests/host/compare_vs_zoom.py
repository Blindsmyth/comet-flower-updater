"""Numbers: Green 808 (the real pedal code via drv808_render.exe) vs the
nonlinear core of Zoom's TS Drive, rebuilt from the decoded binary
(recon/05): drive table -> 4x upsample (x4 zero-stuff + 5th-order IIR) ->
asymmetric piecewise-quadratic clipper -> same IIR -> decimate.

Zoom's fixed EQ biquads and the order of its stages are NOT modelled, so the
Zoom figures describe its clipping core, not the whole effect.
"""
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RENDER = ROOT / "build" / "host" / "drv808_render.exe"
TMP = ROOT / "build" / "host"
SR = 44100

# --- decoded Zoom data (TS_DRIVE.ZD2) -----------------------------------
OVS_B = np.array([0.000887, 0.003756, 0.006944, 0.006944, 0.003756, 0.000887])
OVS_A = np.array([3.612194, -5.727617, 4.889112, -2.23206, 0.435198])
DRIVE_TBL = [1.332514, 1.515553, 1.740797, 2.046577, 2.554789, 3.114133,
             3.85869, 4.724075, 6.259302, 9.456255, 9.891251]   # knob 0,10..100
CLIP_P = [1.0, 1.330363, 0.0, 0.925, 1.43823, 0.0, -0.486842, -2.732636]


def zoom_clip(x):
    p = CLIP_P
    u = p[0] * x
    neg = x < 0
    a = np.clip(u * np.where(neg, p[7], p[4]), -1, 1)
    b = np.clip(p[1] * u, -1, 1)
    c = np.clip(u * np.where(neg, p[5], p[2]) + np.where(neg, p[6], p[3]), -1, 1)
    return a * c + b * np.abs(a - 1)


def iir(x):
    y = np.zeros_like(x)
    xb = np.concatenate([np.zeros(5), x])
    yb = np.zeros(len(x) + 5)
    for n in range(len(x)):
        acc = np.dot(OVS_B, xb[n + 5::-1][:6])
        acc += np.dot(OVS_A, yb[n + 4::-1][:5])
        yb[n + 5] = acc
    return yb[5:]


def zoom_core(x, knob):
    g = np.interp(knob, np.arange(0, 101, 10), DRIVE_TBL)
    up = np.zeros(len(x) * 4)
    up[::4] = x * g * 4.0
    return iir(zoom_clip(iir(up)))[::4]


def ours(x, drive, tone=0.6, gain=1.0):
    TMP.mkdir(parents=True, exist_ok=True)
    i, o = TMP / "in.f32", TMP / "out.f32"
    x.astype(np.float32).tofile(i)
    subprocess.run([str(RENDER), str(i), str(o), str(drive), str(tone), str(gain)], check=True)
    return np.fromfile(o, dtype=np.float32).astype(np.float64)


def spectrum(y):
    y = y[SR // 2:]                       # skip the start-up transient
    w = np.blackman(len(y))
    return np.abs(np.fft.rfft(y * w)), np.fft.rfftfreq(len(y), 1 / SR)


def harmonics(y, f0, n=9):
    s, f = spectrum(y)
    amp = []
    for k in range(1, n + 1):
        if k * f0 >= SR / 2:
            break
        idx = np.argmin(np.abs(f - k * f0))
        amp.append(s[max(idx - 3, 0):idx + 4].max())
    return np.array(amp)


def alias_db(y, f0):
    s, f = spectrum(y)
    p = s ** 2
    mask = np.zeros_like(p, dtype=bool)
    for k in range(1, int((SR / 2) // f0) + 1):
        mask |= np.abs(f - k * f0) < 15
    mask |= f < 20
    harm = p[mask & (f >= 20)].sum()
    alias = p[~mask].sum()
    return 10 * np.log10(alias / harm)


def sine(f0, amp, secs=1.5):
    t = np.arange(int(SR * secs)) / SR
    return amp * np.sin(2 * np.pi * f0 * t)


def db(v):
    return 20 * np.log10(np.maximum(v, 1e-12))


if __name__ == "__main__":
    print("== 1. small-signal gain into the clipper")
    for knob in (0, 25, 50, 75, 100):
        zg = np.interp(knob, np.arange(0, 101, 10), DRIVE_TBL) * 2.660726
        d = knob / 10.0
        rdrive = 51000 + (d / 10) ** 2 * 500000
        print(f"  knob {knob:3d}: Zoom {zg:6.1f}x ({db(zg):5.1f} dB)   "
              f"ours above 720 Hz {1 + rdrive / 4700:6.1f}x ({db(1 + rdrive / 4700):5.1f} dB)")

    print("\n== 2. clipper ceilings")
    print("  Zoom: +0.925 / -0.487 (asymmetric, ratio 1.90)")
    print("  ours: +/-0.6 above the clean path (symmetric diode pair, Vf 0.6, knee 0.08)")

    print("\n== 3. harmonics, 220 Hz sine at guitar level (0.25 peak)")
    x = sine(220.0, 0.25)
    for knob in (25, 50, 100):
        for name, y in (("Zoom core", zoom_core(x, knob)), ("ours     ", ours(x, knob / 10))):
            h = harmonics(y, 220.0)
            rel = db(h[1:] / h[0])
            thd = 100 * np.sqrt((h[1:] ** 2).sum()) / h[0]
            print(f"  knob {knob:3d} {name}: THD {thd:5.1f}%  H2 {rel[0]:6.1f} dB  "
                  f"H3 {rel[1]:6.1f}  H4 {rel[2]:6.1f}  H5 {rel[3]:6.1f}  (rel. fundamental)")

    print("\n== 4. aliasing, 3.7 kHz sine at 0.5, knob 100 (alias energy vs harmonics)")
    x = sine(3700.0, 0.5)
    naive = zoom_clip(x * DRIVE_TBL[-1])
    print(f"  Zoom clipper, no oversampling : {alias_db(naive, 3700.0):6.1f} dB")
    print(f"  Zoom core, 4x IIR             : {alias_db(zoom_core(x, 100), 3700.0):6.1f} dB")
    print(f"  ours, 2x FIR + ADAA           : {alias_db(ours(x, 10.0, 1.0), 3700.0):6.1f} dB")
