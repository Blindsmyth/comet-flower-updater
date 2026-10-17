"""USB string 3 (audio interface name) patch in tools/make_controller_fw.py. Offline."""
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import make_controller_fw as ctl  # noqa: E402

OFF = ctl.CONST_DATA[0] + ctl.USB_STR3_RECORD - 0xc016f780


class UsbString3Tests(unittest.TestCase):
    def base(self):
        data = bytearray(OFF + 16)
        struct.pack_into("<II", data, OFF, ctl.USB_STR3_STOCK_HDR, ctl.USB_STR3_STOCK_PTR)
        return data

    def test_record_points_at_text_with_length(self):
        data = self.base()
        tail = ctl.usb_string3_patch(data, "CF8 Out1-2 DI3-4 BusA5-6 BusB7-8", 0xc01a29d8)
        self.assertEqual(struct.unpack_from("<II", data, OFF), ((3 << 8) | 66, 0xc01a29d8))
        self.assertEqual(tail, b"CF8 Out1-2 DI3-4 BusA5-6 BusB7-8\0")

    def test_rejects_31_chars_too_long_and_non_ascii(self):
        # 31 characters = a 64-byte descriptor: the stock ZLP path that failed on port 13.
        for bad in ("x" * 31, "x" * 63, "", "caf\xe9"):
            with self.assertRaises(SystemExit):
                ctl.usb_string3_patch(self.base(), bad, 0xc01a29d8)

    def test_refuses_a_non_stock_record(self):
        data = self.base()
        struct.pack_into("<I", data, OFF, 0x342)
        with self.assertRaises(SystemExit):
            ctl.usb_string3_patch(data, "name", 0xc01a29d8)

    def test_stock_firmware_has_the_empty_record(self):
        fw = ROOT / "build" / "fw" / "res1_cf_usbname.bin"
        if not fw.exists():
            self.skipTest("base image not present")
        hdr, ptr = struct.unpack_from("<II", fw.read_bytes(), OFF)
        self.assertEqual((hdr, ptr), (ctl.USB_STR3_STOCK_HDR, ctl.USB_STR3_STOCK_PTR))


if __name__ == "__main__":
    unittest.main()
