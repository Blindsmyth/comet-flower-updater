#!/usr/bin/env python3
"""G1 Four write test for a DIY effect: stage 1 of the first hardware test.

  python tools/pedal_g1.py writetest build/G1GAIN.ZD2 [--dry-run]
  python tools/pedal_g1.py uninstall-stock ORG1201U.ZD2
  python tools/pedal_g1.py install build/G1GAIN.ZD2

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


BACKUP = PROJ / "backup" / "2026-10-04" / "files"


def set_installed(flst, name, installed):
    """Flip one entry's installed byte. Refuses unless the grammar round-trips
    the list byte-exactly and the result differs from it in exactly one byte."""
    import zoomzt2
    if zoomzt2.ZT2.build(zoomzt2.ZT2.parse(flst)) != flst:
        refuse("effect list does not round-trip through the zoom-zt2 grammar")
    cfg = zoomzt2.ZT2.parse(flst)
    hits = [e for g in cfg[1] for e in g["effects"]
            if str(e["effect"]).upper() == name]
    if len(hits) != 1:
        refuse(f"{name} appears {len(hits)} times in the effect list")
    hits[0]["installed"] = int(installed)
    new = zoomzt2.ZT2.build(cfg)
    diff = sum(a != b for a, b in zip(flst, new))
    if len(new) != len(flst) or diff != 1:
        refuse(f"computed list differs in {diff} bytes, expected exactly 1")
    return new


def add_entry(flst, path):
    """zoom-zt2's add, checked: same length, old entries unchanged and in
    order, exactly one new installed entry for this file."""
    import zoomzt2
    if zoomzt2.ZT2.build(zoomzt2.ZT2.parse(flst)) != flst:
        refuse("effect list does not round-trip through the zoom-zt2 grammar")
    new = zoomzt2.zoomzt2().add_effect_from_filename(flst, str(path))
    old_e, new_e = flst_entries(flst), flst_entries(new)
    base = os.path.basename(path).upper()
    added = [e for e in new_e if e not in old_e]
    if len(new) != len(flst) or [e for e in new_e if e[0] != base] != old_e \
            or len(added) != 1 or added[0][0] != base:
        refuse("computed effect list is not a clean single-entry add")
    return new


def open_session():
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
    sess.pcmode_on()
    return pedal, sess


def uninstall_stock(name):
    """Free flash by uninstalling a STOCK effect the way Zoom stores
    uninstalled effects: file deleted, entry kept with installed=0.

    Order is file first, then list, because the list rewrite needs free
    space and the pedal has too little until the file is gone. Between the
    two steps the list names a missing file; on any failure there, the file
    is uploaded again from the backup."""
    import file_session as fs
    name = name.upper()
    original = (BACKUP / name).read_bytes()
    flst_backup = (BACKUP / fs.FLST_NAME).read_bytes()
    flst_new = set_installed(flst_backup, name, 0)
    print(f"pedal_g1: uninstall-stock {name} ({len(original)} bytes); "
          f"new effect list computed and checked (1 byte changes)")

    pedal, sess = open_session()
    try:
        flst_now = sess.download(fs.FLST_NAME)
        sess.close()
        if flst_now != flst_backup:
            refuse("the pedal's effect list no longer matches the backup")
        present = sess.file_check(name)
        sess.close()
        if not present:
            refuse(f"{name} is not on the pedal")
        if sess.download(name) != original:
            refuse(f"{name} on the pedal differs from the backup copy")
        sess.close()

        try:
            sess.delete(name)
            sess.close()
            if sess.file_check(name):
                raise fs.TransferError(f"{name} still present after delete")
            sess.close()
            print(f"pedal_g1: {name} deleted; flash free now "
                  f"{sess.disk_usage()[1]} bytes")
            retries = fs.replace_flst(sess, flst_backup, flst_new,
                                      log=lambda line: print(line))
        except fs.TransferError as e:
            print(f"pedal_g1: FAILED before the list was rewritten ({e}); "
                  f"restoring {name} from the backup")
            sess.abort()
            fs.verified_upload(sess, name, original)
            back = sess.download(fs.FLST_NAME)
            sess.close()
            if back != flst_backup:
                raise fs.PedalUnresolved("effect list changed during restore")
            print(f"pedal_g1: restored {name}; pedal verified unchanged")
            return EXIT_SAFE_ABORT
        sess.pcmode_off()
        print(f"pedal_g1: uninstall-stock PASSED: {name} removed, effect list "
              f"rewritten and read back identical (retries: {retries})")
        return EXIT_OK
    except fs.PedalUnresolved as e:
        print(f"pedal_g1: UNRESOLVED - keep the pedal POWERED. {e}")
        return EXIT_UNRESOLVED
    finally:
        if pedal.is_connected():
            pedal.disconnect()


def install(path):
    """Install a DIY effect: upload + verify the file, then rewrite the list
    (stomphacks install_effect: files-then-list, guarded, verified)."""
    import file_session as fs
    data = Path(path).read_bytes()
    base = os.path.basename(path).upper()
    p = check_container(data)
    print(f"pedal_g1: install {base} (id 0x{p.header.effect_id:08x}, "
          f"'{p.header.name}', {len(data)} bytes)")

    pedal, sess = open_session()
    try:
        flst_old = sess.download(fs.FLST_NAME)
        sess.close()
        if any(n == base or i == p.header.effect_id
               for n, i in flst_entries(flst_old)):
            refuse(f"{base} or its id is already in the effect list")
        flst_new = add_entry(flst_old, path)
        _, available = sess.disk_usage()
        need = len(data) + len(flst_new) + fs.DISK_MARGIN
        if available < need:
            refuse(f"{available} bytes free, need {need}")
        try:
            result = fs.install_effect(sess, [(base, data)], flst_old, flst_new,
                                       log=lambda line: print(line))
        except fs.TransferAborted as e:
            print(f"pedal_g1: install did NOT complete, pedal verified SAFE: {e}")
            return EXIT_SAFE_ABORT
        sess.pcmode_off()
        (PROJ / "build" / "pedal-logs" / "FLST_after_install.ZT2").write_bytes(flst_new)
        print(f"pedal_g1: install PASSED: {base} uploaded and verified, effect "
              f"list rewritten and read back identical "
              f"(retries: {result['flst_retries']})")
        return EXIT_OK
    except fs.PedalUnresolved as e:
        print(f"pedal_g1: UNRESOLVED - keep the pedal POWERED. {e}")
        return EXIT_UNRESOLVED
    finally:
        if pedal.is_connected():
            pedal.disconnect()


def wipe_stock(keep):
    """Uninstall every installed effect except `keep` (DIY effects).

    List first, then files: one effect-list rewrite sets installed=0 on
    every other entry (as Zoom stores uninstalled effects), then each file
    is deleted and verified absent. An interruption after the list rewrite
    only leaves orphan files, which nothing references. Patches that use a
    wiped effect skip it (verified on patch 40, 2026-10-04)."""
    import file_session as fs
    import zoomzt2
    keep = {k.upper() for k in keep}
    expected = (PROJ / "build" / "pedal-logs" / "FLST_after_install.ZT2").read_bytes()

    pedal, sess = open_session()
    try:
        flst_old = sess.download(fs.FLST_NAME)
        sess.close()
        if flst_old != expected:
            refuse("the pedal's effect list is not the one our last install wrote")
        if zoomzt2.ZT2.build(zoomzt2.ZT2.parse(flst_old)) != flst_old:
            refuse("effect list does not round-trip through the zoom-zt2 grammar")
        cfg = zoomzt2.ZT2.parse(flst_old)
        victims = []
        for g in cfg[1]:
            for e in g["effects"]:
                name = str(e["effect"]).upper()
                if int(e["installed"]) and name not in keep:
                    victims.append(name)
                    e["installed"] = 0
        flst_new = zoomzt2.ZT2.build(cfg)
        changed = sum(a != b for a, b in zip(flst_old, flst_new))
        if len(flst_new) != len(flst_old) or changed != len(victims) \
                or not all(v.endswith(".ZD2") for v in victims):
            refuse(f"computed list changes {changed} bytes for {len(victims)} effects")
        print(f"pedal_g1: wipe {len(victims)} effects, keeping {sorted(keep)}; "
              f"effect list: {changed} installed bytes set to 0")

        retries = fs.replace_flst(sess, flst_old, flst_new,
                                  log=lambda line: print(line))
        print(f"pedal_g1: effect list rewritten and verified (retries {retries})")

        for i, name in enumerate(victims, 1):
            present = sess.file_check(name)
            sess.close()
            if present:
                sess.delete(name)
                sess.close()
                if sess.file_check(name):
                    raise fs.TransferError(f"{name} still present after delete")
                sess.close()
            print(f"  [{i}/{len(victims)}] {name} "
                  f"{'deleted' if present else 'already absent'}", flush=True)

        back = sess.download(fs.FLST_NAME)
        sess.close()
        if back != flst_new:
            raise fs.PedalUnresolved("effect list changed during file deletes")
        maximum, available = sess.disk_usage()
        sess.pcmode_off()
        (PROJ / "build" / "pedal-logs" / "FLST_after_wipe.ZT2").write_bytes(flst_new)
        print(f"pedal_g1: wipe PASSED: {len(victims)} effects removed; "
              f"flash free {available} of {maximum} bytes")
        return EXIT_OK
    except fs.TransferError as e:
        print(f"pedal_g1: wipe stopped ({e}). The effect list was already "
              f"rewritten if the message above says so; any files left are "
              f"orphans. Re-run to continue.")
        sess.abort()
        return EXIT_SAFE_ABORT
    except fs.PedalUnresolved as e:
        print(f"pedal_g1: UNRESOLVED - keep the pedal POWERED. {e}")
        return EXIT_UNRESOLVED
    finally:
        if pedal.is_connected():
            pedal.disconnect()


def replace(path):
    """Overwrite an installed DIY effect with a new build of it. The id and
    version must match the effect-list entry, so the list is not written;
    it is read before and after and must be unchanged. Run it with the
    pedal on a patch that does NOT use the effect."""
    import file_session as fs
    data = Path(path).read_bytes()
    base = os.path.basename(path).upper()
    p = check_container(data)
    pedal, sess = open_session()
    try:
        flst = sess.download(fs.FLST_NAME)
        sess.close()
        import zoomzt2
        hits = [e for g in zoomzt2.ZT2.parse(flst)[1] for e in g["effects"]
                if str(e["effect"]).upper() == base]
        if len(hits) != 1 or int(hits[0]["id"]) != p.header.effect_id \
                or str(hits[0]["version"]) != p.header.version:
            refuse(f"{base} is not listed with id 0x{p.header.effect_id:08x} "
                   f"version {p.header.version}")
        if not sess.file_check(base):
            refuse(f"{base} is not on the pedal")
        sess.close()
        try:
            fs.verified_upload(sess, base, data)
            back = sess.download(fs.FLST_NAME)
            sess.close()
            if back != flst:
                raise fs.TransferError("effect list changed during replace")
        except fs.TransferError as e:
            print(f"pedal_g1: replace FAILED ({e}); the old file may be gone. "
                  f"Re-run replace while the pedal stays powered.")
            sess.abort()
            return EXIT_UNRESOLVED
        sess.pcmode_off()
        print(f"pedal_g1: replace PASSED: {base} ({len(data)} bytes) written and "
              f"read back identical; effect list unchanged")
        return EXIT_OK
    finally:
        if pedal.is_connected():
            pedal.disconnect()


def main(argv):
    if len(argv) == 2 and argv[0] == "replace":
        return replace(argv[1])
    if len(argv) >= 2 and argv[0] == "wipe-stock" and argv[1] == "--keep":
        return wipe_stock(argv[2:])
    if len(argv) >= 2 and argv[0] == "writetest":
        return writetest(argv[1], "--dry-run" in argv[2:])
    if len(argv) == 2 and argv[0] == "uninstall-stock":
        return uninstall_stock(argv[1])
    if len(argv) == 2 and argv[0] == "install":
        return install(argv[1])
    print(__doc__)
    return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
