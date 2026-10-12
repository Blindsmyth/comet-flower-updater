import re
import struct

dis_path = 'build/codex7/boot.dis'
refs_path = 'build/codex7/bootrefs.txt'

def parse_strings(dis_path):
    # read .word directives
    addr_to_bytes = {}
    with open(dis_path, 'r', encoding='latin-1') as f:
        for line in f:
            if '.word' in line:
                m = re.search(r'(c[0-9a-f]{7})\s+([0-9a-f]{8})?\s*(?:\|\|)?\s*\.word\s+(0x[0-9a-f]+)', line)
                if m:
                    addr = int(m.group(1), 16)
                    val = int(m.group(3), 16)
                    addr_to_bytes[addr] = struct.pack('<I', val)
    
    # build contiguous blocks
    sorted_addrs = sorted(addr_to_bytes.keys())
    blocks = {}
    curr_addr = None
    curr_bytes = bytearray()
    
    for a in sorted_addrs:
        if curr_addr is None:
            curr_addr = a
            curr_bytes.extend(addr_to_bytes[a])
        elif a == curr_addr + len(curr_bytes):
            curr_bytes.extend(addr_to_bytes[a])
        else:
            blocks[curr_addr] = bytes(curr_bytes)
            curr_addr = a
            curr_bytes = bytearray(addr_to_bytes[a])
    if curr_addr is not None:
        blocks[curr_addr] = bytes(curr_bytes)
        
    # extract strings
    strings = {}
    for base, data in blocks.items():
        s = b""
        start_offset = 0
        for i, b in enumerate(data):
            if 32 <= b < 127:
                if not s: start_offset = i
                s += bytes([b])
            else:
                if len(s) >= 4:
                    strings[base + start_offset] = s.decode('ascii')
                s = b""
        if len(s) >= 4:
            strings[base + start_offset] = s.decode('ascii')
            
    return strings

def main():
    strings = parse_strings(dis_path)
    
    # get refs
    refs_by_func = {} # we'll map instruction address to references
    func_callers = {}
    
    call_targets = set()
    code_ptrs = set()
    
    instrs = []
    
    with open(dis_path, 'r', encoding='latin-1') as f:
        for line in f:
            if not line.strip(): continue
            parts = line.split()
            if not parts: continue
            addr_str = parts[0]
            if len(addr_str) == 8 and all(c in '0123456789abcdef' for c in addr_str):
                addr = int(addr_str, 16)
                instrs.append((addr, line))
                
                # find CALLP
                if 'CALLP' in line:
                    m = re.search(r'CALLP\.[S12X]+\s+(0xc[0-9a-f]+)', line)
                    if m:
                        target = int(m.group(1), 16)
                        call_targets.add(target)
                        func_callers.setdefault(target, []).append(addr)
                        
                # find .word pointers to code
                if '.word' in line:
                    m = re.search(r'\.word\s+(0xc[0-9a-f]+)', line)
                    if m:
                        val = int(m.group(1), 16)
                        if val >= 0xc01f4000 and val < 0xc0230000:
                            code_ptrs.add(val)

    # get bootrefs
    instr_to_ref = {}
    with open(refs_path, 'r', encoding='utf-16') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 3:
                iaddr = int(parts[0], 16)
                refval = int(parts[2], 16)
                instr_to_ref.setdefault(iaddr, []).append(refval)
                
    # function starts
    starts = sorted(list(call_targets | code_ptrs))
    starts = [s for s in starts if 0xc01f4000 <= s < 0xc0230000] # roughly in range
    
    if 0xc01f4000 not in starts:
        starts.insert(0, 0xc01f4000)
        
    start_set = set(starts)
    
    # group instructions into functions
    funcs = {}
    curr_start = None
    for addr, line in instrs:
        if addr in start_set:
            curr_start = addr
            funcs[curr_start] = {'end': addr, 'refs': set(), 'callers': func_callers.get(addr, [])}
        if curr_start is not None:
            funcs[curr_start]['end'] = addr
            if addr in instr_to_ref:
                for r in instr_to_ref[addr]:
                    funcs[curr_start]['refs'].add(r)
                    
    # write markdown
    out = ["| Address | Name | Description | Confidence | Evidence |",
           "|---|---|---|---|---|"]
           
    for start in sorted(funcs.keys()):
        f = funcs[start]
        size = f['end'] - start + 4
        if size <= 4: continue # ignore empty/data
        
        # gather strings
        func_strings = []
        for r in f['refs']:
            # check if r is a string or near a string
            for saddr, sval in strings.items():
                if 0 <= saddr - r < 16 or 0 <= r - saddr < 16:
                    func_strings.append(sval)
        
        # gather mmio
        mmios = [hex(r) for r in f['refs'] if (0x01800000 <= r < 0x01e50000)]
        
        desc_parts = [f"size {size}"]
        if mmios:
            desc_parts.append(f"mmio {','.join(mmios)}")
        if func_strings:
            desc_parts.append(f"strings: {', '.join(repr(s) for s in set(func_strings))}")
        
        callers = f['callers']
        if callers:
            desc_parts.append(f"callers {len(callers)}")
            
        desc = "; ".join(desc_parts)
        
        # build evidence
        evid = ""
        # just list the first caller for evidence if available
        if callers:
            evid = f"called by {hex(callers[0])[2:]}"
        else:
            evid = "code pointer or entry"
            
        addr_hex = hex(start)[2:]
        out.append(f"| {addr_hex} | unk_{addr_hex} | {desc} | guess | {evid} |")
        
    with open('recon/map/res5_boot.md', 'w', encoding='utf-8') as f:
        f.write("# Recon 5 Boot\n\n")
        f.write("\n".join(out))
        f.write("\n")

if __name__ == '__main__':
    main()
