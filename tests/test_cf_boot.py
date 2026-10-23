"""Start-up bloom animation (firmware/controller/cf_boot.c) on the host, against
the frames tools/make_boot_anim.py generates (the C decoder must match)."""
import ctypes
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import make_boot_anim as anim  # noqa: E402
import test_usb_audio_proto as host  # noqa: E402

SRC = ROOT / "firmware" / "controller"


class CfBoot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = anim.build()[1]
        hdr = (SRC / "boot_anim.h").read_text(encoding="utf-8")
        if hdr != anim.header(anim.build()[2]):
            raise AssertionError("boot_anim.h is stale: run tools/make_boot_anim.py")

    def setUp(self):
        try:
            self.lib = host.build_host_library("cf_boot_host_harness.c", "cf_boot_HOST_TEST_ONLY", src_dir=SRC)
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))
        ctypes.memset(self.lcd_addr(), 0, 512)
        for name in ("host_blits", "host_flushes"):
            ctypes.c_uint.in_dll(self.lib, name).value = 0

    def lcd_addr(self):
        return ctypes.addressof((ctypes.c_ubyte * 512).in_dll(self.lib, "host_lcd"))

    def lcd(self):
        return bytes((ctypes.c_ubyte * 512).in_dll(self.lib, "host_lcd"))

    def test_rle_round_trip(self):
        for r in self.raw:
            self.assertEqual(anim.rle_decode(anim.rle_encode(r))[0], r)

    def test_full_run(self):
        L = self.lib
        n = L.host_nframes()
        self.assertEqual(n, len(self.raw))
        self.assertEqual(L.host_logo(0), 0x100)           # stock result passed back
        self.assertEqual(self.lcd(), self.raw[0])          # frame 0 over the stock logo
        for k in range(1, n):
            self.assertEqual(L.host_tick(), 1)
            self.assertEqual(self.lcd(), self.raw[k])
        self.assertEqual(L.host_tick(), 0)                 # last frame held, done
        self.assertEqual(L.host_state(), 2)
        self.assertEqual(ctypes.c_uint.in_dll(L, "host_flushes").value, n - 1)
        L.host_logo(0)                                     # later visit: stock only
        self.assertNotEqual(self.lcd(), self.raw[-1])

    def test_redraw_mid_animation_restores_frame(self):
        L = self.lib
        L.host_logo(0)
        L.host_tick()
        L.host_tick()
        L.host_logo(0)                                     # the screen is redrawn
        self.assertEqual(self.lcd(), self.raw[2])
        self.assertEqual(L.host_tick(), 1)

    def test_next_screen_stops_it(self):
        L = self.lib
        L.host_logo(0)
        ctypes.memset(self.lcd_addr(), 0x55, 512)          # stock draws the next screen
        self.assertEqual(L.host_tick(), 0)
        self.assertEqual(L.host_state(), 2)
        self.assertEqual(self.lcd(), b"\x55" * 512)

    def test_other_ctx_is_stock(self):
        L = self.lib
        L.host_logo(1)
        self.assertEqual(L.host_state(), 0)
        self.assertEqual(L.host_tick(), 0)


if __name__ == "__main__":
    unittest.main()
