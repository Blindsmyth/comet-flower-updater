"""Build the single-file Comet Flower installer: the intro with the updater inside.

    .venv/Scripts/python.exe -m tools.cf_intro.build_exe --updater "<Comet Flower updater .exe>"
        [--out-dir build/cf_installer]

Packs the intro (tools/cf_intro/intro.py), the pre-rendered chip tune and the
given updater (with its SHA-256 in payload.json) into one windowed .exe with
PyInstaller. At [ INSTALL ] the intro unpacks the updater to %TEMP%, checks the
hash, and opens it; flashing is still the updater's Execute button.

The packed updater carries Zoom's code (the owner's own v2.00 updater, patched):
this .exe is for the owner's use. A distributable version must build the
updater on the user's machine from their own official updater (Phase E).
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = "Comet Flower G1X4 Installer"


def make_icon(path):
    """A small CF badge in the intro's colours (multi-size .ico)."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((8, 8, 248, 248), 40, fill=(3, 3, 24, 255), outline=(90, 90, 255, 255), width=10)
    try:
        font = ImageFont.truetype("consolab.ttf", 120)
    except OSError:
        font = ImageFont.load_default()
    d.text((128, 132), "CF", font=font, fill=(255, 64, 200, 255), anchor="mm")
    im.save(path, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return path


def build(updater, out_dir):
    updater = Path(updater).resolve()
    out_dir = Path(out_dir).resolve()
    work = ROOT / "build" / "cf_installer_work"
    payload = work / "payload"
    if payload.exists():
        shutil.rmtree(payload)
    payload.mkdir(parents=True)

    from tools.cf_intro import music
    tune = music.ensure(ROOT / "build" / "cf_intro" / "cf_tune.wav")
    shutil.copyfile(tune, payload / "cf_tune.wav")
    shutil.copyfile(updater, payload / updater.name)
    digest = hashlib.sha256(updater.read_bytes()).hexdigest()
    (payload / "payload.json").write_text(json.dumps({"updater": updater.name, "sha256": digest}))
    icon = make_icon(work / "cf.ico")

    entry = work / "cf_installer_entry.py"
    entry.write_text("from tools.cf_intro.intro import main\n\nmain()\n")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile",
           "--windowed", "--name", NAME, "--icon", str(icon),
           "--paths", str(ROOT), "--add-data", "%s;payload" % payload,
           "--exclude-module", "numpy", "--exclude-module", "PIL",
           "--distpath", str(out_dir), "--workpath", str(work / "pyi"),
           "--specpath", str(work), str(entry)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        sys.exit("PyInstaller failed:\n" + r.stdout[-3000:] + r.stderr[-3000:])
    exe = out_dir / (NAME + ".exe")
    print("wrote %s (%.1f MB); packed updater %s sha256 %s"
          % (exe, exe.stat().st_size / 1e6, updater.name, digest[:16]))
    return exe


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--updater", required=True)
    ap.add_argument("--out-dir", default=str(ROOT / "build" / "cf_installer"))
    a = ap.parse_args(argv)
    build(a.updater, a.out_dir)


if __name__ == "__main__":
    main()
