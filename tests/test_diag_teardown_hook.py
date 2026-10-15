"""Offline checks for the teardown-diagnostic hook row (never flashable)."""
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import make_controller_fw as ctl  # noqa: E402

RES1 = ROOT / "build" / "fw" / "res1_493412.bin"
MAIN_DIS = ROOT / "build" / "fw" / "map" / "main.dis"


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

    def test_diag_rows_are_distinct_and_do_not_overlap(self):
        self.assertEqual({h[0] for h in ctl.DIAG_HOOKS},
                         {0xc0120744, 0xc0121a18})
        offs = sorted(h[1] for h in ctl.DIAG_HOOKS)
        for a, b in zip(offs, offs[1:]):
            self.assertGreaterEqual(b - a, 4)
        self.assertEqual(len({h[4] for h in ctl.DIAG_HOOKS}), len(ctl.DIAG_HOOKS))

    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_diag_sites_pinned_to_stock_disassembly(self):
        # Evidence tags for docs/helpers/USB_TEARDOWN_PATCH_SITES_2026-10-14.md
        text = MAIN_DIS.read_text(errors="replace")
        for vma, _, stock, target, _ in ctl.DIAG_HOOKS:
            m = re.search(r"^%08x\s+%08x\s+CALLP\.S2\s+0x%08x,B3" % (vma, stock, target),
                          text, re.M)
            self.assertIsNotNone(m, "stock disassembly differs at %#x" % vma)

    @unittest.skipUnless(RES1.exists() and ctl.CGT.exists(), "stock res1 or TI CGT not available")
    def test_diag_build_reaches_both_thunks(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "diag.bin"
            ctl.build(str(RES1), str(out), str(RES1), diag=True)
            data = out.read_bytes()
            _, _, syms = ctl.elf_image(ctl.OUT / "diag" / "controller_diag.elf")
            for vma, off, _, _, sym in ctl.DIAG_HOOKS:
                word = struct.unpack_from("<I", data, off)[0]
                self.assertEqual(ctl.callp_target(vma, word), syms[sym])
            for name in ("controller_diag_teardown", "controller_diag_consumer"):
                self.assertTrue(ctl.CTL_BASE <= syms[name] < ctl.CTL_BASE + ctl.CTL_SIZE)

    def test_ring_semantics_model(self):
        """Host model of controller_diag.c: head publishes last; wrap sets the
        sticky bit only from the 25th entry on; tags carry site/aux/seq."""
        N = 24
        head, fault, ring = 0, 0, [None] * N

        def log(site, aux, idx, w0, f):
            nonlocal head, fault
            if head >= N:
                f |= 0x4
            ring[head % N] = ((site << 24) | ((aux & 0xff) << 16) | (head & 0xffff), idx, w0)
            fault |= f
            head += 1

        for i in range(N):
            log(2, 32, i, 19 << 27, 0x8)
        self.assertEqual(fault, 0x8)
        log(1, 4, 99, 19 << 27, 0x1)
        self.assertEqual(fault, 0x8 | 0x1 | 0x4)
        self.assertEqual(ring[0][0], (1 << 24) | (4 << 16) | 24)
        self.assertEqual(ring[1][0], (2 << 24) | (32 << 16) | 1)

    def test_decode_ctl_diag_tool(self):
        """Test decode_ctl_diag parser and text formatter."""
        import decode_ctl_diag as dcd

        # Build simulated dump buffer
        # Header: magic, head=26, fault=0x8|0x1|0x4, teardown_seen=2, pops=100, other=5
        header = struct.pack("<6I", dcd.MAGIC, 26, 0x1 | 0x4 | 0x8, 2, 100, 5)
        entries = []
        for i in range(24):
            # Slots 0 and 1 correspond to seq 24 and 25
            seq = i if i >= 2 else i + 24
            site = 1 if seq == 24 else 2
            aux = 4 if site == 1 else 33
            tag = (site << 24) | (aux << 16) | seq
            idx = 10 + i
            w0 = (19 << 27) | (3 if site == 1 else 0)
            tscl = 1000 + i
            entries.append(struct.pack("<4I", tag, idx, w0, tscl))
        blob = b"\xaa" * 32 + header + b"".join(entries) + b"\x55" * 16

        # Auto-find magic
        rep = dcd.decode_diag(blob)
        self.assertEqual(rep["offset"], 32)
        self.assertEqual(rep["head"], 26)
        self.assertEqual(rep["active_entries"], 24)
        self.assertEqual(rep["teardown_seen"], 2)
        self.assertEqual(len(rep["faults"]), 3)
        self.assertIn("FAULT_TYPE19_RECYCLED (site 1: type 19 recycled by abort drain)", rep["faults"])
        self.assertIn("FAULT_RING_WRAPPED (ring wrapped, oldest entries overwritten)", rep["faults"])
        self.assertIn("FAULT_TYPE19_CONSUMER (site 2: type 19 recycled by queue 32..35 consumer)", rep["faults"])

        # Check chronological ordering: oldest should be seq 2, newest seq 25
        self.assertEqual(rep["entries"][0]["seq"], 2)
        self.assertEqual(rep["entries"][-1]["seq"], 25)
        self.assertEqual(rep["entries"][-2]["seq"], 24)
        self.assertEqual(rep["entries"][-2]["site_id"], 1)
        self.assertEqual(rep["entries"][-2]["aux"], 4)
        self.assertEqual(rep["entries"][-2]["type"], 19)
        self.assertEqual(rep["entries"][-2]["channel"], 3)

        # Test text output
        txt = dcd.format_diag_text(rep)
        self.assertIn("=== ctl_diag USB Teardown Diagnostic Report ===", txt)
        self.assertIn("FAULT_TYPE19_RECYCLED", txt)

        # Test missing magic error
        with self.assertRaises(ValueError):
            dcd.decode_diag(b"\x00" * 500)


if __name__ == "__main__":
    unittest.main()

