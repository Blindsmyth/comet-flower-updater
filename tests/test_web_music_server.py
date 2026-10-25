"""Tests for tools/web_music_server.py HTTP server and track payload sync."""

import json
from pathlib import Path
import threading
import time
import unittest
import urllib.request
import urllib.error

import sys
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))

import web_music_server as server


class WebMusicServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Use a high ephemeral port for testing
        cls.test_port = 18888
        server.PORT = cls.test_port
        cls.httpd = server.HTTPServer(("127.0.0.1", cls.test_port), server.StudioHTTPRequestHandler)
        cls.server_thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def test_get_index_html(self):
        url = f"http://127.0.0.1:{self.test_port}/"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            data = resp.read().decode("utf-8")
            self.assertIn("SONY ACID CHIPTUNE STUDIO", data)
            self.assertIn("DIGITAL INSANITY", data)

    def test_post_save_track_and_get_track(self):
        url_save = f"http://127.0.0.1:{self.test_port}/api/save_track"
        payload = {
            "title": "Mobile Test Beat",
            "bpm": 130,
            "step_duration": 0.115,
            "lead_program": 81,
            "bass_program": 38,
            "chords": ["Bm", "A", "G", "Em"],
            "bars": [
                {"chord": "Bm", "root": 47, "notes": [59] * 16}
            ]
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url_save, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            res_data = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(res_data["status"], "ok")

        # Now test GET /api/track
        url_get = f"http://127.0.0.1:{self.test_port}/api/track"
        with urllib.request.urlopen(url_get) as resp:
            self.assertEqual(resp.status, 200)
            saved = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(saved["title"], "Mobile Test Beat")
            self.assertEqual(saved["bpm"], 130)


if __name__ == "__main__":
    unittest.main()
