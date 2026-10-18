"""CPU bench over USB: measure what every effect costs on the pedal, automatically.

    python tools/ua_bench.py measure [--seconds 4] [--label NAME]
    python tools/ua_bench.py run [--plan plan.json] [--location 50] [--seconds 4]
    python tools/ua_bench.py patch <out.ZPTC> <effect|-> <effect|-> ... (up to 5)
    python tools/ua_bench.py decode <take.wav>

Needs the bench firmware (make_usb_audio_fw.py --bench, docs/CF_BENCH_2026-10-17.md): every
16-sample audio block, USB channel 8 carries a frame of TSCL (CPU cycle counter) differences:
sync 0x7e5a, sequence (11 bits) | slots-that-ran mask << 11, then seven u32 (lo, hi): slot 0..4
cost, busy (Pre looper -> TX pack) and the block period. Slot 4 also holds the patch-level stage
and the output-EQ slot: the empty-patch baseline is subtracted in `run` reports.

measure: capture, decode, print per-slot cycles (median / 99th percentile / max), busy and the
period, load % = cycles / period (the period is measured with the same counter, so the
percentages need no clock assumption), lost frames, and slow blocks (period > 1.5 x median: the
Swi missed a block, the symptom of an overload).

run: for each test of the plan (default: empty baseline, every installed CF and stock counterpart
alone in slot 1, then the CF effects five times, then the shootout chains), builds a patch with
the effects at their default knob values, writes it to --location (read back byte for byte, as
tools/patch_g1.py does), selects it with a MIDI Program Change, checks with the pedal's current-
patch dump that it really is the active patch (else asks you to select it and press Enter),
waits for the slots to load, measures, and writes build/bench/<time>.{json,md}.
Never touches firmware or the effect list; only the one patch location is rewritten.
"""
import argparse
import json
import re
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

SYNC = 0x7E5A
FRAME = 16
NAMES = ["slot1", "slot2", "slot3", "slot4", "slot5", "busy", "period"]
BENCH_CH = 7            # USB channel 8 (0-based)
EMPTY_SLOT = bytes([0x01]) + bytes(23)
# EDTB slot entry (zoom-zt2 decode_preset.py EDTB2), as one little-endian 192-bit number:
# bit 0 on, bits 1..29 effect id, then param1..12 with these widths.
PARAM_BITS = [12, 12, 12, 12, 12, 8, 8, 8, 12, 12, 12, 12]


# ---------------------------------------------------------------- frames
def frames(words):
    """Decode bench frames from a sequence of channel-8 words (unsigned 16-bit)."""
    w = [int(x) & 0xFFFF for x in words]
    i = 0
    while i + FRAME <= len(w):
        if w[i] != SYNC:
            i += 1
            continue
        f = w[i:i + FRAME]
        v = [f[2 + 2 * k] | f[3 + 2 * k] << 16 for k in range(7)]
        yield {"seq": f[1] & 0x7FF, "mask": f[1] >> 11, "slots": v[:5], "busy": v[5],
               "period": v[6], "at": i}
        i += FRAME


def stats(fr):
    """Per-slot and whole-block statistics from decoded frames."""
    fr = fr[1:]                                   # the first period has no predecessor
    out = {"frames": len(fr)}
    if not fr:
        return out
    seq = np.array([f["seq"] for f in fr])
    out["lost_frames"] = int(np.sum((np.diff(seq) - 1) % 2048))
    period = np.array([f["period"] for f in fr], dtype=float)
    pmed = float(np.median(period))
    out["period_median"] = pmed
    out["slow_blocks"] = int(np.sum(period > 1.5 * pmed))
    ran = [f for f in fr if f["mask"] == 0x1F]
    out["chain_skipped_blocks"] = len(fr) - len(ran)
    for k, name in enumerate(NAMES):
        if k < 5:
            v = np.array([f["slots"][k] for f in ran], dtype=float)
        else:
            v = np.array([f["busy" if k == 5 else "period"] for f in (ran if k == 5 else fr)], dtype=float)
        if len(v) == 0:
            continue
        out[name] = {"median": float(np.median(v)), "p99": float(np.percentile(v, 99)),
                     "max": float(v.max()), "load_pct": 100.0 * float(np.median(v)) / pmed}
    return out


def table(rows, baseline=None):
    """Markdown table; with a baseline (empty patch), slot costs are shown above it."""
    head = "| test | " + " | ".join(NAMES[:5]) + " | busy | busy % | max busy % | slow | lost |\n"
    head += "|---" * 11 + "|\n"
    lines = []
    for name, s in rows:
        if "slot1" not in s:
            lines.append("| %s | (no complete frames) |" % name)
            continue
        cells = []
        for k in range(5):
            m = s[NAMES[k]]["median"] - (baseline[NAMES[k]]["median"] if baseline else 0)
            cells.append("%.0f" % m)
        p = s["period_median"]
        lines.append("| %s | %s | %.0f | %.1f | %.1f | %d | %d |" % (
            name, " | ".join(cells), s["busy"]["median"], 100 * s["busy"]["median"] / p,
            100 * s["busy"]["max"] / p, s["slow_blocks"], s["lost_frames"]))
    return head + "\n".join(lines) + "\n"


def print_stats(label, s):
    print("== %s: %d frames, period median %.0f cycles, slow blocks %d, lost %d, chain skipped %d"
          % (label, s["frames"], s.get("period_median", 0), s.get("slow_blocks", 0),
             s.get("lost_frames", 0), s.get("chain_skipped_blocks", 0)))
    for name in NAMES:
        if name in s:
            v = s[name]
            print("  %-7s median %8.0f  p99 %8.0f  max %8.0f  (%5.1f %% of the period)"
                  % (name, v["median"], v["p99"], v["max"], v["load_pct"]))


def capture(seconds):
    import ua_capture8
    data = ua_capture8.record(seconds, 8)
    return data, list(frames(data[:, BENCH_CH].astype(np.uint16)))


# ---------------------------------------------------------------- patches
def zd2_info(path):
    """(effect id, [default of each knob]) from `zd2 inspect` (OnOff and the name entry skipped)."""
    out = subprocess.run([str(ROOT / ".venv/Scripts/zd2"), "inspect", str(path)],
                         capture_output=True, text=True, check=True).stdout
    eid = int(re.search(r"Effect ID:\s+0x([0-9A-Fa-f]+)", out).group(1), 16)
    params = re.findall(r"param\s+(\S+)\s+max\s+(\d+)\s+default\s+(\d+)", out)
    knobs = [int(d) for name, mx, d in params if name != "OnOff" and int(mx) != 0xFFFFFFFF]
    return eid, knobs[:12]


def slot_entry(eid, knobs, on=True):
    v = (1 if on else 0) | (eid & ((1 << 29) - 1)) << 1
    pos = 30
    for k, width in enumerate(PARAM_BITS):
        x = knobs[k] if k < len(knobs) else 0
        if not 0 <= x < (1 << width):
            raise ValueError("param %d = %d does not fit %d bits" % (k + 1, x, width))
        v |= x << pos
        pos += width
    return v.to_bytes(24, "little")


def decode_entry(b):
    v = int.from_bytes(b, "little")
    knobs, pos = [], 30
    for width in PARAM_BITS:
        knobs.append((v >> pos) & ((1 << width) - 1))
        pos += width
    return v & 1, (v >> 1) & ((1 << 29) - 1), knobs


def make_patch(slots, name="CF BENCH"):
    """slots: up to 5 of (effect id, knobs) or None; the rest stay empty."""
    import patch_g1
    raw = bytearray(patch_g1.make_blank())
    n = struct.unpack_from("<I", raw, 12)[0]
    if len(slots) > n:
        raise ValueError("%d slots requested, the template has %d" % (len(slots), n))
    ids_off = raw.find(b"TXJ1") - 4 * n
    edtb = raw.find(b"EDTB")
    for i, s in enumerate(slots):
        if s is None:
            continue
        eid, knobs = s
        struct.pack_into("<I", raw, ids_off + 4 * i, eid)
        raw[edtb + 8 + 24 * i:edtb + 8 + 24 * i + 24] = slot_entry(eid, knobs)
    nm = name.encode("ascii")[:10].ljust(10)
    off = raw.find(b"PTCF")
    raw[off + 0x1A:off + 0x24] = nm
    return bytes(raw)


def effect_library():
    """Effect name (as installed by the shootout image) -> ZD2 path for zd2_info."""
    lib = {}
    for p in sorted((ROOT / "build").glob("*.ZD2")):
        lib[p.stem] = p
    stock = ROOT / "build/bench/stock"
    if not stock.exists():
        import g1fs
        stock.mkdir(parents=True)
        img = (ROOT / "build/fw/res3_3137536.bin").read_bytes()
        flat = []

        def walk(x):
            if isinstance(x, tuple) and isinstance(x[0], str):
                flat.append(x)
            elif isinstance(x, (list, tuple)):
                for y in x:
                    walk(y)
        walk(g1fs.current_dir(img))
        for n, first, size, *_ in flat:
            if n.upper().endswith(".ZD2"):
                (stock / n).write_bytes(g1fs.read_file(img, first, size))
    for p in sorted(stock.glob("*.ZD2")):
        lib.setdefault(p.stem, p)
    return lib


CF = ["DYNACX", "MISTRX", "CE2X", "DRV808X", "RATX", "MUFFX", "DR103"]
STOCK = ["COMP", "VINFLNGR", "STEREOCH", "ANDLY_3S", "TS_DRIVE", "SQUEAK", "NYC_MUFF", "HW100_1U"]


def default_plan():
    plan = [{"name": "empty (baseline)", "slots": []}]
    plan += [{"name": e + " alone", "slots": [e]} for e in CF + STOCK]
    plan += [{"name": e + " x5", "slots": [e] * 5} for e in ["DYNACX", "MISTRX", "CE2X"]]
    plan += [{"name": "shootout stock", "slots": ["COMP", "NYC_MUFF", "HW100_1U", "VINFLNGR", "ANDLY_3S"]},
             {"name": "shootout CF", "slots": ["DYNACX", "MUFFX", "DR103", "MISTRX", "ANDLY_3S"]}]
    return plan


# ---------------------------------------------------------------- pedal
def pedal_session():
    from backup_g1 import GuardedPort, zoomzt2
    import pedal_ports
    logdir = ROOT / "build" / "pedal-logs"
    logdir.mkdir(parents=True, exist_ok=True)
    log = open(logdir / "wire.log", "a")
    pedal_ports.register_zoomzt2(zoomzt2)
    pedal = zoomzt2.zoomzt2()
    if not pedal.connect():
        sys.exit("FAIL: no 'ZOOM G' / 'Comet Flower' MIDI port found.")
    pedal.inport = GuardedPort(pedal.inport, log)
    pedal.outport = GuardedPort(pedal.outport, log)
    pedal.pcmode_on()
    return pedal


def load_patch(location, data, ids):
    """Write, read back, select by Program Change, confirm it is the current patch."""
    import mido
    pedal = pedal_session()
    try:
        pedal.patch_upload(location, data)
        if bytes(pedal.patch_download(location)) != data:
            sys.exit("patch %d: read back differs; stopping" % location)
        pedal.outport.send(mido.Message("program_change", program=location - 1))
        time.sleep(0.5)
        cur = bytes(pedal.patch_download_current() or b"")
    finally:
        pedal.disconnect()
    if not cur or ids_of(cur) != ids:
        input("  The pedal did not switch by itself: select patch %d on the pedal, then press Enter. "
              % location)


def ids_of(patch):
    n = struct.unpack_from("<I", patch, 12)[0]
    off = patch.find(b"TXJ1") - 4 * n
    return list(struct.unpack_from("<%dI" % n, patch, off))


def run(plan, location, seconds):
    lib = effect_library()
    info = {}
    rows = []
    stamp = time.strftime("%Y%m%d_%H%M%S")
    outdir = ROOT / "build" / "bench"
    outdir.mkdir(parents=True, exist_ok=True)
    for test in plan:
        slots = []
        for e in test["slots"]:
            if e not in lib:
                sys.exit("effect %s: no ZD2 found (build it or check the name)" % e)
            if e not in info:
                info[e] = zd2_info(lib[e])
            slots.append(info[e])
        data = make_patch(slots)
        print("== %s" % test["name"], flush=True)
        load_patch(location, data, ids_of(data))
        time.sleep(1.5)                                   # slots load, ramps settle
        _, fr = capture(seconds)
        s = stats(fr)
        print_stats(test["name"], s)
        rows.append((test["name"], s))
        (outdir / (stamp + ".json")).write_text(json.dumps(rows, indent=1))
    base = next((s for n, s in rows if n.startswith("empty") and "slot1" in s), None)
    md = "# CPU bench %s\n\nCycles above the empty patch (slot 5 includes patch level + output EQ in the " \
         "baseline). busy %% = Pre looper -> TX pack over the measured block period.\n\n" % stamp
    md += table(rows, base)
    (outdir / (stamp + ".md")).write_text(md)
    print(md)
    print("wrote", outdir / (stamp + ".md"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--seconds", type=float, default=4)
    m.add_argument("--label", default="current patch")
    r = sub.add_parser("run")
    r.add_argument("--plan")
    r.add_argument("--location", type=int, default=50)
    r.add_argument("--seconds", type=float, default=4)
    p = sub.add_parser("patch")
    p.add_argument("out")
    p.add_argument("effects", nargs="+")
    d = sub.add_parser("decode")
    d.add_argument("wav")
    a = ap.parse_args()
    if a.cmd == "measure":
        _, fr = capture(a.seconds)
        print_stats(a.label, stats(fr))
    elif a.cmd == "decode":
        import ua_capture8
        data = ua_capture8.load(a.wav)
        print_stats(a.wav, stats(list(frames(data[:, BENCH_CH].astype(np.uint16)))))
    elif a.cmd == "patch":
        lib = effect_library()
        slots = [None if e == "-" else zd2_info(lib[e]) for e in a.effects]
        Path(a.out).write_bytes(make_patch(slots))
        print("wrote", a.out)
    else:
        plan = json.loads(Path(a.plan).read_text()) if a.plan else default_plan()
        run(plan, a.location, a.seconds)


if __name__ == "__main__":
    main()
