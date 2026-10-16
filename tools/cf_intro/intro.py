"""Comet Flower intro / installer front-end, in the old keygen / cracktro style.

    .venv/Scripts/pythonw.exe -m tools.cf_intro [--updater "<Comet Flower updater .exe>"]

An homage to the scene loaders of the late 90s / 2000s (greetings to Razor 1911
and their Digital Voyage era): copper-cycled block logo, starfield, NFO panel,
sine scroller and a chip tune (tools/cf_intro/music.py, original composition).

INSTALL never flashes anything by itself. It walks through update mode and
then only *opens* the Comet Flower updater, where the owner still selects the
MIDI port and presses Execute -- the same manual step as always.
"""
import argparse
import math
import os
import random
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

ROOT = Path(__file__).resolve().parents[2]
W, H = 720, 460
BG = "#000000"

FONT5 = {
    "C": [" ### ", "#    ", "#    ", "#    ", " ### "],
    "O": [" ### ", "#   #", "#   #", "#   #", " ### "],
    "M": ["#   #", "## ##", "# # #", "#   #", "#   #"],
    "E": ["#####", "#    ", "#### ", "#    ", "#####"],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  "],
    "F": ["#####", "#    ", "#### ", "#    ", "#    "],
    "L": ["#    ", "#    ", "#    ", "#    ", "#####"],
    "W": ["#   #", "#   #", "# # #", "## ##", "#   #"],
    "R": ["#### ", "#   #", "#### ", "#  # ", "#   #"],
    " ": ["   ", "   ", "   ", "   ", "   "],
}

NFO = """\
  .:: COMET FLOWER ::.  G1X FOUR CUSTOM FIRMWARE  .:: 2026 ::.

  RELEASE ....... Comet Flower G1X4 (unified, TEST build)
  TARGET ........ Zoom G1X FOUR, v2.00 updater (yours)
  CONTENTS ...... CF 808 / CF RAT / CF Muff / DR103 / G1 Gain
                  USB MIDI controller mode + on-pedal screen
                  USB name "Comet Flower"   CF logo + presets
  DIAGNOSTICS ... the CLAUDE page (hold RHYTHM at power-on)
  RECOVERY ...... both footswitches at plug-in -> RESTORE

  [ INSTALL ] opens the updater. YOU press Execute. Nothing is
  ever flashed behind your back.
"""

SCROLL = ("   *** COMET FLOWER *** proudly presents the G1X FOUR custom firmware ...   "
          "drives, fuzz and a Hiwatt in 40 KiB slots ...  USB MIDI controller mode with a "
          "screen that talks back ...   code & late nights: COMET FLOWER  ...  a quiet nod to "
          "CLAUDE, who does the thankless part for everybody  ...   greetings to RAZOR 1911 "
          "and the DIGITAL VOYAGE era, to every scener who ever wrote a loader at 4 am, to "
          "stomphacks, and to the guitarists who never read the manual  ...   music: "
          "'Comfortably Numb' changes, built like 'Shine On' part one, in chip  ...   "
          "hold RHYTHM at power-on to meet the CLAUDE page  ...   wrap ...   ")


def logo_lines(text="COMET FLOWER"):
    rows = [""] * 5
    for ch in text:
        g = FONT5[ch]
        for r in range(5):
            rows[r] += g[r].replace("#", "█") + " "
    return rows


class Player:
    """Loop a WAV like a media app: Windows MCI (its own Volume Mixer entry, the
    default playback device). winsound.PlaySound is only a fallback: Windows
    files it under "System Sounds", which is often muted."""

    def __init__(self):
        self.mode = None

    def start(self, wav):
        try:
            import ctypes
            mci = ctypes.windll.winmm.mciSendStringW
            mci("close cfintro", None, 0, 0)
            if (mci('open "%s" type mpegvideo alias cfintro' % wav, None, 0, 0) == 0
                    and mci("play cfintro repeat", None, 0, 0) == 0):
                self.mode = "mci"
                return True
        except (AttributeError, OSError):
            pass
        try:
            import winsound
            winsound.PlaySound(str(wav), winsound.SND_FILENAME | winsound.SND_ASYNC
                               | winsound.SND_LOOP)
            self.mode = "winsound"
            return True
        except (ImportError, RuntimeError):
            return False

    def stop(self):
        if self.mode == "mci":
            import ctypes
            ctypes.windll.winmm.mciSendStringW("close cfintro", None, 0, 0)
        elif self.mode == "winsound":
            import winsound
            winsound.PlaySound(None, 0)
        self.mode = None


def copper(t, row):
    """Classic copper-bar colour cycling: hue rolls down the logo rows."""
    h = (t * 0.6 + row * 0.11) % 1.0
    i = int(h * 6)
    f = h * 6 - i
    v, s = 1.0, 0.85
    p, q, u = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r, g, b = [(v, u, p), (q, v, p), (p, v, u), (p, q, v), (u, p, v), (v, p, q)][i % 6]
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


class Intro(tk.Tk):
    def __init__(self, updater=None, music=True):
        super().__init__()
        self.title("Comet Flower G1X4")
        self.configure(bg=BG)
        self.geometry("%dx%d" % (W, H))
        self.resizable(False, False)
        self.updater = Path(updater) if updater else None
        self.music_on = False
        self.wav = None
        self.player = Player()
        self.t = 0.0
        self.cv = tk.Canvas(self, width=W, height=H, bg=BG, highlightthickness=0)
        self.cv.pack()
        rnd = random.Random(1911)
        self.stars = [[rnd.uniform(0, W), rnd.uniform(0, H), rnd.choice((1, 2, 3))]
                      for _ in range(110)]
        self.star_ids = [self.cv.create_rectangle(0, 0, 0, 0, fill="#ffffff", width=0)
                         for _ in self.stars]
        self.logo_ids = []
        for r, line in enumerate(logo_lines()):
            self.logo_ids.append(self.cv.create_text(W // 2, 34 + r * 15, text=line,
                                                     font=("Consolas", 12, "bold"),
                                                     fill="#ffffff"))
        self.cv.create_text(W // 2, 118, text="- G1X FOUR CUSTOM FIRMWARE -",
                            font=("Consolas", 10, "bold"), fill="#8a8aff")
        self.cv.create_rectangle(24, 134, W - 24, 330, outline="#3a3aff", fill="#03030c", width=1)
        self.cv.create_text(36, 140, text=NFO, anchor="nw", font=("Consolas", 9),
                            fill="#c8c8c8")
        self.scroll_x = float(W)
        self.char_w = 14
        self.scroll_ids = [self.cv.create_text(0, 0, text=c, font=("Consolas", 15, "bold"),
                                               fill="#ffffff") for c in SCROLL]
        self.buttons = []
        for i, (label, cmd) in enumerate((("INSTALL", self.install), ("MUSIC", self.toggle_music),
                                          ("ABOUT", self.about), ("EXIT", self.quit_app))):
            x = 90 + i * 180
            rid = self.cv.create_rectangle(x - 62, 412, x + 62, 440, outline="#5a5aff",
                                           fill="#0a0a30", width=2)
            tid = self.cv.create_text(x, 426, text="[ %s ]" % label,
                                      font=("Consolas", 11, "bold"), fill="#e0e0ff")
            for item in (rid, tid):
                self.cv.tag_bind(item, "<Button-1>", lambda e, c=cmd: c())
                self.cv.tag_bind(item, "<Enter>", lambda e, r=rid: self.cv.itemconfig(r, fill="#20208a"))
                self.cv.tag_bind(item, "<Leave>", lambda e, r=rid: self.cv.itemconfig(r, fill="#0a0a30"))
            self.buttons.append((rid, tid))
        self.bind("<Escape>", lambda e: self.quit_app())
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        if music:
            self.after(200, self.toggle_music)
        self.tick()

    # -- animation -----------------------------------------------------------
    def tick(self):
        self.t += 1 / 40
        for s, sid in zip(self.stars, self.star_ids):
            s[0] -= s[2] * 1.4
            if s[0] < 0:
                s[0] = W
            c = ("#555555", "#aaaaaa", "#ffffff")[s[2] - 1]
            self.cv.coords(sid, s[0], s[1], s[0] + s[2], s[1] + s[2] / 2 + 0.5)
            self.cv.itemconfig(sid, fill=c)
        for r, lid in enumerate(self.logo_ids):
            self.cv.itemconfig(lid, fill=copper(self.t, r))
            self.cv.coords(lid, W // 2 + 6 * math.sin(self.t * 1.7 + r * 0.5), 34 + r * 15)
        self.scroll_x -= 2.4
        if self.scroll_x < -len(SCROLL) * self.char_w:
            self.scroll_x = W
        for k, cid in enumerate(self.scroll_ids):
            x = self.scroll_x + k * self.char_w
            if -20 < x < W + 20:
                y = 370 + 16 * math.sin(self.t * 3.1 + x * 0.018)
                self.cv.coords(cid, x, y)
                self.cv.itemconfig(cid, fill=copper(self.t * 0.7 + x / W, 2), state="normal")
            else:
                self.cv.itemconfig(cid, state="hidden")
        self.after(25, self.tick)

    # -- actions -------------------------------------------------------------
    def toggle_music(self):
        if self.music_on:
            self.player.stop()
            self.music_on = False
        else:
            if self.wav is None:
                from tools.cf_intro import music
                self.wav = music.ensure(ROOT / "build" / "cf_intro" / "cf_tune.wav")
            self.music_on = self.player.start(self.wav)
        self.cv.itemconfig(self.buttons[1][1],
                           text="[ MUSIC %s ]" % ("ON" if self.music_on else "OFF"))

    def find_updater(self):
        if self.updater and self.updater.exists():
            return self.updater
        here = sorted(Path.cwd().glob("Comet Flower G1X4 Updater*.exe"))
        return here[0] if here else None

    def install(self):
        exe = self.find_updater()
        if exe is None:
            messagebox.showerror("Comet Flower", "Updater not found. Start the intro with\n"
                                 "--updater \"...\\Comet Flower G1X4 Updater (TEST build).exe\"")
            return
        steps = ("1. Unplug USB. Close ToneLib / Guitar Lab / MIDI tools.\n"
                 "2. Hold BOTH footswitches and plug USB in; keep holding until the\n"
                 "   pedal shows FIRMWARE UPDATE.\n"
                 "3. Press OK: the updater opens. Select MIDI IN/OUT = 'ZOOM G Series'\n"
                 "   (update mode keeps that name), press Execute.\n"
                 "4. Wait for 'Version update completed'. Never unplug mid-write.\n\n"
                 "Open the updater now?\n\n%s" % exe.name)
        if messagebox.askokcancel("Comet Flower :: install", steps):
            os.startfile(str(exe))

    def about(self):
        messagebox.showinfo("Comet Flower", "Comet Flower G1X4 -- custom firmware for the Zoom G1X FOUR.\n"
                            "Built on your own v2.00 updater; Zoom's engine, our effects,\n"
                            "controller mode and screens.\n\nMusic: original chip tune over the "
                            "Comfortably Numb solo changes,\nshaped like Shine On part one.\n\n"
                            "Greetings to Razor 1911. Thanks, Claude.")

    def quit_app(self):
        self.player.stop()
        self.destroy()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--updater")
    ap.add_argument("--no-music", action="store_true")
    a = ap.parse_args(argv)
    Intro(a.updater, music=not a.no_music).mainloop()


if __name__ == "__main__":
    main()
