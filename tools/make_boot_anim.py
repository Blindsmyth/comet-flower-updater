#!/usr/bin/env python3
"""Comet Flower start-up animation: frames, preview and the firmware table.

  python tools/make_boot_anim.py [--gif build/boot_anim.gif] [--header firmware/controller/boot_anim.h]

Draws BOOT_FRAMES 128x32 1-bit frames of a flower blooming (stem, bud, petals
opening with a slight twist, then "COMET / FLOWER" letter by letter) and writes
  - the header for firmware/controller/cf_boot.c: every frame in LCD page format
    (4 pages x 128 columns, bit 0 = top row, as make_fs_restore_updater.splash_bytes),
    run-length coded: token t < 0x80 = t + 1 literal bytes follow, t >= 0x80 =
    (t & 0x7f) + 1 zero bytes;
  - a 4x GIF preview;
  - the boot program's logo (--boot-logo, 92x16 for tools/make_boot_logo_updater.py): frame
    BOOT_FIRST cropped to the logo box (x 18..109, y 8..23), so the main firmware's bloom
    (cf_boot.c, frames BOOT_FIRST..) appears to continue from it.
The decoder in cf_boot.c and rle_decode() below must stay the same.
"""
import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from make_splash import FONT  # noqa: E402

W, H = 128, 32
CX, CY = 22, 13            # flower centre
PETALS = 6
FRAME_MS = 70              # cf_boot.c FRAME_CYCLES: 70 ms per frame


def petal(d, ang, length, width):
    pts = []
    for k in range(24):
        t = 2 * math.pi * k / 24
        u, v = length * math.cos(t), width * math.sin(t)
        x, y = d + u, v
        pts.append((CX + x * math.cos(ang) - y * math.sin(ang), CY + x * math.sin(ang) + y * math.cos(ang)))
    return pts


def text(dr, s, x0, y0, scale=2):
    for i, ch in enumerate(s):
        for r, row in enumerate(FONT[ch]):
            for c, p in enumerate(row):
                if p == "#":
                    x, y = x0 + (6 * i + c) * scale, y0 + r * scale
                    dr.rectangle([x, y, x + scale - 1, y + scale - 1], fill=255)


def frame(n):
    im = Image.new("L", (W, H), 0)
    dr = ImageDraw.Draw(im)
    stem_top = 31 - min(n + 1, 4) * 4                     # frames 0..3: the stem grows
    dr.line([(CX, 31), (CX, max(stem_top, CY + 2))], fill=255)
    if n >= 2:                                            # leaves
        dr.polygon([(CX, 27), (CX - 6, 23), (CX - 2, 27)], outline=255)
    if n >= 3:
        dr.polygon([(CX, 25), (CX + 6, 21), (CX + 2, 25)], outline=255)
    if 4 <= n <= 5:                                       # bud
        r = n - 2
        dr.ellipse([CX - r, CY - r - 1, CX + r, CY + r], outline=255, fill=255)
    if n >= 6:                                            # petals open, 6 frames
        k = min(n - 6, 5) / 5.0
        size = 2 + 8 * k
        twist = 0.6 * (1 - k)
        for p in range(PETALS):
            ang = twist + 2 * math.pi * p / PETALS - math.pi / 2
            dr.polygon(petal(size * 0.55 + 1, ang, size * 0.55, 1 + 2.2 * k), fill=0, outline=255)
        rc = 1 + round(1.5 * k)
        dr.ellipse([CX - rc, CY - rc, CX + rc, CY + rc], fill=255)
    if n >= 12:                                           # name, letter by letter
        shown = min(11, 3 * (n - 11))
        top, bottom = "COMET", "FLOWER"
        text(dr, top[:min(shown, 5)], 50, 1)
        text(dr, bottom[:max(0, shown - 5)], 44, 17)
    return im.point(lambda v: 255 if v >= 128 else 0)


BOOT_FRAMES = 16
BOOT_FIRST = 4             # the bud; must match cf_boot.c BOOT_FIRST
LOGO_BOX = (18, 8, 18 + 92, 8 + 16)


def boot_logo():
    return frame(BOOT_FIRST).crop(LOGO_BOX)


def pages(im):
    out = bytearray(W * H // 8)
    for page in range(H // 8):
        for x in range(W):
            v = 0
            for bit in range(8):
                if im.getpixel((x, page * 8 + bit)):
                    v |= 1 << bit
            out[page * W + x] = v
    return bytes(out)


def rle_encode(data):
    out, i = bytearray(), 0
    while i < len(data):
        if data[i] == 0:
            n = 1
            while i + n < len(data) and data[i + n] == 0 and n < 128:
                n += 1
            out.append(0x80 | (n - 1))
        else:
            n = 1
            while i + n < len(data) and n < 128 and not (data[i + n] == 0 and i + n + 1 < len(data)
                                                         and data[i + n + 1] == 0):
                n += 1
            out.append(n - 1)
            out += data[i:i + n]
        i += n
    return bytes(out)


def rle_decode(code, size=512):
    out, i = bytearray(), 0
    while len(out) < size:
        t = code[i]
        i += 1
        if t & 0x80:
            out += b"\0" * ((t & 0x7F) + 1)
        else:
            out += code[i:i + t + 1]
            i += t + 1
    if len(out) != size:
        raise ValueError("frame decodes to %d bytes" % len(out))
    return bytes(out), i


def build():
    frames = [frame(n) for n in range(BOOT_FRAMES)]
    raw = [pages(f) for f in frames]
    codes = [rle_encode(r) for r in raw]
    for r, c in zip(raw, codes):
        assert rle_decode(c)[0] == r
    return frames, raw, codes


def header(codes):
    offs, blob = [], bytearray()
    for c in codes:
        offs.append(len(blob))
        blob += c
    lines = ["/* Generated by tools/make_boot_anim.py: do not edit. %d frames, %d bytes coded"
             " (%d raw). */" % (len(codes), len(blob), 512 * len(codes)),
             "#define BOOT_NFRAMES %du" % len(codes),
             "static const unsigned short boot_off[BOOT_NFRAMES] = { %s };" % ", ".join(map(str, offs)),
             "static const unsigned char boot_rle[%d] = {" % len(blob)]
    for i in range(0, len(blob), 16):
        lines.append("    " + ", ".join("0x%02x" % b for b in blob[i:i + 16]) + ",")
    lines.append("};")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gif", default=str(ROOT / "build/boot_anim.gif"))
    ap.add_argument("--header", default=str(ROOT / "firmware/controller/boot_anim.h"))
    ap.add_argument("--boot-logo", default=str(ROOT / "assets/boot_logo_bud.png"))
    a = ap.parse_args(argv)
    frames, raw, codes = build()
    Path(a.header).write_text(header(codes), encoding="utf-8")
    boot_logo().convert("1").save(a.boot_logo)
    # preview as on the pedal: the boot logo (bud in the logo box), then frames BOOT_FIRST..
    bud = Image.new("L", (W, H), 0)
    bud.paste(boot_logo(), LOGO_BOX[:2])
    seq = [bud] * 8 + frames[BOOT_FIRST:]
    big = [f.convert("L").resize((W * 4, H * 4), Image.NEAREST) for f in seq]
    big[0].save(a.gif, save_all=True, append_images=big[1:] + [big[-1]] * 12,
                duration=FRAME_MS, loop=0)
    print("%d frames, %d bytes coded (%d raw) -> %s, preview %s"
          % (len(codes), sum(map(len, codes)), sum(map(len, raw)), a.header, a.gif))


if __name__ == "__main__":
    main()
