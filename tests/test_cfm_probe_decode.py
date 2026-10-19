"""CF Master probe pages (effects/common/cfm_probe.h) through the tone-code decoder, offline."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import decode_memprobe as dm  # noqa: E402

SR, SYNC, BIT = 44100, 6624, 882          # mp_fsk.h


def fsk(words):
    """mp_fsk.h's transmitter: 3 kHz sync, then 32 bits per word MSB first, 1 kHz = 0, 2 kHz = 1;
    the phase restarts at every symbol."""
    words = list(words[:11])
    chk = 0
    for v in words:
        chk ^= v
    words.append(chk)
    syms = [(3000, SYNC)] + [((2000 if w >> (31 - b) & 1 else 1000), BIT) for w in words for b in range(32)]
    return np.concatenate([0.25 * np.sin(2 * np.pi * f * np.arange(1, n + 1) / SR) for f, n in syms])


def page0(calls=21582, tim=21582 * 6966, other=0, work=0xC0226000, code=0xC01F4120):
    return [0xCF0071ED, 0x43464D30, calls, tim, other, 0x11F03AD0, 0x11F00000, 0x11F013B0,
            work, 0x81330, code]


def page1(changed=0b00001, zero=0b11110, knobs=range(1, 13)):
    k = list(knobs)
    pack = lambda a: k[a] << 24 | k[a + 1] << 16 | k[a + 2] << 8 | k[a + 3]
    return [0xCF0071ED, 0x43464D31, changed, zero, pack(0), pack(4), pack(8), 1, 2, 3, 4]


class CfmReport(unittest.TestCase):
    def test_page0_one_call_per_block_in_slot0(self):
        r = dm.cfm_report(page0())
        self.assertAlmostEqual(r["calls_per_block"], 1.0, places=3)
        self.assertEqual((r["work_slot"], r["code_slot"], r["other_instance_calls"]), (0, 0, 0))

    def test_page0_five_calls_per_block(self):
        r = dm.cfm_report(page0(calls=5 * 21582, other=4 * 21582))
        self.assertAlmostEqual(r["calls_per_block"], 5.0, places=3)

    def test_page0_slot_from_addresses(self):
        r = dm.cfm_report(page0(work=0xC0226000 + 2 * 0x81330, code=0xC01F4000 + 2 * 0xA000 + 0x40))
        self.assertEqual((r["work_slot"], r["code_slot"]), (2, 2))
        self.assertIsNone(dm.cfm_report(page0(work=0x11800000))["work_slot"])

    def test_page1(self):
        r = dm.cfm_report(page1())
        self.assertEqual(r["changed"], [0])
        self.assertEqual(r["zero"], [1, 2, 3, 4])
        self.assertEqual(r["knobs"], list(range(1, 13)))


class CfmToneCode(unittest.TestCase):
    def test_round_trip_both_pages(self):
        sig = np.concatenate([np.zeros(4000), fsk(page0()), fsk(page1(knobs=[1, 50] + [7] * 10)),
                              np.zeros(4000)])
        good = [w for _, w, ok in dm.decode(sig) if ok]
        tags = [w[1] for w in good]
        self.assertIn(0x43464D30, tags)
        self.assertIn(0x43464D31, tags)
        p1 = dm.cfm_report(next(w for w in good if w[1] == 0x43464D31))
        self.assertEqual(p1["knobs"], [1, 50] + [7] * 10)


if __name__ == "__main__":
    unittest.main()
