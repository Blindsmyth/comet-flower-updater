import struct
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class ZD2Block:
    tag: str
    length: int
    data: bytes

@dataclass
class ZD2Header:
    magic: str
    header_length: int
    checksum: int
    target: int        # bitfield of pedal families allowed to load the effect
    unknown: bytes     # the undecoded 73 bytes at 0x10..0x58
    version: str
    group_id: int
    effect_id: int
    name: str
    group_name: str

@dataclass
class ZD2Info:
    word0: int         # effect class: 0 normal, 1 EQ, 2 line selector (MS+ data)
    group_text: str    # e.g. "DRVDRIVE" on G1 Four, empty on DIY builds
    dspload: float     # declared DSP load; the pedal trusts it

@dataclass
class ZD2Patch:
    header: ZD2Header
    blocks: List[ZD2Block] = field(default_factory=list)
    trailer: bytes = b""
    crc_ok: bool = False

    def get_block(self, tag: str) -> Optional[ZD2Block]:
        for block in self.blocks:
            if block.tag == tag:
                return block
        return None

    @property
    def info(self) -> Optional[ZD2Info]:
        block = self.get_block("INFO")
        if block is None or len(block.data) < 20:
            return None
        word0 = struct.unpack("<I", block.data[0:4])[0]
        text = block.data[4:16].split(b"\x00")[0].decode("latin-1")
        dspload = struct.unpack("<f", block.data[16:20])[0]
        return ZD2Info(word0=word0, group_text=text, dspload=dspload)
