"""Core business logic for CF Loader.

Pure functions and helpers for:
- Scanning effect library (build/*.ZD2), checking slot heap and parsing reports.
- Pre-flight checks before image building.
- Subprocess tool execution with line streaming, logging, timeouts, and cancellation.
- Status and configuration persistence (build/loader/config.json, status.json).
- Safe image and patched updater creation.

NO tkinter import allowed in this module.
"""

from dataclasses import dataclass, field
import hashlib
import json
import math
import queue
import threading
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
from typing import Callable, Dict, List, Optional, Set, Tuple, Union
import zlib

import pefile

# Repository root derived from module location (never assumes current working dir)
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOADER_DIR = REPO_ROOT / "build" / "loader"
DEFAULT_PYTHON = REPO_ROOT / ".venv" / "Scripts" / "python.exe"

# Slot heap limits (fixed 0xa000 = 40 KiB per slot on G1 Four, recon/14)
SLOT_HEAP = 0xA000  # 40,960 bytes
WARN_HEADROOM = 2048
BLOCK_HEADER = 8
SEG_ALIGN = 32
MODULE_RECORD = 132

# Flash & updater constants
TABLE_VA = 0x43AC88
EXPECTED_TABLE = [
    (1, 0xBF000, 0x1000, 0),
    (1, 0x28000, 0xB000, 0),
    (2, 0x28000, 0, 0x85),
    (1, 0x0, 0x28000, 0),
    (2, 0x0, 0, 0x8E),
    (1, 0x33000, 0x8C000, 0),
    (2, 0x33000, 0, 0x81),
    (2, 0xBF000, 0, 0x8B),
]
FS_ADDR, FS_SIZE, FS_RES = 0x102000, 0x2FE000, 0x88

# 130 stock effect IDs and filenames from official G1X Four v2.00 image (FLST_SEQ.ZT2)
STOCK_EFFECTS: Dict[str, int] = {
    "COMP.ZD2": 0x01000010,
    "RACKCOMP.ZD2": 0x01000020,
    "SLWATK.ZD2": 0x01000030,
    "ZNR.ZD2": 0x01000040,
    "MUTESW.ZD2": 0x01000050,
    "GRAYCOMP.ZD2": 0x01000060,
    "N_GATE.ZD2": 0x01000070,
    "OPTCOMP.ZD2": 0x01000080,
    "BLACKOPT.ZD2": 0x01800010,
    "LMT1176.ZD2": 0x01800020,
    "AUTOWAH.ZD2": 0x02000010,
    "RESONANC.ZD2": 0x02000020,
    "CRY.ZD2": 0x02000030,
    "SEQFLTR.ZD2": 0x02000040,
    "GT_GEQ1U.ZD2": 0x02000051,
    "GTGEQ71U.ZD2": 0x02000054,
    "STGTGE1U.ZD2": 0x02000061,
    "PARAEQ.ZD2": 0x02000070,
    "RNDMFLTR.ZD2": 0x02000090,
    "LOWPASSF.ZD2": 0x020000a0,
    "EXCITER.ZD2": 0x020000b0,
    "STEP.ZD2": 0x020000c0,
    "LFO_FLTR.ZD2": 0x020000d0,
    "TS_DRIVE.ZD2": 0x03000010,
    "EP_STOMP.ZD2": 0x03000020,
    "RCBOOST.ZD2": 0x03000030,
    "GOLD_DRV.ZD2": 0x03000040,
    "SWEETDRV.ZD2": 0x03000050,
    "DYNDRIVE.ZD2": 0x03000060,
    "REDCRUNC.ZD2": 0x03000070,
    "MTLWRLD.ZD2": 0x03000080,
    "TB_MK15.ZD2": 0x03000090,
    "OCTFUZZ.ZD2": 0x030000a0,
    "SPTBOOST.ZD2": 0x030000b0,
    "ACOSIM.ZD2": 0x030000c0,
    "NYC_MUFF.ZD2": 0x030000d0,
    "BGTHRTTL.ZD2": 0x030000e0,
    "BG_GRID.ZD2": 0x030000f0,
    "DIST_1.ZD2": 0x03000120,
    "SQUEAK.ZD2": 0x03000130,
    "UPOCTBST.ZD2": 0x03000140,
    "OUT_BST.ZD2": 0x03000150,
    "DISTPLUS.ZD2": 0x03000160,
    "ZEN_DRV.ZD2": 0x03000170,
    "VIOLETDS.ZD2": 0x03000190,
    "MS800_1U.ZD2": 0x04000011,
    "MS19591U.ZD2": 0x04000019,
    "MS45OS1U.ZD2": 0x0400001b,
    "FD_TWR1U.ZD2": 0x04000021,
    "FDBMAN1U.ZD2": 0x04000028,
    "FDDLXR1U.ZD2": 0x0400002c,
    "FDMSTR1U.ZD2": 0x0400002d,
    "UK30A_1U.ZD2": 0x04000031,
    "BGMK1_1U.ZD2": 0x04000041,
    "BGMK3_1U.ZD2": 0x04000043,
    "XTSBLU1U.ZD2": 0x04000051,
    "HW100_1U.ZD2": 0x04000061,
    "RCTORG1U.ZD2": 0x04000071,
    "ORG1201U.ZD2": 0x04000081,
    "DZ_DRV1U.ZD2": 0x04000091,
    "MACH301U.ZD2": 0x040000a1,
    "MS4X12.ZD2": 0x05000010,
    "MS4X12GB.ZD2": 0x05000018,
    "MS4X12AL.ZD2": 0x0500001a,
    "FD2X12.ZD2": 0x05000020,
    "FDB4X10.ZD2": 0x05000027,
    "FDDX1X12.ZD2": 0x0500002a,
    "FDMA2X12.ZD2": 0x0500002b,
    "UK2X12.ZD2": 0x05000030,
    "MK1_1X12.ZD2": 0x05000040,
    "MK3_1X12.ZD2": 0x05000042,
    "BGN4X12.ZD2": 0x05000050,
    "HW4X12.ZD2": 0x05000060,
    "RCT4X12.ZD2": 0x05000070,
    "ORG_4X12.ZD2": 0x05000080,
    "DZ4X12F.ZD2": 0x05000090,
    "MA2X12.ZD2": 0x050000a0,
    "TREMOLO.ZD2": 0x06000010,
    "CHORUS.ZD2": 0x06000020,
    "STEREOCH.ZD2": 0x06000030,
    "PHASER.ZD2": 0x06000040,
    "VINFLNGR.ZD2": 0x06000050,
    "THEVIBE.ZD2": 0x06000060,
    "VIBRATO.ZD2": 0x06000070,
    "OCTAVE.ZD2": 0x06000080,
    "RINGMOD.ZD2": 0x06000090,
    "DETUNE.ZD2": 0x060000a0,
    "PITCHSHF.ZD2": 0x060000b0,
    "MONOPITC.ZD2": 0x060000c0,
    "HPS.ZD2": 0x060000d0,
    "SLICER.ZD2": 0x060000f0,
    "CLONECHO.ZD2": 0x06000100,
    "SUPERCHO.ZD2": 0x06000110,
    "STONEPHA.ZD2": 0x06000120,
    "CRNTRI3S.ZD2": 0x06000131,
    "BENDCHO.ZD2": 0x06000140,
    "ANA234CH.ZD2": 0x06000150,
    "WRPPHASE.ZD2": 0x06000160,
    "DUOPHA1U.ZD2": 0x06000171,
    "BOMBER.ZD2": 0x07000010,
    "AUTOPAN.ZD2": 0x07000020,
    "LPROLL3S.ZD2": 0x07000041,
    "HOTSPICE.ZD2": 0x07000050,
    "DELAY_3S.ZD2": 0x08000011,
    "ANDLY_3S.ZD2": 0x08000021,
    "TAPEECHO.ZD2": 0x08000030,
    "RVRSDL3S.ZD2": 0x08000041,
    "MODDELAY.ZD2": 0x08000050,
    "PPDLY_3S.ZD2": 0x08000081,
    "FLTRDLY.ZD2": 0x08000090,
    "DUALDL3S.ZD2": 0x080000a1,
    "PTCHDL3S.ZD2": 0x080000b1,
    "SLPBKD3S.ZD2": 0x080000c1,
    "APANDL3S.ZD2": 0x080000d1,
    "PHASDL1U.ZD2": 0x080000e1,
    "TPEC3_3S.ZD2": 0x080000f1,
    "ICEDLY3S.ZD2": 0x08000101,
    "SLATDL3S.ZD2": 0x08000111,
    "SOFTEC3S.ZD2": 0x08000121,
    "AIR.ZD2": 0x09000010,
    "ROOM.ZD2": 0x09000020,
    "HALL.ZD2": 0x09000030,
    "HD_HALL.ZD2": 0x09000040,
    "SPRING.ZD2": 0x09000050,
    "FDSPRING.ZD2": 0x09000060,
    "PLATEREV.ZD2": 0x09000070,
    "EARLYREF.ZD2": 0x09000080,
    "CHURCH.ZD2": 0x090000a0,
    "CHAMBER.ZD2": 0x090000d0,
    "GATE_REV.ZD2": 0x090000e0,
}
STOCK_EFFECT_NAMES: Set[str] = set(STOCK_EFFECTS.keys())
STOCK_EFFECT_IDS: Set[int] = set(STOCK_EFFECTS.values())


# Valid stages in effect lifecycle
VALID_STAGES = ["built", "in image", "audio-pass", "cost-measured", "ok-save"]


@dataclass
class EffectReportInfo:
    text_bytes: Optional[int] = None
    const_bytes: Optional[int] = None
    state_bytes: Optional[int] = None
    stack: Optional[str] = None


@dataclass
class EffectInfo:
    path: Path
    filename: str
    name: str
    effect_id: int
    target: int
    size: int
    crc_ok: bool
    is_g1_target: bool
    slot_used: int
    slot_free: int
    slot_ok: bool
    has_oversize_sibling: bool
    report: EffectReportInfo
    valid_for_selection: bool
    rejection_reasons: List[str] = field(default_factory=list)

    @property
    def id_hex(self) -> str:
        return f"0x{self.effect_id:08x}"


@dataclass
class PreflightCheckResult:
    check_num: int
    title: str
    passed: bool
    message: str


@dataclass
class ToolExecutionResult:
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_sec: float


class PreflightError(Exception):
    """Raised when pre-flight checks fail before building."""
    pass


def get_python_exe() -> Path:
    """Return path to python interpreter."""
    if DEFAULT_PYTHON.exists():
        return DEFAULT_PYTHON
    return Path(sys.executable)


def crc32_of_file(path: Union[str, Path]) -> str:
    """Calculate hex CRC32 of file."""
    buf = Path(path).read_bytes()
    return f"{zlib.crc32(buf) & 0xFFFFFFFF:08x}"


# ---------------------------------------------------------------------------
# Slot memory calculation (exact algorithm from tools/check_slot_mem.py)
# ---------------------------------------------------------------------------

def _block_size(n: int, align: int = 8) -> int:
    """Worst-case heap bytes for an n-byte allocation."""
    return ((n + 7) & ~7) + BLOCK_HEADER + (align - 8 if align > 8 else 0)


def calculate_slot_bytes(zd2_bytes: bytes) -> int:
    """Calculate slot heap usage for a ZD2 container."""
    idx = zd2_bytes.find(b"\x7fELF")
    if idx < 0:
        raise ValueError("No ELF image found in ZD2 container")
    elf = zd2_bytes[idx:]
    phoff, shoff = struct.unpack_from("<II", elf, 0x1C)
    phent, phnum, shent, shnum, shstr = struct.unpack_from("<HHHHH", elf, 0x2A)
    total = _block_size(MODULE_RECORD)
    for k in range(phnum):
        ptype, _, _, _, _, memsz = struct.unpack_from("<6I", elf, phoff + k * phent)
        if ptype == 1:  # PT_LOAD
            total += _block_size(memsz, SEG_ALIGN)
    sh = [struct.unpack_from("<10I", elf, shoff + k * shent) for k in range(shnum)]
    names_offset = sh[shstr][4]
    for s in sh:
        name_start = names_offset + s[0]
        name_end = elf.find(b"\x00", name_start)
        name = elf[name_start:name_end]
        if name in (b".dynsym", b".dynstr"):
            total += _block_size(s[5])
    return total


# ---------------------------------------------------------------------------
# ZD2 parsing and report extraction
# ---------------------------------------------------------------------------

def parse_report_file(zd2_path: Path) -> EffectReportInfo:
    """Parse .text, const, state, stack from build/<FILE>.REPORT.md or manifest."""
    stem = zd2_path.stem
    report_paths = [
        zd2_path.parent / f"{zd2_path.name}.REPORT.md",
        zd2_path.parent / f"{stem}.REPORT.md",
        zd2_path.parent / f"{stem}.ZD2.REPORT.md",
    ]
    info = EffectReportInfo()
    for rp in report_paths:
        if rp.exists():
            text = rp.read_text(encoding="utf-8", errors="ignore")
            # Look for .text bytes
            m_text = re.search(r"\.text\s+(\d+)\s*B", text)
            if m_text:
                info.text_bytes = int(m_text.group(1))
            else:
                m_text2 = re.search(r"kernel:\s*~(\d+)\s*B in \.text", text)
                if m_text2:
                    info.text_bytes = int(m_text2.group(1))

            # Look for const words or bytes
            m_const = re.search(r"const_blob:\s*['\"][^'\"]+['\"]\s+(\d+)\s*words", text)
            if m_const:
                info.const_bytes = int(m_const.group(1)) * 4

            # Look for stack or safe-dsp note
            m_stack = re.search(r"(stack\s+ALLOWED|no\s+stack)", text, re.IGNORECASE)
            if m_stack:
                info.stack = m_stack.group(1)
            break

    # Also check effects/<stem_lower>/manifest.json for state_bytes and const
    manifest_path = REPO_ROOT / "effects" / stem.lower() / "manifest.json"
    if manifest_path.exists():
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            if "state_bytes" in m and info.state_bytes is None:
                info.state_bytes = int(m["state_bytes"])
            if "const_blob" in m and info.const_bytes is None:
                cb = m["const_blob"]
                if isinstance(cb, dict) and "words" in cb:
                    info.const_bytes = int(cb["words"]) * 4
        except Exception:
            pass

    return info


def inspect_zd2(path: Union[str, Path]) -> EffectInfo:
    """Inspect a ZD2 file and return detailed metadata and safety status."""
    p = Path(path)
    data = p.read_bytes()
    filename = p.name.upper()
    size = len(data)

    rejections: List[str] = []

    # Check container header (120 bytes)
    if len(data) < 120 or data[:4] != b"ZDLF":
        rejections.append("Not a valid ZD2 file (invalid magic)")
        return EffectInfo(
            path=p,
            filename=filename,
            name="",
            effect_id=0,
            target=0,
            size=size,
            crc_ok=False,
            is_g1_target=False,
            slot_used=0,
            slot_free=0,
            slot_ok=False,
            has_oversize_sibling=False,
            report=EffectReportInfo(),
            valid_for_selection=False,
            rejection_reasons=rejections,
        )

    try:
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from zd2tools.parser import parse_zd2
        patch = parse_zd2(data)
        h = patch.header
        name = h.name
        effect_id = h.effect_id
        target = h.target
        crc_ok = patch.crc_ok
        if not crc_ok:
            rejections.append(f"CRC invalid (file: 0x{h.checksum:08x})")
        is_g1_target = bool(target & 0x02)
        if not is_g1_target:
            rejections.append(f"Target 0x{target:x} lacks G1 Four bit 0x02")
    except Exception as e:
        rejections.append(f"Failed to parse ZD2 container: {e}")
        return EffectInfo(
            path=p,
            filename=filename,
            name="",
            effect_id=0,
            target=0,
            size=size,
            crc_ok=False,
            is_g1_target=False,
            slot_used=0,
            slot_free=0,
            slot_ok=False,
            has_oversize_sibling=False,
            report=EffectReportInfo(),
            valid_for_selection=False,
            rejection_reasons=rejections,
        )

    # Check stock collision
    if filename in STOCK_EFFECT_NAMES:
        rejections.append(f"Filename {filename} collides with stock effect")
    if effect_id in STOCK_EFFECT_IDS:
        rejections.append(f"Effect ID 0x{effect_id:08x} collides with stock effect")

    # Check oversize sibling
    oversize_sibling_1 = p.parent / f"{p.name}.oversize"
    oversize_sibling_2 = p.parent / f"{p.stem}.ZD2.oversize"
    has_oversize_sibling = oversize_sibling_1.exists() or oversize_sibling_2.exists()
    if has_oversize_sibling:
        rejections.append("Oversize marker file (*.oversize) exists")

    # Check slot heap
    slot_used = 0
    slot_free = 0
    slot_ok = False
    try:
        slot_used = calculate_slot_bytes(data)
        slot_free = SLOT_HEAP - slot_used
        slot_ok = (slot_free >= 0)
        if not slot_ok:
            rejections.append(f"Exceeds 40 KiB slot heap ({slot_used} > {SLOT_HEAP} B, {slot_free} free)")
    except Exception as e:
        rejections.append(f"Failed to calculate slot memory: {e}")

    report = parse_report_file(p)

    valid_for_selection = (len(rejections) == 0)

    return EffectInfo(
        path=p,
        filename=filename,
        name=name,
        effect_id=effect_id,
        target=target,
        size=size,
        crc_ok=crc_ok,
        is_g1_target=is_g1_target,
        slot_used=slot_used,
        slot_free=slot_free,
        slot_ok=slot_ok,
        has_oversize_sibling=has_oversize_sibling,
        report=report,
        valid_for_selection=valid_for_selection,
        rejection_reasons=rejections,
    )


def scan_library(build_dir: Optional[Path] = None) -> List[EffectInfo]:
    """Scan build/*.ZD2 and return list of inspected effects."""
    target_dir = Path(build_dir) if build_dir else (REPO_ROOT / "build")
    if not target_dir.exists():
        return []
    effects: List[EffectInfo] = []
    for f in sorted(target_dir.glob("*.ZD2")):
        try:
            effects.append(inspect_zd2(f))
        except Exception as e:
            # If an unreadable or corrupt file is found, still note it
            effects.append(
                EffectInfo(
                    path=f,
                    filename=f.name.upper(),
                    name="",
                    effect_id=0,
                    target=0,
                    size=f.stat().st_size if f.exists() else 0,
                    crc_ok=False,
                    is_g1_target=False,
                    slot_used=0,
                    slot_free=0,
                    slot_ok=False,
                    has_oversize_sibling=False,
                    report=EffectReportInfo(),
                    valid_for_selection=False,
                    rejection_reasons=[f"Unreadable file: {e}"],
                )
            )
    return effects


# ---------------------------------------------------------------------------
# Official Updater Verification
# ---------------------------------------------------------------------------

@dataclass
class UpdaterVerification:
    valid: bool
    path: Path
    size: int
    crc32: str
    message: str


def verify_official_updater(path: Union[str, Path]) -> UpdaterVerification:
    """Verify that path is Zoom's official v2.00 G1X FOUR updater executable."""
    p = Path(path)
    if not p.exists() or not p.is_file():
        return UpdaterVerification(False, p, 0, "", f"File does not exist: {p}")

    size = p.stat().st_size
    crc = crc32_of_file(p)

    try:
        pe = pefile.PE(str(p))
        # Check table
        off = pe.get_offset_from_rva(TABLE_VA - pe.OPTIONAL_HEADER.ImageBase)
        data = p.read_bytes()
        table = [struct.unpack_from("<4I", data, off + 16 * k) for k in range(8)]
        if table != EXPECTED_TABLE:
            return UpdaterVerification(
                False, p, size, crc, "Unexpected stage table: not the official v2.00 G1X FOUR updater"
            )

        # Check resource 0x88 (BIN)
        res_entries = [
            r for t in pe.DIRECTORY_ENTRY_RESOURCE.entries if str(t.name) == "BIN"
            for r in t.directory.entries if r.id == FS_RES
        ]
        if not res_entries:
            return UpdaterVerification(False, p, size, crc, "Missing resource 0x88 (filesystem)")
        fs_size = res_entries[0].directory.entries[0].data.struct.Size
        if fs_size != FS_SIZE:
            return UpdaterVerification(
                False, p, size, crc, f"Resource 0x88 size is {fs_size}, expected {FS_SIZE}"
            )

        return UpdaterVerification(True, p, size, crc, "Official v2.00 G1X FOUR updater verified")
    except Exception as e:
        return UpdaterVerification(False, p, size, crc, f"Failed to parse PE updater: {e}")


# ---------------------------------------------------------------------------
# Pre-flight Checks (§2 Build Image)
# ---------------------------------------------------------------------------

def resolve_effects(selected_effects, add_probe10=False, refresh=False):
    effects = list(selected_effects)
    if add_probe10:
        probe = REPO_ROOT / "build" / "PROBE10.ZD2"
        if not probe.is_file():
            raise PreflightError(f"Selected PROBE10 is missing: {probe}")
        if not any(e.path.resolve() == probe.resolve() for e in effects):
            effects.append(inspect_zd2(probe))
    if refresh:
        effects = [inspect_zd2(e.path) for e in effects]
    return effects


def run_preflight_checks(
    official_updater_path: Optional[Union[str, Path]],
    selected_effects: List[EffectInfo],
    clean: bool = True,
    keep_stock: Tuple[str, ...] = (),
    add_probe10: bool = False,
) -> List[PreflightCheckResult]:
    """Execute the 7 pre-flight checks required before building an image."""
    results: List[PreflightCheckResult] = []
    try:
        selected_effects = resolve_effects(selected_effects, add_probe10)
    except (OSError, PreflightError) as exc:
        results.append(PreflightCheckResult(2, "PROBE10", False, str(exc)))

    # Check 1: Official updater exists and is v2.00 G1X FOUR
    if not official_updater_path:
        results.append(
            PreflightCheckResult(
                1, "Official updater", False, "No official updater selected. Select ZOOM G1X FOUR System v2.00 Updater.exe."
            )
        )
    else:
        v = verify_official_updater(official_updater_path)
        if v.valid:
            results.append(
                PreflightCheckResult(
                    1, "Official updater", True, f"Verified v2.00 G1X FOUR updater ({v.size:,} B, CRC32 {v.crc32})"
                )
            )
        else:
            results.append(PreflightCheckResult(1, "Official updater", False, v.message))

    # Check 2: Every selected .ZD2 passes Library rules
    if not selected_effects:
        results.append(
            PreflightCheckResult(2, "Selected effects", False, "No effects selected from library.")
        )
    else:
        invalid_effects = [e for e in selected_effects if not e.valid_for_selection]
        if invalid_effects:
            reasons = "; ".join(f"{e.filename}: {', '.join(e.rejection_reasons)}" for e in invalid_effects)
            results.append(
                PreflightCheckResult(2, "Selected effects", False, f"Invalid effect(s): {reasons}")
            )
        else:
            results.append(
                PreflightCheckResult(
                    2, "Selected effects", True, f"All {len(selected_effects)} selected effects valid (G1 target, valid CRC)."
                )
            )

    # Check 3: No duplicate ID or filename within selection, no stock collision
    filenames = [e.filename for e in selected_effects]
    ids = [e.effect_id for e in selected_effects]
    dup_names = {n for n in filenames if filenames.count(n) > 1}
    dup_ids = {f"0x{i:08x}" for i in ids if ids.count(i) > 1}
    stock_name_hits = [n for n in filenames if n in STOCK_EFFECT_NAMES]
    stock_id_hits = [f"0x{i:08x}" for i in ids if i in STOCK_EFFECT_IDS]

    problems: List[str] = []
    if dup_names:
        problems.append(f"Duplicate filenames: {', '.join(dup_names)}")
    if dup_ids:
        problems.append(f"Duplicate IDs: {', '.join(dup_ids)}")
    if stock_name_hits:
        problems.append(f"Collides with stock filename: {', '.join(stock_name_hits)}")
    if stock_id_hits:
        problems.append(f"Collides with stock ID: {', '.join(stock_id_hits)}")

    if problems:
        results.append(PreflightCheckResult(3, "Unique IDs & names", False, "; ".join(problems)))
    else:
        results.append(PreflightCheckResult(3, "Unique IDs & names", True, "No duplicate IDs/names and no stock collisions."))

    # Check 4: File count in resulting image (< 127 directory slots; red above 110)
    # Clean mode removes all 78 stock effects, leaving 27 system files + kept + selected
    # Stock mode keeps all 105 files + selected
    base_count = (27 + len(keep_stock)) if clean else (105 + len(selected_effects))
    total_count = base_count + (len(selected_effects) if clean else 0)
    if total_count > 110:
        results.append(
            PreflightCheckResult(
                4,
                "Image file count",
                False,
                f"Resulting image would have {total_count} files (limit: red > 110, hard max 127). "
                f"Directories have 127 slots (DSP_RULES §2). Use --clean or select fewer effects.",
            )
        )
    else:
        results.append(
            PreflightCheckResult(
                4,
                "Image file count",
                True,
                f"Estimated {total_count} files in image (well under directory limit of 127, green <= 110).",
            )
        )

    # Check 5: Slot heap check <= 40 KiB for each effect
    oversize_slots = [e for e in selected_effects if not e.slot_ok]
    if oversize_slots:
        msgs = [f"{e.filename} ({e.slot_used} B uses > {SLOT_HEAP} B)" for e in oversize_slots]
        results.append(
            PreflightCheckResult(
                5, "40 KiB slot heap limit", False, f"Effects exceed 40 KiB slot heap: {', '.join(msgs)}"
            )
        )
    else:
        results.append(
            PreflightCheckResult(5, "40 KiB slot heap limit", True, "All selected effects fit the 40 KiB per-slot heap.")
        )

    # Check 6: Multiple effects reminder
    results.append(
        PreflightCheckResult(
            6,
            "Patch CPU reminder",
            True,
            "Notice: the full patch CPU budget is uncalibrated; measure each kernel with TSCL and verify a loaded multi-effect patch on the pedal.",
        )
    )

    # Check 7: Post-build verification rule
    results.append(
        PreflightCheckResult(
            7,
            "Post-build verification",
            True,
            "Post-build gate active: g1fs.check_image + check_updater_stages.py must all report 'ok'.",
        )
    )

    return results


def all_preflight_passed(checks: List[PreflightCheckResult]) -> bool:
    """Return True if every pre-flight check passed."""
    return bool(checks) and all(c.passed for c in checks)


# ---------------------------------------------------------------------------
# Output Folders & Logging
# ---------------------------------------------------------------------------

def create_output_folder(prefix: str = "loader_", base_dir: Optional[Path] = None) -> Path:
    """Create a unique timestamped output folder under build/loader/.

    Guaranteed never to overwrite an existing folder (appends _1, _2 if needed).
    """
    root = Path(base_dir) if base_dir else LOADER_DIR
    root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    folder = root / f"{prefix}{stamp}"
    idx = 1
    while folder.exists():
        folder = root / f"{prefix}{stamp}_{idx}"
        idx += 1
    folder.mkdir(parents=True, exist_ok=False)
    return folder


def append_to_loader_log(line: str) -> None:
    """Append a line to build/loader/loader.log."""
    LOADER_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOADER_DIR / "loader.log"
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {line}\n")


# ---------------------------------------------------------------------------
# Subprocess Runner (Streaming, Timeout, Cancel, Log)
# ---------------------------------------------------------------------------

def run_tool(
    cmd: List[str],
    cwd: Optional[Path] = None,
    on_output: Optional[Callable[[str], None]] = None,
    timeout: float = 300.0,
    is_cancelled: Optional[Callable[[], bool]] = None,
) -> ToolExecutionResult:
    """Run a tool as a subprocess.

    Safety requirements:
    - No shell=True.
    - cmd[0] must be python/python.exe, NEVER an updater executable.
    - Streams output lines to on_output.
    - Logs to build/loader/loader.log.
    """
    if not cmd:
        raise ValueError("Empty command list")

    if Path(cmd[0]).resolve() not in {get_python_exe().resolve(), Path(sys.executable).resolve()}:
        raise ValueError(f"Safety violation: only the configured Python interpreter may be executed: {cmd[0]}")

    working_dir = cwd or REPO_ROOT
    append_to_loader_log(f"EXEC: {subprocess.list2cmdline([str(c) for c in cmd])}")
    start_time = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=str(working_dir), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, errors="replace", bufsize=1)
    output = queue.Queue()

    # Windows pipe reads cannot be polled with select(). Keep blocking reads
    # in a reader thread; the controlling thread always checks the deadline.
    def read_output():
        try:
            for line in proc.stdout:
                output.put(line.rstrip("\r\n"))
        finally:
            output.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    lines = []
    failure = None
    eof = False
    try:
        while not eof or proc.poll() is None:
            if failure is None:
                if is_cancelled and is_cancelled():
                    failure = "Execution cancelled by user"
                elif time.monotonic() - start_time >= timeout:
                    failure = f"Command timed out after {timeout} seconds"
                if failure:
                    append_to_loader_log(failure)
                    if proc.poll() is None:
                        proc.kill()
            try:
                line = output.get(timeout=0.02)
            except queue.Empty:
                continue
            if line is None:
                eof = True
            else:
                lines.append(line)
                append_to_loader_log(f"OUT: {line}")
                if on_output:
                    on_output(line)
    finally:
        if proc.poll() is None:
            proc.kill()
        exit_code = proc.wait()
        reader.join()
        proc.stdout.close()
        duration = time.monotonic() - start_time
        append_to_loader_log(f"EXIT: {exit_code} (took {duration:.2f}s)")
    if failure:
        raise TimeoutError(failure)

    return ToolExecutionResult(
        command=cmd,
        exit_code=exit_code,
        stdout="\n".join(lines),
        stderr="",
        duration_sec=duration,
    )


# ---------------------------------------------------------------------------
# Status and Config Storage
# ---------------------------------------------------------------------------

def get_config_path() -> Path:
    return LOADER_DIR / "config.json"


def get_status_path() -> Path:
    return LOADER_DIR / "status.json"


def load_config() -> dict:
    """Load configuration from build/loader/config.json."""
    cp = get_config_path()
    if cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_config(data: dict) -> None:
    """Save configuration to build/loader/config.json."""
    LOADER_DIR.mkdir(parents=True, exist_ok=True)
    get_config_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_status() -> dict:
    """Load effect status dictionary from build/loader/status.json."""
    sp = get_status_path()
    if sp.exists():
        try:
            return json.loads(sp.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_status(data: dict) -> None:
    """Save effect status dictionary to build/loader/status.json."""
    LOADER_DIR.mkdir(parents=True, exist_ok=True)
    get_status_path().write_text(json.dumps(data, indent=2), encoding="utf-8")


def update_effect_stage(
    filename: str,
    new_stage: str,
    notes: str = "",
    measured_cost: Optional[int] = None,
) -> dict:
    """Update status for an effect under the safety gating rules.

    The old audio + Probe 10 cost gate is insufficient for "ok-save".
    Approval remains closed until direct timing and artifact identity are
    represented in this status model.
    """
    if new_stage not in VALID_STAGES:
        raise ValueError(f"Invalid stage '{new_stage}'. Must be one of: {VALID_STAGES}")

    status_data = load_status()
    entry = status_data.get(
        filename.upper(),
        {
            "stage": "built",
            "audio_passed": False,
            "cost_measured": False,
            "measured_cost": None,
            "history": [],
            "notes": "",
        },
    )

    if new_stage in ("built", "in image"):
        entry.update(audio_passed=False, cost_measured=False, measured_cost=None)
    if new_stage == "audio-pass":
        entry["audio_passed"] = True
    elif new_stage == "cost-measured":
        if measured_cost is None or not math.isfinite(measured_cost) or not 0 <= measured_cost <= 96000:
            raise ValueError("A finite measured cost between 0 and 96000 is required")
        entry["cost_measured"] = True
        if measured_cost is not None:
            entry["measured_cost"] = measured_cost
    elif new_stage == "ok-save":
        raise ValueError(
            "Safety gate blocked: CPU budget and exact-artifact timing approval are not calibrated"
        )

    entry["stage"] = new_stage
    entry["notes"] = notes
    entry["history"].append(
        {
            "stage": new_stage,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "notes": notes,
        }
    )

    status_data[filename.upper()] = entry
    save_status(status_data)
    return entry


def calculate_probe10_cost(freeze_load: float) -> int:
    """Reject the withdrawn Probe 10 freeze-load-to-cycles inference."""
    raise ValueError("Probe 10 freeze load is not a calibrated CPU cost; use a TSCL measurement")


# ---------------------------------------------------------------------------
# Image & Patched Updater Workflow (§2 Build Image)
# ---------------------------------------------------------------------------

def build_image_and_updater(
    official_updater_path: Union[str, Path],
    selected_effects: List[EffectInfo],
    clean: bool = True,
    keep_stock: Tuple[str, ...] = (),
    add_probe10: bool = False,
    empty_patches: bool = False,
    splash_png: Optional[Union[str, Path]] = None,
    factory_image_path: Optional[Union[str, Path]] = None,
    on_output: Optional[Callable[[str], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    base_output_dir: Optional[Path] = None,
) -> Path:
    """Execute the full safe build pipeline.

    Steps:
    1. Run pre-flight checks. If any red -> refuse (PreflightError).
    2. Create fresh timestamped output folder under build/loader/.
    3. Run tools/make_g1_image.py to build 3 MB file-system image.
    4. Run tools/make_fs_restore_updater.py to build patched updater .exe.
    5. Run tools/check_updater_stages.py to verify updater stages.
    6. Write comprehensive report.txt.
    7. Any failure writes FAILED marker.
    """
    # Re-read inputs so a stale Library scan cannot authorize changed files.
    selected_effects = resolve_effects(selected_effects, add_probe10, refresh=True)
    # 1. Pre-flight checks
    checks = run_preflight_checks(
        official_updater_path, selected_effects, clean=clean, keep_stock=keep_stock
    )
    if not all_preflight_passed(checks):
        failed_msgs = [f"Check {c.check_num} ({c.title}): {c.message}" for c in checks if not c.passed]
        raise PreflightError("Pre-flight checks failed:\n" + "\n".join(failed_msgs))

    # Determine factory image
    factory_img = factory_image_path or (REPO_ROOT / "build" / "fw" / "res3_3137536.bin")
    if not Path(factory_img).exists():
        raise FileNotFoundError(f"Factory filesystem image not found at {factory_img}")

    # Determine effects list to include
    effect_paths: List[Path] = [e.path for e in selected_effects]
    # 2. Output folder
    out_dir = create_output_folder("image_", base_dir=base_output_dir)
    img_out = out_dir / "cf_g1_image.bin"
    updater_out = out_dir / "ZOOM G1X FOUR Patched Updater.exe"
    report_file = out_dir / "report.txt"
    failed_marker = out_dir / "FAILED"

    py = str(get_python_exe())
    report_lines = ["CF Loader Build Report"]
    try:
        report_lines: List[str] = [
            "CF Loader Build Report",
            f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Official updater: {official_updater_path} ({Path(official_updater_path).stat().st_size} B, CRC32: {crc32_of_file(official_updater_path)})",
            f"Factory image: {factory_img} (CRC32: {crc32_of_file(factory_img)})",
            f"Clean mode: {clean}",
            f"Kept stock: {', '.join(keep_stock) if keep_stock else 'none'}",
            f"Add PROBE10: {add_probe10}",
            f"Empty patches: {empty_patches}",
            f"Splash PNG: {splash_png or 'none'}",
            "Selected effects:",
        ]
        for ep in effect_paths:
            report_lines.append(f"  - {ep.name} ({ep.stat().st_size} B, CRC32: {crc32_of_file(ep)})")

        report_lines.append("\nPre-flight check results:")
        for c in checks:
            report_lines.append(f"  [{'PASS' if c.passed else 'FAIL'}] Check {c.check_num} - {c.title}: {c.message}")
        report_lines.append("\nTool Execution:")

        # Step 1: tools/make_g1_image.py
        cmd1 = [py, str(REPO_ROOT / "tools" / "make_g1_image.py")]
        if clean:
            cmd1.append("--clean")
            for k in keep_stock:
                cmd1.extend(["--keep", k])
        cmd1.extend([str(factory_img), str(img_out)])
        for ep in effect_paths:
            cmd1.append(str(ep))

        if on_output:
            on_output(f"> Building filesystem image: {' '.join(cmd1)}")
        report_lines.append("EXEC: " + subprocess.list2cmdline(cmd1))
        res1 = run_tool(cmd1, on_output=on_output, is_cancelled=is_cancelled)
        report_lines.append(f"\n1. make_g1_image.py exit code: {res1.exit_code}")
        report_lines.append(res1.stdout)
        if res1.exit_code != 0:
            raise RuntimeError(f"make_g1_image.py failed with exit code {res1.exit_code}")

        # Step 2: tools/make_fs_restore_updater.py --image <img_out>
        cmd2 = [
            py,
            str(REPO_ROOT / "tools" / "make_fs_restore_updater.py"),
            str(official_updater_path),
            str(updater_out),
            "--image",
            str(img_out),
        ]
        if splash_png:
            cmd2.extend(["--splash", str(splash_png)])
        if empty_patches:
            # --presets needs the whole 0xB000 resource, not a 760-byte ZPTC.
            presets_source = REPO_ROOT / "build" / "fw" / "res2_45056.bin"
            if not presets_source.is_file():
                raise FileNotFoundError(f"Factory presets resource missing: {presets_source}")
            blank_bin = out_dir / "empty_presets.bin"
            blank_cmd = [py, str(REPO_ROOT / "tools" / "g1presets.py"), "blank",
                         str(presets_source), str(blank_bin)]
            report_lines.append(f"Presets source CRC32: {crc32_of_file(presets_source)}")
            report_lines.append("EXEC: " + subprocess.list2cmdline(blank_cmd))
            blank_result = run_tool(blank_cmd, on_output=on_output, is_cancelled=is_cancelled)
            report_lines.append(f"g1presets.py exit code: {blank_result.exit_code}\n{blank_result.stdout}")
            if blank_result.exit_code != 0:
                raise RuntimeError("g1presets.py failed")
            cmd2.extend(["--presets", str(blank_bin)])

        if on_output:
            on_output(f"> Patching updater: {' '.join(cmd2)}")
        report_lines.append("EXEC: " + subprocess.list2cmdline(cmd2))
        res2 = run_tool(cmd2, on_output=on_output, is_cancelled=is_cancelled)
        report_lines.append(f"\n2. make_fs_restore_updater.py exit code: {res2.exit_code}")
        report_lines.append(res2.stdout)
        if res2.exit_code != 0:
            raise RuntimeError(f"make_fs_restore_updater.py failed with exit code {res2.exit_code}")

        # Step 3: tools/check_updater_stages.py <updater_out>
        cmd3 = [py, str(REPO_ROOT / "tools" / "check_updater_stages.py"), str(updater_out)]
        if on_output:
            on_output(f"> Checking updater stages: {' '.join(cmd3)}")
        report_lines.append("EXEC: " + subprocess.list2cmdline(cmd3))
        res3 = run_tool(cmd3, on_output=on_output, is_cancelled=is_cancelled)
        report_lines.append(f"\n3. check_updater_stages.py exit code: {res3.exit_code}")
        report_lines.append(res3.stdout)
        if not stages_verified(res3):
            raise RuntimeError(f"check_updater_stages.py failed or refused stages in {updater_out}")

        report_lines.append("\nSTATUS: SUCCESS")
        report_file.write_text("\n".join(report_lines), encoding="utf-8")

        # Update status for each selected effect to 'in image'
        for ep in effect_paths:
            try:
                update_effect_stage(ep.name, "in image", notes=f"Included in {out_dir.name}")
            except Exception:
                pass

        if on_output:
            on_output(f"\nSUCCESS: Output generated at {out_dir}")
        return out_dir

    except Exception as e:
        failed_marker.write_text(f"Build failed: {e}\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}", encoding="utf-8")
        report_lines.append(f"\nSTATUS: FAILED ({e})")
        report_file.write_text("\n".join(report_lines), encoding="utf-8")
        if on_output:
            on_output(f"\nERROR: Build failed: {e}")
        raise


def stages_verified(result):
    stages = [line.strip() for line in result.stdout.splitlines()
              if line.strip().startswith(("erase ", "write "))]
    required = {
        "erase 0x102000 size 0x2fe000",
        "write 0x102000 resource 0x88",
    }
    passed = {line.rsplit(" ok", 1)[0].rstrip() for line in stages
              if line.endswith(" ok")}
    return (result.exit_code == 0 and len(passed) == len(stages)
            and required <= passed)


def build_factory_restore_updater(
    official_updater_path: Union[str, Path],
    on_output: Optional[Callable[[str], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    base_output_dir: Optional[Path] = None,
) -> Path:
    """Build the clean factory restore updater (Recovery tab).

    Invokes tools/make_fs_restore_updater.py without --image and verifies stages.
    """
    v = verify_official_updater(official_updater_path)
    if not v.valid:
        raise ValueError(f"Official updater invalid: {v.message}")

    out_dir = create_output_folder("recovery_", base_dir=base_output_dir)
    updater_out = out_dir / "ZOOM G1X FOUR Factory Restore Updater.exe"
    report_file = out_dir / "report.txt"
    failed_marker = out_dir / "FAILED"

    py = str(get_python_exe())
    report_lines = [
        "CF Loader Recovery Build Report",
        f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Official updater: {official_updater_path} ({v.size} B, CRC32: {v.crc32})",
        "Mode: Factory Restore (no --image)",
    ]

    try:
        # Step 1: make_fs_restore_updater.py without --image
        cmd1 = [
            py,
            str(REPO_ROOT / "tools" / "make_fs_restore_updater.py"),
            str(official_updater_path),
            str(updater_out),
        ]
        if on_output:
            on_output(f"> Building factory restore updater: {' '.join(cmd1)}")
        report_lines.append("EXEC: " + subprocess.list2cmdline(cmd1))
        res1 = run_tool(cmd1, on_output=on_output, is_cancelled=is_cancelled)
        report_lines.append(f"\n1. make_fs_restore_updater.py exit code: {res1.exit_code}")
        report_lines.append(res1.stdout)
        if res1.exit_code != 0:
            raise RuntimeError(f"make_fs_restore_updater.py failed with exit code {res1.exit_code}")

        # Step 2: check_updater_stages.py
        cmd2 = [py, str(REPO_ROOT / "tools" / "check_updater_stages.py"), str(updater_out)]
        if on_output:
            on_output(f"> Checking updater stages: {' '.join(cmd2)}")
        report_lines.append("EXEC: " + subprocess.list2cmdline(cmd2))
        res2 = run_tool(cmd2, on_output=on_output, is_cancelled=is_cancelled)
        report_lines.append(f"\n2. check_updater_stages.py exit code: {res2.exit_code}")
        report_lines.append(res2.stdout)
        if not stages_verified(res2):
            raise RuntimeError("check_updater_stages.py failed or refused stages")

        report_lines.append("\nSTATUS: SUCCESS")
        report_file.write_text("\n".join(report_lines), encoding="utf-8")
        if on_output:
            on_output(f"\nSUCCESS: Factory restore updater built at {updater_out}")
        return out_dir

    except Exception as e:
        failed_marker.write_text(f"Recovery build failed: {e}\n", encoding="utf-8")
        report_lines.append(f"\nSTATUS: FAILED ({e})")
        report_file.write_text("\n".join(report_lines), encoding="utf-8")
        raise


# ===========================================================================
# Comet Flower Installer Integration & Re-exports
# ===========================================================================
from tools.cf_loader.backups import (
    BackupInfo,
    scan_backups,
    delete_backup,
    create_backup_destination,
    build_backup_commands,
)
from tools.cf_loader.catalog import (
    UnifiedEffect,
    load_stock_catalog,
    scan_cf_effects,
    assemble_unified_catalog,
    calculate_filesystem_usage,
    FS_TOTAL_BYTES,
    FS_TOTAL_DATA_BLOCKS,
    FS_MAX_DIR_SLOTS,
)
from tools.cf_loader.patches import (
    PatchSlot,
    PatchRecord,
    decode_patch_bytes,
    make_blank_patch,
    scan_backup_patches,
    build_presets_command,
    build_id_name_map,
    write_patch_live,
)
from tools.cf_loader.profiles import (
    Profile,
    load_profiles,
    save_profile,
    save_profiles,
    delete_profile,
    rename_profile,
    set_default_profile,
    get_default_profile,
    get_default_fallback_profile,
)
from tools.cf_loader.build_engine import (
    parse_next_version,
    find_default_firmware_bin,
    find_default_official_updater,
    calculate_sha256,
    append_installer_log,
    build_make_g1_image_cmd,
    build_make_splash_cmd,
    build_make_fs_restore_updater_cmd,
    parse_updater_stages,
    INSTALLER_LOG_PATH,
)


def execute_cf_installer_build(
    official_updater_path: Union[str, Path],
    firmware_bin_path: Union[str, Path],
    selected_stock_effects: List[str],
    selected_cf_effects: List[Union[str, Path, UnifiedEffect]],
    version: str,
    presets_bin_path: Optional[Union[str, Path]] = None,
    patch_records: Optional[List[PatchRecord]] = None,
    do_backup: bool = True,
    factory_image_path: Optional[Union[str, Path]] = None,
    on_output: Optional[Callable[[str], None]] = None,
    is_cancelled: Optional[Callable[[], bool]] = None,
    base_output_dir: Optional[Path] = None,
) -> Dict[str, Union[Path, str, List[str]]]:
    """Execute the complete Comet Flower Installer build recipe.

    Steps:
    1. (Optional) Run pedal backup if requested.
    2. Build 3 MB filesystem image with make_g1_image.py (--clean, --keep for stock, CF files).
    3. Build splash screen PNG with make_splash.py.
    4. Build or locate presets 0xB000 region.
    5. Build installer .exe with make_fs_restore_updater.py.
    6. Check updater stages with check_updater_stages.py.
    7. Calculate SHA-256 and stages summary.
    8. Append to build/installer_log.json.
    """
    v = verify_official_updater(official_updater_path)
    if not v.valid:
        raise ValueError(f"Official updater invalid: {v.message}")

    fw_path = Path(firmware_bin_path).resolve()
    if not fw_path.exists():
        raise FileNotFoundError(f"Firmware binary not found at {fw_path}")

    # Determine factory image
    factory_img = Path(factory_image_path or (REPO_ROOT / "build" / "fw" / "res3_3137536.bin")).resolve()
    if not factory_img.exists():
        raise FileNotFoundError(f"Factory filesystem image not found at {factory_img}")

    # Extract CF paths
    cf_paths: List[Path] = []
    cf_unified: List[UnifiedEffect] = []
    for item in selected_cf_effects:
        if isinstance(item, UnifiedEffect):
            cf_unified.append(item)
            if item.path and Path(item.path).exists():
                cf_paths.append(Path(item.path).resolve())
        elif isinstance(item, (str, Path)):
            p = Path(item).resolve()
            if p.exists():
                cf_paths.append(p)

    # Pre-flight check on filesystem space
    stock_catalog = load_stock_catalog(factory_img)
    checked_stock_unified = [stock_catalog[k.upper()] for k in selected_stock_effects if k.upper() in stock_catalog]
    all_checked_unified = checked_stock_unified + cf_unified
    total_bytes, total_blocks, free_blocks, fits, msg = calculate_filesystem_usage(all_checked_unified, factory_img)
    if not fits:
        raise ValueError(f"Filesystem space check failed: {msg}")

    # Create timestamped build output directory
    out_dir = create_output_folder("cf_build_", base_dir=base_output_dir)
    report_file = out_dir / "report.txt"
    failed_marker = out_dir / "FAILED"
    py = str(get_python_exe())
    report_lines: List[str] = [
        "Comet Flower Installer Build Report",
        f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Version: {version}",
        f"Official updater: {official_updater_path} ({v.size} B, CRC32: {v.crc32})",
        f"Firmware: {fw_path} ({fw_path.stat().st_size} B, SHA256: {calculate_sha256(fw_path)[:8]})",
        f"Factory image: {factory_img}",
        f"Stock kept ({len(selected_stock_effects)}): {', '.join(selected_stock_effects)}",
        f"CF effects added ({len(cf_paths)}): {', '.join(p.name for p in cf_paths)}",
        f"Filesystem usage: {total_bytes:,} / {FS_TOTAL_BYTES:,} bytes ({free_blocks} blocks free)",
        "",
        "Tool Execution:",
    ]

    try:
        # Step 0: Backup pedal if requested
        if do_backup:
            if on_output:
                on_output("> Step 0: Backing up pedal prior to build...")
            backup_dest = create_backup_destination()
            cmds = build_backup_commands(backup_dest, python_exe=Path(py))
            for bcmd in cmds:
                if on_output:
                    on_output(f"  EXEC: {' '.join(bcmd)}")
                report_lines.append("EXEC: " + subprocess.list2cmdline(bcmd))
                res = run_tool(bcmd, on_output=on_output, is_cancelled=is_cancelled)
                report_lines.append(f"Backup exit code: {res.exit_code}\n{res.stdout}")
                # We do not fail the build if pedal is disconnected/offline
                if res.exit_code != 0:
                    if on_output:
                        on_output("  Notice: Pedal not connected or backup skipped; continuing build.")

        # Step 1: tools/make_g1_image.py
        fs_img_out = out_dir / "cf_g1_image.bin"
        cmd_img = build_make_g1_image_cmd(
            factory_img=factory_img,
            out_img=fs_img_out,
            keep_stock=selected_stock_effects,
            cf_effect_paths=cf_paths,
            clean=True,
            python_exe=Path(py),
        )
        if on_output:
            on_output(f"\n> Step 1: Building filesystem image: {' '.join(cmd_img)}")
        report_lines.append("EXEC: " + subprocess.list2cmdline(cmd_img))
        res_img = run_tool(cmd_img, on_output=on_output, is_cancelled=is_cancelled)
        report_lines.append(f"make_g1_image.py exit code: {res_img.exit_code}\n{res_img.stdout}")
        if res_img.exit_code != 0:
            raise RuntimeError(f"make_g1_image.py failed with exit code {res_img.exit_code}")

        # Step 2: tools/make_splash.py
        splash_png_out = out_dir / "splash.png"
        cmd_splash = build_make_splash_cmd(
            version=version,
            out_png=splash_png_out,
            title="CF-ZGX4",
            tag="TEST",
            python_exe=Path(py),
        )
        if on_output:
            on_output(f"\n> Step 2: Generating start-up screen: {' '.join(cmd_splash)}")
        report_lines.append("EXEC: " + subprocess.list2cmdline(cmd_splash))
        res_splash = run_tool(cmd_splash, on_output=on_output, is_cancelled=is_cancelled)
        report_lines.append(f"make_splash.py exit code: {res_splash.exit_code}\n{res_splash.stdout}")
        if res_splash.exit_code != 0:
            raise RuntimeError(f"make_splash.py failed with exit code {res_splash.exit_code}")

        # Step 3: Presets binary
        presets_target: Optional[Path] = None
        if presets_bin_path and Path(presets_bin_path).exists():
            presets_target = Path(presets_bin_path).resolve()
        elif patch_records:
            # g1presets.py can only blank and rename (no .ZPTC composition yet): a "default set"
            # built from names alone would be 50 empty patches wearing the owner's names. Keep the
            # CF presets until the composer exists (docs/helpers/GEMINI_INSTALLER_2026-10-23.md 5).
            if on_output:
                on_output("\n> Step 3: default patch set not supported yet (g1presets.py cannot compose "
                          "patches); keeping the CF factory presets.")
            report_lines.append("Presets: default patch set skipped (no composer); CF presets kept")
        if not presets_target or not presets_target.exists():
            # Fallback to CF presets or factory presets
            cf_presets = REPO_ROOT / "build" / "fw" / "cfupd_res85.bin"
            if cf_presets.exists():
                presets_target = cf_presets

        # Step 4: tools/make_fs_restore_updater.py
        safe_name = f"Comet Flower ZG1X4 {version} TEST.exe"
        exe_out = out_dir / safe_name
        cmd_updater = build_make_fs_restore_updater_cmd(
            official_updater=Path(official_updater_path).resolve(),
            out_exe=exe_out,
            test_controller_fw=fw_path,
            fs_image=fs_img_out,
            presets_bin=presets_target,
            splash_png=splash_png_out,
            python_exe=Path(py),
        )
        if on_output:
            on_output(f"\n> Step 4: Packaging installer .exe: {' '.join(cmd_updater)}")
        report_lines.append("EXEC: " + subprocess.list2cmdline(cmd_updater))
        res_updater = run_tool(cmd_updater, on_output=on_output, is_cancelled=is_cancelled)
        report_lines.append(f"make_fs_restore_updater.py exit code: {res_updater.exit_code}\n{res_updater.stdout}")
        if res_updater.exit_code != 0:
            raise RuntimeError(f"make_fs_restore_updater.py failed with exit code {res_updater.exit_code}")

        # Step 5: tools/check_updater_stages.py
        cmd_check = [py, str(REPO_ROOT / "tools" / "check_updater_stages.py"), str(exe_out)]
        if on_output:
            on_output(f"\n> Step 5: Checking updater stages: {' '.join(cmd_check)}")
        report_lines.append("EXEC: " + subprocess.list2cmdline(cmd_check))
        res_check = run_tool(cmd_check, on_output=on_output, is_cancelled=is_cancelled)
        report_lines.append(f"check_updater_stages.py exit code: {res_check.exit_code}\n{res_check.stdout}")
        if not stages_verified(res_check):
            raise RuntimeError("check_updater_stages.py failed or refused stages")

        # Step 6: Hash & Summary
        sha256_full = calculate_sha256(exe_out)
        sha256_short = sha256_full[:8]
        stages = parse_updater_stages(res_updater.stdout)

        report_lines.append(f"\nOUTPUT EXECUTABLE: {exe_out.name}")
        report_lines.append(f"SHA-256: {sha256_full} (short: {sha256_short})")
        report_lines.append("STAGES:")
        for st in stages:
            report_lines.append(f"  {st}")
        report_lines.append("\nSTATUS: SUCCESS")
        report_file.write_text("\n".join(report_lines), encoding="utf-8")

        # Step 7: Append to build/installer_log.json
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "version": version,
            "output_exe": str(exe_out),
            "sha256": sha256_full,
            "sha256_short": sha256_short,
            "firmware": str(fw_path.name),
            "fs_image": str(fs_img_out.name),
            "presets": str(presets_target.name) if presets_target else "none",
            "splash": str(splash_png_out.name),
            "stages": stages,
            "effects_count": len(selected_stock_effects) + len(cf_paths),
        }
        append_installer_log(log_entry, log_path=INSTALLER_LOG_PATH)

        if on_output:
            on_output(f"\nSUCCESS: Comet Flower Installer successfully built!")
            on_output(f"File: {exe_out}")
            on_output(f"SHA-256: {sha256_full}")
            on_output("\nStages written:")
            for st in stages:
                on_output(f"  {st}")
            on_output("\n[IMPORTANT INSTRUCTIONS]")
            on_output("Never flash automatically over MIDI. To update your pedal:")
            on_output("1. Disconnect USB / power down the Zoom G1X Four.")
            on_output("2. Hold down BOTH footswitches and plug in the USB cable (UPDATE MODE).")
            on_output(f"3. Run '{exe_out.name}' on your PC and click Execute.")

        return {
            "out_dir": out_dir,
            "exe_path": exe_out,
            "sha256": sha256_full,
            "sha256_short": sha256_short,
            "stages": stages,
            "version": version,
        }

    except Exception as e:
        failed_marker.write_text(f"Installer build failed: {e}\n", encoding="utf-8")
        report_lines.append(f"\nSTATUS: FAILED ({e})")
        report_file.write_text("\n".join(report_lines), encoding="utf-8")
        if on_output:
            on_output(f"\nERROR: Installer build failed: {e}")
        raise
