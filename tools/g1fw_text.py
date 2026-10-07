#!/usr/bin/env python3
"""Text edits in the G1X Four main firmware (const data only).

  python tools/g1fw_text.py version <in_res1.bin> <out_res1.bin> [TEXT]

version: the start-up screen prints the firmware version with
sprintf(buf, "v%s", version) (code 0xc014dc2c..0xc014dc38; the format string
at 0xc017416c is referenced nowhere else). TEXT replaces that 4-byte format:
  ""      (default) prints nothing, so "v2.0" disappears;
  up to 3 characters, e.g. "1.0", prints that text instead.
A "%" in TEXT is refused (it would become a format directive).
The result goes on the pedal with make_fs_restore_updater.py --firmware,
which refuses any change outside the const data.
"""
import sys

SEC_ADDR, SEC_FILE = 0xc016f780, 0x63708
VERSION_FMT = 0xc017416c


def main(a):
    if len(a) < 3 or a[0] != "version":
        sys.exit(__doc__)
    text = a[3] if len(a) > 3 else ""
    if len(text) > 3 or "%" in text or not text.isascii():
        sys.exit("TEXT must be at most 3 ASCII characters, without '%'")
    d = bytearray(open(a[1], "rb").read())
    o = VERSION_FMT - SEC_ADDR + SEC_FILE
    if bytes(d[o:o + 4]) != b"v%s\x00":
        sys.exit("version format string not found at %#x (not the v2.00 firmware?)" % o)
    d[o:o + 4] = text.encode().ljust(4, b"\x00")
    open(a[2], "wb").write(d)
    print("version text %r written at file %#x -> %s" % (text, o, a[2]))


if __name__ == "__main__":
    main(sys.argv[1:])
