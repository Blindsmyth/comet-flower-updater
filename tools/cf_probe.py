"""CF Probe link host tool (TEST firmware only; docs/FW_RND_BRIEF5_2026-10-22.md).

    python tools/cf_probe.py ping
    python tools/cf_probe.py peek <address> [<length>]          (hex dump, length <= 512)
    python tools/cf_probe.py dump <address> <length> <out.bin>  (any length, 512 B per request)
    python tools/cf_probe.py watch-set <address>...              (replace the watch list, <= 64)
    python tools/cf_probe.py watch [--seconds 4] [--csv out.csv]
    python tools/cf_probe.py poll [--seconds 10] [--region ADDR:LEN]... [--out run.json]

poll: works over MIDI alone (no USB audio mode needed): reads whole regions round after
round (about 15 ms per request) and reports every 32-bit word that changed, with its values
and times. Default regions cover watch list v1 and their neighbourhoods; --region adds or
replaces them. --out keeps every round for later diffing.

SysEx (docs/helpers/FW_RND_S12_SYSEX_HOOK_2026-10-22.md): F0 52 00 6E 64 'CFPR' <op> ... F7,
the reply carries the same header and the op in lower case ('e' = refused). Numbers are 7-bit
little-endian groups (address 5 bytes, length 2), data MIDI-packed (7 bytes -> top-bit byte +
7 low bytes). Only RAM can be read (L2 0x11800000.., L1D 0x11f00000.., SDRAM 0xc0000000..+8 MB).

watch: record the pedal's USB audio (8 channels) and decode channel 7's watch frames:
sync 0x7e5b, sequence (8 bits) | list length << 8, index of the first entry, six u32
(lo, hi), XOR check of the 15 words before it. Prints, per watched address, its first,
last, minimum and maximum value and how many times it changed; --csv writes every sample.
The address list is the firmware's default (CF Probe watch list v1) until `watch-set`
(SysEx, next step) replaces it.
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

SYNC = 0x7E5B
FRAME = 16
PER = 6
WATCH_CH = 6          # 0-based: channel 7

# CF Probe watch list v1, as compiled into the firmware (usb_audio_tap.c ua_watch_addr).
DEFAULT_LIST = [
    (0x11F03C58, "looper_active"), (0x11F03C54, "looper_fade"), (0x11F03E38, "looper_vol_ramp"),
    (0x11F03C64, "looper_vol_target"), (0x11F03CD8, "looper_vol_param"), (0x11F03ED0, "looper_ptr_pre"),
    (0x11F03ED4, "looper_ptr_post"), (0xC011ACA8, "looper_arena_base"), (0xC011ACAC, "looper_arena_end"),
    (0xC011ACB0, "looper_capacity"), (0xC011ACB4, "looper_write_ptr"), (0xC011ACC0, "looper_undo_ptr"),
    (0xC0184FB0, "looper_transport_state"), (0xC0184FB4, "looper_transport_mirror"),
    (0xC0184FB8, "looper_transport_flags"), (0x11F03D54, "rhythm_active"), (0x11F03D1C, "rhythm_gain_master"),
    (0x11F03D08, "rhythm_mute_mult"), (0x11F03D0C, "rhythm_level_raw"), (0x11F03D14, "rhythm_level_ramp"),
    (0x11F03D58, "drum_voice0_active"), (0x11F03D5C, "drum_voice1_active"), (0x11F03D60, "drum_voice2_active"),
    (0x11812F78, "system_bpm"), (0x118133B4, "transport_run_flag(byte0)"), (0x118133BC, "rhythm_clock_word"),
    (0xC011ADA4, "rhythm_pattern_idx(byte2)"), (0xC011ADA8, "rhythm_running_flag(byte1)"),
    (0x1181191C, "rhythm_pattern_count(lo16)"), (0x11F03E34, "audio_master_gain"), (0x11812F74, "system_mvol"),
    (0x1180312C, "system_mute_mask"),
]


HEADER = bytes([0xF0, 0x52, 0x00, 0x6E, 0x64]) + b"CFPR"
PEEK_MAX = 512


def num7(v, n):
    return bytes((v >> (7 * k)) & 0x7F for k in range(n))


def unnum7(b):
    return sum((x & 0x7F) << (7 * k) for k, x in enumerate(b))


def unpack7(b):
    """Inverse of the firmware's cfp_pack: groups of (top-bit byte, up to 7 low bytes)."""
    out = bytearray()
    i = 0
    while i < len(b):
        hi = b[i]
        grp = b[i + 1:i + 8]
        for k, x in enumerate(grp):
            out.append(x | ((hi >> k) & 1) << 7)
        i += 1 + len(grp)
    return bytes(out)


def request(op, args=b""):
    return HEADER + op.encode() + bytes(args) + bytes([0xF7])


def peek_request(addr, length):
    return request("P", num7(addr, 5) + num7(length, 2))


def watch_set_request(addrs):
    return request("W", bytes([len(addrs)]) + b"".join(num7(a, 5) for a in addrs))


def parse_reply(msg):
    """Return (op, payload) for a CF Probe reply (F0..F7 included), or None."""
    msg = bytes(msg)
    if not msg.startswith(HEADER) or not msg.endswith(bytes([0xF7])) or len(msg) < len(HEADER) + 2:
        return None
    op = chr(msg[len(HEADER)])
    body = msg[len(HEADER) + 1:-1]
    if op == "p":
        addr, n = unnum7(body[:5]), unnum7(body[5:7])
        data = unpack7(body[7:])
        if len(data) != n:
            raise ValueError("peek reply length %d != %d" % (len(data), n))
        return op, (addr, data)
    if op == "w":
        return op, body[0]
    if op == "v":
        return op, body[0]
    return op, body


class Link:
    """CF Probe over the pedal's USB MIDI port (mido)."""

    def __init__(self, timeout=2.0):
        import mido
        import pedal_ports
        ins = [n for n in mido.get_input_names() if pedal_ports.is_pedal_port(n)]
        outs = [n for n in mido.get_output_names() if pedal_ports.is_pedal_port(n)]
        if not ins or not outs:
            sys.exit("no 'ZOOM G' / 'Comet Flower' MIDI port (is an editor open?)")
        self.inp, self.out, self.timeout = mido.open_input(ins[0]), mido.open_output(outs[0]), timeout
        self.mido = mido

    def call(self, msg):
        import time
        for _ in self.inp.iter_pending():
            pass
        self.out.send(self.mido.Message("sysex", data=list(msg[1:-1])))
        end = time.time() + self.timeout
        while time.time() < end:
            for m in self.inp.iter_pending():
                if m.type == "sysex":
                    r = parse_reply(bytes([0xF0] + list(m.data) + [0xF7]))
                    if r:
                        return r
            time.sleep(0.002)
        sys.exit("no CF Probe reply (is a CF Probe TEST firmware flashed?)")

    def peek(self, addr, length):
        op, r = self.call(peek_request(addr, length))
        if op != "p":
            sys.exit("peek %#x+%d refused" % (addr, length))
        return r[1]

    def dump(self, addr, length):
        out = bytearray()
        while len(out) < length:
            n = min(PEEK_MAX, length - len(out))
            out += self.peek(addr + len(out), n)
        return bytes(out)


DEFAULT_REGIONS = [(0x11F03C00, 0x300), (0xC011AC80, 0x140), (0xC0184F80, 0x80),
                   (0x11812F60, 0x40), (0x118133A0, 0x40), (0x11811900, 0x40), (0x11803120, 0x20)]


def name_of(addr):
    for a, n in DEFAULT_LIST:
        if a == addr:
            return n
    return ""


def poll(link, regions, seconds):
    """Read the regions round after round. Returns (times, {region start: [bytes per round]})."""
    import time
    t0, times, snaps = time.time(), [], {a: [] for a, _ in regions}
    while time.time() - t0 < seconds:
        times.append(time.time() - t0)
        for a, n in regions:
            snaps[a].append(link.dump(a, n))
    return times, snaps


def changes(times, snaps):
    """[(address, [(time, value), ...])] for every aligned word whose value changed."""
    import struct
    out = []
    for a, rounds in snaps.items():
        for off in range(0, len(rounds[0]) - 3, 4):
            seq, last = [], None
            for t, r in zip(times, rounds):
                v = struct.unpack_from("<I", r, off)[0]
                if v != last:
                    seq.append((t, v))
                    last = v
            if len(seq) > 1:
                out.append((a + off, seq))
    return out


def hexdump(addr, data):
    for i in range(0, len(data), 16):
        row = data[i:i + 16]
        print("%08x  %-48s %s" % (addr + i, " ".join("%02x" % x for x in row),
                                  "".join(chr(x) if 32 <= x < 127 else "." for x in row)))


def frames(words):
    """Decode watch frames from channel-7 words (unsigned 16-bit). Yields dicts:
    seq, n (list length), first (index of the first entry), values (six u32), at."""
    w = [int(x) & 0xFFFF for x in words]
    i = 0
    while i + FRAME <= len(w):
        if w[i] != SYNC:
            i += 1
            continue
        f = w[i:i + FRAME]
        x = 0
        for v in f[:15]:
            x ^= v
        if x != f[15]:
            i += 1
            continue
        yield {"seq": f[1] & 0xFF, "n": f[1] >> 8, "first": f[2],
               "values": [f[3 + 2 * k] | f[4 + 2 * k] << 16 for k in range(PER)], "at": i}
        i += FRAME


def samples(fr):
    """Flatten frames to (frame number, list index, value)."""
    for j, f in enumerate(fr):
        n = f["n"]
        if not n:
            continue
        for k, v in enumerate(f["values"]):
            yield j, (f["first"] + k) % n, v


def summary(fr, names=DEFAULT_LIST):
    rows = {}
    for j, idx, v in samples(fr):
        r = rows.setdefault(idx, {"first": v, "last": v, "min": v, "max": v, "changes": 0, "n": 0})
        if v != r["last"]:
            r["changes"] += 1
        r["last"] = v
        r["min"] = min(r["min"], v)
        r["max"] = max(r["max"], v)
        r["n"] += 1
    out = []
    for idx in sorted(rows):
        addr, name = names[idx] if idx < len(names) else (0, "entry %d" % idx)
        out.append((idx, addr, name, rows[idx]))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping")
    pk = sub.add_parser("peek")
    pk.add_argument("address")
    pk.add_argument("length", nargs="?", default="64")
    dp = sub.add_parser("dump")
    dp.add_argument("address")
    dp.add_argument("length")
    dp.add_argument("out")
    ws = sub.add_parser("watch-set")
    ws.add_argument("addresses", nargs="+")
    po = sub.add_parser("poll")
    po.add_argument("--seconds", type=float, default=10)
    po.add_argument("--region", action="append", default=[], help="ADDR:LEN (hex or decimal)")
    po.add_argument("--only", action="store_true", help="use only the --region regions")
    po.add_argument("--out")
    w = sub.add_parser("watch")
    w.add_argument("--seconds", type=float, default=4)
    w.add_argument("--csv")
    a = ap.parse_args()
    if a.cmd == "poll":
        import json
        regions = [] if a.only else list(DEFAULT_REGIONS)
        for r in a.region:
            x, n = r.split(":")
            regions.append((int(x, 0), int(n, 0)))
        times, snaps = poll(Link(), regions, a.seconds)
        print("%d rounds in %.1f s over %d regions" % (len(times), a.seconds, len(regions)))
        for addr, seq in changes(times, snaps):
            vals = " ".join("%.2f:%08x" % (t, v) for t, v in seq[:12])
            more = " ... (%d changes)" % (len(seq) - 1) if len(seq) > 12 else ""
            print("%08x %-26s %s%s" % (addr, name_of(addr), vals, more))
        if a.out:
            Path(a.out).write_text(json.dumps({"times": times, "regions": {
                "%08x" % k: [r.hex() for r in v] for k, v in snaps.items()}}), encoding="utf-8")
            print("wrote", a.out)
        return
    if a.cmd in ("ping", "peek", "dump", "watch-set"):
        link = Link()
        if a.cmd == "ping":
            print("CF Probe reply:", link.call(request("V")))
        elif a.cmd == "peek":
            addr = int(a.address, 0)
            hexdump(addr, link.peek(addr, int(a.length, 0)))
        elif a.cmd == "dump":
            addr, n = int(a.address, 0), int(a.length, 0)
            Path(a.out).write_bytes(link.dump(addr, n))
            print("wrote %d bytes from %#x to %s" % (n, addr, a.out))
        else:
            addrs = [int(x, 0) for x in a.addresses]
            op, got = link.call(watch_set_request(addrs))
            print("watch list:", got if op == "w" else "refused", "of", len(addrs), "accepted")
        return
    import numpy as np
    import ua_capture8
    data = ua_capture8.record(a.seconds, 8)
    fr = list(frames(data[:, WATCH_CH].astype(np.uint16)))
    print("%d watch frames" % len(fr))
    for idx, addr, name, r in summary(fr):
        print("%2d %08x %-28s first %08x last %08x min %08x max %08x changes %d"
              % (idx, addr, name, r["first"], r["last"], r["min"], r["max"], r["changes"]))
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as fh:
            cw = csv.writer(fh)
            cw.writerow(["frame", "index", "address", "name", "value"])
            for j, idx, v in samples(fr):
                addr, name = DEFAULT_LIST[idx] if idx < len(DEFAULT_LIST) else (0, "")
                cw.writerow([j, idx, "%08x" % addr, name, "%08x" % v])
        print("wrote", a.csv)


if __name__ == "__main__":
    main()
