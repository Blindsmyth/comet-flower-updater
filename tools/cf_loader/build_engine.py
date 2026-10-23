"""Build engine and recipe executor for Comet Flower Installer."""

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from typing import Callable, Dict, List, Optional, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BUILDS_MD_PATH = REPO_ROOT / "docs" / "BUILDS.md"
INSTALLER_LOG_PATH = REPO_ROOT / "build" / "installer_log.json"
DEFAULT_PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"


def parse_next_version(builds_md_path: Optional[Path] = None) -> str:
    """Read docs/BUILDS.md and compute next 0.<updater>.<rebuild>."""
    p = builds_md_path or BUILDS_MD_PATH
    fallback = "0.34.5"
    if not p.exists():
        return fallback

    try:
        content = p.read_text(encoding="utf-8")
        matches = re.findall(r"\|\s*0\.(\d+)\.(\d+)\s*\|", content)
        if not matches:
            return fallback

        # Last match in the table
        updater_str, rebuild_str = matches[-1]
        updater = int(updater_str)
        rebuild = int(rebuild_str)
        return f"0.{updater}.{rebuild + 1}"
    except Exception:
        return fallback


def approved_firmware_hash(builds_md_path: Optional[Path] = None) -> Optional[str]:
    """Short firmware hash of the docs/BUILDS.md row marked "flash this" (the approved build).

    Newest-by-date is not safe: a shelved experiment can be the newest file (0.34.5 was
    packaged with the shelved 0.34.4 bloom firmware that way, 2026-10-23)."""
    p = builds_md_path or BUILDS_MD_PATH
    if not p.exists():
        return None
    for line in p.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 7 and "flash this" in cells[-1].lower() and re.fullmatch(r"[0-9a-f]{8}", cells[3]):
            return cells[3]
    return None


def find_default_firmware_bin(builds_md_path: Optional[Path] = None) -> Optional[Path]:
    """The approved firmware under build/cf_header/: the res1_*.bin whose SHA-256 starts with the
    firmware hash of the "flash this" row in docs/BUILDS.md; newest res1_*.bin only if none is marked."""
    cf_header_dir = REPO_ROOT / "build" / "cf_header"
    if not cf_header_dir.is_dir():
        return None

    # res1_*.bin = the finished firmware (controller + USB audio layers); ctl_*.bin are
    # intermediate controller-only builds and must not be packaged.
    bins = [f for f in cf_header_dir.glob("res1_*.bin") if f.is_file() and f.stat().st_size > 100000]
    if not bins:
        return None
    want = approved_firmware_hash(builds_md_path)
    if want:
        for f in bins:
            if calculate_sha256(f).startswith(want):
                return f
    bins.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return bins[0]


def find_default_official_updater() -> Optional[Path]:
    """Find Zoom's official updater executable."""
    candidates = [
        REPO_ROOT / "build" / "fw" / "ZOOM G1X FOUR System v2.00 Updater.exe",
        REPO_ROOT / "build" / "fw" / "Comet Flower ZG1X4 Controller TEST Updater.exe",
    ]
    for c in candidates:
        if c.exists():
            return c
    # Search under build/
    for p in REPO_ROOT.glob("build/**/ZOOM*.exe"):
        if p.is_file():
            return p
    return None


def calculate_sha256(path: Path) -> str:
    """Calculate SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def append_installer_log(entry: dict, log_path: Optional[Path] = None) -> None:
    """Append a build entry to build/installer_log.json."""
    p = log_path or INSTALLER_LOG_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    records = []
    if p.exists():
        try:
            records = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                records = []
        except Exception:
            records = []

    records.append(entry)
    p.write_text(json.dumps(records, indent=2), encoding="utf-8")


def build_make_g1_image_cmd(
    factory_img: Path,
    out_img: Path,
    keep_stock: List[str],
    cf_effect_paths: List[Path],
    clean: bool = True,
    python_exe: Optional[Path] = None,
) -> List[str]:
    """Build the exact argv for tools/make_g1_image.py."""
    py = str(python_exe or DEFAULT_PYTHON)
    cmd = [py, str(REPO_ROOT / "tools" / "make_g1_image.py")]
    if clean:
        cmd.append("--clean")
        for k in keep_stock:
            cmd.extend(["--keep", k])
    cmd.extend([str(factory_img), str(out_img)])
    for ep in cf_effect_paths:
        cmd.append(str(ep))
    return cmd


def build_make_splash_cmd(
    version: str,
    out_png: Path,
    title: str = "CF-ZGX4",
    tag: str = "TEST",
    python_exe: Optional[Path] = None,
) -> List[str]:
    """Build the exact argv for tools/make_splash.py."""
    py = str(python_exe or DEFAULT_PYTHON)
    return [
        py,
        str(REPO_ROOT / "tools" / "make_splash.py"),
        str(version),
        str(out_png),
        "--title",
        str(title),
        "--tag",
        str(tag),
    ]


def build_make_fs_restore_updater_cmd(
    official_updater: Path,
    out_exe: Path,
    test_controller_fw: Path,
    fs_image: Path,
    presets_bin: Optional[Path] = None,
    splash_png: Optional[Path] = None,
    python_exe: Optional[Path] = None,
) -> List[str]:
    """Build the exact argv for tools/make_fs_restore_updater.py."""
    py = str(python_exe or DEFAULT_PYTHON)
    cmd = [
        py,
        str(REPO_ROOT / "tools" / "make_fs_restore_updater.py"),
        str(official_updater),
        str(out_exe),
        "--test-controller-fw",
        str(test_controller_fw),
        "--image",
        str(fs_image),
    ]
    if presets_bin:
        cmd.extend(["--presets", str(presets_bin)])
    if splash_png:
        cmd.extend(["--splash", str(splash_png)])
    return cmd


def parse_updater_stages(stdout_text: str) -> List[str]:
    """Extract erase/write stages from make_fs_restore_updater output."""
    stages = []
    capture = False
    for line in stdout_text.splitlines():
        line_clean = line.strip()
        if "stages:" in line_clean.lower():
            capture = True
            continue
        if capture:
            if line_clean.startswith(("erase ", "write ")):
                stages.append(line_clean)
            elif not line_clean or line_clean.startswith("---") or "done" in line_clean.lower():
                pass
    return stages
