"""Evidence pins for docs/helpers/USB_HWI_COEXISTENCE_2026-10-15.md (stock image only)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_DIS = ROOT / "build" / "fw" / "map" / "main.dis"

PINS = [
    # pop / push / type primitives
    ("c011fa28", r"MVK\.S1\s+0x1803,A5"),
    ("c011fa2c", r"LDW\.D1T1\s+\*A4\[A5\],A0"),
    ("c011fa4a", r"MVK\.L1\s+-1,A4"),
    ("c011fa90", r"ADDK\.S1\s+24588,A4"),
    ("c011fa96", r"STW\.D1T2\s+B0,\*A4\[0\]"),
    ("c011fa66", r"SHRU\.S1\s+A0,0x1b,A0"),
    ("c011fa68", r"MVK\.S1\s+16,A1"),
    # Hwi drains 24 and 25 unconditionally
    ("c011fcb8", r"CALLP\.S2\s+0xc011faa0,B3"),
    ("c011fcba", r"MVK\.S1\s+24,A4"),
    ("c011fcc0", r"CALLP\.S2\s+0xc011faa0,B3"),
    ("c011fcc2", r"MVK\.S1\s+25,A4"),
    # non-type-16 entries forwarded to queue 32
    ("c011faae", r"MVK\.S1\s+32,A6"),
    ("c011fab0", r"MVK\.L1\s+0,A7"),
    ("c011fab6", r"\[!A0\]\s+BNOP\.S1\s+0xc011fb70,5"),
    ("c011fb74", r"CALLP\.S2\s+0xc011fa70,B3"),
    ("c011fb76", r"MV\.L1\s+A6,A4"),
    # event decoder: PEND1 bit 0 -> queue 32 consumer
    ("c0121d88", r"MVK\.S1\s+148,A0"),
    ("c0121d8c", r"SET\.S1\s+A0,14,14,A0"),
    ("c0121e38", r"AND\.L1\s+1,A0,A0"),
    ("c0121e40", r"\[ A0\]\s+BNOP\.S1\s+0xc0121e94,5"),
    ("c0121e94", r"MVK\.S2\s+32,B4"),
    ("c0121e96", r"CALLP\.S2\s+0xc01219f4,B3"),
    # deferred consumer recycles non-type-16 with B4=0
    ("c0121a22", r"\[ A0\]\s+BNOP\.S1\s+0xc0121a38,5"),
    ("c0121a24", r"CALLP\.S2\s+0xc0120550,B3"),
    ("c0121a28", r"MVK\.L2\s+0,B4"),
    # c0120550 B4=0 -> push to queue 28
    ("c0120556", r"MV\.L2\s+B4,B0"),
    ("c0120560", r"\[!B0\]\s+BNOP\.S1\s+0xc0120618,5"),
    ("c0120618", r"CALLP\.S2\s+0xc011fa70,B3"),
    ("c0120620", r"MVK\.S1\s+28,A4"),
    # abort drain: empty pop exits without recycling
    ("c012073a", r"CMPGT\.L1\s+0,A4,A0"),
    ("c0120740", r"\[ A0\]\s+BNOP\.S1\s+0xc0120764,4"),
    ("c012074c", r"MVK\.L2\s+0,B4"),
    ("c0120760", r"\[!A0\]\s+BNOP\.S1\s+0xc0120744,4"),
]


class UsbHwiCoexistence(unittest.TestCase):
    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_pins(self):
        text = MAIN_DIS.read_text(errors="replace")
        for addr, ins in PINS:
            with self.subTest(addr=addr):
                self.assertRegex(text, rf"(?m)^{addr}\s+\S+\s+(\|\|\s+)?{ins}\s*$")

    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_hwi_queue_calls_precede_status_branch(self):
        # Queue service at fcb8/fcc0 is not inside any conditional skip: the only
        # branch before it (c011fca4) targets c011fcb8 itself.
        lines = MAIN_DIS.read_text(errors="replace").splitlines()
        start = next(i for i, l in enumerate(lines) if l.startswith("c011fc8c "))
        end = next(i for i, l in enumerate(lines) if l.startswith("c011fcb8 "))
        branches = [l for l in lines[start:end] if "BNOP" in l or " B.S" in l]
        self.assertEqual(len(branches), 1)
        self.assertIn("0xc011fcb8", branches[0])


if __name__ == "__main__":
    unittest.main()
