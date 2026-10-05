#!/usr/bin/env python3
"""Write patches to a G1 Four, verified by readback.

  python tools/patch_g1.py make-blank <out.ZPTC>
  python tools/patch_g1.py write <location 1..50> <file.ZPTC> [<to-location>]

make-blank derives an all-empty patch from factory patch 30 (5 slots, three
of them already empty): its two effects become the empty-slot entry patch 30
itself uses (id 0, enabled bit set); every other byte is the pedal's own.

write uploads with zoom-zt2's patch_upload (0x45), reads the patch back with
patch_download (0x46) and requires a byte-identical result. With a second
location it writes the same file to every patch in the range. Every reply
is timeout-bounded and logged (build/pedal-logs/wire.log).
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backup_g1 import GuardedPort, PedalTimeout, zoomzt2  # noqa: E402

PROJ = Path(__file__).resolve().parent.parent
EMPTY_SLOT = bytes([0x01]) + bytes(23)


def make_blank():
    raw = bytearray((PROJ / "backup/2026-10-04/patches/PATCH_030.ZPTC").read_bytes())
    n = struct.unpack("<I", raw[12:16])[0]
    ids_off = raw.find(b"TXJ1") - 4 * n
    edtb = raw.find(b"EDTB")
    for i in range(n):
        raw[ids_off + 4 * i:ids_off + 4 * i + 4] = bytes(4)
        raw[edtb + 8 + 24 * i:edtb + 8 + 24 * i + 24] = EMPTY_SLOT
    return bytes(raw)


def write(first, data, last):
    logdir = PROJ / "build" / "pedal-logs"
    logdir.mkdir(parents=True, exist_ok=True)
    log = open(logdir / "wire.log", "a")
    pedal = zoomzt2.zoomzt2()
    if not pedal.connect():
        sys.exit("FAIL: no 'ZOOM G' MIDI port found.")
    pedal.inport = GuardedPort(pedal.inport, log)
    pedal.outport = GuardedPort(pedal.outport, log)
    try:
        pedal.pcmode_on()
        count, _, _ = pedal.patch_check()
        if not (1 <= first <= last <= count):
            sys.exit(f"locations must be within 1..{count}")
        for loc in range(first, last + 1):
            pedal.patch_upload(loc, data)
            back = bytes(pedal.patch_download(loc))
            if back != data:
                print(f"  patch {loc}: READBACK DIFFERS ({len(back)} B) - stopping")
                pedal.disconnect()
                return 3
            print(f"  patch {loc}: written, read back identical", flush=True)
        pedal.disconnect()
        return 0
    except PedalTimeout as e:
        print(f"STOPPED: pedal stopped replying ({e}). Keep it powered.")
        return 4


def main(a):
    if len(a) == 2 and a[0] == "make-blank":
        data = make_blank()
        Path(a[1]).write_bytes(data)
        print(f"blank patch: {len(data)} bytes -> {a[1]}")
        return 0
    if len(a) in (3, 4) and a[0] == "write":
        first = int(a[1])
        last = int(a[3]) if len(a) == 4 else first
        return write(first, Path(a[2]).read_bytes(), last)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
