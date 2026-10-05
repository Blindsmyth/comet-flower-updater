"""Static cycle count of cl6x assembly, per block.

Counts execute packets (instruction lines not starting with ||) plus the
extra cycles of NOP n. A block runs from a label, or from the packet after a
branch, to the next label or branch (shown as "-> target"; blocks after a
branch are named <label>+). Branch delay slots are filled by the following
packets, so the count is each block's schedule length; multiply by trip
counts to size a kernel. For an SPLOOP, the KERNEL block is one iteration's
length; the loop runs about (trips - 1) * ii + that length.

    python tools/c6x_cycles.py file.asm
"""
import re
import sys

LABEL = re.compile(r"^(\$C\$L\d+|[A-Za-z_]\w*):")
NOP = re.compile(r"\bNOP\s+(\d+)")
BRANCH = re.compile(r"\s(B|BNOP)\s+(\.S\d\s+)?(\$C\$L\d+)")


def count(path):
    blocks, cur = [], None
    for line in open(path, encoding="latin-1"):
        m = LABEL.match(line)
        if m:
            cur = [m.group(1), 0, line.split(";", 1)[1].strip() if ";" in line else ""]
            blocks.append(cur)
            continue
        if cur is None:
            continue
        s = line.split(";", 1)[0]
        if not s.strip() or not s[:1].isspace() and not s.startswith("||"):
            continue
        if s.lstrip().startswith("."):
            continue
        if not s.lstrip().startswith("||"):
            cur[1] += 1
            n = NOP.search(s)
            if n:
                cur[1] += int(n.group(1)) - 1
        b = BRANCH.search(s)
        if b:
            cur[2] = (cur[2] + f" -> {b.group(3)}").strip()
            cur = [cur[0] + "+", 0, ""]
            blocks.append(cur)
    return blocks


if __name__ == "__main__":
    for name, cyc, note in count(sys.argv[1]):
        if cyc:
            print(f"{name:14s} {cyc:6d}  {note}")
