#!/usr/bin/env python3
"""Complete backup tool for Zoom G1 Four / G1X Four pedals.

Backs up:
  1. All 50 user/factory patches (PATCH_001.ZPTC .. PATCH_050.ZPTC)
  2. All installed effect files (.ZD2, FLST_SEQ.ZT2, etc.)
  3. Writes backup_manifest.json with metadata

Usage:
  python tools/backup_pedal.py [output_dir]
"""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from backup_g1 import GuardedPort, PedalTimeout, registered_effects, walk, zoomzt2
import pedal_ports


def backup_pedal(out_dir):
    out_dir = Path(out_dir).resolve()
    patches_dir = out_dir / "patches"
    effects_dir = out_dir / "effects"
    patches_dir.mkdir(parents=True, exist_ok=True)
    effects_dir.mkdir(parents=True, exist_ok=True)

    log_path = out_dir / "wire.log"
    log = open(log_path, "a", encoding="utf-8")
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log.write(f"\n# Backup session started {timestamp}\n")

    print("====================================================================")
    print("  ZOOM G1 / G1X FOUR — COMPLETE PEDAL BACKUP")
    print("====================================================================")
    print(f"Target directory: {out_dir}")
    print("Connecting to pedal over USB MIDI...")

    pedal_ports.register_zoomzt2(zoomzt2)
    pedal = zoomzt2.zoomzt2()
    if not pedal.connect():
        print("\nERROR: No Zoom G Series or Comet Flower pedal detected!")
        print("Please ensure the pedal is powered on and connected via USB.")
        return 1

    pedal.inport = GuardedPort(pedal.inport, log)
    pedal.outport = GuardedPort(pedal.outport, log)

    manifest = {
        "timestamp": timestamp,
        "patches": {},
        "effects": [],
        "disk_usage_percent": None
    }

    try:
        pedal.pcmode_on()

        # -------------------------------------------------------------
        # Phase 1: Back up patches
        # -------------------------------------------------------------
        print("\n[Phase 1/2] Backing up patches 1..50...")
        count, psize, bsize = pedal.patch_check()
        print(f"  Detected {count} patches (patch size={psize}B, bank size={bsize}B)")

        method = None
        saved_patches = 0
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
                print(f"  Warning: patch {loc:2d} did not return valid PTCF header.")
                continue

            dest_file = patches_dir / f"PATCH_{loc:03d}.ZPTC"
            dest_file.write_bytes(bytes(data))
            manifest["patches"][loc] = {
                "file": dest_file.name,
                "size": len(data)
            }
            saved_patches += 1
            print(f"  Saved patch {loc:2d}/{count:2d} ({len(data)} bytes)", flush=True)

        print(f"Phase 1 complete: {saved_patches} patches backed up to {patches_dir.name}/")

        # -------------------------------------------------------------
        # Phase 2: Back up effects filesystem
        # -------------------------------------------------------------
        print("\n[Phase 2/2] Backing up installed effect files (.ZD2)...")
        usage = pedal.disk_usage()
        manifest["disk_usage_percent"] = usage
        print(f"  Pedal filesystem usage: {usage:.1f}%")

        names = walk(pedal)
        print(f"  Discovered {len(names)} files on pedal filesystem.")

        # Download FLST_SEQ.ZT2 first
        flst_dest = effects_dir / "FLST_SEQ.ZT2"
        flst_data = zoomzt2.download_and_save_file(pedal, "FLST_SEQ.ZT2", str(flst_dest))
        if flst_data:
            print("  Downloaded FLST_SEQ.ZT2 (effect catalog index).")

        saved_files = 0
        for i, name in enumerate(names, 1):
            target = effects_dir / name
            print(f"  [{i:2d}/{len(names):2d}] Downloading {name}...", flush=True)
            zoomzt2.download_and_save_file(pedal, name, str(target))
            manifest["effects"].append(name)
            saved_files += 1

        print(f"Phase 2 complete: {saved_files} effect files backed up to {effects_dir.name}/")

        pedal.disconnect()

        manifest_path = out_dir / "backup_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        print("\n====================================================================")
        print("  BACKUP SUCCESSFULLY COMPLETED!")
        print("====================================================================")
        print(f"  Patches:  {saved_patches} files in {patches_dir}")
        print(f"  Effects:  {saved_files} files in {effects_dir}")
        print(f"  Manifest: {manifest_path}")
        print("====================================================================")
        return 0

    except PedalTimeout as e:
        print(f"\nPedal communication timed out: {e}")
        try:
            pedal.file_close()
            pedal.pcmode_off()
        except Exception:
            pass
        return 1
    except Exception as e:
        print(f"\nUnexpected error during backup: {e}")
        try:
            pedal.disconnect()
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else (ROOT / "build" / "public_release" / "my_pedal_backup")
    sys.exit(backup_pedal(target))
