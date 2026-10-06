"""Build a G1X Four effect file-system image: Zoom's factory image plus DIY
effects, installed the way tools/pedal_g1.py installs over USB (file added,
one effect-list entry added with zoom-zt2 and the same checks), but written
as a whole image for update mode instead of through the MIDI file protocol.

    python tools/make_g1_image.py [--clean] <factory image> <out image> <effect.ZD2>...

--clean removes every stock effect: its file goes and its effect-list entry
is kept with installed = 0 (how Zoom stores uninstalled effects; the pedal
booted this way after our 2026-10-04 wipe). The directory is compacted.
System files (rhythm samples, output EQ, guard file, effect list) stay.

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


def main(base_path, out_path, effects, clean=False):
    base = open(base_path, "rb").read()
    _, _, ents = g1fs.current_dir(base)
    files = {n: g1fs.read_file(base, f, s) for n, f, s, _, _ in ents}
    flst = files["FLST_SEQ.ZT2"]
    remove = []
    if clean:
        installed = [n for n, i in ((str(e["effect"]).upper(), int(e["installed"]))
                     for g in __import__("zoomzt2").ZT2.parse(flst)[1] for e in g["effects"]) if i]
        for name in installed:
            flst = pedal_g1.set_installed(flst, name, 0)
        remove = [n for n in files if n.endswith(".ZD2")]
        if sorted(remove) != sorted(installed):
            sys.exit("installed entries and effect files differ")
    add = {}
    for p in effects:
        name = os.path.basename(p).upper()
        data = Path(p).read_bytes()
        pedal_g1.check_container(data)
        flst = pedal_g1.add_entry(flst, p)
        add[name] = data
    img = g1fs.build_image(base, add=add, remove=remove,
                           replace={"FLST_SEQ.ZT2": flst}, compact=clean)
    expect = {n: d for n, d in files.items() if n not in remove}
    expect.update(add)
    expect["FLST_SEQ.ZT2"] = flst
    n = g1fs.check_image(img, expect)
    listed = pedal_g1.flst_entries(flst)
    import zoomzt2
    inst = sorted(str(e["effect"]).upper() for g in zoomzt2.ZT2.parse(flst)[1]
                  for e in g["effects"] if int(e["installed"]))
    if inst != sorted(add) + ([] if clean else sorted(n for n in files if n.endswith(".ZD2"))) \
            and clean:
        sys.exit("installed set is %s, expected %s" % (inst, sorted(add)))
    open(out_path, "wb").write(img)
    print("image %s: %d files (%d removed, %d added: %s); effect list %d entries, "
          "%d installed; verified" % (out_path, n, len(remove), len(add), ", ".join(add),
                                      len(listed), len(inst)))


if __name__ == "__main__":
    a = sys.argv[1:]
    clean = "--clean" in a
    a = [x for x in a if x != "--clean"]
    if len(a) < 3:
        sys.exit(__doc__)
    main(a[0], a[1], a[2:], clean)
