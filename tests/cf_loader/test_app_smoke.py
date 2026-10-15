"""CF Loader GUI smoke test: the window must construct and lay out every tab.

The app shipped with an invalid Tk geometry string ("1024, 700") that raised
TclError in __init__, so the GUI never opened; core tests could not catch it.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    HAVE_DISPLAY = True
except Exception:  # no Tk or no display
    HAVE_DISPLAY = False


@unittest.skipUnless(HAVE_DISPLAY, "Tk display not available")
class AppSmoke(unittest.TestCase):
    def test_window_constructs_with_all_tabs(self):
        from tools.cf_loader import app
        a = app.CFLoaderApp()
        try:
            a.withdraw()
            a.update()
            tabs = [a.notebook.tab(t, "text") for t in a.notebook.tabs()]
            self.assertEqual(tabs, ["Library", "Build image", "Test (Wizard)",
                                    "Recovery", "Log", "Advanced"])
            # save authorization stays closed in every state
            self.assertEqual(str(a.btn_mark_ok.cget("state")), "disabled")
        finally:
            a.destroy()


if __name__ == "__main__":
    unittest.main()
