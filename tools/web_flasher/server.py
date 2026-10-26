"""Local HTTP Server for Comet Flower Web MIDI Updater.

Serves the Web MIDI Flasher and pre-baked binary payloads locally,
and launches the default browser.
"""

from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
from pathlib import Path
import socket
import sys
import webbrowser

WEB_DIR = Path(__file__).resolve().parent
PORT = 5000


class WebFlasherHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def guess_type(self, path):
        if str(path).endswith(".bin"):
            return "application/octet-stream"
        return super().guess_type(path)

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        super().end_headers()

    def log_message(self, format, *args):
        # Keep terminal output clean
        pass


def main():
    server_address = ("127.0.0.1", PORT)
    httpd = HTTPServer(server_address, WebFlasherHandler)
    url = f"http://localhost:{PORT}"
    print("\n" + "=" * 65)
    print("   COMET FLOWER LABS 1911 // WEB MIDI UPDATER SERVER")
    print("=" * 65)
    print(f"[+] Server running at: {url}")
    print(f"[+] Serving directory: {WEB_DIR}")
    print(f"[+] Opening browser automatically...")
    print("=" * 65 + "\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[+] Server stopped.")
        httpd.server_close()


if __name__ == "__main__":
    main()
