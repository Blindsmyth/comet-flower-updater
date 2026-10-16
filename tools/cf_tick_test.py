"""Guided tick-period test (receive-only): no stopwatch, no button timing.

    .venv/Scripts/python.exe tools/cf_tick_test.py [--seconds 90] [--port NAME]

The diag build sends a timing beacon every 1000 SYS/BIOS ticks (CC118=127,
CC112..116 = 7-bit slices of the tick counter, CC118=1; controller_diag.c).
This tool timestamps each beacon with the PC's monotonic clock and fits
ticks against time, so the tick period comes from the PC clock over many
beacons, not from anyone's reaction time. Opens a MIDI INPUT only.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pedal_ports import is_pedal_port  # noqa: E402

BEGIN_END, SLICE0 = 118, 112


class BeaconParser:
    """Feed (host_time, control, value); yields (host_time, ticks) per complete frame."""

    def __init__(self):
        self.slices = None

    def feed(self, t, control, value):
        if control == BEGIN_END and value == 127:
            self.slices = {}
        elif self.slices is not None and SLICE0 <= control < SLICE0 + 5:
            self.slices[control - SLICE0] = value
        elif control == BEGIN_END and value == 1:
            s, self.slices = self.slices, None
            if s is not None and len(s) == 5:
                return t, sum(v << (7 * k) for k, v in s.items()) & 0xFFFFFFFF
        return None


def unwrap(points):
    out, base, prev = [], 0, None
    for t, ticks in points:
        if prev is not None and ticks < prev and prev - ticks > 1 << 31:
            base += 1 << 32
        prev = ticks
        out.append((t, ticks + base))
    return out


def fit(points):
    """Least-squares seconds-per-tick; drops outliers (frames delayed by other
    traffic) beyond 3 x MAD of the residuals, at least 5 ms. Returns a dict."""
    pts = unwrap(points)
    keep = pts
    for _ in range(3):
        n = len(keep)
        if n < 3:
            return None
        mx = sum(k for _, k in keep) / n
        my = sum(t for t, _ in keep) / n
        sxx = sum((k - mx) ** 2 for _, k in keep)
        if sxx == 0:
            return None
        slope = sum((k - mx) * (t - my) for t, k in keep) / sxx
        icpt = my - slope * mx
        res = [t - (icpt + slope * k) for t, k in pts]
        mad = sorted(abs(r) for r in res)[len(res) // 2]
        lim = max(3 * 1.4826 * mad, 0.005)
        nxt = [p for p, r in zip(pts, res) if abs(r) <= lim]
        if len(nxt) == len(keep):
            break
        keep = nxt
    n = len(keep)
    res = [t - (icpt + slope * k) for t, k in keep]
    rms = (sum(r * r for r in res) / max(1, n - 2)) ** 0.5
    stderr = rms / sxx ** 0.5
    return {"seconds_per_tick": slope, "ticks_per_second": 1 / slope,
            "stderr_seconds_per_tick": stderr, "rel_uncertainty": stderr / slope,
            "beacons_used": n, "beacons_total": len(pts),
            "span_seconds": keep[-1][0] - keep[0][0], "residual_rms_ms": rms * 1e3}


def describe(r):
    us = r["seconds_per_tick"] * 1e6
    return ("1 tick = %.3f us (%.3f ticks/s), +-%.3f%%, from %d of %d beacons over %.0f s "
            "(timing jitter %.2f ms rms)" % (us, r["ticks_per_second"], 100 * r["rel_uncertainty"],
                                             r["beacons_used"], r["beacons_total"],
                                             r["span_seconds"], r["residual_rms_ms"]))


def main(argv=None):
    import mido
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seconds", type=float, default=90.0)
    ap.add_argument("--port", default="")
    ap.add_argument("--out", type=Path, default=Path("build/tick_test.json"))
    a = ap.parse_args(argv)

    print("CF tick test (receive-only)\n")
    print("Step 1. Switch the pedal on while holding RHYTHM, with USB connected.")
    print("        The pedal screen shows 'CLAUDE W#..'; the 'b' number on the bottom line")
    print("        counts the timing beacons.\n")
    names = [n for n in mido.get_input_names()
             if (a.port.lower() in n.lower() if a.port else is_pedal_port(n))]
    if not names:
        sys.exit("No pedal MIDI input found (%s). Close other MIDI tools and re-plug."
                 % mido.get_input_names())
    parser, points = BeaconParser(), []
    with mido.open_input(names[0]) as port:
        print("Listening on %r. Waiting for the first beacon..." % names[0])
        deadline = time.perf_counter() + 60
        while not points:
            for msg in port.iter_pending():
                if msg.type == "control_change":
                    got = parser.feed(time.perf_counter(), msg.control, msg.value)
                    if got:
                        points.append(got)
            if time.perf_counter() > deadline:
                sys.exit("No beacon in 60 s. Is this the CLAUDE diag build, in controller mode?")
            time.sleep(0.001)
        print("\nStep 2. Measuring for %.0f s. Leave the pedal alone; no need to time anything.\n"
              % a.seconds)
        start = points[0][0]
        while time.perf_counter() - start < a.seconds:
            for msg in port.iter_pending():
                if msg.type == "control_change":
                    got = parser.feed(time.perf_counter(), msg.control, msg.value)
                    if got:
                        points.append(got)
                        r = fit(points)
                        est = (" estimate %.3f us/tick" % (r["seconds_per_tick"] * 1e6)) if r else ""
                        print("\r  %3.0f s  beacons %3d %s   "
                              % (time.perf_counter() - start, len(points), est), end="", flush=True)
            time.sleep(0.001)
    print("\n")
    r = fit(points)
    if r is None:
        sys.exit("Too few beacons for a result (%d)." % len(points))
    print("Step 3. Result:\n  " + describe(r))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps({"result": r, "points": points}, indent=1))
    print("  saved %s" % a.out)


if __name__ == "__main__":
    main()
