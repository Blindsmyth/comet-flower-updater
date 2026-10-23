"""Unified effects catalog for Zoom G1X Four stock and Comet Flower effects."""

from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FACTORY_IMG_DEFAULT = REPO_ROOT / "build" / "fw" / "res3_3137536.bin"

FS_TOTAL_BYTES = 0x2FE000  # 3,137,536 bytes
FS_BLOCK_SIZE = 4096
FS_PAYLOAD_SIZE = 4090
FS_TOTAL_DATA_BLOCKS = 756
FS_MAX_DIR_SLOTS = 127

GROUP_NAMES = {
    1: "DYN",
    2: "FLTR",
    3: "DRV",
    4: "AMP",
    5: "CAB",
    6: "MOD",
    7: "SFX",
    8: "DLY",
    9: "REV",
    10: "PEDAL",
}


@dataclass
class UnifiedEffect:
    filename: str              # e.g. "COMP.ZD2", "RATX.ZD2"
    name: str                  # e.g. "Comp", "CF RAT"
    group: str                 # e.g. "DYN", "DRV", "DLY", "MOD", "SFX"
    group_id: int              # 1..10
    source: str                # "Zoom" or "CF"
    dspload: float             # declared dspload
    size_bytes: int            # raw file size in bytes
    effect_id: int             # e.g. 0x01000010
    path: Optional[Path] = None  # file path on disk (if available)
    on_pedal: bool = False     # present in selected backup
    is_checked: bool = True    # selected for installation
    is_valid: bool = True      # passed preflight/container check
    blocks_required: int = 1   # blocks taken on filesystem

    def __post_init__(self):
        if self.size_bytes > 0:
            self.blocks_required = max(1, math.ceil(self.size_bytes / FS_PAYLOAD_SIZE))


# Cache to avoid re-parsing factory image unnecessarily
_STOCK_CATALOG_CACHE: Optional[Dict[str, UnifiedEffect]] = None


def load_stock_catalog(factory_img_path: Optional[Path] = None) -> Dict[str, UnifiedEffect]:
    """Parse stock effects from factory filesystem image (res3_3137536.bin)."""
    global _STOCK_CATALOG_CACHE
    if _STOCK_CATALOG_CACHE is not None and (factory_img_path is None or factory_img_path == FACTORY_IMG_DEFAULT):
        return dict(_STOCK_CATALOG_CACHE)

    img_path = factory_img_path or FACTORY_IMG_DEFAULT
    catalog: Dict[str, UnifiedEffect] = {}

    if not img_path.exists():
        # Fallback to minimal stock list if factory image is missing
        from tools.cf_loader.core import STOCK_EFFECTS
        for fn, eid in STOCK_EFFECTS.items():
            gid = (eid >> 24) & 0xFF
            gname = GROUP_NAMES.get(gid, "FX")
            catalog[fn.upper()] = UnifiedEffect(
                filename=fn.upper(),
                name=fn.replace(".ZD2", "").replace("_", " ").title(),
                group=gname,
                group_id=gid,
                source="Zoom",
                dspload=30.0,
                size_bytes=24000,
                effect_id=eid,
                path=None,
                on_pedal=False,
                is_checked=True,
                is_valid=True,
            )
        return catalog

    try:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
        sys.path.insert(0, str(REPO_ROOT / "src"))
        import g1fs
        from zd2tools.parser import parse_zd2

        img = img_path.read_bytes()
        _, _, ents = g1fs.current_dir(img)
        files = {n: g1fs.read_file(img, f, s) for n, f, s, _, _ in ents}

        for fname, data in files.items():
            if fname.upper().endswith(".ZD2"):
                try:
                    patch = parse_zd2(data)
                    h = patch.header
                    gid = h.group_id
                    gname = GROUP_NAMES.get(gid, "FX")
                    dspload = getattr(patch.info, "dspload", 30.0) if hasattr(patch, "info") else 30.0
                    catalog[fname.upper()] = UnifiedEffect(
                        filename=fname.upper(),
                        name=h.name.strip() or fname.replace(".ZD2", ""),
                        group=gname,
                        group_id=gid,
                        source="Zoom",
                        dspload=float(dspload),
                        size_bytes=len(data),
                        effect_id=h.effect_id,
                        path=None,
                        on_pedal=False,
                        is_checked=True,
                        is_valid=True,
                    )
                except Exception:
                    catalog[fname.upper()] = UnifiedEffect(
                        filename=fname.upper(),
                        name=fname.replace(".ZD2", ""),
                        group="FX",
                        group_id=1,
                        source="Zoom",
                        dspload=30.0,
                        size_bytes=len(data),
                        effect_id=0,
                        path=None,
                        on_pedal=False,
                        is_checked=True,
                        is_valid=True,
                    )

        if factory_img_path is None or factory_img_path == FACTORY_IMG_DEFAULT:
            _STOCK_CATALOG_CACHE = catalog

    except Exception:
        pass

    return catalog


def find_newest_bench_image() -> Optional[Path]:
    """Find newest fs_bench*.bin under build/fw_rnd*."""
    candidates: List[Path] = []
    for fw_dir in REPO_ROOT.glob("build/fw_rnd*"):
        if fw_dir.is_dir():
            for f in fw_dir.glob("fs_bench*.bin"):
                if f.is_file():
                    candidates.append(f)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0]


def newest_image_effects(bench_img_path: Optional[Path] = None) -> Set[str]:
    """Upper-case .ZD2 names in the newest bench image (empty set if none or unreadable)."""
    img_path = bench_img_path or find_newest_bench_image()
    if not img_path or not img_path.exists():
        return set()
    try:
        sys.path.insert(0, str(REPO_ROOT / "tools"))
        import g1fs
        _, _, ents = g1fs.current_dir(img_path.read_bytes())
        return {n.upper() for n, _, _, _, _ in ents if n.upper().endswith(".ZD2")}
    except Exception:
        return set()


def scan_cf_effects(
    build_dir: Optional[Path] = None,
    bench_img_path: Optional[Path] = None,
) -> Dict[str, UnifiedEffect]:
    """Scan build/*.ZD2 and the newest fs_bench*.bin image for CF effects."""
    from tools.cf_loader.core import inspect_zd2, STOCK_EFFECT_NAMES
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from zd2tools.parser import parse_zd2

    bdir = build_dir or (REPO_ROOT / "build")
    cf_catalog: Dict[str, UnifiedEffect] = {}

    # 1. Scan build/*.ZD2
    if bdir.exists():
        for p in sorted(bdir.glob("*.ZD2")):
            fn = p.name.upper()
            if fn in STOCK_EFFECT_NAMES or "_BEFORE_" in fn:
                continue
            try:
                info = inspect_zd2(p)
                # Parse dspload and group
                patch = parse_zd2(p.read_bytes())
                gid = patch.header.group_id
                gname = GROUP_NAMES.get(gid, "CF")
                dspload = float(getattr(patch.info, "dspload", 30.0))
                cf_catalog[fn] = UnifiedEffect(
                    filename=fn,
                    name=info.name or patch.header.name or p.stem,
                    group=gname,
                    group_id=gid,
                    source="CF",
                    dspload=dspload,
                    size_bytes=info.size,
                    effect_id=info.effect_id,
                    path=p,
                    on_pedal=False,
                    is_checked=info.valid_for_selection,
                    is_valid=info.valid_for_selection,
                )
            except Exception:
                pass

    # 2. Scan newest fs_bench*.bin for any additional or newer CF effects
    bench_img = bench_img_path or find_newest_bench_image()
    if bench_img and bench_img.exists():
        try:
            sys.path.insert(0, str(REPO_ROOT / "tools"))
            import g1fs
            img = bench_img.read_bytes()
            _, _, ents = g1fs.current_dir(img)
            files = {n: g1fs.read_file(img, f, s) for n, f, s, _, _ in ents}

            for fname, data in files.items():
                fn = fname.upper()
                # The newest bench image holds the versions on the pedal (e.g. the re-declared
                # dsploads of 0.34.3); they replace older copies of the same file in build/.
                if fn.endswith(".ZD2") and fn not in STOCK_EFFECT_NAMES:
                    try:
                        patch = parse_zd2(data)
                        h = patch.header
                        gid = h.group_id
                        gname = GROUP_NAMES.get(gid, "CF")
                        dspload = float(getattr(patch.info, "dspload", 30.0))
                        # If file not in build/, write to cache folder
                        cache_file = REPO_ROOT / "build" / "loader" / "extracted_cf" / fn
                        cache_file.parent.mkdir(parents=True, exist_ok=True)
                        if not cache_file.exists() or cache_file.read_bytes() != data:
                            cache_file.write_bytes(data)

                        cf_catalog[fn] = UnifiedEffect(
                            filename=fn,
                            name=h.name.strip() or fn.replace(".ZD2", ""),
                            group=gname,
                            group_id=gid,
                            source="CF",
                            dspload=dspload,
                            size_bytes=len(data),
                            effect_id=h.effect_id,
                            path=cache_file,
                            on_pedal=False,
                            is_checked=True,
                            is_valid=True,
                        )
                    except Exception:
                        pass
        except Exception:
            pass

    return cf_catalog


def assemble_unified_catalog(
    backup_dir: Optional[Path] = None,
    factory_img_path: Optional[Path] = None,
    build_dir: Optional[Path] = None,
) -> List[UnifiedEffect]:
    """Assemble complete catalog of all stock and CF effects with on_pedal status."""
    stock = load_stock_catalog(factory_img_path)
    cf = scan_cf_effects(build_dir)

    all_effects: Dict[str, UnifiedEffect] = {}
    all_effects.update(stock)
    all_effects.update(cf)

    # Check on_pedal status if a backup is provided
    pedal_files: Set[str] = set()
    if backup_dir and backup_dir.is_dir():
        for sub in (backup_dir / "files", backup_dir / "effects", backup_dir):
            if sub.is_dir():
                for f in sub.glob("*.ZD2"):
                    pedal_files.add(f.name.upper())

    for fn, ef in all_effects.items():
        ef.on_pedal = fn in pedal_files

    # Default ticks (a profile overrides them): the effect set of the newest bench image, i.e.
    # what the last TEST installer put on the pedal. Ticking everything overflows the file system.
    image_files = newest_image_effects()
    if image_files:
        for fn, ef in all_effects.items():
            ef.is_checked = ef.is_valid and fn in image_files

    # Sort: CF first then stock, then by name
    return sorted(all_effects.values(), key=lambda e: (0 if e.source == "CF" else 1, e.group, e.name))


def calculate_filesystem_usage(
    checked_effects: List[UnifiedEffect],
    factory_img_path: Optional[Path] = None,
) -> Tuple[int, int, int, bool, str]:
    """Calculate filesystem bytes and blocks used against 0x2FE000 capacity.

    Returns:
        (total_bytes, total_blocks, free_blocks, fits, status_message)
    """
    # System overhead: 27 files = 588,541 bytes, 147 data blocks
    system_bytes = 588541
    system_blocks = 147
    system_entries = 27

    effects_bytes = sum(e.size_bytes for e in checked_effects)
    effects_blocks = sum(e.blocks_required for e in checked_effects)
    effects_count = len(checked_effects)

    total_bytes = system_bytes + effects_bytes
    total_blocks = system_blocks + effects_blocks
    total_entries = system_entries + effects_count

    free_blocks = FS_TOTAL_DATA_BLOCKS - total_blocks

    fits = True
    reasons = []

    if total_blocks > FS_TOTAL_DATA_BLOCKS:
        fits = False
        reasons.append(f"Blocks exceeded ({total_blocks} / {FS_TOTAL_DATA_BLOCKS})")

    if total_bytes > FS_TOTAL_BYTES:
        fits = False
        reasons.append(f"Size exceeded ({total_bytes} / {FS_TOTAL_BYTES} bytes)")

    if total_entries > FS_MAX_DIR_SLOTS:
        fits = False
        reasons.append(f"Directory entries exceeded ({total_entries} / {FS_MAX_DIR_SLOTS})")

    pct = (total_bytes / FS_TOTAL_BYTES) * 100
    if fits:
        msg = f"Filesystem: {total_bytes:,} / {FS_TOTAL_BYTES:,} bytes ({pct:.1f}%) — {free_blocks} blocks free"
    else:
        msg = f"CAPACITY EXCEEDED: {', '.join(reasons)}"

    return total_bytes, total_blocks, free_blocks, fits, msg
