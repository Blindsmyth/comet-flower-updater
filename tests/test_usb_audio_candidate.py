"""Offline checks for the USB audio silence-stream candidate (never flashable)."""
import re
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import make_controller_fw as ctl  # noqa: E402
import make_usb_audio_fw as ua  # noqa: E402

RES1 = ROOT / "build" / "fw" / "res1_493412.bin"
MAIN_DIS = ROOT / "build" / "fw" / "map" / "main.dis"
MAIN_ELF = ROOT / "build" / "fw" / "map" / "main.elf"
CAN_BUILD = RES1.exists() and ctl.CGT.exists()


def payload(data):
    i = data.rfind(struct.pack("<I", ctl.AIS_SECTION_LOAD))
    a, n = struct.unpack_from("<II", data, i + 4)
    return a, data[i + 12:i + 12 + n]


@unittest.skipUnless(CAN_BUILD, "stock res1 or TI CGT not available")
class UsbAudioCandidateBuild(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        out = Path(cls.tmp.name) / "ua.bin"
        cls.data, cls.plan, cls.syms = ua.build(RES1, out)
        cls.stock = RES1.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_only_patch_words_change_in_stock_sections(self):
        close = len(self.stock) - 8
        changed = {i for i in range(close) if self.data[i] != self.stock[i]}
        allowed = {off + k for _, off, *_ in self.plan for k in range(4)}
        self.assertTrue(changed <= allowed)
        self.assertEqual(len(self.plan), 11)

    def test_every_patch_decodes_to_its_symbol(self):
        for vma, off, old, new, kind, sym in self.plan:
            word = struct.unpack_from("<I", self.data, off)[0]
            self.assertEqual(ua.decode(vma, word, kind), ua.expected(kind, self.syms[sym]))
            if kind in ("callp", "callp_over"):
                keep = ~(0x1fffff << 7) & 0xffffffff
                base = ua.CALLP_S2_TEMPLATE if kind == "callp_over" else old
                self.assertEqual(word & keep, base & keep)   # unit/creg/p-bit kept
                # Retargets keep the stock p-bit (stock sites pass arguments in
                # parallel); the CALLP written over the c015c674 BNOP must not be
                # parallel, matching the BNOP it replaces.
                self.assertEqual(word & 1, 0 if kind == "callp_over" else old & 1)
                if kind == "callp_over":
                    self.assertEqual(old & 1, 0)

    def test_handler_records_hold_glue_functions(self):
        a, img = payload(self.data)
        for rec, cb in (("ua_if2_record", "ua_if2_request"), ("ua_if3_record", "ua_if3_request")):
            words = struct.unpack_from("<5I", img, self.syms[rec] - a)
            stub = self.syms["ua_ret0"]
            self.assertEqual(words, (stub, stub, stub, self.syms[cb], stub))

    def test_payload_clear_of_controller_region(self):
        a, img = payload(self.data)
        self.assertGreaterEqual(a, ctl.CTL_BASE + ctl.CTL_SIZE)
        self.assertLessEqual(a + len(img), ua.UA_BASE + ua.UA_SIZE)

    def test_map_thunk_shape(self):
        dis = (ua.OUT / "usb_audio.dis").read_text(errors="replace")
        body = dis[dis.index("ua_map_thunk:"):dis.index("ua_map_reject:") + 200]
        self.assertIn("MVK.S2        0xffffc768,B3", body)
        self.assertIn("MVKH.S2       0xc0150000,B3", body)
        self.assertIn("STW.D1T2      B0,*+A5[A4]", body)
        self.assertIn("STW.D1T1      A4,*+A5[17]", body)            # aa4c + 68 = EP 0x84
        regs = set(re.findall(r"\b([AB]\d+)\b", re.sub(r"0x[0-9a-f]+", "", body)))
        self.assertTrue(regs <= {"A0", "A4", "A5", "B0", "B3"}, regs)

    def test_descriptor_veneer_delegates_non_fragment_types(self):
        # Regression for the STRING-descriptor bug (REVIEW_USB_AUDIO_CANDIDATE.md):
        # the veneer may only replace A4 = 1/2; all else goes to stock c0160ec0
        # before anything (B3, A6, B4, stack) is touched.
        dis = (ua.OUT / "usb_audio.dis").read_text(errors="replace")
        body = dis[dis.index("usb_audio_descriptor_veneer:"):].splitlines()[1:5]
        text = "\n".join(body)
        self.assertRegex(body[0], r"ADD\.L1\s+A4,-1,A0")
        self.assertRegex(body[1], r"CMPLTU\.L1\s+1,A0,A0")
        self.assertRegex(body[2], r"\[ A0\]\s+B\.S1\s+stock_descriptor_builder .*= 0xc0160ec0\)")
        self.assertRegex(body[3], r"NOP\s+5")
        self.assertNotIn("B15", text)

    def test_layers_onto_controller_lifecycle_candidate(self):
        with tempfile.TemporaryDirectory() as d:
            life = Path(d) / "life.bin"
            ctl.build(RES1, life, RES1)
            data, plan, _ = ua.build(life, Path(d) / "both.bin")
            for vma, off, stock, target, sym in ctl.HOOKS:
                word = struct.unpack_from("<I", data, off)[0]
                self.assertNotEqual(word, stock)                     # controller hook kept
            hook_offs = {off for _, off, *_ in ctl.HOOKS}
            self.assertFalse(hook_offs & {off for _, off, *_ in plan})


class UsbAudioStockFacts(unittest.TestCase):
    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_patch_assumptions_pinned(self):
        text = MAIN_DIS.read_text(errors="replace")
        # c015c66c's only caller is the compact CALLP at c015c760; its packet ends
        # at c015c766, so the continuation the thunk returns to is c015c768.
        self.assertEqual(re.findall(r"(?m)^(c[0-9a-f]{7})\s.*0xc015c66c\b", text), ["c015c760"])
        for addr, ins in [
            ("c015c762", r"\|\|\s+LDW"), ("c015c764", r"\|\|\s+ADD"), ("c015c766", r"\|\|\s+MV"),
            ("c015c768", r"ADD\.L2\s+B1,1,B1"),
            # state at the c015c674 gate: A0 = selector==6, A4 = slot (A6), B0 = record (B4)
            ("c015c66c", r"MV\.L1\s+A4,A0"), ("c015c66e", r"\|\|\s+MV\.S1\s+A6,A4"),
            ("c015c670", r"\|\|\s+MV\.L2\s+B4,B0"), ("c015c672", r"CMPEQ\.L1\s+6,A0,A0"),
            ("c015c674", r"\[!A0\]\s+BNOP\.S1\s+0xc015c6ac,5"),
            # the stock SOF veneer and the ACK sequence the glue copies
            ("c016f770", r"MVK\.S2\s+0xffff8e80,B31"), ("c016f778", r"B\.S2\s+B31"),
            ("c0151f60", r"\|\|\s+MVK\.S1\s+128,A4"), ("c0151f64", r"\|\|\s+CALLP\.S2\s+0xc015af48,B3"),
            ("c0151f6c", r"\|\|\s+MVK\.S1\s+0xfffffffe,A8"),
            # stock builder: A4-1 <= 1 builds fragments; 3 = string table; 6/7 empty
            ("c0160ee2", r"ADD\.L1\s+A7,-1,A0"), ("c0160ee4", r"CMPLTU\.L1\s+1,A0,A0"),
            ("c0160ee6", r"\[!A0\]\s+BNOP\.S1\s+0xc0160ef4,4"),
            ("c0160eea", r"CMPEQ\.L1\s+3,A4,A0"), ("c0160eec", r"\[ A0\]\s+BNOP\.S1\s+0xc0161008,5"),
            # the string caller reads {len, .., ptr} records, not fragments
            ("c0135262", r"\|\|\s+MV\.S1\s+A10,A4"), ("c01352a4", r"LDW\.D1T1\s+\*A4\[1\],A5"),
            # GET_INTERFACE reads the alt array the IF3 callback writes
            ("c0134e7c", r"MVK\.S1\s+0xffffa1b0,A5"), ("c0134e8c", r"LDB\.D1T1\s+\*A4\[A5\],A0"),
        ]:
            with self.subTest(addr=addr):
                self.assertRegex(text, rf"(?m)^{addr}\s+\S+\s+{ins}")
        builder_calls = re.findall(r"(?m)^(c[0-9a-f]{7})\s.*CALLP\.\S+\s+0xc0160ec0,B3", text)
        self.assertEqual(sorted(builder_calls), sorted("%08x" % a for a in ua.BUILDER_CALLS))

    @unittest.skipUnless(MAIN_ELF.exists(), "stock ELF not available")
    def test_prototype_stock_fragments_match_rom(self):
        from elftools.elf.elffile import ELFFile
        src = (ROOT / "firmware" / "usb_audio_proto" / "usb_audio.c").read_text()
        frags = {m.group(1): bytes(int(x, 16) for x in re.findall(r"0x([0-9a-fA-F]{2})", m.group(2)))
                 for m in re.finditer(r"static const u8 (\w+)\[\d+\]\s*=\s*\{([^}]*)\}", src)}
        with MAIN_ELF.open("rb") as fh:
            blob = b"".join(s.data() for s in ELFFile(fh).iter_sections()
                            if s["sh_type"] == "SHT_PROGBITS")
        names = [k for k in frags if k.startswith("stock_") or k == "device_desc"]
        self.assertEqual(len(names), 13)
        for k in names:
            with self.subTest(fragment=k):
                self.assertGreaterEqual(blob.find(frags[k]), 0)


if __name__ == "__main__":
    unittest.main()
