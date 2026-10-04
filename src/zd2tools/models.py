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
    version: str
    group_id: int
    effect_id: int
    name: str
    group_name: str

@dataclass
class ZD2Patch:
    header: ZD2Header
    blocks: List[ZD2Block] = field(default_factory=list)

    def get_block(self, tag: str) -> Optional[ZD2Block]:
        for block in self.blocks:
            if block.tag == tag:
                return block
        return None
