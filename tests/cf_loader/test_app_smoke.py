"""Comet Flower Installer GUI smoke test.

Verifies the window constructs properly, all 5 pages are laid out, navigation works,
and busy states lock actions.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    import tkinter as tk
    _root = tk.Tk()
    _root.destroy()
    HAVE_DISPLAY = True
except Exception:
    HAVE_DISPLAY = False


@unittest.skipUnless(HAVE_DISPLAY, "Tk display not available")
class AppSmoke(unittest.TestCase):
    def test_window_constructs_with_all_pages(self):
        from tools.cf_loader import app
        a = app.CFLoaderApp()
        try:
            a.withdraw()
            a.update()
            self.assertEqual(a.title(), "Comet Flower Installer")
            # Verify 5 pages are registered
            expected_pages = ["Backups", "Effects", "Patches", "Firmware & Build", "Profiles"]
            self.assertEqual(list(a.pages.keys()), expected_pages)
            # Verify navigation buttons
            self.assertEqual(list(a.nav_buttons.keys()), expected_pages)

            # Test switching between pages
            for page in expected_pages:
                a._switch_page(page)
                self.assertEqual(a.nav_selection.get(), page)
                self.assertEqual(a.pages[page].winfo_manager(), "pack")
                # other pages should not be packed
                for other in expected_pages:
                    if other != page:
                        self.assertEqual(a.pages[other].winfo_manager(), "")
        finally:
            a.destroy()

    def test_busy_locks_actions(self):
        from tools.cf_loader import app
        a = app.CFLoaderApp()
        try:
            a.withdraw()
            st = lambda w: str(w.cget("state"))
            self.assertEqual(st(a.btn_cancel_build), "disabled")
            self.assertEqual(st(a.btn_build_installer), "normal")
            self.assertEqual(st(a.btn_backup_now), "normal")

            a._set_busy(True, "Working...")
            self.assertEqual(st(a.btn_build_installer), "disabled")
            self.assertEqual(st(a.btn_backup_now), "disabled")
            self.assertEqual(st(a.btn_quick_update), "disabled")

            a._set_busy(False)
            self.assertEqual(st(a.btn_build_installer), "normal")
            self.assertEqual(st(a.btn_backup_now), "normal")
            self.assertEqual(st(a.btn_cancel_build), "disabled")
        finally:
            a.destroy()

    def test_profile_loading(self):
        from tools.cf_loader import app
        a = app.CFLoaderApp()
        try:
            a.withdraw()
            self.assertIsNotNone(a.active_profile)
            self.assertTrue(len(a.combo_profiles["values"]) > 0)
        finally:
            a.destroy()


if __name__ == "__main__":
    unittest.main()
