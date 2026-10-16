"""Rename the pedal's USB device strings (main firmware res1, const data only).

    python tools/cf_usb_name.py <res1.bin> <out.bin> [--name "Comet Flower"]

The main firmware's USB string table at c017f410 holds (bLength | 3 << 8,
pointer) records; the descriptor builder c01352a4 copies (bLength - 2) / 2
ASCII characters as UTF-16 (it never uses strlen), so a name may be shorter or
longer than the slot as long as bLength matches and the text fits the slot:

    string 1 (manufacturer)  record c017f424 -> c0181420 "ZOOM Corporation" (17-byte slot)
    string 2 (product)       record c017f42c -> c0181638 "ZOOM G Series"    (14-byte slot)

The product string is what Windows shows as the MIDI port name. Both changes
are in the constant-data section, so make_fs_restore_updater accepts the image
with --firmware, and make_controller_fw accepts it as a base. Update mode is
unaffected: the boot program (res5) has its own copies of both strings and is
never written, so updaters still see "ZOOM G Series" there.
"""
import argparse
import struct
import sys
from pathlib import Path

CONST_VMA, CONST_FILE, CONST_SIZE = 0xc016f780, 0x63708, 0x123a4
# (record VMA, string VMA, stock text, slot bytes incl. NUL padding)
STRINGS = [
    (0xc017f424, 0xc0181420, b"ZOOM Corporation", 17),
    (0xc017f42c, 0xc0181638, b"ZOOM G Series", 14),
]


def off(vma):
    o = vma - CONST_VMA
    if not 0 <= o < CONST_SIZE:
        raise ValueError("%#x is outside the constant-data section" % vma)
    return CONST_FILE + o


def rename(fw, name):
    name_b = name.encode("ascii")
    if not 1 <= len(name_b) or any(not 32 <= c <= 126 for c in name_b):
        raise ValueError("name must be printable ASCII")
    out = bytearray(fw)
    for rec, ptr, stock, slot in STRINGS:
        hdr, p = struct.unpack_from("<II", fw, off(rec))
        if p != ptr or hdr >> 8 != 3:
            raise ValueError("record %#x is not the expected string record" % rec)
        current = fw[off(ptr):off(ptr) + slot].rstrip(b"\0")
        if hdr & 0xff != 2 + 2 * len(current):
            raise ValueError("record %#x bLength does not match its text" % rec)
        if current != stock:
            raise ValueError("string at %#x is %r, expected stock %r" % (ptr, current, stock))
        if len(name_b) > slot - 1:
            raise ValueError("%r does not fit the %d-byte slot at %#x" % (name, slot, ptr))
        out[off(ptr):off(ptr) + slot] = name_b + bytes(slot - len(name_b))
        struct.pack_into("<I", out, off(rec), (3 << 8) | (2 + 2 * len(name_b)))
    return bytes(out)


def read_names(fw):
    names = []
    for rec, ptr, _, slot in STRINGS:
        hdr = struct.unpack_from("<I", fw, off(rec))[0]
        n = ((hdr & 0xff) - 2) // 2
        names.append(fw[off(ptr):off(ptr) + n].decode("ascii"))
    return names


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--name", default="Comet Flower")
    a = ap.parse_args(argv)
    fw = Path(a.input).read_bytes()
    try:
        out = rename(fw, a.name)
    except ValueError as exc:
        sys.exit(str(exc))
    changed = [i for i in range(len(fw)) if fw[i] != out[i]]
    assert all(CONST_FILE <= i < CONST_FILE + CONST_SIZE for i in changed)
    Path(a.output).write_bytes(out)
    print("manufacturer %r, product %r (%d bytes changed, all in const data) -> %s"
          % (*read_names(out), len(changed), a.output))


if __name__ == "__main__":
    main()
