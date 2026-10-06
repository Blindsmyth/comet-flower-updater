"""Checks for tools/g1fs.py against the factory image and the pedal backup.

    python tools/g1fs_test.py [factory image] [pedal backup dir]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import g1fs  # noqa: E402

IMG = sys.argv[1] if len(sys.argv) > 1 else "build/fw/res3_3137536.bin"
BAK = sys.argv[2] if len(sys.argv) > 2 else "backup/2026-10-04/files"
fails = 0


def check(ok, what):
    global fails
    print("  %-62s %s" % (what, "ok" if ok else "FAIL"))
    fails += not ok


base = open(IMG, "rb").read()
dirs = g1fs.directories(base)
live = [d for d in dirs if d[3]]
check(len(live) == 1, "exactly one live directory (%d copies)" % len(dirs))
blk, seq, ents = g1fs.current_dir(base)
orig = {n: g1fs.read_file(base, f, s) for n, f, s, _, _ in ents}
check(len(orig) == len(ents), "all %d files read with valid chains" % len(ents))
same = [n for n in orig if os.path.exists(os.path.join(BAK, n))
        and open(os.path.join(BAK, n), "rb").read() == orig[n]]
check(len(same) >= 30, "%d files byte-identical to the pedal backup" % len(same))

img = g1fs.build_image(base)
check(g1fs.check_image(img, orig) == len(orig), "no-op build: same files")
changed = [k for k in range(len(base) // 4096)
           if base[k * 4096:(k + 1) * 4096] != img[k * 4096:(k + 1) * 4096]]
check(all(img[k * 4096:(k + 1) * 4096] == b"\xff" * 4096 for k in changed),
      "no-op build: only unreferenced blocks change (%d, all erased)" % len(changed))
check(blk not in changed, "no-op build: directory block byte-identical")

diy = {"T1.ZD2": os.urandom(10000), "T2.ZD2": os.urandom(4090), "T3.ZD2": os.urandom(1)}
img2 = g1fs.build_image(base, add=diy)
exp = dict(orig)
exp.update(diy)
check(g1fs.check_image(img2, exp) == len(exp), "add 3 files (multi-block, exact block, 1 byte)")
cur = [d[4] for d in g1fs.directories(img2) if d[3]][0]
check(cur != [d[4] for d in dirs if d[3]][0], "cursor moved to the last block written (%d)" % cur)

victim = sorted(orig)[5]
img3 = g1fs.build_image(base, remove=[victim])
exp3 = {n: d for n, d in orig.items() if n != victim}
check(g1fs.check_image(img3, exp3) == len(exp3), "remove %s (marked deleted, blocks freed)" % victim)

flst = bytearray(orig["FLST_SEQ.ZT2"])
flst[100] ^= 1
img4 = g1fs.build_image(base, replace={"FLST_SEQ.ZT2": bytes(flst)})
exp4 = dict(orig)
exp4["FLST_SEQ.ZT2"] = bytes(flst)
check(g1fs.check_image(img4, exp4) == len(exp4), "replace FLST_SEQ.ZT2 in place")

print("all passed" if not fails else "FAILED (%d)" % fails)
sys.exit(1 if fails else 0)
