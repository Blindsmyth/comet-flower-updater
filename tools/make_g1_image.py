"""Build a G1X Four effect file-system image: Zoom's factory image plus DIY
effects, installed the way tools/pedal_g1.py installs over USB (file added,
one effect-list entry added with zoom-zt2 and the same checks), but written
as a whole image for update mode instead of through the MIDI file protocol.

    python tools/make_g1_image.py [--clean [--keep STOCK.ZD2]...] [--replace NEW.ZD2]... <factory image> <out image> <effect.ZD2>...

--clean removes every stock effect: its file goes and its effect-list entry
is kept with installed = 0 (how Zoom stores uninstalled effects; the pedal
booted this way after our 2026-10-04 wipe). The directory is compacted.
--keep NAME.ZD2 (with --clean, repeatable) leaves that stock effect installed,
e.g. TS_DRIVE.ZD2 for a stock-vs-CF comparison.
System files (rhythm samples, output EQ, guard file, effect list) stay.
--replace NEW.ZD2 (repeatable) swaps the file of the same name already in the
image for a rebuild of it: same effect id and group, so the effect list stays
as it is and patches using the effect keep working.

The factory image is resource 136 of Zoom's v2.00 G1X FOUR updater
(build/fw/res3_3137536.bin). The result is re-read and checked
(g1fs.check_image) and its effect list re-parsed. Put it on the pedal with
tools/make_fs_restore_updater.py --image <out image>.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
import g1fs  # noqa: E402
import pedal_g1  # noqa: E402  (zoom-zt2 paths, add_entry, set_installed)


def main(base_path, out_path, effects, clean=False, keep=(), replace=()):
    base = open(base_path, "rb").read()
    _, _, ents = g1fs.current_dir(base)
    files = {n: g1fs.read_file(base, f, s) for n, f, s, _, _ in ents}
    flst = files["FLST_SEQ.ZT2"]
    remove = []
    swap = {}
    for p in replace:
        from zd2tools.parser import parse_zd2
        name = os.path.basename(p).upper()
        data = Path(p).read_bytes()
        if name not in files:
            sys.exit("--replace %s: no such file in the image" % name)
        pedal_g1.check_container(data)
        old_h, new_h = parse_zd2(files[name]).header, parse_zd2(data).header
        if (old_h.group_id, old_h.effect_id) != (new_h.group_id, new_h.effect_id):
            sys.exit("--replace %s: effect id differs from the file in the image" % name)
        swap[name] = data
    if clean:
        installed = [n for n, i in ((str(e["effect"]).upper(), int(e["installed"]))
                     for g in __import__("zoomzt2").ZT2.parse(flst)[1] for e in g["effects"]) if i]
        keep = [k.upper() for k in keep]
        for k in keep:
            if k not in installed or k not in files:
                sys.exit("--keep %s: not an installed stock effect" % k)
        for name in installed:
            if name not in keep:
                flst = pedal_g1.set_installed(flst, name, 0)
        stock = [n for n in files if n.endswith(".ZD2")]
        if sorted(stock) != sorted(installed):
            sys.exit("installed entries and effect files differ")
        remove = [n for n in stock if n not in keep]
    add = {}
    for p in effects:
        name = os.path.basename(p).upper()
        data = Path(p).read_bytes()
        pedal_g1.check_container(data)
        flst = pedal_g1.add_entry(flst, p)
        add[name] = data
    # a swapped file is removed and written again under its name (sizes differ, so
    # not in place); compact drops the removed slot, so the directory keeps its count
    img = g1fs.build_image(base, add=dict(add, **swap), remove=list(remove) + list(swap),
                           replace={"FLST_SEQ.ZT2": flst}, compact=clean or bool(swap))
    expect = {n: d for n, d in files.items() if n not in remove and n not in swap}
    expect.update(add)
    expect.update(swap)
    expect["FLST_SEQ.ZT2"] = flst
    n = g1fs.check_image(img, expect)
    listed = pedal_g1.flst_entries(flst)
    import zoomzt2
    inst = sorted(str(e["effect"]).upper() for g in zoomzt2.ZT2.parse(flst)[1]
                  for e in g["effects"] if int(e["installed"]))
    if clean and inst != sorted(list(add) + list(keep)):
        sys.exit("installed set is %s, expected %s" % (inst, sorted(list(add) + list(keep))))
    open(out_path, "wb").write(img)
    print("image %s: %d files (%d removed, %d added: %s, %d replaced: %s); effect list %d entries, "
          "%d installed; verified" % (out_path, n, len(remove), len(add), ", ".join(add),
                                      len(swap), ", ".join(swap), len(listed), len(inst)))


if __name__ == "__main__":
    a = sys.argv[1:]
    clean = "--clean" in a
    a = [x for x in a if x != "--clean"]
    keep, replace = [], []
    while "--keep" in a:
        k = a.index("--keep")
        keep.append(a[k + 1])
        del a[k:k + 2]
    while "--replace" in a:
        k = a.index("--replace")
        replace.append(a[k + 1])
        del a[k:k + 2]
    if len(a) < 2 or (len(a) < 3 and not replace) or (keep and not clean):
        sys.exit(__doc__)
    main(a[0], a[1], a[2:], clean, keep, replace)
