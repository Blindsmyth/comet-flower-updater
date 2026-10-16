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

With --splash <png>, the 128x32 start-up screen shown after the ZOOM logo
(normally "G1X FOUR": the first 512 bytes of resource 133, the factory
presets region at flash 0x28000, LCD page format, LSB = top row) is replaced
by a 1-bit 128x32 PNG (white = lit), and the copy also rewrites that region.
Zoom's official updater rewrites it too, which restores the original screen.

With --presets <bin>, resource 133 is replaced by that whole 0xB000-byte
presets region (e.g. from tools/g1presets.py blank), and the copy erases and
writes flash 0x28000. --splash, if also given, is applied on top. The
pedal's patches take the new presets only at a factory reset.

With --logo <png>, the 92x16 ZOOM logo (184 bytes, 2 LCD pages x 92 columns,
drawn at x 18, y 8) is replaced in the main firmware, resource 129 (0x81), and
the copy also erases and writes flash 0x33000 as Zoom's updater does. The
firmware is a TI AIS image with no CRC commands, and the logo is stored raw
in a load section. The boot program holds its own copy of the logo and draws
it first; that copy is never touched, so the ZOOM logo still flashes before
ours. Zoom's official updater restores the original firmware (recon/09).

With --firmware <res1.bin>, the whole main firmware (resource 0x81) is
replaced by that file, typically made by tools/g1fw_gfx.py import (edited
fonts and bitmaps). It must be the same size as Zoom's and may differ only
inside the constant-data section (file 0x63708..0x75aac), so a code change
cannot slip in this way. --logo, if also given, is applied on top.

With --patch-fw <res1_patched.bin>, only the exact hash-pinned nine-byte
Slot 0 residency patch is accepted. Firmware erase/write stages at 0x33000
are added to the filesystem restore; the boot/update program and recovery
sector are preserved. This is NOT firmware-only packaging. --firmware and
--logo cannot be combined with --patch-fw. Runtime stability is not certified.

With --controller-fw <res1_controller_worker_candidate.bin>
(tools/make_controller_fw.py), the main firmware becomes stock v2.00 plus USB
MIDI controller mode: seven redirected CALLPs and one extra AIS section in free SDRAM, checked
structurally here; const-data edits (logo, start-up text) are allowed too. The image is larger than Zoom's, so it is appended to the
end of the resource section and resource 0x81 is pointed at it; the
updater's (already invalid) signature block is dropped. Same stage limits
as --patch-fw.
"""
# --patch-fw <res1_patched.bin> accepts only the exact hash-pinned nine-byte
# residency patch. It rewrites main firmware at 0x33000 in addition to the
# existing filesystem restore stages; boot/update-mode code is preserved.
# It cannot be combined with --firmware or --logo. This validates packaging,
# not runtime stability of the firmware experiment.
import argparse
import hashlib
from pathlib import Path
import struct
import sys

import pefile

TABLE_VA = 0x43AC88
EXPECTED = [(1, 0xBF000, 0x1000, 0), (1, 0x28000, 0xB000, 0), (2, 0x28000, 0, 0x85),
            (1, 0x0, 0x28000, 0), (2, 0x0, 0, 0x8E), (1, 0x33000, 0x8C000, 0),
            (2, 0x33000, 0, 0x81), (2, 0xBF000, 0, 0x8B)]
FS_ADDR, FS_SIZE, FS_RES = 0x102000, 0x2FE000, 0x88


PRESET_ADDR, PRESET_SIZE, PRESET_RES = 0x28000, 0xB000, 0x85
FW_ADDR, FW_SIZE, FW_RES = 0x33000, 0x8C000, 0x81
FW_CONST = (0x63708, 0x63708 + 0x123a4)   # res1 file range of the const data section
ZOOM_LOGO = bytes.fromhex(
    "0e0e8ececececececececececececececeeefefe7c3800f8fcfe0e0e0e0e0e0e0e0e0e0e"
    "0e0e0e0e1e7c787070787c1e0e0e0e0e0e0e0e0e0e0e0e0e0e0efefcf800f0fcfe1e0e0e"
    "0e0e0efefcf88080f8fcfe0e0e0e0e0e1efefcf00e1f3f3b393939393939393939393939"
    "393939383838000f1f3f38383838383838383838383838383c1f0f07070f1f3c38383838"
    "383838383838383838383f1f0f003f3f3f00000000000000030307070303000000000000"
    "003f3f3f")


def splash_bytes(png, w=128, h=32):
    """w x h PNG -> LCD page format (h/8 pages x w columns, LSB = top row)."""
    from PIL import Image
    im = Image.open(png).convert("L")
    if im.size != (w, h):
        sys.exit("%s must be %dx%d, got %s" % (png, w, h, im.size))
    out = bytearray(w * h // 8)
    for page in range(h // 8):
        for x in range(w):
            v = 0
            for bit in range(8):
                if im.getpixel((x, page * 8 + bit)) >= 128:
                    v |= 1 << bit
            out[page * w + x] = v
    return bytes(out)


PATCH_SOURCE_SHA256 = "43060686fce75e175a217194ab1be3aeffe0be7d59f9d3df4181d41b9d3cc5a7"
PATCH_RESULT_SHA256 = "9e2ccc1b727672c250d431a8d88a1d5101105c5db90ec7cfc8ca85799267c002"
PATCH_BYTES = {0x61008: 0x27, 0x61009: 0x44, 0x6100a: 0x05,
               0x6100b: 0xfc, 0x6101b: 0xe1, 0x756b0: 0x02,
               0x77efd: 0x00, 0x77efe: 0x82, 0x77eff: 0x11}


def validate_patch_fw(old_fw, new_fw):
    """Accept only the reviewed Slot 0 residency image; no generic code bypass."""
    if len(old_fw) != 493412 or len(new_fw) != 493412:
        raise ValueError("--patch-fw requires the 493412-byte v2.00 firmware")
    if hashlib.sha256(old_fw).hexdigest() != PATCH_SOURCE_SHA256:
        raise ValueError("--patch-fw source firmware SHA-256 mismatch")
    if hashlib.sha256(new_fw).hexdigest() != PATCH_RESULT_SHA256:
        raise ValueError("--patch-fw patched firmware SHA-256 mismatch")
    diff = {i: b for i, b in enumerate(new_fw) if b != old_fw[i]}
    if diff != PATCH_BYTES:
        raise ValueError("--patch-fw requires the exact reviewed nine-byte diff")


def validate_controller_fw(old_fw, new_fw, test=False):
    """Accept only stock v2.00 + the controller section and listed hooks.
    test=True (--test-controller-fw) also accepts the OFFLINE diag/UI hook
    rows (make_controller_fw DIAG_HOOKS, UI_HOOKS), each either untouched or
    redirected into the controller section; the seven lifecycle hooks are
    still required."""
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    import make_controller_fw as ctl
    if hashlib.sha256(old_fw).hexdigest() != ctl.STOCK_SHA256:
        raise ValueError("--controller-fw needs the stock v2.00 firmware in the updater")
    # Allowed: const-data edits (logo, text), listed hooks, one new section.
    close = len(old_fw) - 8
    if new_fw[-8:] != old_fw[-8:]:
        raise ValueError("--controller-fw: jump-and-close command changed")
    cmds = list(ctl.ais_commands(new_fw))
    off, op, args = cmds[-2]
    if op != ctl.AIS_SECTION_LOAD or off != close:
        raise ValueError("--controller-fw: no added section before jump-and-close")
    base, size = args
    lo, hi = ctl.FREE_SDRAM
    if not (lo <= base and base + size <= hi):
        raise ValueError("--controller-fw: section %#x+%#x outside free SDRAM" % (base, size))
    if len(new_fw) != close + 12 + ((size + 3) & ~3) + 8:
        raise ValueError("--controller-fw: unexpected image length")
    hooks = {off: (vma, target) for vma, off, _, target, _ in ctl.HOOKS}
    optional = {off: (vma, target) for vma, off, _, target, _ in
                (ctl.DIAG_HOOKS + ctl.UI_HOOKS if test else [])}
    for off, (vma, stock_target) in optional.items():
        old = struct.unpack_from("<I", old_fw, off)[0]
        new = struct.unpack_from("<I", new_fw, off)[0]
        if ctl.callp_target(vma, old) != stock_target:
            raise ValueError("--test-controller-fw: hook %#x is not the stock CALLP" % vma)
        if new == old:
            continue
        if (old ^ new) & ~(0x1fffff << 7):
            raise ValueError("--test-controller-fw: hook %#x changed more than its target" % vma)
        if not base <= ctl.callp_target(vma, new) < base + size:
            raise ValueError("--test-controller-fw: hook %#x leaves the controller section" % vma)
    allowed_hook_words = set(hooks) | set(optional)
    for i in range(close):
        if (new_fw[i] != old_fw[i] and i & ~3 not in allowed_hook_words
                and not FW_CONST[0] <= i < FW_CONST[1]):
            raise ValueError("--controller-fw: stock byte %#x changed" % i)
    for off, (vma, stock_target) in hooks.items():
        old = struct.unpack_from("<I", old_fw, off)[0]
        new = struct.unpack_from("<I", new_fw, off)[0]
        if ctl.callp_target(vma, old) != stock_target:
            raise ValueError("--controller-fw: hook %#x is not the stock CALLP" % vma)
        if (old ^ new) & ~(0x1fffff << 7):
            raise ValueError("--controller-fw: hook %#x changed more than its target" % vma)
        if not base <= ctl.callp_target(vma, new) < base + size:
            raise ValueError("--controller-fw: hook %#x leaves the controller section" % vma)


def grow_resource(data, res_id, payload):
    """Append payload to the last (.rsrc) section and point resource res_id
    at it. Returns the new file bytes."""
    pe = pefile.PE(data=bytes(data))
    sec = pe.sections[-1]
    if sec.Name.rstrip(b"\0") != b".rsrc":
        sys.exit("resource section is not last: cannot grow it")
    end = sec.PointerToRawData + sec.SizeOfRawData
    sec_dir = pe.OPTIONAL_HEADER.DATA_DIRECTORY[4]
    tail = len(data) - end
    if tail and not (sec_dir.VirtualAddress == end and sec_dir.Size == tail):
        sys.exit("unexpected data after the resource section")
    rva = sec.VirtualAddress + max(sec.SizeOfRawData, sec.Misc_VirtualSize)
    rva = (rva + 15) & ~15
    gap = rva - sec.VirtualAddress - sec.SizeOfRawData
    align = pe.OPTIONAL_HEADER.FileAlignment
    blob = b"\0" * gap + payload
    blob += b"\0" * (-len(blob) % align)
    sec.SizeOfRawData += len(blob)
    sec.Misc_VirtualSize = sec.SizeOfRawData
    salign = pe.OPTIONAL_HEADER.SectionAlignment
    pe.OPTIONAL_HEADER.SizeOfImage = -(-(sec.VirtualAddress + sec.Misc_VirtualSize) // salign) * salign
    sec_dir.VirtualAddress = sec_dir.Size = 0
    entry = [e for t in pe.DIRECTORY_ENTRY_RESOURCE.entries if str(t.name) == "BIN"
             for e in t.directory.entries if e.id == res_id][0].directory.entries[0].data.struct
    entry.OffsetToData, entry.Size = rva, len(payload)
    out = pefile.PE(data=bytes(pe.write()[:end]) + blob)
    out.OPTIONAL_HEADER.CheckSum = out.generate_checksum()
    return bytearray(out.write())


def main(src, dst, image=None, splash=None, presets=None, logo=None, firmware=None,
         patch_fw=None, controller_fw=None, test_controller_fw=None):
    if Path(src).resolve() == Path(dst).resolve():
        sys.exit("output must differ from the official updater")
    if patch_fw is not None and (firmware is not None or logo is not None):
        sys.exit("--patch-fw cannot be combined with --firmware or --logo")
    if test_controller_fw is not None:
        if controller_fw is not None:
            sys.exit("--test-controller-fw and --controller-fw are exclusive")
        if "TEST" not in Path(dst).name.upper():
            sys.exit("--test-controller-fw: the output name must contain TEST")
        controller_fw, test = test_controller_fw, True
    else:
        test = False
    if controller_fw is not None and (firmware is not None or logo is not None
                                      or patch_fw is not None):
        sys.exit("--controller-fw cannot be combined with --firmware, --logo or --patch-fw")
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
    new = [(1, FS_ADDR, FS_SIZE, 0), (2, FS_ADDR, 0, FS_RES)]
    if presets is not None or splash is not None:
        e = res[PRESET_RES].directory.entries[0].data.struct
        if e.Size != PRESET_SIZE:
            sys.exit("resource 0x85 is %d bytes, expected %d" % (e.Size, PRESET_SIZE))
        roff = pe.get_offset_from_rva(e.OffsetToData)
        if presets is not None:
            pre = open(presets, "rb").read()
            if len(pre) != PRESET_SIZE:
                sys.exit("presets is %d bytes, must be %d" % (len(pre), PRESET_SIZE))
            data[roff:roff + PRESET_SIZE] = pre
            print("presets %s placed in resource 0x85 (presets region %#x)" % (presets, PRESET_ADDR))
        if splash is not None:
            data[roff:roff + 512] = splash_bytes(splash)
            print("splash %s placed in resource 0x85 (presets region %#x)" % (splash, PRESET_ADDR))
        new = [(1, PRESET_ADDR, PRESET_SIZE, 0), (2, PRESET_ADDR, 0, PRESET_RES)] + new
    if firmware is not None or patch_fw is not None:
        e = res[FW_RES].directory.entries[0].data.struct
        roff = pe.get_offset_from_rva(e.OffsetToData)
        firmware_path = patch_fw if patch_fw is not None else firmware
        new_fw = Path(firmware_path).read_bytes()
        old_fw = bytes(data[roff:roff + e.Size])
        if len(new_fw) != len(old_fw):
            sys.exit("firmware is %d bytes, must be %d" % (len(new_fw), len(old_fw)))
        diff = [i for i in range(len(old_fw)) if new_fw[i] != old_fw[i]]
        if patch_fw is not None:
            try:
                validate_patch_fw(old_fw, new_fw)
            except ValueError as exc:
                sys.exit(str(exc))
        elif any(not FW_CONST[0] <= i < FW_CONST[1] for i in diff):
            sys.exit("firmware differs outside the constant-data section: refused")
        data[roff:roff + e.Size] = new_fw
        print("firmware %s placed in resource 0x81 (%d bytes differ; %s)"
              % (firmware_path, len(diff), "reviewed residency patch" if patch_fw is not None
                 else "all in const data"))
    if logo is not None:
        e = res[FW_RES].directory.entries[0].data.struct
        roff = pe.get_offset_from_rva(e.OffsetToData)
        fw = data[roff:roff + e.Size]
        at = fw.find(ZOOM_LOGO)
        if at < 0 or fw.find(ZOOM_LOGO, at + 1) >= 0:
            sys.exit("ZOOM logo not found exactly once in resource 0x81")
        data[roff + at:roff + at + len(ZOOM_LOGO)] = splash_bytes(logo, 92, 16)
        print("logo %s placed in resource 0x81 at %#x (main firmware %#x)" % (logo, at, FW_ADDR))
    grown = None
    if controller_fw is not None:
        e = res[FW_RES].directory.entries[0].data.struct
        roff = pe.get_offset_from_rva(e.OffsetToData)
        old_fw = bytes(data[roff:roff + e.Size])
        new_fw = Path(controller_fw).read_bytes()
        if len(new_fw) > FW_SIZE:
            sys.exit("firmware is %d bytes, larger than its %#x flash region" % (len(new_fw), FW_SIZE))
        try:
            validate_controller_fw(old_fw, new_fw, test=test)
        except ValueError as exc:
            sys.exit(str(exc))
        grown = new_fw
        print("firmware %s: stock v2.00 + controller section (%d bytes larger)%s"
              % (controller_fw, len(new_fw) - len(old_fw),
                 "; TEST build with diag/UI hooks (owner-run test only)" if test else ""))
    if logo is not None or firmware is not None or patch_fw is not None or grown is not None:
        new += [(1, FW_ADDR, FW_SIZE, 0), (2, FW_ADDR, 0, FW_RES)]
    # Every image: the boot/update-mode program [0, 0x28000) holds the only
    # recovery path (recon/25), so it, the settings/recovery sector
    # [0xbf000, 0xc0000) and all unused flash regions stay untouched.
    allowed = {(1, FS_ADDR, FS_SIZE, 0), (2, FS_ADDR, 0, FS_RES),
               (1, PRESET_ADDR, PRESET_SIZE, 0), (2, PRESET_ADDR, 0, PRESET_RES),
               (1, FW_ADDR, FW_SIZE, 0), (2, FW_ADDR, 0, FW_RES)}
    if len(new) > 8 or any(stage not in allowed for stage in new):
        sys.exit("unsafe update stages: refused")
    new += [(0, 0, 0, 0)] * (8 - len(new))
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
    if grown is not None:
        data = grow_resource(data, FW_RES, grown)
        check = pefile.PE(data=bytes(data))
        e = [r for t in check.DIRECTORY_ENTRY_RESOURCE.entries if str(t.name) == "BIN"
             for r in t.directory.entries if r.id == FW_RES][0].directory.entries[0].data.struct
        if bytes(check.get_data(e.OffsetToData, e.Size)) != grown:
            sys.exit("resource 0x81 read-back mismatch after growing")
    open(dst, "wb").write(data)
    print("wrote %s; stages:" % dst)
    for e in new:
        if e[0]:
            print("   %s %#08x %s" % ("erase" if e[0] == 1 else "write", e[1],
                                      "size %#x" % e[2] if e[0] == 1 else "resource %#x" % e[3]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("src")
    parser.add_argument("dst")
    for key in ("image", "splash", "presets", "logo", "firmware", "patch-fw",
                "controller-fw", "test-controller-fw"):
        parser.add_argument("--" + key)
    main(**vars(parser.parse_args()))
