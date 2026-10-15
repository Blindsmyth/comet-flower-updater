#!/usr/bin/env python3
"""Decode the USB teardown diagnostic ring (ctl_diag) from a memory dump.

Usage:
  python tools/decode_ctl_diag.py <dump.bin> [--offset 0x1234] [--json]

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
    ap.add_argument("dump", type=Path, help="Path to binary memory dump")
    ap.add_argument("--offset", type=lambda s: int(s, 0), default=None, help="Explicit byte offset to ctl_diag")
    ap.add_argument("--json", action="store_true", help="Output JSON instead of formatted text")
    args = ap.parse_args()

    if not args.dump.exists():
        sys.exit(f"File not found: {args.dump}")

    data = args.dump.read_bytes()
    try:
        report = decode_diag(data, args.offset)
    except Exception as e:
        sys.exit(f"Error decoding ctl_diag: {e}")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_diag_text(report))


if __name__ == "__main__":
    main()
