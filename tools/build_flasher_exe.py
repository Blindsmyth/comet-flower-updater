"""Build script to compile Comet Flower Updater into standalone Windows executables.

Builds two standalone, windowed executables with no Zoom dependencies:
1. "Comet Flower Updater.exe":
   Full Comet Flower suite v0.34.9 (5 real effect slots, Violet Muff 12nF, CFM Preamp,
   CF Delay spillover, unlocked 340% cycle gate, custom bloom animation splash & icons).
2. "Comet Flower Updater - Stereo USB Audio.exe":
   Non-destructive Stereo USB Audio Out patch (updates flash 0x033000 only, preserving
   all stock Zoom effects, DIY effects, patches, and presets).

Both executables:
- Pure windowed GUI (no command terminal window appears)
- Full "Comet Flower" branding (no abbreviations)
- Demoscene chiptune player using Comfortably Numb Solo 2 chords (Bm - A - G - Em)
- Embedded baked-in payload ready to update with one click
"""

import json
from pathlib import Path
import shutil
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
FLASHER_PY = REPO_ROOT / "tools" / "cf_flasher.py"
OUTPUT_DIR = REPO_ROOT / "build" / "flasher"
PUBLIC_RELEASE_DIR = REPO_ROOT / "build" / "public_release"


def build_edition(edition: str = "full", dist_dir: Path = OUTPUT_DIR) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    temp_payload_dir = REPO_ROOT / "build" / f"payload_{edition}"
    if temp_payload_dir.exists():
        shutil.rmtree(temp_payload_dir)
    temp_payload_dir.mkdir(parents=True, exist_ok=True)

    work_dir = REPO_ROOT / "build" / f"pyinstaller_{edition}"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    if edition == "full":
        exe_name = "Comet Flower Updater"
        manifest = {
            "edition": "full",
            "version": "0.34.9",
            "firmware": "firmware_0349.bin",
            "filesystem": "fs_0349.bin",
            "presets": "presets_0349.bin",
            "title": "Comet Flower Updater",
            "subtitle": "[+] RAZOR 1911 DEMOGROUP STYLE  ///  COMET FLOWER FIRMWARE UPDATER [+]",
        }
        # Copy binaries into temp payload
        shutil.copyfile(REPO_ROOT / "build" / "fw_rnd_2026-10-22" / "res1_0348.bin", temp_payload_dir / "firmware_0349.bin")
        shutil.copyfile(REPO_ROOT / "build" / "fw_rnd_2026-10-22" / "fs_bench349.bin", temp_payload_dir / "fs_0349.bin")
        shutil.copyfile(REPO_ROOT / "build" / "fw_rnd_2026-10-22" / "res2_0349.bin", temp_payload_dir / "presets_0349.bin")
    elif edition == "stereo_usb":
        exe_name = "Comet Flower Updater - Stereo USB Audio"
        manifest = {
            "edition": "stereo_usb",
            "version": "Stereo USB Audio Tap",
            "firmware": "firmware_stereo_usb.bin",
            "title": "Comet Flower Updater - Stereo USB Audio",
            "subtitle": "[+] NON-DESTRUCTIVE STEREO USB AUDIO PATCH  ///  COMET FLOWER UPDATER [+]",
        }
        # Copy binary into temp payload
        shutil.copyfile(REPO_ROOT / "build" / "fw" / "res1_public_usb_audio_tap.bin", temp_payload_dir / "firmware_stereo_usb.bin")
    else:
        raise ValueError(f"Unknown edition: {edition}")

    (temp_payload_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    add_data_arg = f"{str(temp_payload_dir)};payload"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        exe_name,
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(work_dir),
        "--specpath",
        str(work_dir),
        "--add-data",
        add_data_arg,
        "--hidden-import",
        "mido.backends.rtmidi",
        "--hidden-import",
        "rtmidi",
        "--hidden-import",
        "tkinter",
        "--hidden-import",
        "cf_flasher_gui",
        "--hidden-import",
        "cf_keygen_music",
        "--collect-all",
        "mido",
        "--collect-all",
        "rtmidi",
        "--collect-all",
        "tkinter",
        str(FLASHER_PY),
    ]

    print(f"\n=======================================================")
    print(f"Building {exe_name}.exe ({edition} edition)...")
    print(f"=======================================================")
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(f"PyInstaller failed for {exe_name} with exit code {result.returncode}")

    exe_path = dist_dir / f"{exe_name}.exe"
    if not exe_path.is_file():
        raise FileNotFoundError(f"Expected executable not found at {exe_path}")

    print(f"\nSuccessfully built {exe_name}.exe")
    print(f"Path: {exe_path}")
    print(f"File size: {exe_path.stat().st_size:,} bytes")
    return exe_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build Comet Flower Updater Executables")
    parser.add_argument("--edition", choices=["full", "stereo_usb", "both"], default="both")
    args = parser.parse_args()

    if args.edition in ("full", "both"):
        build_edition("full")

    if args.edition in ("stereo_usb", "both"):
        usb_exe = build_edition("stereo_usb")
        PUBLIC_RELEASE_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(usb_exe, PUBLIC_RELEASE_DIR / usb_exe.name)
        print(f"Also copied to public release: {PUBLIC_RELEASE_DIR / usb_exe.name}")


if __name__ == "__main__":
    main()
