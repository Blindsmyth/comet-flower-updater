"""Diagnostic pattern tap (make_usb_audio_fw.py --tap-pattern) and its PC analyser
(tools/ua_capture.py). Offline only: the C runs on the host (host_harness_tap_pattern.c).
"""
import ctypes
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from test_usb_audio_proto import build_host_library  # noqa: E402
import ua_capture  # noqa: E402

TXCSR = 0x01e00512
I32 = ctypes.c_int * 16


def pattern(start, n):
    """Frames start..start+n-1 as the firmware sends them: 16-bit counter, sine by full count."""
    c = np.arange(start, start + n, dtype=np.int64)
    return np.stack([(c % 65536).astype(np.uint16).view(np.int16), ua_capture.SINE[c % 44]], axis=1)


def words_to_frames(words):
    w = np.array(words, dtype=np.uint32)
    return np.stack([(w & 0xffff).astype(np.uint16).view(np.int16),
                     (w >> 16).astype(np.uint16).view(np.int16)], axis=1)


class AnalyserTests(unittest.TestCase):
    def kinds(self, data):
        lines, events = ua_capture.analyse_pattern(data)
        return lines, [(k, s) for _, k, s in events]

    def test_clean_stream_has_no_events_and_wraps(self):
        data = pattern(65000, 3000)                       # crosses the 16-bit wrap
        self.assertTrue(ua_capture.is_pattern(data))
        lines, ev = self.kinds(data)
        self.assertEqual(ev, [])
        self.assertIn("in-order valid frames: 3000 (100.000 %)", lines)

    def test_take_starting_after_earlier_wraps(self):
        data = pattern(7 * 65536 + 123, 5000)              # pedal streamed for a while first
        self.assertTrue(ua_capture.is_pattern(data))
        self.assertEqual(self.kinds(data)[1], [])

    def test_in_band_diag_frames_are_decoded(self):
        data = pattern(1000, 44 * 64)
        for p in range(64):                               # one diag frame per 44-frame packet
            tag, val = p % 8, (p // 8 if p % 8 == 0 else 5 if p % 8 == 4 else 3)
            data[p * 44, 1] = np.uint16(tag << 13 | val).view(np.int16)
        lines, ev = self.kinds(data)
        self.assertEqual(ev, [])
        text = "\n".join(lines)
        self.assertIn("pedal diag: 64 packet-start frames", text)
        self.assertIn("packets loaded by the pedal 56, received 56, lost on the way 0", text)
        self.assertIn("ring fill at SOF: min 5, median 5, max 5", text)

    def test_variant_loss_report(self):
        data = pattern(0, 44 * 160)
        for p in range(160):
            tag, var = p % 8, p // 80                    # variant 0 then 1
            val = {0: p // 8, 3: var << 11}.get(tag, 0)
            data[p * 44, 1] = np.uint16(tag << 13 | val).view(np.int16)
        keep = np.ones(len(data), bool)
        for p in range(88, 160, 4):                      # variant 1: lose 1 packet in 4
            if p % 8:                                    # (never a tag-0 packet)
                keep[p * 44:(p + 1) * 44] = False
        text = "\n".join(ua_capture.analyse_pattern(data[keep])[0])
        self.assertRegex(text, r"0 double buffer, ISOUpdate off +\d+ / +\d+ / +0\.0 %")
        self.assertRegex(text, r"1 single buffer, ISOUpdate off +\d+ / +\d+ / +[1-9]")

    def test_gap_repeat_padding_corrupt(self):
        a = pattern(0, 500)
        gap = pattern(516, 300)                           # 16 frames lost
        rep = pattern(771, 300)                           # 45 frames repeated (816 - 45)
        pad = np.zeros((44, 2), np.int16)                 # one empty packet, nothing lost
        b = pattern(1071, 200)
        bad = pattern(1271, 3)
        bad[1, 1] ^= 0x0100                               # one corrupt sample
        data = np.concatenate([a, gap, rep, pad, b, bad])
        lines, ev = self.kinds(data)
        self.assertEqual(ev, [("gap", 16), ("repeat/back", 45)])
        text = "\n".join(lines)
        self.assertIn("padding (all-zero) runs: 1, frames 44", text)
        self.assertIn("corrupt runs (right channel does not match counter): 1, frames 1", text)

    def test_padding_that_replaced_frames_counts_as_gap(self):
        data = np.concatenate([pattern(0, 100), np.zeros((44, 2), np.int16), pattern(150, 100)])
        self.assertEqual(self.kinds(data)[1], [("gap", 50)])   # 50 values lost, 44 zeros in place

    def test_inserted_padding_loses_nothing(self):
        data = np.concatenate([pattern(0, 100), np.zeros((45, 2), np.int16), pattern(100, 100)])
        self.assertEqual(self.kinds(data)[1], [])

    def test_guitar_take_is_not_pattern(self):
        t = np.arange(44100) / 44100.0
        x = (8000 * np.sin(2 * np.pi * 110 * t)).astype(np.int16)
        data = np.stack([x, x], axis=1)
        self.assertFalse(ua_capture.is_pattern(data))
        lines = ua_capture.analyse_audio(data)
        self.assertTrue(lines[-1].startswith("0 defects"), lines[-1])

    def test_wav_round_trip(self):
        data = pattern(7, 1000)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.wav"
            ua_capture.save_wav(p, data)
            self.assertTrue(np.array_equal(ua_capture.load_wav(p), data))


class PatternFirmwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = build_host_library("host_harness_tap_pattern.c", "usb_audio_pattern_HOST_TEST_ONLY")
        cls.lib.usb_audio_set_alt.argtypes = [ctypes.c_uint]
        cls.lib.host_take_fifo.argtypes = [ctypes.c_void_p, ctypes.c_uint]

    def setUp(self):
        self.lib.host_reset()
        self.lib.host_pattern_reset()
        self.lib.usb_audio_set_alt(1)

    def block(self):
        self.lib.host_set_block(I32(*range(16)), I32(*range(16)))   # ignored by the pattern
        self.lib.ua_tx_pack_tap()

    def sof(self):
        self.lib.host_set_register(TXCSR, 0)
        self.lib.usb_audio_sof_tick_tap()
        buf = (ctypes.c_uint * 64)()
        n = self.lib.host_take_fifo(buf, 64)
        return list(buf[:n])

    def run_stream(self, ms, skip_sof_every=0):
        """44.1 frames/ms producer (16-frame blocks), one SOF per ms."""
        words, produced = [], 0.0
        for t in range(ms):
            produced += 44.1
            while produced >= 16:
                self.block()
                produced -= 16
            if not (skip_sof_every and t % skip_sof_every == skip_sof_every - 1):
                words += self.sof()
        return words_to_frames(words)

    def test_steady_stream_is_clean_after_priming(self):
        frames = self.run_stream(2000)
        start = np.argmax(np.any(frames != 0, axis=1))    # silence until primed
        lines, events = ua_capture.analyse_pattern(frames[start:])
        self.assertEqual(events, [], lines)
        self.assertTrue(ua_capture.is_pattern(frames[start:]))
        text = "\n".join(lines)
        self.assertIn("lost on the way 0 (0.00 %)", text)
        self.assertIn("SOFs skipped (TxPktRdy still set): +0", text)
        self.assertEqual(self.lib.host_tap_state(4), 0)   # no overruns

    def test_overrun_shows_as_16_frame_gap(self):
        frames = self.run_stream(200)
        for _ in range(20):                               # producer runs with no SOFs: ring fills
            self.block()
        self.assertGreater(self.lib.host_tap_state(4), 0)
        more = self.run_stream(300)
        start = np.argmax(np.any(frames != 0, axis=1))
        _, events = ua_capture.analyse_pattern(np.concatenate([frames[start:], more]))
        self.assertTrue(events)
        self.assertTrue(all(k == "gap" and s % 16 == 0 for _, k, s in events), events)


class PatternBuildTests(unittest.TestCase):
    def test_pattern_build_patches_the_same_sites_as_the_tap(self):
        import make_usb_audio_fw as ua
        base = ROOT / "build/fw/res1_493412.bin"
        if not base.exists():
            self.skipTest("stock res1 not present")
        with tempfile.TemporaryDirectory() as d:
            _, tap_plan, _ = ua.build(base, Path(d) / "tap.bin", tap=True)
            _, pat_plan, syms = ua.build(base, Path(d) / "pat.bin", pattern=True)
        self.assertEqual([(p[0], p[2]) for p in tap_plan], [(p[0], p[2]) for p in pat_plan])
        self.assertIn("ua_tx_pack_tap", syms)


if __name__ == "__main__":
    unittest.main()
