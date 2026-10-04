import struct
import zlib
from .models import ZD2Header, ZD2Block, ZD2Patch

HEADER_SIZE = 0x80
TRAILER_SIZE = 16


def zd2_crc(data: bytes) -> int:
    """Checksum stored at 0x08: CRC32 over everything after the 12-byte
    prefix and before the 16-byte trailer, without the final xor."""
    return zlib.crc32(data[12:-TRAILER_SIZE]) ^ 0xFFFFFFFF


def _cstr(raw: bytes) -> str:
    return raw.split(b"\x00")[0].decode("latin-1")


def parse_zd2(data: bytes) -> ZD2Patch:
    if len(data) < HEADER_SIZE + TRAILER_SIZE:
        raise ValueError("File too small to be a ZD2 patch")

    magic = data[0:4].decode('ascii', errors='replace')
    if magic != "ZDLF":
        raise ValueError(f"Invalid magic: {magic}")

    header_length, checksum, target = struct.unpack('<III', data[4:16])

    header = ZD2Header(
        magic=magic,
        header_length=header_length,
        checksum=checksum,
        target=target,
        unknown=data[0x10:0x59],
        version=data[0x59:0x5D].decode('ascii', errors='ignore').strip('\x00'),
        group_id=data[0x5F],
        effect_id=struct.unpack('<I', data[0x60:0x64])[0],
        # Both fields are 11-byte padded CStrings; bytes after the NUL are
        # leftover garbage from Zoom's build tools (e.g. "m=" in NYC Muff).
        name=_cstr(data[0x64:0x6F]),
        group_name=_cstr(data[0x6F:0x7A]),
    )

    # Tagged blocks tile the file from 0x80 up to the trailer.
    blocks = []
    offset = HEADER_SIZE
    end = len(data) - TRAILER_SIZE
    while offset + 8 <= end:
        tag_bytes = data[offset:offset+4]
        if not all(32 <= b <= 126 for b in tag_bytes):
            break
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        if offset + 8 + length > end:
            break
        blocks.append(ZD2Block(tag=tag_bytes.decode('ascii'), length=length,
                               data=data[offset+8:offset+8+length]))
        offset += 8 + length

    return ZD2Patch(header=header, blocks=blocks, trailer=data[end:],
                    crc_ok=zd2_crc(data) == checksum)
