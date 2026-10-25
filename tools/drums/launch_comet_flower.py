"""Launcher for the Comet Flower Drum Machine Emulator & Pattern Lab.

Usage:
  python tools/drums/launch_comet_flower.py              # Opens in default browser directly
  python tools/drums/launch_comet_flower.py --server     # Starts local HTTP server on port 8080
  python tools/drums/launch_comet_flower.py --port 8000  # Specify server port
"""
import argparse
import http.server
import os
import socketserver
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HTML_PATH = ROOT / "comet_flower_drums.html"


def main():
    parser = argparse.ArgumentParser(description="Launch Comet Flower Drum Studio")
    parser.add_argument("--server", action="store_true", help="Run via local HTTP server")
    parser.add_argument("--port", type=int, default=8080, help="Port for local HTTP server")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    if not HTML_PATH.exists():
        print("comet_flower_drums.html not found, regenerating...")
        import generate_studio
        generate_studio.build_studio_html()

    if args.server:
        os.chdir(ROOT)
        handler = http.server.SimpleHTTPRequestHandler
        url = f"http://localhost:{args.port}/comet_flower_drums.html"
        print(f"★ Comet Flower Drum Studio serving at: {url}")
        if not args.no_browser:
            webbrowser.open(url)
        with socketserver.TCPServer(("", args.port), handler) as httpd:
            print("Press Ctrl+C to stop server.")
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")
    else:
        file_url = HTML_PATH.as_uri()
        print(f"★ Opening Comet Flower Drum Studio directly: {file_url}")
        if not args.no_browser:
            webbrowser.open(file_url)


if __name__ == "__main__":
    main()
