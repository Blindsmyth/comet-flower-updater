"""Evidence pins for docs/helpers/USB_ABORT_ENTRY_IRQ_2026-10-15.md (stock image only)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN_DIS = ROOT / "build" / "fw" / "map" / "main.dis"

PINS = [
    # c015ee80 saves CSR before each DINT and restores it
    ("c015eeb0", r"MVC\.S2\s+CSR,B7"), ("c015eeb4", r"DINT"), ("c015eec8", r"MVC\.S2\s+B7,CSR"),
    ("c015eecc", r"MVC\.S2\s+CSR,B7"), ("c015eed0", r"DINT"), ("c015eff0", r"MVC\.S2\s+B7,CSR"),
    ("c015f044", r"MVC\.S2\s+CSR,B4"), ("c015f048", r"DINT"), ("c015f078", r"MVC\.S2\s+B4,CSR"),
    # reach path from the abort's resubmit branch
    ("c012050c", r"CALLP\.S2\s+0xc016e380,B3"),
    ("c016e38c", r"CALLP\.S2\s+0xc015ee80,B3"),
    # c012154c brackets the rearm: c0121530(1) ... c0121530(0)
    ("c0121550", r"CALLP\.S2\s+0xc0121530,B3"), ("c0121552", r"MVK\.L1\s+1,A4"),
    ("c0121578", r"CALLP\.S2\s+0xc0121530,B3"), ("c012157a", r"MVK\.L1\s+0,A4"),
    ("c014a230", r"DINT"),
    ("c014a0b4", r"MVC\.S2\s+CSR,B0"), ("c014a0b8", r"SET\.S2\s+B0,0,0,B0"), ("c014a0c0", r"MVC\.S2\s+B0,CSR"),
    # c015e9d0 calls the abort dispatcher first
    ("c015e9d8", r"CALLP\.S2\s+0xc01229e8,B3"),
    # event task loop
    ("c0138390", r"CALLP\.S2\s+0xc012154c,B3"),
]


class UsbAbortEntryIrq(unittest.TestCase):
    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_pins(self):
        text = MAIN_DIS.read_text(errors="replace")
        for addr, ins in PINS:
            with self.subTest(addr=addr):
                self.assertRegex(text, rf"(?m)^{addr}\s+\S+\s+(\|\|\s+)?{ins}\s*$")


if __name__ == "__main__":
    unittest.main()
