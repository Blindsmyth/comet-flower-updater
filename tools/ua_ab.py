"""A/B two effect versions on the pedal (or on the PC) with the CF Tone test program, and graph it.

    python tools/ua_ab.py capture <name> [--seconds 14]     record the active patch over USB
    python tools/ua_ab.py compare <A> <B> [--out DIR]        graphs + report of two takes
    python tools/ua_ab.py host [--out DIR]                   the same, rendered on the PC from the
                                                             pedal code (CF Watt 4x vs 2x)

On the pedal: patch A = CF Tone (slot 1) -> effect version A (slot 2); patch B the same with
version B; identical knobs. `capture` records 14 s (one 12 s program plus margin) of USB channel 3
(Guitar FX L: after the slots, before the drums and master level, so the master knob does not
matter) and, with the bench firmware, channel 8's timing frames (slot 2's cycles). Takes are
saved as build/ab/<name>.wav (+ .json with the cycles).

The CF Tone program (effects/cftone/cftone.c): 0.5 s silence, 1 s tones 82.4/110/220/440/880/
1760/3520 Hz, 0.5 s silence, 4 s exponential sweep 40 Hz - 16 kHz. `compare` finds the program
by its tone onset followed 7.5 s later by the sweep onset, then per tone (0.65 s window, 4-term
Blackman-Harris): harmonics 2..10 in dB re the fundamental, and the non-harmonic floor (every
bin outside +-4 bins of a harmonic and above 20 Hz: aliasing plus noise) in dB re the
fundamental; for the sweep a spectrogram, where aliasing shows as lines that fold back down.
Output: <out>/ab_report.png, ab_sweep.png, ab_report.md.
"""
import argparse
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
FS = 44100
TONES = [82.40689, 110.0, 220.0, 440.0, 880.0, 1760.0, 3520.0]
SIL, TONE, SWEEP = FS // 2, FS, 4 * FS
FX_CH, BENCH_CH = 2, 7          # USB channels 3 and 8 (0-based)


# ---------------------------------------------------------------- takes
def save_take(path, x, cycles=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    y = np.clip(np.round(x * 32767), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes(y.tobytes())
    if cycles is not None:
        path.with_suffix(".json").write_text(json.dumps(cycles, indent=1))


def load_take(path):
    path = Path(path)
    if path.suffix.lower() == ".f32":
        return np.fromfile(path, "<f4").astype(float), None
    with wave.open(str(path)) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32768.0
    meta = path.with_suffix(".json")
    return x, (json.loads(meta.read_text()) if meta.exists() else None)


def capture(name, seconds):
    import ua_capture8
    import ua_bench
    data = ua_capture8.record(seconds, 8)
    x = data[:, FX_CH].astype(float) / 32768.0
    fr = list(ua_bench.frames(data[:, BENCH_CH].astype(np.uint16)))
    st = ua_bench.stats(fr) if fr else {}
    cyc = {k: st[k]["median"] for k in ("slot1", "slot2", "slot3", "busy") if k in st}
    out = ROOT / "build" / "ab" / (name + ".wav")
    save_take(out, x, cyc or None)
    print("saved", out, "(slot 2: %.0f cycles)" % cyc["slot2"] if "slot2" in cyc else "")


# ---------------------------------------------------------------- analysis
def onsets(x, quiet_s=0.3):
    """Sample indices where the signal starts after >= quiet_s of near silence."""
    peak = np.max(np.abs(x)) or 1.0
    thr = peak * 10 ** (-50 / 20)
    loud = np.abs(x) > thr
    idx = np.flatnonzero(loud)
    if len(idx) == 0:
        return []
    gaps = np.flatnonzero(np.diff(idx) > quiet_s * FS)
    starts = [idx[0]] + [idx[g + 1] for g in gaps]
    return [s for s in starts if s >= quiet_s * FS]


def find_program(x):
    """Start of the tone section: an onset followed 7.5 s later (+-20 ms) by the sweep onset."""
    on = onsets(x)
    for a in on:
        for b in on:
            if abs(b - a - (NT := len(TONES)) * TONE - SIL) < 0.02 * FS:
                return a
    raise SystemExit("CF Tone program not found (need one full 12 s program in the take)")


def bh4(n):
    t = np.arange(n) / n
    return (0.35875 - 0.48829 * np.cos(2 * np.pi * t) + 0.14128 * np.cos(4 * np.pi * t)
            - 0.01168 * np.cos(6 * np.pi * t))


def tone_metrics(seg, f0):
    n = len(seg)
    w = bh4(n)
    spec = np.abs(np.fft.rfft(seg * w)) ** 2
    df = FS / n
    harm = []
    mask = np.zeros(len(spec), bool)
    mask[: int(20 / df)] = True
    for k in range(1, 40):
        f = k * f0
        if f >= FS / 2 - 50:
            break
        c = int(round(f / df))
        lo, hi = max(c - 4, 0), min(c + 5, len(spec))
        mask[lo:hi] = True
        if k <= 10:
            harm.append(spec[lo:hi].sum())
    fund = harm[0] or 1e-30
    rest = spec[~mask].sum()
    return {"harm_db": [10 * np.log10(h / fund + 1e-30) for h in harm[1:]],
            "floor_db": 10 * np.log10(rest / fund + 1e-30),
            "thd_db": 10 * np.log10(sum(harm[1:]) / fund + 1e-30),
            "level_db": 10 * np.log10(4 * fund / (n * (w ** 2).sum()) + 1e-30)}   # peak dBFS


def analyse(x):
    s0 = find_program(x)
    res = []
    for k, f0 in enumerate(TONES):
        a = s0 + k * TONE + int(0.2 * FS)
        res.append(tone_metrics(x[a:a + int(0.65 * FS)], f0))
    sw0 = s0 + len(TONES) * TONE + SIL
    return res, x[sw0:sw0 + SWEEP]


def compare(a_path, b_path, out, labels=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    la, lb = labels or (Path(a_path).stem, Path(b_path).stem)
    xa, ma = load_take(a_path)
    xb, mb = load_take(b_path)
    ra, swa = analyse(xa)
    rb, swb = analyse(xb)

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))
    xs = np.arange(len(TONES))
    names = ["%g" % round(f, 1) for f in TONES]
    ax[0].plot(xs, [r["floor_db"] for r in ra], "o-", label=la)
    ax[0].plot(xs, [r["floor_db"] for r in rb], "s--", label=lb)
    ax[0].set(title="Non-harmonic floor (aliasing + noise)", xlabel="tone Hz", ylabel="dB re fundamental")
    ax[1].plot(xs, [r["thd_db"] for r in ra], "o-", label=la)
    ax[1].plot(xs, [r["thd_db"] for r in rb], "s--", label=lb)
    ax[1].set(title="Total harmonic distortion", xlabel="tone Hz", ylabel="dB re fundamental")
    k3 = TONES.index(440.0)
    hs = np.arange(2, 2 + len(ra[k3]["harm_db"]))
    ax[2].bar(hs - 0.2, ra[k3]["harm_db"], 0.4, label=la)
    ax[2].bar(hs + 0.2, rb[k3]["harm_db"][: len(hs)], 0.4, label=lb)
    ax[2].set(title="Harmonics of the 440 Hz tone", xlabel="harmonic", ylabel="dB re fundamental")
    for a in ax[:2]:
        a.set_xticks(xs, names)
    for a in ax:
        a.grid(alpha=0.3)
        a.legend()
    fig.tight_layout()
    fig.savefig(out / "ab_report.png", dpi=110)

    fig, ax = plt.subplots(1, 2, figsize=(15, 5), sharey=True)
    for a, sw, lab in ((ax[0], swa, la), (ax[1], swb, lb)):
        a.specgram(sw, NFFT=2048, Fs=FS, noverlap=1536, cmap="magma", vmin=-160, vmax=-20)
        a.set(title="Sweep 40 Hz - 16 kHz: %s" % lab, xlabel="s", ylabel="Hz")
    fig.tight_layout()
    fig.savefig(out / "ab_sweep.png", dpi=110)

    md = ["# A/B: %s vs %s" % (la, lb), "",
          "| tone Hz | floor A | floor B | THD A | THD B | level A | level B |", "|---" * 7 + "|"]
    for f, a, b in zip(TONES, ra, rb):
        md.append("| %g | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f |" % (
            round(f, 1), a["floor_db"], b["floor_db"], a["thd_db"], b["thd_db"], a["level_db"], b["level_db"]))
    if ma or mb:
        md += ["", "Slot 2 cycles per block: %s %s, %s %s" % (
            la, "%.0f" % ma["slot2"] if ma and "slot2" in ma else "-",
            lb, "%.0f" % mb["slot2"] if mb and "slot2" in mb else "-")]
    md += ["", "dB re the fundamental; floor = everything that is not a harmonic (aliasing + noise).",
           "Graphs: ab_report.png, ab_sweep.png"]
    (out / "ab_report.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print("wrote", out)


def host(out, knobs):
    exe = ROOT / "build" / "host"
    tmp = ROOT / "build" / "ab"
    tmp.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(exe / "cftone_render.exe"), "13", str(tmp / "host_tone.f32")], check=True)
    for os_ in (4, 2):
        subprocess.run([str(exe / ("hiwatt_render_os%d.exe" % os_)), str(tmp / "host_tone.f32"),
                        str(tmp / ("host_watt_%dx.f32" % os_))] + knobs.split(","), check=True)
    compare(tmp / "host_watt_4x.f32", tmp / "host_watt_2x.f32", out, ("CF Watt 4x (PC)", "CF Watt 2x (PC)"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("capture")
    c.add_argument("name")
    c.add_argument("--seconds", type=float, default=14)
    m = sub.add_parser("compare")
    m.add_argument("a")
    m.add_argument("b")
    m.add_argument("--out", default=str(ROOT / "build" / "ab" / "report"))
    h = sub.add_parser("host")
    h.add_argument("--out", default=str(ROOT / "build" / "ab" / "host_report"))
    h.add_argument("--knobs", default="50,50,50,50,50,50",
                   help="CF Watt Volume,Treble,Middle,Bass,Presence,Master (0..100)")
    a = ap.parse_args()
    if a.cmd == "capture":
        capture(a.name, a.seconds)
    elif a.cmd == "compare":
        compare(a.a, a.b, a.out)
    else:
        host(a.out, a.knobs)


if __name__ == "__main__":
    main()
