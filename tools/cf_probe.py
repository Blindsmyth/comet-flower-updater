"""CF Probe link host tool (TEST firmware only; docs/FW_RND_BRIEF5_2026-10-22.md).

    python tools/cf_probe.py watch [--seconds 4] [--csv out.csv]

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
    w = sub.add_parser("watch")
    w.add_argument("--seconds", type=float, default=4)
    w.add_argument("--csv")
    a = ap.parse_args()
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
