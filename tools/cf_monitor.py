"""CF Monitor: listen to the pedal's USB channels, watch their levels, record them, play recordings.

    python tools/cf_monitor.py            (or double-click "CF Monitor.cmd" on the desktop)
    python tools/cf_monitor.py --selftest  open the streams for 3 s and print the levels (no window)

Input: the pedal's 8-channel USB audio (any WASAPI input named "Comet Flower" or "CF8"), opened
exclusive at 44.1 kHz so recordings are bit-exact. Output: your default playback device, shared,
with Windows converting the rate (the pedal's clock and your speakers' are independent; a small
buffer absorbs the drift by repeating or dropping a few samples, which only affects listening,
never the recording).

Channel count follows the pedal: 10 with the Audio Bridge firmware (tools/ua_channels_10.json: 1-2 mix,
3-4 guitar FX, 5-6 drums, 7-8 DI, 9-10 looper), 8 with the bench firmware (ua_channels_bench.json, where
8 is timing data, not audio). Only 1-2 start ticked for listening. Recordings: build/recordings/<time>.wav (all 8 channels) plus one labelled WAV per
channel and a .channels.json, as tools/ua_capture8.py writes them.
"""
import argparse
import collections
import json
import queue
import sys
import threading
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
FS = 44100
NCH = 10                          # opened with what the pedal offers (10, or 8 for the bench build)
BLOCK = 441                      # 10 ms
MAPS = ["ua_channels_10.json", "ua_channels_bench.json", "ua_channels_fx.json", "ua_channels_stems.json", "ua_channels.json"]


STALE_FORMAT_HINT = ("Windows still has the pedal's old channel count stored (WASAPI shows %d, the pedal has %d). "
                     "Fix: Sound settings > Recording > Line (Comet Flower Audio Bridge) > Properties > Advanced > "
                     "Default Format: pick the %d channel entry, OK, then restart CF Monitor.")


def stale_format():
    """(wasapi channels, real channels) when Windows' stored endpoint format lags the pedal, else None."""
    import sounddevice as sd
    was, other = 0, 0
    for d in sd.query_devices():
        if "Comet Flower" in d["name"] or "CF8" in d["name"]:
            api = sd.query_hostapis(d["hostapi"])["name"]
            if "WASAPI" in api:
                was = max(was, d["max_input_channels"])
            elif "WDM-KS" in api or "MME" in api:
                other = max(other, d["max_input_channels"])
    return (was, other) if was and other and was != other else None


def find_input():
    import sounddevice as sd
    for i, d in enumerate(sd.query_devices()):
        api = sd.query_hostapis(d["hostapi"])["name"]
        if ("Comet Flower" in d["name"] or "CF8" in d["name"]) and d["max_input_channels"] >= 8 and "WASAPI" in api:
            return i, d["name"], d["max_input_channels"]
    return None, None, 0


def load_map(name):
    m = json.loads((ROOT / "tools" / name).read_text())
    labels = [c["label"] for c in m["channels"]][:NCH]
    return labels + ["ch %d" % (k + 1) for k in range(len(labels), NCH)], m


class Engine:
    """Input stream -> meters, recorder, and a drift-tolerant queue to the output stream."""

    def __init__(self):
        self.lock = threading.Lock()
        self.peak = np.zeros(NCH)            # since the last meter read
        self.clip = np.zeros(NCH, bool)
        self.monitor = np.zeros(NCH, bool)
        self.monitor[[0, 1]] = True
        self.gain = 0.5
        self.rec = None                      # list of int16 blocks while recording
        self.fifo = collections.deque()
        self.fifo_len = 0
        self.playfile = None                 # (data float32 [n, 2], position)
        self.inp = self.out = None
        self.in_name = None
        self.status = ""

    # --- streams
    def start(self):
        import sounddevice as sd
        dev, name, nch = find_input()
        self.in_name = name
        st = stale_format()
        if st:
            self.status = STALE_FORMAT_HINT % (st[0], st[1], st[1])
            dev = None
        if dev is not None:
            try:
                self.inp = sd.InputStream(device=dev, samplerate=FS, channels=NCH, dtype="int16",
                                          blocksize=BLOCK, callback=self._in_cb,
                                          extra_settings=sd.WasapiSettings(exclusive=True))
                self.inp.start()
            except Exception as e:           # exclusive refused (another app holds it): try shared
                try:
                    self.inp = sd.InputStream(device=dev, samplerate=FS, channels=NCH, dtype="int16",
                                              blocksize=BLOCK, callback=self._in_cb)
                    self.inp.start()
                    self.status = "pedal input shared (exclusive refused: %s)" % e
                except Exception as e2:
                    self.inp = None
                    self.status = "pedal input could not open: %s" % e2
        elif not self.status:
            self.status = "no pedal input found (USB mode on? bench/FX firmware?)"
        try:
            out_dev = sd.default.device[1]
            api = sd.query_hostapis(sd.query_devices(out_dev)["hostapi"])["name"]
            extra = sd.WasapiSettings(auto_convert=True) if "WASAPI" in api else None
            self.out = sd.OutputStream(samplerate=FS, channels=2, dtype="float32", blocksize=BLOCK,
                                       callback=self._out_cb, extra_settings=extra)
            self.out.start()
        except Exception as e:
            self.out = None
            self.status += ("; " if self.status else "") + "playback device could not open: %s" % e

    def stop(self):
        for s in (self.inp, self.out):
            if s is not None:
                try:
                    s.stop()
                    s.close()
                except Exception:
                    pass

    def _in_cb(self, data, frames, t, status):
        x = data.astype(np.float32) / 32768.0
        with self.lock:
            self.peak = np.maximum(self.peak, np.abs(x).max(axis=0))
            self.clip |= (np.abs(data) >= 32767).any(axis=0)
            if self.rec is not None:
                self.rec.append(data.copy())
            sel = np.flatnonzero(self.monitor)
            if len(sel):
                # selected channels -> stereo: odd-numbered channels left, even right, mono ones both
                left = [c for c in sel if c % 2 == 0]
                right = [c for c in sel if c % 2 == 1]
                L = x[:, left].sum(axis=1) if left else x[:, right].sum(axis=1)
                R = x[:, right].sum(axis=1) if right else L
                st = np.stack([L, R], axis=1) * self.gain
            else:
                st = np.zeros((frames, 2), np.float32)
            self.fifo.append(st)
            self.fifo_len += frames
            while self.fifo_len > 8 * BLOCK:          # >80 ms behind: drop (drift)
                self.fifo_len -= len(self.fifo.popleft())

    def _out_cb(self, out, frames, t, status):
        with self.lock:
            if self.playfile is not None:
                data, pos = self.playfile
                chunk = data[pos:pos + frames]
                out[:len(chunk)] = chunk
                out[len(chunk):] = 0
                self.playfile = (data, pos + frames) if pos + frames < len(data) else None
                return
            if self.fifo_len < frames:                # starved: repeat silence (drift)
                out[:] = 0
                return
            got = 0
            while got < frames:
                blk = self.fifo[0]
                n = min(frames - got, len(blk))
                out[got:got + n] = blk[:n]
                if n == len(blk):
                    self.fifo.popleft()
                else:
                    self.fifo[0] = blk[n:]
                got += n
                self.fifo_len -= n
            np.clip(out, -1.0, 1.0, out=out)

    # --- controls
    def read_meters(self):
        with self.lock:
            p, c = self.peak.copy(), self.clip.copy()
            self.peak[:] = 0
        return p, c

    def reset_clip(self):
        with self.lock:
            self.clip[:] = False

    def rec_start(self):
        with self.lock:
            self.rec = []
            self.rec_t0 = time.time()

    def rec_stop(self, labels, chmap):
        with self.lock:
            blocks, self.rec = self.rec, None
        if not blocks:
            return None
        data = np.concatenate(blocks)
        out = ROOT / "build" / "recordings"
        out.mkdir(parents=True, exist_ok=True)
        path = out / (time.strftime("rec_%Y%m%d_%H%M%S") + ".wav")
        with wave.open(str(path), "wb") as w:
            w.setnchannels(NCH)
            w.setsampwidth(2)
            w.setframerate(FS)
            w.writeframes(np.ascontiguousarray(data, "<i2").tobytes())
        files = []
        for c, lab in enumerate(labels):
            slug = "".join(ch if ch.isalnum() else "_" for ch in lab).strip("_")
            p = path.with_name("%s_%02d_%s.wav" % (path.stem, c + 1, slug))
            with wave.open(str(p), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(FS)
                w.writeframes(np.ascontiguousarray(data[:, c], "<i2").tobytes())
            files.append(p.name)
        path.with_suffix(".channels.json").write_text(json.dumps(
            {"take": path.name, "firmware": chmap.get("firmware"), "channels": chmap["channels"],
             "files": files, "seconds": len(data) / FS}, indent=2))
        return path, len(data) / FS

    def play_file(self, path):
        with wave.open(str(path)) as w:
            n, ch, sw, fs = w.getnframes(), w.getnchannels(), w.getsampwidth(), w.getframerate()
            raw = w.readframes(n)
        if sw != 2:
            raise ValueError("only 16-bit WAV files")
        x = np.frombuffer(raw, "<i2").reshape(-1, ch).astype(np.float32) / 32768.0
        st = np.stack([x[:, 0], x[:, 1 if ch > 1 else 0]], axis=1)
        if fs != FS:                                   # simple linear resample for listening
            t = np.arange(0, len(st), fs / FS)
            st = np.stack([np.interp(t, np.arange(len(st)), st[:, k]) for k in (0, 1)], axis=1).astype(np.float32)
        with self.lock:
            self.playfile = (np.ascontiguousarray(st * self.gain), 0)

    def stop_file(self):
        with self.lock:
            self.playfile = None


def selftest():
    e = Engine()
    e.start()
    print("input:", e.in_name, "|", e.status or "ok")
    time.sleep(3)
    p, c = e.read_meters()
    e.stop()
    for k in range(NCH):
        print("  ch%d peak %6.1f dBFS%s" % (k + 1, 20 * np.log10(p[k] + 1e-9), "  CLIP" if c[k] else ""))


def gui(close_after=0):
    import tkinter as tk
    from tkinter import filedialog, ttk

    e = Engine()
    e.start()
    root = tk.Tk()
    root.title("CF Monitor")
    root.configure(bg="#16191b")
    BG, PANEL, INK, MUTED, GLOW, RED, GREEN = "#16191b", "#1f2427", "#e6e9e4", "#8f9a95", "#e8934a", "#e2735f", "#5cbf86"
    font = ("Segoe UI", 10)
    big = ("Segoe UI Semibold", 13)

    labels, chmap = load_map(MAPS[0])
    head = tk.Frame(root, bg=BG)
    head.pack(fill="x", padx=14, pady=(12, 4))
    tk.Label(head, text="CF Monitor", font=("Segoe UI Semibold", 16), fg=INK, bg=BG).pack(side="left")
    src = tk.Label(head, text=(e.in_name or "no pedal input"), font=font, fg=MUTED, bg=BG)
    src.pack(side="left", padx=12)
    mapvar = tk.StringVar(value=MAPS[0])

    meters = tk.Frame(root, bg=PANEL)
    meters.pack(fill="x", padx=14, pady=6)
    mon_vars, bars, clips, names = [], [], [], []
    for c in range(NCH):
        row = tk.Frame(meters, bg=PANEL)
        row.pack(fill="x", padx=10, pady=3)
        v = tk.BooleanVar(value=bool(e.monitor[c]))
        cb = tk.Checkbutton(row, variable=v, bg=PANEL, activebackground=PANEL, selectcolor=BG, fg=INK,
                            command=lambda c=c, v=v: e.monitor.__setitem__(c, v.get()))
        cb.pack(side="left")
        mon_vars.append(v)
        nm = tk.Label(row, text="%d  %s" % (c + 1, labels[c]), width=22, anchor="w", font=font, fg=INK, bg=PANEL)
        nm.pack(side="left")
        names.append(nm)
        cv = tk.Canvas(row, height=14, width=360, bg=BG, highlightthickness=0)
        cv.pack(side="left", padx=6)
        bar = cv.create_rectangle(0, 0, 0, 14, fill=GREEN, width=0)
        txt = cv.create_text(354, 7, text="", anchor="e", fill=MUTED, font=("Consolas", 8))
        bars.append((cv, bar, txt))
        cl = tk.Label(row, text="CLIP", font=("Segoe UI Semibold", 9), fg=BG, bg=BG, width=5)
        cl.pack(side="left")
        clips.append(cl)

    def relabel(*_):
        nonlocal labels, chmap
        labels, chmap = load_map(mapvar.get())
        for c in range(NCH):
            names[c].config(text="%d  %s" % (c + 1, labels[c]))

    ctl = tk.Frame(root, bg=BG)
    ctl.pack(fill="x", padx=14, pady=6)
    tk.Label(ctl, text="Listen volume", font=font, fg=MUTED, bg=BG).pack(side="left")
    vol = tk.Scale(ctl, from_=0, to=100, orient="horizontal", length=180, bg=BG, fg=INK, troughcolor=PANEL,
                   highlightthickness=0, command=lambda s: setattr(e, "gain", int(s) / 100))
    vol.set(50)
    vol.pack(side="left", padx=6)
    tk.Label(ctl, text="Channel names", font=font, fg=MUTED, bg=BG).pack(side="left", padx=(18, 4))
    ttk.OptionMenu(ctl, mapvar, MAPS[0], *MAPS, command=relabel).pack(side="left")
    tk.Button(ctl, text="Reset clip lights", font=font, command=e.reset_clip).pack(side="right")

    act = tk.Frame(root, bg=BG)
    act.pack(fill="x", padx=14, pady=(6, 4))
    status = tk.Label(root, text=e.status or "Ready.", font=font, fg=MUTED, bg=BG, anchor="w", wraplength=640, justify="left")
    rec_btn = tk.Button(act, text="Record", font=big, bg=GLOW, fg="#1b120a", width=10, relief="flat")
    rec_state = {"on": False}

    def toggle_rec():
        if not rec_state["on"]:
            if e.inp is None:
                status.config(text="No pedal input to record.")
                return
            e.rec_start()
            rec_state["on"] = True
            rec_btn.config(text="Stop", bg=RED)
        else:
            rec_state["on"] = False
            rec_btn.config(text="Record", bg=GLOW)
            res = e.rec_stop(labels, chmap)
            status.config(text="Saved %s (%.1f s) + one WAV per channel." % (res[0], res[1]) if res else "Nothing recorded.")

    rec_btn.config(command=toggle_rec)
    rec_btn.pack(side="left")
    rec_time = tk.Label(act, text="", font=big, fg=INK, bg=BG)
    rec_time.pack(side="left", padx=10)

    def play():
        p = filedialog.askopenfilename(initialdir=str(ROOT / "build"), filetypes=[("WAV", "*.wav")])
        if p:
            try:
                e.play_file(p)
                status.config(text="Playing %s (channels 1-2 of the file). Live listening resumes when it ends." % Path(p).name)
            except Exception as ex:
                status.config(text="Could not play: %s" % ex)

    tk.Button(act, text="Play a file...", font=font, command=play).pack(side="left", padx=(24, 4))
    tk.Button(act, text="Stop playback", font=font, command=e.stop_file).pack(side="left")
    status.pack(fill="x", padx=14, pady=(2, 12))

    def tick():
        p, c = e.read_meters()
        for k in range(NCH):
            cv, bar, txt = bars[k]
            db = 20 * np.log10(p[k] + 1e-9)
            w = max(0.0, min(1.0, (db + 60) / 60)) * 340
            cv.coords(bar, 0, 0, w, 14)
            cv.itemconfig(bar, fill=RED if db > -1 else (GLOW if db > -12 else GREEN))
            cv.itemconfig(txt, text=("%.0f dB" % db) if db > -90 else "")
            clips[k].config(bg=RED if c[k] else BG, fg=BG)
        if rec_state["on"]:
            rec_time.config(text="%.1f s" % (time.time() - e.rec_t0))
        else:
            rec_time.config(text="")
        root.after(50, tick)

    def close():
        if rec_state["on"]:
            toggle_rec()
        e.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    if close_after:
        root.after(int(close_after * 1000), close)
    tick()
    root.mainloop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--close-after", type=float, default=0, help=argparse.SUPPRESS)   # smoke test of the window
    a = ap.parse_args()
    _, _, n = find_input()                 # 10 (FX firmware) or 8 (bench firmware): open what is there
    if n >= 10:
        NCH = 10
    elif n:
        NCH = 8
        MAPS.insert(0, MAPS.pop(MAPS.index("ua_channels_bench.json")))
    selftest() if a.selftest else gui(a.close_after)
