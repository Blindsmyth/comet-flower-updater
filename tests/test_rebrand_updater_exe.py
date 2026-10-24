"""Tests for tools/rebrand_updater_exe.py.

A synthetic-structure test runs unconditionally (no updater.exe needed): it builds a minimal
fake buffer shaped like the real offsets/lengths and checks the patch logic and its
assertions. A second test runs against the owner's real, locally-downloaded updater.exe (not
committed to this repo -- recon/26's whole point is that we never redistribute Zoom's binary)
and is skipped if that file isn't present, e.g. in a fresh checkout or CI.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import rebrand_updater_exe as reb  # noqa: E402

REAL_EXE = ROOT / "build" / "public_release" / "ZOOM G1X FOUR System v2.00 (Official Stock Restore).exe"


class FitTests(unittest.TestCase):
    def test_pads_short_text(self):
        self.assertEqual(reb.fit("ab", 5), "ab   ")

    def test_exact_length_unchanged(self):
        self.assertEqual(reb.fit("abcde", 5), "abcde")

    def test_rejects_too_long(self):
        with self.assertRaises(ValueError):
            reb.fit("abcdef", 5)


class RebrandOnSyntheticBufferTests(unittest.TestCase):
    """Builds a minimal buffer with the exact byte layout rebrand() expects at each of the
    six real offsets, so the patch/verify logic is tested without needing the real exe."""

    def setUp(self):
        size = max(off + n * 2 + 2 for off, n, _, _ in reb.PATCHES) + 16
        self.buf = bytearray(size)
        for off, n, null_terminated, _ in reb.PATCHES:
            placeholder = ("x" * n).encode("utf-16le")
            self.buf[off:off + n * 2] = placeholder
            if null_terminated:
                self.buf[off + n * 2:off + n * 2 + 2] = b"\x00\x00"

    def test_applies_every_patch_and_changes_nothing_else(self):
        out = reb.rebrand(bytes(self.buf))
        self.assertEqual(len(out), len(self.buf))
        touched = set()
        for off, n, _, text in reb.PATCHES:
            span = range(off, off + n * 2)
            touched.update(span)
            got = out[off:off + n * 2].decode("utf-16le")
            self.assertEqual(got, reb.fit(text, n))
        for i in range(len(self.buf)):
            if i not in touched:
                self.assertEqual(out[i], self.buf[i], "byte %#x changed outside any patch span" % i)

    def test_missing_null_terminator_raises(self):
        buf = bytearray(self.buf)
        off, n, null_terminated, _ = next(p for p in reb.PATCHES if p[2])
        buf[off + n * 2:off + n * 2 + 2] = b"\x01\x01"  # corrupt the terminator
        with self.assertRaises(AssertionError):
            reb.rebrand(bytes(buf))


@unittest.skipUnless(REAL_EXE.exists(), "needs the owner's real Zoom updater exe (not in git)")
class RebrandOnRealExeTests(unittest.TestCase):
    def test_version_strings_and_byte_scope(self):
        import pefile
        data = REAL_EXE.read_bytes()
        out = reb.rebrand(data)
        self.assertEqual(len(out), len(data))

        diffs = [i for i in range(len(data)) if data[i] != out[i]]
        self.assertTrue(diffs)
        spans = [range(off, off + n * 2) for off, n, _, _ in reb.PATCHES]
        for i in diffs:
            self.assertTrue(any(i in s for s in spans), "unexpected change at %#x" % i)

        p = pefile.PE(data=out)
        try:
            strings = {}
            for fi in p.FileInfo:
                for e in fi:
                    if hasattr(e, "StringTable"):
                        for st in e.StringTable:
                            for k, v in st.entries.items():
                                strings[k.decode()] = v.decode()
            self.assertEqual(strings["CompanyName"], "Comet Flower Labs")
            self.assertEqual(strings["ProductName"], "Comet FX")
            self.assertIn("Comet Flower Labs", strings["LegalCopyright"])
        finally:
            p.close()


if __name__ == "__main__":
    unittest.main()
