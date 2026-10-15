"""Host tests for the real-audio tap (firmware/usb_audio_proto/usb_audio_tap.c).

Offline only: the C is compiled for the host with in-memory MMIO and stub
TX buffers (host_harness_tap.c). Nothing touches the pedal.
"""
import ctypes
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from test_usb_audio_proto import build_host_library  # noqa: E402

TXCSR, FIFO = 0x01e00512, 0x01e00424
GAIN = 0x4534fd79
FS, BLOCK = 44100.0, 16
PRIME = 128
I32 = ctypes.c_int * 16


def smpy32(a, b):
    if a == b == -2**31:
        return 2**31 - 1
    return (a * b) >> 31


def sshl(a, n):
    return max(-2**31, min(2**31 - 1, a << n))


def sample(x):
    """Stock pack 11818b00..b18 math, then the high half."""
    return (sshl(smpy32(x, GAIN), 2) >> 16) & 0xffff


class UsbAudioTapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = build_host_library("host_harness_tap.c", "usb_audio_tap_HOST_TEST_ONLY")
        cls.lib.usb_audio_set_alt.argtypes = [ctypes.c_uint]
        cls.lib.host_tap_sample.argtypes = [ctypes.c_int]
        cls.lib.host_take_fifo.argtypes = [ctypes.c_void_p, ctypes.c_uint]

    def setUp(self):
        self.lib.host_reset()
        self.rng = random.Random(1)

    def state(self, i):
        return self.lib.host_tap_state(i)

    def block(self, l, r):
        self.lib.host_set_block(I32(*l), I32(*r))
        self.lib.ua_tx_pack_tap()

    def random_block(self):
        l = [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
        r = [self.rng.randrange(-2**31, 2**31) for _ in range(16)]
        return l, r

    def sof(self):
        """One SOF with the host having taken the previous packet."""
        self.lib.host_set_register(TXCSR, 0)
        self.lib.usb_audio_sof_tick_tap()
        buf = (ctypes.c_uint * 64)()
        n = self.lib.host_take_fifo(buf, 64)
        return list(buf[:n])

    def test_sample_conversion_matches_stock_math(self):
        values = [0, 1, -1, 2**31 - 1, -2**31, 0x10000, -0x10000, 0x3b2f0000,
                  -0x3b2f0000, 0x3b300000, -0x3b300000]
        values += [self.rng.randrange(-2**31, 2**31) for _ in range(2000)]
        for x in values:
            self.assertEqual(self.lib.host_tap_sample(x), sample(x), hex(x))

    def test_pack_always_runs_and_block_needs_stream(self):
        l, r = self.random_block()
        self.block(l, r)
        self.assertEqual(self.lib.host_pack_count(), 1)
        self.assertEqual(self.state(0), 0)          # stream off: nothing stored
        self.lib.usb_audio_set_alt(1)
        self.block(l, r)
        self.assertEqual(self.lib.host_pack_count(), 2)
        self.assertEqual((self.state(0), self.state(3)), (16, 1))

    def test_inactive_sof_writes_nothing(self):
        self.assertEqual(self.sof(), [])
        self.assertEqual(self.lib.host_get_register(TXCSR), 0)

    def test_busy_endpoint_skips_without_fifo_writes(self):
        self.lib.usb_audio_set_alt(1)
        self.lib.host_set_register(TXCSR, 0x6001)
        self.lib.usb_audio_sof_tick_tap()
        buf = (ctypes.c_uint * 64)()
        self.assertEqual(self.lib.host_take_fifo(buf, 64), 0)
        self.assertEqual((self.state(7), self.state(8)), (1, 0))

    def test_priming_sends_silence_then_newest_frames_in_order(self):
        self.lib.usb_audio_set_alt(1)
        expected = []
        for _ in range(10):                          # 160 frames, > PRIME
            l, r = self.random_block()
            expected += [sample(a) | sample(b) << 16 for a, b in zip(l, r)]
        # Interleave: two SOFs while only 2 blocks exist -> silence.
        self.lib.host_reset()
        self.lib.usb_audio_set_alt(1)
        self.rng = random.Random(1)
        for _ in range(2):
            self.block(*self.random_block())
        first = self.sof()
        self.assertEqual(first, [0] * 45)
        self.assertEqual(self.state(2), 0)
        for _ in range(8):
            self.block(*self.random_block())
        packet = self.sof()
        self.assertEqual(self.state(2), 1)
        # Primed on the newest PRIME frames, fill 128 > target -> 45 frames.
        self.assertEqual(packet, expected[160 - PRIME:160 - PRIME + 45])
        self.assertEqual(self.lib.host_get_register(TXCSR), 0x6001)

    def test_left_low_half_right_high_half(self):
        self.lib.usb_audio_set_alt(1)
        l = [0x10000000 + k for k in range(16)]
        r = [-0x10000000] * 16
        for _ in range(8):
            self.block(l, r)
        word = self.sof()[0]
        self.assertEqual(word & 0xffff, sample(l[0]))
        self.assertEqual(word >> 16, sample(r[0]))

    def test_underrun_pads_zeros_counts_and_reprimes(self):
        self.lib.usb_audio_set_alt(1)
        for _ in range(8):
            self.block(*self.random_block())
        sizes = [len(self.sof()) for _ in range(4)]  # 128 frames: 45, 44, 39 + pad
        self.assertTrue(all(s in (44, 45) for s in sizes))
        self.assertEqual(self.state(5), 1)
        self.assertEqual(self.state(2), 0)
        self.assertEqual(self.state(1), self.state(0))  # all frames consumed once

    def test_overrun_drops_whole_blocks_and_bounds_fill(self):
        self.lib.usb_audio_set_alt(1)
        for _ in range(40):
            self.block(*self.random_block())
            self.assertLessEqual(self.state(0) - self.state(1), 256)
        self.assertEqual(self.state(0) % 16, 0)
        self.assertEqual(self.state(0), 256)
        self.assertEqual(self.state(4), 40 - 16)

    def test_restart_drops_stale_frames(self):
        self.lib.usb_audio_set_alt(1)
        for _ in range(16):
            self.block(*self.random_block())
        self.lib.usb_audio_set_alt(0)
        self.lib.usb_audio_sof_tick_tap()            # disabled: un-primes
        self.lib.usb_audio_set_alt(1)
        fresh = []
        for _ in range(8):
            l, r = self.random_block()
            fresh += [sample(a) | sample(b) << 16 for a, b in zip(l, r)]
            self.block(l, r)
        # The disabled SOF discarded the old ring: only fresh frames play.
        self.assertEqual(self.state(4), 0)
        self.assertEqual(self.sof(), fresh[:45])
        self.assertEqual(self.state(2), 1)

    def run_clocks(self, ppm, seconds=10):
        """Blocks at the codec rate (with drift) against 1 ms SOFs."""
        self.lib.usb_audio_set_alt(1)
        block_period = BLOCK / (FS * (1 + ppm * 1e-6))
        produced, received = [], []
        t_block, t_sof = 0.0, 0.0
        primed_at = None
        while t_sof < seconds:
            if t_block <= t_sof:
                l, r = self.random_block()
                produced += [sample(a) | sample(b) << 16 for a, b in zip(l, r)]
                self.block(l, r)
                t_block += block_period
            else:
                packet = self.sof()
                self.assertIn(len(packet), (44, 45))
                if self.state(2):
                    if primed_at is None:
                        primed_at = self.state(1) - len(packet)
                    received += packet
                t_sof += 1e-3
        return produced, received, primed_at

    def check_drift(self, ppm):
        produced, received, start = self.run_clocks(ppm)
        self.assertEqual(self.state(5), 0, "underruns")
        self.assertEqual(self.state(4), 0, "overruns")
        self.assertEqual(received, produced[start:start + len(received)])
        backlog = len(produced) - start - len(received)
        self.assertLess(backlog, 256)

    def test_nominal_clock_continuous(self):
        self.check_drift(0)

    def test_slow_codec_clock_continuous(self):
        self.check_drift(-1000)

    def test_fast_codec_clock_continuous(self):
        self.check_drift(+10000)


ROOT = Path(__file__).resolve().parents[1]
RES1 = ROOT / "build" / "fw" / "res1_493412.bin"
MAIN_DIS = ROOT / "build" / "fw" / "map" / "main.dis"


@unittest.skipUnless(RES1.exists(), "stock res1 not available")
class UsbAudioTapImage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import struct
        import tempfile
        import make_controller_fw as ctl
        import make_usb_audio_fw as ua
        if not ctl.CGT.exists():
            raise unittest.SkipTest("TI CGT not available")
        cls.ua, cls.struct = ua, struct
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data, cls.plan, cls.syms = ua.build(RES1, Path(cls.tmp.name) / "tap.bin", tap=True)
        cls.stock = RES1.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def word(self, data, vma):
        return self.struct.unpack_from("<I", data, self.ua.vma_offset(self.stock, vma))[0]

    def test_only_planned_words_change(self):
        close = len(self.stock) - 8
        changed = {i for i in range(close) if self.data[i] != self.stock[i]}
        allowed = {off + k for _, off, *_ in self.plan for k in range(4)}
        self.assertTrue(changed <= allowed)
        self.assertEqual(len(self.plan), 16)

    def test_tx_pack_call_goes_to_veneer_and_keeps_bits(self):
        old, new = self.word(self.stock, 0x11818c64), self.word(self.data, 0x11818c64)
        ctl = sys.modules["make_controller_fw"]
        self.assertEqual(ctl.callp_target(0x11818c64, old), 0x11818aa0)
        self.assertEqual(ctl.callp_target(0x11818c64, new), self.ua.TAP_VENEER)
        keep = ~(0x1fffff << 7) & 0xffffffff
        self.assertEqual(new & keep, old & keep)
        self.assertEqual(new & 1, 0)

    def test_veneer_is_stock_shape_and_reaches_tap(self):
        v = self.ua.TAP_VENEER
        words = [self.word(self.data, v + 4 * k) for k in range(4)]
        self.assertEqual([self.word(self.stock, v + 4 * k) for k in range(4)], [0] * 4)
        stock = [self.word(self.stock, 0x11818ea0 + 4 * k) for k in range(4)]
        keep = ~(0xffff << 7) & 0xffffffff
        self.assertEqual([w & keep for w in words[:2]], [w & keep for w in stock[:2]])
        self.assertEqual(words[2:], stock[2:])
        lo, hi = (words[0] >> 7) & 0xffff, (words[1] >> 7) & 0xffff
        self.assertEqual(hi << 16 | lo, self.syms["ua_tx_pack_tap"])
        self.assertTrue(all(w & 1 == 0 for w in words))   # four serial packets

    def test_sof_hook_targets_tap_tick(self):
        lo = (self.word(self.data, 0xc016f770) >> 7) & 0xffff
        hi = (self.word(self.data, 0xc016f774) >> 7) & 0xffff
        self.assertEqual(hi << 16 | lo, self.syms["usb_audio_sof_tick_tap"])

    @unittest.skipUnless(MAIN_DIS.exists(), "main.dis not available")
    def test_veneer_padding_is_dead_after_swi_epilogue(self):
        text = MAIN_DIS.read_text(errors="replace")
        self.assertRegex(text, r"11818c7a\s+01ef\s+\|\|\s+BNOP.S2\s+B3,0")
        self.assertRegex(text, r"11818c84\s+00006000\s+NOP\s+4")
        for k in range(8):   # no stock branch or call lands in 11818c88..c9f
            self.assertNotRegex(text, r"(CALLP|B|BNOP)\S*\s+0x11818c%02x" % (0x88 + 4 * k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
