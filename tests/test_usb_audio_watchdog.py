"""Host tests for the slot watchdog (make_usb_audio_fw.py --bench --watchdog, UA_WATCHDOG):
a slot over the limit for N blocks in a row gets ua_wd_noop in the live callback table;
a new function from the loader re-arms it; the tripped mask rides in the period word.
The harness uses UA_WD_LIMIT 1000 and UA_WD_TRIPS 4."""
import ctypes
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_usb_audio_proto import build_host_library  # noqa: E402
from test_usb_audio_tap import TXCSR  # noqa: E402
import ua_bench  # noqa: E402

F32 = ctypes.c_float * 16
I32 = ctypes.c_int * 16
LIMIT, TRIPS = 1000, 4
FX = [0x1000 + 0x100 * k for k in range(5)]        # stand-in effect functions per slot


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.lib = build_host_library("host_harness_tap8_watchdog.c", "usb_audio_wd_HOST_TEST_ONLY")
        self.lib.usb_audio_set_alt.argtypes = [ctypes.c_uint]
        self.lib.host_set_stem_ctl.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int, ctypes.c_float]
        self.lib.host_take_fifo.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        self.lib.ua_looper_tap.argtypes = [ctypes.c_int]
        self.lib.host_bench_set.argtypes = [ctypes.c_uint, ctypes.c_int]
        self.lib.ua_slot_enter.restype = ctypes.c_void_p
        self.lib.host_slot_table_set.argtypes = [ctypes.c_int, ctypes.c_void_p]
        self.lib.host_slot_table_get.restype = ctypes.c_void_p
        self.lib.host_slot_table_get.argtypes = [ctypes.c_int]
        self.noop = ctypes.cast(self.lib.ua_wd_noop, ctypes.c_void_p).value
        self.lib.host_reset()
        self.lib.usb_audio_set_alt(1)
        for k in range(5):
            self.lib.host_slot_table_set(k, FX[k])
        self.t = 0

    def block(self, slots):
        z = [0.0] * 16
        self.lib.host_set_sources(I32(*[0] * 16), I32(*[0] * 16), F32(*z), F32(*z), F32(*z), F32(*z))
        self.lib.host_set_stem_ctl(0, 1.0, 1, 1.0)
        self.lib.host_bench_set(self.t & 0xffffffff, 0)
        self.lib.ua_looper_tap(0)
        t = self.t + 100
        for k in range(5):
            self.lib.host_bench_set(t & 0xffffffff, k)
            self.lib.ua_slot_enter()
            t += slots[k]
        self.lib.host_bench_set(t & 0xffffffff, 5)
        self.lib.ua_looper_tap(1)
        self.lib.ua_drums_tap()
        self.lib.host_bench_set((t + 500) & 0xffffffff, 5)
        self.lib.host_set_block(I32(*[0] * 16), I32(*[0] * 16))
        self.lib.ua_tx_pack_tap()
        self.t += 50000

    def table(self):
        return [self.lib.host_slot_table_get(k) for k in range(5)]

    def frames(self):
        self.lib.host_set_register(TXCSR, 0)
        self.lib.usb_audio_sof_tick_tap()
        buf = (ctypes.c_uint * 256)()
        n = self.lib.host_take_fifo(buf, 256)
        return list(ua_bench.frames([w >> 16 for w in buf[3:n:4]]))

    def test_healthy_slots_are_never_touched(self):
        for _ in range(20):
            self.block([LIMIT, 10, 10, 10, 10])          # at the limit is not over it
        self.assertEqual(self.table(), FX)

    def test_trips_after_n_in_a_row_only(self):
        heavy = [10, LIMIT + 1, 10, 10, 10]
        for _ in range(TRIPS - 1):
            self.block(heavy)
        self.block([10] * 5)                             # one good block resets the count
        for _ in range(TRIPS - 1):
            self.block(heavy)
        self.assertEqual(self.table(), FX)
        self.block(heavy)
        self.assertEqual(self.table(), [FX[0], self.noop, FX[2], FX[3], FX[4]])

    def test_tripped_mask_reported_and_period_kept(self):
        for _ in range(TRIPS + 8):                       # the ring needs ~8 blocks to prime
            self.block([10, 10, 10, LIMIT * 5, 10])
        fr = self.frames()
        self.assertTrue(fr)
        self.assertEqual(fr[-1]["tripped"], 1 << 3)
        self.assertEqual(fr[-1]["period"], 50000)

    def test_first_block_of_a_new_function_is_not_judged(self):
        for _ in range(TRIPS):                           # block 1 only records the function
            self.block([10, 10, LIMIT * 2, 10, 10])
        self.assertEqual(self.table(), FX)
        self.block([10, 10, LIMIT * 2, 10, 10])
        self.assertEqual(self.table()[2], self.noop)

    def test_loader_replacement_rearms_the_slot(self):
        for _ in range(TRIPS + 1):
            self.block([10, 10, LIMIT * 2, 10, 10])
        self.assertEqual(self.table()[2], self.noop)
        self.lib.host_slot_table_set(2, FX[2])          # same effect reinstalled
        for _ in range(8):
            self.block([10, 10, 10, 10, 10])
        fr = self.frames()
        self.assertEqual(fr[-1]["tripped"], 0)
        for _ in range(TRIPS + 1):
            self.block([10, 10, LIMIT * 2, 10, 10])
        self.assertEqual(self.table()[2], self.noop)     # and it can trip again

    def test_slot_that_did_not_run_is_not_judged(self):
        for b in range(TRIPS * 3):
            z = [0.0] * 16
            self.lib.host_set_sources(I32(*[0] * 16), I32(*[0] * 16), F32(*z), F32(*z), F32(*z), F32(*z))
            self.lib.host_bench_set(self.t & 0xffffffff, 0)
            self.lib.ua_looper_tap(0)                    # tuner mute: the slot loop is skipped
            self.lib.host_bench_set((self.t + 9000) & 0xffffffff, 5)
            self.lib.ua_looper_tap(1)
            self.lib.ua_drums_tap()
            self.lib.host_bench_set((self.t + 9500) & 0xffffffff, 5)
            self.lib.host_set_block(I32(*[0] * 16), I32(*[0] * 16))
            self.lib.ua_tx_pack_tap()
            self.t += 50000
        self.assertEqual(self.table(), FX)


if __name__ == "__main__":
    unittest.main()
