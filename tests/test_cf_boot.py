"""Start-up bloom (firmware/controller/cf_boot.c) on the host, against the frames
tools/make_boot_anim.py generates (the C decoder must match)."""
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
        _, cls.raw, codes = anim.build()
        if (SRC / "boot_anim.h").read_text(encoding="utf-8") != anim.header(codes):
            raise AssertionError("boot_anim.h is stale: run tools/make_boot_anim.py")

    def setUp(self):
        try:
            self.lib = host.build_host_library("cf_boot_host_harness.c", "cf_boot_HOST_TEST_ONLY", src_dir=SRC)
        except RuntimeError as exc:
            raise unittest.SkipTest(str(exc))

    def u32(self, name):
        return ctypes.c_uint.in_dll(self.lib, name)

    def lcd(self):
        return bytes((ctypes.c_ubyte * 512).in_dll(self.lib, "host_lcd"))

    def seen(self, k):
        return bytes((ctypes.c_ubyte * 512).from_buffer(
            (ctypes.c_ubyte * (16 * 512)).in_dll(self.lib, "host_seen"), 512 * k))

    def test_first_frame_matches_tools(self):
        self.assertEqual(self.lib.host_first(), anim.BOOT_FIRST)
        self.assertEqual(self.lib.host_nframes(), len(self.raw))

    def test_plays_bloom_then_leaves_last_frame(self):
        L, first, n = self.lib, anim.BOOT_FIRST, len(self.raw)
        self.assertEqual(L.host_logo(0), 0x100)              # stock result passed back
        self.assertEqual(self.u32("host_flushes").value, n - 1 - first)
        for k in range(n - 1 - first):
            self.assertEqual(self.seen(k), self.raw[first + k])
        self.assertEqual(self.lcd(), self.raw[-1])            # for UpdateUI's own flush
        self.assertEqual(self.u32("host_starts").value, 0)     # counter was running
        L.host_logo(0)                                         # later visit: stock only
        self.assertEqual(self.u32("host_flushes").value, n - 1 - first)
        self.assertNotEqual(self.lcd(), self.raw[-1])

    def test_stopped_counter_is_started_and_cannot_hang(self):
        self.u32("host_step").value = 0
        self.lib.host_logo(0)                                  # returns: WAIT_CAP bounds it
        self.assertEqual(self.u32("host_starts").value, 1)
        self.assertEqual(self.lcd(), self.raw[-1])

    def test_other_ctx_is_stock(self):
        self.lib.host_logo(1)
        self.assertEqual(self.u32("host_flushes").value, 0)

    def test_boot_logo_is_the_first_frame_cropped(self):
        im = anim.boot_logo()
        self.assertEqual(im.size, (92, 16))
        self.assertEqual(list(im.getdata()), list(anim.frame(anim.BOOT_FIRST).crop(anim.LOGO_BOX).getdata()))

    def test_rle_round_trip(self):
        for r in self.raw:
            self.assertEqual(anim.rle_decode(anim.rle_encode(r))[0], r)


if __name__ == "__main__":
    unittest.main()
