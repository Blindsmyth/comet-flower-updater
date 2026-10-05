"""Design the polyphase IIR half-band filters of effects/common/os_hbiir.h.

Two allpass paths of first-order sections in z^-2 (the structure of Laurent
de Soras' hiir and JUCE's polyphase-IIR oversampler); coefficients from the
elliptic design (hiir PolyphaseIir2Designer). Passband to 20 kHz:
  stage 1 (44.1 <-> 88.2 kHz):  10 coefficients, images/aliases >= 24.1 kHz down 106 dB
  stage 2 (88.2 <-> 176.4 kHz):  5 coefficients, >= 68.2 kHz down ~100 dB
Prints the C constants.  python tools/gen_halfband_iir.py
"""
import numpy as np


def transition_param(tbw):
    k = np.tan((1 - tbw * 2) * np.pi / 4) ** 2
    kk = (1 - k * k) ** 0.25
    e = 0.5 * (1 - kk) / (1 + kk)
    e4 = e ** 4
    return k, e * (1 + e4 * (2 + e4 * (15 + 150 * e4)))


def _series(q, order, c, num):
    r, i, j = 0.0, (0 if num else 1), (1 if num else -1)
    while True:
        t = (q ** (i * (i + 1)) * np.sin((i * 2 + 1) * c * np.pi / order) if num
             else q ** (i * i) * np.cos(i * 2 * c * np.pi / order)) * j
        r += t
        j, i = -j, i + 1
        if abs(t) <= 1e-100:
            return r


def coefs(n, tbw):
    k, q = transition_param(tbw)
    order, out = n * 2 + 1, []
    for c in range(1, n + 1):
        ww = _series(q, order, c, True) * q ** 0.25 / (_series(q, order, c, False) + 0.5)
        w2 = ww * ww
        x = np.sqrt((1 - w2 * k) * (1 - w2 / k)) / (1 + w2)
        out.append((1 - x) / (1 + x))
    return out


for name, fs_lo, n in (("HBI1", 44100, 10), ("HBI2", 88200, 5)):
    c = coefs(n, (fs_lo / 2 - 20000) / (2 * fs_lo))
    print(f"#define {name}_N {n}")
    print(f"static const float {name.lower()}_c[{n}] = {{ " + ", ".join(f"{v:.9g}f" for v in c) + " };")
