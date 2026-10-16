"""Comet Flower intro: the tune's structure and the window (no audio played)."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tools.cf_intro import music  # noqa: E402


class Tune(unittest.TestCase):
    def test_progression_and_scale(self):
        self.assertEqual(music.PROG, ["Bm", "A", "G", "Em"])
        penta = {"B", "D", "E", "F#", "A"}                  # B minor pentatonic lead
        for phrase in (music.LEAD_A, music.LEAD_B):
            self.assertTrue({n for n, *_ in phrase} <= penta)

    def test_render_shape(self):
        x = music.render()
        self.assertGreater(len(x) / music.SR, 100)
        self.assertLessEqual(np.max(np.abs(x)), 0.851)
        self.assertLess(np.max(np.abs(x[-200:])), 1e-3)   # ends in silence: loops cleanly
        self.assertLess(np.max(np.abs(x[:200])), 1e-2)    # starts from silence


class Window(unittest.TestCase):
    def test_intro_builds(self):
        try:
            import tkinter as tk
            tk.Tk().destroy()
        except Exception:
            self.skipTest("no Tk display")
        from tools.cf_intro.intro import Intro, logo_lines
        a = Intro(music=False)
        try:
            a.withdraw()
            for _ in range(5):
                a.tick()
            self.assertEqual(len(logo_lines()), 5)
            self.assertEqual(len(a.buttons), 4)
        finally:
            a.destroy()


if __name__ == "__main__":
    unittest.main()
