#!/usr/bin/env python3
"""Export and re-import the G1X Four main firmware's fonts and screen bitmaps.

  python tools/g1fw_gfx.py export <res1.bin> <dir>
  python tools/g1fw_gfx.py import <res1.bin> <dir> <out_res1.bin>
  python tools/g1fw_gfx.py selftest <res1.bin>

<res1.bin> is the main firmware (updater resource 0x81, build/fw/res1_493412.bin).
`export` writes one PNG per font (a glyph sheet) and one per bitmap, white =
lit pixel. Edit them in any paint program, keeping the size and the grey grid
lines, then `import` re-encodes every PNG into a copy of the firmware. Only
bytes inside the known assets can change; everything else is checked to be
identical. Put the result on the pedal with
`tools/make_fs_restore_updater.py ... --firmware <out_res1.bin>`.

Where the assets come from (recon/10):
  * fonts: the glyph routines at 0xc011e2c0..0xc011eb40 and the font
    pointers at 0xc01654a4 / 0xc0137xxx, with the cell sizes they pass to the
    bitmap routine 0xc011c508(ctx, x, y, w, h, ptr);
  * bitmaps: every call of 0xc011c508 with a constant pointer, width and
    height (build/fw/map/bitmap_calls.txt): 54 found, 51 kept (two
    overlap, one has an unsure size).
Storage is LCD page format: for each 8-pixel page, w column bytes, LSB = top.
"""
import os
import sys

from PIL import Image

SEC_ADDR, SEC_FILE, SEC_SIZE = 0xc016f780, 0x63708, 0x123a4   # const data section

# name: (address of glyph `first`, width, pages, first char, count, char order)
#   order None = consecutive codes from `first`; otherwise the string of chars
ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
FONTS = {
    "font_5x7":   (0xc01788a0, 6, 1, 0x20, 95, None),
    "font_bold7": (0xc01783b0, 7, 1, 0x20, 95, None),
    "font_8x13":  (0xc0177180, 8, 2, 0x20, 95, None),
    "font_11x13": (0xc0176250, 11, 2, 0x20, 95, None),
    "font_14x18": (0xc01757f8, 14, 3, None, 63, ALNUM + "-"),
    "font_16x21": (0xc0174170, 16, 3, None, 62, ALNUM),
    "font_25x40": (0xc0172fd8, 25, 5, None, 36, "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"),
}

# (address, width, height) of each bitmap drawn through 0xc011c508
BITMAPS = [
    (0xc0178ae0, 128, 32),
    (0xc0178ce0, 128, 32),
    (0xc0178ee0, 128, 32),
    (0xc01790e0, 128, 32),
    (0xc01792e0, 128, 32),
    (0xc01796e0, 128, 32),
    (0xc01798e0, 128, 32),
    (0xc017a458, 128, 21),
    (0xc017a8d8, 128, 20),
    (0xc017b3a8, 128, 9),
    (0xc017b4a8, 128, 12),
    (0xc017b858, 101, 15),
    (0xc017bf38, 92, 16),
    (0xc017d3f8, 128, 8),
    (0xc017d478, 128, 8),
    (0xc017d9f8, 60, 11),
    (0xc017ecc8, 24, 32),
    (0xc017f268, 31, 18),
    (0xc01802e8, 17, 20),
    (0xc0180320, 50, 5),
    (0xc0180718, 22, 12),
    (0xc0180748, 22, 12),
    (0xc01807d0, 40, 5),
    (0xc01807f8, 18, 7),
    (0xc01808c0, 13, 20),
    (0xc0180c38, 33, 7),
    (0xc0180f40, 10, 17),
    (0xc0180f60, 10, 17),
    (0xc01810b8, 25, 7),
    (0xc01811e0, 22, 20),
    (0xc0181270, 7, 19),
    (0xc01812c8, 10, 15),
    (0xc01812e0, 10, 15),
    (0xc01812f8, 10, 15),
    (0xc0181310, 10, 15),
    (0xc01813f0, 18, 7),
    (0xc0181438, 17, 7),
    (0xc01815a8, 15, 7),
    (0xc01815b8, 15, 7),
    (0xc01815d8, 15, 7),
    (0xc01815e8, 15, 7),
    (0xc0181628, 14, 6),
    (0xc01816c0, 9, 6),
    (0xc01817c0, 4, 9),
    (0xc01817c8, 4, 9),
    (0xc01818b0, 4, 9),
    (0xc01818b8, 3, 9),
    (0xc0181908, 5, 3),
    (0xc0181918, 5, 8),
    (0xc0181920, 5, 7),
    (0xc0181a68, 2, 5),
]
GRID = 1          # grey separator between glyphs in a sheet
PER_ROW = 16


def a2f(a):
    return a - SEC_ADDR + SEC_FILE


def decode(buf, o, w, pages):
    im = Image.new("L", (w, pages * 8), 0)
    px = im.load()
    for p in range(pages):
        for c in range(w):
            b = buf[o + p * w + c]
            for bit in range(8):
                if b >> bit & 1:
                    px[c, p * 8 + bit] = 255
    return im


def encode(im, w, pages):
    px = im.load()
    out = bytearray(w * pages)
    for p in range(pages):
        for c in range(w):
            v = 0
            for bit in range(8):
                if px[c, p * 8 + bit] >= 128:
                    v |= 1 << bit
            out[p * w + c] = v
    return bytes(out)


def assets():
    """Yield (name, file offset, byte length, kind, params)."""
    for name, (a, w, pg, first, n, order) in FONTS.items():
        yield name, a2f(a), w * pg * n, "font", (w, pg, n)
    for a, w, h in BITMAPS:
        yield "bmp_%08x_%dx%d" % (a, w, h), a2f(a), w * ((h + 7) // 8), "bmp", (w, (h + 7) // 8)


def check_layout():
    spans = sorted((o, o + n, name) for name, o, n, _, _ in assets())
    for (a0, a1, n0), (b0, b1, n1) in zip(spans, spans[1:]):
        if b0 < a1:
            sys.exit("assets overlap: %s and %s" % (n0, n1))
    for o0, o1, name in spans:
        if not (SEC_FILE <= o0 and o1 <= SEC_FILE + SEC_SIZE):
            sys.exit("%s lies outside the const section" % name)


def sheet(buf, o, w, pg, n):
    ch = pg * 8
    rows = (n + PER_ROW - 1) // PER_ROW
    im = Image.new("L", (PER_ROW * (w + GRID) + GRID, rows * (ch + GRID) + GRID), 128)
    for g in range(n):
        x, y = GRID + (g % PER_ROW) * (w + GRID), GRID + (g // PER_ROW) * (ch + GRID)
        im.paste(decode(buf, o + g * w * pg, w, pg), (x, y))
    return im


def unsheet(im, w, pg, n):
    ch = pg * 8
    out = b""
    for g in range(n):
        x, y = GRID + (g % PER_ROW) * (w + GRID), GRID + (g // PER_ROW) * (ch + GRID)
        out += encode(im.crop((x, y, x + w, y + ch)), w, pg)
    return out


def export(src, d):
    buf = open(src, "rb").read()
    check_layout()
    os.makedirs(d, exist_ok=True)
    for name, o, n, kind, prm in assets():
        im = sheet(buf, o, *prm) if kind == "font" else decode(buf, o, *prm)
        im.save(os.path.join(d, name + ".png"))
    print("exported %d fonts and %d bitmaps to %s" % (len(FONTS), len(BITMAPS), d))


def import_(src, d, dst=None):
    buf = bytearray(open(src, "rb").read())
    orig = bytes(buf)
    check_layout()
    changed = []
    for name, o, n, kind, prm in assets():
        p = os.path.join(d, name + ".png")
        if not os.path.exists(p):
            continue
        im = Image.open(p).convert("L")
        ref = sheet(orig, o, *prm) if kind == "font" else decode(orig, o, *prm)
        if im.size != ref.size:
            sys.exit("%s is %s, must be %s" % (p, im.size, ref.size))
        new = unsheet(im, *prm) if kind == "font" else encode(im, *prm)
        assert len(new) == n
        if new != orig[o:o + n]:
            changed.append(name)
        buf[o:o + n] = new
    spans = [(o, o + n) for _, o, n, _, _ in assets()]
    for i, (x, y) in enumerate(zip(orig, buf)):
        if x != y and not any(a <= i < b for a, b in spans):
            sys.exit("internal error: byte %#x outside the assets changed" % i)
    if dst:
        open(dst, "wb").write(buf)
        print("wrote %s; changed: %s" % (dst, ", ".join(changed) or "nothing"))
    return bytes(buf)


def selftest(src):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        export(src, d)
        assert import_(src, d) == open(src, "rb").read(), "round trip changed bytes"
    print("selftest: export + import reproduces the firmware byte for byte")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["export"] and len(a) == 3:
        export(a[1], a[2])
    elif a[:1] == ["import"] and len(a) == 4:
        import_(a[1], a[2], a[3])
    elif a[:1] == ["selftest"] and len(a) == 2:
        selftest(a[1])
    else:
        sys.exit(__doc__)
