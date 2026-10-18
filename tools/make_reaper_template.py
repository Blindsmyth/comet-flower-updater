"""Write a REAPER project template whose tracks are named after the pedal's USB channels.

    python tools/make_reaper_template.py [--out "build/reaper/Comet Flower 8ch.RPP"]

Reads tools/ua_channels.json (the same map tools/ua_capture8.py uses): one track per stereo
pair (Pedal Out = inputs 1/2, Bus A = 5/6) and one mono track for every other channel, each
armed with its hardware input, so a recording's files carry the track names. REAPER input
codes (I_RECINPUT): n = mono input n+1, 1024 + n = stereo pair starting at input n+1.
Open the template with the pedal selected as REAPER's audio input device (8 inputs).
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP_FILE = Path(__file__).with_name("ua_channels.json")


def tracks(chmap):
    pairs = {p[0]: p for p in chmap.get("stereo_pairs", [])}
    paired = {c for p in chmap.get("stereo_pairs", []) for c in p[:2]}
    out = []
    for c in chmap["channels"]:
        ch = c["ch"]
        if ch in pairs:
            a, b, name = pairs[ch]
            out.append(("%s (in %d/%d)" % (name, a, b), 1024 + a - 1, 2))
        elif ch not in paired:
            out.append(("%s (in %d)" % (c["label"], ch), ch - 1, 1))
    return out


def rpp(chmap):
    lines = ['<REAPER_PROJECT 0.1 "7.0" 0', "  SAMPLERATE 44100 0 0",
             '  NOTES 0 2', '    |Comet Flower ZG1X4 USB channels, %s' % chmap.get("firmware", ""), "  >"]
    for name, rec_input, nch in tracks(chmap):
        lines += ["  <TRACK", '    NAME "%s"' % name, "    NCHAN 2",
                  # armed, input, monitor off, record mode input, monitor media, preserve PDC, path
                  "    REC 1 %d 0 0 0 0 0" % rec_input, "  >"]
    lines.append(">")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "build" / "reaper" / "Comet Flower 8ch.RPP"))
    ap.add_argument("--map", default=str(MAP_FILE), help="channel map JSON (default tools/ua_channels.json)")
    a = ap.parse_args()
    chmap = json.loads(Path(a.map).read_text())
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rpp(chmap))
    print("wrote", out)
    for name, rec_input, nch in tracks(chmap):
        print("  %-26s input code %d" % (name, rec_input))


if __name__ == "__main__":
    main()
