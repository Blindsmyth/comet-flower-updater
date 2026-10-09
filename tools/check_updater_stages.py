"""Pre-flight check for a patched G1X FOUR updater (recon/25).

Prints the updater's flash stage table and refuses (exit 1) if any stage
erases or writes the boot/update-mode program [0, 0x28000) or the
settings/signature sector [0xbf000, 0xc0000). Run it on every updater
before it goes near the pedal:

    .venv/Scripts/python.exe tools/check_updater_stages.py "build/fw/<name>.exe"
"""
import struct
import sys

import pefile

STAGE_VA = 0x43AC88          # 8 x 16-byte [op, flash addr, size, resource]
PROTECTED = [(0x0, 0x28000, "boot/update-mode program"),
             (0xBF000, 0xC0000, "settings/signature sector")]


def stages(path):
    pe = pefile.PE(path, fast_load=True)
    off = pe.get_offset_from_rva(STAGE_VA - pe.OPTIONAL_HEADER.ImageBase)
    rows = [struct.unpack_from("<4I", pe.__data__, off + 16 * i) for i in range(8)]
    return [r for r in rows if r[0] in (1, 2)]


def main():
    bad = False
    for path in sys.argv[1:]:
        print(path)
        for op, addr, size, res in stages(path):
            end = addr + (size if op == 1 else 1)
            hit = [name for lo, hi, name in PROTECTED if addr < hi and end > lo]
            what = "erase %#08x size %#x" % (addr, size) if op == 1 else "write %#08x resource %#x" % (addr, res)
            print("   %-36s %s" % (what, "REFUSED: touches " + ", ".join(hit) if hit else "ok"))
            bad |= bool(hit)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
