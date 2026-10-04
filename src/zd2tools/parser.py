import struct
from .models import ZD2Header, ZD2Block, ZD2Patch

def parse_zd2(data: bytes) -> ZD2Patch:
    if len(data) < 120:
        raise ValueError("File too small to be a ZD2 patch")

    # Header parsing
    magic = data[0:4].decode('ascii')
    if magic != "ZDLF":
        raise ValueError(f"Invalid magic: {magic}")

    header_length = struct.unpack('<I', data[4:8])[0]
    checksum = struct.unpack('<I', data[8:12])[0]
    
    version = data[0x59:0x5D].decode('ascii', errors='ignore').strip('\x00')
    group_id = data[0x5F]
    effect_id = struct.unpack('<I', data[0x60:0x64])[0]
    
    # Name is likely 9 bytes (offset 0x64 to 0x6C)
    name = data[0x64:0x6D].decode('latin-1').split('\x00')[0]
    # Group Name is likely 11 bytes (offset 0x6D to 0x77)
    group_name = data[0x6D:0x78].decode('latin-1').split('\x00')[0]

    header = ZD2Header(
        magic=magic,
        header_length=header_length,
        checksum=checksum,
        version=version,
        group_id=group_id,
        effect_id=effect_id,
        name=name,
        group_name=group_name
    )

    # Blocks parsing
    blocks = []
    offset = 128  # Blocks start at 0x80
    # Stop before the last 16 bytes (footer)
    while offset < len(data) - 16:
        if offset + 8 > len(data) - 16:
            break
        
        tag_bytes = data[offset:offset+4]
        if not all(32 <= b <= 126 for b in tag_bytes):
            break # Not an ASCII tag
            
        tag = tag_bytes.decode('ascii', errors='ignore')
        length = struct.unpack('<I', data[offset+4:offset+8])[0]
        
        if offset + 8 + length > len(data) - 16:
            # Potentially the last block or invalid length
            break
        
        block_data = data[offset+8:offset+8+length]
        blocks.append(ZD2Block(tag=tag, length=length, data=block_data))
        
        offset += 8 + length

    return ZD2Patch(header=header, blocks=blocks)
