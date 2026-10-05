"""Score the G1 Hiwatt (G_*) against the 16x desktop-circuit reference (ref_*)
written by hiwatt_accuracy.cpp: harmonic amplitudes H1..H9 (within 60 dB of
H1) and the in-band non-harmonic (alias) energy, as ts808_accuracy.py does.

    python tests/host/hiwatt_accuracy.py [folder under build/host, default hw]
"""
import glob
import sys
from pathlib import Path

import numpy as np

D = Path(__file__).resolve().parents[2] / "build" / "host" / (sys.argv[1] if len(sys.argv) > 1 else "hw")
SR = 44100
MODELS = {"G": 1, "Gm1c": 1, "Gm18": 1, "GP": 1, "R4A": 4}   # prefix -> rate multiple


def decimate_ref(x, os=16):
    """Band-limit to 20 kHz and decimate the last exact second only: that
    segment is periodic for integer-Hz tones, so the brickwall cannot ring."""
    x = x[-SR * os:]
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / (SR * os))
    X[f > 20000] = 0
    return np.fft.irfft(X, len(x))[::os]


def analyse(y, f0):
    """Leakage-free: the last exact second (integer-Hz tones land on bins),
    rectangular window. Harmonics k*f0 below 20 kHz; everything else in
    20 Hz..20 kHz is non-harmonic (aliases, intermodulation, noise)."""
    y = y[-SR:]
    s = np.abs(np.fft.rfft(y)) ** 2
    k0 = int(round(f0))
    harm = np.array([s[k * k0] for k in range(1, 10) if k * k0 < 20000])
    mask = np.zeros(len(s), bool)
    mask[:20] = True
    mask[20000:] = True
    mask[np.arange(k0, 20000, k0)] = True
    alias = s[~mask].sum() / max(s[np.arange(k0, 20000, k0)].sum(), 1e-30)
    return harm, 10 * np.log10(alias + 1e-30)


rows = []
models = [m for m in MODELS if glob.glob(str(D / f"{m}_*.f32"))]
for rf in sorted(glob.glob(str(D / "ref_*.f32"))):
    tag = Path(rf).stem[4:]
    f0 = float(tag.split("_")[1][1:])
    ref = decimate_ref(np.fromfile(rf, dtype=np.float32).astype(np.float64))
    hr, ar = analyse(ref, f0)
    sig = hr > hr[0] * 1e-6
    row = {"tag": tag, "ref": ar}
    for m in models:
        y = np.fromfile(D / f"{m}_{tag}.f32", dtype=np.float32).astype(np.float64)
        if MODELS[m] > 1:
            y = decimate_ref(y, MODELS[m])
        hm, am = analyse(y, f0)
        n = min(len(hm), len(hr))
        d = 10 * np.log10(hm[:n][sig[:n]] / hr[:n][sig[:n]])
        row[m] = (np.abs(d).max(), d[0], am)
    rows.append(row)

print(f"{'test':20s} {'ref alias':>9s} | " + " | ".join(f"{m + ' maxH  H1  alias':>22s}" for m in models))
for r in rows:
    print(f"{r['tag']:20s} {r['ref']:9.1f} | " + " | ".join(
        f"{r[m][0]:7.2f} {r[m][1]:5.2f} {r[m][2]:7.1f}" for m in models))
print()
print("worst: max harmonic error dB / worst alias dB")
for m in models:
    print(f"  {m:3s}: {max(r[m][0] for r in rows):6.2f} dB   alias {max(r[m][2] for r in rows):6.1f} dB")
