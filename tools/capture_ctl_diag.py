#!/usr/bin/env python3
"""Receive-only capture of the diag build's MIDI readback (owner-run).

Opens a MIDI INPUT port (never an output), records Control Change messages on
channel 1, and stops at the readback end marker (CC119=1) or after --timeout
seconds. Writes the raw [control, value] list to --out (JSON) and prints the
decoded report. Trigger the readback on the pedal with both footswitches
pressed together (event 4) while it runs the --diag-teardown build.

  python tools/capture_ctl_diag.py --port "ZOOM" --out build/diag_capture.json
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decode_ctl_diag as dcd  # noqa: E402


def main():
    import mido
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", default="", help="substring of the MIDI input port name "
                    "(default: the pedal, 'ZOOM G...' or 'Comet Flower...')")
    ap.add_argument("--out", type=Path, default=Path("build/diag_capture.json"))
    ap.add_argument("--timeout", type=float, default=60.0)
    a = ap.parse_args()
    from pedal_ports import is_pedal_port
    names = [n for n in mido.get_input_names()
             if (a.port.lower() in n.lower() if a.port else is_pedal_port(n))]
    if not names:
        sys.exit(f"no MIDI input port matching {a.port!r}; available: {mido.get_input_names()}")
    pairs, begun = [], False
    deadline = time.monotonic() + a.timeout
    print(f"listening on {names[0]}; press both footswitches on the pedal")
    with mido.open_input(names[0]) as port:
        while time.monotonic() < deadline:
            for msg in port.iter_pending():
                if msg.type == "control_change" and msg.channel == 0:
                    pairs.append([msg.control, msg.value])
                    begun |= msg.control == dcd.CC_BEGIN and msg.value == 127
                    if begun and msg.control == dcd.CC_BEGIN and msg.value == 1:
                        deadline = 0
            time.sleep(0.005)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(pairs))
    print(f"saved {len(pairs)} CCs to {a.out}")
    try:
        print(dcd.format_diag_text(dcd.decode_cc_stream(pairs)))
    except ValueError as e:
        sys.exit(f"decode failed: {e}")


if __name__ == "__main__":
    main()
