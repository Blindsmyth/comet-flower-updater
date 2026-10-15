"""Diag-build MIDI readback: firmware encoder model vs host decoder (offline)."""
import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import decode_ctl_diag as dcd  # noqa: E402
import make_controller_fw as ctl  # noqa: E402

DIAG_C = (ROOT / "firmware" / "controller" / "controller_diag.c").read_text()
CTL_C = (ROOT / "firmware" / "controller" / "controller.c").read_text()
RES1 = ROOT / "build" / "fw" / "res1_493412.bin"
LIFECYCLE_SHA = "3e7f523649fcbb8bbd8c0c440e64b332dabe9d2854b2656103932204131928b9"


def fw_stream(words):
    """Mirror of controller_diag_peek/commit: begin, 5 CCs per word, end."""
    total = 5 * len(words) + 2
    out = []
    for p in range(total):
        if p in (0, total - 1):
            out.append([119, 127 if p == 0 else 1])
        else:
            part = (p - 1) % 5
            out.append([102 + part, (words[(p - 1) // 5] >> (7 * part)) & 0x7F])
    return out


def snapshot(diag_words, tx, stack=(0x800, 0xc0300000, 0x500)):
    body = list(diag_words)
    for slot in range(1, 5):
        body += tx[slot]
    body += list(stack)
    return [0x31504D44, len(body)] + body


class DiagReadback(unittest.TestCase):
    def test_c_constants_match_decoder(self):
        self.assertIn("#define DUMP_MAGIC 0x31504d44u", DIAG_C)
        self.assertIn("*control = 119u;", DIAG_C)
        self.assertIn("*control = 102u + part;", DIAG_C)
        self.assertIn("(7u * part)) & 0x7fu", DIAG_C)
        fields = re.findall(r"TXREC\(n\)\[(\d)\]", DIAG_C)
        self.assertEqual(tuple(int(f) for f in fields), dcd.DUMP_TX_FIELDS)
        self.assertIn("#define TXREC(n) ((volatile u32 *)(0xc011297cu + 0x2a8u * (n)))", DIAG_C)
        # 6 header words + 24 entries x 4 words
        self.assertEqual(dcd.DUMP_DIAG_WORDS, 6 + 24 * 4)

    def test_controller_changes_are_diag_only(self):
        # Every readback reference in controller.c sits inside #ifdef CTL_DIAG.
        depth, bad = 0, []
        for ln in CTL_C.splitlines():
            s = ln.strip()
            if s.startswith("#ifdef CTL_DIAG"):
                depth += 1
            elif s.startswith("#endif") and depth:
                depth -= 1
            elif "controller_diag_" in s and not depth:
                bad.append(s)
        self.assertEqual(bad, [])

    def test_round_trip_with_noise_and_restart(self):
        diag = [dcd.MAGIC, 3, 0x9, 2, 77, 1] + [0] * 96
        diag[6:10] = [(1 << 24) | (4 << 16) | 0, 12, (19 << 27) | 3, 555]
        tx = {1: [0, 0, 0, 0], 2: [0, 0, 0, 0], 3: [0, 0, 0, 0],
              4: [1, 0, 1, 0xFFFFFFFF]}
        words = snapshot(diag, tx)
        stream = fw_stream(words)
        # an interrupted earlier frame, unrelated button CCs, then the full frame
        pairs = stream[:40] + [[20, 127], [21, 0]] + stream
        rep = dcd.decode_cc_stream(json.loads(json.dumps(pairs)))
        self.assertEqual(rep["head"], 3)
        self.assertEqual(rep["teardown_seen"], 2)
        self.assertEqual(rep["entries"][0]["type"], 19)
        self.assertEqual(rep["entries"][0]["channel"], 3)
        self.assertEqual(rep["tx_records"][4]["field5_outstanding"], 1)
        self.assertEqual(rep["tx_records"][4]["field9"], -1)
        self.assertIn("outstanding[5]=1", dcd.format_diag_text(rep))
        self.assertEqual(rep["worker_stack"]["peak_used_bytes"], 0x800 - 0x500)
        self.assertIn("peak 768 of 2048", dcd.format_diag_text(rep))

    def test_stack_guard_failure_reported(self):
        words = snapshot([dcd.MAGIC] + [0] * 101, {s: [0] * 4 for s in range(1, 5)},
                         stack=(0, 0, 0xFFFFFFFF))
        rep = dcd.decode_cc_stream(fw_stream(words))
        self.assertIsNone(rep["worker_stack"]["peak_used_bytes"])
        self.assertIn("not measured", dcd.format_diag_text(rep))

    def test_stack_scan_matches_stock_check(self):
        # stock c016e300 compares the byte at task word [8] with 0xbe
        self.assertIn("p[n] == 0xbeu", DIAG_C)
        self.assertIn("*size = t[7];", DIAG_C)
        self.assertIn("*base = t[8];", DIAG_C)
        dis = ROOT / "build" / "fw" / "map" / "main.dis"
        if dis.exists():
            text = dis.read_text(errors="replace")
            self.assertRegex(text, r"(?m)^c016e300\s+\S+\s+LDB\.D1T1\s+\*\+A4\[0\],A3")
            self.assertRegex(text, r"(?m)^c016e304\s+\S+\s+MVK\.S1\s+0xffffffbe,A4")
            self.assertRegex(text, r"(?m)^c0160680\s+\S+\s+\|\|\s+\[ A0\]\s+LDW\.D1T1\s+\*\+A10\[8\],A4")

    def test_rejects_truncated_frame(self):
        words = snapshot([dcd.MAGIC] + [0] * 101, {s: [0] * 4 for s in range(1, 5)})
        stream = fw_stream(words)  # noqa
        with self.assertRaises(ValueError):
            dcd.decode_cc_stream(stream[:-1])                       # no end marker
        with self.assertRaises(ValueError):
            dcd.decode_cc_stream(stream[:10] + stream[11:])         # one CC lost

    @unittest.skipUnless(RES1.exists() and ctl.CGT.exists(), "stock res1 or TI CGT not available")
    def test_lifecycle_build_unchanged(self):
        import hashlib
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "life.bin"
            ctl.build(ctl.DEFAULT_BASE if hasattr(ctl, "DEFAULT_BASE") else RES1, out, RES1)
            self.assertEqual(hashlib.sha256(out.read_bytes()).hexdigest(), LIFECYCLE_SHA)


if __name__ == "__main__":
    unittest.main()
