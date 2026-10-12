from pathlib import Path
import os
import glob
import re
import subprocess
import sys

def parse_instruction(text):
    text = re.sub(r'^\|\|\^?\s*', '', text)
    text = re.sub(r'^\[[^\]]+\]\s*', '', text)
    parts = text.split(None, 1)
    if not parts:
        return "", ""
    mnemonic = parts[0]
    operands = parts[1] if len(parts) > 1 else ""
    mnemonic = mnemonic if mnemonic.startswith('.') else mnemonic.split('.')[0]
    operands = re.sub(r'\s+', ' ', operands).strip()
    return mnemonic, operands

def read_dis(path):
    instructions, ranges = {}, []
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"^TEXT Section .*?, (0x[0-9a-f]+) bytes at (0x[0-9a-f]+)", line)
        if m:
            size, base = (int(x, 16) for x in m.groups())
            ranges.append((base, base + size))
        m = re.match(r"^([0-9a-f]{8})\s+[0-9a-f]+\s+(.+)", line)
        if m:
            instructions[m[1]] = m[2].strip()
    return instructions, ranges


def read_refs(path):
    raw = path.read_bytes()
    return raw.decode("utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8").splitlines()


def boot_candidates(root, instructions):
    candidates = {}
    _, ranges = read_dis(root / "build/codex7/boot.dis")
    def add(target, source, kind):
        if any(lo <= int(target, 16) < hi for lo, hi in ranges) and target in instructions and not parse_instruction(instructions[target])[0].startswith("."):
            candidates.setdefault(target, []).append((source, kind))
    for addr, text in instructions.items():
        mn, op = parse_instruction(text)
        m = re.match(r"0x([0-9a-f]{8})(?:,|$)", op)
        if m and mn in ("CALLP", ".word"):
            add(m[1], addr, mn)
    for line in read_refs(root / "build/codex7/bootrefs.txt"):
        fields = line.split()
        if len(fields) == 3 and fields[0] in instructions:
            add(fields[2], fields[0], "materialized pointer " + fields[1])
    return candidates


def sequential_starts(instructions):
    """Starts following an independently visible return and short padding."""
    starts = set()
    prior_addr, prior_text = None, ""
    for addr in sorted(instructions):
        text = instructions[addr]
        mnemonic, operands = parse_instruction(text)
        if mnemonic.startswith(".") or mnemonic == "NOP":
            continue
        if text.startswith("||") and re.match(
            r"CALLP\s+(?:0xc016e000|0x1180bcc0),A3\b", prior_text):
            # Parallel result move belongs to the same return packet.
            continue
        if prior_addr is not None and int(addr, 16) - int(prior_addr, 16) <= 32:
            returned = re.match(r"BNOP\s+B3,5\b", prior_text)
            restored = re.match(r"CALLP\s+(?:0xc016e000|0x1180bcc0),A3\b", prior_text)
            if returned or restored:
                starts.add(addr)
        prior_addr, prior_text = addr, f"{mnemonic} {operands}"
    return starts


def reviewed_starts(instructions):
    """Unusual starts with independent return/caller evidence in main.dis."""
    evidence = {
        # cosf alternate entry after the prior routine's indirect return and
        # its delay-slot instructions, followed by six NOP words.
        "c0165020": (("c0164ff4", "B.S2X         A10"),
                      ("c0165004", "XOR.L1        A5,A4,A4"),
                      ("c0165020", "MVK.S2        0x0fdb,B6")),
        # Branches from c01662cc/c0166318 target this divide helper; the
        # previous routine returns at c01687ae and leaves NOP padding.
        "c01687c0": (("c01662cc", "B.S1          0xc01687c0"),
                      ("c0166318", "B.S1          0xc01687c0"),
                      ("c01687ae", "BNOP.S2       B3,0"),
                      ("c01687c0", "CMPEQ.L1X     8,B4,A0")),
        # c016a904/a908 construct 0x118164c0 and c016a90e stores it as a
        # function pointer in the object table.
        "118164c0": (("c016a904", "MVK.S1        0x64c0,A0"),
                      ("c016a908", "MVKH.S1       0x11810000,A0"),
                      ("c016a90e", "STW.D1T1      A0,*A4[A5]"),
                      ("118164c0", "STW.D2T1      A11,*B15--[2]")),
    }
    return {start for start, checks in evidence.items()
            if all(fragment in instructions.get(addr, "") for addr, fragment in checks)}


def operand_prefix(quote, actual):
    def normalize(text):
        # The disassembler prints addresses with 0x and small immediates in
        # either decimal or hex; the map uses both spellings.
        pattern = r"(?<![0-9A-Za-z_])(?:0x[0-9a-fA-F]+|[0-9a-fA-F]{8}|\d+)(?![0-9A-Za-z_])"
        def number(match):
            value = match[0]
            base = 16 if value.startswith("0x") or len(value) == 8 else 10
            return f"#{int(value, base)}"
        return re.sub(pattern, number, re.sub(r"\s+", "", text))
    quote, actual = normalize(quote), normalize(actual)
    return actual.startswith(quote) and (len(quote) == len(actual) or not quote or actual[len(quote)] in ",[]()+-*")


def predicate_matches(quote, actual):
    # Omitted predicates remain accepted for legacy snippets; explicit ones must agree.
    q = re.search(r"\[\s*(!?[AB][012])\s*\]", quote)
    d = re.search(r"\[\s*(!?[AB][012])\s*\]", actual)
    return not q or bool(d and q[1] == d[1])


def main():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--output", default=str(Path(root) / "build/gemini_scratch/check_rows.txt"))
    args = parser.parse_args()
    facts_dir = os.path.join(root, "build", "fw", "map", "facts")
    map_dir = os.path.join(root, "recon", "map")
    library_text = (Path(map_dir) / "00_library_kernel.md").read_text(encoding="utf-8")
    library_starts = set(re.findall(r"(?m)^\| ([0-9a-f]{8}) \|", library_text))
    out_file = args.output
    main_image = read_dis(Path(root) / "build/fw/map/main.dis")
    boot_image = read_dis(Path(root) / "build/codex7/boot.dis")
    boot_starts = boot_candidates(Path(root), boot_image[0])
    main_sequential_starts = sequential_starts(main_image[0])
    main_reviewed_starts = reviewed_starts(main_image[0])

    valid_starts = set()
    for path in glob.glob(os.path.join(facts_dir, "chunk_*.md")):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^## ([0-9a-f]{8})", line)
                if m:
                    valid_starts.add(m.group(1))

    hidden_script = os.path.join(root, "tools", "fwmap", "hidden_starts.py")
    res = subprocess.run([sys.executable, hidden_script], capture_output=True, text=True, check=True)
    for line in res.stdout.splitlines():
        if line.strip() and not line.startswith("candidates"):
            parts = line.split()
            if len(parts) >= 1 and len(parts[0]) == 8:
                valid_starts.add(parts[0])

    def is_code_addr(addr_str):
        val = int(addr_str, 16)
        return any(base <= val < end for base, end in code_ranges)

    md_files = args.paths or glob.glob(os.path.join(map_dir, "*.md"))
    Path(out_file).parent.mkdir(parents=True, exist_ok=True)
    total = 0
    
    with open(out_file, "w", encoding="utf-8") as out:
        for md_path in sorted(md_files):
            basename = os.path.basename(md_path)
            
            boot = basename == "res5_boot.md"
            dis_addrs, code_ranges = boot_image if boot else main_image
            starts = boot_starts if boot else valid_starts
            image_name = "boot.dis" if boot else "main.dis"
            names = set()
            failures = []

            with open(md_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("| ") and " addr " not in line and "---" not in line:
                        parts = [p.strip() for p in re.split(r"(?<!\|)\|(?!\|)", line)]
                        if len(parts) < 6:
                            continue
                        
                        addr = parts[1]
                        name = parts[2]
                        # Existing map prose contains literal pipes in roles
                        # (for example bitwise OR). Find the confidence field
                        # instead of assuming every pipe is a table delimiter.
                        conf_index = next((i for i in range(4, len(parts) - 1)
                                           if parts[i].startswith(("guess", "likely", "confirmed"))
                                           or parts[i] in ("-", "--", "—", "see")), 4)
                        role = " | ".join(parts[3:conf_index])
                        conf = parts[conf_index]
                        evidence = " | ".join(parts[conf_index + 1:-1])

                        if not re.match(r"^[0-9a-f]{8}$", addr):
                            continue

                        row_failures = []

                        library_reference = name.startswith("see 00") and addr in library_starts
                        if not re.fullmatch(r"[A-Za-z_][\w.$]*", name) and not library_reference:
                            row_failures.append("Invalid function name")

                        addr_int = int(addr, 16)
                        is_legit_trampoline = (
                            (0x1180BC00 <= addr_int <= 0x1180BD30)
                            or addr in ("11818ea0", "11818eb0", "11818ec0", "c0140000")
                        )
                        if addr not in dis_addrs or parse_instruction(dis_addrs.get(addr, ""))[0].startswith("."):
                            row_failures.append("Start is not an instruction")
                        if addr not in starts and not (not boot and (
                            is_legit_trampoline or addr in main_sequential_starts
                            or addr in main_reviewed_starts)):
                            row_failures.append("Invalid start address")
                        cross_reference = (library_reference or role.startswith("see ")
                                           or "00_library_kernel.md" in evidence)
                        if conf not in ("guess", "likely", "confirmed") and not (
                            cross_reference and conf in ("-", "--", "—", "see")):
                            row_failures.append("Invalid confidence")

                        if name in names:
                            # Exempt rows starting with "see " from duplicate name checks (used for cross-references)
                            if not name.startswith("see "):
                                row_failures.append(f"Duplicate name: {name}")
                        names.add(name)

                        ev_addrs = set()
                        for match in re.finditer(r'(?<![0-9a-z])(?:0x)?([0-9a-f]{8})\b', evidence):
                            # Inclusive/exclusive span ends need not decode as
                            # instructions; the quoted instruction check below
                            # still validates concrete source sites.
                            before = evidence[:match.start()]
                            if re.search(r'[0-9a-f]{8}\s*(?:\.\.|[-–])\s*$', before):
                                continue
                            ev_addrs.add(match[1])
                        for ea in ev_addrs:
                            if is_code_addr(ea) and ea not in dis_addrs:
                                row_failures.append(f"Evidence address {ea} not in {image_name}")

                        for quote in re.findall(r'`([^`]+)`', evidence):
                            for part in re.split(r';|\n', quote):
                                m = re.match(r'^\s*(?:0x)?([0-9a-f]{8})\s+(.+)', part)
                                if m:
                                    s_addr, s_text = m.groups()
                                    s_text = re.sub(r'\s+', ' ', s_text).strip()
                                    # A backticked address plus arithmetic or
                                    # prose is a data reference, not an
                                    # instruction quotation.
                                    if not re.match(r'^(?:\|\|\s*)?(?:\[!?[AB][012]\]\s*)?[A-Z][A-Z0-9]*(?:\.|\s|$)', s_text):
                                        continue
                                    if s_addr not in dis_addrs:
                                        row_failures.append(f"Quoted address {s_addr} not in {image_name}")
                                    if s_addr in dis_addrs:
                                        d_text = dis_addrs[s_addr]
                                        s_mn, s_op = parse_instruction(s_text)
                                        d_mn, d_op = parse_instruction(d_text)
                                        
                                        if s_mn != d_mn or not operand_prefix(s_op, d_op) or not predicate_matches(s_text, d_text):
                                            row_failures.append(f"Snippet `{s_addr} {s_text}` does not match disassembly `{d_text}`")
                        
                        if row_failures:
                            failures.append((addr, row_failures))
            
            total += len(failures)
            if failures:
                out.write(f"{basename}: {len(failures)} failures\n")
                print(f"{basename}: {len(failures)} failures")
                for addr, row_fails in failures:
                    for rf in row_fails:
                        out.write(f"  - row {addr}: {rf}\n")
            else:
                out.write(f"{basename}: 0 failures\n")
                print(f"{basename}: 0 failures")

    return bool(total)

if __name__ == "__main__":
    sys.exit(main())
