"""Assign firmware functions to the tasks that reach them (direct calls).

    python tools/fwmap/subsystems.py     (needs build/fw/map/coverage.tsv from coverage.py)

Roots are the SYS/BIOS task entries decoded from the C-initialised task
records (build/codex3/init_c0181b28.bin, recon/15) plus known Swi/Hwi entry
points. Only direct CALLP/B edges between function starts are followed, so
callbacks reached through tables show up as "pointer-only" roots.
Writes build/fw/map/subsystems.tsv and prints per-root coverage.
"""
import bisect
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import coverage  # noqa: E402

TASKS = {
    "MainApp": 0xc0134e10, "UpdateUI": 0xc013c754, "QFuncService": 0xc0161ce4,
    "TunerService": 0xc01674e0, "MIDI": 0xc0129118, "SwitchNrmlSpdRead": 0x118076c0,
    "RepeatEventHandler": 0x11809d40, "PopUpTimeCounter": 0x11809580,
    "RhythmService": 0xc016aac0, "LooperUI": 0xc013b38c, "AD": 0x11809004,
    "PreLoad": 0xc016c0c0, "DataStore": 0xc016d340, "BatteryManagement": 0x11809bd4,
    # Swi / Hwi entry points from recon/16 and recon/17
    "Swi:audio": 0x11818ba0, "Swi:USB": 0xc015b0f0, "Hwi:USB": 0xc011fc8c,
    "Hwi:EDMA-RX": 0xc0151a90, "UsbTask-worker": 0xc0138310, "reset": 0xc0169a20,
}


def main():
    rows = {}
    for line in open(ROOT / "build/fw/map/coverage.tsv", encoding="utf-8"):
        if line.startswith("addr"):
            continue
        f = line.rstrip("\n").split("\t")
        rows[int(f[0], 16)] = {"size": int(f[1]), "recon": f[4], "ptrs": int(f[3])}
    starts = sorted(rows)
    _, _, calls, stubs = coverage.load(str(ROOT / "build/fw/map/main.dis"))

    def owner(a):
        i = bisect.bisect_right(starts, a) - 1
        return starts[i] if i >= 0 else None

    edges = defaultdict(set)
    for tgt, srcs in calls.items():
        tgt = stubs.get(tgt, tgt)
        if tgt not in rows:
            continue
        for src, _ in srcs:
            o = owner(src)
            if o is not None and o != tgt:
                edges[o].add(tgt)

    reach = defaultdict(set)
    for name, root in TASKS.items():
        root = root if root in rows else owner(root)
        q, seen = deque([root]), {root}
        while q:
            f = q.popleft()
            reach[f].add(name)
            for g in edges.get(f, ()):
                if g not in seen:
                    seen.add(g)
                    q.append(g)

    with open(ROOT / "build/fw/map/subsystems.tsv", "w", encoding="utf-8") as out:
        out.write("addr\tsize\trecon\troots\n")
        for a in starts:
            out.write("%08x\t%d\t%s\t%s\n" % (a, rows[a]["size"], rows[a]["recon"],
                                            ",".join(sorted(reach.get(a, ())))))

    def line(label, sel):
        n = len(sel)
        b = sum(rows[a]["size"] for a in sel)
        t = sum(1 for a in sel if rows[a]["recon"])
        tb = sum(rows[a]["size"] for a in sel if rows[a]["recon"])
        print("%-22s %5d fn %7d B   touched %3.0f%% fn, %3.0f%% B"
              % (label, n, b, 100 * t / max(n, 1), 100 * tb / max(b, 1)))

    print("per root (shared library code counts under every root that reaches it):")
    for name in TASKS:
        line(name, [a for a in starts if name in reach.get(a, ())])
    only = defaultdict(list)
    for a in starts:
        r = reach.get(a, set())
        only[next(iter(r)) if len(r) == 1 else ("shared" if r else "unreached")].append(a)
    print("\nexclusive ownership (each function counted once):")
    for name in list(TASKS) + ["shared", "unreached"]:
        if only.get(name):
            line(name, only[name])
    ptr_only = [a for a in only["unreached"] if rows[a]["ptrs"]]
    line("unreached, has ptr", ptr_only)


if __name__ == "__main__":
    main()
