"""Build script to compile tools/cf_flasher.py into a standalone Windows executable.

Uses PyInstaller to bundle Python, mido, and python-rtmidi into a single .exe
so firmware flashing can be performed without any Python runtime or Zoom dependencies.

    python tools/build_flasher_exe.py
"""

from pathlib import Path
import subprocess
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
FLASHER_PY = REPO_ROOT / "tools" / "cf_flasher.py"
OUTPUT_DIR = REPO_ROOT / "build" / "flasher"


def build_flasher_exe(dist_dir: Path = OUTPUT_DIR) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    work_dir = REPO_ROOT / "build" / "pyinstaller_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    payload_dir = REPO_ROOT / "tools" / "payload"
    add_data_arg = f"{str(payload_dir)};payload"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",  # No command terminal window: purely the graphical application!
        "--name",
        "Comet Flower Flasher",
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

    print("Running PyInstaller...")
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        raise RuntimeError(f"PyInstaller failed with exit code {result.returncode}")

    exe_path = dist_dir / "Comet Flower Flasher.exe"
    if not exe_path.is_file():
        raise FileNotFoundError(f"Expected executable not found at {exe_path}")

    print(f"\nSuccessfully built standalone flasher: {exe_path}")
    print(f"File size: {exe_path.stat().st_size:,} bytes")
    return exe_path


if __name__ == "__main__":
    build_flasher_exe()
