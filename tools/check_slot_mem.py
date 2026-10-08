"""Check that a ZD2 effect fits the pedal's fixed 40 KiB per-slot image heap.

    python tools/check_slot_mem.py <file.ZD2> [...]

The G1 Four loads every effect into a fixed 0xa000-byte region per slot
(c01f4000 + slot*0xa000, recon/14 section 1). The same heap holds each
PT_LOAD segment (memsz, 32-byte aligned, 8-byte block header), the 132-byte
module record, and the symbol array and string storage (module[5]..[8]).
There is no spill to other memory: an effect that does not fit fails to load.

The estimate is conservative: alignment padding is counted at its worst case
and the symbol/string storage is taken as the full .dynsym + .dynstr size.
Exit status 1 if any file exceeds the slot; a warning below WARN_HEADROOM.
"""
import struct
import sys

SLOT_HEAP = 0xa000
WARN_HEADROOM = 2048
BLOCK_HEADER = 8
SEG_ALIGN = 32
MODULE_RECORD = 132


def block(n, align=8):
    """Worst-case heap bytes for an n-byte allocation."""
    return ((n + 7) & ~7) + BLOCK_HEADER + (align - 8 if align > 8 else 0)


def slot_bytes(zd2):
    e = zd2[zd2.find(b"\x7fELF"):]
    if not e:
        raise ValueError("no ELF image in file")
    phoff, shoff = struct.unpack_from("<II", e, 0x1c)
    phent, phnum, shent, shnum, shstr = struct.unpack_from("<HHHHH", e, 0x2a)
    total = block(MODULE_RECORD)
    for k in range(phnum):
        ptype, _, _, _, _, memsz = struct.unpack_from("<6I", e, phoff + k * phent)
        if ptype == 1:
            total += block(memsz, SEG_ALIGN)
    sh = [struct.unpack_from("<10I", e, shoff + k * shent) for k in range(shnum)]
    names = sh[shstr][4]
    for s in sh:
        name = e[names + s[0]:e.index(b"\0", names + s[0])]
        if name in (b".dynsym", b".dynstr"):
            total += block(s[5])
    return total


def main(paths):
    bad = False
    for p in paths:
        used = slot_bytes(open(p, "rb").read())
        free = SLOT_HEAP - used
        tag = "OVER" if free < 0 else "tight" if free < WARN_HEADROOM else "ok"
        print("slot memory: %s uses %d of %d bytes (%d free) %s"
              % (p, used, SLOT_HEAP, free, tag))
        bad |= free < 0
    if bad:
        sys.exit("slot memory: effect does not fit the 40 KiB slot heap: refused")


if __name__ == "__main__":
    main(sys.argv[1:])
