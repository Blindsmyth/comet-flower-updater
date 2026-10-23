"""A small local drum machine that plays the pedal's own drum samples.

Uses:
  build/drums/patterns.json   -- written by decode_patterns.py: pattern
                                   names, time signature, and which .raw
                                   sample is assigned to which of the 9
                                   voice slots for each of the firmware's
                                   69 built-in patterns (all confirmed by
                                   static firmware decode).
  build/drums/wav/*.wav       -- written by raw2wav.py from the pedal's
                                   backup/2026-10-04/files/*.raw dump.

IMPORTANT HONESTY NOTE: the firmware's per-pattern *hit grid* (which 16th
step each voice fires on, at what velocity) is NOT decoded -- see
docs/DRUM_MACHINE_2026-10-22.md. Each built-in pattern record points at a
small binary blob (terminated by 0xf0) that is almost certainly the real
step/velocity data, but its byte encoding wasn't cracked in the time
available. So `render` on a built-in pattern plays a GENERIC, algorithmic
groove (kick/snare/hat positions derived from the pattern's own time
signature and a style guessed from its name) using that pattern's real,
firmware-assigned samples -- it is a reasonable-sounding stand-in, not a
transcription of the real pedal groove. `new` lets you write your own exact
step grid in JSON and is not an approximation.

Commands:
  list                               list all decoded patterns
  render <name-or-index> [options]   render a built-in pattern (approximate
                                      groove, real samples/tempo/meter)
  new <pattern.json> [options]       render a user-authored exact pattern

Options (render/new):
  --bpm N          tempo (render default: pattern has no stored tempo, so
                    you must pass one; new: JSON's "bpm" field, overridable)
  --bars N         number of bars to render (default 4)
  -o, --out PATH   output WAV path (default build/drums/render/out.wav)
  --sample VOICE=path.wav   use path.wav instead of the stock sample for
                    VOICE (match by the .raw name, e.g. Kik1.raw, or by
                    its bare name, e.g. Kik1)
  --click          also play the metronome click voice (slot 0), off by
                    default since it's just a timing reference
"""
from __future__ import annotations

import argparse
import json
import math
import os
import struct
import sys
import wave

SAMPLE_RATE = 44100
PATTERNS_JSON = "build/drums/patterns.json"
WAV_DIR = "build/drums/wav"
DEFAULT_OUT = "build/drums/render/out.wav"


# ---------------------------------------------------------------- sample IO

def load_wav_mono_float(path: str):
    with wave.open(path, "rb") as w:
        assert w.getsampwidth() == 2, f"{path}: expected 16-bit PCM"
        n = w.getnframes()
        raw = w.readframes(n)
        nch = w.getnchannels()
    samples = struct.unpack(f"<{n * nch}h", raw)
    if nch > 1:
        samples = samples[0::nch]  # left channel only
    return [s / 32768.0 for s in samples]


def write_wav_mono_float(path: str, samples) -> None:
    peak = max((abs(s) for s in samples), default=0.0)
    scale = 1.0
    if peak > 0.999:
        scale = 0.999 / peak  # avoid clipping on busy renders
    ints = [max(-32768, min(32767, int(round(s * scale * 32767)))) for s in samples]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(struct.pack(f"<{len(ints)}h", *ints))


# --------------------------------------------------------- pattern loading

def load_patterns():
    if not os.path.exists(PATTERNS_JSON):
        sys.exit(
            f"{PATTERNS_JSON} not found -- run "
            f"`python tools/drums/decode_patterns.py` first"
        )
    with open(PATTERNS_JSON, "r", encoding="utf-8") as f:
        return json.load(f)["patterns"]


def find_pattern(patterns, name_or_index: str):
    try:
        idx = int(name_or_index)
        for p in patterns:
            if p["index"] == idx:
                return p
        sys.exit(f"no pattern at index {idx}")
    except ValueError:
        pass
    target = name_or_index.strip().lower().replace(" ", "")
    matches = [p for p in patterns if p["name"].strip().lower().replace(" ", "") == target]
    if not matches:
        # loose substring match as a fallback
        matches = [p for p in patterns if target in p["name"].lower().replace(" ", "")]
    if not matches:
        sys.exit(f"no pattern named {name_or_index!r} (try the `list` command)")
    if len(matches) > 1:
        sys.exit(
            f"{name_or_index!r} matches multiple patterns: "
            + ", ".join(f"{p['index']}:{p['name']}" for p in matches)
        )
    return matches[0]


# ----------------------------------------------------- voice role guessing

def voice_role(raw_name: str) -> str:
    n = raw_name
    if n.startswith("Kik"):
        return "kick"
    if n.startswith("Snr") or n.startswith("Clap") or n.startswith("Rim"):
        return "snare"
    if n.startswith("HHO"):
        return "hat_open"
    if n.startswith("HHC") or n.startswith("HHF"):
        return "hat_closed"
    if n.startswith("Ride"):
        return "ride"
    if n.startswith("Tom"):
        return "tom"
    if n.startswith("Tamb"):
        return "tamb"
    if n.startswith("Click"):
        return "click"
    return "other"


def is_ambience(raw_name: str) -> bool:
    return "Amb" in raw_name


def roles_for_pattern(voices):
    """voices: the 9-slot list from patterns.json (slot 0 = click).
    Returns {role: [primary_raw_name, amb_raw_name_or_none]}."""
    roles: dict[str, list] = {}
    for slot_idx, raw in enumerate(voices):
        raw = (raw or "").strip()
        if not raw:
            continue
        role = voice_role(raw)
        if role == "click":
            continue  # handled separately via --click
        entry = roles.setdefault(role, [None, None])
        if is_ambience(raw):
            if entry[1] is None:
                entry[1] = raw
        else:
            if entry[0] is None:
                entry[0] = raw
    return roles


# --------------------------------------------------------- groove builder

def guess_style(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("metro", "guide")):
        return "metro"
    if any(k in n for k in ("funk",)):
        return "funk"
    if any(k in n for k in ("break",)):
        return "breaks"
    if any(k in n for k in ("jazz", "bossa", "samba", "swing", "latin")):
        return "latin"
    if any(k in n for k in ("shuffle",)):
        return "shuffle"
    return "rock"


def generic_groove(beats_per_bar: int, beat_unit: int, style: str):
    """Build an approximate, generically-derived one-bar groove, expressed
    as {role: [(step, velocity), ...]} on a 16th-note step grid whose size
    follows the pattern's own time signature. This is NOT extracted from
    the firmware -- see the module docstring."""
    steps_per_beat = 2 if beat_unit == 8 else 4  # both give a 16th-note step
    steps_per_bar = max(1, beats_per_bar) * steps_per_beat
    hits: dict[str, list] = {}

    if style == "metro":
        return steps_per_bar, hits  # click-only; no kit

    def add(role, step, vel):
        hits.setdefault(role, []).append((step % steps_per_bar, vel))

    # kick: beat 1, and roughly the mid-bar beat for anything >= 3 beats
    add("kick", 0, 112)
    if beats_per_bar >= 3:
        add("kick", (beats_per_bar // 2) * steps_per_beat, 100)
    if style in ("funk", "breaks") and steps_per_beat >= 4:
        add("kick", (beats_per_bar - 1) * steps_per_beat - steps_per_beat // 4, 92)

    # snare/backbeat: odd beats (2, 4, ...), or just the last beat if too short
    snare_beats = [b for b in range(1, beats_per_bar, 2)] or [max(0, beats_per_bar - 1)]
    for b in snare_beats:
        add("snare", b * steps_per_beat, 108)

    # hats (or ride, for a latin/jazz feel): every 8th-note position
    role = "ride" if style == "latin" else "hat_closed"
    sub = max(1, steps_per_beat // 2)
    for s in range(0, steps_per_bar, sub):
        accent = 92 if s % steps_per_beat == 0 else 66
        add(role, s, accent)
    if style == "rock" and steps_per_beat >= 4:
        add("hat_open", steps_per_bar - 1, 85)

    return steps_per_bar, hits


def groove_from_json_voices(voices: dict, steps_per_bar_hint: int | None = None):
    """voices: {raw_sample_name: [[step, vel], ...]} from a user pattern.json.
    Returns (steps_per_bar, {raw_sample_name: [(step, vel), ...]})."""
    max_step = 0
    out = {}
    for raw, events in voices.items():
        pairs = [(int(s), int(v)) for s, v in events]
        out[raw] = pairs
        if pairs:
            max_step = max(max_step, max(s for s, _ in pairs))
    steps_per_bar = steps_per_bar_hint or (max_step + 1)
    return steps_per_bar, out


# -------------------------------------------------------------- rendering

def render(
    steps_per_bar: int,
    bpm: float,
    bars: int,
    hits_by_raw_name: dict,  # {raw_sample_name: [(step, velocity0_127), ...]}
    sample_lookup: dict,  # {raw_sample_name: [float samples]}
):
    sec_per_step = 60.0 / bpm / 4.0  # one step = one 16th note, always
    samples_per_step = SAMPLE_RATE * sec_per_step
    total_steps = steps_per_bar * bars
    total_len = int(total_steps * samples_per_step) + max(
        (len(s) for s in sample_lookup.values()), default=0
    )
    out = [0.0] * total_len

    for raw_name, events in hits_by_raw_name.items():
        voice_samples = sample_lookup.get(raw_name)
        if voice_samples is None:
            continue
        for bar in range(bars):
            for step, vel in events:
                abs_step = bar * steps_per_bar + step
                start = int(round(abs_step * samples_per_step))
                gain = max(0.0, min(1.0, vel / 127.0))
                for i, s in enumerate(voice_samples):
                    j = start + i
                    if j >= total_len:
                        break
                    out[j] += s * gain
    return out


def resolve_sample_path(raw_name: str, overrides: dict) -> str | None:
    base = raw_name[:-4] if raw_name.lower().endswith(".raw") else raw_name
    if raw_name in overrides:
        return overrides[raw_name]
    if base in overrides:
        return overrides[base]
    path = os.path.join(WAV_DIR, base + ".wav")
    return path if os.path.exists(path) else None


def parse_sample_overrides(items) -> dict:
    out = {}
    for item in items or []:
        if "=" not in item:
            sys.exit(f"--sample must be VOICE=path.wav, got {item!r}")
        voice, path = item.split("=", 1)
        out[voice] = path
    return out


# ---------------------------------------------------------------- commands

def cmd_list(args, patterns):
    print(f"{'idx':>3s}  {'name':10s}  {'meter':>6s}  voices")
    for p in patterns:
        meter = f"{p['beats_per_bar']}/{p['beat_unit']}"
        voices = ", ".join(v for v in p["voices"] if v)
        print(f"{p['index']:3d}  {p['name']:10s}  {meter:>6s}  {voices}")


def cmd_render(args, patterns):
    p = find_pattern(patterns, args.pattern)
    if args.bpm is None:
        sys.exit("--bpm is required (the firmware's stored tempo is a global "
                  "setting, not part of the pattern record -- pick any BPM)")
    style = guess_style(p["name"])
    steps_per_bar, role_hits = generic_groove(p["beats_per_bar"], p["beat_unit"], style)

    roles = roles_for_pattern(p["voices"])
    hits_by_raw_name: dict = {}
    for role, events in role_hits.items():
        primary, amb = roles.get(role, (None, None))
        if primary:
            hits_by_raw_name.setdefault(primary, []).extend(events)
        if amb:
            # ambience mic companion: same hits, quieter
            hits_by_raw_name.setdefault(amb, []).extend(
                (s, int(v * 0.7)) for s, v in events
            )
    if args.click and p["voices"][0]:
        click_steps = [(b * 4, 70) for b in range(p["beats_per_bar"])]
        # re-scale click to this pattern's own step grid
        spb = steps_per_bar // max(1, p["beats_per_bar"])
        click_steps = [(b * spb, 70) for b in range(p["beats_per_bar"])]
        hits_by_raw_name.setdefault(p["voices"][0], []).extend(click_steps)

    overrides = parse_sample_overrides(args.sample)
    sample_lookup = {}
    for raw_name in hits_by_raw_name:
        path = resolve_sample_path(raw_name, overrides)
        if path is None:
            print(f"warning: no WAV found for voice {raw_name!r}, skipping", file=sys.stderr)
            continue
        sample_lookup[raw_name] = load_wav_mono_float(path)

    out = render(steps_per_bar, args.bpm, args.bars, hits_by_raw_name, sample_lookup)
    write_wav_mono_float(args.out, out)
    print(
        f"rendered {p['name']!r} ({style} groove, approximate -- see module "
        f"docstring) at {args.bpm} BPM, {args.bars} bar(s), "
        f"{steps_per_bar} steps/bar -> {args.out}"
    )


def cmd_new(args, patterns):
    with open(args.pattern_file, "r", encoding="utf-8") as f:
        spec = json.load(f)
    bpm = args.bpm or spec.get("bpm")
    if not bpm:
        sys.exit("pattern JSON needs a \"bpm\" field, or pass --bpm")
    bars = args.bars or spec.get("bars", 1)
    steps_per_bar, hits_by_raw_name = groove_from_json_voices(
        spec["voices"], spec.get("steps_per_bar")
    )

    overrides = parse_sample_overrides(args.sample)
    sample_lookup = {}
    for raw_name in hits_by_raw_name:
        path = resolve_sample_path(raw_name, overrides)
        if path is None:
            print(f"warning: no WAV found for voice {raw_name!r}, skipping", file=sys.stderr)
            continue
        sample_lookup[raw_name] = load_wav_mono_float(path)

    out = render(steps_per_bar, bpm, bars, hits_by_raw_name, sample_lookup)
    write_wav_mono_float(args.out, out)
    print(
        f"rendered {spec.get('name', args.pattern_file)!r} at {bpm} BPM, "
        f"{bars} bar(s), {steps_per_bar} steps/bar -> {args.out}"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="list all decoded patterns")

    pr = sub.add_parser("render", help="render a built-in pattern (approximate groove)")
    pr.add_argument("pattern", help="pattern name (e.g. 'Rock1') or index (e.g. 7)")
    pr.add_argument("--bpm", type=float, default=None)
    pr.add_argument("--bars", type=int, default=4)
    pr.add_argument("-o", "--out", default=DEFAULT_OUT)
    pr.add_argument("--sample", action="append", default=[], help="VOICE=path.wav")
    pr.add_argument("--click", action="store_true")

    pn = sub.add_parser("new", help="render a user-authored exact pattern JSON")
    pn.add_argument("pattern_file")
    pn.add_argument("--bpm", type=float, default=None)
    pn.add_argument("--bars", type=int, default=None)
    pn.add_argument("-o", "--out", default=DEFAULT_OUT)
    pn.add_argument("--sample", action="append", default=[], help="VOICE=path.wav")

    args = ap.parse_args()
    patterns = load_patterns() if args.cmd in ("list", "render") else None

    if args.cmd == "list":
        cmd_list(args, patterns)
    elif args.cmd == "render":
        cmd_render(args, patterns)
    elif args.cmd == "new":
        cmd_new(args, None)


if __name__ == "__main__":
    main()
