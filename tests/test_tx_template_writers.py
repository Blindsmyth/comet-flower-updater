"""Evidence pins for docs/helpers/USB_TX_TEMPLATE_WRITERS_2026-10-15.md (stock image only)."""
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP = ROOT / "build" / "fw" / "map"
MAIN_DIS = MAP / "main.dis"
MAIN_ELF = MAP / "main.elf"

TABLE, TABLE_END = 0xc01805c4, 0xc0180600  # 5 slots x 3 words
TEMPLATES = [(4, 26, 27), (16, 24, 25), (18, 24, 25), (20, 24, 25), (22, 24, 25)]
# Every instruction forming a low half inside the table (all paired with MVKH 0xc0180000).
REFS = {0xc01201f0: 0x05c8, 0xc0120210: 0x05cc, 0xc0120484: 0x05c4,
        0xc0120658: 0x05d0, 0xc0120c00: 0x05c4, 0xc01219a4: 0x05c4}


class TxTemplateWriters(unittest.TestCase):
    @unittest.skipUnless(MAIN_ELF.exists(), "stock ELF not available")
    def test_template_words_and_no_pointer_literals(self):
        from elftools.elf.elffile import ELFFile
        with MAIN_ELF.open("rb") as fh:
            elf = ELFFile(fh)
            owner = [s for s in elf.iter_sections()
                     if s["sh_addr"] <= TABLE < s["sh_addr"] + s["sh_size"]]
            self.assertEqual(len(owner), 1)
            sec = owner[0]
            self.assertTrue(sec["sh_flags"] & 1, "table lies in a writable section")
            data = sec.data()
            base = TABLE - sec["sh_addr"]
            words = struct.unpack_from("<15I", data, base)
            self.assertEqual([tuple(words[i:i + 3]) for i in range(0, 15, 3)], TEMPLATES)
            hits = []
            for s in elf.iter_sections():
                if s["sh_type"] != "SHT_PROGBITS":
                    continue
                d = s.data()
                for i in range(0, len(d) - 3, 4):
                    v = struct.unpack_from("<I", d, i)[0]
                    if TABLE <= v < TABLE_END:
                        hits.append(s["sh_addr"] + i)
            self.assertEqual(hits, [])

    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_only_six_references_all_reads(self):
        lines = MAIN_DIS.read_text(errors="replace").splitlines()
        pat = re.compile(r"^(c[0-9a-f]{7})\s.*MVK\.[SL][12]\s+0x(05[c-f][0-9a-f]),")
        found = {}
        for i, ln in enumerate(lines):
            m = pat.match(ln)
            if not m or not TABLE <= 0xc0180000 + int(m.group(2), 16) < TABLE_END:
                continue
            # Other 0x05dc/0x05fc hits are numeric constants (1500 etc.) with no
            # 0xc0180000 high half; count only true table addresses.
            if any("MVKH" in w and "0xc0180000" in w for w in lines[i:i + 16]):
                found[int(m.group(1), 16)] = int(m.group(2), 16)
        self.assertEqual(found, REFS)

    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_abort_tail_reads_submit_queue_word(self):
        text = MAIN_DIS.read_text(errors="replace")
        for addr, ins in [
            ("c0120672", r"MV\.L2X\s+A3,B5"),            # B5 = 0xc01805d0
            ("c0120684", r"MPYLI\.M2\s+B0,B4,B1:B0"),    # B0 = 12 * N
            ("c0120692", r"MV\.L1X\s+B0,A15"),           # A15 = 12 * N
            ("c0120714", r"MV\.S1X\s+B5,A12"),           # A12 = 0xc01805d0
            ("c0120774", r"ADD\.L1\s+A1,A0,A4"),         # A4 = A12 + A15
            ("c0120778", r"LDW\.D1T1\s+\*-A4\[3\],A11"),  # word [0] of slot N
            ("c0120794", r"CALLP\.S2\s+0xc0120550,B3"),
        ]:
            self.assertRegex(text, rf"(?m)^{addr}\s+\S+\s+(\|\|\s+)?{ins}")


if __name__ == "__main__":
    unittest.main()
