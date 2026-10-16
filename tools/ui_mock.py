"""Offline mock-ups of on-pedal status screens, drawn with the pedal's own fonts.

The G1X Four LCD is 128x32, 1 bit, page format (recon/10). This renders a screen
spec with glyphs decoded straight from the v2.00 firmware, so a mock-up shows
exactly the pixels the firmware fonts would produce. It is for design review before
any drawing hook exists (docs/ONDEVICE_UI_2026-10-15.md); nothing here touches the pedal.

    python tools/ui_mock.py [res1.bin] [out_dir]

A spec is a list of items:
    ("text", font, x, y, string)   glyph cells left to right; y should be a page multiple of 8
    ("bar", x, y, w, h, frac)      outlined bar filled to frac (0..1)
    ("invert", x, y, w, h)         invert a rectangle (highlight)
    ("bitmap", addr, x, y, w, h)   a stock bitmap from the firmware (g1fw_gfx.BITMAPS)
    ("columns", data)              raw page buffer (4 pages x 128 column bytes, bit 0 on top)
"""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import g1fw_gfx as gfx  # noqa: E402

W, H = 128, 32
ROOT = Path(__file__).resolve().parent.parent
RES1 = ROOT / "build" / "fw" / "res1_493412.bin"


class Fonts:
    def __init__(self, buf):
        self.buf = buf

    def glyph(self, font, ch):
        a, w, pages, first, n, order = gfx.FONTS[font]
        if order is None:
            idx = ord(ch) - first
        else:
            idx = order.find(ch)
        if ch == " " or not 0 <= idx < n:
            return None, w, pages * 8     # blank cell (the big fonts have no space glyph)
        return gfx.decode(self.buf, gfx.a2f(a) + idx * w * pages, w, pages), w, pages * 8


def render(spec, buf):
    fonts = Fonts(buf)
    im = Image.new("1", (W, H), 0)
    px = im.load()
    for item in spec:
        kind = item[0]
        if kind == "text":
            _, font, x, y, s = item
            for ch in s:
                g, w, h = fonts.glyph(font, ch)
                if g is not None:
                    gp = g.load()
                    for cx in range(w):
                        for cy in range(h):
                            if gp[cx, cy] and 0 <= x + cx < W and 0 <= y + cy < H:
                                px[x + cx, y + cy] = 1
                x += w
        elif kind == "bar":
            _, x, y, w, h, frac = item
            fill = round((w - 2) * max(0.0, min(1.0, frac)))
            for cx in range(w):
                for cy in range(h):
                    edge = cx in (0, w - 1) or cy in (0, h - 1)
                    if edge or cx - 1 < fill:
                        px[x + cx, y + cy] = 1
        elif kind == "columns":
            data = item[1]
            for i, b in enumerate(data[:W * H // 8]):
                for bit in range(8):
                    if b >> bit & 1:
                        px[i % W, (i // W) * 8 + bit] = 1
        elif kind == "invert":
            _, x, y, w, h = item
            for cx in range(x, min(W, x + w)):
                for cy in range(y, min(H, y + h)):
                    px[cx, cy] ^= 1
        elif kind == "bitmap":
            _, addr, x, y, w, h = item
            g = gfx.decode(buf, gfx.a2f(addr), w, (h + 7) // 8).load()
            for cx in range(w):
                for cy in range(h):
                    if g[cx, cy]:
                        px[x + cx, y + cy] = 1
        else:
            raise ValueError(f"unknown item {kind!r}")
    return im


def show(im, scale=4):
    """Scale up with a pixel grid, lit pixels light on a dark panel."""
    out = Image.new("RGB", (W * scale, H * scale), (18, 22, 26))
    px, op = im.load(), out.load()
    for x in range(W):
        for y in range(H):
            if px[x, y]:
                for dx in range(scale - 1):
                    for dy in range(scale - 1):
                        op[x * scale + dx, y * scale + dy] = (225, 240, 255)
    return out


# Proposed screens (docs/ONDEVICE_UI_2026-10-15.md). Text must fit 21 cells of font_5x7.
SCREENS = {
    "ctl_entry": [
        ("text", "font_14x18", 1, 0, "MIDI-CTRL"),
        ("text", "font_5x7", 4, 24, "CH 1   USB MIDI MODE"),
    ],
    "ctl_waiting": [
        ("text", "font_5x7", 0, 0, "MIDI CTRL       CH 1"),
        ("invert", 0, 0, 128, 8),
        ("text", "font_8x13", 0, 12, "USB: WAITING"),
        ("text", "font_5x7", 0, 24, "connect to a computer"),
    ],
    "ctl_last_cc": [
        ("text", "font_5x7", 0, 0, "MIDI CTRL  USB OK CH1"),
        ("invert", 0, 0, 128, 8),
        ("text", "font_11x13", 0, 8, "CC11 EXP"),
        ("text", "font_11x13", 106, 8, "96"),
        ("bar", 0, 26, 128, 6, 96 / 127),
    ],
    "ctl_footswitch": [
        ("text", "font_5x7", 0, 0, "MIDI CTRL  USB OK CH1"),
        ("invert", 0, 0, 128, 8),
        ("text", "font_11x13", 0, 8, "CC20 FS1"),
        ("text", "font_11x13", 106, 8, "ON"),
        ("text", "font_5x7", 0, 24, "127   sent 1,204 CCs"),
    ],
    "ctl_tx_stalled": [
        ("text", "font_5x7", 0, 0, "MIDI CTRL       CH 1"),
        ("text", "font_8x13", 0, 8, "USB TX STALLED"),
        ("invert", 0, 8, 128, 16),
        ("text", "font_5x7", 0, 24, "replug USB; 37 queued"),
    ],
    "audio_streaming": [
        ("text", "font_5x7", 0, 0, "USB AUDIO  44.1k 16b"),
        ("invert", 0, 0, 128, 8),
        ("text", "font_8x13", 0, 8, "STREAMING"),
        ("text", "font_5x7", 0, 24, "underruns 0  fill 50%"),
        ("bar", 96, 10, 32, 10, 0.5),
    ],
    "audio_idle": [
        ("text", "font_5x7", 0, 0, "USB AUDIO  44.1k 16b"),
        ("invert", 0, 0, 128, 8),
        ("text", "font_8x13", 0, 8, "IDLE"),
        ("text", "font_5x7", 0, 24, "waiting for the host"),
    ],
    "diag_readout": [
        ("text", "font_5x7", 0, 0, "DIAG  worker #2"),
        ("text", "font_5x7", 0, 8, "STACK  768 / 2048"),
        ("text", "font_5x7", 0, 16, "TX4 out 0  fault 0x0"),
        ("text", "font_5x7", 0, 24, "teardown 1  ring 3"),
    ],
}


def overflows():
    """Text items that run past the 128-pixel width."""
    bad = []
    for name, spec in SCREENS.items():
        for it in spec:
            if it[0] == "text" and it[2] + gfx.FONTS[it[1]][1] * len(it[4]) > W:
                bad.append((name, it[4]))
    return bad


def main(argv):
    res1 = Path(argv[1]) if len(argv) > 1 else RES1
    out = Path(argv[2]) if len(argv) > 2 else ROOT / "build" / "ui_mock"
    out.mkdir(parents=True, exist_ok=True)
    buf = res1.read_bytes()
    for name, spec in SCREENS.items():
        show(render(spec, buf)).save(out / f"{name}.png")
    print(f"wrote {len(SCREENS)} screens to {out}")


if __name__ == "__main__":
    main(sys.argv)
