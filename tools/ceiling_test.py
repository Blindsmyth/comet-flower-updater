#!/usr/bin/env python3
"""CPU ceiling test over the CF Probe link (TEST firmware 0.33+ with the CPU meter).

  python tools/ceiling_test.py watch [--csv run.csv] [--every 0.25]
  python tools/ceiling_test.py set <slot 1-5> <param> <value>        (EXPERIMENTAL)
  python tools/ceiling_test.py ramp <slot 1-5> [--param 2] [--from 0] [--to 100] [--step 5]
                                    [--hold 2.0] [--csv run.csv]      (EXPERIMENTAL)

watch: reads the meter record (ua_cpu, 0xc01a8020: magic "CPUM", seq, busy mean,
busy peak, mean cycles per slot) over MIDI about four times a second and prints
peak % (the number on the edit page), mean % and each slot's mean kcycles. You turn
PROBE's Load by hand. It stops by itself and reports when the pedal freezes:
  - AUDIO STALL: MIDI still answers but seq stops counting (the audio loop is stuck);
  - NO REPLY: the pedal stops answering MIDI (whole pedal frozen).
Ctrl+C stops it normally; both print the highest reading seen and the last readings.

set / ramp: turn a knob from the computer with Zoom's parameter-edit SysEx
(F0 52 00 6E 64 03 00 <slot-1> <param> <lo7> <hi7> F7, after editor mode on, 50).
NOT yet confirmed on this pedal: try `set` once first and check the knob moves on
the screen. Param 0 = on/off, 1 = effect type (do not ramp it), 2.. = knobs (Load = 2
on PROBE 10/30, assumed). ramp steps the value, holds each step, logs the meter and
stops at the first freeze. Keep AUTO SAVE off: the edit stays in the live patch only.

Percent = busy cycles * 100 / 132354 (one 16-frame block at 364.8 MHz), as the meter.
"""
import argparse
import csv
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cf_probe  # noqa: E402

CPU_ADDR, CPU_LEN = 0xC01A8020, 36
MAGIC = 0x4D555043
BLOCK_CYCLES = 132354
ZOOM = [0x52, 0x00, 0x6E]


class NoReply(Exception):
    pass


class Link(cf_probe.Link):
    def call(self, msg):
        try:
            return super().call(msg)
        except SystemExit as e:
            raise NoReply(str(e))

    def zoom(self, *data):
        self.out.send(self.mido.Message("sysex", data=ZOOM + list(data)))


def read_cpu(link):
    d = link.peek(CPU_ADDR, CPU_LEN)
    magic, seq, avg, peak, *slots = struct.unpack("<9I", d)
    if magic != MAGIC:
        return None
    return {"seq": seq, "avg": avg * 100.0 / BLOCK_CYCLES, "peak": peak * 100.0 / BLOCK_CYCLES,
            "slots": [s / 1000.0 for s in slots]}


def line(t, r, extra=""):
    return "%7.2fs  peak %5.1f%%  mean %5.1f%%  slots %s%s" % (
        t, r["peak"], r["avg"], " ".join("%5.1fk" % s for s in r["slots"]), extra)


class Monitor:
    """Reads the meter; raises NoReply / returns 'stall' on a freeze."""

    def __init__(self, link, csv_path=None, label="value"):
        self.link, self.t0, self.hist, self.best = link, time.time(), [], None
        self.last_seq, self.same = None, 0
        self.w = None
        if csv_path:
            self.f = open(csv_path, "w", newline="")
            self.w = csv.writer(self.f)
            self.w.writerow(["t", label, "seq", "peak_pct", "mean_pct"] + ["slot%d_k" % k for k in range(1, 6)])

    def sample(self, value="", show=True):
        r = read_cpu(self.link)
        t = time.time() - self.t0
        if r is None:
            print("%7.2fs  meter record not live (magic missing): is 0.33+ flashed?" % t)
            return "dead"
        stall = self.last_seq is not None and r["seq"] == self.last_seq
        self.same = self.same + 1 if stall else 0
        self.last_seq = r["seq"]
        self.hist = (self.hist + [(t, value, r)])[-12:]
        if self.best is None or r["peak"] > self.best[2]["peak"]:
            self.best = (t, value, r)
        if self.w:
            self.w.writerow(["%.3f" % t, value, r["seq"], "%.2f" % r["peak"], "%.2f" % r["avg"]]
                            + ["%.2f" % s for s in r["slots"]])
            self.f.flush()
        if show:
            print(line(t, r, "  [%s]" % value if value != "" else ""), flush=True)
        return "stall" if self.same >= 3 else "ok"

    def report(self, why):
        print("\n== %s ==" % why)
        if self.best:
            t, v, r = self.best
            print("highest reading: " + line(t, r, "  [%s]" % v if v != "" else ""))
        if self.hist:
            print("last readings before the stop:")
            for t, v, r in self.hist[-6:]:
                print("  " + line(t, r, "  [%s]" % v if v != "" else ""))


def watch(a):
    link = Link(timeout=1.5)
    m = Monitor(link, a.csv)
    print("watching the meter; turn Load up by hand. Ctrl+C to stop.")
    try:
        while True:
            s = m.sample()
            if s == "dead":
                return
            if s == "stall":
                m.report("AUDIO STALL: MIDI answers but the audio loop stopped counting")
                return
            time.sleep(a.every)
    except NoReply:
        m.report("NO REPLY: the pedal stopped answering MIDI (frozen)")
    except KeyboardInterrupt:
        m.report("stopped")


def set_param(link, slot, param, value):
    link.zoom(0x64, 0x03, 0x00, slot - 1, param, value & 0x7F, (value >> 7) & 0x7F)


def editor(link, on):
    link.zoom(0x50 if on else 0x51)
    time.sleep(0.1)


def cmd_set(a):
    link = Link()
    editor(link, True)
    set_param(link, a.slot, a.param, a.value)
    print("sent slot %d param %d = %d; check the knob on the pedal screen" % (a.slot, a.param, a.value))
    editor(link, False)


def ramp(a):
    if a.param == 1:
        sys.exit("param 1 is the effect type; refusing to ramp it")
    link = Link(timeout=1.5)
    m = Monitor(link, a.csv, label="param%d" % a.param)
    editor(link, True)
    why = "ramp finished, no freeze"
    try:
        for v in range(a.start, a.to + 1, a.step):
            set_param(link, a.slot, a.param, v)
            end = time.time() + a.hold
            while time.time() < end:
                s = m.sample(v)
                if s == "dead":
                    return
                if s == "stall":
                    why = "AUDIO STALL at value %d" % v
                    raise StopIteration
                time.sleep(0.25)
    except StopIteration:
        pass
    except NoReply:
        why = "NO REPLY (pedal frozen) at value %s" % (m.hist[-1][1] if m.hist else "?")
    except KeyboardInterrupt:
        why = "stopped"
    finally:
        try:
            editor(link, False)
        except Exception:
            pass
    m.report(why)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch")
    w.add_argument("--csv")
    w.add_argument("--every", type=float, default=0.25)
    s = sub.add_parser("set")
    s.add_argument("slot", type=int, choices=range(1, 6))
    s.add_argument("param", type=int)
    s.add_argument("value", type=int)
    r = sub.add_parser("ramp")
    r.add_argument("slot", type=int, choices=range(1, 6))
    r.add_argument("--param", type=int, default=2)
    r.add_argument("--from", dest="start", type=int, default=0)
    r.add_argument("--to", type=int, default=100)
    r.add_argument("--step", type=int, default=5)
    r.add_argument("--hold", type=float, default=2.0, help="seconds per step (the peak window is ~0.74 s)")
    r.add_argument("--csv")
    a = ap.parse_args(argv)
    {"watch": watch, "set": cmd_set, "ramp": ramp}[a.cmd](a)


if __name__ == "__main__":
    main()
