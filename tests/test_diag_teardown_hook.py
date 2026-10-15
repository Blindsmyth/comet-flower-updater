"""Offline checks for the teardown-diagnostic hook row (never flashable)."""
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import make_controller_fw as ctl  # noqa: E402

RES1 = ROOT / "build" / "fw" / "res1_493412.bin"


class DiagTeardownHook(unittest.TestCase):
    def test_diag_hook_is_not_in_lifecycle_hooks(self):
        # The updater packager and lifecycle verifier iterate HOOKS only.
        vmas = {h[0] for h in ctl.HOOKS}
        for vma, *_ in ctl.DIAG_HOOKS:
            self.assertNotIn(vma, vmas)
        self.assertEqual(len(ctl.HOOKS), 7)

    @unittest.skipUnless(RES1.exists(), "stock res1 not available")
    def test_diag_stock_word_matches_and_decodes(self):
        data = RES1.read_bytes()
        for vma, off, stock, target, _ in ctl.DIAG_HOOKS:
            word = struct.unpack_from("<I", data, off)[0]
            self.assertEqual(word, stock)
            self.assertEqual(ctl.callp_target(vma, word), target)
            # Round trip of the retarget arithmetic at an in-range payload address.
            new = ctl.callp_retarget(vma, word, 0xc01a0cc0)
            self.assertEqual(ctl.callp_target(vma, new), 0xc01a0cc0)
            # Only the 21-bit displacement changes; unit/parallel bits are kept.
            keep = ~(0x1fffff << 7) & 0xffffffff
            self.assertEqual(new & keep, word & keep)

    @unittest.skipUnless(RES1.exists(), "stock res1 not available")
    def test_diag_site_is_in_a_loaded_section(self):
        data = RES1.read_bytes()
        for vma, off, *_ in ctl.DIAG_HOOKS:
            hit = [(o, a) for o, op, a in ctl.ais_commands(data)
                   if op == ctl.AIS_SECTION_LOAD and a[0] <= vma < a[0] + a[1]]
            self.assertEqual(len(hit), 1)
            o, (addr, _) = hit[0]
            self.assertEqual(o + 12 + (vma - addr), off)


if __name__ == "__main__":
    unittest.main()
