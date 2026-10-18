"""Host tests for the CPU bench tap (make_usb_audio_fw.py --bench): one 16-word timing frame
per audio block on USB channel 8 (high half of ring word 3), decoded by tools/ua_bench.py."""
import ctypes
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_usb_audio_proto import build_host_library  # noqa: E402
from test_usb_audio_tap import TXCSR, PRIME  # noqa: E402
import ua_bench  # noqa: E402

F32 = ctypes.c_float * 16
I32 = ctypes.c_int * 16


class BenchFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = build_host_library("host_harness_tap8_bench.c", "usb_audio_bench_HOST_TEST_ONLY")
        cls.lib.usb_audio_set_alt.argtypes = [ctypes.c_uint]
        cls.lib.host_take_fifo.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        cls.lib.host_set_stem_ctl.argtypes = [ctypes.c_int, ctypes.c_float, ctypes.c_int, ctypes.c_float]
        cls.lib.ua_looper_tap.argtypes = [ctypes.c_int]
        cls.lib.host_bench_set.argtypes = [ctypes.c_uint, ctypes.c_int]
        cls.lib.ua_slot_enter.restype = ctypes.c_void_p

    def setUp(self):
        self.lib.host_reset()

    def block(self, t0, slots, run_slots=True):
        """One Swi block: Pre looper at t0, slot k starts at t0 + sum(slots[:k]) + 100,
        Post looper after slot 4, TX 500 later. Returns the expected values."""
        z = [0.0] * 16
        self.lib.host_set_sources(I32(*[0] * 16), I32(*[0] * 16), F32(*z), F32(*z), F32(*z), F32(*z))
        self.lib.host_set_stem_ctl(0, 1.0, 1, 1.0)
        self.lib.host_bench_set(t0 & 0xffffffff, 0)
        self.lib.ua_looper_tap(0)
        t = t0 + 100
        for k in range(5):
            if run_slots:
                self.lib.host_bench_set(t & 0xffffffff, k)
                self.assertEqual(self.lib.ua_slot_enter(), 0x11f03b48)
            t += slots[k]
        self.lib.host_bench_set(t & 0xffffffff, 5)
        self.lib.ua_looper_tap(1)
        self.lib.ua_drums_tap()
        self.lib.host_bench_set((t + 500) & 0xffffffff, 5)
        self.lib.host_set_block(I32(*[0] * 16), I32(*[0] * 16))
        self.lib.ua_tx_pack_tap()
        return t + 500 - t0

    def capture(self):
        self.lib.host_set_register(TXCSR, 0)
        self.lib.usb_audio_sof_tick_tap()
        buf = (ctypes.c_uint * 256)()
        n = self.lib.host_take_fifo(buf, 256)
        return [w >> 16 for w in buf[3:n:4]]            # channel 8 = high half of word 3

    def test_slot_index_out_of_range_ignored_and_ctx_returned(self):
        self.lib.host_bench_set(5, 7)
        self.assertEqual(self.lib.ua_slot_enter(), 0x11f03b48)

    def test_frames_decode_to_slot_costs_busy_and_period(self):
        self.lib.usb_audio_set_alt(1)
        period = 50600
        slots = [1200, 70000 - 3, 300, 0, 4200]
        t0 = 0xfff00000                                  # crosses the 32-bit wrap
        busy = []
        for b in range(8):
            busy.append(self.block(t0 + b * period, slots))
        words = self.capture()
        frames = list(ua_bench.frames(words))
        self.assertGreaterEqual(len(frames), 2)
        for f in frames[1:]:
            self.assertEqual(f["mask"], 0x1f)
            self.assertEqual(f["slots"], slots)
            self.assertEqual(f["busy"], busy[0])
            self.assertEqual(f["period"], period)
        seqs = [f["seq"] for f in frames]
        self.assertEqual(seqs, list(range(seqs[0], seqs[0] + len(seqs))))

    def test_skipped_slot_loop_gives_empty_mask(self):
        self.lib.usb_audio_set_alt(1)
        for b in range(8):
            self.block(1000 + b * 50000, [1, 2, 3, 4, 5], run_slots=(b % 2 == 0))
        masks = [f["mask"] for f in ua_bench.frames(self.capture())]
        self.assertIn(0, masks)
        self.assertIn(0x1f, masks)


class BenchPatchTests(unittest.TestCase):
    def test_slot_entries_of_all_factory_patches_round_trip(self):
        import g1presets
        res2 = ROOT / "build/fw/res2_45056.bin"
        if not res2.exists():
            self.skipTest("factory presets not present")
        n = 0
        for r in g1presets.records(res2.read_bytes()):
            raw = r["raw"]
            ids = struct.unpack_from("<5I", raw, 0x24)
            for k in range(5):
                e = raw[r["edtb"] + 24 * k:r["edtb"] + 24 * k + 24]
                if ids[k] == 0:
                    continue
                on, eid, knobs = ua_bench.decode_entry(e)
                self.assertEqual(eid, ids[k])
                self.assertEqual(ua_bench.slot_entry(eid, knobs, bool(on)), e)
                n += 1
        self.assertGreater(n, 100)

    def test_make_patch_places_ids_and_entries(self):
        if not (ROOT / "backup/2026-10-04/patches/PATCH_030.ZPTC").exists():
            self.skipTest("backup template not present")
        data = ua_bench.make_patch([(0x01000f86, [50, 50]), None, (0x06000f87, [30, 70, 60, 0])])
        self.assertEqual(ua_bench.ids_of(data), [0x01000f86, 0, 0x06000f87, 0, 0])
        e = data.find(b"EDTB") + 8
        self.assertEqual(ua_bench.decode_entry(data[e:e + 24]), (1, 0x01000f86, [50, 50] + [0] * 10))
        self.assertEqual(data[e + 24:e + 48], ua_bench.EMPTY_SLOT)
        self.assertEqual(data[data.find(b"PTCF") + 0x1A:][:10], b"CF BENCH  ")


class BenchBuildTests(unittest.TestCase):
    def test_packager_accepts_bench_layer_and_refuses_a_bad_slot_veneer(self):
        import make_controller_fw as ctl
        import make_usb_audio_fw as ua
        import make_fs_restore_updater as packager
        res1 = ROOT / "build/fw/res1_493412.bin"
        if not res1.exists():
            self.skipTest("stock firmware not present")
        stock = res1.read_bytes()
        with tempfile.TemporaryDirectory() as d:
            menu = Path(d) / "menu.bin"
            ctl.build(res1, menu, res1, ui=True, usb_product="Comet Flower ZG1X4 MIDI",
                      usb_audio_name="Comet Flower Audio Bridge")
            both, plan, _ = ua.build(menu, Path(d) / "bench.bin", bench=True)
            self.assertEqual(packager.strip_usb_audio(stock, both), menu.read_bytes())
            p = [q for q in plan if q[0] == ua.SLOT_VENEER + 4][0]
            bad = bytearray(both)
            struct.pack_into("<I", bad, p[1], ua.mvk_set(p[3], 0xc012))   # aimed outside
            with self.assertRaises(ValueError):
                packager.strip_usb_audio(stock, bytes(bad))
            bad = bytearray(both)
            struct.pack_into("<I", bad, p[1], p[3] ^ 4)                    # outside the field
            with self.assertRaises(ValueError):
                packager.strip_usb_audio(stock, bytes(bad))


if __name__ == "__main__":
    unittest.main()
