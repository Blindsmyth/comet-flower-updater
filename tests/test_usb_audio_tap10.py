"""Host tests for the 10-channel USB tap (make_usb_audio_fw.py --tap10): 1-2 mix (output words without the
converter gain), 3-4 guitar FX, 5-6 drums, 7-8 DI on both, 9-10 looper on both (owner, 2026-10-18)."""
import ctypes
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_usb_audio_proto import build_host_library, descriptors  # noqa: E402
from test_usb_audio_tap import TXCSR, PRIME  # noqa: E402
from test_usb_audio_tap8 import dry, fbus, f32  # noqa: E402
import random  # noqa: E402

F32 = ctypes.c_float * 16
I32 = ctypes.c_int * 16
NCH, WPF = 10, 5
MIX_L, MIX_R, DRUM_L, DRUM_R, LOOP = range(5)


class Tap10Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = build_host_library("host_harness_tap10.c", "usb_audio_tap10_HOST_TEST_ONLY")
        cls.lib.usb_audio_set_alt.argtypes = [ctypes.c_uint]
        cls.lib.host_take_fifo.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        cls.lib.usb_audio_copy_descriptors.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
        cls.lib.usb_audio_copy_descriptors.restype = ctypes.c_uint
        cls.lib.host_set_stem_ctl.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int, ctypes.c_float]
        cls.lib.ua_looper_tap.argtypes = [ctypes.c_int]

    def setUp(self):
        self.lib.host_reset()
        self.rng = random.Random(5)

    def fl(self, a=0.6):
        return [f32(self.rng.uniform(-a, a)) for _ in range(16)]

    def test_descriptor_10ch_900_bytes(self):
        self.lib.usb_audio_build_descriptors()
        out = (ctypes.c_ubyte * 512)()
        n = self.lib.usb_audio_copy_descriptors(out, 65535, 512)
        data = bytes(out[:n])
        self.assertEqual(n, 195)
        self.assertNotEqual(n % 64, 0)
        recs = descriptors(data)
        it = next(r for r in recs if r[1:3] == b"\x24\x02" and r[0] == 12)
        self.assertEqual(it[7], NCH)
        mask = int.from_bytes(it[8:10], "little")
        self.assertEqual(mask, 0x06ff)
        self.assertEqual(bin(mask).count("1"), NCH)
        fmt = next(r for r in recs if r[:4] == b"\x0e\x24\x02\x01")
        self.assertEqual(fmt[4:7], bytes([NCH, 2, 16]))
        ep = [r for r in recs if r[1] == 5][-1]
        self.assertEqual(int.from_bytes(ep[4:6], "little"), 45 * 2 * NCH)
        self.assertLessEqual(45 * 2 * NCH, 1023)

    def test_alt1_sets_maxp_900_and_1024_byte_banks(self):
        self.lib.usb_audio_set_alt(1)
        self.assertEqual(self.lib.host_get_register(0x01e00410), 900)
        self.assertEqual(self.lib.host_get_register(0x01e00462) & 0xff, 0x17)

    def test_packet_layout_every_pair(self):
        self.lib.usb_audio_set_alt(1)
        exp = []
        for _ in range(8):
            l = [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
            r = [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
            di, z = self.fl(), [0.0] * 16
            self.lib.host_set_sources(I32(*[0] * 16), I32(*[0] * 16), F32(*z), F32(*z), F32(*di), F32(*z))
            g_l, g_r = self.fl(), self.fl()
            self.lib.host_set_stem_buf(MIX_L, F32(*g_l))
            self.lib.host_set_stem_buf(MIX_R, F32(*g_r))
            d_l, d_r, p = self.fl(0.3), self.fl(0.3), self.fl(0.3)
            self.lib.host_set_stem_buf(DRUM_L, F32(*d_l))
            self.lib.host_set_stem_buf(DRUM_R, F32(*d_r))
            self.lib.host_set_stem_buf(LOOP, F32(*p))
            self.lib.host_set_stem_ctl(1, 1.0, 1, 1.0)
            self.lib.ua_looper_tap(0)
            self.lib.ua_looper_tap(1)
            self.lib.ua_drums_tap()
            self.lib.host_set_block(I32(*l), I32(*r))
            self.lib.ua_tx_pack_tap()
            exp += [(dry(l[i]) | dry(r[i]) << 16, fbus(g_l[i]) | fbus(g_r[i]) << 16,
                     fbus(d_l[i]) | fbus(d_r[i]) << 16, fbus(di[i]) * 0x10001, fbus(p[i]) * 0x10001)
                    for i in range(16)]
        self.lib.host_set_register(TXCSR, 0)
        self.lib.usb_audio_sof_tick_tap()
        buf = (ctypes.c_uint * 512)()
        n = self.lib.host_take_fifo(buf, 512)
        self.assertEqual(n, 45 * WPF)
        got = [tuple(buf[k:k + WPF]) for k in range(0, n, WPF)]
        self.assertEqual(got, exp[128 - PRIME:128 - PRIME + 45])


class Pairs8Tests(Tap10Tests):
    """--pairs8: the proven 8-channel descriptor, 7-8 DI on both, no looper."""
    @classmethod
    def setUpClass(cls):
        cls.lib = build_host_library("host_harness_pairs8.c", "usb_audio_pairs8_HOST_TEST_ONLY")
        cls.lib.usb_audio_set_alt.argtypes = [ctypes.c_uint]
        cls.lib.host_take_fifo.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        cls.lib.usb_audio_copy_descriptors.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
        cls.lib.usb_audio_copy_descriptors.restype = ctypes.c_uint
        cls.lib.host_set_stem_ctl.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int, ctypes.c_float]
        cls.lib.ua_looper_tap.argtypes = [ctypes.c_int]

    def test_descriptor_10ch_900_bytes(self):
        self.lib.usb_audio_build_descriptors()
        out = (ctypes.c_ubyte * 512)()
        n = self.lib.usb_audio_copy_descriptors(out, 65535, 512)
        recs = descriptors(bytes(out[:n]))
        it = next(r for r in recs if r[1:3] == b"$" and r[0] == 12)
        self.assertEqual((it[7], int.from_bytes(it[8:10], "little")), (8, 0x00ff))   # the proven shape

    def test_alt1_sets_maxp_900_and_1024_byte_banks(self):
        self.lib.usb_audio_set_alt(1)
        self.assertEqual(self.lib.host_get_register(0x01e00410), 720)

    def test_packet_layout_every_pair(self):
        self.lib.usb_audio_set_alt(1)
        exp = []
        for _ in range(8):
            l = [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
            r = [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
            di, z = self.fl(), [0.0] * 16
            self.lib.host_set_sources(I32(*[0] * 16), I32(*[0] * 16), F32(*z), F32(*z), F32(*di), F32(*z))
            g = self.fl()
            self.lib.host_set_stem_buf(MIX_L, F32(*g))
            self.lib.host_set_stem_buf(MIX_R, F32(*g))
            d = self.fl(0.3)
            self.lib.host_set_stem_buf(DRUM_L, F32(*d))
            self.lib.host_set_stem_buf(DRUM_R, F32(*d))
            self.lib.host_set_stem_ctl(1, 1.0, 1, 1.0)
            self.lib.ua_looper_tap(0)
            self.lib.ua_looper_tap(1)
            self.lib.ua_drums_tap()
            self.lib.host_set_block(I32(*l), I32(*r))
            self.lib.ua_tx_pack_tap()
            exp += [(dry(l[i]) | dry(r[i]) << 16, fbus(g[i]) | fbus(g[i]) << 16,
                     fbus(d[i]) | fbus(d[i]) << 16, fbus(di[i]) * 0x10001) for i in range(16)]
        self.lib.host_set_register(TXCSR, 0)
        self.lib.usb_audio_sof_tick_tap()
        buf = (ctypes.c_uint * 512)()
        n = self.lib.host_take_fifo(buf, 512)
        got = [tuple(buf[k:k + 4]) for k in range(0, n, 4)]
        self.assertEqual(got, exp[128 - PRIME:128 - PRIME + 45])


if __name__ == "__main__":
    unittest.main()
