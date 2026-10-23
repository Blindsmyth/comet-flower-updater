"""Decode the rhythm/pattern resource table out of the firmware image and
write build/drums/patterns.json.

Where the table is (confirmed by direct inspection of
build/fw/res1_493412.bin with tools/fwmap/ais.py sections()):

  - AIS section 0xc016f780, size 0x123a4, file offset 0x63708 (this is the
    "constant data: rhythm table, strings, fonts, bitmaps, tables" region
    named in docs/FIRMWARE_MAP.md).
  - The first record's voice-0 filename field ("Click.raw") starts at
    0xc016f7e9. A fixed-stride record of 124 (0x7c) bytes starting there
    decodes cleanly for 69 records (index 0..68); record 69 runs into
    unrelated string data ("...Params struct...") which marks the end of
    the table.
  - Record 0 is named "GUIDE" and record 7 is named "Rock1" -- this matches
    the pedal's live-read pattern-number value for Rock 1 (7, from
    docs/LOOPER_DRUMS_TEARDOWN_2026-10-22.md), so index 0 = GUIDE is the
    correct base for at least the first block of the table. See the
    "Pattern numbering" section of docs/DRUM_MACHINE_2026-10-22.md for the
    one case (Blues 2) where this static index does NOT match the pedal's
    live reading, and what we think is going on.

Record layout (124 bytes), all offsets relative to the record's voice-0
field (0xc016f7e9 + 124*k):

   0x00  12 bytes  voice_slot[0] filename, null-padded (metronome "click"
                    voice; empty in a few records)
   0x0c   1 byte   beats_per_bar   (3,4,5,6,8,12 seen)
   0x0d   1 byte   beat_unit       (4 or 8 seen -> quarter- or eighth-note
                    beat; together these look exactly like the time-sig
                    fields documented in docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md
                    for a *different*, RAM-only struct at offsets 117/118;
                    "likely" the same meaning, "guess" that it is the same
                    field)
   0x0e   1 byte   unknown flag byte; uniformly 0x02 across all 69 records
                    we decoded, so not a category id in this table
   0x0f   4 bytes  uint32 LE pointer into the SAME constant-data region;
                    points at a per-pattern binary blob terminated by a
                    0xf0 byte -- almost certainly the step/hit event list,
                    but the exact byte encoding is NOT decoded (see report)
   0x13   9 bytes  pattern display name, null-padded cstring
   0x1c.. 8 * 12B  voice_slot[1..8] filenames, null-padded, empty if unused

9 voice-name slots per record matches the firmware's confirmed 9-voice
drum mixer (11817520/11817640, see docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md
"Drum Voice PCM Fetcher"). Every filename found in the table is one of the
24 *.raw samples in backup/2026-10-04/files/, with no leftovers either way.

This script is read-only: it only parses build/fw/res1_493412.bin and
writes build/drums/patterns.json (and does not touch anything else).
"""
from __future__ import annotations

import json
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "fwmap"))
from ais import sections  # noqa: E402

FW_IMAGE = "build/fw/res1_493412.bin"
TABLE_BASE_ADDR = 0xC016F7E9
RECORD_STRIDE = 124
MAX_RECORDS = 69  # 0..68; record 69 runs into unrelated data (verified)

VOICE_NAME_OFF = 0x00
VOICE_NAME_LEN = 12
BPB_OFF = 0x0C
BU_OFF = 0x0D
FLAG_OFF = 0x0E
EVENT_PTR_OFF = 0x0F
NAME_OFF = 0x13
NAME_LEN = 9
VOICE1_OFF = 0x1C
N_VOICE_SLOTS = 9  # slot 0 (click) + 8 more


def _addr2off_factory(sects):
    def addr2off(addr):
        for a, n, o in sects:
            if isinstance(a, str):
                continue
            if a <= addr < a + n:
                return o + (addr - a)
        return None

    return addr2off


def _cstr(b: bytes) -> str:
    i = b.find(b"\x00")
    return (b[:i] if i >= 0 else b).decode("ascii", "replace")


def read_event_blob(data: bytes, addr2off, addr: int, max_len: int = 4000) -> bytes | None:
    """Read the per-pattern binary blob pointed to by the record's event
    pointer field, up to and including its 0xf0 terminator byte. Returns
    None if the pointer doesn't resolve into the known static sections
    (seen for a few records, e.g. GUIDE's pointer lands in unrelated
    bitmap/string data rather than an event-style blob)."""
    off = addr2off(addr)
    if off is None:
        return None
    chunk = data[off : off + max_len]
    idx = chunk.find(b"\xf0")
    if idx == -1:
        return None
    return chunk[: idx + 1]


def decode_table(fw_path: str = FW_IMAGE) -> list[dict]:
    with open(fw_path, "rb") as f:
        data = f.read()
    _, sects = sections(fw_path)
    addr2off = _addr2off_factory(sects)
    base_off = addr2off(TABLE_BASE_ADDR)
    if base_off is None:
        raise RuntimeError(f"table base {TABLE_BASE_ADDR:#x} not found in {fw_path} sections")

    patterns = []
    for k in range(MAX_RECORDS):
        rec = data[base_off + k * RECORD_STRIDE : base_off + (k + 1) * RECORD_STRIDE]
        if len(rec) < RECORD_STRIDE:
            break
        name = _cstr(rec[NAME_OFF : NAME_OFF + NAME_LEN])
        if not name or not all(32 <= ord(c) < 127 for c in name):
            break  # ran off the end of the table
        bpb = rec[BPB_OFF]
        bu = rec[BU_OFF]
        flag = rec[FLAG_OFF]
        event_ptr = struct.unpack_from("<I", rec, EVENT_PTR_OFF)[0]

        voices = []
        voices.append(_cstr(rec[VOICE_NAME_OFF : VOICE_NAME_OFF + VOICE_NAME_LEN]))
        for i in range(N_VOICE_SLOTS - 1):
            off = VOICE1_OFF + 12 * i
            voices.append(_cstr(rec[off : off + 12]))
        voices = [v.strip() for v in voices]

        blob = read_event_blob(data, addr2off, event_ptr)
        patterns.append(
            {
                "index": k,
                "name": name,
                "beats_per_bar": bpb,
                "beat_unit": bu,
                "flag_byte": flag,
                "event_ptr": f"0x{event_ptr:08x}",
                "voices": voices,  # 9 slots, "" = unused
                "active_voice_count": sum(1 for v in voices if v),
                "event_blob_hex": blob.hex() if blob else None,
                "event_blob_len": len(blob) if blob else None,
                "event_blob_decoded": False,
            }
        )
    return patterns


def main() -> None:
    patterns = decode_table()
    os.makedirs("build/drums", exist_ok=True)
    out_path = "build/drums/patterns.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "source": FW_IMAGE,
                "table_base_addr": f"0x{TABLE_BASE_ADDR:08x}",
                "record_stride": RECORD_STRIDE,
                "count": len(patterns),
                "patterns": patterns,
            },
            f,
            indent=2,
        )
    print(f"wrote {len(patterns)} patterns to {out_path}")
    # quick sanity print of the two pedal-confirmed names
    by_index = {p["index"]: p["name"] for p in patterns}
    print(f"  index 7  -> {by_index.get(7)!r} (pedal live reading: Rock1 = 7)")
    print(f"  index 44 -> {by_index.get(44)!r} (pedal live reading: Blues2 = 44 -- see report)")
    for p in patterns:
        if p["name"].replace(" ", "") == "Blues2":
            print(f"  'Blues2' actually found at static index {p['index']}")


if __name__ == "__main__":
    main()
