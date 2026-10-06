"""Build a G1X FOUR file-system restore tool from Zoom's official updater.

Zoom's "ZOOM G1X FOUR System v2.00 Updater.exe" (G1X_FOUR_v2.00_Win_E.zip from
zoomcorp.com) carries five BIN resources but its 8-stage table (.rdata VA
0x43AC88, 16-byte entries [op, flash addr, size, resource]; op 1 erase,
op 2 write, anything else skipped) only writes the boot program, graphics,
main firmware and the settings sector. Resource 136 (0x88), a 3,137,536-byte
factory image of the effect file system, is never sent.

The firmware's own region table (main firmware image offset 0x77C82) places
the file system at flash 0x102000, size 0x2FE000 (to the end of the 4 MB
flash), exactly the image size.

This script writes a COPY of the updater whose table is
    erase 0x102000 size 0x2FE000 ; write resource 0x88 at 0x102000
and skips the other six stages. Run the copy with the pedal in update mode
(hold both footswitches while connecting USB). It does not touch the boot
program or the firmware, so update mode stays available.

Used 2026-10-06 to recover the owner's G1X Four, which hung at the ZOOM logo
after an interrupted effect upload damaged its file system (recon/04).
Afterwards the pedal boots with the factory effects; DIY effects must be
reinstalled. The copy breaks Zoom's code signature; Zoom's licence forbids
altering the updater, so this is for repairing your own unit only.

    python tools/make_fs_restore_updater.py <official updater.exe> <output.exe> [--image <fs image>]

With --image, the copy carries that file-system image (exactly 0x2FE000
bytes, e.g. from tools/make_g1_image.py) in place of Zoom's factory one;
it is parsed and checked (tools/g1fs.py) before it is written in.
"""
import struct
import sys

import pefile

TABLE_VA = 0x43AC88
EXPECTED = [(1, 0xBF000, 0x1000, 0), (1, 0x28000, 0xB000, 0), (2, 0x28000, 0, 0x85),
            (1, 0x0, 0x28000, 0), (2, 0x0, 0, 0x8E), (1, 0x33000, 0x8C000, 0),
            (2, 0x33000, 0, 0x81), (2, 0xBF000, 0, 0x8B)]
FS_ADDR, FS_SIZE, FS_RES = 0x102000, 0x2FE000, 0x88


def main(src, dst, image=None):
    pe = pefile.PE(src)
    off = pe.get_offset_from_rva(TABLE_VA - pe.OPTIONAL_HEADER.ImageBase)
    data = bytearray(open(src, "rb").read())
    table = [struct.unpack_from("<4I", data, off + 16 * k) for k in range(8)]
    if table != EXPECTED:
        sys.exit("unexpected stage table: not the v2.00 G1X FOUR updater this was made for")
    res = {e.id: e for t in pe.DIRECTORY_ENTRY_RESOURCE.entries if str(t.name) == "BIN"
           for e in t.directory.entries}
    size = res[FS_RES].directory.entries[0].data.struct.Size
    if size != FS_SIZE:
        sys.exit("resource 0x88 is %d bytes, expected %d" % (size, FS_SIZE))
    new = [(1, FS_ADDR, FS_SIZE, 0), (2, FS_ADDR, 0, FS_RES)] + [(0, 0, 0, 0)] * 6
    if image is not None:
        import os
        sys.path.insert(0, os.path.dirname(__file__))
        import g1fs
        img = open(image, "rb").read()
        if len(img) != FS_SIZE:
            sys.exit("image is %d bytes, must be %d" % (len(img), FS_SIZE))
        _, _, ents = g1fs.current_dir(img)
        files = {n: g1fs.read_file(img, f, sz) for n, f, sz, _, _ in ents}
        g1fs.check_image(img, files)
        e = res[FS_RES].directory.entries[0].data.struct
        roff = pe.get_offset_from_rva(e.OffsetToData)
        data[roff:roff + FS_SIZE] = img
        print("image %s: %d files, verified, placed at file offset %#x" % (image, len(files), roff))
    for k, e in enumerate(new):
        struct.pack_into("<4I", data, off + 16 * k, *e)
    open(dst, "wb").write(data)
    print("wrote %s: erase %#x+%#x, write resource %#x there; other stages skipped"
          % (dst, FS_ADDR, FS_SIZE, FS_RES))


if __name__ == "__main__":
    a = sys.argv[1:]
    img = None
    if "--image" in a:
        k = a.index("--image")
        img = a[k + 1]
        del a[k:k + 2]
    main(a[0], a[1], img)
