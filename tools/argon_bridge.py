"""Argon web bridge: paste bridge/to_argon.md into a logged-in Gemini tab and
save the reply to bridge/from_argon/response.md.

One-time setup (the profile keeps your Google login):
    python tools/argon_bridge.py --launch      # opens Chrome on port 9222 with a dedicated profile
    (log in to gemini.google.com in that window, pick the Argon model, leave the tab open)

Then, each time:
    python tools/argon_bridge.py               # send packet, wait, save reply
    python tools/argon_bridge.py --dry-run     # only check it can find the tab/input box

Notes for maintainers: Gemini's DOM changes. If a selector breaks, fix SELECTORS below.
The reply is taken from the LAST model response element; completion = text unchanged for
SETTLE seconds and no 'stop' button visible. Human stays in the loop: review the saved
response before executing its action plan.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKET = ROOT / "bridge" / "to_argon.md"
OUT = ROOT / "bridge" / "from_argon" / "response.md"
PROFILE = ROOT / "bridge" / ".chrome_profile"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9222
SETTLE = 8
TIMEOUT = 900

SELECTORS = {
    "input": 'div.ql-editor[contenteditable="true"], rich-textarea div[contenteditable="true"]',
    "send": 'button[aria-label*="Send" i]',
    "stop": 'button[aria-label*="Stop" i]',
    "reply": "model-response, message-content",
}


def launch():
    PROFILE.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([CHROME, f"--remote-debugging-port={PORT}",
                      f"--user-data-dir={PROFILE}", "https://gemini.google.com/app"])
    print("Chrome launched. Log in, choose the Argon model, keep the tab open.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--launch", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.launch:
        return launch()

    from playwright.sync_api import sync_playwright
    text = PACKET.read_text(encoding="utf-8")
    with sync_playwright() as p:
        br = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
        page = next((pg for c in br.contexts for pg in c.pages
                     if "gemini.google.com" in pg.url), None)
        if page is None:
            sys.exit("No gemini.google.com tab found. Run with --launch and log in.")
        box = page.locator(SELECTORS["input"]).last
        box.wait_for(timeout=15000)
        if a.dry_run:
            print("OK: found Gemini tab and input box:", page.url)
            return
        before = page.locator(SELECTORS["reply"]).count()
        box.click()
        # Paste via clipboard-style insert: fast, avoids typing 11 KB key by key.
        page.evaluate("t => document.execCommand('insertText', false, t)", text)
        page.locator(SELECTORS["send"]).last.click()

        deadline = time.time() + TIMEOUT
        last, stable_since = "", time.time()
        while time.time() < deadline:
            time.sleep(2)
            replies = page.locator(SELECTORS["reply"])
            if replies.count() <= before:
                continue
            cur = replies.last.inner_text()
            generating = page.locator(SELECTORS["stop"]).count() > 0
            if cur != last or generating:
                last, stable_since = cur, time.time()
            elif cur and time.time() - stable_since >= SETTLE:
                break
        else:
            sys.exit("Timed out waiting for the reply.")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(last, encoding="utf-8")
        print(f"Saved {len(last)} chars to {OUT}")
        print("\a")


if __name__ == "__main__":
    main()
