"""Tests for the pure MIDI mapping module (tools/cf_midi_mapping.py)."""

from pathlib import Path
import tempfile
import unittest

from tools.cf_midi_mapping import (
    ControlKind,
    DEFAULT_CONTROLS,
    MidiStateManager,
)


class TestMidiMapping(unittest.TestCase):
    def setUp(self):
        self.mgr = MidiStateManager()

    def test_seventeen_controls_defined(self):
        self.assertEqual(len(self.mgr.controls), 17)
        cids = [c.cid for c in self.mgr.controls]
        self.assertEqual(len(set(cids)), 17, "All control IDs must be unique")

        # Verify exact expected control IDs
        expected_ids = {
            "fs_0", "fs_1",
            "btn_0", "btn_1", "btn_2", "btn_3", "btn_4", "btn_5", "btn_6", "btn_7", "btn_8", "btn_9",
            "knob_1", "knob_2", "knob_3", "knob_4",
            "expr",
        }
        self.assertEqual(set(cids), expected_ids)

        # Verify CC numbers
        ccs = [c.cc for c in self.mgr.controls]
        self.assertEqual(len(set(ccs)), 17, "All CCs must be unique in stock config")
        self.assertEqual(self.mgr.controls_by_cid["fs_0"].cc, 20)
        self.assertEqual(self.mgr.controls_by_cid["fs_1"].cc, 21)
        self.assertEqual(self.mgr.controls_by_cid["btn_0"].cc, 22)
        self.assertEqual(self.mgr.controls_by_cid["btn_9"].cc, 31)
        self.assertEqual(self.mgr.controls_by_cid["knob_1"].cc, 40)
        self.assertEqual(self.mgr.controls_by_cid["knob_4"].cc, 43)
        self.assertEqual(self.mgr.controls_by_cid["expr"].cc, 11)

    def test_button_press_and_release(self):
        ev_press = self.mgr.process_raw(20, 127)
        self.assertIsNotNone(ev_press)
        self.assertEqual(ev_press.cid, "fs_0")
        self.assertEqual(ev_press.value, 127)
        self.assertEqual(ev_press.display_value, "PRESSED")
        self.assertTrue(self.mgr.pressed["fs_0"])
        self.assertEqual(self.mgr.values["fs_0"], 127)

        ev_release = self.mgr.process_raw(20, 0)
        self.assertIsNotNone(ev_release)
        self.assertEqual(ev_release.cid, "fs_0")
        self.assertEqual(ev_release.value, 0)
        self.assertEqual(ev_release.display_value, "RELEASED")
        self.assertFalse(self.mgr.pressed["fs_0"])
        self.assertEqual(self.mgr.values["fs_0"], 0)

    def test_knob_and_expression_values(self):
        ev_knob = self.mgr.process_raw(40, 85)
        self.assertIsNotNone(ev_knob)
        self.assertEqual(ev_knob.cid, "knob_1")
        self.assertEqual(ev_knob.value, 85)
        self.assertEqual(ev_knob.display_value, "85")
        self.assertEqual(self.mgr.values["knob_1"], 85)

        ev_expr = self.mgr.process_raw(11, 102)
        self.assertIsNotNone(ev_expr)
        self.assertEqual(ev_expr.cid, "expr")
        self.assertEqual(ev_expr.value, 102)
        self.assertEqual(ev_expr.display_value, "102")
        self.assertEqual(self.mgr.values["expr"], 102)

    def test_mido_message_processing(self):
        try:
            import mido
            msg = mido.Message("control_change", channel=0, control=22, value=127)
            ev = self.mgr.process_mido_message(msg)
            self.assertIsNotNone(ev)
            self.assertEqual(ev.cid, "btn_0")
            self.assertEqual(ev.value, 127)

            # Non-CC message ignored
            note = mido.Message("note_on", channel=0, note=60, velocity=64)
            self.assertIsNone(self.mgr.process_mido_message(note))
        except ImportError:
            pass

    def test_custom_names_and_json_roundtrip(self):
        self.mgr.set_name("fs_0", "Preset Down")
        self.mgr.set_name("btn_9", "Rhythm Toggle")
        self.assertEqual(self.mgr.get_name("fs_0"), "Preset Down")
        self.assertEqual(self.mgr.get_name("btn_9"), "Rhythm Toggle")
        self.assertEqual(self.mgr.get_name("fs_1"), "Footswitch Right")

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = Path(tmpdir) / "midi_names.json"
            self.mgr.save_names(json_path)
            self.assertTrue(json_path.is_file())

            # Load into fresh manager
            mgr2 = MidiStateManager()
            loaded = mgr2.load_names(json_path)
            self.assertTrue(loaded)
            self.assertEqual(mgr2.get_name("fs_0"), "Preset Down")
            self.assertEqual(mgr2.get_name("btn_9"), "Rhythm Toggle")
            self.assertEqual(mgr2.get_name("fs_1"), "Footswitch Right")

    def test_export_csv(self):
        self.mgr.set_name("expr", "Wah / Volume")
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "daw_mapping.csv"
            self.mgr.export_csv(csv_path)
            content = csv_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(content[0], "Index,Control_ID,Name,CC,Type,Pin_Desc")
            self.assertEqual(len(content), 18)  # header + 17 rows
            self.assertIn('"Wah / Volume"', content[17])

    def test_learn_mode(self):
        self.mgr.start_learn("btn_3")
        # Simulate moving non-standard CC 55 to btn_3
        ev = self.mgr.process_raw(55, 127)
        self.assertIsNotNone(ev)
        self.assertEqual(ev.cid, "btn_3")
        self.assertIn("LEARNED CC 55", ev.display_value)
        self.assertIsNone(self.mgr.learn_target_cid)

        # Subsequent messages to CC 55 route to btn_3
        ev2 = self.mgr.process_raw(55, 0)
        self.assertEqual(ev2.cid, "btn_3")
        self.assertEqual(ev2.display_value, "RELEASED")

    def test_simulation_sequence(self):
        seq = MidiStateManager.simulation_sequence()
        self.assertGreater(len(seq), 0)
        for cc, val in seq:
            ev = self.mgr.process_raw(cc, val)
            self.assertIsNotNone(ev)
            self.assertFalse(ev.cid.startswith("unmapped"))

    def test_safety_grep_no_output_operations(self):
        """Strict check that both mapping and GUI monitor contain zero output/send calls."""
        root_tools = Path(__file__).resolve().parents[1] / "tools"
        for fname in ["cf_midi_mapping.py", "cf_midi_monitor.py"]:
            mod_file = root_tools / fname
            text = mod_file.read_text(encoding="utf-8")
            forbidden = ["open_output", ".send(", "Output(", "pedal_g1"]
            for bad in forbidden:
                self.assertNotIn(bad, text, f"Found forbidden term '{bad}' in {fname}")


if __name__ == "__main__":
    unittest.main()
