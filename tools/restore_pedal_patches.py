#!/usr/bin/env python3
"""Restore user patches (PATCH_NNN.ZPTC) to Zoom G1 Four / G1X Four.

Reads patches from a directory and uploads them to the pedal, verifying
each upload byte-for-byte with a readback check.

Usage:
  python tools/restore_pedal_patches.py [patches_dir]
"""
import glob
import os
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from backup_g1 import GuardedPort, PedalTimeout, zoomzt2
import pedal_ports


def restore_patches(patches_dir):
    patches_dir = Path(patches_dir).resolve()
    if not patches_dir.exists():
        print(f"ERROR: Directory not found: {patches_dir}")
        return 1

    files = sorted(patches_dir.glob("PATCH_*.ZPTC"))
    if not files:
        # Check subfolder 'patches' if user passed the parent backup directory
        if (patches_dir / "patches").exists():
            patches_dir = patches_dir / "patches"
            files = sorted(patches_dir.glob("PATCH_*.ZPTC"))

    if not files:
        print(f"ERROR: No PATCH_*.ZPTC files found in {patches_dir}")
        return 1

    print("====================================================================")
    print("  ZOOM G1 / G1X FOUR — RESTORE PATCHES")
    print("====================================================================")
    print(f"Source directory: {patches_dir}")
    print(f"Found {len(files)} patch file(s) to restore.")
    print("Connecting to pedal over USB MIDI...")

    log_path = patches_dir.parent / "restore_wire.log"
    log = open(log_path, "a", encoding="utf-8")
    log.write(f"\n# Restore session started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

    pedal_ports.register_zoomzt2(zoomzt2)
    pedal = zoomzt2.zoomzt2()
    if not pedal.connect():
        print("\nERROR: No Zoom G Series or Comet Flower pedal detected!")
        print("Please ensure the pedal is powered on and connected via USB.")
        return 1

    pedal.inport = GuardedPort(pedal.inport, log)
    pedal.outport = GuardedPort(pedal.outport, log)

    try:
        pedal.pcmode_on()
        count, psize, bsize = pedal.patch_check()
        print(f"Pedal ready: {count} patch slots available.\n")

        restored = 0
        for pfile in files:
            m = re.search(r"PATCH_(\d+)\.ZPTC", pfile.name, re.IGNORECASE)
            if not m:
                continue
            loc = int(m.group(1))
            if not (1 <= loc <= count):
                print(f"  Skipping {pfile.name} (location {loc} out of bounds 1..{count})")
                continue

            data = pfile.read_bytes()
            if not data.startswith(b"PTCF"):
                print(f"  Skipping {pfile.name} (corrupt or non-PTCF file)")
                continue

            pedal.patch_upload(loc, data)
            back = bytes(pedal.patch_download(loc))
            if back != data:
                print(f"  ERROR: Patch {loc:2d} readback differs ({len(back)}B vs {len(data)}B)!")
                pedal.disconnect()
                return 1

            restored += 1
            print(f"  [{restored:2d}/{len(files):2d}] Restored Patch {loc:2d}: {pfile.name} (Verified OK)", flush=True)

        pedal.disconnect()
        print("\n====================================================================")
        print("  PATCH RESTORE COMPLETED SUCCESSFULLY!")
        print(f"  Total patches restored and verified: {restored}")
        print("====================================================================")
        return 0

    except PedalTimeout as e:
        print(f"\nPedal communication timed out: {e}")
        try:
            pedal.pcmode_off()
        except Exception:
            pass
        return 1
    except Exception as e:
        print(f"\nUnexpected error during patch restore: {e}")
        try:
            pedal.disconnect()
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else (ROOT / "build" / "public_release" / "my_pedal_backup" / "patches")
    sys.exit(restore_patches(target))
