"""Offline glitch-detector tests for tools/ua_capture.py (pytest, numpy only).

Tests synthetic signals (60 Hz hum + harmonics + small noise, guitar-like decaying
pluck chain, silence with +-1 LSB noise) with clean streams, leading priming zeros,
all four USB stream defect types (lost frames, repeated frames, inserted zero runs,
sample jumps), and the real 10 s idle take build/ua_takes/take_20261016_172545.wav.
"""
from pathlib import Path
import sys

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ua_capture  # noqa: E402

FS = ua_capture.FS


def make_hum(n=FS * 4, seed=1):
    """60 Hz mains hum + odd/even harmonics + small Gaussian noise (~ -34 dBFS)."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / FS
    sig = (
        650 * np.sin(2 * np.pi * 60 * t + 0.1)
        + 450 * np.sin(2 * np.pi * 180 * t + 0.7)
        + 140 * np.sin(2 * np.pi * 300 * t + 1.3)
        + 90 * np.sin(2 * np.pi * 540 * t + 2.1)
        + 70 * np.sin(2 * np.pi * 900 * t + 0.4)
        + 55 * np.sin(2 * np.pi * 1500 * t + 1.8)
        + 45 * np.sin(2 * np.pi * 2700 * t + 0.9)
        + rng.normal(0, 0.5, n)
    )
    s = np.round(sig).astype(np.int16)
    return np.column_stack([s, s])


def make_pluck_chain(n=FS * 4, seed=2):
    """Guitar-like decaying pluck chain with smooth pick attack and harmonic decay."""
    rng = np.random.default_rng(seed)
    t = np.arange(n) / FS
    sig = np.zeros(n, dtype=np.float64)
    notes = [(0.05, 110.0), (1.0, 146.83), (1.95, 196.0), (2.9, 246.94)]
    for t0, f0 in notes:
        idx = np.where(t >= t0)[0]
        dt = t[idx] - t0
        attack_t = 0.003
        env_attack = np.where(dt < attack_t, np.sin(0.5 * np.pi * dt / attack_t) ** 2, 1.0)
        note = np.zeros(len(dt))
        for h in range(1, 13):
            decay = np.exp(-dt * (1.2 + 0.35 * h))
            amp = 5000.0 / (h ** 1.1)
            note += amp * decay * np.sin(2 * np.pi * f0 * h * dt + 0.3 * h)
        sig[idx] += env_attack * note
    sig += rng.normal(0, 0.6, n)
    s = np.round(sig).astype(np.int16)
    return np.column_stack([s, s])


def make_silence_lsb(n=FS * 4, seed=3):
    """Silence with +-1 LSB dither noise."""
    rng = np.random.default_rng(seed)
    return rng.integers(-1, 2, size=(n, 2), dtype=np.int16)


def _pick_active_point(sig, pos):
    """Nudge pos by at most a few samples so 1-frame defects are not placed at a 0-slope peak."""
    local_d_std = float(np.std(np.diff(sig[pos - 400:pos + 400, 0].astype(np.float64))))
    p = pos
    while abs(int(sig[p, 0]) - int(sig[p - 1, 0])) < max(0.8 * local_d_std, 14.0) or abs(int(sig[p, 0])) < 30:
        p += 1
    return p


def test_clean_synthetic_signals_have_zero_false_events():
    for sig in (make_hum(), make_pluck_chain(), make_silence_lsb()):
        priming, events = ua_capture.detect_glitches(sig)
        assert priming == 0
        assert events == []


def test_leading_zero_priming_is_reported_separately_not_as_defect():
    hum = make_hum()
    padded = np.vstack([np.zeros((89, 2), dtype=np.int16), hum])
    priming, events = ua_capture.detect_glitches(padded)
    assert priming == 89
    assert events == []


def test_real_wav_takes_have_zero_false_events():
    wav_path = ROOT / "build" / "ua_takes" / "take_20261016_172545.wav"
    if not wav_path.exists():
        pytest.skip(f"{wav_path} not present")
    data = ua_capture.load_wav(wav_path)
    priming, events = ua_capture.detect_glitches(data)
    assert priming == 89
    assert events == []
    lines = ua_capture.analyse_audio(data)
    assert any("leading zero (priming) frames: 89" in ln for ln in lines)
    assert lines[-1] == "0 defects in 0.17 min"


@pytest.mark.parametrize("sig_fn", [make_hum, make_pluck_chain], ids=["hum", "pluck"])
@pytest.mark.parametrize("gap_len", [1, 8, 45])
@pytest.mark.parametrize("base_pos", [24000, 65536, 118000])
def test_lost_frames_detected_within_two_frames(sig_fn, gap_len, base_pos):
    sig = sig_fn()
    p = _pick_active_point(sig, base_pos)
    corrupted = np.concatenate([sig[:p], sig[p + gap_len:]])
    _, events = ua_capture.detect_glitches(corrupted)
    assert len(events) == 1
    frame, kind, _ = events[0]
    assert abs(frame - p) <= 2
    assert kind == "lost"


@pytest.mark.parametrize("sig_fn", [make_hum, make_pluck_chain], ids=["hum", "pluck"])
@pytest.mark.parametrize("rep_len", [1, 6, 44])
@pytest.mark.parametrize("base_pos", [28000, 72000, 125000])
def test_repeated_frames_detected_within_two_frames(sig_fn, rep_len, base_pos):
    sig = sig_fn()
    p = _pick_active_point(sig, base_pos)
    corrupted = np.concatenate([sig[:p], sig[p - rep_len:p], sig[p:]])
    _, events = ua_capture.detect_glitches(corrupted)
    assert len(events) == 1
    frame, kind, size = events[0]
    assert abs(frame - p) <= 2
    assert kind == "repeat"
    assert size >= rep_len


@pytest.mark.parametrize("sig_fn", [make_hum, make_pluck_chain], ids=["hum", "pluck"])
@pytest.mark.parametrize("zero_len", [1, 12, 45])
@pytest.mark.parametrize("base_pos", [32000, 80000, 132000])
def test_inserted_zero_frames_detected_within_two_frames(sig_fn, zero_len, base_pos):
    sig = sig_fn()
    p = _pick_active_point(sig, base_pos)
    zeros = np.zeros((zero_len, 2), dtype=np.int16)
    corrupted = np.concatenate([sig[:p], zeros, sig[p:]])
    _, events = ua_capture.detect_glitches(corrupted)
    assert len(events) == 1
    frame, kind, size = events[0]
    assert abs(frame - p) <= 2
    assert kind == "zero"
    assert size == zero_len


@pytest.mark.parametrize("sig_fn,delta", [(make_hum, 65), (make_pluck_chain, 110), (make_silence_lsb, 18)],
                         ids=["hum", "pluck", "silence"])
@pytest.mark.parametrize("base_pos", [36000, 90000, 140000])
def test_sample_jump_detected_within_two_frames(sig_fn, delta, base_pos):
    sig = sig_fn()
    p = _pick_active_point(sig, base_pos) if sig_fn is not make_silence_lsb else base_pos
    corrupted = sig.copy()
    corrupted[p] = np.clip(corrupted[p].astype(np.int32) + delta, -32768, 32767).astype(np.int16)
    _, events = ua_capture.detect_glitches(corrupted)
    assert len(events) == 1
    frame, kind, _ = events[0]
    assert abs(frame - p) <= 2
    assert kind == "jump"


def test_silence_zero_run_and_repeat_detected_within_two_frames():
    sil = make_silence_lsb()
    p_zero = 45000
    while sil[p_zero - 1, 0] == 0 and sil[p_zero - 1, 1] == 0:
        p_zero += 1
    with_zeros = np.concatenate([sil[:p_zero], np.zeros((24, 2), dtype=np.int16), sil[p_zero:]])
    _, ev_z = ua_capture.detect_glitches(with_zeros)
    assert len(ev_z) == 1
    assert abs(ev_z[0][0] - p_zero) <= 2
    assert ev_z[0][1] == "zero"

    p_rep = 85000
    with_rep = np.concatenate([sil[:p_rep], sil[p_rep - 24:p_rep], sil[p_rep:]])
    _, ev_r = ua_capture.detect_glitches(with_rep)
    assert len(ev_r) == 1
    assert abs(ev_r[0][0] - p_rep) <= 2
    assert ev_r[0][1] == "repeat"


def test_multi_defect_take_and_analyse_audio_formatting():
    hum = make_hum()
    # Build a take with 60 priming frames and one of each defect at known final coordinates
    prim = np.zeros((60, 2), dtype=np.int16)
    p1 = _pick_active_point(hum, 25000)
    p2 = _pick_active_point(hum, 65000)
    p3 = _pick_active_point(hum, 105000)
    p4 = _pick_active_point(hum, 145000)

    # Construct from back to front so earlier indices are simple to track
    seg = hum.copy()
    # 1. Sample jump at p4
    seg[p4] = seg[p4] + 80
    # 2. Insert 10 zeros at p3 (shifts p4 by +10)
    seg = np.concatenate([seg[:p3], np.zeros((10, 2), dtype=np.int16), seg[p3:]])
    p4 += 10
    # 3. Repeat 8 frames at p2 (shifts p3, p4 by +8)
    seg = np.concatenate([seg[:p2], seg[p2 - 8:p2], seg[p2:]])
    p3 += 8
    p4 += 8
    # 4. Drop 12 frames at p1 (shifts p2, p3, p4 by -12)
    seg = np.concatenate([seg[:p1], seg[p1 + 12:]])
    p2 -= 12
    p3 -= 12
    p4 -= 12
    # 5. Prepend 60 priming frames (shifts all by +60)
    take = np.vstack([prim, seg])
    expected = [(p1 + 60, "lost"), (p2 + 60, "repeat"), (p3 + 60, "zero"), (p4 + 60, "jump")]

    priming, events = ua_capture.detect_glitches(take)
    assert priming == 60
    assert len(events) == 4
    for (got_f, got_k, _), (exp_f, exp_k) in zip(events, expected):
        assert abs(got_f - exp_f) <= 2
        assert got_k == exp_k

    lines = ua_capture.analyse_audio(take)
    assert lines[0].startswith("audio take:")
    assert lines[1].startswith("L: rms ")
    assert lines[2].startswith("R: rms ")
    assert lines[3] == "leading zero (priming) frames: 60"
    assert any(ln.startswith("lost frames: 1, positions") for ln in lines)
    assert any(ln.startswith("repeated frames: 1, positions") for ln in lines)
    assert any(ln.startswith("inserted zero runs: 1, positions") for ln in lines)
    assert any(ln.startswith("sample jumps: 1, positions") for ln in lines)
    assert lines[-1].startswith("4 defects in ")
    assert lines[-1].endswith(" min")
