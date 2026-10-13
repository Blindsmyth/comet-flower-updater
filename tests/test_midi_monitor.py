"""Tests for the pure MIDI mapping module (tools/cf_midi_mapping.py)."""

from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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
        self.assertEqual(self.mgr.get_name("fs_1"), "Footswitch GPIO5")

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
            self.assertEqual(mgr2.get_name("fs_1"), "Footswitch GPIO5")

    def test_other_channels_do_not_change_controls_or_consume_learn(self):
        values = self.mgr.values.copy()
        pressed = self.mgr.pressed.copy()
        bindings = self.mgr.cc_to_cid.copy()
        for channel in range(1, 16):
            self.assertIsNone(self.mgr.process_raw(20, 127, channel=channel))
            self.mgr.start_learn("btn_3")
            msg = SimpleNamespace(type="control_change", channel=channel,
                                  control=55, value=127)
            self.assertIsNone(self.mgr.process_mido_message(msg))
            self.assertEqual(self.mgr.learn_target_cid, "btn_3")
            self.assertEqual(self.mgr.values, values)
            self.assertEqual(self.mgr.pressed, pressed)
            self.assertEqual(self.mgr.cc_to_cid, bindings)
        learned = self.mgr.process_raw(55, 127, channel=0)
        self.assertEqual(learned.cid, "btn_3")
        self.assertEqual(learned.raw_bytes, "B0 37 7F")
        self.assertIsNone(self.mgr.learn_target_cid)

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
        self.assertEqual(self.mgr.get_cc("btn_3"), 55)
        self.assertTrue(self.mgr.process_raw(25, 127).cid.startswith("unmapped"))

        with tempfile.TemporaryDirectory() as tmpdir:
            names_path = Path(tmpdir) / "names.json"
            csv_path = Path(tmpdir) / "mapping.csv"
            self.mgr.save_names(names_path)
            restored = MidiStateManager()
            self.assertTrue(restored.load_names(names_path))
            self.assertEqual(restored.get_cc("btn_3"), 55)
            self.assertTrue(restored.process_raw(25, 127).cid.startswith("unmapped"))
            restored.export_csv(csv_path)
            self.assertIn('btn_3,"Button 3 (GPIO 27)",55,', csv_path.read_text(encoding="utf-8"))

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


class TestMidiMonitorGui(unittest.TestCase):
    """Exercise GUI connection/dispatch code without Tk windows or MIDI hardware."""

    def test_reconnect_rejects_old_messages_errors_and_blocked_reader(self):
        from tools.cf_midi_monitor import MidiMonitorApp

        class FakePort:
            def __init__(self, message, fail_on_release=False):
                self.message = message
                self.fail_on_release = fail_on_release
                self.reads = 0
                self.blocked = threading.Event()
                self.release = threading.Event()
                self.closed = False

            def iter_pending(self):
                self.reads += 1
                yield self.message
                self.blocked.set()
                if not self.release.wait(5):
                    raise RuntimeError("fake-port test timed out")
                if self.fail_on_release:
                    raise RuntimeError("old port closed")
                yield self.message

            def close(self):
                self.closed = True

        for fail_on_release in (False, True):
            with self.subTest(fail_on_release=fail_on_release):
                old = FakePort(SimpleNamespace(type="control_change", channel=0,
                                               control=20, value=127), fail_on_release)
                new = FakePort(SimpleNamespace(type="control_change", channel=0,
                                               control=21, value=127))
                root = Mock()
                main_thread = threading.get_ident()

                def after(*args):
                    self.assertEqual(threading.get_ident(), main_thread)
                    return "timer"

                root.after.side_effect = after

                def build_ui(app):
                    app.port_combo = Mock()
                    app.port_combo.get.return_value = "Fake input"
                    app.btn_connect = Mock()
                    app.btn_refresh = Mock()
                    app.status_var = Mock()
                    app.log_text = Mock()

                with tempfile.TemporaryDirectory() as tmpdir, \
                        patch("tools.cf_midi_monitor.DEFAULT_NAMES_PATH", Path(tmpdir) / "names.json"), \
                        patch.object(MidiMonitorApp, "_build_ui", build_ui), \
                        patch.object(MidiMonitorApp, "_refresh_ports"), \
                        patch("tools.cf_midi_monitor.mido") as midi:
                    midi.open_input.side_effect = [old, new]
                    app = MidiMonitorApp(root)
                    app._apply_event = Mock()
                    app._log_line = Mock()
                    workers = []
                    try:
                        app._connect_port()
                        workers.append(app.listen_thread)
                        self.assertTrue(old.blocked.wait(2))
                        old_stop = app.stop_listening
                        app._disconnect_port()
                        app._connect_port()
                        workers.append(app.listen_thread)
                        self.assertTrue(new.blocked.wait(2))
                        self.assertIsNot(app.stop_listening, old_stop)
                        self.assertTrue(old_stop.is_set())
                        self.assertTrue(old.closed)
                        old.release.set()
                        workers[0].join(2)
                        self.assertFalse(workers[0].is_alive())
                        self.assertEqual(old.reads, 1)
                        self.assertEqual(new.reads, 1)

                        app._poll_incoming()
                        self.assertEqual(app.state_mgr.values["fs_0"], 0)
                        self.assertEqual(app.state_mgr.values["fs_1"], 127)
                        app._apply_event.assert_called_once()
                        self.assertEqual(app._apply_event.call_args.args[0].cid, "fs_1")
                        self.assertFalse(any("MIDI read error" in str(call)
                                             for call in app._log_line.call_args_list))

                        app.state_mgr.start_learn("btn_3")
                        app._handle_incoming_mido(SimpleNamespace(
                            type="control_change", channel=1, control=55, value=127))
                        self.assertEqual(app.state_mgr.learn_target_cid, "btn_3")
                        self.assertTrue(app._log_line.call_args.args[0].startswith("Raw MIDI:"))
                        app._apply_event.assert_called_once()
                        app._on_close()
                        root.after_cancel.assert_called_once_with("timer")
                        root.destroy.assert_called_once()
                    finally:
                        app.stop_listening.set()
                        old.release.set()
                        new.release.set()
                        for worker in workers:
                            worker.join(2)
                            self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
