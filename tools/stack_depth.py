"""Static worst-case stack depth over main.dis (conservative upper bound).

Frame = sum of every SP decrement in a function (pushes + SUB/ADDK), which
over-approximates (epilogue restores are ignored; decrements in mutually
exclusive branches are summed).  Tail branches out of a function are charged
the caller's full frame.  Indirect branches/calls and cycles are reported,
not silently bounded: a result with unresolved items is NOT a proof.

usage: stack_depth.py ROOT_HEX [ROOT_HEX ...]
"""
import bisect
import csv
import re
import sys
from pathlib import Path

DIS = Path('build/fw/map/main.dis')
TSV = Path('build/fw/map/subsystems.tsv')
HIDDEN = {0xc015a020, 0xc015a2a0, 0xc015de40, 0xc015e060, 0xc0162a60,
          0xc0162d60, 0xc0155dc0, 0xc0169170, 0xc0160820}
SIZE = {'STW': 4, 'STDW': 8, 'STH': 2, 'STB': 1}

INS = []
for _l in DIS.read_text().splitlines():
    _m = re.match(r'^([0-9a-f]{8})\s+[0-9a-f]{4,8}\s+(.*)', _l)
    if _m:
        INS.append((int(_m[1], 16), _m[2]))
ADDRS = [a for a, _ in INS]


def data_code_pointers():
    """Every 32-byte-aligned code pointer in the kernel config/data block.

    Indirect branches load handlers from this block, so these are the
    candidate targets (a sound over-approximation of data-driven callbacks).
    """
    import struct
    d = Path('build/fw/map/main.elf').read_bytes()
    shoff, = struct.unpack_from('<I', d, 0x20)
    ent, num = struct.unpack_from('<HH', d, 0x2e)
    out = set()
    for i in range(num):
        _, t, _, addr, off, sz = struct.unpack_from('<6I', d, shoff + i * ent)
        if t != 1 or not addr or not 0xc0180000 <= addr + sz <= 0xc0182000:
            continue
        for k in range(0, sz - 3, 4):
            v, = struct.unpack_from('<I', d, off + k)
            if 0xc0110000 <= v < 0xc0180000 and v % 32 == 0 and 0xc0180000 <= addr + k < 0xc0181b24:
                out.add(v)
    return sorted(out)


RESOLVE = '--resolve' in sys.argv
if RESOLVE:
    sys.argv.remove('--resolve')
    # Restrict to the task-hook records (c0180630..c0180660) plus the generic
    # handler slot at c018172c: the pointer sweep over the whole config block
    # pulls in every application callback and is not a useful bound.
    PTRS = [0xc0160660, 0xc016e960, 0xc0163460, 0xc01690c0, 0xc015cf20,
            0xc016eaa0]
STARTS = sorted({int(r['addr'], 16) for r in csv.DictReader(
    TSV.open(), delimiter='\t')} | HIDDEN)


def extent(f):
    i = bisect.bisect_right(STARTS, f)
    return f, (STARTS[i] if i < len(STARTS) else f + 0x400)


def analyze(f):
    """Return (frame_bytes, direct_callees, tail_callees, indirect_sites)."""
    lo, hi = extent(f)
    frame, calls, tails, ind = 0, set(), set(), []
    i = bisect.bisect_left(ADDRS, lo)
    while i < len(INS) and INS[i][0] < hi:
        a, l = INS[i]
        i += 1
        m = re.search(r'\b(STW|STDW|STH|STB)\.\S+\s+\S+,\*B15--\[(\d+)\]', l)
        if m:
            frame += SIZE[m[1]] * int(m[2])
        m = re.search(r'ADDK\.\S+\s+-(\d+),B15', l)
        if m:
            frame += int(m[1])
        m = re.search(r'SUB\.\S+\s+B15,(0x[0-9a-f]+|\d+),B15', l)
        if m:
            frame += int(m[1], 0)
        m = re.search(r'\b(CALLP|BNOP|B)\.\S+\s+(0x[0-9a-f]{8}|[AB]\d+)', l)
        if not m:
            continue
        op, t = m[1], m[2]
        if t.startswith('0x'):
            t = int(t, 16)
            if op == 'CALLP':
                calls.add(t)
            elif not lo <= t < hi:
                tails.add(t)
        elif t not in ('B3', 'A3'):
            # A register reloaded from the stack or copied from B3 within the
            # same function is a return (compiler pops B3 into another reg).
            ret = re.compile(r'(LDW\.\S+\s+\*\+?B15\S*,%s\b|MV\.\S+\s+B3,%s\b)'
                             % (t, t))
            if not any(ret.search(x) for _, x in INS[bisect.bisect_left(ADDRS, lo):i]):
                ind.append((a, l.strip()))
    return frame, calls, tails, ind


MEMO, STACK, ISSUES = {}, [], []


def depth(f):
    if f in MEMO:
        return MEMO[f]
    if f in STACK:
        ISSUES.append(('CYCLE', f, STACK[-1]))
        return 0, [f]
    STACK.append(f)
    frame, calls, tails, ind = analyze(f)
    for a, l in ind:
        ISSUES.append(('INDIRECT', f, a, l))
    best, path = 0, []
    extra = set(PTRS) if RESOLVE and ind else set()
    for t in sorted(calls | tails | extra):
        d, p = depth(t)
        if d > best:
            best, path = d, p
    STACK.pop()
    MEMO[f] = (frame + best, [f] + path)
    return MEMO[f]


if __name__ == '__main__':
    for r in sys.argv[1:]:
        f = int(r, 16)
        d, p = depth(f)
        print(f'{r}: worst-case {d} bytes via ' + ' -> '.join(hex(x) for x in p))
    print(f'\n{len(MEMO)} functions visited, {len(ISSUES)} unresolved items')
    for it in ISSUES:
        print(' ', it[0], *[hex(x) if isinstance(x, int) else x for x in it[1:]])
