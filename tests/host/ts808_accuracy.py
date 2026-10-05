"""Score TS808 models against the 32x circuit reference (ts808_accuracy.cpp).

Per test (sine f0, amplitude, drive knob): harmonic amplitudes H1..H9 of each
model vs the band-limited reference, and the model's alias energy (in-band
non-harmonic energy re harmonic energy). Models: A = current Green 808 core,
C8 = full implicit solve at 8x (bench version), X = the pedal build
(effects/common/ts808_exact.h).
"""
import glob
from pathlib import Path

import numpy as np

import sys
D = Path(__file__).resolve().parents[2] / "build" / "host" / (sys.argv[1] if len(sys.argv) > 1 else "acc")
SR = 44100


def decimate_ref(x, os=32):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / (SR * os))
    X[f > 20000] = 0
    return np.fft.irfft(X, len(x))[::os]


def analyse(y, f0):
    y = y[SR // 4:]
    w = np.blackman(len(y))
    s = np.abs(np.fft.rfft(y * w)) ** 2
    f = np.fft.rfftfreq(len(y), 1 / SR)
    harm, mask = [], (f < 20)
    for k in range(1, 10):
        if k * f0 >= 20000:
            break
        m = np.abs(f - k * f0) < 12
        harm.append(s[m].sum())
        mask |= m
    for k in range(10, int(20000 // f0) + 1):
        mask |= np.abs(f - k * f0) < 12
    band = f < 20000
    alias = s[band & ~mask].sum() / max(sum(harm), 1e-30)
    return np.array(harm), 10 * np.log10(alias + 1e-30)


models = ["A", "C8", "X"]
rows = []
for rf in sorted(glob.glob(str(D / "ref_*.f32"))):
    tag = Path(rf).stem[4:]
    f0 = float(tag.split("_")[0][1:])
    ref = decimate_ref(np.fromfile(rf, dtype=np.float32).astype(np.float64))
    hr, _ = analyse(ref, f0)
    sig = hr > hr[0] * 1e-6                     # harmonics within 60 dB of H1
    row = {"tag": tag}
    for m in models:
        y = np.fromfile(D / f"{m}_{tag}.f32", dtype=np.float32).astype(np.float64)
        hm, al = analyse(y, f0)
        n = min(len(hm), len(hr))
        d = 10 * np.log10(hm[:n][sig[:n]] / hr[:n][sig[:n]])
        row[m] = (np.abs(d).max(), d[0], al)
    rows.append(row)

print(f"{'test':18s} | " + " | ".join(f"{m:>22s}" for m in models))
print(f"{'':18s} | " + " | ".join(f"{'maxHdB  H1dB  alias':>22s}" for _ in models))
for r in rows:
    print(f"{r['tag']:18s} | " + " | ".join(
        f"{r[m][0]:6.2f} {r[m][1]:6.2f} {r[m][2]:7.1f}" for m in models))
print("\nworst over all tests: max harmonic error dB / worst alias dB")
for m in models:
    print(f"  {m:3s}: {max(r[m][0] for r in rows):6.2f} dB   alias {max(r[m][2] for r in rows):6.1f} dB")
