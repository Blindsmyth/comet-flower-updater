"""Sanity checks for the drum sample format decode (tools/drums/raw2wav.py).

See docs/DRUM_MACHINE_2026-10-22.md "Samples" for the evidence behind the
format (no header, signed 16-bit little-endian, mono, 44.1 kHz): these
tests pin that down so a future change can't silently flip it.
"""
import glob
import os
import struct
import sys
import unittest
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "drums"))
import raw2wav  # noqa: E402

RAW_DIR = Path(__file__).resolve().parents[1] / "backup" / "2026-10-04" / "files"


def _raw_files():
    return sorted(glob.glob(str(RAW_DIR / "*.raw")))


@unittest.skipUnless(RAW_DIR.is_dir(), "pedal backup not present in this checkout")
class TestRawFormat(unittest.TestCase):
    def test_all_24_expected_samples_present(self):
        names = {os.path.splitext(os.path.basename(p))[0] for p in _raw_files()}
        expected = {
            "Kik1", "Kik2", "KikAmb", "Snr1", "Snr2", "Snr3", "Snr4", "SnrAmb",
            "HHC", "HHO", "HHF", "HHCAmb", "HHOAmb", "Ride", "Rim", "RimAmb",
            "Clap", "ClapAmb", "Click", "Tamb", "TomH", "TomL", "TomF", "TomFAmb",
        }
        self.assertEqual(names, expected)

    def test_even_byte_length(self):
        # 16-bit samples -> every file must be an even number of bytes.
        for p in _raw_files():
            size = os.path.getsize(p)
            self.assertEqual(size % 2, 0, f"{p} has an odd length ({size} bytes)")

    def test_le16_decode_has_decaying_envelope(self):
        # The defining sanity check: a drum one-shot should start loud and
        # decay. Interpreting the bytes as signed 16-bit little-endian mono
        # gives a strong head/tail amplitude ratio; big-endian or 8-bit
        # readings of the same bytes do not (see raw2wav.py docstring and
        # docs/DRUM_MACHINE_2026-10-22.md for the numbers this pins down).
        kik1 = RAW_DIR / "Kik1.raw"
        if not kik1.exists():
            self.skipTest("Kik1.raw not present")
        data = kik1.read_bytes()
        n = len(data) // 2
        samples = struct.unpack(f"<{n}h", data[: n * 2])
        head = samples[: n // 10]
        tail = samples[-(n // 10):]
        head_amp = sum(abs(s) for s in head) / len(head)
        tail_amp = sum(abs(s) for s in tail) / len(tail)
        self.assertGreater(head_amp, 20 * tail_amp,
                            "expected a strong attack-then-decay envelope")

    def test_raw_to_pcm16_is_passthrough_and_even(self):
        odd = b"\x01\x02\x03"
        out = raw2wav.raw_to_pcm16(odd)
        self.assertEqual(len(out) % 2, 0)
        self.assertEqual(out, b"\x01\x02")

    def test_convert_and_analyze_roundtrip(self, tmp_name="build/drums/wav/_test_Kik1.wav"):
        kik1 = RAW_DIR / "Kik1.raw"
        if not kik1.exists():
            self.skipTest("Kik1.raw not present")
        stats = raw2wav.convert_one(str(kik1), "build/drums/wav")
        self.assertGreater(stats["peak"], 0)
        self.assertGreater(stats["duration_s"], 0)
        with wave.open(stats["out_path"], "rb") as w:
            self.assertEqual(w.getframerate(), raw2wav.SAMPLE_RATE)
            self.assertEqual(w.getsampwidth(), 2)
            self.assertEqual(w.getnchannels(), 1)
            self.assertEqual(w.getnframes(), stats["n_samples"])


if __name__ == "__main__":
    unittest.main()
