"""Comet Flower settings page (controller_menu.c) on the host.

The stock tables are host arrays with their boot contents (decoded from the
.cinit data, docs/CF_MENU_PAGE_2026-10-16.md); the stock screen/draw/editor
routines are recorders.
"""
import ctypes
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import test_usb_audio_proto as host  # noqa: E402

SRC = ROOT / "firmware" / "controller"
W = ctypes.c_ulonglong


def load():
    try:
        return host.build_host_library("menu_host_harness.c", "ctl_menu_HOST_TEST_ONLY", src_dir=SRC)
    except RuntimeError as exc:
        raise unittest.SkipTest(str(exc))


class Menu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.L = load()
        cls.L.host_icon.restype = W
        cls.L.host_event.argtypes = [ctypes.POINTER(W), ctypes.c_int, ctypes.c_int]

    def setUp(self):
        self.L.host_reset()

    def tab(self, name, n):
        return (W * n).in_dll(self.L, name)

    def u(self, name):
        return ctypes.c_uint.in_dll(self.L, name).value

    def event(self, desc, id_, w2=0):
        return self.L.host_event(self.tab(desc, 9), id_, w2)

    def test_install_rewrites_only_the_listed_words(self):
        L = self.L
        self.assertEqual(L.host_install(), 1)
        d0, d1, d5 = (list(self.tab(n, 9)) for n in ("host_desc0", "host_desc1", "host_desc5"))
        self.assertEqual(list(self.tab("host_list_b", 5)), [5, 1, 1, 1, 1])
        self.assertEqual(d0[:8], [0, 0, 0, 0, 0, 0, 0xc0157c0c, 0xc01579c0])
        self.assertEqual(d1[:8], [1, 0, 0, 0, 0, 0, 0xc0157c0c, 0xc01579c0])
        self.assertEqual(d0[8], d1[8])
        self.assertNotEqual(d0[8], 0xc0157bac)
        self.assertEqual(d5[1:4], [L.host_icon(0), L.host_icon(1), L.host_icon(2)])
        self.assertEqual([d5[0], d5[4], d5[5], d5[7]], [5, 0xc016a978, 0, 0xc016a940])

    def test_install_leaves_unexpected_tables_stock(self):
        names = ("host_desc0", "host_desc1", "host_desc5")
        for name, idx in (("host_desc0", 8), ("host_desc1", 1), ("host_desc5", 6), ("host_list_b", 4)):
            self.L.host_reset()
            t = self.tab(name, 5 if name == "host_list_b" else 9)
            t[idx] += 1
            before = [list(self.tab(n, 9)) for n in names] + [list(self.tab("host_list_b", 5))]
            self.assertEqual(self.L.host_install(), 0, name)
            after = [list(self.tab(n, 9)) for n in names] + [list(self.tab("host_list_b", 5))]
            self.assertEqual(before, after, name)

    def test_knob_turn_flips_chooser_pages(self):
        self.L.host_install()
        self.assertEqual(self.event("host_desc0", 25, 1), 1)      # right on page 1 -> page 2
        self.assertEqual((self.u("host_set_calls"), self.u("host_set_last")), (1, 1))
        self.assertEqual(self.event("host_desc1", 28, 3), 0)      # right on page 2: stays
        self.assertEqual(self.event("host_desc1", 27, -2), 1)     # left -> page 1
        self.assertEqual(self.u("host_set_last"), 0)
        self.assertEqual(self.event("host_desc0", 26, -1), 0)     # left on page 1: stays
        self.assertEqual(self.event("host_desc0", 25, 0), 0)      # no movement
        self.assertEqual(self.u("host_set_calls"), 2)
        self.assertEqual(self.u("host_chooser_calls"), 0)         # knobs never reach stock

    def test_page_two_empty_slots_are_swallowed(self):
        L = self.L
        L.host_install()
        ctypes.c_uint.in_dll(L, "host_screen").value = 1
        for ev in (12, 14, 16, 18, 20):
            self.assertEqual(self.event("host_desc1", ev, 2), 0)   # slot 3: empty
        self.assertEqual(self.u("host_chooser_calls"), 0)
        self.assertEqual(self.event("host_desc1", 12, 0), 7)       # slot 1: our page, stock opens it
        self.assertEqual(self.event("host_desc1", 6, 0), 7)        # SETTING/exit stays stock
        self.assertEqual(self.event("host_desc1", 13, 2), 7)       # presses stay stock (ignored there)
        ctypes.c_uint.in_dll(L, "host_screen").value = 0
        self.assertEqual(self.event("host_desc0", 16, 2), 7)       # page 1 slots unchanged
        self.assertEqual(self.u("host_chooser_calls"), 4)

    def test_cf_page_draw_and_mode_item(self):
        L = self.L
        L.host_install()
        L.host_page_draw()
        self.assertEqual(self.u("host_draw_count"), 1)
        self.assertEqual((self.u("host_draw_font_label"), self.u("host_draw_font_value")), (1, 1))
        title = ctypes.c_char_p.in_dll(L, "host_draw_title").value
        self.assertEqual(title, b"COMET FLOWER")
        rec = ctypes.cast(ctypes.c_void_p.in_dll(L, "host_draw_records"), ctypes.POINTER(W))
        words = [rec[i] for i in range(11)]
        self.assertEqual(words[:3], [0, 0xfff, 0xfff])
        self.assertEqual(ctypes.string_at(words[3]), b"MODE")
        self.assertEqual((words[4], words[5], words[6], words[10]), (0, 0, 1, 0))   # min 0, max 1
        fmt = ctypes.CFUNCTYPE(ctypes.c_char_p, ctypes.c_int)(words[7])
        self.assertEqual((fmt(0), fmt(1)), (b"FX", b"MIDI"))
        get = ctypes.CFUNCTYPE(ctypes.c_int)(words[8])
        put = ctypes.CFUNCTYPE(None, ctypes.c_int)(words[9])
        self.assertEqual(get(), 0)
        put(1)
        self.assertEqual((get(), self.u("host_mode_sets")), (1, 1))

    def test_cf_page_edits_only_its_knob(self):
        self.L.host_install()
        self.assertEqual(self.event("host_desc5", 25, 1), 1)
        self.assertEqual((self.u("host_edit_calls"), self.u("host_edit_count")), (1, 1))
        for ev in (26, 27, 28, 6, 12, 24):
            self.assertEqual(self.event("host_desc5", ev, 1), 0)
        self.assertEqual(self.u("host_edit_calls"), 1)


class Icon(unittest.TestCase):
    def test_icon_header_is_current(self):
        import make_menu_icon
        hdr = (SRC / "menu_icon.h").read_text()
        for name, art in make_menu_icon.VARIANTS:
            data = make_menu_icon.pack(make_menu_icon.icon(art))
            self.assertEqual(len(data), 96)
            self.assertIn(", ".join("0x%02x" % b for b in data[:12]), hdr, name)


if __name__ == "__main__":
    unittest.main()
