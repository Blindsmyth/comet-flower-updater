"""On-pedal status screen (controller_ui.c) on the host, with recording stubs.

The real controller_ui.c is compiled for the host (ui_host_harness*.c); the
stock LCD/gate/wait calls are recorders. Each test checks behaviour, and the
recorded draw calls are rendered with the firmware's own fonts to
build/ui_mock/fw_<name>.png, so the screens can be reviewed as the pedal
would show them.
"""
import ctypes
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import test_usb_audio_proto as host  # noqa: E402
import ui_mock  # noqa: E402

SRC = ROOT / "firmware" / "controller"
RES1 = ROOT / "build" / "fw" / "res1_493412.bin"
OUT = ROOT / "build" / "ui_mock"


def load(source, prefix):
    try:
        return host.build_host_library(source, prefix, src_dir=SRC)
    except RuntimeError as exc:
        raise unittest.SkipTest(str(exc))


def arr(lib, name, ctype, n):
    return (ctype * n).in_dll(lib, name)


def ops(lib):
    n = ctypes.c_uint.in_dll(lib, "host_nops").value
    op, a, b, c = (arr(lib, k, ctypes.c_uint, 256) for k in ("host_op", "host_a", "host_b", "host_c"))
    strs = (ctypes.c_char * 32 * 256).in_dll(lib, "host_str")
    return [(op[i], a[i], b[i], c[i], strs[i].value.decode()) for i in range(n)]


def lines(rec):
    """5x7 lines by page, and 8x13 strings, as text."""
    pages = {}
    for op, a, b, c, _ in rec:
        if op == 2:
            pages.setdefault(b, []).append((c, chr(a)))
    text = {p: "".join(ch for _, ch in sorted(v)) for p, v in pages.items()}
    big = [(a, b, s) for op, a, b, c, s in rec if op == 3]
    return text, big


def render(rec, buf, columns=None):
    """Replay recorded calls with the firmware fonts (glyph = font_5x7 at page*8,
    text8 = font_8x13 with the stock 9-pixel advance), over the raw columns the
    code wrote straight into the page buffer (bars)."""
    spec = [("columns", bytes(columns))] if columns is not None else []
    for op, a, b, c, s in rec:
        if op == 2:
            spec.append(("text", "font_5x7", c, b * 8, chr(a)))
        elif op == 3:
            for k, ch in enumerate(s):
                spec.append(("text", "font_8x13", a + 9 * k, b, ch))
    return ui_mock.render(spec, buf)


class ControllerUi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = load("ui_host_harness.c", "ctl_ui_HOST_TEST_ONLY")
        cls.lib.host_pend.restype = ctypes.c_uint
        cls.lib.host_pend.argtypes = [ctypes.c_int]
        cls.lib.host_repaint.restype = ctypes.c_uint

    def setUp(self):
        L = self.lib
        L.host_reset()
        arr(L, "host_port", ctypes.c_uint, 16)[3] = 0
        arr(L, "host_port", ctypes.c_uint, 16)[9] = 0
        arr(L, "host_tx4", ctypes.c_uint, 16)[5] = 0

    def usb(self, ready):
        p = arr(self.lib, "host_port", ctypes.c_uint, 16)
        p[3], p[9] = (1, 1) if ready else (0, 0)

    def lcd(self):
        return bytes(arr(self.lib, "host_lcd", ctypes.c_ubyte, 512))

    def shot(self, name):
        rec = ops(self.lib)
        if RES1.exists():
            OUT.mkdir(parents=True, exist_ok=True)
            ui_mock.show(render(rec, RES1.read_bytes(), self.lcd())).save(OUT / f"fw_{name}.png")
        return rec

    def bar_fill(self, page, x0, w, full):
        """Filled columns inside a bar's outline."""
        cols = self.lcd()[page * 128 + x0: page * 128 + x0 + w]
        return sum(1 for c in cols[1:-1] if c == full)

    def test_screens_and_repaint_policy(self):
        L = self.lib
        L.host_set_mode(1)
        for i in range(4):
            L.host_knob(i, 64)
        L.host_tick()                                   # first tick always paints
        text, big = lines(self.shot("ctl_no_usb"))
        self.assertEqual(text[0], "MIDI CH1 NO USB")
        self.assertEqual(big, [(0, 10, "CONNECT USB")])
        self.assertEqual(text[3], "1234")               # knob labels; the bars are columns
        for i in range(4):
            self.assertEqual(self.bar_fill(3, 32 * i + 7, 24, 0x7e), 11)   # 64/127 of 22
        self.assertEqual(ctypes.c_uint.in_dll(L, "host_flushes").value, 1)
        self.assertEqual(ctypes.c_uint.in_dll(L, "host_gate_bad").value, 0)
        dirty = arr(L, "host_dirty", ctypes.c_ubyte, 4)
        self.assertEqual(dirty[0] & 0b1001, 0b1001)     # pages 0 and 3

        L.host_reset()
        L.host_tick()                                   # nothing changed: no draw, no flush
        self.assertEqual(ops(L), [])
        self.assertEqual(ctypes.c_uint.in_dll(L, "host_flushes").value, 0)

        self.usb(True)
        L.host_sent(21, 127)
        L.host_reset()
        L.host_tick()
        text, big = lines(self.shot("ctl_fs2_on"))
        self.assertEqual(text[0], "MIDI CH1 USB     CC21")
        self.assertEqual(big, [(0, 10, "FS2"), (45, 10, "ON")])

        L.host_sent(24, 0)
        L.host_reset()
        L.host_tick()
        _, big = lines(self.shot("ctl_b3_off"))
        self.assertEqual(big, [(0, 10, "B3"), (45, 10, "OFF")])

        L.host_knob(1, 127)
        L.host_sent(41, 127)
        L.host_reset()
        L.host_tick()
        text, big = lines(self.shot("ctl_k2"))
        self.assertEqual(big, [(0, 10, "K2"), (36, 10, "127")])
        self.assertEqual(self.bar_fill(1, 72, 56, 0xf0), 54)     # full value bar
        self.assertEqual(self.bar_fill(3, 32 + 7, 24, 0x7e), 22)  # K2 bar full
        self.assertEqual(self.bar_fill(3, 7, 24, 0x7e), 11)

        L.host_sent(11, 0)
        L.host_reset()
        L.host_tick()
        _, big = lines(self.shot("ctl_exp"))
        self.assertEqual(big, [(0, 10, "EXP"), (36, 10, "  0")])
        self.assertEqual(self.bar_fill(1, 72, 56, 0xf0), 0)

        L.host_knob(2, 0)                               # a knob move alone repaints
        L.host_reset()
        L.host_tick()
        self.assertEqual(ctypes.c_uint.in_dll(L, "host_flushes").value, 1)
        self.assertEqual(self.bar_fill(3, 64 + 7, 24, 0x7e), 0)

    def test_hold_prompt(self):
        L = self.lib
        L.host_set_mode(1)
        self.usb(True)
        ctypes.c_uint.in_dll(L, "host_hold").value = 1999
        L.host_tick()
        L.host_reset()
        ctypes.c_uint.in_dll(L, "host_hold").value = 2000
        L.host_tick()
        _, big = lines(self.shot("ctl_hold"))
        self.assertEqual(big, [(0, 10, "LET GO=EFFECTS")])
        ctypes.c_uint.in_dll(L, "host_hold").value = 0

    def test_tx_stall_indicator(self):
        L = self.lib
        L.host_set_mode(1)
        self.usb(True)
        arr(L, "host_tx4", ctypes.c_uint, 16)[5] = 3
        for _ in range(19):
            L.host_tick()
        L.host_reset()
        L.host_tick()                                   # 20th consecutive tick
        text, _ = lines(self.shot("ctl_stall"))
        self.assertTrue(text[0].startswith("MIDI CH1 STALL"), text[0])
        arr(L, "host_tx4", ctypes.c_uint, 16)[5] = 0
        L.host_reset()
        L.host_tick()                                   # drains: back to OK at once
        text, _ = lines(ops(L))
        self.assertTrue(text[0].startswith("MIDI CH1 USB"), text[0])

    def test_pend_contract(self):
        L = self.lib
        res = arr(L, "host_pend_results", ctypes.c_uint, 8)
        # infinite wait: timeouts are absorbed, the first real event is returned
        L.host_set_mode(0)
        L.host_reset()
        res[0], res[1], res[2] = 0, 0, 0x24
        self.assertEqual(L.host_pend(-1), 0x24)
        self.assertEqual(ops(L), [])                    # stock mode never draws
        L.host_set_mode(1)
        L.host_reset()
        res[0], res[1], res[2] = 0, 0, 0x01
        self.assertEqual(L.host_pend(-1), 0x01)
        self.assertEqual(L.host_repaint(), 1)          # stock may have drawn: repaint next
        # a finite wait is passed through, including its 0 (timeout) result
        L.host_reset()
        res[0] = 0
        self.assertEqual(L.host_pend(100), 0)

    def test_leaving_midi_mode_requests_one_stock_redraw(self):
        L = self.lib
        res = arr(L, "host_pend_results", ctypes.c_uint, 8)
        L.host_set_mode(0)
        L.host_ui_mode(0)                               # MainApp left MIDI mode
        L.host_reset()
        res[0], res[1] = 0, 0x24
        self.assertEqual(L.host_pend(-1), 0x01)         # bit 0: full stock redraw
        self.assertEqual(ops(L), [])                    # drawn by stock, not by us
        L.host_reset()
        res[0], res[1] = 0, 0x24
        self.assertEqual(L.host_pend(-1), 0x24)         # only once
        L.host_ui_mode(1)                               # entering MIDI mode
        self.assertEqual(L.host_repaint(), 1)

    def test_slide_geometry(self):
        """ENTER: the new frame enters at the right edge and pushes the old one
        left; LEAVE mirrors it. Every page row moves together."""
        L = self.lib
        for n in (0, 22, 100, 128):
            L.host_slide_frame(1, n)                    # ANIM_ENTER
            lcd = self.lcd()
            for page in range(4):
                row = lcd[page * 128:(page + 1) * 128]
                want = [x + n if x + n < 128 else 0x80 | (x + n - 128) for x in range(128)]
                self.assertEqual(list(row), want, (n, page))
            L.host_slide_frame(2, n)                    # ANIM_LEAVE
            row = self.lcd()[:128]
            want = [0x80 | (x + 128 - n) if x < n else x - n for x in range(128)]
            self.assertEqual(list(row), want, n)
        self.assertEqual(arr(L, "host_dirty", ctypes.c_ubyte, 4)[0], 0x0f)

    def test_entering_midi_mode_slides_then_repaints(self):
        L = self.lib
        res = arr(L, "host_pend_results", ctypes.c_uint, 8)
        stock = bytes((7 * i) & 0xff for i in range(512))
        arr(L, "host_lcd", ctypes.c_ubyte, 512)[:] = list(stock)
        L.host_set_mode(1)
        L.host_ui_mode(1)
        L.host_tick()                                   # compose + slide frame 0
        self.assertEqual(L.host_anim_dir(), 1)
        self.assertEqual(ctypes.c_uint.in_dll(L, "host_flushes").value, 1)
        self.assertEqual(self.lcd()[:128 - 22], stock[22:128])   # stock pushed left
        L.host_reset()
        L.host_ui_mode(1)                               # reset cleared it; re-arm
        L.host_tick()
        for k in range(6):
            res[k] = 0                                  # timeouts drive the frames
        res[6] = 0x24
        self.assertEqual(L.host_pend(-1), 0x24)
        self.assertEqual(L.host_anim_dir(), 0)          # 6 more frames: done
        self.assertEqual(ctypes.c_uint.in_dll(L, "host_flushes").value, 1 + 6)
        self.assertEqual(L.host_repaint(), 1)           # live page painted next

    def test_leaving_midi_mode_slides_stock_screen_in(self):
        L = self.lib
        res = arr(L, "host_pend_results", ctypes.c_uint, 8)
        L.host_set_mode(0)
        L.host_ui_mode(0)
        res[0] = 0
        self.assertEqual(L.host_pend(-1), 0x01)         # stock redraws first
        self.assertEqual(L.host_anim_req(), 2)          # MIDI page saved
        ctypes.c_uint.in_dll(L, "host_pend_count").value = 0
        ctypes.c_uint.in_dll(L, "host_flushes").value = 0
        for k in range(6):
            res[k] = 0
        res[6] = 0x24
        self.assertEqual(L.host_pend(-1), 0x24)         # 7 frames, then the event
        self.assertEqual(ctypes.c_uint.in_dll(L, "host_flushes").value, 7)
        self.assertEqual(L.host_anim_dir(), 0)

    def test_text_fits_the_panel(self):
        L = self.lib
        L.host_set_mode(1)
        self.usb(True)
        L.host_sent(119, 127)
        L.host_reset()
        L.host_tick()
        for op, a, b, c, s in ops(L):
            if op == 2:
                self.assertLessEqual(c + 6, 128)
            if op == 3:
                self.assertLessEqual(a + 9 * len(s), 128, s)


class DiagUi(unittest.TestCase):
    def test_diag_screen(self):
        lib = load("ui_host_harness_diag.c", "ctl_ui_diag_HOST_TEST_ONLY")
        lib.host_reset()
        lib.host_set_mode(1)
        ctypes.c_uint.in_dll(lib, "host_ticks").value = 123456
        p = arr(lib, "host_port", ctypes.c_uint, 16)
        p[3], p[9] = 1, 1
        lib.host_sent(40, 64)
        lib.host_tick()
        rec = ops(lib)
        if RES1.exists():
            OUT.mkdir(parents=True, exist_ok=True)
            ui_mock.show(render(rec, RES1.read_bytes())).save(OUT / "fw_diag.png")
        text, big = lines(rec)
        self.assertEqual(text[0], "CLAUDE W#2 t123456")
        self.assertEqual(text[1], "STACK 768/2048")
        self.assertEqual(text[2], "USB OK q0 F0x0 TD1")
        self.assertEqual(text[3], "b7 s1 CC40=64")
        self.assertEqual(big, [])
        lib.host_reset()
        lib.host_tick()                                 # diag repaints every tick (live counter)
        self.assertEqual(ctypes.c_uint.in_dll(lib, "host_flushes").value, 1)


if __name__ == "__main__":
    unittest.main()


import re  # noqa: E402
import struct  # noqa: E402
import make_controller_fw as ctl  # noqa: E402
import make_fs_restore_updater as packager  # noqa: E402

MAIN_DIS = ROOT / "build" / "fw" / "map" / "main.dis"


class UiHook(unittest.TestCase):
    def test_ui_hook_is_not_in_lifecycle_hooks(self):
        self.assertNotIn(0xc013c76c, {h[0] for h in ctl.HOOKS})
        self.assertEqual(len(ctl.HOOKS), 7)

    @unittest.skipUnless(MAIN_DIS.exists(), "stock disassembly not available")
    def test_ui_site_is_updateui_infinite_pend(self):
        text = MAIN_DIS.read_text(errors="replace")
        # the wait is called with timeout -1 (B6) and orMask 255 (A6) on B14[139]
        for pat in (r"^c013c764\s+\S+\s+MVK\.L2\s+-1,B6",
                    r"^c013c766\s+\S+\s+MVK\.S1\s+255,A6",
                    r"^c013c768\s+\S+\s+\|\|\s+LDW\.D2T1\s+\*\+B14\[139\],A4",
                    r"^c013c76c\s+100fc413\s+\|\|\s+CALLP\.S2\s+0xc0144580,B3",
                    # flush path mirrored from UpdateUI's own render
                    r"^c013c72c\s+\S+\s+CALLP\.S2\s+0xc0161200,B3",
                    r"^c013c740\s+\S+\s+\|\|\s+CALLP\.S2\s+0xc016df00,B3",
                    r"^c013c744\s+\S+\s+CALLP\.S2\s+0xc016d880,B3",
                    # 5x7 glyph: A6 is the page (SHL 7), B6 the x column
                    r"^c011d330\s+\S+\s+SHL\.S2\s+B1,0x7,B2",
                    # 8x13 string advances x (A6) by 9
                    r"^c011ec68\s+\S+\s+ADD\.L1\s+9,A22,A22"):
            self.assertRegex(text, "(?m)" + pat)

    @unittest.skipUnless(RES1.exists() and ctl.CGT.exists(), "stock res1 or TI CGT not available")
    def test_ui_build_hooks_and_packager_accepts_it_without_diag(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "ui.bin"
            ctl.build(str(RES1), str(out), str(RES1), ui=True)
            data, stock = out.read_bytes(), RES1.read_bytes()
            _, _, syms = ctl.elf_image(ctl.OUT / "ui" / "controller.elf")
            vma, off, word0, _, sym = ctl.UI_HOOKS[0]
            word = struct.unpack_from("<I", data, off)[0]
            self.assertEqual(ctl.callp_target(vma, word), syms[sym])
            keep = ~(0x1fffff << 7) & 0xffffffff
            self.assertEqual(word & keep, word0 & keep)         # p-bit and unit kept
            packager.validate_controller_fw(stock, data)        # release: the screen hook is allowed
            packager.validate_controller_fw(stock, data, test=True)
            bad = bytearray(data)
            bad[0x30000] ^= 1                                    # any other stock byte
            with self.assertRaises(ValueError):
                packager.validate_controller_fw(stock, bytes(bad), test=True)
            ctl.build(str(RES1), str(out), str(RES1), diag=True, ui=True)
            packager.validate_controller_fw(stock, out.read_bytes(), test=True)
            with self.assertRaises(ValueError):                 # diag hooks stay TEST-only
                packager.validate_controller_fw(stock, out.read_bytes())
            bad = bytearray(data)
            bad[off] ^= 1 << 3                                   # screen hook: opcode bits changed
            with self.assertRaises(ValueError):
                packager.validate_controller_fw(stock, bytes(bad))

    def test_test_package_needs_test_in_name(self):
        with self.assertRaises(SystemExit):
            packager.main("in.exe", "out.exe", test_controller_fw="x.bin")
