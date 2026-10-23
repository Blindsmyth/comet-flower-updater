"""Host tests for the CF Probe watch stream (UA_PROBE): channel 7 carries six watched
words per block round-robin over the list, decoded by tools/cf_probe.py; the list
accepts only word-aligned RAM addresses. The harness's fake memory returns
address ^ salt for every read."""
import ctypes
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_usb_audio_proto import build_host_library  # noqa: E402
from test_usb_audio_tap import TXCSR  # noqa: E402
import cf_probe  # noqa: E402
import ua_bench  # noqa: E402

F32 = ctypes.c_float * 16
I32 = ctypes.c_int * 16
SALT = 0x5A5A0000


class WatchStreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = build_host_library("host_harness_tap8_probe.c", "usb_audio_probe_HOST_TEST_ONLY")
        cls.lib.usb_audio_set_alt.argtypes = [ctypes.c_uint]
        cls.lib.host_set_stem_ctl.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int, ctypes.c_float]
        cls.lib.host_take_fifo.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        cls.lib.ua_looper_tap.argtypes = [ctypes.c_int]
        cls.lib.host_bench_set.argtypes = [ctypes.c_uint, ctypes.c_int]
        cls.lib.host_watch_salt_set.argtypes = [ctypes.c_uint]
        cls.lib.ua_watch_set.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        cls.lib.ua_watch_set.restype = ctypes.c_uint
        cls.lib.ua_watch_ok.argtypes = [ctypes.c_uint]
        cls.lib.ua_watch_ok.restype = ctypes.c_uint

    def setUp(self):
        self.lib.host_reset()
        self.lib.usb_audio_set_alt(1)
        self.lib.host_watch_salt_set(SALT)
        self.t = 0
        addrs = [a for a, _ in cf_probe.DEFAULT_LIST]
        self.set_list(addrs)

    def set_list(self, addrs):
        arr = (ctypes.c_uint * len(addrs))(*addrs)
        return self.lib.ua_watch_set(arr, len(addrs))

    def block(self):
        z = [0.0] * 16
        self.lib.host_set_sources(I32(*[0] * 16), I32(*[0] * 16), F32(*z), F32(*z), F32(*z), F32(*z))
        self.lib.host_set_stem_ctl(0, 1.0, 1, 1.0)
        self.lib.host_bench_set(self.t & 0xffffffff, 0)
        self.lib.ua_looper_tap(0)
        for k in range(5):
            self.lib.host_bench_set((self.t + 100 + 50 * k) & 0xffffffff, k)
            self.lib.ua_slot_enter()
        self.lib.host_bench_set((self.t + 400) & 0xffffffff, 5)
        self.lib.ua_looper_tap(1)
        self.lib.ua_drums_tap()
        self.lib.host_bench_set((self.t + 900) & 0xffffffff, 5)
        self.lib.host_set_block(I32(*[0] * 16), I32(*[0] * 16))
        self.lib.ua_tx_pack_tap()
        self.t += 50000

    def capture(self, blocks):
        """Run blocks, sending one USB packet (about 2.8 blocks of frames) after each."""
        words = []
        for _ in range(blocks):
            self.block()
            self.lib.host_set_register(TXCSR, 0)
            self.lib.usb_audio_sof_tick_tap()
            buf = (ctypes.c_uint * 512)()
            n = self.lib.host_take_fifo(buf, 512)
            words += buf[3:n:4]
        return [w & 0xffff for w in words], [w >> 16 for w in words]

    def test_default_list_round_robin_and_values(self):
        ch7, _ = self.capture(16)
        fr = list(cf_probe.frames(ch7))
        self.assertGreaterEqual(len(fr), 6)
        addrs = [a for a, _ in cf_probe.DEFAULT_LIST]
        for f in fr:
            self.assertEqual(f["n"], 32)
            for k, v in enumerate(f["values"]):
                self.assertEqual(v, addrs[(f["first"] + k) % 32] ^ SALT)
        firsts = [f["first"] for f in fr]
        for a, b in zip(firsts, firsts[1:]):
            self.assertEqual(b, (a + 6) % 32)
        seqs = [f["seq"] for f in fr]
        for a, b in zip(seqs, seqs[1:]):
            self.assertEqual(b, (a + 1) & 0xff)

    def test_bench_frames_still_on_channel_8(self):
        _, ch8 = self.capture(16)
        bf = list(ua_bench.frames(ch8))
        self.assertTrue(bf)
        self.assertEqual(bf[-1]["slots"][:4], [50, 50, 50, 50])

    def test_list_rejects_peripherals_and_unaligned(self):
        ok = [0x11800000, 0x1183fffc, 0x11f00000, 0x11f07ffc, 0xc0000000, 0xc07ffffc]
        bad = [0x01c00000, 0x01e00400, 0x11f03c59, 0x11840000, 0x11f08000, 0xc0800000, 0x0, 0xffffffff]
        for a in ok:
            self.assertEqual(self.lib.ua_watch_ok(a), 1, hex(a))
        for a in bad:
            self.assertEqual(self.lib.ua_watch_ok(a), 0, hex(a))
        self.assertEqual(self.set_list(ok + bad), len(ok))

    def test_short_list_and_empty_list(self):
        self.assertEqual(self.set_list([0x11f03d1c, 0x11812f78]), 2)
        ch7, _ = self.capture(12)
        fr = list(cf_probe.frames(ch7))
        self.assertTrue(fr)
        for f in fr:
            self.assertEqual(f["n"], 2)
            self.assertEqual(f["values"][0], [0x11f03d1c, 0x11812f78][f["first"]] ^ SALT)
        self.assertEqual(self.set_list([]), 0)
        ch7, _ = self.capture(24)
        fr = list(cf_probe.frames(ch7))
        self.assertTrue(fr)
        self.assertEqual(fr[-1]["n"], 0)
        self.assertEqual(fr[-1]["values"], [0] * 6)

    def test_corrupted_frame_is_skipped(self):
        ch7, _ = self.capture(16)
        good = len(list(cf_probe.frames(ch7)))
        i = ch7.index(cf_probe.SYNC)
        ch7[i + 5] ^= 1
        self.assertEqual(len(list(cf_probe.frames(ch7))), good - 1)


if __name__ == "__main__":
    unittest.main()
