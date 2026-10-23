"""Patch decoding and preset building for Zoom G1X Four."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import struct
import sys
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FACTORY_PRESETS_DEFAULT = REPO_ROOT / "build" / "fw" / "res2_45056.bin"
EMPTY_SLOT_BYTES = bytes([0x01]) + bytes(23)


@dataclass
class PatchSlot:
    slot_index: int       # 0..4
    effect_id: int        # e.g. 0x01000010
    effect_name: str      # display name, e.g. "COMP", "(Empty)"
    is_enabled: bool      # whether slot is turned ON
    knobs: List[int] = field(default_factory=list)


@dataclass
class PatchRecord:
    index: int            # 1..50
    name: str             # 10 ASCII characters, e.g. "comfy numb"
    slots: List[PatchSlot]
    raw_data: bytes       # 760-byte ZPTC data
    is_empty: bool = False
    is_checked: bool = True
    file_path: Optional[Path] = None

    @property
    def slots_summary(self) -> str:
        names = [s.effect_name for s in self.slots if s.effect_name and s.effect_name != "(Empty)"]
        return " > ".join(names) if names else "(Empty patch)"


def build_id_name_map() -> Dict[int, str]:
    """Build mapping from effect_id uint32 to friendly effect display name."""
    from tools.cf_loader.core import STOCK_EFFECTS
    id_map: Dict[int, str] = {0: "(Empty)", 1: "(Companion)"}
    # Add stock effects
    for fn, eid in STOCK_EFFECTS.items():
        clean_name = fn.replace(".ZD2", "").replace("_", " ").title()
        id_map[eid] = clean_name

    # Add CF effects from library
    from tools.cf_loader.catalog import scan_cf_effects
    cf_fx = scan_cf_effects()
    for ef in cf_fx.values():
        if ef.effect_id:
            id_map[ef.effect_id] = ef.name

    return id_map


def decode_patch_bytes(
    data: bytes,
    index: int = 1,
    id_map: Optional[Dict[int, str]] = None,
    file_path: Optional[Path] = None,
) -> PatchRecord:
    """Decode a single 760-byte PTCF patch."""
    if len(data) < 56 or data[:4] != b"PTCF":
        # Create empty placeholder
        empty_slots = [
            PatchSlot(slot_index=i, effect_id=0, effect_name="(Empty)", is_enabled=False)
            for i in range(5)
        ]
        return PatchRecord(
            index=index,
            name="Empty",
            slots=empty_slots,
            raw_data=data,
            is_empty=True,
            is_checked=True,
            file_path=file_path,
        )

    if id_map is None:
        id_map = build_id_name_map()

    # Patch name: 10 bytes at offset 26
    raw_name = data[26:36]
    name = raw_name.decode("ascii", "replace").rstrip(" \x00") or "Empty"

    # Number of slots from offset 12
    n_slots = struct.unpack_from("<I", data, 12)[0]
    n_slots = min(n_slots, 5)

    # Locate EDTB chunk
    edtb_off = data.find(b"EDTB")
    slots: List[PatchSlot] = []

    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import ua_bench

    all_empty = True
    if edtb_off != -1 and edtb_off + 8 + 24 * n_slots <= len(data):
        for i in range(n_slots):
            slot_bytes = data[edtb_off + 8 + 24 * i : edtb_off + 8 + 24 * (i + 1)]
            try:
                enabled, eid, knobs = ua_bench.decode_entry(slot_bytes)
                ename = id_map.get(eid, f"0x{eid:08x}" if eid else "(Empty)")
                if eid != 0:
                    all_empty = False
                slots.append(
                    PatchSlot(
                        slot_index=i,
                        effect_id=eid,
                        effect_name=ename,
                        is_enabled=bool(enabled),
                        knobs=knobs,
                    )
                )
            except Exception:
                slots.append(
                    PatchSlot(
                        slot_index=i,
                        effect_id=0,
                        effect_name="(Error)",
                        is_enabled=False,
                    )
                )
    else:
        # Fallback to header IDs if EDTB missing
        ids_off = data.find(b"TXJ1") - 4 * n_slots
        if ids_off >= 0:
            for i in range(n_slots):
                eid = struct.unpack_from("<I", data, ids_off + 4 * i)[0]
                ename = id_map.get(eid, f"0x{eid:08x}" if eid else "(Empty)")
                if eid != 0:
                    all_empty = False
                slots.append(
                    PatchSlot(
                        slot_index=i,
                        effect_id=eid,
                        effect_name=ename,
                        is_enabled=True,
                    )
                )

    return PatchRecord(
        index=index,
        name=name,
        slots=slots,
        raw_data=data,
        is_empty=all_empty,
        is_checked=True,
        file_path=file_path,
    )


def make_blank_patch(index: int = 1, name: str = "Empty") -> bytes:
    """Generate a clean 760-byte empty patch."""
    blank_template_path = REPO_ROOT / "backup" / "2026-10-04" / "patches" / "PATCH_030.ZPTC"
    if blank_template_path.exists():
        raw = bytearray(blank_template_path.read_bytes())
        n = struct.unpack_from("<I", raw, 12)[0]
        ids_off = raw.find(b"TXJ1") - 4 * n
        edtb = raw.find(b"EDTB")
        for i in range(n):
            raw[ids_off + 4 * i : ids_off + 4 * i + 4] = bytes(4)
            raw[edtb + 8 + 24 * i : edtb + 8 + 24 * i + 24] = EMPTY_SLOT_BYTES
        # Set patch name
        nm = name.encode("ascii")[:10].ljust(10, b" ")
        raw[26:36] = nm
        return bytes(raw)

    # Fallback synthetic 760-byte patch
    data = bytearray(760)
    data[:4] = b"PTCF"
    struct.pack_into("<I", data, 4, 760)
    struct.pack_into("<I", data, 8, 1)   # version
    struct.pack_into("<I", data, 12, 5)  # 5 slots
    data[16:26] = b"\x20" + bytes(9)
    data[26:36] = name.encode("ascii")[:10].ljust(10, b" ")
    return bytes(data)


def scan_backup_patches(
    backup_dir: Optional[Path] = None,
    id_map: Optional[Dict[int, str]] = None,
) -> List[PatchRecord]:
    """Scan and decode 50 patches from backup directory.

    If directory is None or lacks patches, returns 50 default empty patches.
    """
    if id_map is None:
        id_map = build_id_name_map()

    patches: List[PatchRecord] = []
    patches_folder = None
    if backup_dir and backup_dir.is_dir():
        if (backup_dir / "patches").is_dir():
            patches_folder = backup_dir / "patches"
        else:
            patches_folder = backup_dir

    for i in range(1, 51):
        target_file = None
        if patches_folder:
            for candidate in (
                patches_folder / f"PATCH_{i:03d}.ZPTC",
                patches_folder / f"PATCH_{i:02d}.ZPTC",
                patches_folder / f"PATCH_{i}.ZPTC",
            ):
                if candidate.exists():
                    target_file = candidate
                    break

        if target_file and target_file.exists():
            data = target_file.read_bytes()
            rec = decode_patch_bytes(data, index=i, id_map=id_map, file_path=target_file)
            patches.append(rec)
        else:
            raw = make_blank_patch(index=i, name=f"Patch {i:02d}")
            rec = decode_patch_bytes(raw, index=i, id_map=id_map, file_path=None)
            rec.is_empty = True
            patches.append(rec)

    return patches


def build_presets_command(
    out_bin_path: Path,
    patch_records: List[PatchRecord],
    factory_presets_path: Optional[Path] = None,
    python_exe: Optional[Path] = None,
) -> List[str]:
    """Build command to generate factory presets region with tools/g1presets.py blank."""
    py = str(python_exe or (REPO_ROOT / ".venv" / "Scripts" / "python.exe"))
    presets_src = factory_presets_path or FACTORY_PRESETS_DEFAULT
    if not presets_src.exists():
        presets_src = REPO_ROOT / "build" / "fw" / "cfupd_res85.bin"

    cmd = [
        py,
        str(REPO_ROOT / "tools" / "g1presets.py"),
        "blank",
        str(presets_src),
        str(out_bin_path),
        "--name",
        "Empty",
    ]
    # Set custom names for non-empty or checked patches
    for p in patch_records[:50]:
        if p.name and p.name != "Empty":
            clean_name = p.name.strip()
            if clean_name:
                cmd.extend(["--set", f"{p.index}={clean_name}"])

    return cmd


def write_patch_live(location: int, data: bytes) -> None:
    """Write one patch to the pedal over MIDI and read it back (UNTESTED in the GUI).

    Uses ua_bench's proven session (pedal_session, patch_upload, patch_download) but not
    ua_bench.load_patch, which is console-only (sys.exit, input(), Program Change).
    Raises RuntimeError on any failure; never exits the process."""
    if not 1 <= location <= 50:
        raise RuntimeError("patch location %d out of range 1..50" % location)
    if len(data) < 56 or data[:4] != b"PTCF":
        raise RuntimeError("not a PTCF patch")
    sys.path.insert(0, str(REPO_ROOT / "tools"))
    import ua_bench
    try:
        pedal = ua_bench.pedal_session()
    except SystemExit as e:
        raise RuntimeError(str(e) or "no pedal MIDI port")
    try:
        pedal.patch_upload(location, data)
        back = bytes(pedal.patch_download(location) or b"")
    finally:
        pedal.disconnect()
    if back != bytes(data):
        raise RuntimeError("patch %d: read back differs from what was written" % location)
