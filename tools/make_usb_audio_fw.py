"""Build the USB audio silence-stream candidate main firmware (OFFLINE only).

    python tools/make_usb_audio_fw.py [--base <res1 image>] [--out <file>]

The base is stock v2.00 res1 or a controller candidate built from it. The
tool adds one AIS section load at c01a8000 (32 KiB) holding
firmware/usb_audio_proto/usb_audio.c + firmware/usb_audio/ua_glue.c + ua_thunks.asm, and
applies recon/20 2.6 patch list v2, reworked as follows:
  - all 7 CALLP c0160ec0 (stock descriptor builder) -> usb_audio_descriptor_veneer.
    This replaces P1..P3: the stock builder only fills its own array, so a
    replacement builder needs no pointer-array relocation;
  - c0145158 CALLP c0152410 (usbmidi_open) -> ua_usbmidi_open (P5 registration);
  - c015c674 "[!A0] BNOP c015c6ac,5" -> CALLP.S2 ua_map_thunk (P5 map writer);
  - c016f770/c016f774 MVK/MVKH 0x11818e80 -> usb_audio_sof_tick (P10 SOF hook).
With --tap (real-audio tap, ROADMAP C3) the payload is built from
usb_audio_tap.c (which includes usb_audio.c unchanged) into build/usb_audio_tap,
and the patch list changes:
  - c016f770/c016f774 -> usb_audio_sof_tick_tap (SOF packets from the ring);
  - 11818c88..11818c94, four zero words of dead padding after the audio Swi
    epilogue -> MVK/MVKH B31, B B31, NOP 5 to ua_tx_pack_tap (the stock
    1181->c0 veneer shape, as at 11818ea0);
  - 11818c64 CALLP 11818aa0 (TX pack) -> CALLP 11818c88. ua_tx_pack_tap runs
    the stock pack, then copies the block into the ring.
Every patched word is checked against its stock value first. Afterwards
only those bytes may differ; the AIS is re-walked and each patch decoded.

It never writes an updater and never touches the pedal. DO_NOT_FLASH.
"""
import argparse
import hashlib
import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_controller_fw as ctl  # noqa: E402

ROOT = ctl.ROOT
OUT = ROOT / "build" / "usb_audio"
PROTO = ROOT / "firmware" / "usb_audio_proto"
GLUE = ROOT / "firmware" / "usb_audio"
UA_BASE, UA_SIZE = 0xc01a8000, 0x8000

BUILDER = 0xc0160ec0
BUILDER_CALLS = [0xc0135014, 0xc0135168, 0xc0135258, 0xc0135568,
                 0xc0135694, 0xc01357e4, 0xc0152514]
# (site, exact stock word or None, kind, stock target / field value, symbol)
PATCHES = [(a, None, "callp", BUILDER, "usb_audio_descriptor_veneer")
           for a in BUILDER_CALLS] + [
    (0xc0145158, 0x101a5a13, "callp", 0xc0152410, "ua_usbmidi_open"),
    (0xc015c674, 0xd026a120, "callp_over", None, "ua_map_thunk"),
    (0xc016f770, 0x0fc7402a, "mvk_lo", 0x8e80, "usb_audio_sof_tick"),
    (0xc016f774, 0x0f88c0ea, "mvk_hi", 0x1181, "usb_audio_sof_tick"),
]
TAP_VENEER = 0x11818c88
# Stock 1181->c0 veneer words at 11818ea0..11818eac: MVK.S2/MVKH.S2 B31,
# B.S2 B31, NOP 5. Only the MVK/MVKH fields are replaced.
VENEER_MVK, VENEER_MVKH, VENEER_B, VENEER_NOP5 = (0x0ffaca2a, 0x0fe00a6a,
                                                  0x007c0362, 0x00008000)
TAP_PATCHES = [p for p in PATCHES if p[2] not in ("mvk_lo", "mvk_hi")] + [
    (0xc016f770, 0x0fc7402a, "mvk_lo", 0x8e80, "usb_audio_sof_tick_tap"),
    (0xc016f774, 0x0f88c0ea, "mvk_hi", 0x1181, "usb_audio_sof_tick_tap"),
    (TAP_VENEER + 0, 0, "veneer_lo", None, "ua_tx_pack_tap"),
    (TAP_VENEER + 4, 0, "veneer_hi", None, "ua_tx_pack_tap"),
    (TAP_VENEER + 8, 0, "fixed", VENEER_B, None),
    (TAP_VENEER + 12, 0, "fixed", VENEER_NOP5, None),
    (0x11818c64, 0x1fffc812, "callp", 0x11818aa0, TAP_VENEER),
]
TAP_OUT = ROOT / "build" / "usb_audio_tap"
TAP_RETAIN = ["--retain=ua_tx_pack_tap", "--retain=usb_audio_sof_tick_tap"]

# A fresh unconditional, non-parallel CALLP.S2: the stock word at c0134e14
# ("CALLP.S2 0xc015d428,B3"); only its displacement is replaced.
CALLP_S2_TEMPLATE = 0x1050c512


def build_payload(tap=False, pattern=False):
    out = (TAP_OUT / "pattern") if pattern else TAP_OUT if tap else OUT
    out.mkdir(parents=True, exist_ok=True)
    main = PROTO / ("usb_audio_tap.c" if tap else "usb_audio.c")
    srcs = [main, PROTO / "usb_audio_hooks.asm",
            GLUE / "ua_glue.c", GLUE / "ua_thunks.asm"]
    objs = [out / (p.stem + ".obj") for p in srcs]
    ctl.run(ctl.CGT / "bin/cl6x", "--silicon_version=6740", "--abi=eabi", "--c99",
            "--opt_level=2", "--mem_model:data=far", "--mem_model:const=data",
            "--keep_asm", "--asm_directory=%s" % out, "--obj_directory=%s" % out,
            *(["--define=UA_TAP_PATTERN"] if pattern else []),
            "--compile_only", *srcs)
    elf = out / "usb_audio.elf"
    ctl.run(ctl.CGT / "bin/lnk6x", "--ram_model", *(TAP_RETAIN if tap else []),
            "--map_file=%s" % (out / "usb_audio.map"),
            "--output_file=%s" % elf, *objs, GLUE / "ua.cmd")
    ctl.run(ctl.CGT / "bin/dis6x", elf, out / "usb_audio.dis")
    return elf


def vma_offset(data, vma):
    hits = [o + 12 + (vma - args[0]) for o, op, args in ctl.ais_commands(data)
            if op == ctl.AIS_SECTION_LOAD and args[0] <= vma < args[0] + args[1]]
    if len(hits) != 1:
        raise ValueError("%#x is not in exactly one AIS section" % vma)
    return hits[0]


def mvk_field(word):
    return (word >> 7) & 0xffff


def mvk_set(word, value):
    return (word & ~(0xffff << 7)) | ((value & 0xffff) << 7)


def stock_ok(vma, word, kind, ref):
    if kind == "callp":
        return ctl.callp_target(vma, word) == ref
    if kind in ("mvk_lo", "mvk_hi"):
        return mvk_field(word) == ref
    return True


def target_of(sym, syms):
    return sym if isinstance(sym, int) else syms[sym]


def patched_word(vma, word, kind, target):
    if kind == "callp":
        return ctl.callp_retarget(vma, word, target)
    if kind == "callp_over":
        return ctl.callp_retarget(vma, CALLP_S2_TEMPLATE, target)
    if kind == "mvk_lo":
        return mvk_set(word, target & 0xffff)
    if kind == "veneer_lo":
        return mvk_set(VENEER_MVK, target & 0xffff)
    if kind == "veneer_hi":
        return mvk_set(VENEER_MVKH, target >> 16)
    return mvk_set(word, target >> 16)


def expected(kind, target):
    if kind in ("callp", "callp_over"):
        return target
    return target & 0xffff if kind in ("mvk_lo", "veneer_lo") else target >> 16


def decode(vma, word, kind):
    if kind in ("callp", "callp_over"):
        return ctl.callp_target(vma, word)
    return mvk_field(word)


def build(base_path, out_path, tap=False, pattern=False):
    tap = tap or pattern
    base = Path(base_path).read_bytes()
    lo, img, syms = ctl.elf_image(build_payload(tap, pattern), (UA_BASE, UA_SIZE))
    if lo != UA_BASE or len(img) > UA_SIZE:
        sys.exit("payload %#x+%#x does not match the reservation" % (lo, len(img)))
    if not (ctl.FREE_SDRAM[0] <= lo and lo + len(img) <= ctl.FREE_SDRAM[1]):
        sys.exit("payload outside the free SDRAM gap")
    cmds = list(ctl.ais_commands(base))
    close_off, op, _ = cmds[-1]
    if op != ctl.AIS_JUMP_CLOSE or close_off + 8 != len(base):
        sys.exit("unexpected AIS tail")
    for _, op, args in cmds:
        if op == ctl.AIS_SECTION_LOAD:
            a, n = args
            if a < lo + len(img) and lo < a + n:
                sys.exit("payload overlaps AIS section %#x+%#x" % (a, n))

    data = bytearray(base[:close_off])
    plan = []
    for vma, stock, kind, ref, sym in (TAP_PATCHES if tap else PATCHES):
        off = vma_offset(base, vma)
        word = struct.unpack_from("<I", data, off)[0]
        if (stock is not None and word != stock) or not stock_ok(vma, word, kind, ref):
            sys.exit("patch site %#x does not hold the expected stock word (%08x)" % (vma, word))
        new = ref if kind == "fixed" else patched_word(vma, word, kind, target_of(sym, syms))
        struct.pack_into("<I", data, off, new)
        plan.append((vma, off, word, new, kind, sym))
    padded = img + b"\0" * (-len(img) % 4)
    data += struct.pack("<III", ctl.AIS_SECTION_LOAD, lo, len(img)) + padded
    data += base[close_off:]

    changed = [i for i in range(close_off) if data[i] != base[i]]
    allowed = {p[1] + k for p in plan for k in range(4)}
    if not set(changed) <= allowed:
        sys.exit("unexpected byte changes at %s" % [hex(i) for i in changed if i not in allowed])
    if data[-8:] != base[-8:]:
        sys.exit("jump-and-close command changed")
    load = list(ctl.ais_commands(bytes(data)))[-2]
    if load[1] != ctl.AIS_SECTION_LOAD or load[2] != (lo, len(img)):
        sys.exit("re-walk did not find the USB audio section")
    if bytes(data[load[0] + 12:load[0] + 12 + len(img)]) != img:
        sys.exit("USB audio payload mismatch after re-walk")
    for vma, off, _, new, kind, sym in plan:
        got = struct.unpack_from("<I", data, off)[0]
        if kind == "fixed":
            ok = got == new
        elif kind in ("veneer_lo", "veneer_hi"):
            ok = mvk_field(got) == expected(kind, target_of(sym, syms))
        else:
            ok = decode(vma, got, kind) == expected(kind, target_of(sym, syms))
        if not ok:
            sys.exit("patch %#x does not reach %s" % (vma, sym))

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(str(out_path) + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, out_path)
    print("usb audio payload %#x..%#x (%d bytes)" % (lo, lo + len(img), len(img)))
    for vma, off, old, new, kind, sym in plan:
        dest = "" if sym is None else " %s (%#x)" % (sym if isinstance(sym, str) else "veneer", target_of(sym, syms))
        print("patch %#x: %08x -> %08x %s%s" % (vma, old, new, kind, dest))
    print("wrote %s (%d bytes, SHA-256 %s)" % (out_path, len(data),
                                               hashlib.sha256(data).hexdigest()))
    return bytes(data), plan, syms


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=str(ROOT / "build/fw/res1_493412.bin"))
    ap.add_argument("--out")
    ap.add_argument("--tap", action="store_true",
                    help="real-audio tap build (ROADMAP C3) instead of silence")
    ap.add_argument("--tap-pattern", action="store_true",
                    help="diagnostic tap build: counter (L) + 1002 Hz sine (R) instead of the "
                         "pedal audio; analyse captures with tools/ua_capture.py")
    a = ap.parse_args()
    out = a.out or str(ROOT / ("build/usb_audio_tap/DO_NOT_FLASH_usb_audio_tap.bin" if a.tap or a.tap_pattern
                               else "build/usb_audio/DO_NOT_FLASH_usb_audio_silence.bin"))
    build(a.base, out, a.tap, a.tap_pattern)
