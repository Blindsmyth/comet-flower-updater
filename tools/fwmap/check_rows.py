import os
import glob
import re
import subprocess
import sys

def parse_instruction(text):
    text = re.sub(r'^\|\|\s*', '', text)
    text = re.sub(r'^\[[^\]]+\]\s*', '', text)
    parts = text.split(None, 1)
    if not parts:
        return "", ""
    mnemonic = parts[0]
    operands = parts[1] if len(parts) > 1 else ""
    mnemonic = mnemonic.split('.')[0]
    operands = re.sub(r'\s+', ' ', operands).strip()
    return mnemonic, operands

def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    dis_path = os.path.join(root, "build", "fw", "map", "main.dis")
    facts_dir = os.path.join(root, "build", "fw", "map", "facts")
    map_dir = os.path.join(root, "recon", "map")
    out_file = os.path.join(root, "build", "gemini_scratch", "check_rows.txt")

    LINE = re.compile(r"^([0-9a-f]{8})\s+[0-9a-f]+\s+(\|\|)?\s*(\[[ !AB0-9]+\])?\s*(\S+)\s*(.*)$")
    SECTION = re.compile(r"^TEXT Section \S+ \(.*?\), (0x[0-9a-f]+) bytes at (0x[0-9a-f]+)")

    dis_addrs = {}
    code_ranges = []
    with open(dis_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if m := SECTION.match(line):
                size = int(m.group(1), 16)
                base = int(m.group(2), 16)
                code_ranges.append((base, base + size))
                continue
            
            m = LINE.match(line)
            if m:
                addr = m.group(1)
                parts = []
                if m.group(2): parts.append(m.group(2).strip())
                if m.group(3): parts.append(m.group(3).strip())
                parts.append(m.group(4).strip())
                if m.group(5): parts.append(m.group(5).strip())
                text = " ".join(parts)
                dis_addrs[addr] = re.sub(r'\s+', ' ', text).strip()

    valid_starts = set()
    for path in glob.glob(os.path.join(facts_dir, "chunk_*.md")):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^## ([0-9a-f]{8})", line)
                if m:
                    valid_starts.add(m.group(1))

    hidden_script = os.path.join(root, "tools", "fwmap", "hidden_starts.py")
    res = subprocess.run([sys.executable, hidden_script], capture_output=True, text=True)
    for line in res.stdout.splitlines():
        if line.strip() and not line.startswith("candidates"):
            parts = line.split()
            if len(parts) >= 1 and len(parts[0]) == 8:
                valid_starts.add(parts[0])

    def is_code_addr(addr_str):
        val = int(addr_str, 16)
        return any(base <= val < end for base, end in code_ranges)

    md_files = glob.glob(os.path.join(map_dir, "*.md"))
    
    with open(out_file, "w", encoding="utf-8") as out:
        for md_path in sorted(md_files):
            basename = os.path.basename(md_path)
            
            names = set()
            failures = []

            with open(md_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("| ") and " addr " not in line and "---" not in line:
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) < 6:
                            continue
                        
                        addr = parts[1]
                        name = parts[2]
                        role = parts[3]
                        conf = parts[4]
                        evidence = parts[5]

                        if not re.match(r"^[0-9a-f]{8}$", addr):
                            continue

                        row_failures = []

                        if addr not in valid_starts and "(hidden start" not in role.lower():
                            row_failures.append("Invalid start address")

                        if name in names:
                            row_failures.append(f"Duplicate name: {name}")
                        names.add(name)

                        ev_addrs = set(re.findall(r'\b[0-9a-f]{8}\b', evidence))
                        for ea in ev_addrs:
                            if is_code_addr(ea) and ea not in dis_addrs:
                                row_failures.append(f"Evidence address {ea} not in main.dis")

                        for quote in re.findall(r'`([^`]+)`', evidence):
                            for part in re.split(r';|\n', quote):
                                m = re.match(r'^\s*([0-9a-f]{8})\s+(.+)', part)
                                if m:
                                    s_addr, s_text = m.groups()
                                    s_text = re.sub(r'\s+', ' ', s_text).strip()
                                    if s_addr in dis_addrs:
                                        d_text = dis_addrs[s_addr]
                                        s_mn, s_op = parse_instruction(s_text)
                                        d_mn, d_op = parse_instruction(d_text)
                                        
                                        if s_mn != d_mn or not d_op.startswith(s_op):
                                            row_failures.append(f"Snippet `{s_addr} {s_text}` does not match disassembly `{d_text}`")
                        
                        if row_failures:
                            failures.append((addr, row_failures))
            
            if failures:
                out.write(f"{basename}: {len(failures)} failures\n")
                print(f"{basename}: {len(failures)} failures")
                for addr, row_fails in failures:
                    for rf in row_fails:
                        out.write(f"  - row {addr}: {rf}\n")
            else:
                out.write(f"{basename}: 0 failures\n")
                print(f"{basename}: 0 failures")

if __name__ == "__main__":
    main()
