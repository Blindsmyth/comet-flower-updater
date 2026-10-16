#!/usr/bin/env python3
"""Read-only backup of a G1 Four / G1X Four: every file on the pedal
(effects .ZD2, FLST_SEQ.ZT2, system files) into <output-dir>/files/.

Uses only zoom-zt2's proven read commands: PC mode on/off, disk usage,
wildcard directory walk, file check/download/close. Nothing is written to
the pedal. Differences from stomphacks' backup_pedal.py (MS Plus):

  * The completeness gate only requires each installed .ZD2. G1 Four
    effects carry their icon inside the ZD2, so there are no .ZIC files.
  * Every reply has a timeout (zoom-zt2 blocks forever). On a timeout the
    script tries one session close and stops. KEEP THE PEDAL POWERED if
    that happens, and re-run: the backup resumes.
  * Every message sent and received is logged to <output-dir>/wire.log.

Usage:
  python tools/backup_g1.py <output-dir>

Needs zoom-zt2 from the toolchain in docs/TOOLCHAIN.md.
"""
import os
import sys
import time
from pathlib import Path

ZOOMLAB = Path(os.environ.get("ZOOMLAB", r"C:\Users\z\zoomlab\stomphacks"))
sys.path.insert(0, str(ZOOMLAB / "zoom-zt2"))

import zoomzt2  # noqa: E402

REPLY_TIMEOUT = 5.0
WALK_ATTEMPTS = 2


class PedalTimeout(Exception):
    pass


class GuardedPort:
    """Wraps a mido port: logs traffic, and bounds every receive."""

    def __init__(self, port, log):
        self._port = port
        self._log = log

    def send(self, msg):
        self._log.write(f"TX {bytes(msg.data).hex()}\n")
        self._log.flush()
        return self._port.send(msg)

    def receive(self):
        deadline = time.monotonic() + REPLY_TIMEOUT
        while time.monotonic() < deadline:
            msg = self._port.poll()
            if msg is not None:
                self._log.write(f"RX {bytes(msg.data).hex()}\n")
                self._log.flush()
                return msg
            time.sleep(0.001)
        self._log.write("RX <timeout>\n")
        self._log.flush()
        raise PedalTimeout(f"no reply within {REPLY_TIMEOUT}s")

    def __getattr__(self, name):
        return getattr(self._port, name)


def registered_effects(flst_data):
    """Filenames of the INSTALLED effects in the pedal's effect list (the
    list also names uninstalled ones, which have no file), or None if the
    list does not parse (then the walk alone is the file list)."""
    try:
        config = zoomzt2.ZT2.parse(flst_data)
        return [str(e["effect"]).upper()
                for g in config[1] for e in g["effects"] if int(e["installed"])]
    except Exception as e:
        print(f"  WARNING: FLST_SEQ.ZT2 did not parse ({e}); "
              "completeness cannot be cross-checked", flush=True)
        return None


def walk(pedal):
    pedal.file_close()
    names = []
    name = pedal.file_wild(True)
    while name:
        names.append(name)
        name = pedal.file_wild(False)
    pedal.file_close()
    return names


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    outdir = Path(sys.argv[1])
    files_dir = outdir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    log = open(outdir / "wire.log", "a")
    log.write(f"# session {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    import pedal_ports
    pedal_ports.register_zoomzt2(zoomzt2)
    pedal = zoomzt2.zoomzt2()
    if not pedal.connect():
        sys.exit("FAIL: no 'ZOOM G' / 'Comet Flower' MIDI port found.")
    pedal.inport = GuardedPort(pedal.inport, log)
    pedal.outport = GuardedPort(pedal.outport, log)

    try:
        pedal.pcmode_on()
        usage = pedal.disk_usage()
        print(f"Disk usage: {usage:.1f}%", flush=True)
        (outdir / "disk-usage.txt").write_text(f"disk_usage_percent: {usage:.1f}\n")

        for attempt in range(1, WALK_ATTEMPTS + 1):
            names = walk(pedal)
            print(f"Walk {attempt}: {len(names)} files", flush=True)
            flst = files_dir / "FLST_SEQ.ZT2"
            data = zoomzt2.download_and_save_file(pedal, "FLST_SEQ.ZT2", str(flst))
            if not data:
                sys.exit("FAIL: could not download FLST_SEQ.ZT2")
            have = {n.upper() for n in names}
            registered = registered_effects(bytes(data)) or []
            missing = [f for f in registered if f not in have]
            print(f"  effect list: {len(registered)} installed effects", flush=True)
            if not missing:
                break
            print(f"  {len(missing)} registered effects missing from walk: "
                  f"{', '.join(missing[:8])}", flush=True)
        (outdir / "walk.txt").write_text("\n".join(names) + "\n")

        for i, name in enumerate(names, 1):
            dest = files_dir / name
            if dest.exists() and dest.stat().st_size > 0:
                continue
            print(f"  [{i}/{len(names)}] {name}", flush=True)
            zoomzt2.download_and_save_file(pedal, name, str(dest))

        pedal.disconnect()
    except PedalTimeout as e:
        print(f"\nSTOPPED: pedal stopped replying ({e}).", flush=True)
        print("DO NOT power-cycle the pedal. Trying one clean session close...")
        try:
            pedal.file_close()
            pedal.pcmode_off()
            print("Session closed cleanly. Re-run to resume.")
        except PedalTimeout:
            print("Close also timed out. Leave the pedal powered, re-plug USB "
                  "only, then re-run.")
        return 4

    if missing:
        print(f"BACKUP INCOMPLETE: {len(missing)} registered effects never "
              f"appeared in the walk: {', '.join(missing)}")
        return 3
    print(f"Backup complete: {len(names)} files in {files_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
