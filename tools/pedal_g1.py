#!/usr/bin/env python3
"""G1 Four write test for a DIY effect: stage 1 of the first hardware test.

  python tools/pedal_g1.py writetest build/G1GAIN.ZD2 [--dry-run]

Uploads the file, reads it back and byte-compares, deletes it and verifies
it is gone. FLST_SEQ.ZT2 (the effect list the pedal boots from) is never
written: it is read before and after and must be byte-identical. The
transfer engine is stomphacks' tools-pedal/file_session.py, unchanged:
every reply has a timeout, any failure closes the session and verifies the
pedal, and an unverifiable state prints a DO-NOT-POWER-CYCLE banner.

Replaces stomphacks' MS Plus-only gates with G1 ones taken from the
87-effect audit (recon/03):
  * container: magic, header length 120, valid CRC, target bit 0x02, blocks
    tiling to the trailer, a 1-bpp BMP icon
  * the effect ID and filename are absent from the pedal's effect list
  * the filename is not already on the pedal (checked by the engine)
  * enough free flash for the file plus a margin

--dry-run runs the offline checks only and opens no MIDI port.
Exit codes: 0 passed, 2 refused (nothing sent), 3 aborted but pedal verified
safe, 4 UNRESOLVED (keep the pedal powered; see the banner).
"""
import os
import struct
import sys
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
LAB = Path(os.environ.get("ZOOMLAB", r"C:\Users\z\zoomlab\stomphacks"))
sys.path.insert(0, str(PROJ / "src"))
sys.path.insert(0, str(LAB / "zoom-zt2"))
sys.path.insert(0, str(LAB / "tools-pedal"))

from zd2tools.parser import parse_zd2  # noqa: E402

EXIT_OK, EXIT_REFUSED, EXIT_SAFE_ABORT, EXIT_UNRESOLVED = 0, 2, 3, 4
FREE_MARGIN = 2048


def refuse(msg):
    print(f"pedal_g1: REFUSED: {msg}")
    sys.exit(EXIT_REFUSED)


def check_container(data):
    p = parse_zd2(data)
    h = p.header
    problems = []
    if h.header_length != 120:
        problems.append(f"header length {h.header_length} != 120")
    if not p.crc_ok:
        problems.append("CRC invalid")
    if not h.target & 0x02:
        problems.append(f"target 0x{h.target:x} lacks the G1 bit 0x02")
    if 0x80 + sum(8 + b.length for b in p.blocks) != len(data) - 16:
        problems.append("blocks do not tile the file up to the trailer")
    icon = p.get_block("ICON")
    if icon is None or icon.data[:2] != b"BM":
        problems.append("ICON is not a BMP")
    for tag in ("INFO", "DATA", "PRMJ", "PRME"):
        if p.get_block(tag) is None:
            problems.append(f"missing {tag} block")
    if h.group_id != h.effect_id >> 24:
        problems.append("group byte does not match the ID's top byte")
    if problems:
        refuse("container check failed: " + "; ".join(problems))
    return p


def flst_entries(flst):
    import zoomzt2
    cfg = zoomzt2.ZT2.parse(flst)
    return [(str(e["effect"]).upper(), int(e["id"]))
            for g in cfg[1] for e in g["effects"]]


class LoggedTransport:
    """MidoTransport plus a wire log, so a session can be reconstructed."""

    def __init__(self, inner, logfile):
        self.inner = inner
        self.f = open(logfile, "a")
        self.f.write(f"# session {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    def send(self, payload):
        self.f.write(f"TX {bytes(payload).hex()}\n")
        self.f.flush()
        self.inner.send(payload)

    def recv(self, timeout):
        r = self.inner.recv(timeout)
        self.f.write(f"RX {r.hex() if r is not None else '<timeout>'}\n")
        self.f.flush()
        return r


def writetest(path, dry_run):
    data = Path(path).read_bytes()
    base = os.path.basename(path).upper()
    if len(base) > 12 or not base.endswith(".ZD2"):
        refuse(f"filename {base} must be 8.3 with .ZD2")
    p = check_container(data)
    eid = p.header.effect_id

    backup_flst = PROJ / "backup" / "2026-10-04" / "files" / "FLST_SEQ.ZT2"
    if backup_flst.exists():
        listed = flst_entries(backup_flst.read_bytes())
        if any(n == base or i == eid for n, i in listed):
            refuse(f"{base} / 0x{eid:08x} is in the backed-up effect list")
    print(f"pedal_g1: offline checks passed for {base} "
          f"(id 0x{eid:08x}, '{p.header.name}', {len(data)} bytes)")
    if dry_run:
        print("pedal_g1: --dry-run, no MIDI port opened")
        return EXIT_OK

    import file_session as fs
    import zoomzt2

    pedal = zoomzt2.zoomzt2()
    if not pedal.connect():
        refuse("no 'ZOOM G' MIDI port (is ToneLib or another editor open?)")
    logdir = PROJ / "build" / "pedal-logs"
    logdir.mkdir(parents=True, exist_ok=True)
    transport = LoggedTransport(fs.MidoTransport(pedal.inport, pedal.outport),
                                logdir / "wire.log")
    sess = fs.FileSession(transport, log=lambda line: print("  engine:", line))
    try:
        sess.pcmode_on()
        maximum, available = sess.disk_usage()
        print(f"pedal_g1: flash {available} bytes free of {maximum}")
        if available < len(data) + FREE_MARGIN:
            sess.pcmode_off()
            refuse(f"not enough free flash for {len(data)} bytes + margin")

        flst_old = sess.download(fs.FLST_NAME)
        sess.close()
        listed = flst_entries(flst_old)
        if any(n == base or i == eid for n, i in listed):
            sess.pcmode_off()
            refuse(f"{base} / 0x{eid:08x} is in the pedal's effect list")

        print(f"pedal_g1: writetest {base}: upload, readback-compare, "
              f"delete; the effect list is never written")
        try:
            fs.writetest_effect(sess, base, data, flst_old,
                                log=lambda line: print(line))
        except fs.TransferAborted as e:
            print(f"pedal_g1: write test did NOT complete, but the pedal was "
                  f"verified SAFE (nothing changed). Reason: {e}")
            return EXIT_SAFE_ABORT
        except fs.PedalUnresolved as e:
            print(f"pedal_g1: UNRESOLVED - keep the pedal POWERED. {e}")
            return EXIT_UNRESOLVED
        sess.pcmode_off()
        print(f"pedal_g1: write test PASSED - {len(data)} bytes uploaded, "
              f"read back byte-identical, deleted, verified absent; effect "
              f"list byte-identical throughout.")
        return EXIT_OK
    finally:
        if pedal.is_connected():
            pedal.disconnect()


def main(argv):
    if len(argv) < 2 or argv[0] != "writetest":
        print(__doc__)
        return EXIT_REFUSED
    return writetest(argv[1], "--dry-run" in argv[2:])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
