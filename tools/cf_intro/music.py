"""Comet Flower intro tune: a chiptune in the keygen / cracktro tradition.

Original composition. Harmony: the Bm - A - G - Em changes that the solos of
"Comfortably Numb" run over (a chord progression, not a melody). Form: like
"Shine On You Crazy Diamond (Pts. I-V)" opening -- a long pad swell out of
silence, slow sustained chords, a sparse bluesy lead entering late, then a
build. No melody or riff from either piece is used; the lead is new, built on
B minor pentatonic phrases.

    python -m tools.cf_intro.music [out.wav]

Voices are chip-style: detuned pulse pads, 12.5 % square arpeggio, 25 % pulse
lead with slides and vibrato, triangle bass, noise hats, sine-drop kick, and a
tape-ish feedback echo. Pure numpy, ~2 minutes, mono 16-bit 22.05 kHz. The end
fades to silence and the start rises from it, so it loops cleanly.
"""
import sys
import wave
from pathlib import Path

import numpy as np

SR = 22050
BPM = 63.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT

NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7,
        "G#": 8, "A": 9, "A#": 10, "B": 11}


def hz(name, octave):
    return 440.0 * 2 ** ((NOTE[name] + 12 * (octave + 1) - 69) / 12)


CHORDS = {  # root, third, fifth (names), bass root
    "Bm": ("B", "D", "F#"),
    "A": ("A", "C#", "E"),
    "G": ("G", "B", "D"),
    "Em": ("E", "G", "B"),
}
PROG = ["Bm", "A", "G", "Em"]


def env(n, a, r, sustain=1.0):
    """Linear attack, hold, linear release (seconds), n samples."""
    e = np.full(n, sustain, dtype=np.float64)
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    if na:
        e[:na] = np.linspace(0, sustain, na)
    if nr:
        e[n - nr:] *= np.linspace(1, 0, nr)
    return e


def pulse(freq, n, duty=0.5, phase=0.0):
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    ph = (phase + np.cumsum(f) / SR) % 1.0
    return np.where(ph < duty, 1.0, -1.0)


def tri(freq, n):
    f = np.broadcast_to(np.asarray(freq, dtype=np.float64), (n,))
    ph = (np.cumsum(f) / SR) % 1.0
    return 4 * np.abs(ph - 0.5) - 1


def lowpass(x, cutoff):
    """One-pole lowpass; cutoff may be an array (Hz) for slow swells."""
    c = np.broadcast_to(np.asarray(cutoff, dtype=np.float64), x.shape)
    a = 1 - np.exp(-2 * np.pi * c / SR)
    y = np.empty_like(x)
    s = 0.0
    for i in range(len(x)):              # ~2.5 M samples; fine once, cached as WAV
        s += a[i] * (x[i] - s)
        y[i] = s
    return y


def add(buf, start_s, sig):
    i = int(start_s * SR)
    j = min(len(buf), i + len(sig))
    if j > i:
        buf[i:j] += sig[:j - i]


def pad_chord(name, dur, octave=3, gain=0.08, attack=1.2, release=1.4):
    n = int(dur * SR)
    out = np.zeros(n)
    for k, note in enumerate(CHORDS[name]):
        o = octave + (1 if k and NOTE[note] < NOTE[CHORDS[name][0]] else 0)
        f = hz(note, o)
        for det in (-0.004, 0.004):
            out += pulse(f * (1 + det), n, duty=0.5 - 0.1 * k, phase=0.13 * k)
    return out * env(n, attack, release) * gain


def arp(name, dur, step, octave=5, gain=0.05):
    tones = [hz(x, octave) for x in CHORDS[name]]
    seq = tones + [tones[0] * 2] + tones[::-1][1:]
    n_step = int(step * SR)
    out = np.zeros(int(dur * SR))
    for i in range(0, len(out) - n_step + 1, n_step):
        f = seq[(i // n_step) % len(seq)]
        out[i:i + n_step] = pulse(f, n_step, duty=0.125) * env(n_step, 0.002, step * 0.6, 1.0)
    return out * gain


def bass(name, dur, gain=0.16):
    root = CHORDS[name][0]
    f = hz(root, 2)
    n = int(dur * SR)
    half = n // 2
    out = np.zeros(n)
    out[:half] = tri(f, half) * env(half, 0.01, 0.2)
    out[half:] = tri(f, n - half) * env(n - half, 0.01, 0.4)
    return out * gain


def lead_note(note, octave, dur, slide_from=None, vib=0.0, gain=0.07):
    """Pulse lead; optional slide up into the note (a guitar-style bend)."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = np.full(n, hz(note, octave))
    if slide_from is not None:
        ns = min(n, int(0.12 * SR))
        f[:ns] = np.linspace(hz(*slide_from), f[0], ns)
    if vib:
        depth = vib * np.clip((t - 0.25) / 0.6, 0, 1)        # vibrato blooms late
        f = f * (1 + depth * np.sin(2 * np.pi * 5.2 * t))
    return pulse(f, n, duty=0.25) * env(n, 0.01, min(0.5, dur * 0.4)) * gain


def echo(x, delay_s=0.357, fb=0.38, mix=0.35):
    d = int(delay_s * SR)
    y = x.copy()
    for i in range(d, len(y), d):                             # block-wise feedback
        y[i:i + d] += fb * y[i - d:i - d + min(d, len(y) - i)]
    return x * (1 - mix) + y * mix


def noise_hat(n, gain=0.03):
    rng = np.random.default_rng(1911)
    return rng.uniform(-1, 1, n) * env(n, 0.001, n / SR * 0.9) * gain


def kick(gain=0.25):
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    f = 110 * np.exp(-t * 18) + 42
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 14) * gain


# Original B minor pentatonic phrases: (note, octave, beats, slide_from).
LEAD_A = [("F#", 4, 2.0, ("E", 4)), ("D", 4, 1.0, None), ("B", 3, 5.0, None),
          ("A", 3, 1.0, None), ("B", 3, 1.0, ("A", 3)), ("D", 4, 6.0, ("C#", 4)),
          ("E", 4, 2.0, None), ("F#", 4, 1.5, ("E", 4)), ("E", 4, 0.5, None),
          ("D", 4, 4.0, None), ("B", 3, 8.0, ("A", 3))]
LEAD_B = [("B", 4, 1.5, ("A", 4)), ("A", 4, 0.5, None), ("F#", 4, 2.0, None),
          ("A", 4, 1.0, ("G", 4)), ("B", 4, 3.0, ("A", 4)), ("D", 5, 2.0, ("C#", 5)),
          ("B", 4, 2.0, None), ("A", 4, 1.0, None), ("F#", 4, 1.0, None),
          ("E", 4, 2.0, ("D", 4)), ("F#", 4, 6.0, ("E", 4)), ("D", 5, 1.0, None),
          ("B", 4, 1.0, None), ("A", 4, 2.0, None), ("B", 4, 4.0, ("A", 4))]


def place_lead(buf, start, phrase, vib):
    t = start
    for note, octv, beats, slide in phrase:
        add(buf, t, lead_note(note, octv, beats * BEAT * 0.97, slide, vib))
        t += beats * BEAT
    return t


def render():
    bars_intro, bars_a, bars_b, bars_c, bars_out = 4, 8, 8, 8, 2
    total = (bars_intro + bars_a + bars_b + bars_c + bars_out) * BAR + 2.0
    pads = np.zeros(int(total * SR))
    keys = np.zeros_like(pads)
    lead = np.zeros_like(pads)
    low = np.zeros_like(pads)
    drums = np.zeros_like(pads)

    # Intro: one long Bm swell out of silence (the Shine On opening gesture).
    t = 0.0
    swell = bars_intro * BAR
    add(pads, t, pad_chord("Bm", swell + 1.0, attack=swell * 0.8, release=1.5, gain=0.09))
    t += swell
    # A: the changes, one bar each, pads plus a soft eighth-note arpeggio.
    for i in range(bars_a):
        c = PROG[i % 4]
        add(pads, t, pad_chord(c, BAR + 0.6))
        add(keys, t, arp(c, BAR, BEAT / 2, gain=0.03 + 0.003 * i))
        t += BAR
    # B: the lead enters, sparse and late; bass joins halfway.
    lead_start = t + BEAT * 2
    for i in range(bars_b):
        c = PROG[i % 4]
        add(pads, t, pad_chord(c, BAR + 0.6))
        add(keys, t, arp(c, BAR, BEAT / 2, gain=0.05))
        if i >= 4:
            add(low, t, bass(c, BAR))
        t += BAR
    place_lead(lead, lead_start, LEAD_A, vib=0.012)
    # C: the build -- sixteenth arpeggio, kick and hats, higher lead.
    c_start = t
    for i in range(bars_c):
        c = PROG[i % 4]
        add(pads, t, pad_chord(c, BAR + 0.6, gain=0.09))
        add(keys, t, arp(c, BAR, BEAT / 4, octave=5 + (i >= 4), gain=0.045))
        add(low, t, bass(c, BAR, gain=0.18))
        for b in range(4):
            if b in (0, 2):
                add(drums, t + b * BEAT, kick())
            for h in range(2):
                add(drums, t + (b + 0.5 * h) * BEAT + 0.5 * BEAT * (h == 0),
                    noise_hat(int(0.06 * SR)))
        t += BAR
    place_lead(lead, c_start + BEAT, LEAD_B, vib=0.016)
    # Outro: home to Bm and back into silence.
    add(pads, t, pad_chord("Bm", bars_out * BAR + 1.5, attack=0.8, release=bars_out * BAR, gain=0.09))
    t += bars_out * BAR

    sweep = np.linspace(600, 3200, len(pads))
    sweep[:int(swell * SR)] = np.linspace(250, 600, int(swell * SR))
    mix = lowpass(pads, sweep) + echo(keys) + echo(lead, 0.476, 0.42, 0.4) + low + drums
    mix = np.tanh(mix * 1.6) / np.tanh(1.6)
    mix *= 0.85 / max(1e-9, np.max(np.abs(mix)))
    fade = int(2.0 * SR)
    mix[-fade:] *= np.linspace(1, 0, fade)
    return mix


def write_wav(path, x):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return path


def ensure(path):
    path = Path(path)
    if not path.exists():
        write_wav(path, render())
    return path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "build/cf_intro/cf_tune.wav"
    p = write_wav(out, render())
    print("wrote %s (%.0f s)" % (p, wave.open(str(p)).getnframes() / SR))
