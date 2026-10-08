"""Build the USB MIDI controller-mode main firmware (offline only).

    python tools/make_controller_fw.py [--base build/fw/res1_493412.bin]
                                       [--out build/fw/res1_controller.bin]

The base may be stock v2.00, the residency image, or stock with edits
inside the const-data section only (logo, start-up text).

Steps, each verified:
 1. compile firmware/controller/ with TI cl6x/lnk6x into one contiguous
    image at CTL_BASE (free SDRAM, recon/17 "Placement in SDRAM");
 2. insert one AIS section-load record for that image just before the
    final jump-and-close command;
 3. redirect the three stock CALLPs (HOOKS) to the controller entry points,
    keeping each word's unit and parallel bits;
 4. re-walk the AIS, check that only the expected bytes changed, and
    disassemble the hook words with dis6x.

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


def build_payload():
    OUT.mkdir(parents=True, exist_ok=True)
    run(CGT / "bin/cl6x", "--silicon_version=6740", "--abi=eabi", "--c99",
        "--opt_level=2", "--mem_model:data=far", "--mem_model:const=data",
        "--keep_asm", "--asm_directory=%s" % OUT, "--obj_directory=%s" % OUT,
        "--compile_only", SRC / "controller.c", SRC / "controller_hooks.asm")
    elf = OUT / "controller.elf"
    run(CGT / "bin/lnk6x", "--ram_model", "--map_file=%s" % (OUT / "controller.map"),
        "--output_file=%s" % elf, OUT / "controller.obj",
        OUT / "controller_hooks.obj", SRC / "controller.cmd")
    run(CGT / "bin/dis6x", elf, OUT / "controller.dis")
    return elf


def elf_image(elf):
    """Contiguous bytes of all allocated sections, plus the symbol table."""
    e = elf.read_bytes()
    shoff = struct.unpack_from("<I", e, 0x20)[0]
    shent, shnum, shstr = struct.unpack_from("<HHH", e, 0x2e)
    sh = [struct.unpack_from("<10I", e, shoff + k * shent) for k in range(shnum)]
    names = sh[shstr][4]
    name = lambda s: e[names + s[0]:e.index(b"\0", names + s[0])].decode()
    alloc = [s for s in sh if s[2] & 2 and s[5]]          # SHF_ALLOC, size > 0
    for s in alloc:
        if not (CTL_BASE <= s[3] and s[3] + s[5] <= CTL_BASE + CTL_SIZE):
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


def build(base_path, out_path, stock_path):
    base = Path(base_path).read_bytes()
    try:
        kind = base_kind(base, Path(stock_path).read_bytes())
    except ValueError as exc:
        sys.exit(str(exc))
    lo, img, syms = elf_image(build_payload())
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
    for vma, off, stock, target, sym in HOOKS:
        word = struct.unpack_from("<I", data, off)[0]
        if word != stock or callp_target(vma, word) != target:
            sys.exit("hook site %#x does not hold the stock CALLP" % vma)
        struct.pack_into("<I", data, off, callp_retarget(vma, word, syms[sym]))
    padded = img + b"\0" * (-len(img) % 4)
    data += struct.pack("<III", AIS_SECTION_LOAD, lo, len(img)) + padded
    data += base[close_off:]

    # Verify: stock bytes unchanged except the hooks; walk the new AIS.
    changed = [i for i in range(close_off) if data[i] != base[i]]
    allowed = {off + k for _, off, _, _, _ in HOOKS for k in range(4)}
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
    for vma, off, _, _, sym in HOOKS:
        word = struct.unpack_from("<I", data, off)[0]
        if callp_target(vma, word) != syms[sym]:
            sys.exit("hook %#x does not reach %s" % (vma, sym))

    tmp = Path(str(out_path) + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, out_path)
    print("controller payload %#x..%#x (%d bytes)" % (lo, lo + len(img), len(img)))
    for vma, off, stock, _, sym in HOOKS:
        print("hook %#x: %08x -> %08x CALLP %s (%#x)" % (
            vma, stock, struct.unpack_from("<I", data, off)[0], sym, syms[sym]))
    print("wrote %s (%d bytes, base %s, SHA-256 %s)" % (
        out_path, len(data), kind,
        hashlib.sha256(data).hexdigest()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=str(ROOT / "build/fw/res1_493412.bin"))
    ap.add_argument("--out", default=str(ROOT / "build/fw/res1_controller.bin"))
    ap.add_argument("--stock", default=str(ROOT / "build/fw/res1_493412.bin"),
                    help="stock v2.00 res1, to check a const-edited base")
    a = ap.parse_args()
    build(a.base, a.out, a.stock)
