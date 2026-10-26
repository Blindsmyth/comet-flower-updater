"""Tests for tools/web_flasher/server.py."""

from pathlib import Path
import threading
import time
import unittest
import urllib.request

REPO_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(REPO_ROOT / "tools" / "web_flasher"))

import server


class WebFlasherServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_port = 15000
        server.PORT = cls.test_port
        cls.httpd = server.HTTPServer(("127.0.0.1", cls.test_port), server.WebFlasherHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_serve_index_html(self):
        url = f"http://127.0.0.1:{self.test_port}/index.html"
        with urllib.request.urlopen(url) as resp:
            self.assertEqual(resp.status, 200)
            data = resp.read().decode("utf-8")
            self.assertIn("COMET FLOWER LABS", data)
            self.assertIn("WEB MIDI UPDATER", data)

    def test_serve_bin_payloads(self):
        payloads = [
            ("firmware_0349.bin", 523504),
            ("fs_0349.bin", 3137536),
            ("presets_0349.bin", 45056),
            ("firmware_stereo_usb.bin", 508772),
        ]
        for name, expected_len in payloads:
            url = f"http://127.0.0.1:{self.test_port}/payload/{name}"
            with urllib.request.urlopen(url) as resp:
                self.assertEqual(resp.status, 200)
                data = resp.read()
                self.assertEqual(len(data), expected_len)


if __name__ == "__main__":
    unittest.main()
