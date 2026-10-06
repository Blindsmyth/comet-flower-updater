"""Wrap AIS sections into an ELF32 C6000 file so dis6x can disassemble them.
mkelf.py <ais.bin> <out.elf> <code_addr,code_addr,...>"""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ais import sections  # noqa: E402

src, out = sys.argv[1], sys.argv[2]
code = set(int(x, 16) for x in sys.argv[3].split(","))
# .c6xabi.attributes of a stock G1 effect, so dis6x knows the C674x ISA
attrs = bytes.fromhex(
    "41290000005449000122000000054c696e6b65720008080a040c058002088202028402028e"
    "02029002031400000063367861626900010900000004080601")
d, secs = sections(src)
secs = [s for s in secs if s[0] != "entry"]

shstr = b"\0"
names = []
for a, n, o in secs:
    names.append(len(shstr))
    shstr += f"s{a:08x}".encode() + b"\0"
attrname = len(shstr); shstr += b".c6xabi.attributes\0"
shname = len(shstr); shstr += b".shstrtab\0"


def pad(b):
    return b + bytes((-len(b)) % 4)


base = 52
body = b""
offs = []
for a, n, o in secs:
    offs.append(base + len(body))
    body = pad(body + d[o:o + n])
attroff = base + len(body); body = pad(body + attrs)
stroff = base + len(body); body = pad(body + shstr)
shoff = base + len(body)

sh = bytes(40)
for i, (a, n, o) in enumerate(secs):
    flags = 0x2 | (0x4 if a in code else 0x1)
    sh += struct.pack("<10I", names[i], 1, flags, a, offs[i], n, 0, 0, 32, 0)
sh += struct.pack("<10I", attrname, 0x70000003, 0, 0, attroff, len(attrs), 0, 0, 1, 0)
sh += struct.pack("<10I", shname, 3, 0, 0, stroff, len(shstr), 0, 0, 1, 0)
nsh = len(secs) + 3
hdr = b"\x7fELF\x01\x01\x01" + bytes(9) + struct.pack(
    "<HHIIIIIHHHHHH", 2, 140, 1, 0, 0, shoff, 0, 52, 0, 0, 40, nsh, nsh - 1)
open(out, "wb").write(hdr + body + sh)
