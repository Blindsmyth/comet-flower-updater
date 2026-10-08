import struct
import sys

def patch_ais(input_path, output_path):
    with open(input_path, 'rb') as f:
        data = bytearray(f.read())
    
    # 1. Patch L2CFG early initializer at 0x61008 (c016d08c)
    # Original: f6 62 3c 00 (32-bit STW.D2T2 B0, *+B15[3])
    # New: 27 44 05 fc (compact 16-bit MVK.L2 2, B0; STW.D2T2 B0, *B15[3])
    data[0x61008:0x6100c] = b'\x27\x44\x05\xfc'
    
    # 1b. Update .fphead at 0x61018 (c016d09c) to declare Slot 3 as compact!
    # Original: 00 00 d0 e0 (0xe0d00000: mask 0000110b -> Slots 1, 2 compact)
    # New: 00 00 d0 e1 (0xe1d00000: mask 0001110b -> Slots 1, 2, 3 compact)
    data[0x61018:0x6101c] = b'\x00\x00\xd0\xe1'
    
    # 2. Patch L2CFG late initializer table at 0x756b0 (c0181728)
    # Original: 03 00 00 00
    # New: 02 00 00 00
    data[0x756b0:0x756b4] = b'\x02\x00\x00\x00'
    
    # 3. Patch Active slot 0 base table (c01839a8) in .cinit RLE stream
    # Original in .cinit at 0x77efa: 1a 05 00 40 1f c0 (5 zeros + 40 1f c0 = 0xc01f4000)
    # New at 0x77efd: 00 82 11 (5 zeros + 00 + 82 + 11 = 0x11820000)
    # Preserves RLE stream length and surrounding data perfectly.
    assert data[0x77efa:0x77f00] == bytes.fromhex('1a0500401fc0'), "Unexpected cinit stream signature!"
    data[0x77efd:0x77f00] = b'\x00\x82\x11'
    
    # 4. Patch c016e380 L1P invalidate + tail call at 0x622FC
    # Replaces entire 32-byte packet
    packet = [
        0x00801428, # MVK.S1 0x0028, A1
        0x0080c268, # MVKH.S1 0x01840000, A1
        0x0004a358, # MVK.L1 1, A0
        0x00040274, # STW.D1T1 A0, *+A1[0]
        0x0320002a, # MVK.S2 0x4000, B6
        0x0300c26a, # MVKH.S2 0x01840000, B6
        0x0fe16012, # B.S2 0xc015ee80
        0x00008000, # NOP 5
    ]
    data[0x622fc:0x622fc+32] = b''.join(struct.pack('<I', i) for i in packet)
    
    with open(output_path, 'wb') as f:
        f.write(data)
    print(f"Successfully generated {output_path}")

if __name__ == '__main__':
    patch_ais('build/fw/res1_493412.bin', 'build/fw/res1_patched.bin')
