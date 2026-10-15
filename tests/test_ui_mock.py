"""On-pedal UI mock-ups: every proposed screen fits 128x32 and renders from the firmware fonts."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import ui_mock  # noqa: E402

RES1 = ROOT / "build" / "fw" / "res1_493412.bin"


class UiMock(unittest.TestCase):
    def test_no_text_overflows(self):
        self.assertEqual(ui_mock.overflows(), [])

    @unittest.skipUnless(RES1.exists(), "stock res1 not available")
    def test_screens_render_lit_pixels(self):
        buf = RES1.read_bytes()
        for name, spec in ui_mock.SCREENS.items():
            im = ui_mock.render(spec, buf)
            self.assertEqual(im.size, (128, 32))
            self.assertGreater(sum(im.histogram()[1:]), 100, name)

    @unittest.skipUnless(RES1.exists(), "stock res1 not available")
    def test_font_glyph_matches_firmware(self):
        # 'A' in font_5x7 is decoded from the firmware, not a host font
        g, w, h = ui_mock.Fonts(RES1.read_bytes()).glyph("font_5x7", "A")
        self.assertEqual((w, h), (6, 8))
        self.assertGreater(sum(g.histogram()[128:]), 8)


if __name__ == "__main__":
    unittest.main()
