"""Minimal reader for the TI C6000 ELF held in a ZD2 DATA block.

Stdlib only. It reads just enough to compare effects across pedal families:
entry symbol, relocation types, the parameter table and the image-info list.
Layouts follow thammer/stomphacks docs/zd2-abi.md, cross-checked against
G1X Four stock effects (see recon/02_g1x4_abi_comparison.md).
"""
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

EM_TI_C6000 = 140
PARAM_RECORD = 56          # bytes per parameter-table record
RELOC_NAMES = {1: "ABS32", 9: "ABS_L16", 10: "ABS_H16"}


@dataclass
class Section:
    name: str
    type: int
    addr: int
    offset: int
    size: int
    link: int
    entsize: int


@dataclass
class Param:
    name: str
    max: int
    default: int
    handler: str
    flags: int


@dataclass
class EffectElf:
    machine: int
    entry: int
    entry_symbol: str
    reloc_types: List[int]
    params: List[Param] = field(default_factory=list)
    images: List[Tuple[int, int, int]] = field(default_factory=list)  # w, h, ptr


def _cstr(raw: bytes) -> str:
    return raw.split(b"\x00")[0].decode("latin-1")


class _Elf:
    def __init__(self, data: bytes):
        if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
            raise ValueError("not a 32-bit little-endian ELF")
        self.data = data
        (_, self.machine, _, self.entry, _, shoff, _, _, _, _,
         shentsize, shnum, shstrndx) = struct.unpack("<HHIIIIIHHHHHH", data[16:52])
        raw = [struct.unpack("<10I", data[shoff + i * shentsize:
                                         shoff + i * shentsize + 40])
               for i in range(shnum)]
        strtab = raw[shstrndx][4]
        self.sections = [
            Section(_cstr(data[strtab + s[0]:]), s[1], s[3], s[4], s[5], s[6], s[9])
            for s in raw
        ]

    def symbols(self) -> Dict[int, str]:
        """addr -> name, preferring .symtab names over .dynsym ones."""
        out: Dict[int, str] = {}
        for sec in sorted(self.sections, key=lambda s: s.type != 2):
            if sec.type not in (2, 11) or not sec.entsize:
                continue
            names = self.sections[sec.link].offset
            for i in range(sec.size // sec.entsize):
                o = sec.offset + i * sec.entsize
                n, value = struct.unpack("<II", self.data[o:o + 8])
                name = _cstr(self.data[names + n:])
                if name and name[0] not in "$." and (
                        value not in out or name.startswith("Dll_")):
                    out[value] = name
        return out

    def reloc_types(self) -> List[int]:
        types = set()
        for sec in self.sections:
            if sec.type == 4 and sec.entsize:
                for i in range(sec.size // sec.entsize):
                    o = sec.offset + i * sec.entsize
                    types.add(struct.unpack("<I", self.data[o + 4:o + 8])[0] & 0xFF)
        return sorted(types)

    def section_named(self, name: str) -> Optional[Section]:
        return next((s for s in self.sections if s.name == name and s.type == 1), None)


def parse_effect_elf(data: bytes) -> EffectElf:
    elf = _Elf(data)
    syms = elf.symbols()
    info = EffectElf(machine=elf.machine, entry=elf.entry,
                     entry_symbol=syms.get(elf.entry, ""),
                     reloc_types=elf.reloc_types())

    const = elf.section_named(".const")
    if const is None:
        return info
    body = data[const.offset:const.offset + const.size]

    # The parameter table opens with the "OnOff" record; the image-info list
    # follows the table directly (true for every stock and DIY effect seen).
    start = body.find(b"OnOff\x00")
    if start < 0 or start % 4:
        return info
    o = start
    while o + PARAM_RECORD <= len(body):
        w = struct.unpack("<14I", body[o:o + PARAM_RECORD])
        name = _cstr(body[o:o + 12])
        if not name or not name.isprintable():
            break
        info.params.append(Param(name=name, max=w[3], default=w[4],
                                 handler=syms.get(w[7], f"0x{w[7]:x}"),
                                 flags=w[12]))
        o += PARAM_RECORD
    while o + 12 <= len(body):
        width, height, ptr = struct.unpack("<III", body[o:o + 12])
        if not ptr:
            break
        info.images.append((width, height, ptr))
        o += 12
    return info


def reloc_names(types: List[int]) -> str:
    return ",".join(RELOC_NAMES.get(t, f"?{t}") for t in types)
