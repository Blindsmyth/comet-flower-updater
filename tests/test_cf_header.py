"""CF edit-page header (firmware/controller/cf_header.c) on the host.

The real cf_header.c is compiled for the host with cf_header_host_harness.c; the
stock renderer is a recorder, the LCD a 512-byte page buffer. Each CFM Pre page is
rendered with the firmware's own font to build/ui_mock/cfh_page<n>.png for review.
"""
import ctypes
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import g1fw_gfx as gfx  # noqa: E402
import test_usb_audio_proto as host  # noqa: E402
import ui_mock  # noqa: E402

SRC = ROOT / "firmware" / "controller"
RES1 = ROOT / "build" / "fw" / "res1_493412.bin"
OUT = ROOT / "build" / "ui_mock"
CFMPRE, DELAY = 0x07000F91, 0x08000F8B


class CfHeader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not RES1.exists():
            raise unittest.SkipTest("stock res1 not present")
        try:
            cls.lib = host.build_host_library("cf_header_host_harness.c", "cf_header_HOST_TEST_ONLY", src_dir=SRC)
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        buf = RES1.read_bytes()
        o = gfx.a2f(gfx.FONTS["font_5x7"][0])
        cls.font = buf[o:o + 95 * 6]

    def setUp(self):
        L = self.lib
        self.u32 = lambda n, k=1: (ctypes.c_uint * k).in_dll(L, n)
        self.lcd = (ctypes.c_ubyte * 512).in_dll(L, "host_lcd")
        f = (ctypes.c_ubyte * (95 * 6)).in_dll(L, "host_font")
        for i, b in enumerate(self.font):
            f[i] = b
        for i in range(512):
            self.lcd[i] = 0x55            # pattern: the stock frame underneath
        (ctypes.c_ubyte * 2).in_dll(L, "host_dirty")[0] = 0
        self.u32("host_stock_calls").__setitem__(0, 0)

    def draw(self, ids, sel, page):
        ids_a, pages = self.u32("host_ids", 5), self.u32("host_page", 5)
        for i in range(5):
            ids_a[i] = ids[i]
            pages[i] = 0
        pages[sel] = page
        self.u32("host_sel")[0] = sel
        return self.lib.host_edit_draw()

    def image(self):
        cols = bytes(self.lcd)
        return ui_mock.render([("columns", cols)], RES1.read_bytes())

    def test_stock_runs_and_return_value_passes_through(self):
        r = self.draw([DELAY] * 5, 0, 0)
        self.assertEqual(r, 0x1234)
        self.assertEqual(self.u32("host_stock_calls")[0], 1)
        self.assertEqual(list(self.u32("host_stock_args", 6)), [0, 1, 2, 3, 4, 5])

    def test_other_effects_untouched(self):
        self.draw([DELAY, DELAY, DELAY, DELAY, DELAY], 1, 0)
        self.assertTrue(all(b == 0x55 for b in self.lcd))
        self.assertEqual((ctypes.c_ubyte * 2).in_dll(self.lib, "host_dirty")[0], 0)

    def test_cfmpre_pages(self):
        stages = ["DYNA COMP", "MUFF FUZZ", "MISTRESS", "OUTPUT"]
        for page, stage in enumerate(stages):
            self.setUp()
            self.draw([CFMPRE, DELAY, DELAY, DELAY, DELAY], 0, page)
            text = "CFM PRE>" + stage
            # expected bar, built in Python from the same font
            x0 = 19 + ((109 - 6 * len(text)) >> 1)
            for x in range(128):
                p0, p1 = self.lcd[x], self.lcd[128 + x]
                if x < 19:
                    self.assertEqual((p0, p1), (0x55, 0x55), x)
                    continue
                k = x - x0
                g = self.font[6 * (ord(text[k // 6]) - 0x20) + k % 6] if 0 <= k < 6 * len(text) else 0
                bits = g << 2
                self.assertEqual(p0, 0xFE & ~bits & 0xFF, (page, x))
                self.assertEqual(p1, (0x55 & 0xF0) | (0x03 & ~(bits >> 8)), (page, x))
            for x in range(256, 512):
                self.assertEqual(self.lcd[x], 0x55)
            self.assertEqual((ctypes.c_ubyte * 2).in_dll(self.lib, "host_dirty")[0], 3)
            OUT.mkdir(parents=True, exist_ok=True)
            ui_mock.show(self.image()).save(OUT / f"cfh_page{page + 1}.png")

    def test_selected_slot_and_out_of_range(self):
        self.draw([DELAY, CFMPRE, DELAY, DELAY, DELAY], 0, 1)
        self.assertTrue(all(b == 0x55 for b in self.lcd))     # CFM Pre not selected
        self.setUp()
        self.draw([DELAY, CFMPRE, DELAY, DELAY, DELAY], 1, 9)  # page past the table: name only
        self.assertNotEqual(self.lcd[64], 0x55)
        self.setUp()
        self.u32("host_sel")[0] = 7
        self.lib.host_edit_draw()
        self.assertTrue(all(b == 0x55 for b in self.lcd))


if __name__ == "__main__":
    unittest.main()
