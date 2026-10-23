"""Score CF WattL (L_*, effects/common/hiwatt_lite.h) against the shipped CF Watt
at 2x (G_*, the owner-approved sound) and the 16x desktop-circuit reference
(ref_*), all in build/host/hwl. Ends with `ACCURACY: PASS` or `ACCURACY: FAIL`.

    tests\\host\\build_hiwatt_accuracy.bat hwl /DHW_OS#2   (once: ref_* and G_*)
    tests\\host\\build_hiwatt_lite.bat                     (after every edit: L_*)
    .venv/Scripts/python.exe tests/host/hiwatt_lite_score.py

Per test (4 knob sets x 110/440/1760 Hz x 3 levels), all must hold:
  1. H1 (output level) within 0.5 dB of the shipped core;
  2. harmonics vs the shipped core: within 1.5 dB where the shipped harmonic
     is within 30 dB of its H1, within 4 dB where it is 30..50 dB down
     (the character of the distortion);
  3. worst harmonic error vs the reference no more than 2 dB above the
     shipped core's;
  4. non-harmonic (alias) energy no more than 6 dB above the shipped core's,
     or below -60 dB.
STRETCH (lower is better, only after PASS): the worst rule-2 deviation.
"""
from pathlib import Path

import numpy as np

D = Path(__file__).resolve().parents[2] / "build" / "host" / "hwl"
SR = 44100


def decimate_ref(x, os=16):
    x = x[-SR * os:]
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / (SR * os))
    X[f > 20000] = 0
    return np.fft.irfft(X, len(x))[::os]


def analyse(y, f0):
    """Last exact second, rectangular window: harmonic powers H1..H9 below
    20 kHz, and the non-harmonic energy in dB relative to the harmonics."""
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


def db(a, b):
    return 10 * np.log10((a + 1e-30) / (b + 1e-30))


def load(p):
    return np.fromfile(p, dtype=np.float32).astype(np.float64)


refs = sorted(D.glob("ref_*.f32"))
if not refs:
    raise SystemExit(f"no references in {D}: run tests\\host\\build_hiwatt_accuracy.bat hwl /DHW_OS#2")
fails, stretch, nan = [], 0.0, False
print(f"{'test':20s} {'dH1':>6s} {'chr':>6s} {'L-ref':>6s} {'G-ref':>6s} {'L al':>7s} {'G al':>7s}")
for rf in refs:
    tag = rf.stem[4:]
    f0 = float(tag.split("_")[1][1:])
    lf = D / f"L_{tag}.f32"
    if not lf.exists():
        raise SystemExit(f"missing {lf.name}: run tests\\host\\build_hiwatt_lite.bat")
    yl, yg = load(lf), load(D / f"G_{tag}.f32")
    if not np.all(np.isfinite(yl)):
        nan = True
        fails.append(f"{tag}: NaN/Inf in the output")
        continue
    hr, _ = analyse(decimate_ref(load(rf)), f0)
    hl, al = analyse(yl, f0)
    hg, ag = analyse(yg, f0)
    n = min(len(hr), len(hl), len(hg))
    hr, hl, hg = hr[:n], hl[:n], hg[:n]
    sig = hr > hr[0] * 1e-6
    err_l = np.abs(db(hl[sig], hr[sig])).max()
    err_g = np.abs(db(hg[sig], hr[sig])).max()
    dh1 = db(hl[0], hg[0])
    rel = db(hg, hg[0])                     # shipped harmonic level below its H1, dB
    dev = np.abs(db(hl, hg))
    near, far = rel > -30, (rel <= -30) & (rel > -50)
    chr_ = max(dev[near].max(initial=0), 0)
    bad = []
    if abs(dh1) > 0.5:
        bad.append(f"H1 {dh1:+.2f} dB")
    if (dev[near] > 1.5).any():
        bad.append(f"strong harmonics off by {dev[near].max():.2f} dB")
    if (dev[far] > 4).any():
        bad.append(f"weak harmonics off by {dev[far].max():.2f} dB")
    if err_l > err_g + 2:
        bad.append(f"vs reference {err_l:.2f} dB (shipped {err_g:.2f})")
    if al > max(ag + 6, -60):
        bad.append(f"alias {al:.1f} dB (shipped {ag:.1f})")
    stretch = max(stretch, chr_, dev[far].max(initial=0) / 4 * 1.5)
    print(f"{tag:20s} {dh1:6.2f} {chr_:6.2f} {err_l:6.2f} {err_g:6.2f} {al:7.1f} {ag:7.1f}"
          + ("  FAIL: " + "; ".join(bad) if bad else ""))
    if bad:
        fails.append(f"{tag}: " + "; ".join(bad))
print()
print(f"failing tests: {len(fails)} of {len(refs)}")
for f in fails[:10]:
    print("  " + f)
print(f"STRETCH (worst character deviation, dB): {stretch:.2f}")
print("ACCURACY: " + ("PASS" if not fails and not nan else "FAIL"))
