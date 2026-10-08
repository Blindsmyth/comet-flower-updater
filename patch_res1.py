import hashlib
import os
import struct
import sys

EXPECTED_SRC_SHA256 = "43060686fce75e175a217194ab1be3aeffe0be7d59f9d3df4181d41b9d3cc5a7"
EXPECTED_SRC_SIZE = 493412

EXPECTED_PATCHED_SHA256 = "9e2ccc1b727672c250d431a8d88a1d5101105c5db90ec7cfc8ca85799267c002"

def verify_cinit_stream(data):
    """Independently verifies that the .cinit RLE stream decompresses with slot 0 = 0x11820000."""
    i = 0x76998
    kind = data[i]; i += 1
    if kind != 1:
        raise ValueError(f"Unexpected cinit kind: {kind}")
    esc = data[i]; i += 1
    out = []
    while i < len(data):
        v = data[i]; i += 1
        if v != esc:
            out.append(v)
            continue
        n = data[i]; i += 1
        if n == 0:
            n = 256 * data[i] + data[i+1]; i += 2
            if n == 0: break
            if n < 256: n = 65536 * n + 256 * data[i] + data[i+1]; i += 2
            v = data[i]; i += 1
        elif n < 4:
            v = esc
        else:
            v = data[i]; i += 1
        out.extend([v] * n)
    
    out = bytes(out)
    if len(out) != 0x2049:
        raise ValueError(f"Decompressed cinit size mismatch: {hex(len(out))}, expected 0x2049")
    slot0_base, = struct.unpack_from('<I', out, 0x1e80)
    if slot0_base != 0x11820000:
        raise ValueError(f"Slot 0 base decompression failed: got {hex(slot0_base)}, expected 0x11820000")
    return True

def patch_ais(input_path, output_path):
    with open(input_path, 'rb') as f:
        src_bytes = f.read()
    
    if len(src_bytes) != EXPECTED_SRC_SIZE:
        raise ValueError(f"Input file size {len(src_bytes)} != expected {EXPECTED_SRC_SIZE}")
    
    src_hash = hashlib.sha256(src_bytes).hexdigest().lower()
    if src_hash != EXPECTED_SRC_SHA256:
        raise ValueError(f"Input file SHA256 {src_hash} does not match expected {EXPECTED_SRC_SHA256}")
    
    data = bytearray(src_bytes)
    
    # 1a. Patch L2CFG early initializer at 0x61008 (c016d08c)
    # Original: f6 62 3c 00 (32-bit STW.D2T2 B0, *+B15[3])
    # New: 27 44 05 fc (compact 16-bit MVK.L2 2, B0; STW.D2T2 B0, *B15[3])
    if data[0x61008:0x6100c] != b'\xf6\x62\x3c\x00':
        raise ValueError("Source mismatch at 0x61008 (early L2CFG)")
    data[0x61008:0x6100c] = b'\x27\x44\x05\xfc'
    
    # 1b. Update .fphead at 0x61018 (c016d09c) to declare Slot 3 as compact!
    # Original: 00 00 d0 e0 (0xe0d00000: mask 0000110b -> Slots 1, 2 compact)
    # New: 00 00 d0 e1 (0xe1d00000: mask 0001110b -> Slots 1, 2, 3 compact)
    if data[0x61018:0x6101c] != b'\x00\x00\xd0\xe0':
        raise ValueError("Source mismatch at 0x61018 (.fphead)")
    data[0x61018:0x6101c] = b'\x00\x00\xd0\xe1'
    
    # 2. Patch L2CFG late initializer table at 0x756b0 (c0181728)
    # Original: 03 00 00 00
    # New: 02 00 00 00
    if data[0x756b0:0x756b4] != b'\x03\x00\x00\x00':
        raise ValueError("Source mismatch at 0x756b0 (late L2CFG)")
    data[0x756b0:0x756b4] = b'\x02\x00\x00\x00'
    
    # 3. Patch Active slot 0 base table (c01839a8) in .cinit RLE stream
    # Original in .cinit at 0x77efa: 1a 05 00 40 1f c0 (5 zeros + 40 1f c0 = 0xc01f4000)
    # New at 0x77efd: 00 82 11 (5 zeros + 00 + 82 + 11 = 0x11820000)
    if data[0x77efa:0x77f00] != bytes.fromhex('1a0500401fc0'):
        raise ValueError("Source mismatch at 0x77efa (cinit RLE stream)")
    data[0x77efd:0x77f00] = b'\x00\x82\x11'
    
    # Verification: Exactly 9 bytes must differ between source and patched data
    diff_indices = [idx for idx in range(len(src_bytes)) if src_bytes[idx] != data[idx]]
    if len(diff_indices) != 9:
        raise ValueError(f"Expected exactly 9 modified bytes, found {len(diff_indices)}")
    
    # Verify .cinit decompression on modified buffer
    verify_cinit_stream(data)
    
    out_hash = hashlib.sha256(data).hexdigest().lower()
    if out_hash != EXPECTED_PATCHED_SHA256:
        raise ValueError(f"Output SHA256 mismatch: {out_hash} != {EXPECTED_PATCHED_SHA256}")
    
    # Atomic file write
    tmp_path = output_path + ".tmp"
    with open(tmp_path, 'wb') as f:
        f.write(data)
    if os.path.exists(output_path):
        os.remove(output_path)
    os.rename(tmp_path, output_path)
    print(f"Successfully and atomically generated {output_path} (SHA256 verified: {out_hash})")

if __name__ == '__main__':
    patch_ais('build/fw/res1_493412.bin', 'build/fw/res1_patched.bin')
