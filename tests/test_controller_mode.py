"""Effects/MIDI mode toggle (controller.c) on the host, with recording stubs.

The real controller.c is compiled for the host (ctl_host_harness.c). The
dispatch hook's choice is modelled by host_dispatch: effects mode goes through
controller_gate, MIDI mode through controller_event.
"""
import ctypes
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import test_usb_audio_proto as host  # noqa: E402

SRC = ROOT / "firmware" / "controller"
PRESS, RELEASE = 23, 24          # the mode button (GPIO0, likely Rhythm)
STOCK, CONSUMED, MIDI = 0, 1, 2


class ModeToggle(unittest.TestCase):
    def setUp(self):
        # A fresh library per test: controller.c keeps its state in globals.
        try:
            self.lib = host.build_host_library("ctl_host_harness.c", "ctl_mode_HOST_TEST_ONLY",
                                               src_dir=SRC)
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        L = self.lib
        L.host_dispatch.restype = ctypes.c_uint
        L.host_dispatch.argtypes = [ctypes.POINTER(ctypes.c_int * 4)]
        for name in ("host_mode", "host_knob_record", "host_connected", "host_edges"):
            getattr(L, name).restype = ctypes.c_uint

    def u(self, name):
        return ctypes.c_uint.in_dll(self.lib, name)

    def at(self, ticks):
        self.u("host_ticks").value = ticks

    def send(self, event_id, *words):
        rec = (ctypes.c_int * 4)(event_id, *words)
        return self.lib.host_dispatch(ctypes.byref(rec)), list(rec)

    def edges(self):
        out = (ctypes.c_uint * 16)()
        n = self.lib.host_edges(out, 16)
        return [(20 + (e >> 8), e & 0xff) for e in out[:n]]

    def ui_modes(self):
        n = self.u("host_ui_nmodes").value
        return list((ctypes.c_uint * 8).in_dll(self.lib, "host_ui_modes")[:n])

    def test_short_press_in_effects_mode_reaches_stock_in_order(self):
        self.at(1000)
        self.assertEqual(self.send(PRESS, 7, 1, 0)[0], CONSUMED)   # held back
        self.at(1300)
        action, rec = self.send(RELEASE, 23, 0, 0)
        self.assertEqual(action, STOCK)
        self.assertEqual(rec, [PRESS, 7, 1, 0])                    # the saved press
        self.assertEqual(self.u("host_posts").value, 1)            # release reposted
        self.assertEqual(self.u("host_post_handle").value, 0x1234)
        self.assertEqual(list((ctypes.c_uint * 4).in_dll(self.lib, "host_post_msg")),
                         [RELEASE, 0, 0, 0])
        self.assertEqual(self.u("host_last_raw").value, PRESS)
        self.assertEqual(self.send(RELEASE, 23, 0, 0), (STOCK, [RELEASE, 23, 0, 0]))
        self.assertEqual(self.lib.host_mode(), 0)
        self.assertEqual(self.send(5, 0, 0, 0)[0], STOCK)          # other buttons untouched

    def test_failed_repost_does_not_swallow_a_later_release(self):
        self.u("host_post_ok").value = 0
        self.at(0)
        self.send(PRESS)
        self.at(100)
        self.assertEqual(self.send(RELEASE)[0], STOCK)
        self.at(200)
        self.assertEqual(self.send(PRESS)[0], CONSUMED)            # next press works as usual

    def test_two_second_hold_toggles_both_ways(self):
        self.at(5000)
        self.send(PRESS)
        self.at(6999)
        self.lib.host_set_connected(1)
        self.assertEqual(self.send(RELEASE)[0], STOCK)             # 1999 ms: still a short press
        self.send(RELEASE)                                         # the reposted release
        self.at(7000)
        self.send(PRESS)
        self.at(9000)
        self.assertEqual(self.send(RELEASE)[0], CONSUMED)          # 2000 ms: MIDI mode
        self.assertEqual(self.lib.host_mode(), 1)
        self.assertEqual(self.lib.host_connected(), 0)             # full replay on next pass
        for i in range(4):
            self.assertEqual(self.lib.host_knob_record(i) & 0x1ff, 0x100 | 64)
        self.assertEqual(self.ui_modes(), [1])
        self.assertEqual(self.u("host_posts").value, 1)            # nothing reposted for a toggle

        # MIDI mode: a short press is a CC31 tap, a long one leaves
        self.at(10000)
        self.assertEqual(self.send(PRESS)[0], MIDI)
        self.assertEqual(self.edges(), [])                         # nothing on press
        self.at(10100)
        self.send(RELEASE)
        self.assertEqual(self.edges(), [(31, 127), (31, 0)])
        self.at(11000)
        self.send(PRESS)
        self.at(13000)
        self.send(RELEASE)
        self.assertEqual(self.lib.host_mode(), 0)
        self.assertEqual(self.ui_modes(), [1, 0])
        self.assertEqual(self.edges(), [(31, 127), (31, 0)])       # no CC for the toggle

    def test_tick_counter_wrap(self):
        self.at(0xFFFFFF00)
        self.send(PRESS)
        self.at(0x00000800)                                        # 2304 ms later, wrapped
        self.assertEqual(self.send(RELEASE)[0], CONSUMED)
        self.assertEqual(self.lib.host_mode(), 1)

    def test_boot_entry_still_swallows_its_own_release(self):
        self.u("host_switches").value = ~(1 << 9) & 0xFFFFFFFF
        self.lib.host_start()
        self.assertEqual(self.lib.host_mode(), 1)
        self.at(5000)
        self.send(RELEASE)                                         # boot hold ends: no toggle
        self.assertEqual(self.lib.host_mode(), 1)
        self.assertEqual(self.edges(), [])

    def test_start_installs_the_settings_page_once(self):
        self.lib.host_start()
        self.assertEqual(self.u("host_menu_installs").value, 1)
        self.assertEqual(self.lib.host_mode(), 0)                  # boots in FX (owner)

    def test_usb_audio_start_up_button(self):
        self.u("host_switches").value = ~(1 << 2) & 0xFFFFFFFF          # B3 held
        self.lib.host_start()
        self.assertEqual((self.u("host_ua_request").value, self.lib.host_mode()), (1, 0))

    def test_no_usb_audio_without_its_button(self):
        self.u("host_switches").value = ~(1 << 9) & 0xFFFFFFFF          # Rhythm: MIDI only
        self.lib.host_start()
        self.assertEqual((self.u("host_ua_request").value, self.lib.host_mode()), (0, 1))

    def test_menu_mode_item_enters_midi_mode(self):
        L = self.lib
        L.host_get_mode_for_menu.restype = ctypes.c_uint
        self.assertEqual(L.host_get_mode_for_menu(), 0)
        L.host_set_mode_from_menu(1)
        self.assertEqual((L.host_mode(), self.ui_modes()), (1, [1]))
        L.host_set_mode_from_menu(1)                               # unchanged: no second entry
        self.assertEqual(self.ui_modes(), [1])
        self.assertEqual(self.send(25, 0, 3, 0)[0], MIDI)          # knobs now send CCs
        L.host_set_mode_from_menu(0)
        self.assertEqual((L.host_mode(), self.ui_modes()), (0, [1, 0]))

    def test_release_without_press_is_stock(self):
        self.assertEqual(self.send(RELEASE), (STOCK, [RELEASE, 0, 0, 0]))
        self.assertEqual(self.u("host_posts").value, 0)


if __name__ == "__main__":
    unittest.main()
