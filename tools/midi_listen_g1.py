#!/usr/bin/env python3
"""Print every MIDI message the G1X Four sends, to see which controls it reports.

  python tools/midi_listen_g1.py [--no-editor] [--log FILE]

Step 1 of the MIDI-controller work (recon/10): press every footswitch and
button, turn every knob, move the expression pedal, and see what arrives.

Sends only Zoom's PC-mode on (52) and editor-mode on (50) commands, the
ones Zoom's own editor sends on connect, and their off commands (51, 53) on
exit. Writes no file, patch or setting. Keep AUTO SAVE off as always.
Ctrl+C to stop. Close ToneLib / browser editors first (they hold the port).
"""
import argparse
import sys
import time

import mido

PREFIX = "ZOOM G"
HDR = [0x52, 0x00, 0x6E]          # Zoom, device 0, G1 Four family


def find(names):
    hits = [n for n in names if n.startswith(PREFIX)]
    if not hits:
        sys.exit(f"no '{PREFIX}' MIDI port (pedal unplugged, or ToneLib holding it?)")
    return hits[0]


def describe(msg):
    if msg.type != "sysex":
        return str(msg)
    d = list(msg.data)
    s = " ".join(f"{b:02x}" for b in d)
    if d[:3] == HDR and len(d) > 3:
        return f"zoom cmd {d[3]:02x}: {s}"
    return f"sysex: {s}"


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-editor", action="store_true",
                    help="listen only; send nothing (shows what the pedal sends unasked)")
    ap.add_argument("--log", help="also append the lines to this file")
    a = ap.parse_args(argv)

    inp = mido.open_input(find(mido.get_input_names()))
    out = None if a.no_editor else mido.open_output(find(mido.get_output_names()))
    log = open(a.log, "a") if a.log else None

    def show(line):
        print(line, flush=True)
        if log:
            log.write(line + "\n")
            log.flush()

    def cmd(c):
        out.send(mido.Message("sysex", data=HDR + [c]))

    t0 = time.monotonic()
    try:
        if out:
            cmd(0x52)                 # PC mode on
            time.sleep(0.2)
            cmd(0x50)                 # editor mode on
            show("sent PC-mode on + editor-mode on")
        show("listening; Ctrl+C to stop")
        while True:
            for msg in inp.iter_pending():
                show(f"{time.monotonic() - t0:8.3f}  {describe(msg)}")
            time.sleep(0.005)
    except KeyboardInterrupt:
        pass
    finally:
        if out:
            cmd(0x51)                 # editor mode off
            time.sleep(0.1)
            cmd(0x53)                 # PC mode off
            out.close()
            show("sent editor-mode off + PC-mode off")
        inp.close()


if __name__ == "__main__":
    main(sys.argv[1:])
