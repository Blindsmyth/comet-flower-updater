"""Read-only checks against the factory presets resource.

    .venv/Scripts/python.exe tools/g1presets_test.py [res2.bin]

No output files, updater execution or pedal connection.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import g1presets as gp  # noqa: E402

IMG = sys.argv[1] if len(sys.argv) > 1 else "build/fw/res2_45056.bin"
fails = 0


def check(ok, what):
    global fails
    print("  %-62s %s" % (what, "ok" if ok else "FAIL"))
    fails += not ok


def rejects(function, what):
    try:
        function()
    except ValueError:
        check(True, what)
    else:
        check(False, what)


def changed(data, offset):
    output = bytearray(data)
    output[offset] ^= 1
    return bytes(output)


base = open(IMG, "rb").read()
before = gp.records(base)
check(len(before) == 50, "50 records parsed")
rebuilt = (base[:gp.START] + b"".join(r["raw"] for r in before) +
           base[gp.END:])
check(rebuilt == base, "parse/reassemble round trip is byte-identical")
tpl = gp.template(before)
check(tpl["index"] == 41, "template is factory record 41 (Zoom's Empty)")

output = gp.blank(base)
after = gp.records(output)
check(gp.verify(base, output) == 50, "blank output verifies")
check(all(r["ids"] == (0,) * 5 for r in after), "all 250 effect IDs are zero")
check(all(r["raw"][r["edtb"]:r["edtb"] + 120] ==
          (b"" + bytes(23)) * 5 for r in after),
      "all 250 EDTB entries use the factory empty encoding")
check(all(r["chunks"][0][2] == r["chunks"][1][2] == 0 for r in after),
      "no description text left")
check(all(r["raw"] == tpl["raw"] for r in after),
      "every record is byte-identical to Zoom's Empty record 41")
check(output[:512] == base[:512], "splash untouched")
check(output[gp.END:] == base[gp.END:], "region trailer untouched")
check(len(output) == len(base), "region size unchanged")
check(gp.blank(output) == output, "blanking is idempotent")

custom = gp.blank(base, "Clean")
check(gp.verify(base, custom, "Clean") == 50, "custom name verifies")
check(gp.records(custom)[0]["name"] == "Clean", "custom name written")
full = gp.blank(base, "0123456789")
check(gp.verify(base, full, "0123456789") == 50, "ten-character name verifies")

rejects(lambda: gp.blank(base, "elevenchars"), "overlong name rejected")
rejects(lambda: gp.blank(base, "é"), "non-ASCII name rejected")
rejects(lambda: gp.records(base[:-1]), "truncated region rejected")
rejects(lambda: gp.records(changed(base, gp.START + 4)),
        "invalid PTCF length rejected")
rejects(lambda: gp.verify(base, changed(output, 0)),
        "verification detects splash damage")
rejects(lambda: gp.verify(base, changed(output, gp.END)),
        "verification detects trailer damage")
rejects(lambda: gp.verify(base, changed(output, gp.START + 36)),
        "verification detects a nonempty ID")
rejects(lambda: gp.verify(base, changed(output, gp.START + 700)),
        "verification detects allocation-tail damage")

print("all passed" if not fails else "FAILED (%d)" % fails)
sys.exit(1 if fails else 0)
