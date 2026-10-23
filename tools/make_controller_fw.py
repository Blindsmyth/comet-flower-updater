"""Build the USB MIDI controller-mode main firmware (offline only).

    python tools/make_controller_fw.py [--base build/fw/res1_493412.bin]
                                       [--out build/fw/res1_controller_worker_candidate.bin]

The base may be stock v2.00, the residency image, or stock with edits
inside the const-data section only (logo, start-up text).

Steps, each verified:
 1. compile firmware/controller/ with TI cl6x/lnk6x into one contiguous
    image at CTL_BASE (free SDRAM, recon/17 "Placement in SDRAM");
 2. insert one AIS section-load record for that image just before the
    final jump-and-close command;
 3. redirect the seven stock CALLPs (HOOKS) to the controller entry points,
    keeping each word's unit and parallel bits;
 4. re-walk the AIS, check that only the expected bytes changed, and
    decode each retargeted CALLP to its controller entry point. dis6x
    disassembles the linked controller ELF, not the patched main image.

It never writes an updater and never touches the pedal. Packaging is
tools/make_fs_restore_updater.py --controller-fw.
"""
import argparse
import hashlib
import os
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "firmware" / "controller"
OUT = ROOT / "build" / "controller"
CGT = Path(os.environ.get("ZOOM_TI_CGT", "C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS"))

STOCK_SHA256 = "43060686fce75e175a217194ab1be3aeffe0be7d59f9d3df4181d41b9d3cc5a7"
RESIDENCY_SHA256 = "9e2ccc1b727672c250d431a8d88a1d5101105c5db90ec7cfc8ca85799267c002"
FREE_SDRAM = (0xc0187024, 0xc01f4000)
CONST_DATA = (0x63708, 0x63708 + 0x123a4)   # res1 file range of the const section
CTL_BASE, CTL_SIZE = 0xc01a0000, 0x4000

AIS_MAGIC = 0x41504954
AIS_SECTION_LOAD = 0x58535901
AIS_JUMP_CLOSE = 0x58535906

# site VMA, AIS file offset, stock word, stock target, controller symbol
HOOKS = [
    (0xc0134e14, 0x28d90, 0x1050c512, 0xc015d428, "controller_start"),
    (0xc0134df0, 0x28d6c, 0x1fe64012, 0xc0127fe0, "controller_dispatch"),
    (0xc015ffd0, 0x53f4c, 0x1fd5e693, 0xc014aef4, "controller_analog"),
    (0xc01600b0, 0x5402c, 0x1fd5ca92, 0xc014aef4, "controller_analog"),
    (0xc0149d4c, 0x3dcc8, 0x10007193, 0xc014a0cc, "controller_worker_wait"),
    (0xc014a048, 0x3dfc4, 0x10003113, 0xc014a1c8, "controller_reset_unlock"),
    (0xc0149fa8, 0x3df24, 0x10008c13, 0xc014a400, "controller_worker_create"),
]

# OFFLINE diagnostic only (--diag-teardown); never in HOOKS, so the updater
# packager and lifecycle verifier keep refusing it. Stock word 1ffe6292 at
# c0120744 is CALLP c011fa54 (type==16 test) inside the abort drain loop.
DIAG_HOOKS = [
    (0xc0120744, 0x146c0, 0x1ffe6292, 0xc011fa54, "controller_diag_teardown_hook"),
    # Site 2: CALLP c011fa54 (type==16 test) in the queue 32..35 consumer c01219f4.
    (0xc0121a18, 0x15994, 0x1ffc0a92, 0xc011fa54, "controller_diag_consumer_hook"),
]

# On-pedal status screen (--ui; run on hardware 2026-10-15, packageable). Stock word 100fc413 at c013c76c is
# UpdateUI's CALLP c0144580 (Event_pend, timeout -1); optional, so not in HOOKS.
UI_HOOKS = [
    (0xc013c76c, 0x306e8, 0x100fc413, 0xc0144580, "controller_ui_pend"),
]

# CF edit-page header (--cf-header, TEST builds; firmware/controller/cf_header.c,
# docs/EDIT_SCREEN_TRACE_2026-10-23.md): both 32-bit CALLPs of the stock edit-page
# renderer c012e5a8 (UpdateUI row dispatch c013c050, MainApp c0135b08) go through
# cf_edit_draw, which runs the stock renderer and then draws the stage header.
CF_HEADER_HOOKS = [
    (0xc013c050, 0x2ffcc, 0x1fe4ad13, 0xc012e5a8, "cf_edit_draw"),
    (0xc0135b08, 0x29a84, 0x1ff15513, 0xc012e5a8, "cf_edit_draw"),
]


# PROCESS OVERFLOW gate (--gate, TEST builds): the patch's declared dspload sum must be below
# 230.0f, loaded by this one MVKH 0x4366,B4 (c0141ad8..c0141b60: ADDSP over slots 0..4,
# CMPLTSP; docs/DSP_RULES.md 4). --gate N rewrites only its 16-bit constant (N must have a
# zero low half as a float, as 230.0 does). Ceiling test 2026-10-23 (docs/FW_RND_BENCH
# section 14): ~340 keeps a patch below ~88 % of the block on Zoom's 7 + 3 x kcycles scale.
GATE_SITE = (0xc0141b54, 0x35ad0, 0x0221b36a)
GATE_RANGE = (230.0, 400.0)


def gate_word(load):
    """The MVKH word that loads `load` (float) instead of 230.0."""
    bits = struct.unpack("<I", struct.pack("<f", float(load)))[0]
    if bits & 0xffff or not GATE_RANGE[0] <= load <= GATE_RANGE[1]:
        raise ValueError("gate %r: needs %g..%g with a zero low half as a float (e.g. 340)" % (
            load, GATE_RANGE[0], GATE_RANGE[1]))
    return (GATE_SITE[2] & ~(0xffff << 7)) | ((bits >> 16) << 7)


def gate_value(word):
    return struct.unpack("<f", struct.pack("<I", ((word >> 7) & 0xffff) << 16))[0]

# Start-up bloom animation (--boot-anim, TEST builds; firmware/controller/cf_boot.c, timed in the call,
# frames from tools/make_boot_anim.py): the start-up screen's logo draw c014db64 calls
# gfx_set_bit_range c011c508 once, at c014db78 (logo c017bf38, x 18, y 8, 92 x 16).
BOOT_HOOKS = [
    (0xc014db78, 0x41af4, 0x1f9d3513, 0xc011c508, "cf_boot_logo"),
]


def callp_target(addr, word):
    cst = (word >> 7) & 0x1fffff
    if cst & 0x100000:
        cst -= 0x200000
    return (addr & ~0x1f) + 4 * cst


def callp_retarget(addr, word, target):
    disp = (target - (addr & ~0x1f)) // 4
    if (target - (addr & ~0x1f)) % 4 or not -0x100000 <= disp < 0x100000:
        raise ValueError("CALLP target %#x out of range from %#x" % (target, addr))
    new = (word & ~(0x1fffff << 7)) | ((disp & 0x1fffff) << 7)
    assert callp_target(addr, new) == target
    return new


def ais_commands(d):
    """Yield (file offset, opcode, args) for each AIS command."""
    if struct.unpack_from("<I", d, 0)[0] != AIS_MAGIC:
        raise ValueError("not an AIS image")
    o = 4
    while o < len(d):
        c = struct.unpack_from("<I", d, o)[0]
        lo = c & 0xff
        if lo == 0x63:
            yield o, c, None
            o += 4
        elif lo == 0x01:
            a, n = struct.unpack_from("<II", d, o + 4)
            yield o, c, (a, n)
            o += 12 + ((n + 3) & ~3)
        elif lo == 0x0d:
            na = struct.unpack_from("<I", d, o + 4)[0] >> 16
            yield o, c, None
            o += 8 + 4 * na
        elif lo == 0x06:
            yield o, c, struct.unpack_from("<I", d, o + 4)[0]
            return
        else:
            raise ValueError("unknown AIS command %#x at %#x" % (c, o))


def run(*cmd):
    r = subprocess.run([str(c) for c in cmd], capture_output=True, text=True)
    if r.returncode:
        sys.exit("%s failed:\n%s%s" % (cmd[0], r.stdout, r.stderr))
    return r.stdout


def build_payload(diag=False, ui=False, cf_header=False, boot_anim=False):
    """diag=True builds the OFFLINE teardown-diagnostic candidate, ui=True the
    OFFLINE on-pedal status screen; each variant gets its own directory under
    build/controller so the lifecycle outputs are untouched."""
    out = OUT / ("diag" if diag else "") / ("ui" if ui else "") if (diag or ui) else OUT
    if cf_header:
        out = out / "cfh"
    if boot_anim:
        out = out / "boot"
    out.mkdir(parents=True, exist_ok=True)
    stem = "controller_diag" if diag else "controller"
    srcs = [SRC / "controller.c", SRC / "controller_hooks.asm"]
    objs = [out / "controller.obj", out / "controller_hooks.obj"]
    if diag:
        srcs += [SRC / "controller_diag.c", SRC / "controller_diag_hooks.asm"]
        objs += [out / "controller_diag.obj", out / "controller_diag_hooks.obj"]
    if ui:
        srcs += [SRC / "controller_ui.c", SRC / "controller_menu.c"]
        objs += [out / "controller_ui.obj", out / "controller_menu.obj"]
    if cf_header:
        srcs += [SRC / "cf_header.c"]
        objs += [out / "cf_header.obj"]
    if boot_anim:
        srcs += [SRC / "cf_boot.c"]
        objs += [out / "cf_boot.obj"]
    cmd_file = SRC / ("controller_diag.cmd" if diag else "controller.cmd")
    run(CGT / "bin/cl6x", "--silicon_version=6740", "--abi=eabi", "--c99",
        "--opt_level=2", "--mem_model:data=far", "--mem_model:const=data",
        "--keep_asm", "--asm_directory=%s" % out, "--obj_directory=%s" % out,
        "--compile_only", *(["--define=CTL_DIAG"] if diag else []),
        *(["--define=CTL_UI"] if ui else []), *(["--define=CTL_CF_HEADER"] if cf_header else []),
        *(["--define=CTL_BOOT_ANIM"] if boot_anim else []), *srcs)
    elf = out / (stem + ".elf")
    run(CGT / "bin/lnk6x", "--ram_model", "--map_file=%s" % (out / (stem + ".map")),
        *(["--retain=cf_edit_draw"] if cf_header else []),
        *(["--retain=cf_boot_logo"] if boot_anim else []),
        "--output_file=%s" % elf, *objs, cmd_file)
    run(CGT / "bin/dis6x", elf, out / (stem + ".dis"))
    return elf


def elf_image(elf, region=(CTL_BASE, CTL_SIZE)):
    """Contiguous bytes of all allocated sections, plus the symbol table."""
    region_base, region_size = region
    e = elf.read_bytes()
    shoff = struct.unpack_from("<I", e, 0x20)[0]
    shent, shnum, shstr = struct.unpack_from("<HHH", e, 0x2e)
    sh = [struct.unpack_from("<10I", e, shoff + k * shent) for k in range(shnum)]
    names = sh[shstr][4]
    name = lambda s: e[names + s[0]:e.index(b"\0", names + s[0])].decode()
    alloc = [s for s in sh if s[2] & 2 and s[5]]          # SHF_ALLOC, size > 0
    for s in alloc:
        if not (region_base <= s[3] and s[3] + s[5] <= region_base + region_size):
            sys.exit("section %s at %#x outside the reserved region" % (name(s), s[3]))
        if name(s) in (".cinit", ".switch", ".init_array"):
            sys.exit("section %s needs run-time support: refused" % name(s))
    lo = min(s[3] for s in alloc)
    hi = max(s[3] + s[5] for s in alloc)
    img = bytearray(hi - lo)
    for s in alloc:
        if s[1] != 8:                                     # not SHT_NOBITS
            img[s[3] - lo:s[3] - lo + s[5]] = e[s[4]:s[4] + s[5]]
    syms = {}
    for s in sh:
        if s[1] == 2:                                     # SHT_SYMTAB
            strtab = sh[s[6]][4]
            for k in range(s[5] // 16):
                st_name, value = struct.unpack_from("<II", e, s[4] + 16 * k)
                n = e[strtab + st_name:e.index(b"\0", strtab + st_name)].decode()
                if n:
                    syms[n] = value
    return lo, bytes(img), syms


def base_kind(base, stock):
    """'stock', 'residency', or 'const' (stock with const-data edits only,
    e.g. the Comet Flower logo and start-up text); anything else is refused."""
    digest = hashlib.sha256(base).hexdigest()
    if digest == STOCK_SHA256:
        return "stock"
    if digest == RESIDENCY_SHA256:
        return "residency"
    if hashlib.sha256(stock).hexdigest() != STOCK_SHA256:
        raise ValueError("stock reference firmware SHA-256 mismatch")
    if len(base) == len(stock) and all(
            CONST_DATA[0] <= i < CONST_DATA[1] for i in range(len(base)) if base[i] != stock[i]):
        return "const"
    raise ValueError("base firmware is not stock v2.00, the residency image, "
                     "or stock with const-data edits only")


# USB product string (string 2): the stock record holds (bLength | 3 << 8, pointer)
# and the builder c01352a4 copies (bLength - 2) / 2 ASCII bytes into its
# static descriptor buffer c0109fb0 (passed on with size 128 at c013533a). The
# stock text slot c0181638 holds only 13 characters (tools/cf_usb_name.py), so a
# longer name is appended to the payload and the record points there.
USB_PRODUCT_RECORD, USB_PRODUCT_STOCK_PTR = 0xc017f42c, 0xc0181638
USB_PRODUCT_MAX = 31            # Windows MIDI port names are at most 31 characters
# USB string 3 (the USB-audio interface name, iInterface of IF2): the string builder
# c0161008 fills the pointer list with records c017f414 (0, language), c017f424 (1),
# c017f42c (2, product), and c017f41c for both 3 and 4 (c0161020 MVK, c016102c/c0161032
# STDW, c0161036 STW). Stock c017f41c is an empty string (0x302 = bLength 2) whose pointer
# c0181b20 is never read; only c0161020 references the record (refs.txt, const scan).
# Windows names a composite function after its first interface's iInterface string, so the
# audio input shows as "Line (<this text>)". The reply buffer takes 128 bytes (c013533a)
# and a reply that is a multiple of 64 bytes takes the stock ZLP path (port 13), so
# 1..62 characters, never 31.
USB_STR3_RECORD, USB_STR3_STOCK_HDR, USB_STR3_STOCK_PTR = 0xc017f41c, 0x302, 0xc0181b20
USB_STR3_MAX = 62


def usb_string3_patch(data, name, addr):
    """Point string 3 at addr; returns the bytes to place at addr."""
    text = name.encode("ascii", "replace")
    if not name.isascii() or not 1 <= len(text) <= USB_STR3_MAX or len(text) == 31 or any(not 32 <= c <= 126 for c in text):
        sys.exit("--usb-audio-name: 1..%d printable ASCII characters, not 31" % USB_STR3_MAX)
    off = CONST_DATA[0] + USB_STR3_RECORD - 0xc016f780
    hdr, ptr = struct.unpack_from("<II", data, off)
    if hdr != USB_STR3_STOCK_HDR or ptr != USB_STR3_STOCK_PTR:
        sys.exit("USB string-3 record %#x is not the stock empty string record" % USB_STR3_RECORD)
    struct.pack_into("<II", data, off, (3 << 8) | (2 + 2 * len(text)), addr)
    return text + b"\0"


def usb_product_patch(data, name, addr):
    """Point string 2 at addr; returns the bytes to place at addr."""
    text = name.encode("ascii")
    if not 1 <= len(text) <= USB_PRODUCT_MAX or any(not 32 <= c <= 126 for c in text):
        sys.exit("--usb-product: 1..%d printable ASCII characters" % USB_PRODUCT_MAX)
    off = CONST_DATA[0] + USB_PRODUCT_RECORD - 0xc016f780
    hdr, ptr = struct.unpack_from("<II", data, off)
    if hdr >> 8 != 3 or ptr != USB_PRODUCT_STOCK_PTR:
        sys.exit("USB product record %#x is not the stock string record" % USB_PRODUCT_RECORD)
    struct.pack_into("<II", data, off, (3 << 8) | (2 + 2 * len(text)), addr)
    return text + b"\0"


def build(base_path, out_path, stock_path, diag=False, ui=False, usb_product=None, usb_audio_name=None,
          cf_header=False, gate=None, boot_anim=False):
    base = Path(base_path).read_bytes()
    try:
        kind = base_kind(base, Path(stock_path).read_bytes())
    except ValueError as exc:
        sys.exit(str(exc))
    lo, img, syms = elf_image(build_payload(diag, ui, cf_header, boot_anim))
    product_addr = None
    if usb_product is not None:
        img += b"\0" * (-len(img) % 4)
        product_addr = lo + len(img)
        img += usb_product.encode("ascii") + b"\0"
    str3_addr = None
    if usb_audio_name is not None:
        img += b"\0" * (-len(img) % 4)
        str3_addr = lo + len(img)
        img += usb_audio_name.encode("ascii") + b"\0"
    hooks = HOOKS + (DIAG_HOOKS if diag else []) + (UI_HOOKS if ui else []) + (CF_HEADER_HOOKS if cf_header else [])
    hooks += BOOT_HOOKS if boot_anim else []
    if lo != CTL_BASE or len(img) > CTL_SIZE:
        sys.exit("payload %#x+%#x does not match the reservation" % (lo, len(img)))
    if not (FREE_SDRAM[0] <= lo and lo + len(img) <= FREE_SDRAM[1]):
        sys.exit("payload outside the free SDRAM gap")

    cmds = list(ais_commands(base))
    close_off, op, entry = cmds[-1]
    if op != AIS_JUMP_CLOSE or close_off + 8 != len(base):
        sys.exit("unexpected AIS tail")
    for _, op, args in cmds:
        if op == AIS_SECTION_LOAD:
            a, n = args
            if a < lo + len(img) and lo < a + n:
                sys.exit("payload overlaps AIS section %#x+%#x" % (a, n))

    data = bytearray(base[:close_off])
    for vma, off, stock, target, sym in hooks:
        word = struct.unpack_from("<I", data, off)[0]
        if word != stock or callp_target(vma, word) != target:
            sys.exit("hook site %#x does not hold the stock CALLP" % vma)
        struct.pack_into("<I", data, off, callp_retarget(vma, word, syms[sym]))
    if gate is not None:
        vma, off, stock = GATE_SITE
        if struct.unpack_from("<I", data, off)[0] != stock:
            sys.exit("gate site %#x does not hold the stock MVKH 0x4366" % vma)
        try:
            struct.pack_into("<I", data, off, gate_word(gate))
        except ValueError as exc:
            sys.exit(str(exc))
    product_off = None
    if product_addr is not None:
        usb_product_patch(data, usb_product, product_addr)
        product_off = CONST_DATA[0] + USB_PRODUCT_RECORD - 0xc016f780
    str3_off = None
    if str3_addr is not None:
        usb_string3_patch(data, usb_audio_name, str3_addr)
        str3_off = CONST_DATA[0] + USB_STR3_RECORD - 0xc016f780
    padded = img + b"\0" * (-len(img) % 4)
    data += struct.pack("<III", AIS_SECTION_LOAD, lo, len(img)) + padded
    data += base[close_off:]

    # Verify: stock bytes unchanged except the hooks; walk the new AIS.
    changed = [i for i in range(close_off) if data[i] != base[i]]
    allowed = {off + k for _, off, _, _, _ in hooks for k in range(4)}
    if gate is not None:
        allowed |= set(range(GATE_SITE[1], GATE_SITE[1] + 4))
    if product_off is not None:
        allowed |= set(range(product_off, product_off + 8))
    if str3_off is not None:
        allowed |= set(range(str3_off, str3_off + 8))
    if not set(changed) <= allowed:
        sys.exit("unexpected byte changes at %s" % [hex(i) for i in changed if i not in allowed])
    if data[-8:] != base[-8:]:
        sys.exit("jump-and-close command changed")
    new_cmds = list(ais_commands(bytes(data)))
    load = new_cmds[-2]
    if load[1] != AIS_SECTION_LOAD or load[2] != (lo, len(img)):
        sys.exit("re-walk did not find the controller section")
    if bytes(data[load[0] + 12:load[0] + 12 + len(img)]) != img:
        sys.exit("controller payload mismatch after re-walk")
    for vma, off, _, _, sym in hooks:
        word = struct.unpack_from("<I", data, off)[0]
        if callp_target(vma, word) != syms[sym]:
            sys.exit("hook %#x does not reach %s" % (vma, sym))

    tmp = Path(str(out_path) + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, out_path)
    print("controller payload %#x..%#x (%d bytes)" % (lo, lo + len(img), len(img)))
    for vma, off, stock, _, sym in hooks:
        print("hook %#x: %08x -> %08x CALLP %s (%#x)" % (
            vma, stock, struct.unpack_from("<I", data, off)[0], sym, syms[sym]))
    if gate is not None:
        print("PROCESS OVERFLOW gate %#x: 230.0 -> %g" % (GATE_SITE[0], gate))
    if product_addr is not None:
        print("USB product string %r at %#x" % (usb_product, product_addr))
    if str3_addr is not None:
        print("USB string 3 (audio interface name) %r at %#x" % (usb_audio_name, str3_addr))
    print("wrote %s (%d bytes, base %s, SHA-256 %s)" % (
        out_path, len(data), kind,
        hashlib.sha256(data).hexdigest()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=str(ROOT / "build/fw/res1_493412.bin"))
    ap.add_argument("--out", default=str(ROOT / "build/fw/res1_controller_worker_candidate.bin"))
    ap.add_argument("--stock", default=str(ROOT / "build/fw/res1_493412.bin"),
                    help="stock v2.00 res1, to check a const-edited base")
    ap.add_argument("--diag-teardown", action="store_true",
                    help="OFFLINE diagnostic candidate (adds the c0120744 trace hook); "
                         "output is not accepted by the updater packager")
    ap.add_argument("--ui", action="store_true",
                    help="OFFLINE on-pedal status screen (adds the UpdateUI c013c76c pend hook); "
                         "with --diag-teardown the screen shows the diag readout")
    ap.add_argument("--usb-product",
                    help="USB product name (Windows MIDI port name), up to 31 characters; "
                         "stored in the controller section")
    ap.add_argument("--usb-audio-name",
                    help="USB string 3, the USB-audio interface name Windows shows for the audio "
                         "input (1..62 characters, not 31); stored in the controller section")
    ap.add_argument("--cf-header", action="store_true",
                    help="TEST: CF edit-page stage header (firmware/controller/cf_header.c; hooks c013c050, "
                         "c0135b08 -> cf_edit_draw)")
    ap.add_argument("--gate", type=float,
                    help="TEST: PROCESS OVERFLOW limit instead of 230.0 (e.g. 340; c0141b54 MVKH)")
    ap.add_argument("--boot-anim", action="store_true",
                    help="TEST: Comet Flower bloom animation in place of the start-up logo "
                         "(firmware/controller/cf_boot.c; hook c014db78)")
    a = ap.parse_args()
    build(a.base, a.out, a.stock, a.diag_teardown, a.ui, a.usb_product, a.usb_audio_name, a.cf_header,
          a.gate, a.boot_anim)
