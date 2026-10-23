"""Backup management and scanning for Comet Flower Installer."""

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Callable, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_BACKUPS_DIR = REPO_ROOT / "build" / "backups"
REPO_BACKUP_DIR = REPO_ROOT / "backup"


@dataclass
class BackupInfo:
    path: Path
    name: str
    date_str: str
    effects_count: int
    patches_count: int
    size_bytes: int
    manifest_present: bool
    is_valid: bool

    @property
    def size_mb(self) -> float:
        return self.size_bytes / (1024 * 1024)

    @property
    def display_size(self) -> str:
        if self.size_bytes >= 1024 * 1024:
            return f"{self.size_mb:.2f} MB"
        return f"{self.size_bytes / 1024:.1f} KB"


def parse_backup_date(folder_name: str, mtime: float) -> str:
    """Extract a friendly date string from folder name or file modification time."""
    # Common format: YYYY-MM-DD_HHMMSS or YYYY-MM-DD
    parts = folder_name.split("_")
    try:
        if len(parts) >= 2:
            dt = datetime.strptime(parts[0] + "_" + parts[1][:6], "%Y-%m-%d_%H%M%S")
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        elif len(parts) == 1 and len(parts[0]) == 10:
            dt = datetime.strptime(parts[0], "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")


def inspect_backup_dir(path: Path) -> Optional[BackupInfo]:
    """Inspect a single directory to see if it represents a valid backup."""
    if not path.is_dir():
        return None

    # Check for effects
    effects_files = set()
    for sub in (path / "files", path / "effects", path):
        if sub.is_dir():
            for f in sub.glob("*.ZD2"):
                effects_files.add(f.name.upper())

    # Check for patches
    patch_files = set()
    for sub in (path / "patches", path):
        if sub.is_dir():
            for p in sub.glob("PATCH_*.ZPTC"):
                patch_files.add(p.name)

    manifest_file = path / "backup_manifest.json"
    manifest_present = manifest_file.is_file()

    # Calculate total size
    total_size = 0
    try:
        for root, _, files in os.walk(path):
            for f in files:
                total_size += Path(root, f).stat().st_size
    except Exception:
        pass

    # A valid backup has either patches or effects
    is_valid = len(effects_files) > 0 or len(patch_files) > 0 or manifest_present
    if not is_valid:
        return None

    date_str = parse_backup_date(path.name, path.stat().st_mtime)

    return BackupInfo(
        path=path,
        name=path.name,
        date_str=date_str,
        effects_count=len(effects_files),
        patches_count=len(patch_files),
        size_bytes=total_size,
        manifest_present=manifest_present,
        is_valid=is_valid,
    )


def scan_backups(search_dirs: Optional[List[Path]] = None) -> List[BackupInfo]:
    """Scan search directories for backups and return list ordered newest first."""
    if search_dirs is None:
        search_dirs = [DEFAULT_BACKUPS_DIR, REPO_BACKUP_DIR]

    results: List[BackupInfo] = []
    seen_paths = set()

    for base in search_dirs:
        if not base.exists():
            continue
        # Direct check of base itself
        info = inspect_backup_dir(base)
        if info and base.resolve() not in seen_paths:
            seen_paths.add(base.resolve())
            results.append(info)

        # Check subdirectories
        try:
            for child in sorted(base.iterdir()):
                if child.is_dir() and child.name not in ("photos", "__pycache__"):
                    child_info = inspect_backup_dir(child)
                    if child_info and child.resolve() not in seen_paths:
                        seen_paths.add(child.resolve())
                        results.append(child_info)
        except Exception:
            pass

    # Sort by mtime descending
    results.sort(key=lambda b: b.path.stat().st_mtime if b.path.exists() else 0, reverse=True)
    return results


def delete_backup(backup_path: Path) -> bool:
    """Delete a backup folder."""
    if not backup_path.exists() or not backup_path.is_dir():
        return False
    shutil.rmtree(backup_path)
    return True


def create_backup_destination(base_dir: Optional[Path] = None) -> Path:
    """Create timestamped destination under build/backups/."""
    target_base = base_dir or DEFAULT_BACKUPS_DIR
    target_base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = target_base / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def build_backup_commands(dest_dir: Path, python_exe: Optional[Path] = None) -> List[List[str]]:
    """Build the command lines to run tools/backup_g1.py and tools/backup_pedal.py."""
    py = str(python_exe or (REPO_ROOT / ".venv" / "Scripts" / "python.exe"))
    cmd1 = [py, str(REPO_ROOT / "tools" / "backup_g1.py"), str(dest_dir)]
    cmd2 = [py, str(REPO_ROOT / "tools" / "backup_pedal.py"), str(dest_dir)]
    return [cmd1, cmd2]
