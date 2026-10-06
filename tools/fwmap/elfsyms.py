#!/usr/bin/env python3
"""Read data symbols from a stock effect's DATA.elf (from `zd2 extract`).

  elfsyms.py list <DATA.elf>                  all symbols: name, section, offset, size
  elfsyms.py dump <DATA.elf> <symbol> [f32|f64|i32|u8]   values of one symbol
  elfsyms.py ovs  <DATA.elf>                  the *_OVS_COE_bn/an filter: same as
                                              the shared 5-drive filter? -3/-60 dB?

The OVS filter is y[n] = sum b[k] x[n-k] - sum a[k] y[n-k]: the stored `an`
values are the feedback terms with the sign that must be NEGATED to get the
standard denominator 1 + a1 z^-1 + ... (checked 2026-10-06: gives -3 dB at
0.1194 and -60 dB at 0.2557 of the oversampled rate for the shared filter).
"""
import sys

import numpy as np
from elftools.elf.elffile import ELFFile

def symbols(path):
    elf = ELFFile(open(path, "rb"))
    out = []
    for s in elf.get_section_by_name(".symtab").iter_symbols():
        if not s.name or s.name.startswith(".") or s["st_shndx"] in ("SHN_UNDEF", "SHN_ABS"):
            continue
        sec = elf.get_section(s["st_shndx"])
        out.append((s.name, sec.name, s["st_value"] - sec["sh_addr"], s["st_size"], sec))
    return out


def raw(path, name):
    for n, secname, off, size, sec in symbols(path):
        if n == name:
            if sec["sh_type"] == "SHT_NOBITS":
                return None
            return sec.data()[off:off + size]
    sys.exit("no symbol %s" % name)


def response(b, a_stored):
    a = np.r_[1.0, -np.asarray(a_stored, float)]
    w = np.linspace(0, 0.5, 40001)
    z = np.exp(-2j * np.pi * w)
    h = np.abs(np.polyval(np.asarray(b, float)[::-1], z) / np.polyval(a[::-1], z))
    db = 20 * np.log10(h / h[0])
    return w[np.argmax(db < -3)], w[np.argmax(db < -60)] if (db < -60).any() else None


def main(a):
    if a[:1] == ["list"]:
        for n, secname, off, size, _ in sorted(symbols(a[1]), key=lambda t: (t[1], t[2])):
            print("%-48s %-10s +0x%05x %6d" % (n, secname, off, size))
    elif a[:1] == ["dump"]:
        fmt = a[3] if len(a) > 3 else "f32"
        d = raw(a[1], a[2])
        if d is None:
            sys.exit("%s is in .bss (no stored data)" % a[2])
        dt = {"f32": "<f4", "f64": "<f8", "i32": "<i4", "u8": "u1"}[fmt]
        v = np.frombuffer(d[:len(d) - len(d) % np.dtype(dt).itemsize], dt)
        print(" ".join("%.7g" % x if fmt[0] == "f" else str(x) for x in v))
    elif a[:1] == ["ovs"]:
        syms = [s[0] for s in symbols(a[1])]
        bn = [s for s in syms if s.endswith("OVS_COE_bn")]
        an = [s for s in syms if s.endswith("OVS_COE_an")]
        if not (bn and an):
            print("no *_OVS_COE_bn/an symbols")
            return
        b = np.frombuffer(raw(a[1], bn[0]), "<f4")
        an_v = np.frombuffer(raw(a[1], an[0]), "<f4")
        shared = np.array([0.00088655448, 0.0037563879, 0.0069437949,
                           0.0069437949, 0.0037563879, 0.00088655448], "<f4")
        same = len(b) == 6 and np.array_equal(b, shared)
        c3, c60 = response(b, an_v)
        print("%s / %s: %d b + %d a values; identical to the shared 5-drive filter: %s"
              % (bn[0], an[0], len(b), len(an_v), same))
        print("b =", " ".join("%.8g" % x for x in b))
        print("a (stored) =", " ".join("%.8g" % x for x in an_v))
        print("-3 dB at %.4f, -60 dB at %s of the filter's own sample rate"
              % (c3, "%.4f" % c60 if c60 is not None else "never"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
