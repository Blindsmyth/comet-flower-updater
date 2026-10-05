"""Retarget a stomphacks-built (MS Plus) DIY ZD2 for the G1 Four family.

Every value written here is one that stock G1X Four effects carry (87-effect
audit, recon/03_g1x4_corpus_audit.md):

  * target 0x02: the one bit present in every stock G1X Four effect
  * header 0x10 = 01, 0x18 = 80, 0x58 = 01 (slot count): a pattern 21 stock
    effects use
  * ICON: a 1-bpp 24x30 BMP, drawn here from scratch (no stock art)
  * INFO text: the group's label, e.g. "SFXSFX" for group 7
  * trailer zeroed (stock trailers are packer filler, shared across unrelated
    effects), CRC recomputed

The ELF is left untouched. Build it with "kernel_section": "text", because no
stock G1 effect has code in .audio.
"""
import struct

from .parser import HEADER_SIZE, TRAILER_SIZE, parse_zd2, zd2_crc

G1_TARGET = 0x02
GROUP_INFO_TEXT = {
    1: "DYNDYNMCS", 2: "FLTFILTER", 3: "DRVDRIVE", 4: "AMPAMP", 5: "CABCAB.",
    6: "MODMOD.", 7: "SFXSFX", 8: "DLYDELAY", 9: "REVREVERB", 11: "PDLPEDAL",
}

# 3x5 pixel font, rows top to bottom, '#' = set.
FONT = {
    "A": ["###", "#.#", "###", "#.#", "#.#"], "B": ["##.", "#.#", "##.", "#.#", "##."],
    "C": ["###", "#..", "#..", "#..", "###"], "D": ["##.", "#.#", "#.#", "#.#", "##."],
    "E": ["###", "#..", "##.", "#..", "###"], "F": ["###", "#..", "##.", "#..", "#.."],
    "G": ["###", "#..", "#.#", "#.#", "###"], "H": ["#.#", "#.#", "###", "#.#", "#.#"],
    "I": ["###", ".#.", ".#.", ".#.", "###"], "J": ["..#", "..#", "..#", "#.#", "###"],
    "K": ["#.#", "#.#", "##.", "#.#", "#.#"], "L": ["#..", "#..", "#..", "#..", "###"],
    "M": ["#.#", "###", "###", "#.#", "#.#"], "N": ["##.", "#.#", "#.#", "#.#", "#.#"],
    "O": ["###", "#.#", "#.#", "#.#", "###"], "P": ["###", "#.#", "###", "#..", "#.."],
    "Q": ["###", "#.#", "#.#", "###", "..#"], "R": ["##.", "#.#", "##.", "#.#", "#.#"],
    "S": ["###", "#..", "###", "..#", "###"], "T": ["###", ".#.", ".#.", ".#.", ".#."],
    "U": ["#.#", "#.#", "#.#", "#.#", "###"], "V": ["#.#", "#.#", "#.#", "#.#", ".#."],
    "W": ["#.#", "#.#", "###", "###", "#.#"], "X": ["#.#", "#.#", ".#.", "#.#", "#.#"],
    "Y": ["#.#", "#.#", ".#.", ".#.", ".#."], "Z": ["###", "..#", ".#.", "#..", "###"],
    "0": ["###", "#.#", "#.#", "#.#", "###"], "1": [".#.", "##.", ".#.", ".#.", "###"],
    "2": ["###", "..#", "###", "#..", "###"], "3": ["###", "..#", "###", "..#", "###"],
    "4": ["#.#", "#.#", "###", "..#", "..#"], "5": ["###", "#..", "###", "..#", "###"],
    "6": ["###", "#..", "###", "#.#", "###"], "7": ["###", "..#", "..#", "..#", "..#"],
    "8": ["###", "#.#", "###", "#.#", "###"], "9": ["###", "#.#", "###", "..#", "###"],
    " ": ["...", "...", "...", "...", "..."],
}


def icon_pixels(label: str, width: int = 24, height: int = 30) -> list:
    """A generic stompbox: body with two knobs, a gap, and the label knocked
    out of the lower panel. Returns rows top to bottom of 0/1."""
    px = [[0] * width for _ in range(height)]
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            px[y][x] = 1
    for y in (1, height - 2):                     # rounded corners
        px[y][1] = px[y][width - 2] = 0
    for x in range(width):                        # gap between the panels
        px[13][x] = 0
    for cx in (6, width - 7):                     # two knobs, outlined
        for dy, row in enumerate([".###.", "#...#", "#.#.#", "#...#", ".###."]):
            for dx, c in enumerate(row):
                if c == "#":
                    px[5 + dy][cx - 2 + dx] = 0
    text = label.upper()[:5]
    tw = len(text) * 4 - 1
    x0 = (width - tw) // 2
    for i, ch in enumerate(text):
        glyph = FONT.get(ch, FONT[" "])
        for dy, row in enumerate(glyph):
            for dx, c in enumerate(row):
                if c == "#":
                    px[19 + dy][x0 + i * 4 + dx] = 0
    return px


def icon_bmp(label: str, width: int = 24, height: int = 30) -> bytes:
    """1-bpp BMP with the exact header layout of stock G1X Four icons."""
    px = icon_pixels(label, width, height)
    stride = ((width + 31) // 32) * 4
    rows = b""
    for row in reversed(px):                      # BMP rows are bottom-up
        bits = "".join(str(b) for b in row).ljust(stride * 8, "0")
        rows += int(bits, 2).to_bytes(stride, "big")
    palette = b"\x00\x00\x00\x00\xff\xff\xff\x00"
    dib = struct.pack("<IiiHHIIiiII", 40, width, height, 1, 1, 0, len(rows),
                      2835, 2835, 0, 0)
    off = 14 + len(dib) + len(palette)
    head = b"BM" + struct.pack("<IHHI", off + len(rows), 0, 0, off)
    return head + dib + palette + rows


def slot_pic_pixels(lines: list, width: int = 23, height: int = 30) -> list:
    """The slot picture the G1 draws for an unselected slot, in the style of
    the stock ones: outlined pedal, three knobs, the name in a lower panel.
    Rows top to bottom of 0/1 (1 = lit)."""
    px = [[0] * width for _ in range(height)]
    for x in range(1, width - 1):
        px[0][x] = px[height - 1][x] = 1
        px[13][x] = 1
    for y in range(1, height - 1):
        px[y][0] = px[y][width - 1] = 1
    px[1][0] = px[1][width - 1] = px[height - 2][0] = px[height - 2][width - 1] = 1
    for cx in (4, 11, 18):                        # three knobs
        for dy, row in enumerate([".###.", "##.##", "#####", "#####", ".###."]):
            for dx, c in enumerate(row):
                if c == "#":
                    px[5 + dy][cx - 2 + dx] = 1
    y0 = 17 if len(lines) == 1 else 15
    for li, text in enumerate(lines[:2]):
        text = text.upper()[:5]
        x0 = (width - (len(text) * 4 - 1)) // 2
        for i, ch in enumerate(text):
            for dy, row in enumerate(FONT.get(ch, FONT[" "])):
                for dx, c in enumerate(row):
                    if c == "#":
                        px[y0 + li * 7 + dy][x0 + i * 4 + dx] = 1
    return px


def slot_pic_bytes(lines: list, width: int = 23, height: int = 30) -> bytes:
    """LCD page format: 8 vertical pixels per byte, LSB at the top, pages of
    `width` columns (decoded from stock NYC Muff / Chorus pictures)."""
    px = slot_pic_pixels(lines, width, height)
    out = bytearray()
    for page in range((height + 7) // 8):
        for x in range(width):
            b = 0
            for bit in range(8):
                y = page * 8 + bit
                if y < height and px[y][x]:
                    b |= 1 << bit
            out.append(b)
    return bytes(out)


def set_slot_picture(elf: bytes, lines: list) -> bytes:
    """Replace the effect's first image-list entry (the slot picture) with a
    drawn 23x30 one. The DIY scaffold reserves 92 bytes for it (blank), which
    is exactly 4 pages x 23 columns."""
    from .elfinfo import _Elf, parse_effect_elf
    info = parse_effect_elf(elf)
    e = _Elf(elf)
    const = e.section_named(".const")
    if not info.images or const is None:
        raise ValueError("no image list in the effect ELF")
    width, height, ptr = info.images[0]
    pic = slot_pic_bytes(lines, 23, 30)
    out = bytearray(elf)
    # rewrite the {width, height} words of entry 0, found right before ptr
    body = elf[const.offset:const.offset + const.size]
    entry = struct.pack("<III", width, height, ptr)
    at = body.find(entry)
    if at < 0:
        raise ValueError("image-list entry not found")
    out[const.offset + at:const.offset + at + 8] = struct.pack("<II", 23, 30)
    o = const.offset + ptr - const.addr
    if o + len(pic) > const.offset + const.size:
        raise ValueError("picture does not fit in .const")
    out[o:o + len(pic)] = pic
    return bytes(out)


def retarget_g1(data: bytes, label: str, pic_lines: list = None) -> bytes:
    patch = parse_zd2(data)
    header = bytearray(data[:HEADER_SIZE])
    header[0x0C:0x10] = struct.pack("<I", G1_TARGET)
    header[0x10:0x59] = bytes(0x59 - 0x10)
    header[0x10] = 0x01
    header[0x18] = 0x80
    header[0x58] = 0x01

    body = b""
    for block in patch.blocks:
        payload = block.data
        if block.tag == "ICON":
            payload = icon_bmp(label)
        elif block.tag == "DATA":
            payload = set_slot_picture(payload, pic_lines or label.split()[:2])
        elif block.tag == "INFO":
            text = GROUP_INFO_TEXT.get(patch.header.group_id, "").encode()
            payload = (payload[:4] + text.ljust(12, b"\x00")[:12] + payload[16:20])
        body += block.tag.encode() + struct.pack("<I", len(payload)) + payload

    out = bytearray(bytes(header) + body + bytes(TRAILER_SIZE))
    out[8:12] = struct.pack("<I", zd2_crc(bytes(out)))
    return bytes(out)
