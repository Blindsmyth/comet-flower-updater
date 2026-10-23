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
        self.u32("host_flushes")[0] = 0
        cpu = self.u32("host_cpu", 9)
        for i in range(9):
            cpu[i] = 0                    # no meter unless a test publishes the record

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

    def cpu(self, pct):
        cpu = self.u32("host_cpu", 9)
        cpu[0] = 0x4D555043
        cpu[3] = (pct * 132354 + 50) // 100

    def bar_text(self, x0, x1, inv):
        """Decode the text centred between x0 and x1 (as cf_header.c centres it) with the firmware font."""
        glyphs = {bytes(self.font[6 * i:6 * i + 6]): chr(0x20 + i) for i in range(94, -1, -1)}
        cols = []
        for x in range(x0, x1):
            b = self.lcd[x] | (self.lcd[128 + x] & 3) << 8
            if inv:
                b = ~b & 0x3FE
            cols.append((b >> 2) & 0x7F)
        for n in range((x1 - x0) // 6, 0, -1):
            left = (x1 - x0 - 6 * n) >> 1
            text = "".join(glyphs.get(bytes(cols[left + 6 * i:left + 6 * i + 6]), "?") for i in range(n))
            pad = cols[:left] + cols[left + 6 * n:]
            if "?" not in text and not any(pad) and text.strip() == text and text:
                return text
        return None

    def test_meter_and_short_header(self):
        self.cpu(83)
        self.draw([CFMPRE, DELAY, DELAY, DELAY, DELAY], 0, 1)
        self.assertEqual(self.bar_text(19, 102, True), "PRE>MUFF FUZZ")
        self.assertEqual(self.bar_text(103, 128, False), "83%")
        OUT.mkdir(parents=True, exist_ok=True)
        ui_mock.show(self.image()).save(OUT / "cfh_meter.png")

    def test_meter_on_stock_effect_leaves_name_box(self):
        self.cpu(64)
        self.draw([DELAY] * 5, 2, 0)
        self.assertTrue(all(self.lcd[x] == 0x55 for x in range(0, 102)))
        self.assertEqual(self.bar_text(103, 128, False), "64%")

    def test_meter_inverted_when_high(self):
        self.cpu(107)
        self.draw([DELAY] * 5, 0, 0)
        self.assertEqual(self.bar_text(103, 128, True), "107%")

    def test_meter_warning_starts_at_88(self):
        self.cpu(87)
        self.draw([DELAY] * 5, 0, 0)
        self.assertEqual(self.bar_text(103, 128, False), "87%")
        self.cpu(88)
        self.draw([DELAY] * 5, 0, 0)
        self.assertEqual(self.bar_text(103, 128, True), "88%")

    def test_tick_refreshes_only_on_change_and_only_while_shown(self):
        self.cpu(70)
        self.draw([DELAY] * 5, 0, 0)
        self.assertEqual(self.lib.host_tick(), 0)            # same value: nothing to do
        self.cpu(81)
        self.assertEqual(self.lib.host_tick(), 1)
        self.assertEqual(self.u32("host_flushes")[0], 1)
        self.assertEqual(self.bar_text(103, 128, False), "81%")
        self.lcd[110] ^= 0xFF                                  # another screen drew there
        self.cpu(90)
        self.assertEqual(self.lib.host_tick(), 0)
        self.cpu(91)
        self.assertEqual(self.lib.host_tick(), 0)             # stays off until the next edit draw
        self.assertEqual(self.u32("host_flushes")[0], 1)
        self.draw([DELAY] * 5, 0, 0)
        self.assertEqual(self.bar_text(103, 128, True), "91%")   # 88 % and above: inverted

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
