"""Package Comet Flower Updater Suite and copy to Google Drive."""

from pathlib import Path
import shutil
import zipfile

REPO_ROOT = Path(__file__).resolve().parent.parent
FLASHER_DIR = REPO_ROOT / "build" / "flasher"
PACKAGE_DIR = REPO_ROOT / "build" / "Comet_Flower_Suite"
ZIP_PATH = REPO_ROOT / "build" / "Comet_Flower_Updater_Suite.zip"
GDRIVE_DIR = Path("G:/My Drive/Comet Flower")
GDRIVE_ZIP = Path("G:/My Drive/Comet_Flower_Updater_Suite.zip")

# 1. Clean staging directory
if PACKAGE_DIR.exists():
    shutil.rmtree(PACKAGE_DIR)
PACKAGE_DIR.mkdir(parents=True, exist_ok=True)

# 2. Copy Executables
full_exe = FLASHER_DIR / "Comet Flower Updater.exe"
usb_exe = FLASHER_DIR / "Comet Flower Updater - Stereo USB Audio.exe"
shutil.copyfile(full_exe, PACKAGE_DIR / full_exe.name)
shutil.copyfile(usb_exe, PACKAGE_DIR / usb_exe.name)

# 3. Copy Mobile & Desktop Music Studio
html_src = REPO_ROOT / "tools" / "web_music_studio" / "index.html"
shutil.copyfile(html_src, PACKAGE_DIR / "Comet Flower Music Studio.html")
shutil.copyfile(REPO_ROOT / "tools" / "cf_music_maker.py", PACKAGE_DIR / "Comet Flower Music Studio (Desktop).py")

# 4. Write README.txt
readme_text = """=============================================================================
                    COMET FLOWER LABS 1911 // 2026
                      STANDALONE UPDATER SUITE
=============================================================================

This suite contains standalone, independent tools for the Zoom G1 / G1X Four.
Zero Zoom proprietary updater software is required.

-----------------------------------------------------------------------------
1. EXECUTABLES INCLUDED
-----------------------------------------------------------------------------
* "Comet Flower Updater.exe"
  - Full Firmware Edition (v0.34.9)
  - 5 Real Effect Slots with Unlocked Cycle Allocation (Gate 230 -> 340)
  - '74 Violet Big Muff (12nF C10 audited circuit), Hiwatt DR103 Custom 100,
    Comet Flower Preamp, Comet Flower Delay with True Spillover Tail,
    Comet Flower Rotary, Comet Flower 808
  - Custom bootloader splash, bloom startup animation, and icon set
  - Pure windowed GUI (no terminal popup)

* "Comet Flower Updater - Stereo USB Audio.exe"
  - Non-destructive Stereo USB Audio Tap
  - Updates flash 0x033000 only
  - Preserves all stock Zoom effects, DIY effects, user patches, and presets
  - Activates line-level USB audio streaming over standard USB connection

-----------------------------------------------------------------------------
2. MUSIC & CHIPTUNE STUDIOS
-----------------------------------------------------------------------------
* "Comet Flower Music Studio.html"
  - Interactive retro chiptune tracker styled after Sony ACID Pro Keygen.
  - Can be opened directly in ANY mobile or desktop browser (Safari, Chrome, etc.).
  - 100% client-side: uses the Web Audio API to play sound directly out of your
    phone or PC speakers.
  - Allows customizing chord progressions (Bm - A - G - Em, etc.), tempo,
    lead waveforms, and bass grooves.
  - Tap "COPY TRACK DATA FOR AGENT" to export your composition.

* "Comet Flower Music Studio (Desktop).py"
  - Native Python / Tkinter GUI studio connecting to Windows MIDI GS Wavetable.
  - One-click "Save to Updater" button.

-----------------------------------------------------------------------------
3. HARDWARE CONNECTION & FLASHING
-----------------------------------------------------------------------------
1. Connect Zoom G1X Four to PC via micro-USB cable.
2. Hold down both foot pedals while connecting USB / powering on to enter
   Update Mode (pedal screen displays "UPDATE").
3. Launch either "Comet Flower Updater.exe" or "Comet Flower Updater - Stereo USB Audio.exe".
4. The tool will auto-detect your pedal and flash safely over native MIDI SysEx.
=============================================================================
"""

(PACKAGE_DIR / "README.txt").write_text(readme_text, encoding="utf-8")

# 5. Create ZIP Archive
print(f"Creating ZIP archive at {ZIP_PATH}...")
with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
    for file in PACKAGE_DIR.rglob("*"):
        if file.is_file():
            arcname = file.relative_to(PACKAGE_DIR)
            zf.write(file, arcname)

print(f"ZIP archive created: {ZIP_PATH.stat().st_size:,} bytes")

# 6. Deploy to Google Drive
print(f"Deploying to Google Drive ({GDRIVE_DIR})...")
GDRIVE_DIR.mkdir(parents=True, exist_ok=True)

# Copy uncompressed files for easy access on phone/drive
for item in PACKAGE_DIR.iterdir():
    dest = GDRIVE_DIR / item.name
    if item.is_file():
        shutil.copyfile(item, dest)
        print(f"  Copied {item.name} -> {dest}")

# Also copy the zip file directly to root of Google Drive and inside the folder
shutil.copyfile(ZIP_PATH, GDRIVE_ZIP)
print(f"  Copied ZIP -> {GDRIVE_ZIP}")
shutil.copyfile(ZIP_PATH, GDRIVE_DIR / ZIP_PATH.name)
print(f"  Copied ZIP -> {GDRIVE_DIR / ZIP_PATH.name}")

print("\n[+] SUCCESS! All files packaged and loaded onto Google Drive.")
