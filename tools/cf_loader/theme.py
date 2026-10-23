"""Black and gold theme and visual asset helpers for Comet Flower Installer.

Owner requirements:
- Near-black background (#0d0d0d / #161616 panels)
- Gold accents (#d4af37 for headings, selected rows, primary buttons; #8a7020 for borders/disabled)
- Off-white text (#eeeeee)
- Tint 1-bit logo white pixels gold with Pillow and scale with NEAREST.
"""

from pathlib import Path
import tkinter as tk
from tkinter import ttk
from typing import Optional, Tuple
from PIL import Image, ImageTk

# Color palette
BG_DARK = "#0d0d0d"       # main window background
PANEL_BG = "#161616"      # cards, left rail, panels
SURFACE_BG = "#1f1f1f"    # inputs, secondary panels
BORDER_COLOR = "#8a7020"  # borders and disabled accents
BORDER_MUTED = "#2c2c2c"  # subtle borders
ACCENT_GOLD = "#d4af37"   # primary gold brand accent
GOLD_HOVER = "#f0c848"    # active / hover gold
TEXT_WHITE = "#eeeeee"    # primary text
TEXT_MUTED = "#8a8a8a"    # secondary / placeholder text
TEXT_DARK = "#0d0d0d"     # dark text on gold button
SELECTION_BG = "#8a7020"  # selected rows
SELECTION_FG = "#ffffff"  # selected row text
DANGER_RED = "#d9383a"    # warnings / delete
SUCCESS_GREEN = "#38d976" # success indicators


def tint_and_scale_image(
    source_path: Path,
    gold_rgb: Tuple[int, int, int] = (212, 175, 55),
    bg_rgb: Tuple[int, int, int] = (22, 22, 22),
    scale: int = 2,
    transparent_bg: bool = False,
) -> Image.Image:
    """Tint white pixels of a 1-bit / grayscale image to gold and scale with NEAREST."""
    if not source_path.exists():
        # Fallback 1x1 image
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    src = Image.open(source_path).convert("L")
    w, h = src.size
    out_img = Image.new("RGBA", (w, h))

    src_pix = src.load()
    out_pix = out_img.load()

    for y in range(h):
        for x in range(w):
            val = src_pix[x, y]
            if val > 80:
                ratio = val / 255.0
                r = int(gold_rgb[0] * ratio)
                g = int(gold_rgb[1] * ratio)
                b = int(gold_rgb[2] * ratio)
                out_pix[x, y] = (r, g, b, 255)
            else:
                if transparent_bg:
                    out_pix[x, y] = (0, 0, 0, 0)
                else:
                    out_pix[x, y] = (bg_rgb[0], bg_rgb[1], bg_rgb[2], 255)

    if scale > 1:
        out_img = out_img.resize((w * scale, h * scale), Image.Resampling.NEAREST)

    return out_img


def setup_theme(style: ttk.Style, root: tk.Tk):
    """Configure ttk Style with the Black and Gold theme."""
    try:
        style.theme_use("clam")
    except Exception:
        pass

    root.configure(background=BG_DARK)

    # General configuration
    style.configure(
        ".",
        background=BG_DARK,
        foreground=TEXT_WHITE,
        font=("Segoe UI", 9),
        troughcolor=PANEL_BG,
        focuscolor=ACCENT_GOLD,
        bordercolor=BORDER_COLOR,
    )

    # Frames
    style.configure("TFrame", background=BG_DARK)
    style.configure("Panel.TFrame", background=PANEL_BG)
    style.configure("Surface.TFrame", background=SURFACE_BG)

    # Labels
    style.configure("TLabel", background=BG_DARK, foreground=TEXT_WHITE)
    style.configure("Panel.TLabel", background=PANEL_BG, foreground=TEXT_WHITE)
    style.configure(
        "GoldHeader.TLabel",
        background=PANEL_BG,
        foreground=ACCENT_GOLD,
        font=("Segoe UI", 12, "bold"),
    )
    style.configure(
        "PageTitle.TLabel",
        background=BG_DARK,
        foreground=ACCENT_GOLD,
        font=("Segoe UI", 14, "bold"),
    )
    style.configure(
        "SubTitle.TLabel",
        background=BG_DARK,
        foreground=TEXT_MUTED,
        font=("Segoe UI", 9),
    )
    style.configure(
        "Muted.TLabel",
        background=PANEL_BG,
        foreground=TEXT_MUTED,
        font=("Segoe UI", 8),
    )

    # Buttons
    style.configure(
        "TButton",
        background=PANEL_BG,
        foreground=TEXT_WHITE,
        bordercolor=BORDER_COLOR,
        darkcolor=BORDER_COLOR,
        lightcolor=BORDER_COLOR,
        relief="groove",
        padding=(8, 4),
    )
    style.map(
        "TButton",
        background=[("pressed", SURFACE_BG), ("active", "#252525"), ("disabled", "#141414")],
        foreground=[("disabled", "#555555"), ("active", ACCENT_GOLD)],
        bordercolor=[("active", ACCENT_GOLD), ("disabled", "#333333")],
    )

    # Accent / Primary Gold Button
    style.configure(
        "Accent.TButton",
        font=("Segoe UI", 9, "bold"),
        foreground=TEXT_DARK,
        background=ACCENT_GOLD,
        relief="raised",
        padding=(10, 5),
    )
    style.map(
        "Accent.TButton",
        background=[("pressed", BORDER_COLOR), ("active", GOLD_HOVER), ("disabled", "#554518")],
        foreground=[("disabled", "#888888"), ("active", "#000000")],
    )

    # Navigation Rail Buttons
    style.configure(
        "Nav.TButton",
        font=("Segoe UI", 10),
        foreground=TEXT_WHITE,
        background=PANEL_BG,
        relief="flat",
        anchor="w",
        padding=(14, 10),
    )
    style.map(
        "Nav.TButton",
        background=[("active", SURFACE_BG), ("disabled", PANEL_BG)],
        foreground=[("active", ACCENT_GOLD), ("disabled", TEXT_MUTED)],
    )

    style.configure(
        "NavActive.TButton",
        font=("Segoe UI", 10, "bold"),
        foreground=TEXT_DARK,
        background=ACCENT_GOLD,
        relief="flat",
        anchor="w",
        padding=(14, 10),
    )
    style.map(
        "NavActive.TButton",
        background=[("active", GOLD_HOVER), ("pressed", BORDER_COLOR)],
        foreground=[("active", TEXT_DARK)],
    )

    # Entry fields
    style.configure(
        "TEntry",
        fieldbackground=SURFACE_BG,
        foreground=TEXT_WHITE,
        insertcolor=ACCENT_GOLD,
        bordercolor=BORDER_COLOR,
        padding=4,
    )

    # Combobox
    style.configure(
        "TCombobox",
        fieldbackground=SURFACE_BG,
        background=PANEL_BG,
        foreground=TEXT_WHITE,
        darkcolor=BORDER_COLOR,
        lightcolor=BORDER_COLOR,
        arrowcolor=ACCENT_GOLD,
        bordercolor=BORDER_COLOR,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", SURFACE_BG)],
        selectbackground=[("readonly", SELECTION_BG)],
        selectforeground=[("readonly", SELECTION_FG)],
    )

    # Checkbutton
    style.configure(
        "TCheckbutton",
        background=BG_DARK,
        foreground=TEXT_WHITE,
        indicatorcolor=SURFACE_BG,
    )
    style.map(
        "TCheckbutton",
        indicatorcolor=[("selected", ACCENT_GOLD), ("pressed", GOLD_HOVER)],
        background=[("active", BG_DARK)],
        foreground=[("active", ACCENT_GOLD)],
    )
    style.configure("Panel.TCheckbutton", background=PANEL_BG, foreground=TEXT_WHITE)
    style.map(
        "Panel.TCheckbutton",
        indicatorcolor=[("selected", ACCENT_GOLD), ("pressed", GOLD_HOVER)],
        background=[("active", PANEL_BG)],
        foreground=[("active", ACCENT_GOLD)],
    )

    # Treeview (Tables)
    style.configure(
        "Treeview",
        background=PANEL_BG,
        foreground=TEXT_WHITE,
        fieldbackground=PANEL_BG,
        bordercolor=BORDER_MUTED,
        rowheight=24,
    )
    style.map(
        "Treeview",
        background=[("selected", SELECTION_BG)],
        foreground=[("selected", SELECTION_FG)],
    )
    style.configure(
        "Treeview.Heading",
        background=SURFACE_BG,
        foreground=ACCENT_GOLD,
        font=("Segoe UI", 9, "bold"),
        relief="groove",
        bordercolor=BORDER_MUTED,
    )
    style.map(
        "Treeview.Heading",
        background=[("active", "#2a2a2a")],
        foreground=[("active", GOLD_HOVER)],
    )

    # Labelframes
    style.configure(
        "TLabelframe",
        background=PANEL_BG,
        bordercolor=BORDER_COLOR,
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=PANEL_BG,
        foreground=ACCENT_GOLD,
        font=("Segoe UI", 9, "bold"),
    )

    # Progressbar
    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=SURFACE_BG,
        background=ACCENT_GOLD,
        bordercolor=BORDER_COLOR,
    )
