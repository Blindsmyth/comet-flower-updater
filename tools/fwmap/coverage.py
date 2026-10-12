"""Firmware map coverage: which functions do the recon notes explain?

    python tools/fwmap/coverage.py [build/fw/map/main.dis] [--out build/fw/map/coverage]

Functions are found from CALLP/B targets and from data words that point at
an instruction start, so this is a lower bound on the real function set.
A function counts as "touched" when any recon/*.md file names an address
inside it. That is a coverage measure, not proof that it is understood.

Writes <out>.tsv (one row per function) and prints a summary plus the
largest untouched functions ranked by number of callers.
"""
import argparse
import bisect
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
INS = re.compile(r"^([0-9a-f]{8})\s+([0-9a-f]{4}|[0-9a-f]{8})\s+(\|\|)?\s*(\[[!AB0-9 ]+\])?\s*(\S+)\s*(.*)$")
WORD = re.compile(r"^([0-9a-f]{8})\s+([0-9a-f]{8})\s+\.word\s+0x([0-9a-f]{8})")
HEXADDR = re.compile(r"\b(?:0x)?((?:c0|11|c8)[0-9a-f]{6})\b", re.I)


def load(dis_path):
    """Instruction addresses, data words, branch/call sites, and the jump
    stubs (MVK/MVKH Bn + B Bn) mapped to their targets."""
    ins, words, calls = [], [], defaultdict(list)
    stubs, window = {}, []
    for line in open(dis_path, encoding="utf-8", errors="replace"):
        m = INS.match(line)
        if m and m[5] != ".word" and not m[5].startswith(".fphead"):
            a = int(m[1], 16)
            ins.append(a)
            window = (window + [(a, m[5], m[6].strip())])[-3:]
            if len(window) == 3 and m[5].startswith("B.") and m[6].strip() == "B31":
                (a0, o0, r0), (a1, o1, r1) = window[0], window[1]
                lo = re.match(r"(0x[0-9a-f]+),B31$", r0)
                hi = re.match(r"(0x[0-9a-f]+),B31$", r1)
                if o0.startswith("MVK.") and o1.startswith("MVKH") and lo and hi and a1 == a0 + 4:
                    stubs[a0] = (int(hi[1], 16) & 0xffff0000) | (int(lo[1], 16) & 0xffff)
            t = re.search(r"0x([0-9a-f]{8})", m[6])
            if t and (m[5].startswith("CALLP") or m[5].startswith("B")):
                calls[int(t[1], 16)].append((a, m[5].startswith("CALLP")))
            continue
        w = WORD.match(line)
        if w:
            words.append((int(w[1], 16), int(w[3], 16)))
    return sorted(set(ins)), words, calls, stubs


def section_ends():
    import sys
    sys.path.insert(0, str(ROOT / "build/fw/map"))
    import ais
    _, secs = ais.sections(str(ROOT / "build/fw/res1_493412.bin"))
    return sorted((a, a + n) for a, n, _ in secs if not isinstance(a, str))


def strings_by_addr():
    out = {}
    p = ROOT / "build/fw/map/strings.txt"
    for line in open(p, encoding="utf-8", errors="replace"):
        parts = line.rstrip("\n").split(" ", 1)
        if len(parts) == 2:
            try:
                out[int(parts[0], 16)] = parts[1]
            except ValueError:
                pass
    return out


def recon_mentions():
    hits = defaultdict(set)
    for md in sorted((ROOT / "recon").glob("*.md")):
        for m in HEXADDR.finditer(md.read_text(encoding="utf-8", errors="replace")):
            hits[int(m[1], 16)].add(md.stem.split("_")[0])
    return hits


def map_names():
    """addr -> confidence from the firmware-map tables in recon/map/*.md."""
    out = {}
    for md in sorted((ROOT / "recon/map").glob("*.md")):
        for line in open(md, encoding="utf-8", errors="replace"):
            if not line.startswith("| "):
                continue
            parts = [p.strip().strip("`") for p in re.split(r"(?<!\|)\|(?!\|)", line)]
            if len(parts) < 6 or not re.fullmatch(r"[0-9a-f]{8}", parts[1]):
                continue
            if not re.fullmatch(r"[A-Za-z_][\w.$]*", parts[2]):
                continue
            conf = next((part for part in parts[4:-1]
                         if part in ("confirmed", "likely", "guess")), None)
            if conf and parts[2] != "unknown":
                out[int(parts[1], 16)] = conf
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dis", nargs="?", default=str(ROOT / "build/fw/map/main.dis"))
    ap.add_argument("--out", default=str(ROOT / "build/fw/map/coverage"))
    a = ap.parse_args()

    ins, words, calls, stubs = load(a.dis)
    secs = section_ends()
    insset = set(ins)
    starts = {t for t, srcs in calls.items() if t in insset and any(c for _, c in srcs)}
    ptr_refs = defaultdict(list)
    for at, v in words:
        if v in insset:
            ptr_refs[v].append(at)
            starts.add(v)
    # Fold jump stubs into their targets: callers of a stub count as callers.
    for st, tgt in stubs.items():
        if st in starts:
            calls[tgt].extend(calls.get(st, []))
            ptr_refs[tgt].extend(ptr_refs.get(st, []))
            if tgt in insset:
                starts.add(tgt)
    starts = sorted(x for x in starts if x not in stubs)

    def sec_end(x):
        for lo, hi in secs:
            if lo <= x < hi:
                return hi
        return x + 4
    # Every jump stub is also a boundary, so a run of stubs is not swallowed
    # by the function before it (recon/map/00, c016ec20).
    bounds = sorted(set(starts) | set(stubs))

    def next_bound(x):
        i = bisect.bisect_right(bounds, x)
        return bounds[i] if i < len(bounds) else 1 << 32
    ends = [min(next_bound(s), sec_end(s)) for s in starts]

    strs = strings_by_addr()
    mentions = recon_mentions()
    mention_keys = sorted(mentions)

    # string references per function: MVK/MVKH pairs resolved per register
    fn_strings = defaultdict(set)
    last = {}
    for line in open(a.dis, encoding="utf-8", errors="replace"):
        m = INS.match(line)
        if not m:
            continue
        addr = int(m[1], 16)
        mk = re.match(r"MVK\.\S+", m[5]) and re.match(r"(-?0x[0-9a-f]+|-?\d+),([AB]\d+)$", m[6].strip())
        if mk and not m[5].startswith("MVKH"):
            last[mk[2]] = int(mk[1], 0) & 0xffff
        elif mk and m[5].startswith("MVKH") and mk[2] in last:
            v = (int(mk[1], 0) & 0xffff0000) | last[mk[2]]
            if v in strs:
                i = bisect.bisect_right(starts, addr) - 1
                if i >= 0:
                    fn_strings[starts[i]].add(strs[v][:24])

    rows = []
    for s, e in zip(starts, ends):
        lo = bisect.bisect_left(mention_keys, s)
        hi = bisect.bisect_left(mention_keys, e)
        files = set()
        for k in mention_keys[lo:hi]:
            files |= mentions[k]
        callers = calls.get(s, [])
        rows.append({
            "addr": s, "size": e - s,
            "callers": len({c for c, _ in callers}),
            "ptrs": len(ptr_refs.get(s, [])),
            "recon": ",".join(sorted(files)),
            "strings": "; ".join(sorted(fn_strings.get(s, ())))[:120],
        })

    with open(a.out + ".tsv", "w", encoding="utf-8") as f:
        f.write("addr\tsize\tcallers\tptr_refs\trecon\tstrings\n")
        for r in rows:
            f.write("%08x\t%d\t%d\t%d\t%s\t%s\n" % (r["addr"], r["size"], r["callers"],
                                                    r["ptrs"], r["recon"], r["strings"]))

    def summary(sel, label):
        n = len(sel)
        t = [r for r in sel if r["recon"]]
        b = sum(r["size"] for r in sel)
        tb = sum(r["size"] for r in t)
        print("%-22s %5d functions, %5d touched (%3.0f%%); %7d bytes, %3.0f%% touched"
              % (label, n, len(t), 100 * len(t) / max(n, 1), b, 100 * tb / max(b, 1)))

    print("functions found: %d (CALLP targets + code pointers in data; %d jump stubs folded)"
          % (len(rows), len(stubs)))
    named = map_names()
    conf = defaultdict(int)
    for r in rows:
        if r["addr"] in named:
            conf[named[r["addr"]]] += 1
    print("named in recon/map: %d of %d (confirmed %d, likely %d, guess %d)"
          % (sum(conf.values()), len(rows), conf["confirmed"], conf["likely"], conf["guess"]))
    summary(rows, "all")
    summary([r for r in rows if r["addr"] >= 0xc0000000], "SDRAM (c0...)")
    summary([r for r in rows if r["addr"] < 0xc0000000], "L2 (118...)")
    print("\nlargest untouched functions by callers (addr size callers ptrs strings):")
    for r in sorted((r for r in rows if not r["recon"]),
                    key=lambda r: (-(r["callers"] + r["ptrs"]), -r["size"]))[:40]:
        print("  %08x %6d %4d %3d  %s" % (r["addr"], r["size"], r["callers"], r["ptrs"], r["strings"]))


if __name__ == "__main__":
    main()
