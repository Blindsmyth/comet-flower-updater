"""Build a G1X Four effect file-system image: Zoom's factory image plus DIY
effects, installed the way tools/pedal_g1.py installs over USB (file added,
one effect-list entry added with zoom-zt2 and the same checks), but written
as a whole image for update mode instead of through the MIDI file protocol.

    python tools/make_g1_image.py <factory image> <out image> <effect.ZD2>...

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
import pedal_g1  # noqa: E402  (zoom-zt2 paths, add_entry, flst_entries)


def main(base_path, out_path, effects):
    base = open(base_path, "rb").read()
    _, _, ents = g1fs.current_dir(base)
    files = {n: g1fs.read_file(base, f, s) for n, f, s, _, _ in ents}
    flst = files["FLST_SEQ.ZT2"]
    add = {}
    for p in effects:
        name = os.path.basename(p).upper()
        data = Path(p).read_bytes()
        pedal_g1.check_container(data)
        flst = pedal_g1.add_entry(flst, p)
        add[name] = data
    img = g1fs.build_image(base, add=add, replace={"FLST_SEQ.ZT2": flst})
    expect = dict(files)
    expect.update(add)
    expect["FLST_SEQ.ZT2"] = flst
    n = g1fs.check_image(img, expect)
    listed = pedal_g1.flst_entries(flst)
    for name in add:
        if not any(e[0] == name for e in listed):
            sys.exit("effect list misses " + name)
    open(out_path, "wb").write(img)
    print("image %s: %d files, %d added (%s); effect list %d entries; verified"
          % (out_path, n, len(add), ", ".join(add), len(listed)))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
