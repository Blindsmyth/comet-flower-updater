"""Convert the pedal's drum sample dumps (backup/*/files/*.raw) to WAV.

Format of the .raw files (established by inspection, see
docs/DRUM_MACHINE_2026-10-22.md "Samples" section for the evidence):
  - no header, just sample data
  - signed 16-bit, little-endian
  - mono
  - 44.1 kHz (the pedal's fixed audio rate; not stored in the file, assumed)

Evidence: interpreting the bytes as int16 little-endian gives a clean
attack-then-decay envelope (e.g. Kik1.raw: head/tail amplitude ratio ~45:1)
and a kick/hat/snare-appropriate frequency spectrum (Kik1 spectral centroid
~790 Hz, HHC ~12.1 kHz, Snr1 ~5.1 kHz). The big-endian or 8-bit readings of
the same bytes give a much flatter envelope (ratio ~2:1 or inverted), so
those are ruled out. This also matches the firmware's own voice mixer
(11817520, see docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md section "Drum
Voice PCM Fetcher"): it LDHs (loads 16-bit halfwords) directly from the
sample ROM into a 16-bit voice buffer, with no decode/unpack step.

Usage:
  raw2wav.py <file.raw> [<file2.raw> ...] -o <out_dir>
  raw2wav.py --all   # convert every backup/2026-10-04/files/*.raw to
                      # build/drums/wav/<name>.wav and print a report
"""
from __future__ import annotations

import argparse
import glob
import os
import struct
import wave

SAMPLE_RATE = 44100
DEFAULT_SRC_DIR = "backup/2026-10-04/files"
DEFAULT_OUT_DIR = "build/drums/wav"


def raw_to_pcm16(raw_bytes: bytes) -> bytes:
    """Return the raw bytes as-is: they are already signed 16-bit LE mono,
    which is exactly what a 16-bit PCM WAV data chunk needs. Trims a
    trailing odd byte if present (shouldn't happen, but be defensive)."""
    if len(raw_bytes) % 2:
        raw_bytes = raw_bytes[:-1]
    return raw_bytes


def write_wav(path: str, pcm16_bytes: bytes, sample_rate: int = SAMPLE_RATE) -> None:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm16_bytes)


def analyze(raw_bytes: bytes) -> dict:
    n = len(raw_bytes) // 2
    samples = struct.unpack(f"<{n}h", raw_bytes[: n * 2])
    peak = max(abs(s) for s in samples) if samples else 0
    duration_s = n / SAMPLE_RATE
    return {"n_samples": n, "duration_s": duration_s, "peak": peak}


def convert_one(src_path: str, out_dir: str) -> dict:
    with open(src_path, "rb") as f:
        raw_bytes = f.read()
    pcm = raw_to_pcm16(raw_bytes)
    stats = analyze(pcm)
    name = os.path.splitext(os.path.basename(src_path))[0]
    out_path = os.path.join(out_dir, name + ".wav")
    os.makedirs(out_dir, exist_ok=True)
    write_wav(out_path, pcm)
    stats["name"] = name
    stats["out_path"] = out_path
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("files", nargs="*", help="*.raw files to convert")
    ap.add_argument("-o", "--out-dir", default=DEFAULT_OUT_DIR)
    ap.add_argument(
        "--all", action="store_true",
        help=f"convert every *.raw in {DEFAULT_SRC_DIR}",
    )
    args = ap.parse_args()

    files = list(args.files)
    if args.all:
        files = sorted(glob.glob(os.path.join(DEFAULT_SRC_DIR, "*.raw")))

    if not files:
        ap.error("no input files (pass paths, or --all)")

    rows = []
    for f in files:
        rows.append(convert_one(f, args.out_dir))

    rows.sort(key=lambda r: r["name"])
    print(f"{'name':12s} {'samples':>8s} {'dur(s)':>8s} {'peak':>7s} {'peak(dBFS)':>11s}")
    import math
    for r in rows:
        peak = r["peak"]
        dbfs_str = "-inf" if peak == 0 else f"{20*math.log10(peak/32768.0):.1f}"
        print(f"{r['name']:12s} {r['n_samples']:8d} {r['duration_s']:8.3f} {r['peak']:7d} {dbfs_str:>11s}")


if __name__ == "__main__":
    main()
