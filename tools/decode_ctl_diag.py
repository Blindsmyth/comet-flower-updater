#!/usr/bin/env python3
"""Decode the USB teardown diagnostic ring (ctl_diag) from a memory dump.

Usage:
  python tools/decode_ctl_diag.py <dump.bin> [--offset 0x1234] [--json]
  python tools/decode_ctl_diag.py --cc-log capture.json [--json]

--cc-log decodes the MIDI readback stream of the diag build (combined
footswitch gesture; see firmware/controller/controller_diag.c): a JSON list of
[control, value] pairs on channel 1, as written by tools/capture_ctl_diag.py.

Searches for the 'TDG1' (0x54444731) magic if --offset is omitted, decodes
the ring header and entries, checks sticky fault flags, and prints a chronological
trace of all observed descriptor pops and recycles.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

MAGIC = 0x54444731
MAGIC_BYTES = struct.pack("<I", MAGIC)
DIAG_ENTRIES = 24
ENTRY_SIZE = 16
HEADER_SIZE = 24
TOTAL_SIZE = HEADER_SIZE + DIAG_ENTRIES * ENTRY_SIZE  # 408 bytes

FAULT_FLAGS = {
    0x1: "FAULT_TYPE19_RECYCLED (site 1: type 19 recycled by abort drain)",
    0x2: "FAULT_CHANNEL_MISMATCH (site 1: channel != slot-1)",
    0x4: "FAULT_RING_WRAPPED (ring wrapped, oldest entries overwritten)",
    0x8: "FAULT_TYPE19_CONSUMER (site 2: type 19 recycled by queue 32..35 consumer)",
}

SITE_NAMES = {
    1: "abort_drain (c0120744, queue 25)",
    2: "queue_consumer (c0121a18, queues 32..35)",
}


def find_magic(data):
    """Find the offset of MAGIC in data."""
    idx = data.find(MAGIC_BYTES)
    if idx == -1:
        raise ValueError("MAGIC 'TDG1' (0x54444731) not found in input data")
    return idx


def decode_diag(data, offset=None):
    """Decode ctl_diag structure from bytes at offset."""
    if offset is None:
        offset = find_magic(data)

    if offset + TOTAL_SIZE > len(data):
        raise ValueError(
            f"Insufficient data at offset {hex(offset)}: need {TOTAL_SIZE} bytes, got {len(data) - offset}"
        )

    magic, head, fault, teardown_seen, consumer_pops, consumer_other = struct.unpack_from(
        "<6I", data, offset
    )

    if magic != MAGIC:
        raise ValueError(f"Invalid magic {hex(magic)}, expected {hex(MAGIC)}")

    fault_list = [desc for bit, desc in FAULT_FLAGS.items() if (fault & bit)]

    # Read all 24 raw slots in ring
    raw_entries = []
    entry_offset = offset + HEADER_SIZE
    for i in range(DIAG_ENTRIES):
        tag, idx, word0, tscl = struct.unpack_from("<4I", data, entry_offset + i * ENTRY_SIZE)
        seq = tag & 0xFFFF
        aux = (tag >> 16) & 0xFF
        site = (tag >> 24) & 0xFF
        raw_entries.append({
            "slot_index": i,
            "tag": tag,
            "site_id": site,
            "site": SITE_NAMES.get(site, f"unknown ({site})"),
            "aux": aux,
            "aux_label": "slot" if site == 1 else ("queue" if site == 2 else "aux"),
            "seq": seq,
            "idx": idx,
            "word0": word0,
            "type": (word0 >> 27) & 0x1F,
            "channel": word0 & 0x3F,
            "tscl": tscl,
        })

    # Order chronologically based on head
    active_count = min(head, DIAG_ENTRIES)
    start_seq = max(0, head - DIAG_ENTRIES)
    chronological = []
    for s in range(start_seq, head):
        slot = s % DIAG_ENTRIES
        entry = dict(raw_entries[slot])
        chronological.append(entry)

    return {
        "offset": offset,
        "magic": hex(magic),
        "head": head,
        "fault_raw": hex(fault),
        "faults": fault_list,
        "teardown_seen": teardown_seen,
        "consumer_pops": consumer_pops,
        "consumer_other": consumer_other,
        "active_entries": active_count,
        "entries": chronological,
    }


DUMP_MAGIC = 0x31504D44  # 'DMP1'
DUMP_DIAG_WORDS = TOTAL_SIZE // 4
DUMP_TX_FIELDS = (2, 3, 5, 9)
CC_BEGIN, CC_FIRST, CC_PARTS = 119, 102, 5


def words_from_cc(pairs):
    """Reassemble 32-bit words from the last complete begin..end CC frame."""
    frames, cur = [], None
    for control, value in pairs:
        if control == CC_BEGIN and value == 127:
            cur = []
        elif control == CC_BEGIN and value == 1 and cur is not None:
            frames.append(cur)
            cur = None
        elif cur is not None and CC_FIRST <= control < CC_FIRST + CC_PARTS:
            cur.append((control - CC_FIRST, value & 0x7F))
    if not frames:
        raise ValueError("no complete readback frame (CC119=127 ... CC119=1) found")
    parts = frames[-1]
    if len(parts) % CC_PARTS:
        raise ValueError(f"frame has {len(parts)} data CCs, not a multiple of {CC_PARTS}")
    words = []
    for i in range(0, len(parts), CC_PARTS):
        group = parts[i:i + CC_PARTS]
        if [g[0] for g in group] != list(range(CC_PARTS)):
            raise ValueError(f"data CCs out of order at word {i // CC_PARTS}")
        words.append(sum(v << (7 * k) for k, v in group) & 0xFFFFFFFF)
    return words


def decode_cc_stream(pairs):
    words = words_from_cc(pairs)
    if len(words) < 2 or words[0] != DUMP_MAGIC:
        raise ValueError("readback frame does not start with DMP1 magic")
    if words[1] != len(words) - 2 or words[1] != DUMP_DIAG_WORDS + 4 * len(DUMP_TX_FIELDS) + 3:
        raise ValueError(f"readback word count {words[1]} does not match frame ({len(words) - 2})")
    body = words[2:]
    report = decode_diag(struct.pack(f"<{DUMP_DIAG_WORDS}I", *body[:DUMP_DIAG_WORDS]), 0)
    tx, k = {}, DUMP_DIAG_WORDS
    for slot in range(1, 5):
        f = dict(zip(DUMP_TX_FIELDS, body[k:k + 4]))
        k += 4
        tx[slot] = {"field2_enabled": f[2], "field3_state": f[3],
                    "field5_outstanding": f[5], "field9": f[9] - (1 << 32) if f[9] >> 31 else f[9]}
    report["tx_records"] = tx
    size, base, unused = body[k:k + 3]
    report["worker_stack"] = {
        "size": size, "base": hex(base),
        "unused_fill_bytes": None if unused == 0xFFFFFFFF else unused,
        "peak_used_bytes": None if unused == 0xFFFFFFFF else size - unused,
    }
    report["source"] = "midi_readback"
    return report


def format_diag_text(diag):
    lines = []
    lines.append("=== ctl_diag USB Teardown Diagnostic Report ===")
    lines.append(f"Offset:          {hex(diag['offset'])}")
    lines.append(f"Head:            {diag['head']} total writes")
    lines.append(f"Faults:          {diag['fault_raw']}")
    if diag["faults"]:
        for f in diag["faults"]:
            lines.append(f"  * {f}")
    else:
        lines.append("  (none)")
    lines.append(f"Teardowns seen:  {diag['teardown_seen']} (type-19)")
    lines.append(f"Consumer pops:   {diag['consumer_pops']} total")
    lines.append(f"Consumer other:  {diag['consumer_other']} (type != 16 logged)")
    lines.append(f"Ring entries:    {len(diag['entries'])} active")
    if "tx_records" in diag:
        lines.append("TX records at snapshot (outstanding [5] should be 0 when idle):")
        for slot, r in diag["tx_records"].items():
            lines.append(f"  slot {slot}: enabled[2]={r['field2_enabled']} state[3]={r['field3_state']} "
                         f"outstanding[5]={r['field5_outstanding']} [9]={r['field9']}")
    if "worker_stack" in diag:
        w = diag["worker_stack"]
        if w["peak_used_bytes"] is None:
            lines.append(f"Worker stack:    not measured (size={w['size']}, base={w['base']}; guard failed)")
        else:
            lines.append(f"Worker stack:    peak {w['peak_used_bytes']} of {w['size']} bytes used "
                         f"({w['unused_fill_bytes']} untouched 0xbe bytes above base {w['base']})")
    lines.append("")
    if diag["entries"]:
        header = f"{'Seq':>5} {'Site':<35} {'Aux':>5} {'Idx':>5} {'Word0':>10} {'Type':>5} {'Ch':>4} {'TSCL':>10}"
        lines.append(header)
        lines.append("-" * len(header))
        for e in diag["entries"]:
            lines.append(
                f"{e['seq']:5d} {e['site']:<35} {e['aux_label']}={e['aux']:<2} {e['idx']:5d} "
                f"0x{e['word0']:08x} {e['type']:5d} {e['channel']:4d} {e['tscl']:10d}"
            )
    else:
        lines.append("(No entries recorded in ring)")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dump", type=Path, nargs="?", help="Path to binary memory dump")
    ap.add_argument("--cc-log", type=Path, help="JSON [control, value] list from capture_ctl_diag.py")
    ap.add_argument("--offset", type=lambda s: int(s, 0), default=None, help="Explicit byte offset to ctl_diag")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of formatted text")
    args = ap.parse_args()

    if args.cc_log is None and args.dump is None:
        ap.error("give a dump file or --cc-log")
    src = args.cc_log or args.dump
    if not src.exists():
        sys.exit(f"File not found: {src}")

    try:
        if args.cc_log:
            report = decode_cc_stream(json.loads(src.read_text()))
        else:
            report = decode_diag(src.read_bytes(), args.offset)
    except Exception as e:
        sys.exit(f"Error decoding ctl_diag: {e}")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_diag_text(report))


if __name__ == "__main__":
    main()
