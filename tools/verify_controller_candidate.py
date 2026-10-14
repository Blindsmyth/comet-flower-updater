"""Verify an offline controller candidate against its ELF and updater inputs.

All artifact paths are explicit. This reads files and optionally writes a
manifest and TI packet listings; it never launches an updater or accesses USB.
Source hashes record the current files, not proof that the ELF was built from
them. Runtime ABI, stack, lifecycle and hardware gates remain separate.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct

import pefile

try:
    from . import make_controller_fw as ctl
    from .make_fs_restore_updater import validate_controller_fw
    from .check_updater_stages import STAGE_VA
except ImportError:  # Direct execution from tools/.
    import make_controller_fw as ctl
    from make_fs_restore_updater import validate_controller_fw
    from check_updater_stages import STAGE_VA


EXPECTED_STAGES = [
    (1, 0x28000, 0xB000, 0), (2, 0x28000, 0, 0x85),
    (1, 0x102000, 0x2FE000, 0), (2, 0x102000, 0, 0x88),
    (1, 0x33000, 0x8C000, 0), (2, 0x33000, 0, 0x81),
    (0, 0, 0, 0), (0, 0, 0, 0),
]
WRITE_REGIONS = {0x85: (0x28000, 0x33000),
                 0x88: (0x102000, 0x400000),
                 0x81: (0x33000, 0xBF000)}
SOURCE_FILES = (
    "firmware/controller/controller.c", "firmware/controller/controller_hooks.asm",
    "firmware/controller/controller.cmd", "tools/make_controller_fw.py",
    "tools/make_fs_restore_updater.py", "tools/verify_controller_candidate.py",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def updater_contents(path):
    """Read every BIN resource and all eight raw rows, including inactive rows."""
    pe = pefile.PE(str(path))
    try:
        resources = {}
        for kind in pe.DIRECTORY_ENTRY_RESOURCE.entries:
            if str(kind.name) != "BIN":
                continue
            for entry in kind.directory.entries:
                require(entry.id is not None and entry.id not in resources,
                        "ambiguous BIN resource ID")
                languages = entry.directory.entries
                require(len(languages) == 1, "ambiguous BIN resource language")
                item = languages[0].data.struct
                payload = bytes(pe.get_data(item.OffsetToData, item.Size))
                require(len(payload) == item.Size, "truncated BIN resource")
                resources[entry.id] = payload
        offset = pe.get_offset_from_rva(STAGE_VA - pe.OPTIONAL_HEADER.ImageBase)
        rows = [struct.unpack_from("<4I", pe.__data__, offset + 16 * i)
                for i in range(8)]
        return resources, rows
    finally:
        pe.close()


def verify_resources(resources, reference, rows, firmware, presets, effects):
    """The official template plus three explicit replacements is the contract."""
    require(set(resources) == set(reference), "BIN resource ID set changed")
    require(all(rid in reference for rid in WRITE_REGIONS),
            "reference updater lacks required resources")
    expected = dict(reference)
    expected.update({0x81: firmware, 0x85: presets, 0x88: effects})
    for rid, payload in expected.items():
        require(resources[rid] == payload, "BIN resource %#x differs from input" % rid)
    require(rows == EXPECTED_STAGES, "unexpected full eight-row stage table")
    require(len(presets) == 0xB000, "presets must occupy the entire 0xB000 region")
    require(len(effects) == 0x2FE000, "effects must occupy the entire 0x2FE000 region")
    for rid, (start, end) in WRITE_REGIONS.items():
        require(start + len(resources[rid]) <= end,
                "resource %#x write exceeds allowed flash region" % rid)


def verify_firmware(stock, firmware, payload_base, payload, symbols):
    validate_controller_fw(stock, firmware)
    commands = list(ctl.ais_commands(firmware))
    offset, opcode, args = commands[-2]
    require(opcode == ctl.AIS_SECTION_LOAD, "missing controller AIS load")
    require(args == (payload_base, len(payload)), "AIS load differs from ELF extent")
    require(payload_base == ctl.CTL_BASE and 0 < len(payload) <= ctl.CTL_SIZE,
            "ELF payload differs from controller reservation")
    require(firmware[offset + 12:offset + 12 + len(payload)] == payload,
            "AIS payload differs from ELF allocation")
    hooks = {}
    for vma, hook_offset, stock_word, _, symbol in ctl.HOOKS:
        require(symbol in symbols, "ELF lacks hook symbol " + symbol)
        target = symbols[symbol]
        require(payload_base <= target < payload_base + len(payload),
                "ELF hook symbol outside payload: " + symbol)
        word = struct.unpack_from("<I", firmware, hook_offset)[0]
        require(ctl.callp_target(vma, word) == target,
                "hook %#x does not reach ELF symbol %s" % (vma, symbol))
        require((word ^ stock_word) & ~(0x1FFFFF << 7) == 0,
                "hook %#x altered non-target bits" % vma)
        broken = bytearray(firmware)
        struct.pack_into("<I", broken, hook_offset, stock_word)
        try:
            validate_controller_fw(stock, broken)
        except ValueError:
            pass
        else:
            raise ValueError("validator accepted missing hook %#x" % vma)
        hooks[hex(vma)] = {"symbol": symbol, "target": hex(target)}
    return hooks


def write_packet_audit(firmware, output, cgt):
    """Reassemble each patched fetch packet at its original address for dis6x."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for vma, offset, _, _, symbol in ctl.HOOKS:
        packet = vma & ~31
        words = struct.unpack_from("<8I", firmware, offset - (vma - packet))
        stem = output / (symbol + "_" + format(vma, "x"))
        stem.with_suffix(".asm").write_text(
            ' .sect ".text"\n .global packet\npacket:\n' +
            "".join(" .word 0x%08x\n" % word for word in words), encoding="utf-8")
        stem.with_suffix(".cmd").write_text(
            '--retain="*(.text)"\nMEMORY { CODE: o=%#x, l=0x100 }\n'
            'SECTIONS { .text > CODE }\n' % packet, encoding="utf-8")
        ctl.run(Path(cgt) / "bin/cl6x", "--silicon_version=6740", "--abi=eabi",
                "--compile_only", "--obj_directory=" + str(output), stem.with_suffix(".asm"))
        ctl.run(Path(cgt) / "bin/lnk6x", "--output_file=" + str(stem.with_suffix(".elf")),
                stem.with_suffix(".obj"), stem.with_suffix(".cmd"))
        ctl.run(Path(cgt) / "bin/dis6x", stem.with_suffix(".elf"), stem.with_suffix(".dis"))


def verify_candidate(firmware, updater, elf, reference_updater, presets, effects,
                     source_root=ctl.ROOT):
    paths = {"firmware": Path(firmware), "updater": Path(updater), "elf": Path(elf),
             "reference_updater": Path(reference_updater), "presets": Path(presets),
             "effects": Path(effects)}
    resources, rows = updater_contents(paths["updater"])
    reference, _ = updater_contents(paths["reference_updater"])
    firmware_data = paths["firmware"].read_bytes()
    verify_resources(resources, reference, rows, firmware_data,
                     paths["presets"].read_bytes(), paths["effects"].read_bytes())
    lo, payload, symbols = ctl.elf_image(paths["elf"])
    hooks = verify_firmware(reference[0x81], firmware_data, lo, payload, symbols)
    source_root = Path(source_root)
    manifest = {
        "status": "DO_NOT_FLASH", "verification": "offline artifact structure and identity",
        "source_hash_note": "Current source hashes do not prove ELF build provenance.",
        "artifact_sha256": {name: sha256(path.read_bytes()) for name, path in paths.items()},
        "hooks": hooks, "payload_base": hex(lo), "payload_size": len(payload),
        "resource_sha256": {hex(rid): sha256(data) for rid, data in resources.items()},
        "source_sha256": {name: sha256((source_root / name).read_bytes()) for name in SOURCE_FILES},
    }
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("firmware", "updater", "elf", "reference-updater", "presets", "effects"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--source-root", type=Path, default=ctl.ROOT)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--packet-audit", type=Path)
    parser.add_argument("--cgt", type=Path, default=ctl.CGT)
    args = parser.parse_args(argv)
    try:
        manifest = verify_candidate(args.firmware, args.updater, args.elf,
                                    args.reference_updater, args.presets, args.effects,
                                    args.source_root)
        if args.packet_audit:
            write_packet_audit(args.firmware.read_bytes(), args.packet_audit, args.cgt)
        result = json.dumps(manifest, indent=2) + "\n"
        if args.manifest:
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            args.manifest.write_text(result, encoding="utf-8")
        print(result, end="")
    except (ValueError, OSError, KeyError, IndexError, struct.error, pefile.PEFormatError) as exc:
        parser.exit(1, "verification refused: %s\n" % exc)


if __name__ == "__main__":
    main()
