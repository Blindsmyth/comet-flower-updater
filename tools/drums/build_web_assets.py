"""Builds the standalone Comet Flower Drum Machine Emulator and Pattern Editor.

This script packs:
  1. All 24 extracted Zoom 44.1 kHz 16-bit PCM WAV samples (build/drums/wav/*.wav)
  2. All 69 firmware-decoded drum patterns (build/drums/patterns.json)
  3. The pedal UI ordering permutation (tools/drums/ui_order.json)
  4. Comet Flower logos and graphics (assets/logo_comet_flower.png & splash)

Outputs:
  - tools/drums/comet_flower_drums.html (and root comet_flower_drums.html)
  - tools/drums/comet_flower_data.js (for standalone data inspection)
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WAV_DIR = ROOT / "build" / "drums" / "wav"
PATTERNS_JSON = ROOT / "build" / "drums" / "patterns.json"
UI_ORDER_JSON = ROOT / "tools" / "drums" / "ui_order.json"
LOGO_PNG = ROOT / "assets" / "logo_comet_flower.png"
SPLASH_PNG = ROOT / "assets" / "splash_comet_flower.png"

OUT_HTML_TOOLS = ROOT / "tools" / "drums" / "comet_flower_drums.html"
OUT_HTML_ROOT = ROOT / "comet_flower_drums.html"
OUT_DATA_JS = ROOT / "tools" / "drums" / "comet_flower_data.js"


def load_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def collect_data():
    if not PATTERNS_JSON.exists():
        sys.exit(f"Missing {PATTERNS_JSON} -- run decode_patterns.py first")
    if not UI_ORDER_JSON.exists():
        sys.exit(f"Missing {UI_ORDER_JSON}")
    if not WAV_DIR.exists():
        sys.exit(f"Missing {WAV_DIR} -- run raw2wav.py --all first")

    # Load patterns
    with open(PATTERNS_JSON, "r", encoding="utf-8") as f:
        patterns_data = json.load(f)["patterns"]

    # Load UI order
    with open(UI_ORDER_JSON, "r", encoding="utf-8") as f:
        ui_order = json.load(f)["order"]

    # Load samples
    samples = {}
    for wav_file in sorted(WAV_DIR.glob("*.wav")):
        raw_key = wav_file.stem + ".raw"
        samples[raw_key] = {
            "name": wav_file.stem,
            "raw_key": raw_key,
            "size_bytes": wav_file.stat().st_size,
            "b64": load_b64(wav_file),
        }

    # Load logos
    logo_b64 = load_b64(LOGO_PNG) if LOGO_PNG.exists() else ""
    splash_b64 = load_b64(SPLASH_PNG) if SPLASH_PNG.exists() else ""

    return {
        "patterns": patterns_data,
        "ui_order": ui_order,
        "samples": samples,
        "logos": {
            "logo_comet_flower_b64": logo_b64,
            "splash_comet_flower_b64": splash_b64,
        },
    }


def main():
    print("Collecting drum machine extraction data...")
    data = collect_data()
    print(f"Loaded {len(data['patterns'])} patterns, {len(data['samples'])} audio samples, {len(data['ui_order'])} UI order entries.")

    # Write separate JS data module
    json_str = json.dumps(data, indent=None)
    with open(OUT_DATA_JS, "w", encoding="utf-8") as f:
        f.write("window.COMET_FLOWER_DATA = " + json_str + ";\n")
    print(f"Wrote {OUT_DATA_JS} ({OUT_DATA_JS.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
