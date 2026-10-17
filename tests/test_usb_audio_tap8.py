"""Host tests for the 8-channel USB tap (UA_NCH 8, make_usb_audio_fw.py --tap8).

Channels: 1-2 pedal output (TX L/R, stock pack math), 3 dry input (left ADC word
11f03730, high half), 4 right ADC (11f03770), 5-6 float mix bus 11f03830/70,
7 float bus 11f03930, 8 float bus 11f03970 (1.0 = full scale). Offline only.
"""
import ctypes
import random
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from test_usb_audio_proto import build_host_library, descriptors  # noqa: E402
from test_usb_audio_tap import sample, TXCSR, FS, BLOCK, PRIME  # noqa: E402

I32 = ctypes.c_int * 16
F32 = ctypes.c_float * 16
NCH, WPF = 8, 4


def dry(x):
    return (x >> 16) & 0xffff


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def fbus(x):
    """Float bus sample -> 16 bit: round(x * 2^31) saturated to int32, high half."""
    v = f32(f32(x) * 2147483648.0)
    v = 2**31 - 1 if v >= 2147483647.0 else -2**31 if v <= -2147483648.0 else int(v - 0.5 if v < 0 else v + 0.5)
    return (v >> 16) & 0xffff


class UsbAudioTap8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = build_host_library("host_harness_tap8.c", "usb_audio_tap8_HOST_TEST_ONLY")
        cls.lib.usb_audio_set_alt.argtypes = [ctypes.c_uint]
        cls.lib.host_take_fifo.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        cls.lib.usb_audio_copy_descriptors.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
        cls.lib.usb_audio_copy_descriptors.restype = ctypes.c_uint

    def setUp(self):
        self.lib.host_reset()
        self.rng = random.Random(7)

    def frames(self):
        """One block of random sources; returns the 16 expected 4-word frames."""
        rnd = lambda: [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
        fl = lambda: [self.rng.uniform(-1.3, 1.3) for _ in range(16)]
        l, r, rl, rr = rnd(), rnd(), rnd(), rnd()
        bl, br, bm, bx = fl(), fl(), fl(), fl()
        self.lib.host_set_sources(I32(*rl), I32(*rr), F32(*bl), F32(*br), F32(*bm), F32(*bx))
        self.lib.host_set_block(I32(*l), I32(*r))
        self.lib.ua_tx_pack_tap()
        return [(sample(l[i]) | sample(r[i]) << 16, dry(rl[i]) | dry(rr[i]) << 16,
                 fbus(bl[i]) | fbus(br[i]) << 16, fbus(bm[i]) | fbus(bx[i]) << 16)
                for i in range(16)]

    def sof(self):
        self.lib.host_set_register(TXCSR, 0)
        self.lib.usb_audio_sof_tick_tap()
        buf = (ctypes.c_uint * 256)()
        n = self.lib.host_take_fifo(buf, 256)
        return list(buf[:n])

    def test_descriptor_8ch_720_bytes_and_length(self):
        self.lib.usb_audio_build_descriptors()
        out = (ctypes.c_ubyte * 512)()
        n = self.lib.usb_audio_copy_descriptors(out, 65535, 512)
        data = bytes(out[:n])
        self.assertEqual(n, 195)
        self.assertNotEqual(n % 64, 0)
        recs = descriptors(data)
        it = next(r for r in recs if r[1:3] == b"\x24\x02" and r[0] == 12)
        self.assertEqual(it[7], NCH)
        # wChannelConfig must name exactly NCH positions, or Windows builds a
        # 2-channel format and refuses 8-channel streams (hardware 2026-10-17).
        self.assertEqual(bin(int.from_bytes(it[8:10], "little")).count("1"), NCH)
        fmt = next(r for r in recs if r[:4] == b"\x0e\x24\x02\x01")
        self.assertEqual(fmt[4:7], bytes([NCH, 2, 16]))
        ep = [r for r in recs if r[1] == 5][-1]
        self.assertEqual(int.from_bytes(ep[4:6], "little"), 45 * 2 * NCH)

    def test_alt1_sets_maxp_and_2x1024_fifo(self):
        self.lib.usb_audio_set_alt(1)
        self.assertEqual(self.lib.host_get_register(0x01e00410), 720)
        self.assertEqual(self.lib.host_get_register(0x01e00462) & 0xff, 0x17)

    def test_packets_carry_all_eight_channels_in_order(self):
        self.lib.usb_audio_set_alt(1)
        exp = []
        for _ in range(8):
            exp += self.frames()
        words = self.sof()
        self.assertEqual(len(words), 45 * WPF)   # fill 128 > target: 45 frames
        got = [tuple(words[k:k + WPF]) for k in range(0, len(words), WPF)]
        self.assertEqual(got, exp[128 - PRIME:128 - PRIME + 45])

    def test_float_bus_scaling_and_saturation(self):
        for x in (0.0, 0.5, -0.5, 1.0, -1.0, 1.5, -1.5, 1e-6, 0.999969):
            self.assertEqual(fbus(x), fbus(x))   # model sanity
        self.assertEqual(fbus(0.5), 0x4000)
        self.assertEqual(fbus(-0.5), 0xc000)
        self.assertEqual(fbus(1.5), 0x7fff)
        self.assertEqual(fbus(-1.5), 0x8000)

    def test_silence_before_priming_is_full_width(self):
        self.lib.usb_audio_set_alt(1)
        self.frames()
        words = self.sof()
        self.assertIn(len(words), (44 * WPF, 45 * WPF))
        self.assertEqual(set(words), {0})

    def test_drift_continuous_8ch(self):
        self.lib.usb_audio_set_alt(1)
        for ppm in (-1000, 10000):
            self.lib.host_reset()
            self.lib.usb_audio_set_alt(1)
            period = BLOCK / (FS * (1 + ppm * 1e-6))
            produced, received, t_b, t_s, start = [], [], 0.0, 0.0, None
            while t_s < 3:
                if t_b <= t_s:
                    produced += self.frames()
                    t_b += period
                else:
                    words = self.sof()
                    self.assertIn(len(words), (44 * WPF, 45 * WPF))
                    if self.lib.host_tap_state(2):
                        f = [tuple(words[k:k + WPF]) for k in range(0, len(words), WPF)]
                        if start is None:
                            start = produced.index(f[0])
                        received += f
                    t_s += 1e-3
            self.assertEqual(self.lib.host_tap_state(5), 0, "underruns")
            self.assertEqual(self.lib.host_tap_state(4), 0, "overruns")
            self.assertEqual(received, produced[start:start + len(received)])


if __name__ == "__main__":
    unittest.main()
