"""List likely function starts that the fact sheets miss.

coverage.py takes function starts from CALLP targets and pointer tables, so
code reached only by plain branches, or a whole function placed right after
another one's return, gets folded into its neighbour. This script flags a
prologue (`STW/STDW reg,*B15--[n]`, `ADDK -n,B15` or `CALLP c016e020,A3`) that
follows an unconditional return (`B/BNOP B3`) plus padding and the return's
remaining delay-slot instructions, and is not a known start. It still misses
leaf functions with no prologue at all.

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
PROLOGUE = re.compile(r"^(STW\.D2T\d\s+[AB]\d+,\*B15--\[\d+\]|STDW\.D2T\d\s+\S+,\*B15--\[\d+\]|CALLP\.S\d\s+0xc016e020,A3|ADDK\.S2\s+-\d+,B15)")
RETURN = re.compile(r"^(BNOP\.S2|B\.S2)\s+B3\b(?:,(\d))?")
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
    delay = 0
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
            r = RETURN.match(text)
            if r and not cond:
                # delay slots still to run after the return: 5 minus the NOP count
                delay = 5 - int(r[2] or 0) if r[1].startswith("BNOP") else 5
                prev_return = True
            elif prev_return and delay > 0 and not PROLOGUE.match(text):
                if not par:
                    delay -= 1  # an instruction in a delay slot of the return
            else:
                prev_return = False
    print(f"candidates: {found}", file=sys.stderr)


if __name__ == "__main__":
    main()
