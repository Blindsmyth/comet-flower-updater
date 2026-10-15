"""CF ClkT frame decoding (tools/decode_memprobe.py), offline."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import decode_memprobe as dm  # noqa: E402


def frame(tscl, tim, pllm=0x12, pllctl=1, iters=0, load=0, n=21581):
    # dividers: PREDIV/POSTDIV/PLLDIV1 enabled with ratio 0 (divide by 1)
    w6 = 0x80 | 0x80 << 8 | 0x80 << 16 | pllctl << 24
    return [0xCF0071ED, 0x434c4b54, n, int(tscl * n), int(tim * n), pllm, w6,
            0x0001ffff, load, 0, iters, 0]


class ClktDecode(unittest.TestCase):
    def test_nominal_pll_budget_and_expected_timer(self):
        r = dm.clock_report(frame(50620, 6966))
        self.assertAlmostEqual(r["sysclk1_hz"], 364.8e6)
        self.assertAlmostEqual(r["budget_cycles"], 132353.74, places=1)
        self.assertAlmostEqual(r["tim_expected"], 6965.986, places=2)
        self.assertTrue(r["gempd"])
        self.assertAlmostEqual(r["busy_fraction"], 50620 / 132353.74, places=3)
        self.assertAlmostEqual(r["tscl_hz_vs_osc"] / 1e6, 139.5, places=0)

    def test_load_cycles_per_iteration(self):
        r = dm.clock_report(frame(130000, 6966, iters=10000, load=80000 * dm.FRAME_BLOCKS))
        self.assertAlmostEqual(r["load_cycles_per_iter"], 8.0)

    def test_bypassed_pll(self):
        r = dm.clock_report(frame(6966, 6966, pllctl=0))
        self.assertFalse(r["pll_enabled"])
        self.assertAlmostEqual(r["sysclk1_hz"], 19.2e6)


if __name__ == "__main__":
    unittest.main()
