"""Lightweight local web server for Comet Flower Mobile Music Studio.

Allows remote phones on the local network (Wi-Fi/LAN) to:
1. Access the Sony ACID Keygen Music Studio directly from mobile browser.
2. Preview and edit chiptunes with native Web Audio API synthesis on the phone.
3. Save the resulting track data directly back to the PC updater (tools/payload/music_track.json).
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import socket
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = REPO_ROOT / "tools" / "web_music_studio" / "index.html"
PAYLOAD_DIR = REPO_ROOT / "tools" / "payload"
PAYLOAD_TRACK = PAYLOAD_DIR / "music_track.json"
PORT = 8888


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


class StudioHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            if not HTML_PATH.is_file():
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"index.html not found.")
                return
            content = HTML_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        elif self.path == "/api/track":
            # Return currently saved track if any
            if PAYLOAD_TRACK.is_file():
                content = PAYLOAD_TRACK.read_bytes()
            else:
                content = json.dumps({"status": "no_track_saved"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/save_track":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body.decode("utf-8"))
                PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
                PAYLOAD_TRACK.write_text(json.dumps(data, indent=2), encoding="utf-8")
                response = {
                    "status": "ok",
                    "message": "Track saved successfully to PC updater payload",
                    "path": str(PAYLOAD_TRACK),
                    "title": data.get("title", "Untitled"),
                    "bpm": data.get("bpm", 125),
                }
                resp_bytes = json.dumps(response).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp_bytes)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(resp_bytes)
                print(f"[+] Track saved from mobile: {data.get('title')} ({data.get('bpm')} BPM)")
            except Exception as e:
                err_bytes = json.dumps({"status": "error", "message": str(e)}).encode("utf-8")
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_bytes)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(err_bytes)
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        # Keep console output clean
        pass


def main():
    local_ip = get_local_ip()
    server_address = ("0.0.0.0", PORT)
    httpd = HTTPServer(server_address, StudioHTTPRequestHandler)
    print("\n" + "=" * 65)
    print("   COMET FLOWER REMOTE MUSIC STUDIO - MOBILE WEB SERVER")
    print("=" * 65)
    print(f"[+] Local URL  : http://localhost:{PORT}")
    print(f"[+] Mobile URL : http://{local_ip}:{PORT}")
    print(f"[+] Open the Mobile URL in your phone browser on the same Wi-Fi.")
    print(f"[+] Direct sync saves to: {PAYLOAD_TRACK}")
    print("=" * 65 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[+] Server stopped.")
        httpd.server_close()


if __name__ == "__main__":
    main()
