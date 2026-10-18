"""Host tests for the stems tap (make_usb_audio_fw.py --stems): drums alone on USB 5-6,
looper alone on 8, with the pedal's own mix unchanged. The stock drum mixer and looper are
host stand-ins with the arithmetic main.dis shows: bus = (bus + x) * gain. Offline only."""
import ctypes
import random
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_usb_audio_proto import build_host_library  # noqa: E402
from test_usb_audio_tap import sample, TXCSR, PRIME  # noqa: E402
from test_usb_audio_tap8 import dry, fbus, f32  # noqa: E402

F32 = ctypes.c_float * 16
I32 = ctypes.c_int * 16
WPF = 4
MIX_L, MIX_R, DRUM_L, DRUM_R, LOOP = range(5)


class UsbAudioStemsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = build_host_library("host_harness_tap8_stems.c", "usb_audio_stems_HOST_TEST_ONLY")
        cls.lib.usb_audio_set_alt.argtypes = [ctypes.c_uint]
        cls.lib.host_take_fifo.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        cls.lib.host_set_stem_ctl.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int, ctypes.c_float]
        cls.lib.ua_looper_tap.argtypes = [ctypes.c_int]

    def setUp(self):
        self.lib.host_reset()
        self.rng = random.Random(11)

    def fl(self, a=0.6):
        return [f32(self.rng.uniform(-a, a)) for _ in range(16)]

    def put(self, which, v):
        self.lib.host_set_stem_buf(which, F32(*v))

    def get(self, which):
        out = F32()
        self.lib.host_get_stem_buf(which, out)
        return list(out)

    def test_drums_stem_and_mix_bit_identical_at_unity(self):
        s_l, s_r, d_l, d_r = self.fl(), self.fl(), self.fl(0.3), self.fl(0.3)
        for w, v in ((MIX_L, s_l), (MIX_R, s_r), (DRUM_L, d_l), (DRUM_R, d_r)):
            self.put(w, v)
        self.lib.host_set_stem_ctl(1, 1.0, 1, 1.0)
        self.lib.ua_drums_tap()
        self.assertEqual(self.get(DRUM_L), d_l)
        self.assertEqual(self.get(DRUM_R), d_r)
        self.assertEqual(self.get(MIX_L), [f32(d + s) for s, d in zip(s_l, d_l)])
        self.assertEqual(self.get(MIX_R), [f32(d + s) for s, d in zip(s_r, d_r)])

    def test_drums_with_gain_stem_is_pure_and_mix_close(self):
        s_l, d_l = self.fl(), self.fl(0.3)
        self.put(MIX_L, s_l)
        self.put(DRUM_L, d_l)
        self.lib.host_set_stem_ctl(1, 0.25, 1, 1.0)
        self.lib.ua_drums_tap()
        self.assertEqual(self.get(DRUM_L), [f32(d * 0.25) for d in d_l])   # no guitar in it
        for got, s, d in zip(self.get(MIX_L), s_l, d_l):
            self.assertAlmostEqual(got, (s + d) * 0.25, delta=1e-6)

    def test_rhythm_off_leaves_mix_alone_and_stem_silent(self):
        s_l = self.fl()
        self.put(MIX_L, s_l)
        self.put(DRUM_L, self.fl())
        self.lib.host_set_stem_ctl(0, 0.0, 1, 1.0)
        self.lib.ua_drums_tap()
        self.assertEqual(self.get(MIX_L), s_l)
        self.assertEqual(self.get(DRUM_L), [0.0] * 16)
        self.assertEqual(self.lib.host_stem_calls() & 0xffff, 1)

    def test_looper_stem_pre_and_post_and_mix_untouched(self):
        for pos in (0, 1):
            self.lib.host_reset()
            s_l, p = self.fl(), self.fl(0.3)
            self.put(MIX_L, s_l)
            self.put(MIX_R, s_l)
            self.put(LOOP, p)
            self.lib.host_set_stem_ctl(0, 1.0, pos, 1.0)
            self.lib.ua_looper_tap(0)     # Swi step 6
            self.lib.ua_looper_tap(1)     # Swi step 14
            self.assertEqual(self.get(MIX_L), [f32(s + x) for s, x in zip(s_l, p)])
            for got, x in zip(self.get(LOOP), p):
                self.assertAlmostEqual(got, x, delta=1e-7)
            self.assertEqual(self.lib.host_stem_calls() >> 16, 2)

    def test_packet_layout_and_looper_cleared_per_block(self):
        self.lib.usb_audio_set_alt(1)
        exp = []
        for _ in range(8):
            l = [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
            r = [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
            rl = [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
            rr = [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
            di = self.fl()
            self.lib.host_set_sources(I32(*rl), I32(*rr), F32(*([0.0] * 16)), F32(*([0.0] * 16)),
                                      F32(*di), F32(*([0.0] * 16)))
            z = [0.0] * 16
            self.put(MIX_L, z)
            self.put(MIX_R, z)
            d_l, d_r, p = self.fl(0.3), self.fl(0.3), self.fl(0.3)
            self.put(DRUM_L, d_l)
            self.put(DRUM_R, d_r)
            self.put(LOOP, p)
            self.lib.host_set_stem_ctl(1, 1.0, 1, 1.0)
            self.lib.ua_looper_tap(0)
            self.lib.ua_looper_tap(1)
            self.lib.ua_drums_tap()
            self.lib.host_set_block(I32(*l), I32(*r))
            self.lib.ua_tx_pack_tap()
            exp += [(sample(l[i]) | sample(r[i]) << 16, dry(rl[i]) | dry(rr[i]) << 16,
                     fbus(d_l[i]) | fbus(d_r[i]) << 16, fbus(di[i]) | fbus(p[i]) << 16)
                    for i in range(16)]
            self.assertEqual(self.get(LOOP), [0.0] * 16)   # cleared for the next block
        self.lib.host_set_register(TXCSR, 0)
        self.lib.usb_audio_sof_tick_tap()
        buf = (ctypes.c_uint * 256)()
        n = self.lib.host_take_fifo(buf, 256)
        got = [tuple(buf[k:k + WPF]) for k in range(0, n, WPF)]
        self.assertEqual(got, exp[128 - PRIME:128 - PRIME + 45])


FX_L, FX_R = 5, 6


class UsbAudioStemsFxTests(UsbAudioStemsTests):
    """--fx: 1-2 = output words without the pack gain, 3-4 = guitar FX. The stem tests above
    run again on this build (inherited), plus the two changed pairs."""
    @classmethod
    def setUpClass(cls):
        cls.lib = build_host_library("host_harness_tap8_fx.c", "usb_audio_stems_fx_HOST_TEST_ONLY")
        cls.lib.usb_audio_set_alt.argtypes = [ctypes.c_uint]
        cls.lib.host_take_fifo.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        cls.lib.host_set_stem_ctl.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int, ctypes.c_float]
        cls.lib.ua_looper_tap.argtypes = [ctypes.c_int]

    def test_fx_is_the_bus_before_the_post_looper(self):
        for pos in (0, 1):
            self.lib.host_reset()
            s_l, s_r, p = self.fl(), self.fl(), self.fl(0.3)
            self.put(MIX_L, s_l)
            self.put(MIX_R, s_r)
            self.put(LOOP, p)
            self.lib.host_set_stem_ctl(0, 1.0, pos, 1.0)
            self.lib.ua_looper_tap(0)
            self.lib.ua_looper_tap(1)
            if pos == 1:    # Post looper: not in the FX pair
                self.assertEqual(self.get(FX_L), s_l)
                self.assertEqual(self.get(FX_R), s_r)
            else:           # Pre looper plays through the effects (here: added before step 14)
                self.assertEqual(self.get(FX_L), [f32(a + b) for a, b in zip(s_l, p)])

    def test_packet_layout_and_looper_cleared_per_block(self):
        self.lib.usb_audio_set_alt(1)
        exp = []
        for _ in range(8):
            l = [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
            r = [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
            di = self.fl()
            z = [0.0] * 16
            self.lib.host_set_sources(I32(*[0] * 16), I32(*[0] * 16), F32(*z), F32(*z), F32(*di), F32(*z))
            g_l, g_r = self.fl(), self.fl()
            self.put(MIX_L, g_l)
            self.put(MIX_R, g_r)
            d_l, d_r, p = self.fl(0.3), self.fl(0.3), self.fl(0.3)
            self.put(DRUM_L, d_l)
            self.put(DRUM_R, d_r)
            self.put(LOOP, p)
            self.lib.host_set_stem_ctl(1, 1.0, 1, 1.0)
            self.lib.ua_looper_tap(0)
            self.lib.ua_looper_tap(1)
            self.lib.ua_drums_tap()
            self.lib.host_set_block(I32(*l), I32(*r))
            self.lib.ua_tx_pack_tap()
            exp += [(dry(l[i]) | dry(r[i]) << 16, fbus(g_l[i]) | fbus(g_r[i]) << 16,
                     fbus(d_l[i]) | fbus(d_r[i]) << 16, fbus(di[i]) | fbus(p[i]) << 16)
                    for i in range(16)]
            self.assertEqual(self.get(LOOP), [0.0] * 16)
        self.lib.host_set_register(TXCSR, 0)
        self.lib.usb_audio_sof_tick_tap()
        buf = (ctypes.c_uint * 256)()
        n = self.lib.host_take_fifo(buf, 256)
        got = [tuple(buf[k:k + WPF]) for k in range(0, n, WPF)]
        self.assertEqual(got, exp[128 - PRIME:128 - PRIME + 45])


class StemsBuildTests(unittest.TestCase):
    def test_patch_list(self):
        import make_usb_audio_fw as m
        sites = {p[0]: p for p in m.STEM_PATCHES}
        self.assertEqual(sites[0x11818d64][3], 0x11817640)
        self.assertEqual(sites[0x11818bc0][3], 0x11818e60)
        self.assertEqual(sites[0x11818c50][3], 0x11818e60)
        for v in (m.DRUM_VENEER, m.LOOP_VENEER):
            self.assertEqual([sites[v + k][1] for k in (0, 4, 8, 12)], [0, 0, 0, 0])
        self.assertEqual(len({p[0] for p in m.STEM_PATCHES}), len(m.STEM_PATCHES))


if __name__ == "__main__":
    unittest.main()
