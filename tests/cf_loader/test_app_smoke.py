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

    def test_wizard_steps_unlock_in_order(self):
        from tools.cf_loader import app
        a = app.CFLoaderApp()
        try:
            a.withdraw()
            a.status_data = {"X.ZD2": {"stage": "in image"}}
            a.test_effect_combo["values"] = ["X.ZD2"]
            a.test_effect_combo.set("X.ZD2")
            a._on_test_effect_selected(object())          # fresh effect: checklist reset
            st = lambda w: str(w.cget("state"))
            self.assertEqual(st(a.wizard_checks[0]), "normal")
            self.assertEqual(st(a.wizard_checks[1]), "disabled")
            self.assertEqual(st(a.btn_audio_pass), "disabled")
            for i, var in enumerate(a.wizard_vars):
                var.set(True)
                a._refresh_wizard()
                if i + 1 < len(a.wizard_checks):
                    self.assertEqual(st(a.wizard_checks[i + 1]), "normal")
            self.assertEqual(st(a.btn_audio_pass), "normal")
            a.wizard_vars[1].set(False)                   # un-ticking re-locks later steps
            a._refresh_wizard()
            self.assertFalse(a.wizard_vars[4].get())
            self.assertEqual(st(a.btn_audio_pass), "disabled")
            # never packaged: audio pass stays locked even with every step done
            a.status_data = {"X.ZD2": {"stage": "built"}}
            for var in a.wizard_vars:
                var.set(True)
            a._refresh_wizard()
            self.assertEqual(st(a.btn_audio_pass), "disabled")
        finally:
            a.destroy()

    def test_busy_locks_actions(self):
        from tools.cf_loader import app
        a = app.CFLoaderApp()
        try:
            a.withdraw()
            st = lambda w: str(w.cget("state"))
            self.assertEqual(st(a.btn_cancel_build), "disabled")
            a._set_busy(True)
            a.refresh_preflight()                         # must not re-enable Build while busy
            self.assertEqual(st(a.btn_build), "disabled")
            self.assertEqual(st(a.btn_restore), "disabled")
            self.assertEqual(st(a.btn_cancel_build), "normal")
            a._set_busy(False)
            self.assertEqual(st(a.btn_restore), "normal")
            self.assertEqual(st(a.btn_cancel_restore), "disabled")
        finally:
            a.destroy()


if __name__ == "__main__":
    unittest.main()
