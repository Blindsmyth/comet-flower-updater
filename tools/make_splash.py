#!/usr/bin/env python3
"""Start-up screen with the build number, for make_fs_restore_updater.py --splash.

  python tools/make_splash.py <version> <out.png> [--title CF-ZGX4] [--tag TEST]

Draws a 128x32 1-bit PNG: the title in a 5x7 pixel font at double size on top,
"<tag> <version>" at normal size below (e.g. "TEST 0.34.1"). Our firmware blanks
the stock "v2.0" text (g1fw_text.py version ""), so nothing is drawn over it.

Version scheme: 0.<updater number>.<rebuild>, e.g. Updater 34b = 0.34.1.
"""
import sys

from PIL import Image

W, H = 128, 32

# 5x7 glyphs, one string per row, '#' = lit
FONT = {
    "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": ["#####", "   # ", "  #  ", "   # ", "    #", "#   #", " ### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": ["  ## ", " #   ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "   # ", " ##  "],
    "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "],
    "D": ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "G": [" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ####"],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "I": [" ### ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "J": ["  ###", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "#   #", "##  #", "# # #", "#  ##", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "# # #", " # # "],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    "-": ["     ", "     ", "     ", "#####", "     ", "     ", "     "],
    ".": ["     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "],
    " ": ["     "] * 7,
}


def text_width(s, scale):
    return (6 * len(s) - 1) * scale


def draw(px, s, x0, y0, scale):
    for i, ch in enumerate(s):
        for r, row in enumerate(FONT[ch]):
            for c, p in enumerate(row):
                if p == "#":
                    for dy in range(scale):
                        for dx in range(scale):
                            px[x0 + (6 * i + c) * scale + dx, y0 + r * scale + dy] = 255


def make(version, title="CF-ZGX4", tag="TEST"):
    lines = [(title.upper(), 2, 1), (("%s %s" % (tag, version)).strip().upper(), 1, 22)]
    im = Image.new("L", (W, H), 0)
    px = im.load()
    for s, scale, y in lines:
        bad = sorted(set(s) - set(FONT))
        if bad:
            sys.exit("no glyph for %r" % "".join(bad))
        w = text_width(s, scale)
        if w > W:
            sys.exit("%r is %d px wide, the screen is %d" % (s, w, W))
        draw(px, s, (W - w) // 2, y, scale)
    return im.convert("1")


def main(a):
    opts = {"--title": "CF-ZGX4", "--tag": "TEST"}
    for k in list(opts):
        if k in a:
            i = a.index(k)
            opts[k] = a[i + 1]
            del a[i:i + 2]
    if len(a) != 2:
        sys.exit(__doc__)
    make(a[0], opts["--title"], opts["--tag"]).save(a[1])
    print("splash %s -> %s" % (a[0], a[1]))


if __name__ == "__main__":
    main(sys.argv[1:])
