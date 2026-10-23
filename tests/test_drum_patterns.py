"""Checks for the rhythm/pattern table decode (tools/drums/decode_patterns.py).

See docs/DRUM_MACHINE_2026-10-22.md "Patterns" for the full writeup,
including the one known discrepancy with the pedal's live reading
(Blues 2's pattern number) that these tests document rather than hide.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FW_IMAGE = ROOT / "build" / "fw" / "res1_493412.bin"

sys.path.insert(0, str(ROOT / "tools" / "drums"))
import decode_patterns  # noqa: E402

KNOWN_VOICE_NAMES = {
    "Kik1.raw", "Kik2.raw", "KikAmb.raw", "Snr1.raw", "Snr2.raw", "Snr3.raw",
    "Snr4.raw", "SnrAmb.raw", "HHC.raw", "HHO.raw", "HHF.raw", "HHCAmb.raw",
    "HHOAmb.raw", "Ride.raw", "Rim.raw", "RimAmb.raw", "Clap.raw", "ClapAmb.raw",
    "Click.raw", "Tamb.raw", "TomH.raw", "TomL.raw", "TomF.raw", "TomFAmb.raw",
}


@unittest.skipUnless(FW_IMAGE.exists(), "firmware image not present in this checkout")
class TestPatternTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patterns = decode_patterns.decode_table(str(FW_IMAGE))
        cls.by_index = {p["index"]: p for p in cls.patterns}

    def test_table_has_69_records(self):
        # Index 0 ("GUIDE") plus 68 selectable patterns; record 69 runs
        # into unrelated data and decode_table() stops there.
        self.assertEqual(len(self.patterns), 69)

    def test_rock1_is_index_7_matching_live_pedal_reading(self):
        # docs/LOOPER_DRUMS_TEARDOWN_2026-10-22.md: the pedal's live
        # "pattern number" read 7 while Rock 1 was selected.
        self.assertEqual(self.by_index[7]["name"], "Rock1")

    def test_blues2_pattern_number_does_not_match_live_pedal_reading(self):
        # Known open issue: the pedal reported Blues 2 = pattern number 44,
        # but in this static ROM table "Blues2" is at index 27 and index 44
        # is "PopRock". Rock 1 matches (see test above) but Blues 2 doesn't,
        # so something reorders the live pattern-number space (see the
        # "Pattern numbering" section of docs/DRUM_MACHINE_2026-10-22.md).
        # This test pins down what the static table actually says, so a
        # future fix to the indexing shows up as a deliberate change here.
        self.assertEqual(self.by_index[27]["name"], "Blues2")
        self.assertEqual(self.by_index[44]["name"], "PopRock")

    def test_every_voice_slot_is_a_known_sample_or_empty(self):
        for p in self.patterns:
            for raw_name in p["voices"]:
                if raw_name:
                    self.assertIn(
                        raw_name, KNOWN_VOICE_NAMES,
                        f"pattern {p['index']} ({p['name']!r}) references "
                        f"unknown voice {raw_name!r}",
                    )

    def test_every_pattern_has_9_voice_slots(self):
        for p in self.patterns:
            self.assertEqual(len(p["voices"]), 9, p["name"])

    def test_click_voice_present_in_every_pattern(self):
        # Slot 0 is the metronome "click" track; every one of the 69
        # records has it, including the click-only Metro/Metro3/4/5
        # patterns (which have nothing else assigned).
        with_click = sum(1 for p in self.patterns if p["voices"][0] == "Click.raw")
        self.assertEqual(with_click, len(self.patterns))

    def test_beats_per_bar_and_beat_unit_are_plausible(self):
        seen_bpb = {p["beats_per_bar"] for p in self.patterns}
        seen_bu = {p["beat_unit"] for p in self.patterns}
        self.assertTrue(seen_bpb.issubset({3, 4, 5, 6, 8, 12}))
        self.assertTrue(seen_bu.issubset({4, 8}))

    def test_all_24_known_samples_are_referenced_somewhere(self):
        used = set()
        for p in self.patterns:
            used.update(v for v in p["voices"] if v)
        self.assertEqual(used, KNOWN_VOICE_NAMES)


if __name__ == "__main__":
    unittest.main()
