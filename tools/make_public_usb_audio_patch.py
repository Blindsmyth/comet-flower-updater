"""Build the public-release USB audio out patch updater for Zoom G1X Four.

Usage:
    python tools/make_public_usb_audio_patch.py [official_updater.exe] [output.exe]

Safety Invariants:
    1. Updates ONLY main firmware (flash 0x33000..0xBF000).
    2. NEVER erases or writes presets (flash 0x28000..0x33000) - stock patches preserved.
    3. NEVER erases or writes settings (flash 0xBF000..0xC0000) - calibration preserved.
    4. NEVER erases or writes filesystem (flash 0x102000..0x400000) - all stock & DIY effects preserved.
    5. NEVER erases or writes bootloader (flash 0x00000..0x28000) - update mode always intact.
    6. Reversible at any time by running Zoom's official v2.00 updater.
"""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STOCK = ROOT / "build" / "fw" / "res1_493412.bin"
DEFAULT_BASE = ROOT / "build" / "fw" / "res1_cfupd.bin"
DEFAULT_OFFICIAL = Path(r"C:\Users\z\Downloads\G1X FOUR_v2.00_Win_E\ZOOM G1X FOUR System v2.00 Updater.exe")
OUT_DIR = ROOT / "build" / "public_release"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("official_updater", nargs="?", default=str(DEFAULT_OFFICIAL),
                        help="Path to official 'ZOOM G1X FOUR System v2.00 Updater.exe'")
    parser.add_argument("out_exe", nargs="?",
                        default=str(OUT_DIR / "ZOOM G1X FOUR USB Audio Patch (Comet Flower TEST).exe"),
                        help="Output patched updater path")
    args = parser.parse_args()

    official = Path(args.official_updater)
    if not official.exists():
        sys.exit(f"Official updater not found: {official}\nPlease download ZOOM G1X FOUR System v2.00 Updater.exe.")

    out_exe = Path(args.out_exe)
    out_exe.parent.mkdir(parents=True, exist_ok=True)

    # 1. Controller base with UI menu
    ctl_bin = ROOT / "build" / "fw" / "res1_public_audio_ctl.bin"
    print("[1/4] Building controller layer with on-pedal UI menu...")
    subprocess.run([
        sys.executable, str(ROOT / "tools" / "make_controller_fw.py"),
        "--base", str(DEFAULT_BASE),
        "--ui",
        "--out", str(ctl_bin)
    ], check=True)

    # 2. USB audio tap layer
    tap_bin = ROOT / "build" / "fw" / "res1_public_usb_audio_tap.bin"
    print("[2/4] Layering USB audio tap...")
    subprocess.run([
        sys.executable, str(ROOT / "tools" / "make_usb_audio_fw.py"),
        "--base", str(ctl_bin),
        "--tap",
        "--out", str(tap_bin)
    ], check=True)

    # 3. Package firmware-only updater
    print("[3/4] Packaging firmware-only updater (flash 0x33000 only)...")
    subprocess.run([
        sys.executable, str(ROOT / "tools" / "make_fs_restore_updater.py"),
        str(official), str(out_exe),
        "--test-controller-fw", str(tap_bin),
        "--fw-only"
    ], check=True)

    # 4. Verify stage table safety
    print("[4/4] Verifying flash stage safety...")
    subprocess.run([
        sys.executable, str(ROOT / "tools" / "check_updater_stages.py"),
        str(out_exe)
    ], check=True)

    print("\nSUCCESS: Public USB audio patch updater created:")
    print(f"  Output: {out_exe}")


if __name__ == "__main__":
    main()
