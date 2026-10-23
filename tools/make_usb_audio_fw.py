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
# --stems (8 channels, drums and looper alone on 5-6 and 8): two more veneers in
# dead padding, each four zero words after a BNOP B3,5 return, before the next
# function or fetch packet (11818d48 BNOP | 11818d4c..11818d5c zero | 11818d60;
# 11818e80 BNOP | 11818e84..11818e9c zero | 11818ea0), and three call sites:
#   11818d64 CALLP 11817640 (drum mixer, inside 11818d60, parallel with a STW)
#   11818bc0 CALLP 11818e60 (looper dispatcher, Pre, A4 = 0)
#   11818c50 CALLP 11818e60 (looper dispatcher, Post, A4 = 1)
DRUM_VENEER, LOOP_VENEER = 0x11818d4c, 0x11818e84


def veneer(at, sym):
    return [(at + 0, 0, "veneer_lo", None, sym), (at + 4, 0, "veneer_hi", None, sym),
            (at + 8, 0, "fixed", VENEER_B, None), (at + 12, 0, "fixed", VENEER_NOP5, None)]


STEM_PATCHES = TAP_PATCHES + veneer(DRUM_VENEER, "ua_drums_tap") + veneer(LOOP_VENEER, "ua_looper_tap") + [
    (0x11818d64, 0x1ffd1c12, "callp", 0x11817640, DRUM_VENEER),
    (0x11818bc0, 0x10005413, "callp", 0x11818e60, LOOP_VENEER),
    (0x11818c50, 0x10004412, "callp", 0x11818e60, LOOP_VENEER),
]
STEM_RETAIN = ["--retain=ua_drums_tap", "--retain=ua_looper_tap"]
# --bench: the stock veneer at 11818eb0 (MVK/MVKH B31 = c01502cc, B B31, NOP 5),
# called only by the slot loop (11818c04) before each slot, is re-aimed at
# ua_slot_enter. Only the two 16-bit constant fields change.
SLOT_VENEER = 0x11818eb0
BENCH_PATCHES = STEM_PATCHES + [
    (SLOT_VENEER + 0, 0x0f81662a, "retarget_lo", 0x02cc, "ua_slot_enter"),
    (SLOT_VENEER + 4, 0x0fe00aea, "retarget_hi", 0xc015, "ua_slot_enter"),
]
# --probe: the SysEx hook (docs/helpers/FW_RND_S12_SYSEX_HOOK_2026-10-22.md). The compact
# pair at c0129324 (CALLP c0128e54 | BNOP c012932c,5) becomes one 32-bit CALLP.S2 to
# cfp_sysex_thunk, and the packet header c012933c marks word 1 as 32-bit
# (layout 1010010b -> 1010000b; that word's p-bits in the header become unused).
PROBE_PATCHES = [
    (0xc0129324, 0xa18ab35b, "callp_over", None, "cfp_sysex_thunk"),
    (0xc012933c, 0xea40a000, "fixed", 0xea00a000, None),
]
TAP_OUT = ROOT / "build" / "usb_audio_tap"
TAP_RETAIN = ["--retain=ua_tx_pack_tap", "--retain=usb_audio_sof_tick_tap"]

# A fresh unconditional, non-parallel CALLP.S2: the stock word at c0134e14
# ("CALLP.S2 0xc015d428,B3"); only its displacement is replaced.
CALLP_S2_TEMPLATE = 0x1050c512


def build_payload(tap=False, pattern=False, nch=2, stems=False, fx=False, bench=False, pairs8=False, watchdog=False, probe=False,
                  cpu_meter=False):
    out = (TAP_OUT / "pattern") if pattern else (TAP_OUT / "pairs8") if pairs8 else (TAP_OUT / "probe") if probe else (TAP_OUT / "bench_wd") if watchdog else (TAP_OUT / "bench") if bench else (TAP_OUT / "ch10") if nch == 10 else (TAP_OUT / "stems_fx") if fx else (TAP_OUT / "stems") if stems else (TAP_OUT / "ch8") if nch == 8 else TAP_OUT if tap else OUT
    if cpu_meter:
        out = out / "cpu"
    out.mkdir(parents=True, exist_ok=True)
    main = PROTO / ("usb_audio_tap.c" if tap else "usb_audio.c")
    srcs = [main, PROTO / "usb_audio_hooks.asm",
            GLUE / "ua_glue.c", GLUE / "ua_thunks.asm"] + ([GLUE / "cfp_thunks.asm"] if probe else [])
    objs = [out / (p.stem + ".obj") for p in srcs]
    ctl.run(ctl.CGT / "bin/cl6x", "--silicon_version=6740", "--abi=eabi", "--c99",
            "--opt_level=2", "--mem_model:data=far", "--mem_model:const=data",
            "--keep_asm", "--asm_directory=%s" % out, "--obj_directory=%s" % out,
            *(["--define=UA_TAP_PATTERN"] if pattern else []),
            *(["--define=UA_NCH=%d" % nch, "--define=UA_AUDIO_STRING=3"] if nch in (8, 10) else []),
            *(["--define=UA_STEMS"] if stems else []),
            *(["--define=UA_FX"] if fx else []),
            *(["--define=UA_BENCH"] if bench else []),
            *(["--define=UA_WATCHDOG"] if watchdog else []),
            *(["--define=UA_PROBE"] if probe else []),
            *(["--define=UA_CPU_METER"] if cpu_meter else []),
            *(["--define=UA_PAIRS8"] if pairs8 else []),
            "--compile_only", *srcs)
    elf = out / "usb_audio.elf"
    ctl.run(ctl.CGT / "bin/lnk6x", "--ram_model", *(TAP_RETAIN if tap else []), *(STEM_RETAIN if stems else []), *(["--retain=ua_slot_enter"] if bench else []), *(["--retain=cfp_sysex_thunk"] if probe else []),
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
    if kind in ("mvk_lo", "mvk_hi", "retarget_lo", "retarget_hi"):
        return mvk_field(word) == ref
    return True


def target_of(sym, syms):
    return sym if isinstance(sym, int) else syms[sym]


def patched_word(vma, word, kind, target):
    if kind == "callp":
        return ctl.callp_retarget(vma, word, target)
    if kind == "callp_over":
        return ctl.callp_retarget(vma, CALLP_S2_TEMPLATE, target)
    if kind in ("mvk_lo", "retarget_lo"):
        return mvk_set(word, target & 0xffff)
    if kind == "veneer_lo":
        return mvk_set(VENEER_MVK, target & 0xffff)
    if kind == "veneer_hi":
        return mvk_set(VENEER_MVKH, target >> 16)
    return mvk_set(word, target >> 16)


def expected(kind, target):
    if kind in ("callp", "callp_over"):
        return target
    return target & 0xffff if kind in ("mvk_lo", "veneer_lo", "retarget_lo") else target >> 16


def decode(vma, word, kind):
    if kind in ("callp", "callp_over"):
        return ctl.callp_target(vma, word)
    return mvk_field(word)


def build(base_path, out_path, tap=False, pattern=False, nch=2, stems=False, fx=False, bench=False, pairs8=False, watchdog=False, probe=False,
          cpu_meter=False):
    bench = bench or watchdog or probe
    fx = fx or bench or pairs8 or nch == 10        # the 10-channel layout is the FX layout (stems hooks)
    stems = stems or fx
    if stems and nch != 10:
        nch = 8
    tap = tap or pattern or nch >= 8
    base = Path(base_path).read_bytes()
    if nch >= 8:
        # IF2's iInterface names string 3: the base must carry it, or Windows
        # would show an empty audio device name.
        off = ctl.CONST_DATA[0] + ctl.USB_STR3_RECORD - 0xc016f780
        if int.from_bytes(base[off:off + 4], "little") == ctl.USB_STR3_STOCK_HDR:
            sys.exit("--tap8 needs a base built with make_controller_fw.py --usb-audio-name")
    lo, img, syms = ctl.elf_image(build_payload(tap, pattern, nch, stems, fx, bench, pairs8, watchdog, probe, cpu_meter), (UA_BASE, UA_SIZE))
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
    for vma, stock, kind, ref, sym in (BENCH_PATCHES + (PROBE_PATCHES if probe else []) if bench else STEM_PATCHES if stems else TAP_PATCHES if tap else PATCHES):
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
    ap.add_argument("--pairs8", action="store_true",
                    help="8 channels, every pair usable: 1-2 mix, 3-4 guitar FX, 5-6 drums, 7-8 DI (no looper)")
    ap.add_argument("--tap10", action="store_true",
                    help="10 channels, every pair usable: 1-2 mix, 3-4 guitar FX, 5-6 drums, 7-8 DI, 9-10 looper")
    ap.add_argument("--tap8", action="store_true",
                    help="8-channel tap: 1-2 output, 3 DI, 4 right ADC, 5-8 internal mix buses")
    ap.add_argument("--stems", action="store_true",
                    help="8-channel tap with drums alone on 5-6 and the looper alone on 8 "
                         "(1-2 output, 3-4 pre-master mix, 7 DI)")
    ap.add_argument("--fx", action="store_true",
                    help="stems layout with 1-2 = output without the converter gain (no USB clipping) "
                         "and 3-4 = guitar FX only (no drums, no Post looper)")
    ap.add_argument("--bench", action="store_true",
                    help="FX layout with a CPU timing frame per block on USB channel 8 "
                         "(tools/ua_bench.py) instead of the looper")
    ap.add_argument("--watchdog", action="store_true",
                    help="--bench plus the slot watchdog (UA_WATCHDOG): a slot over 64k cycles for 16 "
                         "blocks in a row is bypassed until the loader installs a new effect there; "
                         "tripped slots in bits 27..31 of the bench period word (TEST builds only)")
    ap.add_argument("--probe", action="store_true",
                    help="CF Probe TEST build: --bench (timing frames on channel 8) plus the watch stream "
                         "on channel 7 instead of the DI (tools/cf_probe.py watch); with --watchdog too if given")
    ap.add_argument("--tap-pattern", action="store_true",
                    help="diagnostic tap build: counter (L) + 1002 Hz sine (R) instead of the "
                         "pedal audio; analyse captures with tools/ua_capture.py")
    ap.add_argument("--cpu-meter", action="store_true",
                    help="with --bench/--probe: publish the CPU budget record at 0xc01a8020 for the CF screen meter "
                         "(docs/BUDGET_MODEL_2026-10-23.md)")
    a = ap.parse_args()
    out = a.out or str(ROOT / ("build/usb_audio_tap/DO_NOT_FLASH_usb_audio_tap.bin" if a.tap or a.tap_pattern or a.tap8 or a.stems or a.fx or a.bench or a.watchdog or a.probe or a.tap10 or a.pairs8
                               else "build/usb_audio/DO_NOT_FLASH_usb_audio_silence.bin"))
    build(a.base, out, a.tap, a.tap_pattern, 10 if a.tap10 else 8 if a.tap8 else 2, a.stems, a.fx, a.bench, a.pairs8, a.watchdog, a.probe, a.cpu_meter)
