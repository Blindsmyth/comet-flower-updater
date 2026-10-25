"""Generates the styled Comet Flower Drum Machine Emulator and Pattern Editor.

Creates a completely standalone, zero-dependency, single-file HTML5/Web Audio app
with all 24 Zoom 44.1kHz 16-bit PCM samples and 69 pattern step tables embedded.
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WAV_DIR = ROOT / "build" / "drums" / "wav"
PATTERNS_JSON = ROOT / "build" / "drums" / "patterns.json"
UI_ORDER_JSON = ROOT / "tools" / "drums" / "ui_order.json"
LOGO_PNG = ROOT / "assets" / "logo_comet_flower.png"
SPLASH_PNG = ROOT / "assets" / "splash_comet_flower.png"

OUT_HTML_TOOLS = ROOT / "tools" / "drums" / "comet_flower_drums.html"
OUT_HTML_ROOT = ROOT / "comet_flower_drums.html"


def load_b64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def build_studio_html():
    with open(PATTERNS_JSON, "r", encoding="utf-8") as f:
        patterns_data = json.load(f)["patterns"]

    with open(UI_ORDER_JSON, "r", encoding="utf-8") as f:
        ui_order = json.load(f)["order"]

    samples = {}
    for wav_file in sorted(WAV_DIR.glob("*.wav")):
        raw_key = wav_file.stem + ".raw"
        samples[raw_key] = {
            "name": wav_file.stem,
            "raw_key": raw_key,
            "size_bytes": wav_file.stat().st_size,
            "b64": load_b64(wav_file),
        }

    logo_b64 = load_b64(LOGO_PNG) if LOGO_PNG.exists() else ""
    splash_b64 = load_b64(SPLASH_PNG) if SPLASH_PNG.exists() else ""

    app_data = {
        "patterns": patterns_data,
        "ui_order": ui_order,
        "samples": samples,
        "logos": {
            "logo_comet_flower_b64": logo_b64,
            "splash_comet_flower_b64": splash_b64,
        },
    }

    data_json = json.dumps(app_data)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>COMET FLOWER CF-DRUM-9 // Zoom G1X FOUR Rhythm Station & Pattern Lab</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Share+Tech+Mono&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg-chassis: #121418;
    --chassis-metal: #1a1e24;
    --chassis-bevel: #252b35;
    --chassis-shadow: #0a0b0e;
    --panel-border: #2e3644;
    
    /* Theme: Zoom Amber (default) */
    --lcd-bg: #1c1404;
    --lcd-text: #ffaa00;
    --lcd-sub: #b37700;
    --lcd-dim: #473000;
    --lcd-glow: rgba(255, 170, 0, 0.25);
    
    --accent-cyan: #00e5ff;
    --accent-green: #00ff66;
    --accent-orange: #ff7700;
    --accent-red: #ff3344;
    --text-main: #d0d7de;
    --text-muted: #808b96;
    --pad-bg: #21262d;
    --pad-active: #ffaa00;
  }}

  body.theme-green {{
    --lcd-bg: #07190c;
    --lcd-text: #2bff6e;
    --lcd-sub: #17963d;
    --lcd-dim: #093c18;
    --lcd-glow: rgba(43, 255, 110, 0.25);
    --pad-active: #2bff6e;
  }}

  body.theme-cyan {{
    --lcd-bg: #051820;
    --lcd-text: #00f0ff;
    --lcd-sub: #008899;
    --lcd-dim: #02363d;
    --lcd-glow: rgba(0, 240, 255, 0.25);
    --pad-active: #00f0ff;
  }}

  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    user-select: none;
  }}

  body {{
    background-color: #0b0c0f;
    color: var(--text-main);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    min-height: 100vh;
    padding: 16px;
    display: flex;
    justify-content: center;
    align-items: flex-start;
  }}

  /* Machine Chassis */
  .machine-frame {{
    width: 100%;
    max-width: 1320px;
    background: radial-gradient(circle at 50% 0%, #222730 0%, var(--bg-chassis) 70%);
    border: 3px solid #333a46;
    border-radius: 12px;
    box-shadow: 0 25px 60px rgba(0,0,0,0.85), inset 0 1px 1px rgba(255,255,255,0.1);
    position: relative;
    padding: 24px;
    margin-bottom: 30px;
  }}

  /* Corner Hardware Screws */
  .screw {{
    position: absolute;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: radial-gradient(circle, #555e6d 30%, #20242b 90%);
    border: 1px solid #111;
    box-shadow: inset 0 1px 1px rgba(255,255,255,0.3);
  }}
  .screw::after {{
    content: '';
    position: absolute;
    top: 6px;
    left: 2px;
    width: 8px;
    height: 1px;
    background: #111;
  }}
  .screw.tl {{ top: 8px; left: 8px; transform: rotate(25deg); }}
  .screw.tr {{ top: 8px; right: 8px; transform: rotate(70deg); }}
  .screw.bl {{ bottom: 8px; left: 8px; transform: rotate(40deg); }}
  .screw.br {{ bottom: 8px; right: 8px; transform: rotate(115deg); }}

  /* Top Branding Header */
  .top-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 2px solid var(--panel-border);
    padding-bottom: 16px;
    margin-bottom: 20px;
    flex-wrap: wrap;
    gap: 12px;
  }}

  .brand-block {{
    display: flex;
    align-items: center;
    gap: 16px;
  }}

  .cf-logo-box {{
    background: #000;
    border: 2px solid #3a4454;
    padding: 6px 12px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    gap: 12px;
    box-shadow: inset 0 0 10px rgba(0,0,0,0.9);
  }}

  .cf-logo-box img.logo-img {{
    image-rendering: pixelated;
    height: 24px;
    filter: drop-shadow(0 0 6px var(--accent-orange));
  }}

  .brand-sub {{
    font-family: 'Orbitron', monospace;
    font-size: 11px;
    letter-spacing: 2px;
    color: var(--accent-cyan);
    text-transform: uppercase;
  }}

  .device-subtitle {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    color: var(--text-muted);
  }}

  .theme-controls {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}

  .badge-mode {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 4px;
    background: #19202a;
    border: 1px solid #303b4b;
    color: #abbcd5;
  }}

  .theme-btn {{
    background: #19202a;
    border: 1px solid #333d4e;
    color: var(--text-main);
    padding: 5px 10px;
    border-radius: 4px;
    font-size: 11px;
    cursor: pointer;
    font-family: 'Share Tech Mono', monospace;
    transition: all 0.15s ease;
  }}
  .theme-btn:hover {{
    background: #232c3a;
    border-color: var(--accent-cyan);
  }}
  .theme-btn.active {{
    background: #2a3445;
    border-color: var(--accent-cyan);
    color: #fff;
    font-weight: bold;
  }}

  /* Top Control & Screen Dashboard */
  .dashboard-grid {{
    display: grid;
    grid-template-columns: 460px 1fr;
    gap: 20px;
    margin-bottom: 24px;
  }}

  @media (max-width: 1024px) {{
    .dashboard-grid {{ grid-template-columns: 1fr; }}
  }}

  /* Authentic LCD Screen Box */
  .lcd-container {{
    background: var(--lcd-bg);
    border: 3px solid #27303d;
    border-radius: 8px;
    box-shadow: inset 0 0 25px rgba(0,0,0,0.9), 0 0 15px var(--lcd-glow);
    padding: 14px 18px;
    font-family: 'Share Tech Mono', monospace;
    color: var(--lcd-text);
    position: relative;
    overflow: hidden;
  }}

  /* Subtle Scanline Overlay */
  .lcd-container::after {{
    content: " ";
    position: absolute;
    top: 0; left: 0; bottom: 0; right: 0;
    background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%);
    background-size: 100% 3px;
    z-index: 2;
    pointer-events: none;
    opacity: 0.7;
  }}

  .lcd-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px dashed var(--lcd-sub);
    padding-bottom: 6px;
    margin-bottom: 8px;
    font-size: 12px;
  }}

  .lcd-title-row {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 8px;
  }}

  .lcd-pattern-name {{
    font-family: 'Orbitron', monospace;
    font-size: 26px;
    font-weight: 900;
    letter-spacing: 1px;
    text-shadow: 0 0 8px var(--lcd-text);
  }}

  .lcd-pattern-meta {{
    font-size: 14px;
    color: var(--lcd-sub);
    font-weight: bold;
  }}

  .lcd-counters {{
    display: flex;
    justify-content: space-between;
    background: rgba(0,0,0,0.35);
    padding: 6px 10px;
    border-radius: 4px;
    border: 1px solid var(--lcd-dim);
    margin-bottom: 10px;
    font-size: 13px;
  }}

  .lcd-counters span.highlight {{
    color: #fff;
    text-shadow: 0 0 6px var(--lcd-text);
  }}

  /* Oscilloscope Canvas */
  .lcd-canvas-box {{
    position: relative;
    width: 100%;
    height: 70px;
    background: rgba(0, 0, 0, 0.6);
    border: 1px solid var(--lcd-dim);
    border-radius: 4px;
    overflow: hidden;
  }}

  canvas#oscilloscope {{
    width: 100%;
    height: 100%;
    display: block;
  }}

  .lcd-footer {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 8px;
    font-size: 11px;
    color: var(--lcd-sub);
  }}

  /* Hardware Controls Panel */
  .hardware-deck {{
    background: var(--chassis-metal);
    border: 2px solid var(--panel-border);
    border-radius: 8px;
    padding: 16px 20px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 16px;
  }}

  .knobs-row {{
    display: flex;
    justify-content: space-around;
    align-items: center;
    gap: 16px;
    flex-wrap: wrap;
  }}

  .knob-widget {{
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 6px;
  }}

  .knob-label {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    letter-spacing: 1px;
    color: var(--text-muted);
    text-transform: uppercase;
  }}

  .knob-dial {{
    width: 58px;
    height: 58px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 35%, #4a5465 0%, #1c222b 65%, #0e1116 100%);
    border: 2px solid #2f3846;
    box-shadow: 0 4px 8px rgba(0,0,0,0.6), inset 0 1px 2px rgba(255,255,255,0.25);
    position: relative;
    cursor: ns-resize;
    touch-action: none;
  }}

  .knob-pointer {{
    position: absolute;
    top: 6px;
    left: 27px;
    width: 4px;
    height: 14px;
    background: var(--accent-orange);
    border-radius: 2px;
    box-shadow: 0 0 5px var(--accent-orange);
    transform-origin: 2px 23px;
    transform: rotate(0deg);
  }}

  .knob-val {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    color: var(--text-main);
    background: #0f1318;
    padding: 2px 6px;
    border-radius: 3px;
    border: 1px solid #232b36;
    min-width: 44px;
    text-align: center;
  }}

  /* Transport Buttons */
  .transport-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
    flex-wrap: wrap;
    background: #111419;
    padding: 10px 14px;
    border-radius: 6px;
    border: 1px solid #28313e;
  }}

  .btn-transport {{
    background: linear-gradient(to bottom, #2b3340, #1c222b);
    border: 1px solid #3e495b;
    border-radius: 5px;
    color: #fff;
    font-family: 'Share Tech Mono', monospace;
    font-size: 13px;
    font-weight: bold;
    padding: 10px 18px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    box-shadow: 0 3px 6px rgba(0,0,0,0.4), inset 0 1px 1px rgba(255,255,255,0.15);
    transition: all 0.1s ease;
  }}
  .btn-transport:active {{
    transform: translateY(2px);
    box-shadow: 0 1px 2px rgba(0,0,0,0.6);
  }}

  .btn-play.active {{
    background: linear-gradient(to bottom, #00883a, #005022);
    border-color: var(--accent-green);
    color: #fff;
    box-shadow: 0 0 12px rgba(0, 255, 102, 0.4);
  }}
  .btn-rec.active {{
    background: linear-gradient(to bottom, #a3111b, #61070d);
    border-color: var(--accent-red);
    box-shadow: 0 0 12px rgba(255, 51, 68, 0.4);
  }}
  .btn-click.active {{
    background: linear-gradient(to bottom, #b37400, #664200);
    border-color: var(--accent-orange);
  }}

  .led-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #333;
    display: inline-block;
  }}
  .led-dot.green.active {{ background: #00ff66; box-shadow: 0 0 8px #00ff66; }}
  .led-dot.red.active {{ background: #ff3344; box-shadow: 0 0 8px #ff3344; }}
  .led-dot.orange.active {{ background: #ffaa00; box-shadow: 0 0 8px #ffaa00; }}

  /* Tabs Navigation */
  .workspace-tabs {{
    display: flex;
    gap: 4px;
    border-bottom: 2px solid #2e3644;
    margin-bottom: 16px;
  }}

  .tab-btn {{
    background: #181d24;
    border: 1px solid #2e3644;
    border-bottom: none;
    color: var(--text-muted);
    font-family: 'Share Tech Mono', monospace;
    font-size: 13px;
    padding: 10px 20px;
    border-radius: 6px 6px 0 0;
    cursor: pointer;
    transition: all 0.15s ease;
  }}
  .tab-btn:hover {{
    color: var(--text-main);
    background: #202732;
  }}
  .tab-btn.active {{
    background: var(--chassis-metal);
    border-color: var(--accent-cyan);
    color: #fff;
    font-weight: bold;
    border-bottom: 2px solid var(--chassis-metal);
    margin-bottom: -2px;
  }}

  .tab-pane {{
    display: none;
  }}
  .tab-pane.active {{
    display: block;
  }}

  /* 9-Voice Planar Mixer Strip */
  .mixer-card {{
    background: #15181f;
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 20px;
  }}

  .mixer-title-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }}
  .mixer-title {{
    font-family: 'Orbitron', monospace;
    font-size: 13px;
    color: var(--accent-cyan);
    letter-spacing: 1px;
  }}

  .mixer-grid {{
    display: grid;
    grid-template-columns: repeat(9, 1fr);
    gap: 8px;
  }}
  @media (max-width: 900px) {{
    .mixer-grid {{ grid-template-columns: repeat(3, 1fr); }}
  }}

  .voice-strip {{
    background: #1b2029;
    border: 1px solid #2b3442;
    border-radius: 6px;
    padding: 10px 8px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    position: relative;
    transition: border-color 0.1s ease;
  }}
  .voice-strip.trigger-flash {{
    border-color: var(--accent-orange);
    box-shadow: inset 0 0 10px rgba(255, 170, 0, 0.3);
  }}

  .voice-id-badge {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    color: var(--text-muted);
  }}
  .voice-name-tag {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    font-weight: bold;
    color: #fff;
    text-align: center;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
  }}

  .voice-led {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #252c38;
    border: 1px solid #3a4556;
    transition: background 0.05s ease;
  }}
  .voice-led.active {{
    background: var(--accent-orange);
    box-shadow: 0 0 10px var(--accent-orange);
  }}

  .voice-mute-solo {{
    display: flex;
    gap: 4px;
    width: 100%;
  }}
  .btn-ms {{
    flex: 1;
    font-size: 10px;
    padding: 3px 0;
    border-radius: 3px;
    border: 1px solid #3b4455;
    background: #202633;
    color: var(--text-muted);
    cursor: pointer;
    font-weight: bold;
  }}
  .btn-ms.mute.active {{
    background: #801818;
    color: #fff;
    border-color: #ff4444;
  }}
  .btn-ms.solo.active {{
    background: #806618;
    color: #fff;
    border-color: #ffaa00;
  }}

  .voice-fader {{
    -webkit-appearance: slider-vertical;
    width: 16px;
    height: 70px;
    background: #111;
    cursor: pointer;
  }}

  /* Pattern Library Browser */
  .pattern-browser {{
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 16px;
  }}
  @media (max-width: 860px) {{
    .pattern-browser {{ grid-template-columns: 1fr; }}
  }}

  .pattern-filter-box {{
    background: #171b22;
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    padding: 14px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }}

  .search-input {{
    background: #0f1217;
    border: 1px solid #2d3644;
    border-radius: 4px;
    padding: 8px 12px;
    color: #fff;
    font-family: 'Share Tech Mono', monospace;
    font-size: 13px;
    width: 100%;
  }}
  .search-input:focus {{
    outline: none;
    border-color: var(--accent-cyan);
  }}

  .filter-tags {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }}
  .filter-tag-btn {{
    background: #202632;
    border: 1px solid #333d4e;
    color: var(--text-muted);
    font-size: 11px;
    font-family: 'Share Tech Mono', monospace;
    padding: 4px 8px;
    border-radius: 4px;
    cursor: pointer;
  }}
  .filter-tag-btn:hover, .filter-tag-btn.active {{
    background: #2b3546;
    color: #fff;
    border-color: var(--accent-cyan);
  }}

  .pattern-cards-grid {{
    background: #14171e;
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    padding: 14px;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 10px;
    max-height: 480px;
    overflow-y: auto;
  }}

  .pattern-card {{
    background: #1c222c;
    border: 1px solid #2d3747;
    border-radius: 6px;
    padding: 10px 12px;
    cursor: pointer;
    transition: all 0.12s ease;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }}
  .pattern-card:hover {{
    background: #242c39;
    border-color: var(--accent-cyan);
    transform: translateY(-1px);
  }}
  .pattern-card.active {{
    background: #263344;
    border-color: var(--accent-orange);
    box-shadow: 0 0 10px rgba(255, 170, 0, 0.25);
  }}

  .pc-header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
  }}
  .pc-name {{
    font-family: 'Orbitron', monospace;
    font-size: 14px;
    font-weight: 700;
    color: #fff;
  }}
  .pc-idx {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: var(--accent-orange);
  }}
  .pc-sub {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: var(--text-muted);
  }}
  .pc-badge {{
    display: inline-block;
    font-size: 9px;
    font-family: 'Share Tech Mono', monospace;
    padding: 1px 5px;
    border-radius: 3px;
    align-self: flex-start;
    margin-top: 2px;
  }}
  .pc-badge.ok {{ background: #0e3d1c; color: #38ef7d; }}
  .pc-badge.partial {{ background: #3d2f0e; color: #ffb830; }}
  .pc-badge.suspect {{ background: #3d0e12; color: #ff4444; }}

  /* Step Sequencer Editor */
  .editor-container {{
    background: #14171e;
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    padding: 16px;
  }}

  .editor-toolbar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 16px;
    background: #1a202a;
    padding: 10px 14px;
    border-radius: 6px;
    border: 1px solid #2e3848;
  }}

  .editor-tools-group {{
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }}

  .editor-btn {{
    background: #242c3a;
    border: 1px solid #374457;
    color: #fff;
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    padding: 6px 12px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.1s ease;
  }}
  .editor-btn:hover {{
    background: #2e394b;
    border-color: var(--accent-cyan);
  }}
  .editor-btn.active {{
    background: #134250;
    border-color: var(--accent-cyan);
    color: var(--accent-cyan);
  }}

  .editor-grid-scroll {{
    overflow-x: auto;
    padding-bottom: 10px;
  }}

  .grid-table {{
    display: grid;
    gap: 4px;
    min-width: 800px;
  }}

  .grid-header-row {{
    display: grid;
    grid-template-columns: 160px repeat(var(--total-steps, 16), 1fr);
    gap: 3px;
    margin-bottom: 4px;
  }}

  .grid-step-num {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 10px;
    text-align: center;
    color: var(--text-muted);
    padding: 2px 0;
  }}
  .grid-step-num.beat-head {{
    color: var(--accent-cyan);
    font-weight: bold;
    border-bottom: 1px solid var(--accent-cyan);
  }}
  .grid-step-num.current-playhead {{
    background: var(--accent-orange);
    color: #000;
    border-radius: 2px;
    font-weight: bold;
  }}

  .grid-track-row {{
    display: grid;
    grid-template-columns: 160px repeat(var(--total-steps, 16), 1fr);
    gap: 3px;
    align-items: center;
  }}

  .track-label-cell {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #1a202a;
    border: 1px solid #2d3747;
    border-radius: 4px;
    padding: 4px 8px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    color: #fff;
  }}

  .track-select {{
    background: transparent;
    border: none;
    color: #fff;
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    outline: none;
    cursor: pointer;
    max-width: 110px;
  }}
  .track-select option {{
    background: #14171e;
    color: #fff;
  }}

  .step-cell {{
    height: 38px;
    background: #1c222c;
    border: 1px solid #2b3544;
    border-radius: 4px;
    cursor: pointer;
    position: relative;
    overflow: hidden;
    transition: background 0.08s ease;
  }}
  .step-cell.beat-bar-start {{
    border-left: 2px solid #4a576d;
  }}
  .step-cell:hover {{
    background: #252d3a;
    border-color: #435269;
  }}
  .step-cell.active {{
    background: #3b2c15;
    border-color: var(--accent-orange);
  }}
  .step-cell.active .step-level-bar {{
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--accent-orange);
    box-shadow: 0 0 6px var(--accent-orange);
  }}
  .step-cell.current-cursor {{
    box-shadow: inset 0 0 0 2px #fff;
  }}

  /* Silicone Drum Pads */
  .pads-container {{
    background: #15181f;
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    padding: 18px;
    margin-bottom: 20px;
  }}

  .pads-title-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
  }}

  .pads-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    max-width: 720px;
    margin: 0 auto 20px auto;
  }}

  .drum-pad {{
    aspect-ratio: 1.25 / 1;
    background: radial-gradient(circle at 40% 40%, #2e3644 0%, #1c222c 70%, #13171e 100%);
    border: 2px solid #3c485a;
    border-radius: 8px;
    box-shadow: 0 6px 12px rgba(0,0,0,0.5), inset 0 1px 1px rgba(255,255,255,0.2);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 12px;
    cursor: pointer;
    position: relative;
    transition: all 0.08s ease;
  }}
  .drum-pad:active, .drum-pad.hit-active {{
    background: radial-gradient(circle at 50% 50%, var(--pad-active) 0%, #8c5b00 80%);
    border-color: #fff;
    box-shadow: 0 0 20px var(--pad-active);
    transform: scale(0.97);
  }}

  .pad-top-row {{
    display: flex;
    justify-content: space-between;
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: var(--text-muted);
  }}
  .pad-key {{
    background: rgba(0,0,0,0.4);
    padding: 1px 6px;
    border-radius: 3px;
    border: 1px solid #354050;
    color: var(--accent-cyan);
    font-weight: bold;
  }}
  .pad-voice-title {{
    font-family: 'Orbitron', monospace;
    font-size: 15px;
    font-weight: 700;
    color: #fff;
    text-align: center;
    text-shadow: 0 2px 4px rgba(0,0,0,0.8);
  }}
  .pad-sample-sub {{
    font-family: 'Share Tech Mono', monospace;
    font-size: 11px;
    color: #8fa0b5;
    text-align: center;
  }}

  /* Full Soundboard 24 Samples */
  .soundboard-drawer {{
    background: #111419;
    border: 1px solid #28313e;
    border-radius: 6px;
    padding: 14px;
    margin-top: 14px;
  }}
  .soundboard-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: 8px;
    margin-top: 10px;
  }}
  .sb-sample-btn {{
    background: #1b2029;
    border: 1px solid #2d3644;
    border-radius: 4px;
    padding: 8px 6px;
    color: #cad4e0;
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    cursor: pointer;
    text-align: center;
    transition: all 0.1s ease;
  }}
  .sb-sample-btn:hover {{
    background: #252d3a;
    border-color: var(--accent-cyan);
    color: #fff;
  }}
  .sb-sample-btn:active, .sb-sample-btn.hit {{
    background: var(--accent-orange);
    color: #000;
    font-weight: bold;
  }}

  /* Bottom Actions Bar */
  .bottom-io-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 12px;
    background: #151921;
    border: 1px solid var(--panel-border);
    border-radius: 8px;
    padding: 14px 18px;
  }}
  .io-group {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }}
  .btn-io {{
    background: #202632;
    border: 1px solid #374355;
    color: #fff;
    font-family: 'Share Tech Mono', monospace;
    font-size: 12px;
    padding: 8px 14px;
    border-radius: 5px;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.12s ease;
  }}
  .btn-io:hover {{
    background: #2b3546;
    border-color: var(--accent-cyan);
  }}
  .btn-io.primary {{
    background: linear-gradient(to bottom, #b37400, #734a00);
    border-color: var(--accent-orange);
    font-weight: bold;
  }}

  /* Hidden file input */
  #importFileInput {{
    display: none;
  }}

  /* Toast Notification */
  #toast {{
    position: fixed;
    bottom: 30px;
    right: 30px;
    background: #1f2530;
    border: 1px solid var(--accent-cyan);
    color: #fff;
    padding: 12px 20px;
    border-radius: 6px;
    font-family: 'Share Tech Mono', monospace;
    font-size: 13px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.8);
    opacity: 0;
    transform: translateY(15px);
    transition: all 0.2s ease;
    pointer-events: none;
    z-index: 999;
  }}
  #toast.show {{
    opacity: 1;
    transform: translateY(0);
  }}
</style>
</head>
<body>

<div class="machine-frame">
  <!-- Corner Screws -->
  <div class="screw tl"></div>
  <div class="screw tr"></div>
  <div class="screw bl"></div>
  <div class="screw br"></div>

  <!-- Header Section with Comet Flower Logo -->
  <div class="top-bar">
    <div class="brand-block">
      <div class="cf-logo-box">
        <img class="logo-img" src="data:image/png;base64,{logo_b64}" alt="COMET FLOWER" title="COMET FLOWER LOGO">
        <div>
          <div class="brand-sub">CF-DRUM-9 LAB</div>
          <div class="device-subtitle">ZOOM G1X FOUR RHYTHM EMULATOR & PATTERN SUITE</div>
        </div>
      </div>
      <div class="badge-mode">44.1 kHz 16-BIT // 9-VOICE PLANAR BUS</div>
    </div>

    <div class="theme-controls">
      <span style="font-size: 11px; font-family: 'Share Tech Mono', monospace; color: var(--text-muted);">LCD THEME:</span>
      <button class="theme-btn active" onclick="setTheme('amber')">ZOOM AMBER</button>
      <button class="theme-btn" onclick="setTheme('green')">CRT GREEN</button>
      <button class="theme-btn" onclick="setTheme('cyan')">OLED CYAN</button>
    </div>
  </div>

  <!-- Main Dashboard: LCD & Knobs -->
  <div class="dashboard-grid">
    <!-- Backlit LCD Screen -->
    <div class="lcd-container">
      <div class="lcd-header">
        <span>★ COMET FLOWER DSP // ENGINE 0xc016f7fc</span>
        <span id="lcdEngineState">STOPPED</span>
      </div>

      <div class="lcd-title-row">
        <div class="lcd-pattern-name" id="lcdPatternName">Rock1</div>
        <div class="lcd-pattern-meta" id="lcdPatternMeta">UI #07 // 4/4 METER</div>
      </div>

      <div class="lcd-counters">
        <div>BAR: <span class="highlight" id="lcdBarNum">01</span>/<span id="lcdTotalBars">02</span></div>
        <div>BEAT: <span class="highlight" id="lcdBeatNum">01</span>.<span id="lcdTickNum">00</span></div>
        <div>TEMPO: <span class="highlight" id="lcdBpmDisplay">120.0</span> BPM</div>
        <div>VOL: <span class="highlight" id="lcdVolDisplay">80%</span></div>
      </div>

      <div class="lcd-canvas-box">
        <canvas id="oscilloscope" width="420" height="70"></canvas>
      </div>

      <div class="lcd-footer">
        <span id="lcdConfidence">DECODE: OK (REAL FIRMWARE STEP GRID)</span>
        <span id="lcdActiveVoices">6 VOICES ACTIVE</span>
      </div>
    </div>

    <!-- Hardware Deck: Knobs & Transport -->
    <div class="hardware-deck">
      <div class="knobs-row">
        <!-- Tempo Knob -->
        <div class="knob-widget">
          <div class="knob-label">TEMPO (BPM)</div>
          <div class="knob-dial" id="knobTempo" data-val="120" data-min="40" data-max="250">
            <div class="knob-pointer"></div>
          </div>
          <div class="knob-val" id="valTempo">120</div>
        </div>

        <!-- Master Volume Knob (0-100) -->
        <div class="knob-widget">
          <div class="knob-label">DRUM VOL</div>
          <div class="knob-dial" id="knobVol" data-val="80" data-min="0" data-max="100">
            <div class="knob-pointer"></div>
          </div>
          <div class="knob-val" id="valVol">80</div>
        </div>

        <!-- Ambience Mix Knob (0-100) -->
        <div class="knob-widget">
          <div class="knob-label">AMBIENCE</div>
          <div class="knob-dial" id="knobAmb" data-val="75" data-min="0" data-max="100">
            <div class="knob-pointer"></div>
          </div>
          <div class="knob-val" id="valAmb">75%</div>
        </div>

        <!-- Swing Knob (0-50%) -->
        <div class="knob-widget">
          <div class="knob-label">SWING</div>
          <div class="knob-dial" id="knobSwing" data-val="0" data-min="0" data-max="50">
            <div class="knob-pointer"></div>
          </div>
          <div class="knob-val" id="valSwing">0%</div>
        </div>
      </div>

      <!-- Transport Row -->
      <div class="transport-row">
        <div style="display: flex; gap: 8px;">
          <button class="btn-transport btn-play" id="btnPlay" onclick="togglePlay()">
            <span class="led-dot green" id="ledPlay"></span> PLAY
          </button>
          <button class="btn-transport" onclick="stopPlayback()">
            STOP
          </button>
          <button class="btn-transport btn-rec" id="btnRec" onclick="toggleRecord()">
            <span class="led-dot red" id="ledRec"></span> REC
          </button>
        </div>

        <div style="display: flex; gap: 8px; align-items: center;">
          <button class="btn-transport btn-click" id="btnClick" onclick="toggleClick()">
            <span class="led-dot orange" id="ledClick"></span> CLICK
          </button>
          <button class="btn-transport" id="btnTapTempo" onclick="handleTapTempo()">
            TAP
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- 9-Voice Planar Mixer Strip -->
  <div class="mixer-card">
    <div class="mixer-title-row">
      <div class="mixer-title">★ 9-VOICE PLANAR MIX BUS (0x11f039b0..0x11f03acf)</div>
      <div style="font-family: 'Share Tech Mono', monospace; font-size: 11px; color: var(--text-muted);">
        PER-VOICE PAN & GAIN ENGINE
      </div>
    </div>

    <div class="mixer-grid" id="mixerGrid">
      <!-- Generated 9 voice strips -->
    </div>
  </div>

  <!-- Navigation Tabs -->
  <div class="workspace-tabs">
    <button class="tab-btn active" onclick="switchTab('tabLibrary')">1. PATTERN EMULATOR & LIBRARY (69 PATTERNS)</button>
    <button class="tab-btn" onclick="switchTab('tabEditor')">2. PATTERN SEQUENCER & LAB EDITOR</button>
    <button class="tab-btn" onclick="switchTab('tabPads')">3. TACTILE DRUM PADS & 24-SAMPLE SOUNDBOARD</button>
  </div>

  <!-- TAB 1: Pattern Library -->
  <div class="tab-pane active" id="tabLibrary">
    <div class="pattern-browser">
      <div class="pattern-filter-box">
        <input type="text" class="search-input" id="patternSearch" placeholder="Search patterns (e.g. Rock, Blues, 16Beats)..." oninput="filterPatterns()">
        
        <div style="font-family: 'Share Tech Mono', monospace; font-size: 11px; color: var(--text-muted); margin-top: 4px;">CATEGORIES:</div>
        <div class="filter-tags" id="categoryTags">
          <button class="filter-tag-btn active" onclick="setCategoryFilter('all')">ALL (69)</button>
          <button class="filter-tag-btn" onclick="setCategoryFilter('Rock')">ROCK (11)</button>
          <button class="filter-tag-btn" onclick="setCategoryFilter('Metal')">METAL/PUNK (6)</button>
          <button class="filter-tag-btn" onclick="setCategoryFilter('Funk')">FUNK/R&B (8)</button>
          <button class="filter-tag-btn" onclick="setCategoryFilter('Pop')">POP/INDIE (6)</button>
          <button class="filter-tag-btn" onclick="setCategoryFilter('Jazz')">JAZZ/BLUES (7)</button>
          <button class="filter-tag-btn" onclick="setCategoryFilter('Latin')">LATIN/REGGAE (9)</button>
          <button class="filter-tag-btn" onclick="setCategoryFilter('Metro')">METRONOME (5)</button>
        </div>

        <div style="margin-top: 10px; border-top: 1px solid #27303d; padding-top: 10px;">
          <label style="font-family: 'Share Tech Mono', monospace; font-size: 12px; color: var(--text-muted); display: flex; align-items: center; gap: 8px; cursor: pointer;">
            <input type="checkbox" id="sortUiOrder" checked onchange="renderPatternCards()">
            Use Pedal UI Display Order
          </label>
        </div>

        <div style="margin-top: 10px;">
          <button class="btn-io" style="width: 100%; justify-content: center;" onclick="loadPatternToEditor()">
            ✎ EDIT CURRENT IN SEQUENCER
          </button>
        </div>
      </div>

      <!-- Pattern Cards Container -->
      <div class="pattern-cards-grid" id="patternCardsGrid">
        <!-- Rendered via JS -->
      </div>
    </div>
  </div>

  <!-- TAB 2: Pattern Editor -->
  <div class="tab-pane" id="tabEditor">
    <div class="editor-container">
      <div class="editor-toolbar">
        <div class="editor-tools-group">
          <span style="font-family: 'Share Tech Mono', monospace; font-size: 12px; color: var(--text-muted);">PATTERN:</span>
          <input type="text" id="editPatternName" value="NewBeat" class="search-input" style="width: 130px; padding: 4px 8px;">

          <span style="font-family: 'Share Tech Mono', monospace; font-size: 12px; color: var(--text-muted);">METER:</span>
          <select id="editBeatsPerBar" class="editor-btn" onchange="updateEditorMeter()">
            <option value="3">3/4 (Waltz)</option>
            <option value="4" selected>4/4 (Standard)</option>
            <option value="5">5/4 (Odd Meter)</option>
            <option value="6">6/8 (Compound)</option>
            <option value="12">12/8 (Shuffle/Blues)</option>
          </select>

          <span style="font-family: 'Share Tech Mono', monospace; font-size: 12px; color: var(--text-muted);">BARS:</span>
          <select id="editBarsCount" class="editor-btn" onchange="updateEditorBars()">
            <option value="1">1 Bar</option>
            <option value="2" selected>2 Bars</option>
            <option value="4">4 Bars</option>
          </select>

          <span style="font-family: 'Share Tech Mono', monospace; font-size: 12px; color: var(--text-muted);">GRID:</span>
          <select id="editStepRes" class="editor-btn" onchange="updateEditorResolution()">
            <option value="3" selected>16th Notes (3 ticks)</option>
            <option value="4">8th Triplets (4 ticks)</option>
            <option value="6">8th Notes (6 ticks)</option>
          </select>
        </div>

        <div class="editor-tools-group">
          <button class="editor-btn" onclick="addEditorTrack()">+ ADD TRACK</button>
          <button class="editor-btn" onclick="clearEditorGrid()">CLEAR</button>
          <button class="editor-btn" onclick="humanizeEditorGroove()">HUMANIZE</button>
          <button class="editor-btn" id="btnAutoAmb" onclick="toggleAutoAmbience()">AUTO-AMBIENCE: ON</button>
          <button class="editor-btn" onclick="shiftEditorSteps(-1)">&lt; SHIFT</button>
          <button class="editor-btn" onclick="shiftEditorSteps(1)">SHIFT &gt;</button>
        </div>
      </div>

      <!-- Sequencer Step Grid -->
      <div class="editor-grid-scroll">
        <div class="grid-table" id="editorGridTable">
          <!-- Step Sequencer Rows generated in JS -->
        </div>
      </div>
    </div>
  </div>

  <!-- TAB 3: Pads & Soundboard -->
  <div class="tab-pane" id="tabPads">
    <div class="pads-container">
      <div class="pads-title-row">
        <div style="font-family: 'Orbitron', monospace; font-size: 14px; color: var(--accent-cyan);">
          ★ SILICONE PERFORMANCE PADS // VELOCITY SENSITIVE (TAP / KEYS 1-9)
        </div>
        <div style="font-family: 'Share Tech Mono', monospace; font-size: 12px; color: var(--text-muted);">
          Tap higher on pad for ghost hits, lower for full velocity
        </div>
      </div>

      <div class="pads-grid" id="drumPadsGrid">
        <!-- 9 Pads generated by JS -->
      </div>

      <!-- Full 24-Sample Bank Drawer -->
      <div class="soundboard-drawer">
        <div style="font-family: 'Share Tech Mono', monospace; font-size: 12px; color: var(--accent-orange); font-weight: bold;">
          ALL 24 EXTRACTED FIRMWARE SAMPLES (44.1 kHz 16-BIT SIGNED MONO PCM)
        </div>
        <div class="soundboard-grid" id="soundboardGrid">
          <!-- 24 Samples generated by JS -->
        </div>
      </div>
    </div>
  </div>

  <!-- Bottom File I/O Bar -->
  <div class="bottom-io-bar">
    <div class="io-group">
      <button class="btn-io primary" onclick="exportCliPatternJson()">
        💾 EXPORT PATTERN JSON (CLI 'drum_machine.py new')
      </button>
      <button class="btn-io" onclick="exportRomStepsJson()">
        📋 EXPORT ROM STEP EVENTS JSON
      </button>
      <button class="btn-io" onclick="document.getElementById('importFileInput').click()">
        📂 IMPORT PATTERN JSON
      </button>
      <input type="file" id="importFileInput" accept=".json" onchange="handleImportFile(event)">
    </div>

    <div class="io-group">
      <button class="btn-io primary" onclick="renderOfflineWav()">
        🎵 RENDER & DOWNLOAD .WAV (44.1kHz 16-BIT)
      </button>
      <button class="btn-io" onclick="copyCliCommand()">
        💻 COPY CLI RENDER CMD
      </button>
    </div>
  </div>
</div>

<!-- Toast Popup Notification -->
<div id="toast">Pattern Loaded</div>

<script>
// Embedded Data Asset
window.COMET_FLOWER_DATA = {data_json};
</script>
<script>
(() => {{
  const DATA = window.COMET_FLOWER_DATA;
  const SAMPLES = DATA.samples;
  const PATTERNS = DATA.patterns;
  const UI_ORDER = DATA.ui_order;

  // Audio Context & State
  let audioCtx = null;
  const sampleBuffers = {{}};
  let masterGainNode = null;
  let analyserNode = null;

  // Mixer Bus (9 voice slots)
  const voiceStrips = [];
  for (let i = 0; i < 9; i++) {{
    voiceStrips.push({{
      slot: i,
      gainNode: null,
      panNode: null,
      sampleName: "",
      volume: 1.0,
      pan: 0.0,
      mute: false,
      solo: false
    }});
  }}

  // Engine playback state
  let isPlaying = false;
  let isRecording = false;
  let includeClick = false;
  let autoAmbience = true;

  let bpm = 120;
  let masterVol = 80;
  let ambienceLevel = 75;
  let swingPct = 0;

  let currentPattern = PATTERNS[7]; // default to Rock1
  let currentBars = 2;
  let playbackStartTime = 0;
  let nextScheduleTick = 0;
  let schedulerTimer = null;
  const TICKS_PER_BEAT = 12;

  // Sequencer / Editor State
  let editorTracks = [];
  let editorStepsPerBar = 16;
  let editorBeatsPerBar = 4;
  let editorBeatUnit = 4;
  let editorBars = 2;
  let editorResolutionTicks = 3; // 16th notes
  let currentPlayheadStep = -1;

  // Tap tempo state
  let tapTimes = [];

  // Theme
  function setTheme(t) {{
    document.body.classList.remove('theme-green', 'theme-cyan');
    if (t === 'green') document.body.classList.add('theme-green');
    if (t === 'cyan') document.body.classList.add('theme-cyan');
    document.querySelectorAll('.theme-btn').forEach(b => b.classList.remove('active'));
    event?.target?.classList.add('active');
  }}
  window.setTheme = setTheme;

  function showToast(msg) {{
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 2200);
  }}

  // -------------------------------------------------------------
  // AUDIO ENGINE INITIALIZATION
  // -------------------------------------------------------------
  async function initAudio() {{
    if (audioCtx) return;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContextClass({{ sampleRate: 44100 }});

    masterGainNode = audioCtx.createGain();
    masterGainNode.gain.value = masterVol / 100.0;

    analyserNode = audioCtx.createAnalyser();
    analyserNode.fftSize = 256;

    masterGainNode.connect(analyserNode);
    analyserNode.connect(audioCtx.destination);

    // Setup 9 voice buses
    for (let i = 0; i < 9; i++) {{
      const g = audioCtx.createGain();
      let p = null;
      if (audioCtx.createStereoPanner) {{
        p = audioCtx.createStereoPanner();
        g.connect(p);
        p.connect(masterGainNode);
      }} else {{
        g.connect(masterGainNode);
      }}
      voiceStrips[i].gainNode = g;
      voiceStrips[i].panNode = p;
    }}

    // Decode all 24 WAV audio samples
    const sampleKeys = Object.keys(SAMPLES);
    for (const k of sampleKeys) {{
      try {{
        const b64 = SAMPLES[k].b64;
        const binary = atob(b64);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        const buf = await audioCtx.decodeAudioData(bytes.buffer);
        sampleBuffers[k] = buf;
      }} catch (err) {{
        console.warn("Failed decoding sample:", k, err);
      }}
    }}
    console.log("Comet Flower Engine initialized. 24 samples decoded.");
    startOscilloscope();
  }}

  function ensureAudio() {{
    if (!audioCtx) {{
      initAudio();
    }} else if (audioCtx.state === 'suspended') {{
      audioCtx.resume();
    }}
  }}

  // -------------------------------------------------------------
  // TRIGGER VOICE
  // -------------------------------------------------------------
  function triggerVoice(rawSampleName, level0_15, time = 0, slotHint = -1) {{
    if (!audioCtx) return;
    const buf = sampleBuffers[rawSampleName];
    if (!buf) return;

    // Check slot
    let slot = slotHint;
    if (slot < 0 || slot >= 9) {{
      slot = voiceStrips.findIndex(v => v.sampleName === rawSampleName);
      if (slot === -1) slot = 1; // fallback
    }}

    const strip = voiceStrips[slot];
    if (strip.mute) return;

    // Check solo
    const anySolo = voiceStrips.some(v => v.solo);
    if (anySolo && !strip.solo) return;

    const src = audioCtx.createBufferSource();
    src.buffer = buf;

    // Velocity gain
    const velGain = audioCtx.createGain();
    const isAmb = rawSampleName.includes("Amb");
    let gainVal = Math.max(0.01, Math.min(1.0, (level0_15 / 15.0)));
    if (isAmb) {{
      gainVal *= (ambienceLevel / 100.0);
    }}
    velGain.gain.setValueAtTime(gainVal, time || audioCtx.currentTime);

    src.connect(velGain);
    velGain.connect(strip.gainNode);

    const playAt = time > 0 ? time : audioCtx.currentTime;
    src.start(playAt);

    // Visual trigger flash
    const delayMs = Math.max(0, (playAt - audioCtx.currentTime) * 1000);
    setTimeout(() => {{
      flashVoice(slot, rawSampleName);
    }}, delayMs);
  }}

  function flashVoice(slot, rawSampleName) {{
    const stripEl = document.getElementById(`voice-strip-${{slot}}`);
    if (stripEl) {{
      stripEl.classList.add('trigger-flash');
      const led = stripEl.querySelector('.voice-led');
      if (led) led.classList.add('active');
      setTimeout(() => {{
        stripEl.classList.remove('trigger-flash');
        if (led) led.classList.remove('active');
      }}, 90);
    }}

    // Pad flash
    const pad = document.querySelector(`.drum-pad[data-slot="${{slot}}"]`);
    if (pad) {{
      pad.classList.add('hit-active');
      setTimeout(() => pad.classList.remove('hit-active'), 80);
    }}
  }}

  // -------------------------------------------------------------
  // PATTERN ENGINE & PLAYBACK
  // -------------------------------------------------------------
  function startPlayback() {{
    ensureAudio();
    if (isPlaying) return;
    isPlaying = true;

    document.getElementById('btnPlay').classList.add('active');
    document.getElementById('ledPlay').classList.add('active');
    document.getElementById('lcdEngineState').textContent = 'RUNNING';

    playbackStartTime = audioCtx.currentTime;
    nextScheduleTick = 0;

    schedulerTimer = setInterval(schedulerTick, 20);
  }}

  function stopPlayback() {{
    isPlaying = false;
    if (schedulerTimer) clearInterval(schedulerTimer);
    schedulerTimer = null;

    document.getElementById('btnPlay').classList.remove('active');
    document.getElementById('ledPlay').classList.remove('active');
    document.getElementById('btnRec').classList.remove('active');
    document.getElementById('ledRec').classList.remove('active');
    document.getElementById('lcdEngineState').textContent = 'STOPPED';

    nextScheduleTick = 0;
    updateLcdCounters(0);
    updatePlayheadCursor(-1);
  }}

  function togglePlay() {{
    if (isPlaying) stopPlayback();
    else startPlayback();
  }}

  function toggleRecord() {{
    isRecording = !isRecording;
    const btn = document.getElementById('btnRec');
    const led = document.getElementById('ledRec');
    if (isRecording) {{
      btn.classList.add('active');
      led.classList.add('active');
      showToast("RECORD MODE ACTIVE: Tap pads to insert hits live!");
      if (!isPlaying) startPlayback();
    }} else {{
      btn.classList.remove('active');
      led.classList.remove('active');
      showToast("RECORD MODE OFF");
    }}
  }}

  function toggleClick() {{
    includeClick = !includeClick;
    const btn = document.getElementById('btnClick');
    const led = document.getElementById('ledClick');
    if (includeClick) {{
      btn.classList.add('active');
      led.classList.add('active');
      showToast("CLICK TRACK ON");
    }} else {{
      btn.classList.remove('active');
      led.classList.remove('active');
      showToast("CLICK TRACK OFF");
    }}
  }}

  function schedulerTick() {{
    if (!isPlaying || !audioCtx) return;

    const secPerTick = 60.0 / bpm / TICKS_PER_BEAT;
    const loopLengthTicks = currentPattern.loop_length_ticks || (currentPattern.beats_per_bar * TICKS_PER_BEAT * currentBars);
    const scheduleAheadSec = 0.12;

    const curAudioTime = audioCtx.currentTime;

    while (true) {{
      const tickAudioTime = playbackStartTime + (nextScheduleTick * secPerTick);
      if (tickAudioTime > curAudioTime + scheduleAheadSec) break;

      const tickInLoop = nextScheduleTick % loopLengthTicks;

      // Find all events occurring at tickInLoop
      if (currentPattern.steps && currentPattern.steps.length > 0) {{
        for (const ev of currentPattern.steps) {{
          if (ev.tick === tickInLoop) {{
            if (ev.voice_id === 9 && !includeClick) continue;
            let sampleName = ev.sample;
            if (!sampleName) {{
              // If unmapped auxiliary, fallback to slot or similar
              if (ev.slot !== undefined && currentPattern.voices[ev.slot]) {{
                sampleName = currentPattern.voices[ev.slot];
              }}
            }}
            if (sampleName) {{
              // Apply swing if 16th note offbeat (tick 3 or 9 in 12-tick beat)
              let timeOffset = 0;
              const tickInBeat = tickInLoop % TICKS_PER_BEAT;
              if (swingPct > 0 && (tickInBeat === 3 || tickInBeat === 9)) {{
                timeOffset = (swingPct / 100.0) * (secPerTick * 1.5);
              }}
              triggerVoice(sampleName, ev.level, tickAudioTime + timeOffset, ev.slot);
            }}
          }}
        }}
      }}

      // UI update timer for counter and playhead
      const delayMs = Math.max(0, (tickAudioTime - curAudioTime) * 1000);
      const scheduledTick = nextScheduleTick;
      setTimeout(() => {{
        if (isPlaying) {{
          updateLcdCounters(scheduledTick % loopLengthTicks);
          const stepIndex = Math.floor((scheduledTick % loopLengthTicks) / editorResolutionTicks);
          updatePlayheadCursor(stepIndex);
        }}
      }}, delayMs);

      nextScheduleTick++;
    }}
  }}

  function updateLcdCounters(tickInLoop) {{
    const bpb = currentPattern.beats_per_bar || 4;
    const barTicks = bpb * TICKS_PER_BEAT;
    const bar = Math.floor(tickInLoop / barTicks) + 1;
    const beat = Math.floor((tickInLoop % barTicks) / TICKS_PER_BEAT) + 1;
    const subTick = tickInLoop % TICKS_PER_BEAT;

    document.getElementById('lcdBarNum').textContent = String(bar).padStart(2, '0');
    document.getElementById('lcdBeatNum').textContent = String(beat).padStart(2, '0');
    document.getElementById('lcdTickNum').textContent = String(subTick).padStart(2, '0');
  }}

  function updatePlayheadCursor(stepIdx) {{
    if (stepIdx === currentPlayheadStep) return;
    currentPlayheadStep = stepIdx;

    document.querySelectorAll('.grid-step-num').forEach((el, i) => {{
      if (i === stepIdx) el.classList.add('current-playhead');
      else el.classList.remove('current-playhead');
    }});

    document.querySelectorAll('.step-cell').forEach(el => {{
      const s = parseInt(el.dataset.step);
      if (s === stepIdx) el.classList.add('current-cursor');
      else el.classList.remove('current-cursor');
    }});
  }}

  // -------------------------------------------------------------
  // PATTERN SELECTION & MIXER POPULATION
  // -------------------------------------------------------------
  function selectPattern(pat, startNow = false) {{
    currentPattern = pat;
    currentBars = pat.loop_bars || 2;

    // Update LCD
    document.getElementById('lcdPatternName').textContent = pat.name;
    const uiMatch = UI_ORDER.find(u => u.record === pat.index);
    const uiNum = uiMatch ? `UI #${{String(uiMatch.ui).padStart(2, '0')}}` : `ROM #${{pat.index}}`;
    document.getElementById('lcdPatternMeta').textContent = `${{uiNum}} // ${{pat.beats_per_bar}}/${{pat.beat_unit}} METER`;
    document.getElementById('lcdTotalBars').textContent = String(currentBars).padStart(2, '0');

    let confText = `DECODE: ${{pat.decode_confidence ? pat.decode_confidence.toUpperCase() : 'OK'}}`;
    if (pat.decode_confidence === 'suspect') confText += ' (GENERIC FALLBACK)';
    document.getElementById('lcdConfidence').textContent = confText;

    // Count mapped voices
    const activeVoices = pat.voices.filter(v => Boolean(v));
    document.getElementById('lcdActiveVoices').textContent = `${{activeVoices.length}} VOICES ASSIGNED`;

    // Populate Mixer
    populateMixer(pat);
    // Populate Pads
    populatePads(pat);
    // Populate Editor
    syncPatternToEditor(pat);

    renderPatternCards();
    showToast(`Loaded ${{pat.name}} (${{pat.beats_per_bar}}/${{pat.beat_unit}})`);

    if (startNow) startPlayback();
  }}

  function populateMixer(pat) {{
    const container = document.getElementById('mixerGrid');
    container.innerHTML = '';

    for (let slot = 0; slot < 9; slot++) {{
      const sample = pat.voices[slot] || "";
      voiceStrips[slot].sampleName = sample;

      const baseName = sample ? sample.replace(".raw", "") : "EMPTY";
      const isClick = slot === 0;

      const stripEl = document.createElement('div');
      stripEl.className = 'voice-strip';
      stripEl.id = `voice-strip-${{slot}}`;

      stripEl.innerHTML = `
        <div class="voice-id-badge">SLOT ${{slot}}${{isClick ? ' [CLICK]' : ''}}</div>
        <div class="voice-led"></div>
        <div class="voice-name-tag" title="${{sample}}">${{baseName}}</div>
        <div class="voice-mute-solo">
          <button class="btn-ms mute ${{voiceStrips[slot].mute ? 'active' : ''}}" onclick="toggleVoiceMute(${{slot}})">M</button>
          <button class="btn-ms solo ${{voiceStrips[slot].solo ? 'active' : ''}}" onclick="toggleVoiceSolo(${{slot}})">S</button>
        </div>
        <input type="range" class="voice-fader" orient="vertical" min="0" max="100" value="${{Math.round(voiceStrips[slot].volume * 100)}}" oninput="setVoiceVolume(${{slot}}, this.value)">
      `;
      container.appendChild(stripEl);
    }}
  }}

  function toggleVoiceMute(slot) {{
    voiceStrips[slot].mute = !voiceStrips[slot].mute;
    populateMixer(currentPattern);
  }}
  window.toggleVoiceMute = toggleVoiceMute;

  function toggleVoiceSolo(slot) {{
    voiceStrips[slot].solo = !voiceStrips[slot].solo;
    populateMixer(currentPattern);
  }}
  window.toggleVoiceSolo = toggleVoiceSolo;

  function setVoiceVolume(slot, val) {{
    voiceStrips[slot].volume = val / 100.0;
    if (voiceStrips[slot].gainNode) {{
      voiceStrips[slot].gainNode.gain.setValueAtTime(voiceStrips[slot].volume, audioCtx.currentTime);
    }}
  }}
  window.setVoiceVolume = setVoiceVolume;

  // -------------------------------------------------------------
  // PATTERN CARDS BROWSER
  // -------------------------------------------------------------
  let currentCategory = 'all';

  function setCategoryFilter(cat) {{
    currentCategory = cat;
    document.querySelectorAll('.filter-tag-btn').forEach(b => b.classList.remove('active'));
    event?.target?.classList.add('active');
    renderPatternCards();
  }}
  window.setCategoryFilter = setCategoryFilter;

  function filterPatterns() {{
    renderPatternCards();
  }}
  window.filterPatterns = filterPatterns;

  function renderPatternCards() {{
    const container = document.getElementById('patternCardsGrid');
    container.innerHTML = '';

    const useUiOrder = document.getElementById('sortUiOrder').checked;
    const query = document.getElementById('patternSearch').value.toLowerCase().trim();

    let list = [];
    if (useUiOrder) {{
      for (const u of UI_ORDER) {{
        if (u.record !== null && u.record !== undefined) {{
          const p = PATTERNS.find(x => x.index === u.record);
          if (p) list.push({{ ...p, uiNum: u.ui }});
        }}
      }}
    }} else {{
      list = PATTERNS.map(p => ({{ ...p, uiNum: null }}));
    }}

    // Filter
    list = list.filter(p => {{
      const n = p.name.toLowerCase();
      if (query && !n.includes(query)) return false;

      if (currentCategory === 'all') return true;
      if (currentCategory === 'Rock') return n.includes('rock') || n.includes('8beats') || n.includes('16beats');
      if (currentCategory === 'Metal') return n.includes('mtl') || n.includes('punk') || n.includes('emo') || n.includes('heavy');
      if (currentCategory === 'Funk') return n.includes('funk') || n.includes('r&b') || n.includes('soul') || n.includes('motown');
      if (currentCategory === 'Pop') return n.includes('pop') || n.includes('indie') || n.includes('disco');
      if (currentCategory === 'Jazz') return n.includes('jazz') || n.includes('blues') || n.includes('swing') || n.includes('fusion');
      if (currentCategory === 'Latin') return n.includes('bossa') || n.includes('samba') || n.includes('latin') || n.includes('ska') || n.includes('reggae') || n.includes('onedrop') || n.includes('steppers') || n.includes('waltz');
      if (currentCategory === 'Metro') return n.includes('metro') || n.includes('guide');
      return true;
    }});

    for (const pat of list) {{
      const card = document.createElement('div');
      card.className = `pattern-card ${{pat.index === currentPattern.index ? 'active' : ''}}`;
      card.onclick = () => selectPattern(pat, isPlaying);

      const uiLabel = pat.uiNum !== null && pat.uiNum !== undefined ? `UI #${{String(pat.uiNum).padStart(2, '0')}}` : `ROM #${{pat.index}}`;
      const conf = pat.decode_confidence || 'ok';

      card.innerHTML = `
        <div class="pc-header">
          <div class="pc-name">${{pat.name}}</div>
          <div class="pc-idx">${{uiLabel}}</div>
        </div>
        <div class="pc-sub">${{pat.beats_per_bar}}/${{pat.beat_unit}} METER • ${{pat.loop_bars || 2}} BARS</div>
        <div class="pc-badge ${{conf}}">${{conf.toUpperCase()}}</div>
      `;
      container.appendChild(card);
    }}
  }}

  // -------------------------------------------------------------
  // PATTERN SEQUENCER / EDITOR
  // -------------------------------------------------------------
  function syncPatternToEditor(pat) {{
    document.getElementById('editPatternName').value = pat.name;
    editorBeatsPerBar = pat.beats_per_bar || 4;
    editorBeatUnit = pat.beat_unit || 4;
    editorBars = pat.loop_bars || 2;
    document.getElementById('editBeatsPerBar').value = String(editorBeatsPerBar);
    document.getElementById('editBarsCount').value = String(editorBars);

    const stepsPerBeat = editorResolutionTicks === 3 ? 4 : (editorResolutionTicks === 4 ? 3 : 2);
    editorStepsPerBar = editorBeatsPerBar * stepsPerBeat;
    const totalSteps = editorStepsPerBar * editorBars;

    // Build tracks from assigned voices
    editorTracks = [];
    for (let slot = 1; slot < 9; slot++) {{
      const sample = pat.voices[slot];
      if (sample) {{
        editorTracks.push({{
          slot: slot,
          sample: sample,
          steps: new Array(totalSteps).fill(null)
        }});
      }}
    }}

    // Populate steps from ROM events
    if (pat.steps && pat.steps.length > 0) {{
      for (const ev of pat.steps) {{
        if (ev.voice_id === 9) continue; // click
        const track = editorTracks.find(t => t.sample === ev.sample || t.slot === ev.slot);
        if (track) {{
          const stepIndex = Math.floor(ev.tick / editorResolutionTicks);
          if (stepIndex >= 0 && stepIndex < totalSteps) {{
            track.steps[stepIndex] = {{ level: ev.level }};
          }}
        }}
      }}
    }}

    renderEditorGrid();
  }}

  function renderEditorGrid() {{
    const table = document.getElementById('editorGridTable');
    table.innerHTML = '';

    const stepsPerBeat = editorResolutionTicks === 3 ? 4 : (editorResolutionTicks === 4 ? 3 : 2);
    const totalSteps = editorBeatsPerBar * stepsPerBeat * editorBars;
    table.style.setProperty('--total-steps', totalSteps);

    // Header step numbers row
    const headerRow = document.createElement('div');
    headerRow.className = 'grid-header-row';
    headerRow.innerHTML = `<div style="font-family:'Share Tech Mono'; font-size:11px; color:var(--text-muted); padding:4px;">VOICE TRACK</div>`;

    for (let s = 0; s < totalSteps; s++) {{
      const isBeatStart = (s % stepsPerBeat) === 0;
      const beatNum = Math.floor(s / stepsPerBeat) + 1;
      const sub = (s % stepsPerBeat) + 1;
      const stepEl = document.createElement('div');
      stepEl.className = `grid-step-num ${{isBeatStart ? 'beat-head' : ''}}`;
      stepEl.textContent = isBeatStart ? `${{beatNum}}` : `.${{sub}}`;
      headerRow.appendChild(stepEl);
    }}
    table.appendChild(headerRow);

    // Track rows
    editorTracks.forEach((track, trackIdx) => {{
      const row = document.createElement('div');
      row.className = 'grid-track-row';

      const labelCell = document.createElement('div');
      labelCell.className = 'track-label-cell';
      
      let optionsHtml = '';
      for (const k of Object.keys(SAMPLES)) {{
        const b = SAMPLES[k].name;
        optionsHtml += `<option value="${{k}}" ${{track.sample === k ? 'selected' : ''}}>${{b}}</option>`;
      }}

      labelCell.innerHTML = `
        <select class="track-select" onchange="changeTrackSample(${{trackIdx}}, this.value)">${{optionsHtml}}</select>
        <span style="font-size: 11px; color: var(--accent-orange); cursor: pointer;" onclick="removeEditorTrack(${{trackIdx}})" title="Delete track">✕</span>
      `;
      row.appendChild(labelCell);

      // Step cells
      for (let s = 0; s < totalSteps; s++) {{
        const isBeatStart = (s % stepsPerBeat) === 0;
        const cell = document.createElement('div');
        cell.className = `step-cell ${{isBeatStart ? 'beat-bar-start' : ''}}`;
        cell.dataset.track = trackIdx;
        cell.dataset.step = s;

        const ev = track.steps[s];
        if (ev) {{
          cell.classList.add('active');
          const pct = Math.max(10, Math.min(100, (ev.level / 15.0) * 100));
          cell.innerHTML = `<div class="step-level-bar" style="height: ${{pct}}%;"></div>`;
        }}

        cell.onmousedown = (e) => handleStepClick(e, trackIdx, s);
        row.appendChild(cell);
      }}

      table.appendChild(row);
    }});
  }}

  function handleStepClick(e, trackIdx, stepIdx) {{
    ensureAudio();
    const track = editorTracks[trackIdx];
    if (track.steps[stepIdx]) {{
      // Turn off
      track.steps[stepIdx] = null;
    }} else {{
      // Turn on
      const level = 12; // default high level
      track.steps[stepIdx] = {{ level: level }};
      triggerVoice(track.sample, level, 0, track.slot);

      // If Auto-Ambience is on and dry sample has an Ambience companion
      if (autoAmbience) {{
        const ambKey = track.sample.replace(".raw", "Amb.raw");
        if (SAMPLES[ambKey]) {{
          let ambTrack = editorTracks.find(t => t.sample === ambKey);
          if (!ambTrack) {{
            ambTrack = {{ slot: -1, sample: ambKey, steps: new Array(track.steps.length).fill(null) }};
            editorTracks.push(ambTrack);
          }}
          ambTrack.steps[stepIdx] = {{ level: Math.max(4, level - 3) }};
          triggerVoice(ambKey, Math.max(4, level - 3), 0);
        }}
      }}
    }}
    syncEditorToCurrentPattern();
    renderEditorGrid();
  }}

  function changeTrackSample(trackIdx, newSample) {{
    editorTracks[trackIdx].sample = newSample;
    syncEditorToCurrentPattern();
  }}
  window.changeTrackSample = changeTrackSample;

  function removeEditorTrack(trackIdx) {{
    editorTracks.splice(trackIdx, 1);
    syncEditorToCurrentPattern();
    renderEditorGrid();
  }}
  window.removeEditorTrack = removeEditorTrack;

  function addEditorTrack() {{
    const stepsPerBeat = editorResolutionTicks === 3 ? 4 : (editorResolutionTicks === 4 ? 3 : 2);
    const totalSteps = editorBeatsPerBar * stepsPerBeat * editorBars;
    const sampleKeys = Object.keys(SAMPLES);
    const unusedKey = sampleKeys.find(k => !editorTracks.some(t => t.sample === k)) || "Kik1.raw";

    editorTracks.push({{
      slot: -1,
      sample: unusedKey,
      steps: new Array(totalSteps).fill(null)
    }});
    syncEditorToCurrentPattern();
    renderEditorGrid();
  }}
  window.addEditorTrack = addEditorTrack;

  function clearEditorGrid() {{
    for (const t of editorTracks) {{
      t.steps.fill(null);
    }}
    syncEditorToCurrentPattern();
    renderEditorGrid();
    showToast("Grid cleared");
  }}
  window.clearEditorGrid = clearEditorGrid;

  function toggleAutoAmbience() {{
    autoAmbience = !autoAmbience;
    const btn = document.getElementById('btnAutoAmb');
    btn.textContent = `AUTO-AMBIENCE: ${{autoAmbience ? 'ON' : 'OFF'}}`;
    btn.classList.toggle('active', autoAmbience);
  }}
  window.toggleAutoAmbience = toggleAutoAmbience;

  function humanizeEditorGroove() {{
    for (const t of editorTracks) {{
      for (let s = 0; s < t.steps.length; s++) {{
        if (t.steps[s]) {{
          // subtle velocity randomize +/- 2
          const delta = Math.floor(Math.random() * 5) - 2;
          t.steps[s].level = Math.max(4, Math.min(15, t.steps[s].level + delta));
        }}
      }}
    }}
    syncEditorToCurrentPattern();
    renderEditorGrid();
    showToast("Groove humanized");
  }}
  window.humanizeEditorGroove = humanizeEditorGroove;

  function shiftEditorSteps(amount) {{
    for (const t of editorTracks) {{
      const len = t.steps.length;
      const copy = [...t.steps];
      for (let i = 0; i < len; i++) {{
        const target = (i + amount + len) % len;
        t.steps[target] = copy[i];
      }}
    }}
    syncEditorToCurrentPattern();
    renderEditorGrid();
  }}
  window.shiftEditorSteps = shiftEditorSteps;

  function updateEditorMeter() {{
    editorBeatsPerBar = parseInt(document.getElementById('editBeatsPerBar').value);
    syncPatternToEditor(currentPattern);
  }}
  window.updateEditorMeter = updateEditorMeter;

  function updateEditorBars() {{
    editorBars = parseInt(document.getElementById('editBarsCount').value);
    syncPatternToEditor(currentPattern);
  }}
  window.updateEditorBars = updateEditorBars;

  function updateEditorResolution() {{
    editorResolutionTicks = parseInt(document.getElementById('editStepRes').value);
    syncPatternToEditor(currentPattern);
  }}
  window.updateEditorResolution = updateEditorResolution;

  function syncEditorToCurrentPattern() {{
    const patName = document.getElementById('editPatternName').value || "CustomPattern";
    const loopTicks = editorBeatsPerBar * TICKS_PER_BEAT * editorBars;

    const newSteps = [];
    editorTracks.forEach((t, tIdx) => {{
      for (let s = 0; s < t.steps.length; s++) {{
        const ev = t.steps[s];
        if (ev) {{
          newSteps.push({{
            tick: s * editorResolutionTicks,
            delta: 0,
            voice_id: t.slot > 0 ? t.slot : 1,
            level: ev.level,
            slot: t.slot > 0 ? t.slot : 1,
            sample: t.sample,
            mapped: true
          }});
        }}
      }}
    }});

    newSteps.sort((a, b) => a.tick - b.tick);

    currentPattern = {{
      ...currentPattern,
      name: patName,
      beats_per_bar: editorBeatsPerBar,
      beat_unit: editorBeatUnit,
      loop_bars: editorBars,
      loop_length_ticks: loopTicks,
      steps: newSteps
    }};

    document.getElementById('lcdPatternName').textContent = patName;
    document.getElementById('lcdTotalBars').textContent = String(editorBars).padStart(2, '0');
  }}

  function loadPatternToEditor() {{
    switchTab('tabEditor');
  }}
  window.loadPatternToEditor = loadPatternToEditor;

  // -------------------------------------------------------------
  // PADS & SOUNDBOARD
  // -------------------------------------------------------------
  function populatePads(pat) {{
    const grid = document.getElementById('drumPadsGrid');
    grid.innerHTML = '';

    const padKeys = ['1', '2', '3', '4', '5', '6', '7', '8', '9'];

    for (let i = 0; i < 9; i++) {{
      const slot = i;
      const sample = pat.voices[slot] || "Click.raw";
      const base = sample.replace(".raw", "");

      const pad = document.createElement('div');
      pad.className = 'drum-pad';
      pad.dataset.slot = slot;
      pad.dataset.sample = sample;

      pad.innerHTML = `
        <div class="pad-top-row">
          <span>PAD ${{i + 1}}</span>
          <span class="pad-key">${{padKeys[i]}}</span>
        </div>
        <div class="pad-voice-title">${{base}}</div>
        <div class="pad-sample-sub">SLOT ${{slot}}</div>
      `;

      pad.onmousedown = (e) => {{
        ensureAudio();
        const rect = pad.getBoundingClientRect();
        const relY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
        const vel = Math.round(5 + (10 * relY)); // higher Y = louder
        hitPad(sample, vel, slot);
      }};

      grid.appendChild(pad);
    }}

    // Populate 24 Soundboard
    populateSoundboard();
  }}

  function populateSoundboard() {{
    const sb = document.getElementById('soundboardGrid');
    if (sb.children.length > 0) return; // already populated

    const sampleKeys = Object.keys(SAMPLES);
    for (const k of sampleKeys) {{
      const btn = document.createElement('button');
      btn.className = 'sb-sample-btn';
      btn.textContent = SAMPLES[k].name;
      btn.onclick = () => {{
        ensureAudio();
        triggerVoice(k, 14, 0);
        btn.classList.add('hit');
        setTimeout(() => btn.classList.remove('hit'), 100);
      }};
      sb.appendChild(btn);
    }}
  }}

  function hitPad(sampleName, vel0_15, slot) {{
    triggerVoice(sampleName, vel0_15, 0, slot);

    // If recording live
    if (isRecording && isPlaying) {{
      const secPerTick = 60.0 / bpm / TICKS_PER_BEAT;
      const loopTicks = currentPattern.loop_length_ticks;
      const curTick = (nextScheduleTick) % loopTicks;
      const stepIdx = Math.round(curTick / editorResolutionTicks);

      let track = editorTracks.find(t => t.sample === sampleName);
      if (!track) {{
        track = {{ slot: slot, sample: sampleName, steps: new Array(editorBeatsPerBar * 4 * editorBars).fill(null) }};
        editorTracks.push(track);
      }}

      if (stepIdx < track.steps.length) {{
        track.steps[stepIdx] = {{ level: vel0_15 }};
        syncEditorToCurrentPattern();
        renderEditorGrid();
      }}
    }}
  }}

  // Keyboard shortcut listener for pads
  window.addEventListener('keydown', (e) => {{
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') return;
    const keyMap = {{
      '1': 0, '2': 1, '3': 2,
      '4': 3, '5': 4, '6': 5,
      '7': 6, '8': 7, '9': 8,
      'q': 0, 'w': 1, 'e': 2,
      'a': 3, 's': 4, 'd': 5,
      'z': 6, 'x': 7, 'c': 8
    }};
    const k = e.key.toLowerCase();
    if (k in keyMap) {{
      const slot = keyMap[k];
      const sample = currentPattern.voices[slot] || "Click.raw";
      ensureAudio();
      hitPad(sample, 14, slot);
      const pad = document.querySelector(`.drum-pad[data-slot="${{slot}}"]`);
      if (pad) {{
        pad.classList.add('hit-active');
        setTimeout(() => pad.classList.remove('hit-active'), 80);
      }}
    }}
  }});

  // -------------------------------------------------------------
  // KNOB INTERACTION LOGIC
  // -------------------------------------------------------------
  function setupKnob(id, onValChange) {{
    const knob = document.getElementById(id);
    const min = parseFloat(knob.dataset.min);
    const max = parseFloat(knob.dataset.max);
    let val = parseFloat(knob.dataset.val);

    function updateRotation(v) {{
      const norm = (v - min) / (max - min);
      const deg = -140 + (norm * 280);
      knob.querySelector('.knob-pointer').style.transform = `rotate(${{deg}}deg)`;
    }}
    updateRotation(val);

    let startY = 0;
    let startVal = val;

    knob.addEventListener('pointerdown', (e) => {{
      startY = e.clientY;
      startVal = val;
      knob.setPointerCapture(e.pointerId);

      function onPointerMove(ev) {{
        const dy = startY - ev.clientY;
        const range = max - min;
        const deltaVal = (dy / 150) * range;
        val = Math.max(min, Math.min(max, Math.round(startVal + deltaVal)));
        knob.dataset.val = val;
        updateRotation(val);
        onValChange(val);
      }}

      function onPointerUp(ev) {{
        knob.releasePointerCapture(ev.pointerId);
        knob.removeEventListener('pointermove', onPointerMove);
        knob.removeEventListener('pointerup', onPointerUp);
      }}

      knob.addEventListener('pointermove', onPointerMove);
      knob.addEventListener('pointerup', onPointerUp);
    }});
  }}

  setupKnob('knobTempo', (v) => {{
    bpm = v;
    document.getElementById('valTempo').textContent = v;
    document.getElementById('lcdBpmDisplay').textContent = `${{v}}.0`;
  }});

  setupKnob('knobVol', (v) => {{
    masterVol = v;
    document.getElementById('valVol').textContent = v;
    document.getElementById('lcdVolDisplay').textContent = `${{v}}%`;
    if (masterGainNode) {{
      masterGainNode.gain.setValueAtTime(v / 100.0, audioCtx.currentTime);
    }}
  }});

  setupKnob('knobAmb', (v) => {{
    ambienceLevel = v;
    document.getElementById('valAmb').textContent = `${{v}}%`;
  }});

  setupKnob('knobSwing', (v) => {{
    swingPct = v;
    document.getElementById('valSwing').textContent = `${{v}}%`;
  }});

  function handleTapTempo() {{
    const now = performance.now();
    tapTimes.push(now);
    if (tapTimes.length > 4) tapTimes.shift();

    if (tapTimes.length >= 2) {{
      const diffs = [];
      for (let i = 1; i < tapTimes.length; i++) {{
        diffs.push(tapTimes[i] - tapTimes[i - 1]);
      }}
      const avgMs = diffs.reduce((a, b) => a + b) / diffs.length;
      const calcBpm = Math.max(40, Math.min(250, Math.round(60000 / avgMs)));
      bpm = calcBpm;
      document.getElementById('knobTempo').dataset.val = bpm;
      document.getElementById('valTempo').textContent = bpm;
      document.getElementById('lcdBpmDisplay').textContent = `${{bpm}}.0`;
      const norm = (bpm - 40) / (250 - 40);
      document.querySelector('#knobTempo .knob-pointer').style.transform = `rotate(${{-140 + norm * 280}}deg)`;
    }}
  }}
  window.handleTapTempo = handleTapTempo;

  // -------------------------------------------------------------
  // TAB NAVIGATION
  // -------------------------------------------------------------
  function switchTab(tabId) {{
    document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');

    const btnIndex = tabId === 'tabLibrary' ? 0 : (tabId === 'tabEditor' ? 1 : 2);
    document.querySelectorAll('.tab-btn')[btnIndex].classList.add('active');
  }}
  window.switchTab = switchTab;

  // -------------------------------------------------------------
  // OSCILLOSCOPE DRAWING
  // -------------------------------------------------------------
  function startOscilloscope() {{
    const canvas = document.getElementById('oscilloscope');
    const ctx = canvas.getContext('2d');
    const dataArray = new Uint8Array(analyserNode.frequencyBinCount);

    function draw() {{
      requestAnimationFrame(draw);
      analyserNode.getByteTimeDomainData(dataArray);

      ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.lineWidth = 2;
      const themeColor = getComputedStyle(document.body).getPropertyValue('--lcd-text').trim() || '#ffaa00';
      ctx.strokeStyle = themeColor;
      ctx.beginPath();

      const sliceWidth = canvas.width / dataArray.length;
      let x = 0;

      for (let i = 0; i < dataArray.length; i++) {{
        const v = dataArray[i] / 128.0;
        const y = (v * canvas.height) / 2;

        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);

        x += sliceWidth;
      }}

      ctx.lineTo(canvas.width, canvas.height / 2);
      ctx.stroke();
    }}
    draw();
  }}

  // -------------------------------------------------------------
  // IMPORT & EXPORT LOGIC
  // -------------------------------------------------------------
  function exportCliPatternJson() {{
    // drum_machine.py format
    const stepsPerBar = editorBeatsPerBar * (editorResolutionTicks === 3 ? 4 : 2);
    const voicesObj = {{}};

    for (const t of editorTracks) {{
      const hitEvents = [];
      for (let s = 0; s < t.steps.length; s++) {{
        if (t.steps[s]) {{
          // level 0-15 converted to velocity 0-127
          const vel127 = Math.round((t.steps[s].level / 15.0) * 127);
          hitEvents.push([s, vel127]);
        }}
      }}
      if (hitEvents.length > 0) {{
        voicesObj[t.sample] = hitEvents;
      }}
    }}

    const payload = {{
      name: currentPattern.name,
      bpm: bpm,
      bars: editorBars,
      steps_per_bar: stepsPerBar,
      voices: voicesObj
    }};

    downloadJson(payload, `${{currentPattern.name.toLowerCase()}}_pattern.json`);
    showToast("Downloaded CLI pattern JSON");
  }}
  window.exportCliPatternJson = exportCliPatternJson;

  function exportRomStepsJson() {{
    const payload = {{
      name: currentPattern.name,
      beats_per_bar: currentPattern.beats_per_bar,
      beat_unit: currentPattern.beat_unit,
      loop_bars: currentPattern.loop_bars,
      loop_length_ticks: currentPattern.loop_length_ticks,
      ticks_per_beat: TICKS_PER_BEAT,
      steps: currentPattern.steps
    }};
    downloadJson(payload, `${{currentPattern.name.toLowerCase()}}_rom_steps.json`);
    showToast("Downloaded ROM steps JSON");
  }}
  window.exportRomStepsJson = exportRomStepsJson;

  function downloadJson(obj, filename) {{
    const blob = new Blob([JSON.stringify(obj, null, 2)], {{ type: 'application/json' }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }}

  function handleImportFile(e) {{
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {{
      try {{
        const json = JSON.parse(evt.target.result);
        if (json.voices) {{
          // drum_machine.py format
          const newName = json.name || file.name.replace(".json", "");
          editorBars = json.bars || 2;
          bpm = json.bpm || 120;
          document.getElementById('knobTempo').dataset.val = bpm;
          document.getElementById('valTempo').textContent = bpm;
          document.getElementById('lcdBpmDisplay').textContent = `${{bpm}}.0`;

          const stepsPerBar = json.steps_per_bar || 16;
          editorTracks = [];
          for (const rawName of Object.keys(json.voices)) {{
            const pairs = json.voices[rawName];
            const trackSteps = new Array(stepsPerBar * editorBars).fill(null);
            for (const [step, vel] of pairs) {{
              if (step < trackSteps.length) {{
                trackSteps[step] = {{ level: Math.round((vel / 127.0) * 15) }};
              }}
            }}
            editorTracks.push({{
              slot: -1,
              sample: rawName.endsWith(".raw") ? rawName : rawName + ".raw",
              steps: trackSteps
            }});
          }}
          syncEditorToCurrentPattern();
          renderEditorGrid();
          switchTab('tabEditor');
          showToast(`Imported ${{newName}} successfully!`);
        }} else if (json.steps) {{
          // ROM steps format
          selectPattern(json, false);
          switchTab('tabEditor');
          showToast(`Imported ${{json.name}} successfully!`);
        }}
      }} catch (err) {{
        alert("Failed to parse pattern JSON: " + err);
      }}
    }};
    reader.readAsText(file);
  }}
  window.handleImportFile = handleImportFile;

  async function renderOfflineWav() {{
    ensureAudio();
    showToast("Rendering 44.1 kHz 16-bit WAV...");

    const bpb = currentPattern.beats_per_bar || 4;
    const loopTicks = currentPattern.loop_length_ticks || (bpb * TICKS_PER_BEAT * currentBars);
    const secPerTick = 60.0 / bpm / TICKS_PER_BEAT;
    const totalDurationSec = loopTicks * secPerTick + 1.0; // tail
    const sampleRate = 44100;
    const totalFrames = Math.ceil(totalDurationSec * sampleRate);

    const offlineCtx = new OfflineAudioContext(1, totalFrames, sampleRate);

    if (currentPattern.steps && currentPattern.steps.length > 0) {{
      for (const ev of currentPattern.steps) {{
        if (ev.voice_id === 9 && !includeClick) continue;
        const buf = sampleBuffers[ev.sample];
        if (!buf) continue;

        const src = offlineCtx.createBufferSource();
        src.buffer = buf;

        const gainNode = offlineCtx.createGain();
        let gainVal = Math.max(0.01, Math.min(1.0, ev.level / 15.0));
        if (ev.sample.includes("Amb")) gainVal *= (ambienceLevel / 100.0);
        gainNode.gain.value = gainVal * (masterVol / 100.0);

        src.connect(gainNode);
        gainNode.connect(offlineCtx.destination);

        const startTime = ev.tick * secPerTick;
        src.start(startTime);
      }}
    }}

    const renderedBuffer = await offlineCtx.startRendering();
    const wavBlob = audioBufferToWav(renderedBuffer);
    const url = URL.createObjectURL(wavBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${{currentPattern.name.toLowerCase()}}_${{bpm}}bpm.wav`;
    a.click();
    URL.revokeObjectURL(url);
    showToast(`Rendered & downloaded ${{currentPattern.name}}.wav`);
  }}
  window.renderOfflineWav = renderOfflineWav;

  function audioBufferToWav(buf) {{
    const numChannels = 1;
    const sampleRate = buf.sampleRate;
    const format = 1; // PCM
    const bitDepth = 16;

    const channelData = buf.getChannelData(0);
    const dataLen = channelData.length * 2;
    const buffer = new ArrayBuffer(44 + dataLen);
    const view = new DataView(buffer);

    function writeString(offset, str) {{
      for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
    }}

    writeString(0, 'RIFF');
    view.setUint32(4, 36 + dataLen, true);
    writeString(8, 'WAVE');
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, format, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * numChannels * 2, true);
    view.setUint16(32, numChannels * 2, true);
    view.setUint16(34, bitDepth, true);
    writeString(36, 'data');
    view.setUint32(40, dataLen, true);

    let offset = 44;
    for (let i = 0; i < channelData.length; i++) {{
      const s = Math.max(-1, Math.min(1, channelData[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
      offset += 2;
    }}

    return new Blob([buffer], {{ type: 'audio/wav' }});
  }}

  function copyCliCommand() {{
    const cmd = `python tools/drums/drum_machine.py render "${{currentPattern.name}}" --bpm ${{bpm}} --bars ${{currentBars}} -o build/drums/render/${{currentPattern.name.toLowerCase()}}.wav`;
    navigator.clipboard.writeText(cmd).then(() => {{
      showToast("Copied CLI command to clipboard!");
    }}).catch(() => {{
      prompt("Copy command:", cmd);
    }});
  }}
  window.copyCliCommand = copyCliCommand;

  // Initial startup selection
  selectPattern(PATTERNS[7]); // Rock1
  renderPatternCards();

}})();
</script>
</body>
</html>
"""

    with open(OUT_HTML_TOOLS, "w", encoding="utf-8") as f:
        f.write(html_content)

    with open(OUT_HTML_ROOT, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"Wrote {OUT_HTML_TOOLS} ({OUT_HTML_TOOLS.stat().st_size / 1024:.1f} KB)")
    print(f"Wrote {OUT_HTML_ROOT} ({OUT_HTML_ROOT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    build_studio_html()
