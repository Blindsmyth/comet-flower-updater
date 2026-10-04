import struct
import sys
import json
from pathlib import Path

def rip_floats(data, min_len=4):
    tables = []
    current_table = []
    start_offset = 0
    
    for i in range(0, len(data) - 4, 4):
        try:
            val = struct.unpack('<f', data[i:i+4])[0]
            # Heuristic for DSP coefficients: 
            # Numbers that look like gain (0.1 to 10) or filters (20 to 20k)
            # and aren't NaN or extremely tiny/huge
            if abs(val) > 0.00001 and abs(val) < 100000.0:
                if not current_table:
                    start_offset = i
                current_table.append(val)
            else:
                if len(current_table) >= min_len:
                    tables.append((start_offset, current_table))
                current_table = []
        except:
            current_table = []
    return tables

def generate_juce(zd2_path):
    # This would be expanded to a full template
    print(f"// Automatically generated JUCE header for {zd2_path}")
    # ... logic to parse PRMJ and write APVTS ...

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python rip_tables.py <path_to_data.elf>")
        sys.exit(1)
    
    with open(sys.argv[1], 'rb') as f:
        data = f.read()
    
    found = rip_floats(data)
    for offset, table in found:
        name = f"table_0x{offset:04x}"
        cpp_vals = ", ".join([f"{v:.6f}f" for v in table])
        print(f"static const float {name}[] = {{ {cpp_vals} }}; // size: {len(table)}")
