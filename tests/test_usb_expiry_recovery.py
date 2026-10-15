"""Pins for the Claude review in docs/helpers/SOL_EXPIRY_RECOVERY_REPORT.md (stock image only)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_DIS = ROOT / "build" / "fw" / "map" / "main.dis"

PINS = [
    # c0120f64 enqueue: store [6]/[7], skip submit while outstanding [5] != 0
    ("c0120f94", r"STW\.D2T2\s+B1,\*B4\[6\]"),
    ("c0120f96", r"STW\.D2T1\s+A1,\*B4\[7\]"),
    ("c0120f98", r"LDW\.D2T2\s+\*B4\[5\],B0"),
    ("c0120fa0", r"\[ B0\]\s+BNOP\.S1\s+0xc0120fa8,5"),
    ("c0120fa4", r"CALLP\.S2\s+0xc01204b4,B3"),
    # Hwi type-16 store gate: field [9] (0xc0112c08 - 616 = record+0x24) must be >= 0
    ("c011fb2c", r"ADDK\.S2\s+-616,B6"),
    ("c011fb36", r"CMPGT\.L2\s+0,B0,B0"),
    ("c011fb38", r"\[ B0\]\s+BNOP\.S1\s+0xc011fb70,5"),
    # c011fd40 sets field [9] = -1 via the old B4 (parallel SUB)
    ("c011fd74", r"MVK\.L2\s+-1,B1"),
    ("c011fd78", r"SUB\.L2X\s+A0,B0,B4"),
    ("c011fd80", r"STW\.D2T2\s+B1,\*B4\[9\]"),
    # c0121224 chooses fd98 only when TX field [2] == 0
    ("c01212a4", r"\[ B0\]\s+BNOP\.S1\s+0xc01212b0,5"),
    ("c01212a8", r"CALLP\.S2\s+0xc011fd98,B3"),
    ("c01212b0", r"CALLP\.S2\s+0xc011fd40,B3"),
]


class UsbExpiryRecovery(unittest.TestCase):
    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_pins(self):
        text = MAIN_DIS.read_text(errors="replace")
        for addr, ins in PINS:
            with self.subTest(addr=addr):
                self.assertRegex(text, rf"(?m)^{addr}\s+\S+\s+(\|\|\s+)?{ins}\s*$")

    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_fd80_is_parallel_with_fd78(self):
        lines = MAIN_DIS.read_text(errors="replace").splitlines()
        i = next(k for k, l in enumerate(lines) if l.startswith("c011fd80 "))
        self.assertIn("||", lines[i])
        prev = [l for l in lines[i - 3:i] if not l.split()[2].startswith(".fphead")]
        self.assertTrue(prev[-1].startswith("c011fd78 "))


if __name__ == "__main__":
    unittest.main()
