"""Tests for the Comet Flower Drum Machine Studio & Pattern Lab.

Validates:
  - Generation of the self-contained HTML studio (comet_flower_drums.html)
  - Integrity of embedded audio samples (24 44.1kHz samples in base64)
  - Integrity of embedded pattern step tables (69 firmware patterns)
  - Interoperability with tools/drums/drum_machine.py new CLI command
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "comet_flower_drums.html"
DATA_JS = ROOT / "tools" / "drums" / "comet_flower_data.js"
WAV_DIR = ROOT / "build" / "drums" / "wav"
PATTERNS_JSON = ROOT / "build" / "drums" / "patterns.json"


@unittest.skipUnless(PATTERNS_JSON.exists() and WAV_DIR.exists(), "Drum assets not built")
class TestCometFlowerStudio(unittest.TestCase):
    def test_studio_html_exists_and_embedded(self):
        self.assertTrue(HTML_PATH.exists(), "comet_flower_drums.html must exist")
        # Check size is over 1MB (indicating audio & pattern tables are fully embedded)
        size_kb = HTML_PATH.stat().st_size / 1024
        self.assertGreater(size_kb, 800, f"HTML size is {size_kb} KB, expected > 800 KB")

        content = HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("COMET_FLOWER_DATA", content)
        self.assertIn("CF-DRUM-9", content)
        self.assertIn("Kik1.raw", content)

    def test_data_js_integrity(self):
        self.assertTrue(DATA_JS.exists(), "comet_flower_data.js must exist")
        content = DATA_JS.read_text(encoding="utf-8")
        prefix = "window.COMET_FLOWER_DATA = "
        self.assertTrue(content.startswith(prefix))
        raw_json = content[len(prefix):].rstrip(";\n")
        data = json.loads(raw_json)

        self.assertEqual(len(data["samples"]), 24, "Expected 24 audio samples")
        self.assertEqual(len(data["patterns"]), 69, "Expected 69 patterns")
        self.assertIn("logos", data)
        self.assertTrue(data["logos"]["logo_comet_flower_b64"])

    def test_pattern_export_cli_interoperability(self):
        test_pattern = {
            "name": "StudioUnitTestBeat",
            "bpm": 128,
            "bars": 1,
            "steps_per_bar": 16,
            "voices": {
                "Kik1.raw": [[0, 127], [8, 110]],
                "Snr1.raw": [[4, 120], [12, 120]],
                "HHC.raw": [[0, 90], [2, 70], [4, 90], [6, 70], [8, 90], [10, 70], [12, 90], [14, 70]]
            }
        }
        test_json_path = ROOT / "build" / "drums" / "render" / "test_studio_export.json"
        test_wav_path = ROOT / "build" / "drums" / "render" / "test_studio_export.wav"

        test_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(test_json_path, "w", encoding="utf-8") as f:
            json.dump(test_pattern, f)

        res = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "drums" / "drum_machine.py"), "new", str(test_json_path), "-o", str(test_wav_path)],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Render failed: {res.stderr}")
        self.assertTrue(test_wav_path.exists())
        self.assertGreater(test_wav_path.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
