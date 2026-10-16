"""Timing beacon: firmware frame format (controller_diag.c) vs the host tool's parser and fit."""
import random
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import cf_tick_test as tt  # noqa: E402

DIAG_C = (ROOT / "firmware" / "controller" / "controller_diag.c").read_text()


def frame(ticks):
    """Mirror of beacon_peek: begin, five 7-bit slices on CC112..116, end."""
    return ([(118, 127)] + [(112 + k, (ticks >> (7 * k)) & 0x7F) for k in range(5)]
            + [(118, 1)])


class Beacon(unittest.TestCase):
    def test_c_matches_tool(self):
        self.assertIn("#define BEACON_CCS 7u", DIAG_C)
        self.assertIn("*control = 118u;", DIAG_C)
        self.assertIn("*control = 112u + (p - 1u);", DIAG_C)
        self.assertIn("(beacon.word >> (7u * (p - 1u))) & 0x7fu", DIAG_C)
        self.assertIn("#define TICKS (*(volatile u32 *)0xc0182054u)", DIAG_C)
        # the readback uses other controllers, so the streams can interleave
        self.assertFalse(set(range(112, 119)) & {102, 103, 104, 105, 106, 119})

    def test_parse_interleaved_and_fit(self):
        rnd = random.Random(1)
        period = 0.000998          # what the tool must recover
        parser, pts, t = tt.BeaconParser(), [], 10.0
        for i in range(80):
            ticks = (0xFFFFF000 + 1000 * i) & 0xFFFFFFFF      # crosses the 32-bit wrap
            host = 10.0 + 1000 * i * period + rnd.gauss(0, 0.0015)
            if i == 40:
                host += 0.25                                   # one frame delayed by a readback
            ev = frame(ticks)
            ev.insert(3, (102, 5))                             # readback CC interleaved
            for c, v in ev:
                got = parser.feed(host, c, v)
                if got:
                    pts.append(got)
        self.assertEqual(len(pts), 80)
        r = tt.fit(pts)
        self.assertAlmostEqual(r["seconds_per_tick"], period, delta=period * 2e-4)
        self.assertEqual(r["beacons_used"], 79)               # the delayed one is dropped
        self.assertIn("1 tick =", tt.describe(r))

    def test_readback_decoder_ignores_beacons(self):
        import decode_ctl_diag as dcd
        words = [0x31504D44, 2, 0x12345678, 0x0FEDCBA9]
        rb = [(119, 127)] + [(102 + k, (w >> (7 * k)) & 0x7F) for w in words for k in range(5)] + [(119, 1)]
        mixed = rb[:7] + frame(4242) + rb[7:]
        self.assertEqual(dcd.words_from_cc(mixed), words)

    def test_incomplete_frame_ignored(self):
        p = tt.BeaconParser()
        ev = frame(12345)
        del ev[2]
        self.assertEqual([x for x in (p.feed(0, c, v) for c, v in ev) if x], [])


if __name__ == "__main__":
    unittest.main()
