"""Decode the rhythm/pattern resource table out of the firmware image and
write build/drums/patterns.json.

## Event blob format (decoded 2026-10-22, job S14)

Each record's event blob (see below) is a sequence of 2-byte events
followed by a 1-byte loop delta and the 0xf0 terminator:

    (delta: u8, value: u8){N}  loop_delta: u8  0xf0

- `delta`: ticks since the previous event (0 = simultaneous with it).
  Running sum gives each event's absolute tick position.
- `value`: high nibble = **voice ID 1..9** (9 = the click/metronome
  voice = record voice-slot 0; 1..8 = record voice-slots 1..8, in the
  same order the record stores them); low nibble = **level 0..15**
  (velocity-like; 15 is loudest, seen as the downbeat accent in every
  metronome-style pattern).
- Tick resolution: **12 ticks = 1 beat** (so 3 ticks = a 16th note, 4 =
  an 8th-note triplet, 6 = an 8th note -- all exact divisions of 12).
- After the last event, one more byte is the **loop delta**: ticks from
  the last event back to the start of the next loop iteration.
  `loop_length_ticks = last_absolute_tick + loop_delta` and this is
  *always* an exact multiple of `beats_per_bar * 12` (checked for all
  69 patterns) -- i.e. every pattern loops on a whole number of bars
  (1 bar for `GUIDE`, 2 bars for almost everything else checked).
- Terminator: a single `0xf0` byte.

Confirmed in disassembly (not just inferred from the bytes): the
firmware's per-16th playback routine (`11806eb4`+, continuing through
`11807000`..`1180720c`, called once from `1180b020`'s caller chain --
see docs/DRUM_MACHINE_2026-10-22.md "Event blob" section for the full
trace) does exactly this:
  - `11807060`/`11807080`/`118070a0`: `CALLP 0x1180b020,B3` with
    `A4` = 9, 8, 7 respectively -- a "trigger voice A4" call, gated by
    `LDBU`+`[!A0] BNOP` tests on adjacent bytes of a small per-step
    buffer. `0x1180b020` immediately does `STB A4,*+B15[4]` then calls
    `0x1180b6f0` -- i.e. it stores the voice ID byte and hands it to a
    sub-routine, matching "voice ID 1..9" as a function parameter.
  - `1180717a`: `MVK.S2 240,B1` (240 = 0xf0) then `1180718a`:
    `CMPEQ.L2 B0,B1,B0` against a byte just read via `LDBU` through a
    pointer derived from `A10` -- the literal 0xf0-terminator compare
    the task brief asked us to find.

**Caveat (not fully resolved)**: for roughly 1/3 of the 69 patterns,
one or more event voice IDs in the 4..7 range reference a record voice
slot that is *empty* for that specific pattern (e.g. `HardRock` has
events tagged voice ID 5, but its slot 5 is blank -- `HHO.raw` lives in
slot 6 instead). For the "core" voices (1=kick, 2=snare-amb, 3=snare,
8=kick-amb, 9=click) this never happens: ID always equals a populated
slot. It's only the auxiliary hat/cymbal/tom region (slots 4-7) where
some patterns' IDs don't land on a populated slot. We did not find, in
the time available, whether this means those events are genuinely
silent (most likely -- the firmware's voice-trigger call would resolve
an empty slot's 0-length PCM descriptor to a no-op) or whether there's
an additional per-pattern remapping we haven't found. `decode_patterns.py`
marks each such event `"mapped": false` and `drum_machine.py` skips
unmapped events (plays nothing for them), which matches the "likely
silent" reading. See docs/DRUM_MACHINE_2026-10-22.md for the full
per-pattern breakdown and the `Metro3` special case (its blob never
references the click voice at all and is flagged `"suspect"` --
almost certainly the same "pointer resolves into non-event data" issue
seen for a couple of other records).

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

TICKS_PER_BEAT = 12  # see module docstring "Event blob format"


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


def voice_id_to_slot(voice_id: int) -> int | None:
    """Map an event's voice ID (1..9, the high nibble of its value byte)
    to the record's 0-indexed voice-slot array position. 9 is the fixed
    click voice (slot 0); 1..8 are record slots 1..8 directly. Anything
    else is not a valid voice ID (not seen in any of the 69 patterns)."""
    if voice_id == 9:
        return 0
    if 1 <= voice_id <= 8:
        return voice_id
    return None


def decode_event_blob(blob: bytes, voices: list[str], beats_per_bar: int) -> dict:
    """Decode one pattern's 0xf0-terminated event blob into a step grid.
    See the module docstring "Event blob format" section for the byte
    layout. Returns a dict with the step list plus loop/confidence info.
    `blob` includes the trailing 0xf0 terminator."""
    body = blob[:-1]  # drop the 0xf0 terminator
    n_pairs = len(body) // 2
    has_trailing = len(body) % 2 == 1
    steps = []
    t = 0
    for i in range(0, n_pairs * 2, 2):
        delta, val = body[i], body[i + 1]
        t += delta
        voice_id = val >> 4
        level = val & 0x0F
        slot = voice_id_to_slot(voice_id)
        sample = voices[slot] if slot is not None and voices[slot] else None
        steps.append(
            {
                "tick": t,
                "delta": delta,
                "voice_id": voice_id,
                "level": level,
                "slot": slot,
                "sample": sample or None,
                "mapped": bool(sample),
            }
        )
    loop_delta = body[n_pairs * 2] if has_trailing else 0
    loop_length_ticks = t + loop_delta
    bar_ticks = beats_per_bar * TICKS_PER_BEAT
    loop_bars = (loop_length_ticks / bar_ticks) if bar_ticks else None

    n_mapped = sum(1 for s in steps if s["mapped"])
    n_click = sum(1 for s in steps if s["voice_id"] == 9)
    if n_mapped == 0 and steps:
        confidence = "suspect"  # e.g. Metro3: no event maps to any real sample
    elif n_mapped < len(steps):
        confidence = "partial_unmapped_voice"  # core voices ok, some aux id has no slot
    else:
        confidence = "ok"

    return {
        "ticks_per_beat": TICKS_PER_BEAT,
        "steps": steps,
        "has_trailing_loop_byte": has_trailing,
        "loop_delta_ticks": loop_delta,
        "loop_length_ticks": loop_length_ticks,
        "bar_ticks": bar_ticks,
        "loop_bars": loop_bars,
        "loop_bars_is_whole": bool(bar_ticks) and loop_length_ticks % bar_ticks == 0,
        "n_events": len(steps),
        "n_events_mapped": n_mapped,
        "n_click_events": n_click,
        "decode_confidence": confidence,
    }


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
        decoded = decode_event_blob(blob, voices, bpb) if blob else None
        entry = {
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
            "event_blob_decoded": decoded is not None,
        }
        if decoded is not None:
            entry.update(decoded)
        patterns.append(entry)
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

    # event-blob decode confidence summary (see module docstring)
    by_conf: dict[str, list[str]] = {}
    for p in patterns:
        conf = p.get("decode_confidence", "no_blob")
        by_conf.setdefault(conf, []).append(p["name"])
    print("  event blob decode confidence:")
    for conf in ("ok", "partial_unmapped_voice", "suspect", "no_blob"):
        names = by_conf.get(conf, [])
        if names:
            print(f"    {conf}: {len(names)} pattern(s)" + (f" (e.g. {names[0]})" if conf != "ok" else ""))


if __name__ == "__main__":
    main()
