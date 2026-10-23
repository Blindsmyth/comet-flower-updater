"""Checks for the per-pattern event-blob decode (tools/drums/decode_patterns.py
"Event blob format" section, added job S14, 2026-10-23).

See docs/DRUM_MACHINE_2026-10-22.md "Event blob (decoded, job S14)" for the
full writeup: byte layout, disassembly evidence, and the known
`partial_unmapped_voice`/`suspect` caveats these tests pin down rather than
hide.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FW_IMAGE = ROOT / "build" / "fw" / "res1_493412.bin"

sys.path.insert(0, str(ROOT / "tools" / "drums"))
import decode_patterns  # noqa: E402


def _ticks_by_voice(pattern, voice_id):
    return sorted({ev["tick"] for ev in pattern["steps"] if ev["voice_id"] == voice_id})


@unittest.skipUnless(FW_IMAGE.exists(), "firmware image not present in this checkout")
class TestEventBlobDecode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patterns = decode_patterns.decode_table(str(FW_IMAGE))
        cls.by_name = {p["name"].strip(): p for p in cls.patterns}

    # -------------------------------------------------- structural checks

    def test_every_pattern_has_a_decoded_blob(self):
        for p in self.patterns:
            self.assertTrue(p["event_blob_decoded"], p["name"])
            self.assertIn("steps", p)

    def test_every_blob_has_an_odd_body_length_ie_a_trailing_loop_byte(self):
        # (delta,value) pairs + exactly one trailing loop-delta byte, every
        # time, across all 69 patterns -- see module docstring.
        for p in self.patterns:
            self.assertTrue(p["has_trailing_loop_byte"], p["name"])

    def test_loop_length_is_always_a_whole_number_of_bars(self):
        # loop_length_ticks (sum of deltas + trailing byte) must equal an
        # exact multiple of beats_per_bar * 12 ticks for every pattern --
        # the strongest structural confirmation that the byte layout
        # (delta,value) pairs + loop-delta + 0xf0 terminator is correct.
        for p in self.patterns:
            self.assertTrue(
                p["loop_bars_is_whole"],
                f"{p['name']}: loop_length_ticks={p['loop_length_ticks']} "
                f"is not a multiple of bar_ticks={p['bar_ticks']}",
            )
            self.assertGreaterEqual(p["loop_bars"], 1)

    def test_voice_ids_are_always_in_1_to_9(self):
        for p in self.patterns:
            for ev in p["steps"]:
                self.assertGreaterEqual(ev["voice_id"], 1, p["name"])
                self.assertLessEqual(ev["voice_id"], 9, p["name"])

    def test_levels_are_always_in_0_to_15(self):
        for p in self.patterns:
            for ev in p["steps"]:
                self.assertGreaterEqual(ev["level"], 0, p["name"])
                self.assertLessEqual(ev["level"], 15, p["name"])

    def test_click_voice_id_always_maps_to_a_populated_slot(self):
        # Voice ID 9 (click) is the one voice ID that resolves to a real
        # sample in literally every one of the 69 patterns -- even Metro3,
        # whose other events are all unmapped, simply never emits a voice-9
        # event at all (see test_metro3_is_flagged_suspect below), rather
        # than emitting one that fails to resolve. IDs 1/2/3/8 (kick,
        # snare-amb, snare, kick-amb) are unmapped in a handful of sparse
        # patterns that genuinely have no kick/snare sample at all (e.g.
        # Jazz1 is hat+ride only) -- not tested here as "always", since
        # that would overclaim; see docs/DRUM_MACHINE_2026-10-22.md.
        for p in self.patterns:
            for ev in p["steps"]:
                if ev["voice_id"] == 9:
                    self.assertTrue(
                        ev["mapped"],
                        f"{p['name']}: click voice id 9 at tick {ev['tick']} "
                        f"has no sample (slot {ev['slot']})",
                    )

    def test_decode_confidence_summary_matches_known_counts(self):
        # Pins the exact split found during job S14's decode so a future
        # change to the mapping rule shows up here. See docs/DRUM_MACHINE_
        # 2026-10-22.md for the per-pattern list.
        counts = {}
        for p in self.patterns:
            counts[p["decode_confidence"]] = counts.get(p["decode_confidence"], 0) + 1
        self.assertEqual(counts.get("ok", 0), 47)
        self.assertEqual(counts.get("partial_unmapped_voice", 0), 21)
        self.assertEqual(counts.get("suspect", 0), 1)

    # ------------------------------------------- known-answer checks (task)

    def test_metronome_pattern_is_one_click_per_beat(self):
        # Metro4 and Metro5 and Metro (undecorated) all decode to a plain
        # click (voice 9) exactly once every beat (12 ticks), for the whole
        # 2-bar loop, with no other voice present. Metro3 is excluded: its
        # blob doesn't resolve to any real voice at all (decode_confidence
        # == "suspect", see docs) and is almost certainly a mis-resolved
        # pointer, not a real metronome groove.
        for name in ("Metro4", "Metro5", "Metro"):
            p = self.by_name[name]
            self.assertEqual(p["decode_confidence"], "ok", name)
            voice_ids = {ev["voice_id"] for ev in p["steps"]}
            self.assertEqual(voice_ids, {9}, f"{name}: expected click-only, got {voice_ids}")

            bpb = p["beats_per_bar"]
            bar_ticks = bpb * p["ticks_per_beat"]
            expected_ticks = list(range(0, p["loop_length_ticks"], p["ticks_per_beat"]))
            actual_ticks = [ev["tick"] for ev in p["steps"]]
            self.assertEqual(
                actual_ticks, expected_ticks,
                f"{name}: clicks are not evenly spaced one-per-beat",
            )
            # exactly bpb clicks per bar, for exactly loop_bars bars
            self.assertEqual(len(p["steps"]), bpb * p["loop_bars"])

            # downbeat (first beat of each bar) is accented louder than the
            # other beats in that bar -- true for every metronome pattern.
            for bar in range(int(p["loop_bars"])):
                bar_start_tick = bar * bar_ticks
                downbeat = next(ev for ev in p["steps"] if ev["tick"] == bar_start_tick)
                others = [
                    ev for ev in p["steps"]
                    if bar_start_tick < ev["tick"] < bar_start_tick + bar_ticks
                ]
                for ev in others:
                    self.assertGreater(downbeat["level"], ev["level"], name)

    def test_guide_pattern_is_one_click_per_beat_one_bar(self):
        p = self.by_name["GUIDE"]
        bpb = p["beats_per_bar"]
        voice_ids = {ev["voice_id"] for ev in p["steps"]}
        self.assertEqual(voice_ids, {9})
        self.assertEqual(len(p["steps"]), bpb)  # 1-bar loop, one click per beat
        self.assertEqual(
            [ev["tick"] for ev in p["steps"]],
            [b * p["ticks_per_beat"] for b in range(bpb)],
        )

    def test_rock1_has_a_classic_backbeat(self):
        # Known-answer check from the task brief: Rock1 should look like a
        # standard rock beat. Confirmed: snare (voice 3 = Snr1.raw) lands
        # on beats 2 and 4 of every bar, nowhere else; kick (voice 1 =
        # Kik1.raw) lands on beat 1 plus syncopated 16th-note pushes.
        p = self.by_name["Rock1"]
        self.assertEqual(p["decode_confidence"], "ok")
        bar_ticks = p["beats_per_bar"] * p["ticks_per_beat"]  # 48

        snare_ticks_mod_bar = {ev["tick"] % bar_ticks for ev in p["steps"] if ev["voice_id"] == 3}
        self.assertEqual(snare_ticks_mod_bar, {12, 36})  # beat 2 and beat 4

        kick_ticks_mod_bar = {ev["tick"] % bar_ticks for ev in p["steps"] if ev["voice_id"] == 1}
        self.assertIn(0, kick_ticks_mod_bar)  # downbeat kick present

        # the hi-hat (voice 5 = HHC.raw) and its ambience companion
        # (voice 7 = HHCAmb.raw) always fire on the exact same ticks --
        # resolves the "do dry/Amb pairs fire together" open question
        # from docs/DRUM_MACHINE_2026-10-22.md section 6 point 5.
        hat_ticks = _ticks_by_voice(p, 5)
        hat_amb_ticks = _ticks_by_voice(p, 7)
        self.assertEqual(hat_ticks, hat_amb_ticks)
        self.assertTrue(hat_ticks)

    def test_8beats1_kick_hits_every_beat(self):
        # Known-answer check: "8Beats1" should literally have 8 kick hits
        # across its loop (one per beat, 4 beats/bar x 2 bars).
        p = self.by_name["8Beats1"]
        kick_ticks = [ev["tick"] for ev in p["steps"] if ev["voice_id"] == 1]
        self.assertEqual(len(kick_ticks), 8)
        self.assertEqual(
            kick_ticks, list(range(0, p["loop_length_ticks"], p["ticks_per_beat"]))
        )

    def test_metro3_is_flagged_suspect_not_silently_trusted(self):
        p = self.by_name["Metro3"]
        self.assertEqual(p["decode_confidence"], "suspect")
        self.assertEqual(p["n_events_mapped"], 0)
        # and, tellingly, its blob never even references the click voice,
        # despite being named "Metro3" -- strong evidence this pointer
        # resolves outside the real event data (see docs).
        voice_ids = {ev["voice_id"] for ev in p["steps"]}
        self.assertNotIn(9, voice_ids)


if __name__ == "__main__":
    unittest.main()
