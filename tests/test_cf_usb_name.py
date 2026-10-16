"""USB device-name rename (tools/cf_usb_name.py) and pedal port matching."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import cf_usb_name as u  # noqa: E402
import pedal_ports  # noqa: E402

RES1 = ROOT / "build" / "fw" / "res1_493412.bin"
RES5 = ROOT / "build" / "fw" / "res5_163840.bin"
MAIN_DIS = ROOT / "build" / "fw" / "map" / "main.dis"


@unittest.skipUnless(RES1.exists(), "stock res1 not available")
class UsbName(unittest.TestCase):
    def test_rename_const_only_and_lengths(self):
        fw = RES1.read_bytes()
        self.assertEqual(u.read_names(fw), ["ZOOM Corporation", "ZOOM G Series"])
        out = u.rename(fw, "Comet Flower")
        self.assertEqual(u.read_names(out), ["Comet Flower", "Comet Flower"])
        changed = [i for i in range(len(fw)) if fw[i] != out[i]]
        self.assertTrue(changed)
        self.assertTrue(all(u.CONST_FILE <= i < u.CONST_FILE + u.CONST_SIZE for i in changed))
        self.assertEqual(len(out), len(fw))

    def test_refuses_too_long_and_non_stock(self):
        fw = RES1.read_bytes()
        with self.assertRaises(ValueError):
            u.rename(fw, "Comet Flower Pedal")          # 18 > 13-char product slot
        with self.assertRaises(ValueError):
            u.rename(u.rename(fw, "Comet Flower"), "X")  # only from the stock strings

    @unittest.skipUnless(RES5.exists(), "boot program not available")
    def test_update_mode_keeps_zoom_name(self):
        boot = RES5.read_bytes()
        self.assertIn(b"ZOOM G Series", boot)           # boot program has its own copy

    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_descriptor_builder_copies_by_blength(self):
        text = MAIN_DIS.read_text(errors="replace")
        for pat in (r"^c01352a6\s+\S+\s+LDBU\.D1T1\s+\*A4\[0\],A0",      # bLength
                    r"^c01352a4\s+\S+\s+LDW\.D1T1\s+\*A4\[1\],A5",       # text pointer
                    r"^c0135322\s+\S+\s+LDB\.D1T1\s+\*A5\+\+\[1\],A0",  # ASCII in
                    r"^c0135328\s+\S+\s+\|\|\s+STB\.D1T1\s+A0,\*A4\+\+\[2\]",  # UTF-16 out
                    r"^c017f428\s+c0181420\s+\.word", r"^c017f430\s+c0181638\s+\.word"):
            self.assertRegex(text, "(?m)" + pat)


class Ports(unittest.TestCase):
    def test_prefixes(self):
        for n in ("ZOOM G Series 0", "Comet Flower 1"):
            self.assertTrue(pedal_ports.is_pedal_port(n))
        self.assertFalse(pedal_ports.is_pedal_port("FootCtrlPlus 0"))

    def test_register_zoomzt2(self):
        class M:
            midinames = ["ZOOM G", "ZOOM MS Plus Series"]
        pedal_ports.register_zoomzt2(M)
        pedal_ports.register_zoomzt2(M)
        self.assertEqual(M.midinames.count("Comet Flower"), 1)


if __name__ == "__main__":
    unittest.main()
