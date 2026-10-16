#!/usr/bin/env python3
"""Read-only backup of every patch memory on a G1 Four, as PATCH_NNN.ZPTC.

  python tools/backup_patches_g1.py <output-dir>

Uses zoom-zt2's patch_check (0x44) and patch download, both read-only. The
G1 Four may use the "new" (0x46) or the "old" (0x09) read; the first patch
decides which, by trying new and falling back to old. Every reply is
timeout-bounded (GuardedPort from backup_g1.py) and logged to wire.log.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from backup_g1 import GuardedPort, PedalTimeout, zoomzt2  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    log = open(out / "wire.log", "a")
    log.write(f"# patch session {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    import pedal_ports
    pedal_ports.register_zoomzt2(zoomzt2)
    pedal = zoomzt2.zoomzt2()
    if not pedal.connect():
        sys.exit("FAIL: no 'ZOOM G' / 'Comet Flower' MIDI port found.")
    pedal.inport = GuardedPort(pedal.inport, log)
    pedal.outport = GuardedPort(pedal.outport, log)
    try:
        pedal.pcmode_on()
        count, psize, bsize = pedal.patch_check()
        print(f"patches: count={count} patch_size={psize} bank_size={bsize}")
        method = None
        for loc in range(1, count + 1):
            data = None
            if method in (None, "new"):
                try:
                    data = pedal.patch_download(loc)
                    method = method or ("new" if data and data[:4] == b"PTCF" else None)
                except (PedalTimeout, IndexError):
                    data = None
            if method is None or method == "old":
                if not (data and data[:4] == b"PTCF"):
                    data = pedal.patch_download_old(loc)
                    method = "old" if data and data[:4] == b"PTCF" else method
            if not data or data[:4] != b"PTCF":
                print(f"  patch {loc:3d}: no PTCF data, stopping")
                return 3
            (out / f"PATCH_{loc:03d}.ZPTC").write_bytes(bytes(data))
            print(f"  patch {loc:3d}: {len(data)} bytes ({method})", flush=True)
        pedal.disconnect()
    except PedalTimeout as e:
        print(f"STOPPED: pedal stopped replying ({e}). Keep it powered; re-run.")
        try:
            pedal.pcmode_off()
        except PedalTimeout:
            pass
        return 4
    print(f"Patch backup complete: {count} patches in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
