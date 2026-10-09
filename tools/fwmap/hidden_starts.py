"""List likely function starts that the fact sheets miss.

coverage.py takes function starts from CALLP targets and pointer tables, so
code reached only by plain branches, or a whole function placed right after
another one's return, gets folded into its neighbour. This script flags a
prologue (`STW B3,*B15--[n]` or `CALLP c016e020,A3`) that directly follows an
unconditional return (`B/BNOP B3`) plus padding, and is not a known start.

Usage: python tools/fwmap/hidden_starts.py [chunk_NN ...]
Prints one line per candidate: address, chunk, and the start it is folded into.
"""
import bisect
import glob
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIS = os.path.join(ROOT, "build", "fw", "map", "main.dis")
FACTS = os.path.join(ROOT, "build", "fw", "map", "facts")

LINE = re.compile(r"^([0-9a-f]{8})\s+[0-9a-f]+\s+(\|\|)?\s*(\[[ !AB0-9]+\])?\s*(\S+)\s*(.*)$")
PROLOGUE = re.compile(r"^(STW\.D2T2\s+B3,\*B15--\[\d+\]|CALLP\.S\d\s+0xc016e020,A3)")
RETURN = re.compile(r"^(BNOP\.S2|B\.S2)\s+B3\b")
PADDING = ("NOP", ".fphead")


def known_starts():
    starts = {}
    for path in sorted(glob.glob(os.path.join(FACTS, "chunk_*.md"))):
        chunk = os.path.basename(path)[:-3]
        with open(path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"^## ([0-9a-f]{8})", line)
                if m:
                    starts[int(m[1], 16)] = chunk
    return starts


def main():
    want = set(sys.argv[1:])
    starts = known_starts()
    order = sorted(starts)
    prev_return = False  # last real instruction was an unconditional return
    found = 0
    with open(DIS, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = LINE.match(line)
            if not m:
                continue
            addr, par, cond, op, rest = int(m[1], 16), m[2], m[3], m[4], m[5]
            if op.startswith(PADDING):
                continue
            text = f"{op} {rest}".strip()
            if prev_return and not par and PROLOGUE.match(text) and addr not in starts:
                i = bisect.bisect_right(order, addr) - 1
                if i >= 0:
                    host = order[i]
                    chunk = starts[host]
                    if not want or chunk in want:
                        print(f"{addr:08x}  {chunk}  inside {host:08x}")
                        found += 1
            prev_return = bool(RETURN.match(text)) and not cond
    print(f"candidates: {found}", file=sys.stderr)


if __name__ == "__main__":
    main()
