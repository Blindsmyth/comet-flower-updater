"""List stack adjustments and outgoing calls for selected kernel root functions."""
import re, csv, bisect
from pathlib import Path

ins = []
for l in Path('build/fw/map/main.dis').read_text().splitlines():
    m = re.match(r'^([0-9a-f]{8})\s+[0-9a-f]{4,8}\s+(.*)', l)
    if m:
        ins.append((int(m[1], 16), m[2]))

starts = sorted(
    set(int(r['addr'], 16) for r in csv.DictReader(
        Path('build/fw/map/subsystems.tsv').open(), delimiter='\t'))
    | {0xc015a020, 0xc015a2a0, 0xc015de40, 0xc015e060, 0xc0162a60,
       0xc0162d60, 0xc0155dc0, 0xc0169170, 0xc0160820})

roots = [0xc0169fc0, 0xc016ba40, 0xc016bac0, 0xc016ea00, 0xc016ea20,
         0xc016e980, 0xc016e9a0, 0xc0167be0, 0xc016b7c0, 0xc0164380,
         0xc0163fc0, 0xc01690c0, 0xc0160660, 0xc0149b60, 0xc0149c14,
         0xc01489a0, 0xc01485a0, 0xc01485b8]

for f in roots:
    end = starts[bisect.bisect_right(starts, f)]
    print('\nFUNC', hex(f), hex(end))
    for a, l in ins:
        if not f <= a < end:
            continue
        if 'B15--' in l or re.search(r'ADDK\.\S+\s+-\d+,B15|SUB\.\S+\s+B15,', l):
            print(hex(a), l)
        m = re.search(r'\b(?:CALLP|B|BNOP)\.\S+\s+(0x[0-9a-f]{8}|[AB]\d+)', l)
        if m:
            if m[1].startswith('0x') and f <= int(m[1], 16) < end:
                continue
            if m[1] in ['B3', 'A3']:
                continue
            print(hex(a), l)
