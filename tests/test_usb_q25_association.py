"""Evidence pins for docs/helpers/USB_Q25_ASSOCIATION_2026-10-15.md (stock image only)."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_DIS = ROOT / "build" / "fw" / "map" / "main.dis"

PINS = [
    # c01201e0: bit 30 = (A6 != 0), TX channel config ADDK 6112; A6 only read
    ("c01201e0", r"MV\.L1\s+A6,A0"),
    ("c0120248", r"ADDK\.S2\s+6112,B4"),
    # c0120888: RX counterpart, ADDK 6120
    ("c012088c", r"MV\.S1\s+A6,A0"),
    ("c01208f8", r"ADDK\.S2\s+6120,B4"),
    # resume loop: A6=0 before the N=1..4 enable loop
    ("c0120dec", r"MVK\.L1\s+0,A6"),
    ("c0120e00", r"CALLP\.S2\s+0xc01201e0,B3"),
    # TX abort teardown request
    ("c01206f0", r"CALLP\.S2\s+0xc01201e0,B3"),
    ("c01206f2", r"MV\.L1X\s+B4,A6"),
    # RX abort: TEARDOWN register write, then c0120888 with A6=B4=1
    ("c01209a8", r"MVK\.S1\s+28,A7"),
    ("c01209ac", r"MVKH\.S1\s+0x1e00000,A7"),
    ("c01209ba", r"STW\.D1T1\s+A0,\*A7\[0\]"),
    ("c01209c0", r"MVK\.L2\s+1,B4"),
    ("c01209c4", r"CALLP\.S2\s+0xc0120888,B3"),
    ("c01209c8", r"MV\.L1X\s+B4,A6"),
    # single dispatch of the handler table
    ("c01383d8", r"MVK\.S2\s+0x07a0,B5"),
    ("c01383e6", r"LDW\.D2T2\s+\*B5\[B4\],B0"),
    ("c01383ea", r"BNOP\.S2\s+B0,0"),
    # std-request table loaded in c01359e4
    ("c0135a94", r"MVK\.S2\s+0x0210,B5"),
    # abort callers
    ("c0120848", r"CALLP\.S2\s+0xc0120650,B3"),
    ("c0121280", r"CALLP\.S2\s+0xc0120650,B3"),
    ("c012296c", r"CALLP\.S2\s+0xc0120650,B3"),
    ("c0122978", r"CALLP\.S2\s+0xc0120800,B3"),
    ("c012146a", r"CALLP\.S2\s+0xc0121224,B3"),
    ("c01358b4", r"CALLP\.S2\s+0xc01212e0,B3"),
]

WORDS = {
    "c01807a4": "c015e924", "c01807a8": "c015e9d0", "c01807ac": "c01359e4",
    "c01807b4": "c015b168", "c01807b8": "c015b2b4", "c01807bc": "c015b290",
    "c0180234": "c0135660", "c018023c": "c0135940",
    # RX normal (26) / teardown (27) return queues, N=1..4
    "c01805a4": "0000001a", "c01805a8": "0000001b", "c01805b0": "0000001a",
    "c01805b4": "0000001b", "c01805bc": "0000001a", "c01805c0": "0000001b",
    "c01805c8": "0000001a", "c01805cc": "0000001b",
}


class UsbQ25Association(unittest.TestCase):
    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_pins(self):
        text = MAIN_DIS.read_text(errors="replace")
        for addr, ins in PINS:
            with self.subTest(addr=addr):
                self.assertRegex(text, rf"(?m)^{addr}\s+\S+\s+(\|\|\s+)?{ins}\s*$")
        for addr, val in WORDS.items():
            with self.subTest(addr=addr):
                self.assertRegex(text, rf"(?m)^{addr}\s+{val}\s+\.word")

    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_abort_and_helper_callers_are_complete(self):
        text = MAIN_DIS.read_text(errors="replace")

        def callers(target):
            return sorted(re.findall(rf"(?m)^(c[0-9a-f]{{7}})\s.*CALLP\.\S+\s+0x{target},B3", text))

        self.assertEqual(callers("c0120650"), ["c0120848", "c0121280", "c012296c"])
        self.assertEqual(callers("c01201e0"), ["c01206f0", "c01207b0", "c01207b8", "c0120e00"])
        self.assertEqual(callers("c0120800"), ["c0122978"])
        # The handler table base 0xc01807a0 is formed in exactly one place.
        self.assertEqual(len(re.findall(r"MVK\.\S+\s+0x07a0,", text)), 1)


if __name__ == "__main__":
    unittest.main()
