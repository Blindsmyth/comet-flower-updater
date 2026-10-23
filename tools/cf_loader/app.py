"""Comet Flower Installer (tools/cf_loader/app.py).

Desktop app for Zoom G1X Four:
- Backups management
- Stock & Comet Flower effects selection
- Patch decoding and factory presets composition
- Firmware & installer packaging (make_fs_restore_updater.py)
- Profiles persistence ("set a default so when you update you can set")

Standard library Tkinter/ttk and Pillow only.
Non-blocking UI: all subprocess operations run in worker threads.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Set

from PIL import Image, ImageTk

from tools.cf_loader import core
from tools.cf_loader.theme import (
    ACCENT_GOLD,
    BG_DARK,
    BORDER_COLOR,
    BORDER_MUTED,
    DANGER_RED,
    GOLD_HOVER,
    PANEL_BG,
    SELECTION_BG,
    SELECTION_FG,
    SURFACE_BG,
    TEXT_DARK,
    TEXT_MUTED,
    TEXT_WHITE,
    setup_theme,
    tint_and_scale_image,
)

REPO_ROOT = core.REPO_ROOT
LOGO_PATH = REPO_ROOT / "assets" / "logo_comet_flower.png"
SPLASH_PATH = REPO_ROOT / "assets" / "splash_comet_flower.png"


class CFLoaderApp(tk.Tk):
    """Main application window for Comet Flower Installer."""

    def __init__(self):
        super().__init__()
        self.title("Comet Flower Installer")
        self.minsize(980, 680)
        self.geometry("1060x740")

        # Application state
        self.config_data = core.load_config()
        self.active_backup: Optional[core.BackupInfo] = None
        self.backups_list: List[core.BackupInfo] = []
        self.effects_catalog: List[core.UnifiedEffect] = []
        self.displayed_effects: List[core.UnifiedEffect] = []
        self.patches_list: List[core.PatchRecord] = []
        self.profiles: Dict[str, core.Profile] = {}
        self.active_profile: core.Profile = core.get_default_fallback_profile()

        # Worker & threading state
        self.active_worker: Optional[threading.Thread] = None
        self.worker_cancel_requested = False
        self.busy = False
        self.log_queue: queue.Queue = queue.Queue()

        # UI variables
        self.nav_selection = tk.StringVar(value="Effects")
        self.effects_filter_text = tk.StringVar(value="")
        self.effects_source_filter = tk.StringVar(value="all")
        self.official_updater_var = tk.StringVar(value=self.config_data.get("official_updater", ""))
        self.firmware_bin_var = tk.StringVar(value="")
        self.presets_bin_var = tk.StringVar(value="")
        self.version_var = tk.StringVar(value="")
        self.auto_backup_var = tk.BooleanVar(value=True)
        self.splash_screen_var = tk.BooleanVar(value=True)
        self.selected_profile_name = tk.StringVar(value="")

        # Setup styling and UI
        self.style = ttk.Style(self)
        setup_theme(self.style, self)
        self._load_window_branding()
        self._build_ui()
        self._poll_log_queue()

        # Initial data loading
        self._initialize_data()

    # -----------------------------------------------------------------------
    # Window Branding & Icons
    # -----------------------------------------------------------------------

    def _load_window_branding(self):
        """Tint white logo pixels gold and configure icon and header assets."""
        try:
            # Create tinted icon
            self.icon_image_pil = tint_and_scale_image(
                LOGO_PATH, gold_rgb=(212, 175, 55), scale=1, transparent_bg=True
            )
            self.tk_icon = ImageTk.PhotoImage(self.icon_image_pil)
            self.iconphoto(True, self.tk_icon)

            # Create header banner logo scaled 2x
            self.header_logo_pil = tint_and_scale_image(
                LOGO_PATH, gold_rgb=(212, 175, 55), scale=2, bg_rgb=(22, 22, 22)
            )
            self.tk_header_logo = ImageTk.PhotoImage(self.header_logo_pil)
        except Exception as e:
            self.tk_header_logo = None

    # -----------------------------------------------------------------------
    # UI Layout Construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        # 1. Top Header Bar
        header = ttk.Frame(self, style="Panel.TFrame", padding=(12, 10))
        header.pack(fill=tk.X, side=tk.TOP)

        if self.tk_header_logo:
            logo_lbl = ttk.Label(header, image=self.tk_header_logo, style="Panel.TLabel")
            logo_lbl.pack(side=tk.LEFT, padx=(4, 12))

        title_box = ttk.Frame(header, style="Panel.TFrame")
        title_box.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Label(
            title_box,
            text="Comet Flower Installer",
            style="GoldHeader.TLabel",
            font=("Segoe UI", 13, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            title_box,
            text="Zoom G1X Four Backup, Effects & Custom Firmware Packager",
            style="Muted.TLabel",
        ).pack(anchor="w")

        # Quick action on top right: "Update with Default"
        btn_box = ttk.Frame(header, style="Panel.TFrame")
        btn_box.pack(side=tk.RIGHT, padx=6)
        self.btn_quick_update = ttk.Button(
            btn_box,
            text="★ Update with Default",
            style="Accent.TButton",
            command=self._on_quick_update_with_default,
        )
        self.btn_quick_update.pack(side=tk.RIGHT)

        # 2. Main Center Body (Left Nav Rail + Right Pages Deck)
        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        # Left Navigation Rail
        self.nav_frame = ttk.Frame(body, style="Panel.TFrame", width=190, padding=(8, 12))
        self.nav_frame.pack(side=tk.LEFT, fill=tk.Y)
        self.nav_frame.pack_propagate(False)

        ttk.Label(
            self.nav_frame,
            text="NAVIGATION",
            style="Panel.TLabel",
            foreground=ACCENT_GOLD,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", padx=10, pady=(4, 10))

        self.nav_buttons: Dict[str, ttk.Button] = {}
        pages = [
            ("Backups", "Backups"),
            ("Effects", "Effects"),
            ("Patches", "Patches"),
            ("Firmware & Build", "Firmware & Build"),
            ("Profiles", "Profiles"),
        ]
        for key, label in pages:
            btn = ttk.Button(
                self.nav_frame,
                text=label,
                style="Nav.TButton",
                command=lambda k=key: self._switch_page(k),
            )
            btn.pack(fill=tk.X, pady=3)
            self.nav_buttons[key] = btn

        # Status footer inside nav rail
        ttk.Separator(self.nav_frame).pack(fill=tk.X, pady=(20, 10))
        self.lbl_nav_status = ttk.Label(
            self.nav_frame,
            text="Source Backup:\nNone (Factory)",
            style="Muted.TLabel",
            wraplength=170,
        )
        self.lbl_nav_status.pack(anchor="w", padx=8, side=tk.BOTTOM, pady=6)

        # Right Pages Container
        self.page_container = ttk.Frame(body, padding=(12, 10))
        self.page_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.pages: Dict[str, ttk.Frame] = {}
        self.pages["Backups"] = self._build_page_backups(self.page_container)
        self.pages["Effects"] = self._build_page_effects(self.page_container)
        self.pages["Patches"] = self._build_page_patches(self.page_container)
        self.pages["Firmware & Build"] = self._build_page_firmware_build(self.page_container)
        self.pages["Profiles"] = self._build_page_profiles(self.page_container)

        # 3. Bottom Streaming Log Pane
        self._build_bottom_log_pane()

        # Show initial page
        self._switch_page("Effects")

    def _switch_page(self, page_name: str):
        """Switch active page on the right view deck."""
        self.nav_selection.set(page_name)
        for name, frame in self.pages.items():
            if name == page_name:
                frame.pack(fill=tk.BOTH, expand=True)
            else:
                frame.pack_forget()

        # Update nav button styles
        for name, btn in self.nav_buttons.items():
            if name == page_name:
                btn.configure(style="NavActive.TButton")
            else:
                btn.configure(style="Nav.TButton")

    # -----------------------------------------------------------------------
    # Bottom Log Pane
    # -----------------------------------------------------------------------

    def _build_bottom_log_pane(self):
        log_panel = ttk.Frame(self, style="Panel.TFrame", padding=(10, 6))
        log_panel.pack(fill=tk.X, side=tk.BOTTOM)

        log_hdr = ttk.Frame(log_panel, style="Panel.TFrame")
        log_hdr.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(
            log_hdr,
            text="Console & Build Output",
            style="Panel.TLabel",
            foreground=ACCENT_GOLD,
            font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.LEFT)

        self.lbl_worker_busy = ttk.Label(
            log_hdr, text="", style="Panel.TLabel", foreground=GOLD_HOVER, font=("Segoe UI", 9, "italic")
        )
        self.lbl_worker_busy.pack(side=tk.LEFT, padx=12)

        self.btn_copy_log = ttk.Button(log_hdr, text="Copy Log", command=self._on_copy_log)
        self.btn_copy_log.pack(side=tk.RIGHT, padx=4)
        self.btn_clear_log = ttk.Button(log_hdr, text="Clear Log", command=self._on_clear_log)
        self.btn_clear_log.pack(side=tk.RIGHT)

        self.log_text = tk.Text(
            log_panel,
            height=6,
            background="#0a0a0a",
            foreground="#dddddd",
            insertbackground=ACCENT_GOLD,
            selectbackground=SELECTION_BG,
            selectforeground=SELECTION_FG,
            font=("Consolas", 8),
            relief="solid",
            borderwidth=1,
            state="disabled",
            wrap="word",
        )
        self.log_text.pack(fill=tk.X, side=tk.TOP)

    # -----------------------------------------------------------------------
    # Page 1: Backups
    # -----------------------------------------------------------------------

    def _build_page_backups(self, parent: ttk.Frame) -> ttk.Frame:
        p = ttk.Frame(parent)

        # Header
        hdr = ttk.Frame(p)
        hdr.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(hdr, text="Pedal Backups", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            hdr,
            text="Read-only backups of all effects and 50 patches from your Zoom G1X Four over USB.",
            style="SubTitle.TLabel",
        ).pack(anchor="w")

        # Action bar
        act_bar = ttk.Frame(p, style="Panel.TFrame", padding=(10, 8))
        act_bar.pack(fill=tk.X, pady=(0, 10))

        self.btn_backup_now = ttk.Button(
            act_bar,
            text="▶ Back Up Pedal Now",
            style="Accent.TButton",
            command=self._on_backup_now,
        )
        self.btn_backup_now.pack(side=tk.LEFT, padx=(0, 10))

        self.chk_auto_backup = ttk.Checkbutton(
            act_bar,
            text="Automatically back up pedal before building installer",
            variable=self.auto_backup_var,
            style="Panel.TCheckbutton",
        )
        self.chk_auto_backup.pack(side=tk.LEFT, padx=10)

        self.btn_refresh_backups = ttk.Button(
            act_bar, text="Refresh", command=self._refresh_backups_list
        )
        self.btn_refresh_backups.pack(side=tk.RIGHT)

        # Table of existing backups
        cols = ("date", "effects", "patches", "size", "path")
        self.tree_backups = ttk.Treeview(p, columns=cols, show="headings", height=10)
        self.tree_backups.heading("date", text="Date / Timestamp")
        self.tree_backups.heading("effects", text="Effects")
        self.tree_backups.heading("patches", text="Patches")
        self.tree_backups.heading("size", text="Size")
        self.tree_backups.heading("path", text="Directory")

        self.tree_backups.column("date", width=160, anchor="w")
        self.tree_backups.column("effects", width=80, anchor="center")
        self.tree_backups.column("patches", width=80, anchor="center")
        self.tree_backups.column("size", width=100, anchor="center")
        self.tree_backups.column("path", width=380, anchor="w")

        self.tree_backups.pack(fill=tk.BOTH, expand=True)
        self.tree_backups.bind("<<TreeviewSelect>>", self._on_backup_selected)

        # Action bar for selected backup
        sel_bar = ttk.Frame(p, style="Panel.TFrame", padding=(10, 8))
        sel_bar.pack(fill=tk.X, pady=(10, 0))

        self.btn_use_backup = ttk.Button(
            sel_bar,
            text="✓ Use As Active Source",
            style="Accent.TButton",
            command=self._on_use_backup_as_source,
            state="disabled",
        )
        self.btn_use_backup.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_open_backup_folder = ttk.Button(
            sel_bar,
            text="Open Folder",
            command=self._on_open_backup_folder,
            state="disabled",
        )
        self.btn_open_backup_folder.pack(side=tk.LEFT, padx=5)

        self.btn_delete_backup = ttk.Button(
            sel_bar,
            text="Delete Backup",
            command=self._on_delete_backup,
            state="disabled",
        )
        self.btn_delete_backup.pack(side=tk.RIGHT)

        return p

    # -----------------------------------------------------------------------
    # Page 2: Effects
    # -----------------------------------------------------------------------

    def _build_page_effects(self, parent: ttk.Frame) -> ttk.Frame:
        p = ttk.Frame(parent)

        # Header
        hdr = ttk.Frame(p)
        hdr.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(hdr, text="Effects Library & Selection", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            hdr,
            text="Select stock Zoom and Comet Flower effects to install on the pedal. Checked effects will be packaged into the installer.",
            style="SubTitle.TLabel",
        ).pack(anchor="w")

        # Filter & Toggle Bar
        filt_bar = ttk.Frame(p, style="Panel.TFrame", padding=(10, 8))
        filt_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(filt_bar, text="Filter:", style="Panel.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        ent_filter = ttk.Entry(filt_bar, textvariable=self.effects_filter_text, width=20)
        ent_filter.pack(side=tk.LEFT, padx=(0, 14))
        self.effects_filter_text.trace_add("write", lambda *_: self._filter_effects_display())

        # Toggle: All / Zoom / CF
        ttk.Label(filt_bar, text="Source:", style="Panel.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        for val, lbl in (("all", "All"), ("Zoom", "Zoom Only"), ("CF", "CF Only")):
            r = ttk.Radiobutton(
                filt_bar,
                text=lbl,
                value=val,
                variable=self.effects_source_filter,
                style="Panel.TCheckbutton",
                command=self._filter_effects_display,
            )
            r.pack(side=tk.LEFT, padx=4)

        # Quick select buttons
        self.btn_sel_all = ttk.Button(filt_bar, text="Select All", command=self._on_select_all_effects)
        self.btn_sel_all.pack(side=tk.RIGHT, padx=4)
        self.btn_sel_none = ttk.Button(filt_bar, text="Select None", command=self._on_select_none_effects)
        self.btn_sel_none.pack(side=tk.RIGHT, padx=4)

        # Effects Treeview
        cols = ("checked", "name", "file", "group", "source", "dspload", "on_pedal")
        self.tree_effects = ttk.Treeview(p, columns=cols, show="headings", selectmode="browse", height=12)
        self.tree_effects.heading("checked", text="Install?")
        self.tree_effects.heading("name", text="Effect Name")
        self.tree_effects.heading("file", text="Filename")
        self.tree_effects.heading("group", text="Group")
        self.tree_effects.heading("source", text="Source")
        self.tree_effects.heading("dspload", text="DSP Load")
        self.tree_effects.heading("on_pedal", text="On Pedal")

        self.tree_effects.column("checked", width=65, anchor="center")
        self.tree_effects.column("name", width=180, anchor="w")
        self.tree_effects.column("file", width=140, anchor="w")
        self.tree_effects.column("group", width=70, anchor="center")
        self.tree_effects.column("source", width=70, anchor="center")
        self.tree_effects.column("dspload", width=80, anchor="center")
        self.tree_effects.column("on_pedal", width=80, anchor="center")

        self.tree_effects.pack(fill=tk.BOTH, expand=True)
        self.tree_effects.bind("<space>", self._on_toggle_effect_checked)
        self.tree_effects.bind("<ButtonRelease-1>", self._on_click_effect_row)

        # Running Total / Space Meter Card
        meter_card = ttk.Frame(p, style="Panel.TFrame", padding=(10, 8))
        meter_card.pack(fill=tk.X, pady=(8, 0))

        self.lbl_space_summary = ttk.Label(
            meter_card,
            text="Filesystem Space: Calculating...",
            style="Panel.TLabel",
            foreground=ACCENT_GOLD,
            font=("Segoe UI", 9, "bold"),
        )
        self.lbl_space_summary.pack(anchor="w", pady=(0, 4))

        self.prog_space = ttk.Progressbar(
            meter_card,
            orient="horizontal",
            mode="determinate",
            maximum=core.FS_TOTAL_BYTES,
        )
        self.prog_space.pack(fill=tk.X)

        return p

    # -----------------------------------------------------------------------
    # Page 3: Patches
    # -----------------------------------------------------------------------

    def _build_page_patches(self, parent: ttk.Frame) -> ttk.Frame:
        p = ttk.Frame(parent)

        # Header
        hdr = ttk.Frame(p)
        hdr.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(hdr, text="Patch Management & Factory Presets", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            hdr,
            text="Inspect all 50 patches from your active backup. Composed presets are written to flash region 0x28000 and appear only after factory reset.",
            style="SubTitle.TLabel",
        ).pack(anchor="w")

        # Top notice box
        notice = ttk.Frame(p, style="Panel.TFrame", padding=(8, 6))
        notice.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            notice,
            text="ℹ Note: The installer builds factory presets. Live pedal patches (0x0C0000) are never touched by update mode.",
            style="Panel.TLabel",
            foreground=ACCENT_GOLD,
            font=("Segoe UI", 9),
        ).pack(anchor="w")

        # Patches Treeview
        cols = ("idx", "name", "slots")
        self.tree_patches = ttk.Treeview(p, columns=cols, show="headings", height=11)
        self.tree_patches.heading("idx", text="#")
        self.tree_patches.heading("name", text="Patch Name")
        self.tree_patches.heading("slots", text="Effect Slots (1 - 5)")

        self.tree_patches.column("idx", width=45, anchor="center")
        self.tree_patches.column("name", width=140, anchor="w")
        self.tree_patches.column("slots", width=550, anchor="w")

        self.tree_patches.pack(fill=tk.BOTH, expand=True)
        self.tree_patches.bind("<<TreeviewSelect>>", self._on_patch_selected)

        # Patch Actions Toolbar
        patch_bar = ttk.Frame(p, style="Panel.TFrame", padding=(10, 8))
        patch_bar.pack(fill=tk.X, pady=(8, 0))

        self.btn_backup_patch = ttk.Button(
            patch_bar, text="Back Up .ZPTC", command=self._on_backup_single_patch, state="disabled"
        )
        self.btn_backup_patch.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_load_patch = ttk.Button(
            patch_bar, text="Load .ZPTC", command=self._on_load_single_patch, state="disabled"
        )
        self.btn_load_patch.pack(side=tk.LEFT, padx=6)

        self.btn_remove_patch = ttk.Button(
            patch_bar, text="Clear / Blank Patch", command=self._on_blank_single_patch, state="disabled"
        )
        self.btn_remove_patch.pack(side=tk.LEFT, padx=6)

        # Untested MIDI Action button
        self.btn_write_midi_patch = ttk.Button(
            patch_bar,
            text="Write to Pedal (MIDI) [UNTESTED]",
            command=self._on_write_live_patch_midi,
            state="disabled",
        )
        self.btn_write_midi_patch.pack(side=tk.RIGHT, padx=6)

        return p

    # -----------------------------------------------------------------------
    # Page 4: Firmware & Build
    # -----------------------------------------------------------------------

    def _build_page_firmware_build(self, parent: ttk.Frame) -> ttk.Frame:
        p = ttk.Frame(parent)

        # Header
        hdr = ttk.Frame(p)
        hdr.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(hdr, text="Firmware & Installer Build", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            hdr,
            text="Build the official update-mode executable (.exe) containing selected firmware, effects image, and presets.",
            style="SubTitle.TLabel",
        ).pack(anchor="w")

        # Configuration Card
        cfg_card = ttk.Labelframe(p, text="Build Configuration", padding=12)
        cfg_card.pack(fill=tk.X, pady=(0, 8))

        # Row 1: Official Updater
        r1 = ttk.Frame(cfg_card, style="Panel.TFrame")
        r1.pack(fill=tk.X, pady=4)
        ttk.Label(r1, text="Official Updater .exe:", style="Panel.TLabel", width=20).pack(side=tk.LEFT)
        self.ent_updater = ttk.Entry(r1, textvariable=self.official_updater_var)
        self.ent_updater.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r1, text="Browse...", command=self._browse_official_updater).pack(side=tk.RIGHT)

        # Row 2: Firmware Binary
        r2 = ttk.Frame(cfg_card, style="Panel.TFrame")
        r2.pack(fill=tk.X, pady=4)
        ttk.Label(r2, text="Firmware .bin:", style="Panel.TLabel", width=20).pack(side=tk.LEFT)
        self.combo_fw = ttk.Combobox(r2, textvariable=self.firmware_bin_var)
        self.combo_fw.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r2, text="Browse...", command=self._browse_firmware_bin).pack(side=tk.RIGHT)

        # Row 3: Presets Binary
        r3 = ttk.Frame(cfg_card, style="Panel.TFrame")
        r3.pack(fill=tk.X, pady=4)
        ttk.Label(r3, text="Presets Region (.bin):", style="Panel.TLabel", width=20).pack(side=tk.LEFT)
        self.ent_presets = ttk.Entry(r3, textvariable=self.presets_bin_var)
        self.ent_presets.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6)
        ttk.Button(r3, text="Browse...", command=self._browse_presets_bin).pack(side=tk.RIGHT)

        # Row 4: Version & Splash
        r4 = ttk.Frame(cfg_card, style="Panel.TFrame")
        r4.pack(fill=tk.X, pady=4)
        ttk.Label(r4, text="Version (0.X.Y):", style="Panel.TLabel", width=20).pack(side=tk.LEFT)
        self.ent_version = ttk.Entry(r4, textvariable=self.version_var, width=15)
        self.ent_version.pack(side=tk.LEFT, padx=6)

        self.chk_splash = ttk.Checkbutton(
            r4,
            text="Generate Start-up Screen with Version (tools/make_splash.py)",
            variable=self.splash_screen_var,
            style="Panel.TCheckbutton",
        )
        self.chk_splash.pack(side=tk.LEFT, padx=12)

        # Build Action & Safety Banner
        action_card = ttk.Frame(p, style="Panel.TFrame", padding=10)
        action_card.pack(fill=tk.X, pady=6)

        self.btn_build_installer = ttk.Button(
            action_card,
            text="🔨 Build Comet Flower Installer (.exe)",
            style="Accent.TButton",
            command=self._on_build_installer,
        )
        self.btn_build_installer.pack(side=tk.LEFT, padx=(0, 12))

        self.btn_cancel_build = ttk.Button(
            action_card, text="Cancel Build", command=self._on_cancel_build, state="disabled"
        )
        self.btn_cancel_build.pack(side=tk.LEFT)

        # Safety Label
        safety_lbl = ttk.Label(
            action_card,
            text="SAFETY GUARANTEE: Never flashes directly. The app only creates the .exe installer.",
            style="Panel.TLabel",
            foreground=ACCENT_GOLD,
            font=("Segoe UI", 9, "bold"),
        )
        safety_lbl.pack(side=tk.RIGHT)

        # Build Output / Result Card
        self.res_card = ttk.Labelframe(p, text="Build Output & Stages", padding=10)
        self.res_card.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

        self.lbl_build_sha = ttk.Label(
            self.res_card,
            text="SHA-256: (No build completed in this session)",
            style="Panel.TLabel",
            foreground=TEXT_WHITE,
            font=("Consolas", 9),
        )
        self.lbl_build_sha.pack(anchor="w", pady=(0, 4))

        self.tree_stages = ttk.Treeview(self.res_card, columns=("op", "addr", "target"), show="headings", height=5)
        self.tree_stages.heading("op", text="Operation")
        self.tree_stages.heading("addr", text="Flash Address")
        self.tree_stages.heading("target", text="Target / Size")
        self.tree_stages.column("op", width=120, anchor="center")
        self.tree_stages.column("addr", width=160, anchor="center")
        self.tree_stages.column("target", width=250, anchor="w")
        self.tree_stages.pack(fill=tk.BOTH, expand=True)

        return p

    # -----------------------------------------------------------------------
    # Page 5: Profiles
    # -----------------------------------------------------------------------

    def _build_page_profiles(self, parent: ttk.Frame) -> ttk.Frame:
        p = ttk.Frame(parent)

        # Header
        hdr = ttk.Frame(p)
        hdr.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(hdr, text="Configuration Profiles", style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(
            hdr,
            text="Save and load named installer profiles. Set a default profile so you can update with your chosen effects in one click.",
            style="SubTitle.TLabel",
        ).pack(anchor="w")

        # Profile selection & action bar
        bar = ttk.Frame(p, style="Panel.TFrame", padding=(10, 10))
        bar.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(bar, text="Selected Profile:", style="Panel.TLabel").pack(side=tk.LEFT, padx=(0, 6))
        self.combo_profiles = ttk.Combobox(bar, textvariable=self.selected_profile_name, state="readonly", width=25)
        self.combo_profiles.pack(side=tk.LEFT, padx=(0, 10))
        self.combo_profiles.bind("<<ComboboxSelected>>", self._on_profile_combo_selected)

        self.btn_load_profile = ttk.Button(bar, text="Load Profile", command=self._on_load_selected_profile)
        self.btn_load_profile.pack(side=tk.LEFT, padx=4)

        self.btn_save_profile = ttk.Button(bar, text="Save Current Settings", command=self._on_save_current_profile)
        self.btn_save_profile.pack(side=tk.LEFT, padx=4)

        self.btn_set_default_profile = ttk.Button(bar, text="★ Set as Default", command=self._on_set_default_profile)
        self.btn_set_default_profile.pack(side=tk.LEFT, padx=4)

        self.btn_delete_profile = ttk.Button(bar, text="Delete Profile", command=self._on_delete_profile)
        self.btn_delete_profile.pack(side=tk.RIGHT, padx=4)

        # Profile details card
        self.card_prof_details = ttk.Labelframe(p, text="Profile Summary", padding=12)
        self.card_prof_details.pack(fill=tk.BOTH, expand=True)

        self.lbl_prof_name = ttk.Label(self.card_prof_details, text="Name: Default", style="Panel.TLabel", font=("Segoe UI", 10, "bold"))
        self.lbl_prof_name.pack(anchor="w", pady=2)

        self.lbl_prof_default = ttk.Label(self.card_prof_details, text="Status: (Default Profile)", style="Panel.TLabel", foreground=ACCENT_GOLD)
        self.lbl_prof_default.pack(anchor="w", pady=2)

        self.lbl_prof_effects_count = ttk.Label(self.card_prof_details, text="Effects Selected: 0", style="Panel.TLabel")
        self.lbl_prof_effects_count.pack(anchor="w", pady=2)

        self.lbl_prof_fw = ttk.Label(self.card_prof_details, text="Firmware: Stock", style="Panel.TLabel")
        self.lbl_prof_fw.pack(anchor="w", pady=2)

        self.lbl_prof_backup = ttk.Label(self.card_prof_details, text="Auto-backup: Enabled", style="Panel.TLabel")
        self.lbl_prof_backup.pack(anchor="w", pady=2)

        return p

    # -----------------------------------------------------------------------
    # Data Initialization
    # -----------------------------------------------------------------------

    def _initialize_data(self):
        """Load initial state across all tabs."""
        # 1. Backups
        self._refresh_backups_list()

        # 2. Effects Catalog
        self.rescan_library()

        # 3. Patches
        self._load_patches_from_active_backup()

        # 4. Firmware & Build setup
        self._init_build_config()

        # 5. Profiles
        self._refresh_profiles_list()

    def _refresh_backups_list(self):
        """Scan existing backups and populate tree."""
        self.backups_list = core.scan_backups()
        for item in self.tree_backups.get_children():
            self.tree_backups.delete(item)

        for b in self.backups_list:
            self.tree_backups.insert(
                "",
                "end",
                iid=str(b.path),
                values=(b.date_str, b.effects_count, b.patches_count, b.display_size, str(b.path)),
            )

        # Preselect newest backup if available
        if self.backups_list and not self.active_backup:
            self.active_backup = self.backups_list[0]
            self.lbl_nav_status.configure(text=f"Source Backup:\n{self.active_backup.name}")

    def rescan_library(self):
        """Assemble unified stock and CF effects catalog."""
        backup_path = self.active_backup.path if self.active_backup else None
        self.effects_catalog = core.assemble_unified_catalog(backup_dir=backup_path)
        self._filter_effects_display()

    def _filter_effects_display(self):
        """Filter effects table based on search text and source toggle."""
        query = self.effects_filter_text.get().strip().lower()
        src_filter = self.effects_source_filter.get()

        for item in self.tree_effects.get_children():
            self.tree_effects.delete(item)

        self.displayed_effects = []
        for e in self.effects_catalog:
            if src_filter != "all" and e.source != src_filter:
                continue
            if query and query not in e.name.lower() and query not in e.filename.lower() and query not in e.group.lower():
                continue
            self.displayed_effects.append(e)

            check_sym = "[X]" if e.is_checked else "[  ]"
            pedal_sym = "Yes" if e.on_pedal else "No"
            self.tree_effects.insert(
                "",
                "end",
                iid=e.filename,
                values=(check_sym, e.name, e.filename, e.group, e.source, f"{e.dspload:.1f}", pedal_sym),
            )

        self._update_space_meter()

    def _update_space_meter(self):
        """Update filesystem capacity gauge."""
        checked = [e for e in self.effects_catalog if e.is_checked]
        tot_bytes, tot_blocks, free_blocks, fits, msg = core.calculate_filesystem_usage(checked)
        self.lbl_space_summary.configure(text=msg)
        if not fits:
            self.lbl_space_summary.configure(foreground=DANGER_RED)
        else:
            self.lbl_space_summary.configure(foreground=ACCENT_GOLD)

        self.prog_space.configure(value=tot_bytes)

    def _load_patches_from_active_backup(self):
        """Load 50 patches from active backup."""
        bpath = self.active_backup.path if self.active_backup else None
        self.patches_list = core.scan_backup_patches(backup_dir=bpath)
        for item in self.tree_patches.get_children():
            self.tree_patches.delete(item)

        for p in self.patches_list:
            self.tree_patches.insert(
                "",
                "end",
                iid=str(p.index),
                values=(f"{p.index:02d}", p.name, p.slots_summary),
            )

    def _init_build_config(self):
        """Initialize firmware and build tab options."""
        # Default official updater
        if not self.official_updater_var.get():
            upd = core.find_default_official_updater()
            if upd:
                self.official_updater_var.set(str(upd))

        # Scan candidate firmware bins in build/cf_header
        fw_bins = []
        default_fw = core.find_default_firmware_bin()
        if (REPO_ROOT / "build" / "cf_header").is_dir():
            for f in (REPO_ROOT / "build" / "cf_header").glob("*.bin"):
                if f.stat().st_size > 100000:
                    fw_bins.append(str(f))
        self.combo_fw["values"] = fw_bins
        if default_fw:
            self.firmware_bin_var.set(str(default_fw))
        elif fw_bins:
            self.firmware_bin_var.set(fw_bins[0])

        # Default presets
        cf_preset = REPO_ROOT / "build" / "fw" / "cfupd_res85.bin"
        if cf_preset.exists():
            self.presets_bin_var.set(str(cf_preset))

        # Auto-detect version
        ver = core.parse_next_version()
        self.version_var.set(ver)

    def _refresh_profiles_list(self):
        """Load profiles and select default."""
        self.profiles = core.load_profiles()
        names = list(self.profiles.keys())
        self.combo_profiles["values"] = names

        default_p = core.get_default_profile()
        self.active_profile = default_p
        self.selected_profile_name.set(default_p.name)
        self._update_profile_display(default_p)

    def _update_profile_display(self, prof: core.Profile):
        """Update profile details card."""
        self.lbl_prof_name.configure(text=f"Name: {prof.name}")
        self.lbl_prof_default.configure(
            text="★ Default Profile (Preselected on start)" if prof.is_default else "Custom Profile"
        )
        self.lbl_prof_effects_count.configure(
            text=f"Effects Configured: {len(prof.checked_effects) if prof.checked_effects else 'All active'}"
        )
        fw_name = Path(prof.firmware_path).name if prof.firmware_path else "Default"
        self.lbl_prof_fw.configure(text=f"Firmware: {fw_name}")
        self.lbl_prof_backup.configure(
            text=f"Auto-backup: {'Enabled' if prof.backup_before_build else 'Disabled'}"
        )

    # -----------------------------------------------------------------------
    # Event Handlers & User Actions
    # -----------------------------------------------------------------------

    def _on_backup_selected(self, event=None):
        sel = self.tree_backups.selection()
        has_sel = bool(sel)
        st = "normal" if has_sel else "disabled"
        self.btn_use_backup.configure(state=st)
        self.btn_open_backup_folder.configure(state=st)
        self.btn_delete_backup.configure(state=st)

    def _on_use_backup_as_source(self):
        sel = self.tree_backups.selection()
        if not sel:
            return
        path_str = sel[0]
        for b in self.backups_list:
            if str(b.path) == path_str:
                self.active_backup = b
                self.lbl_nav_status.configure(text=f"Source Backup:\n{b.name}")
                self.log(f"> Active source backup set to: {b.path}")
                self.rescan_library()
                self._load_patches_from_active_backup()
                break

    def _on_open_backup_folder(self):
        sel = self.tree_backups.selection()
        if sel:
            p = Path(sel[0])
            if p.exists():
                if sys.platform == "win32":
                    os.startfile(p)
                else:
                    subprocess.run(["xdg-open", str(p)])

    def _on_delete_backup(self):
        sel = self.tree_backups.selection()
        if not sel:
            return
        p = Path(sel[0])
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to permanently delete the backup '{p.name}'?",
            parent=self,
        )
        if confirm:
            core.delete_backup(p)
            if self.active_backup and self.active_backup.path == p:
                self.active_backup = None
                self.lbl_nav_status.configure(text="Source Backup:\nNone (Factory)")
            self._refresh_backups_list()
            self.rescan_library()
            self._load_patches_from_active_backup()

    def _on_backup_now(self):
        """Run complete backup in worker thread."""
        if self.busy:
            return
        self._set_busy(True, "Backing up pedal...")
        dest_dir = core.create_backup_destination()
        py = core.get_python_exe()
        cmds = core.build_backup_commands(dest_dir, python_exe=py)

        def worker():
            try:
                self.log(f"> Starting complete pedal backup to: {dest_dir}")
                for cmd in cmds:
                    self.log(f"EXEC: {' '.join(cmd)}")
                    res = core.run_tool(
                        cmd,
                        on_output=self.log,
                        is_cancelled=lambda: self.worker_cancel_requested,
                    )
                    self.log(f"Tool exited with code {res.exit_code}")
                self.log("\nBackup completed.")
            except Exception as e:
                self.log(f"\nERROR during backup: {e}")
            finally:
                self.after(0, self._on_backup_worker_finished)

        self.worker_cancel_requested = False
        self.active_worker = threading.Thread(target=worker, daemon=True)
        self.active_worker.start()

    def _on_backup_worker_finished(self):
        self._set_busy(False)
        self._refresh_backups_list()
        self.rescan_library()
        self._load_patches_from_active_backup()

    # Effects Page Actions
    def _on_toggle_effect_checked(self, event=None):
        sel = self.tree_effects.selection()
        if not sel:
            return
        fn = sel[0]
        for e in self.effects_catalog:
            if e.filename == fn:
                e.is_checked = not e.is_checked
                break
        self._filter_effects_display()

    def _on_click_effect_row(self, event=None):
        # Clicked on install column or double click
        sel = self.tree_effects.selection()
        if not sel:
            return
        col = self.tree_effects.identify_column(event.x) if event else "#1"
        if col == "#1":
            self._on_toggle_effect_checked()

    def _on_select_all_effects(self):
        for e in self.displayed_effects:
            e.is_checked = True
        self._filter_effects_display()

    def _on_select_none_effects(self):
        for e in self.displayed_effects:
            e.is_checked = False
        self._filter_effects_display()

    # Patches Page Actions
    def _on_patch_selected(self, event=None):
        sel = self.tree_patches.selection()
        has_sel = bool(sel)
        st = "normal" if has_sel else "disabled"
        self.btn_backup_patch.configure(state=st)
        self.btn_load_patch.configure(state=st)
        self.btn_remove_patch.configure(state=st)
        self.btn_write_midi_patch.configure(state=st)

    def _on_backup_single_patch(self):
        sel = self.tree_patches.selection()
        if not sel:
            return
        idx = int(sel[0])
        patch = next((p for p in self.patches_list if p.index == idx), None)
        if not patch:
            return
        fn = filedialog.asksaveasfilename(
            title=f"Save Patch {idx:02d}",
            initialfile=f"PATCH_{idx:03d}.ZPTC",
            defaultextension=".ZPTC",
            filetypes=[("Zoom Patch", "*.ZPTC"), ("All Files", "*.*")],
            parent=self,
        )
        if fn:
            Path(fn).write_bytes(patch.raw_data)
            self.log(f"> Exported Patch {idx:02d} to {fn}")

    def _on_load_single_patch(self):
        sel = self.tree_patches.selection()
        if not sel:
            return
        idx = int(sel[0])
        fn = filedialog.askopenfilename(
            title=f"Load .ZPTC into Patch {idx:02d}",
            filetypes=[("Zoom Patch", "*.ZPTC"), ("All Files", "*.*")],
            parent=self,
        )
        if fn:
            data = Path(fn).read_bytes()
            new_patch = core.decode_patch_bytes(data, index=idx, file_path=Path(fn))
            for i, p in enumerate(self.patches_list):
                if p.index == idx:
                    self.patches_list[i] = new_patch
                    break
            self.tree_patches.item(str(idx), values=(f"{idx:02d}", new_patch.name, new_patch.slots_summary))
            self.log(f"> Loaded {Path(fn).name} into Patch {idx:02d}")

    def _on_blank_single_patch(self):
        sel = self.tree_patches.selection()
        if not sel:
            return
        idx = int(sel[0])
        raw = core.make_blank_patch(index=idx, name="Empty")
        new_patch = core.decode_patch_bytes(raw, index=idx)
        for i, p in enumerate(self.patches_list):
            if p.index == idx:
                self.patches_list[i] = new_patch
                break
        self.tree_patches.item(str(idx), values=(f"{idx:02d}", "Empty", "(Empty patch)"))
        self.log(f"> Reset Patch {idx:02d} to empty patch")

    def _on_write_live_patch_midi(self):
        sel = self.tree_patches.selection()
        if not sel:
            return
        idx = int(sel[0])
        patch = next((p for p in self.patches_list if p.index == idx), None)
        if not patch:
            return

        confirm = messagebox.askyesno(
            "Write Live Patch to Pedal",
            f"WARNING: This writes Patch {idx:02d} ('{patch.name}') directly to the connected pedal over USB MIDI right now!\n\n"
            "(Marked as UNTESTED IN GUI)\n\n"
            "Do you wish to proceed?",
            parent=self,
            icon="warning",
        )
        if not confirm:
            return

        if self.busy:
            return
        self._set_busy(True, f"Writing Patch {idx:02d} over MIDI...")

        def worker():
            try:
                self.log(f"> Attempting MIDI write for Patch {idx:02d}...")
                core.write_patch_live(idx, patch.raw_data)
                self.log(f"\nSUCCESS: Patch {idx:02d} written and verified over MIDI.")
            except BaseException as e:
                self.log(f"\nERROR writing patch over MIDI: {e}")
            finally:
                self.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    # Firmware & Build Actions
    def _browse_official_updater(self):
        fn = filedialog.askopenfilename(
            title="Select Official Zoom Updater .exe",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")],
            parent=self,
        )
        if fn:
            self.official_updater_var.set(fn)

    def _browse_firmware_bin(self):
        fn = filedialog.askopenfilename(
            title="Select Firmware Binary (.bin)",
            filetypes=[("Binary", "*.bin"), ("All Files", "*.*")],
            parent=self,
        )
        if fn:
            self.firmware_bin_var.set(fn)

    def _browse_presets_bin(self):
        fn = filedialog.askopenfilename(
            title="Select Presets Region (.bin)",
            filetypes=[("Binary", "*.bin"), ("All Files", "*.*")],
            parent=self,
        )
        if fn:
            self.presets_bin_var.set(fn)

    def _on_build_installer(self):
        """Execute full safe installer build in worker thread."""
        if self.busy:
            return

        upd = self.official_updater_var.get().strip()
        fw = self.firmware_bin_var.get().strip()
        ver = self.version_var.get().strip()
        if not upd or not Path(upd).exists():
            messagebox.showerror("Build Error", "Please specify a valid official Zoom updater .exe", parent=self)
            return
        if not fw or not Path(fw).exists():
            messagebox.showerror("Build Error", "Please specify a valid firmware .bin", parent=self)
            return
        if not ver:
            messagebox.showerror("Build Error", "Please specify a build version (e.g. 0.34.5)", parent=self)
            return

        # Check capacity
        checked = [e for e in self.effects_catalog if e.is_checked]
        _, _, _, fits, msg = core.calculate_filesystem_usage(checked)
        if not fits:
            messagebox.showerror("Capacity Exceeded", msg, parent=self)
            return

        stock_keep = [e.filename for e in checked if e.source == "Zoom"]
        cf_effects = [e for e in checked if e.source == "CF"]
        presets = self.presets_bin_var.get().strip() or None
        do_backup = self.auto_backup_var.get()

        self._set_busy(True, "Building installer...")
        self.btn_cancel_build.configure(state="normal")

        def worker():
            try:
                res = core.execute_cf_installer_build(
                    official_updater_path=upd,
                    firmware_bin_path=fw,
                    selected_stock_effects=stock_keep,
                    selected_cf_effects=cf_effects,
                    version=ver,
                    presets_bin_path=presets,
                    patch_records=self.patches_list,
                    do_backup=do_backup,
                    on_output=self.log,
                    is_cancelled=lambda: self.worker_cancel_requested,
                )
                self.after(0, lambda: self._on_build_completed(res))
            except Exception as e:
                err_text = str(e)
                self.log(f"\nBUILD FAILED: {err_text}")
                self.after(0, lambda msg=err_text: messagebox.showerror("Build Failed", msg, parent=self))
            finally:
                self.after(0, lambda: self._set_busy(False))

        self.worker_cancel_requested = False
        self.active_worker = threading.Thread(target=worker, daemon=True)
        self.active_worker.start()

    def _on_cancel_build(self):
        self.worker_cancel_requested = True
        self.log("\n[User requested build cancellation...]")

    def _on_build_completed(self, result: dict):
        sha = result.get("sha256", "")
        sha_short = result.get("sha256_short", "")
        exe_path = result.get("exe_path", "")
        stages = result.get("stages", [])

        self.lbl_build_sha.configure(text=f"SHA-256: {sha} (short: {sha_short})\nFile: {exe_path}")

        for item in self.tree_stages.get_children():
            self.tree_stages.delete(item)

        for st in stages:
            parts = st.split()
            op = parts[0] if parts else ""
            addr = parts[1] if len(parts) > 1 else ""
            target = " ".join(parts[2:]) if len(parts) > 2 else ""
            self.tree_stages.insert("", "end", values=(op, addr, target))

        messagebox.showinfo(
            "Build Complete",
            f"Comet Flower Installer successfully built!\n\n"
            f"File: {Path(exe_path).name}\n"
            f"SHA-256: {sha_short}\n\n"
            "To install:\n"
            "1. Hold both footswitches while connecting USB (Update Mode).\n"
            "2. Run the generated .exe on your PC and click Execute.",
            parent=self,
        )

    # Profiles Actions
    def _on_profile_combo_selected(self, event=None):
        name = self.selected_profile_name.get()
        if name in self.profiles:
            self._update_profile_display(self.profiles[name])

    def _on_load_selected_profile(self):
        name = self.selected_profile_name.get()
        if name not in self.profiles:
            return
        prof = self.profiles[name]
        self._apply_profile(prof)
        self.log(f"> Loaded profile: '{prof.name}'")

    def _apply_profile(self, prof: core.Profile):
        """Apply profile settings to UI."""
        if prof.firmware_path:
            self.firmware_bin_var.set(prof.firmware_path)
        if prof.version:
            self.version_var.set(prof.version)
        self.auto_backup_var.set(prof.backup_before_build)

        # Apply effect selection
        if prof.checked_effects:
            target_set = set(f.upper() for f in prof.checked_effects)
            for e in self.effects_catalog:
                e.is_checked = (e.filename in target_set)
            self._filter_effects_display()

        self._update_profile_display(prof)

    def _on_save_current_profile(self):
        name = self.selected_profile_name.get().strip() or "Custom Profile"
        checked = [e.filename for e in self.effects_catalog if e.is_checked]
        prof = core.Profile(
            name=name,
            is_default=self.active_profile.is_default if self.active_profile.name == name else False,
            checked_effects=checked,
            default_patch_names={str(p.index): p.name for p in self.patches_list},
            firmware_path=self.firmware_bin_var.get(),
            version=self.version_var.get(),
            backup_before_build=self.auto_backup_var.get(),
        )
        core.save_profile(prof)
        self._refresh_profiles_list()
        self.selected_profile_name.set(name)
        self.log(f"> Saved profile: '{name}'")
        messagebox.showinfo("Profile Saved", f"Profile '{name}' saved successfully.", parent=self)

    def _on_set_default_profile(self):
        name = self.selected_profile_name.get()
        if name in self.profiles:
            core.set_default_profile(name)
            self._refresh_profiles_list()
            self.log(f"> Profile '{name}' marked as default.")

    def _on_delete_profile(self):
        name = self.selected_profile_name.get()
        if len(self.profiles) <= 1:
            messagebox.showwarning("Delete Refused", "Cannot delete the only remaining profile.", parent=self)
            return
        confirm = messagebox.askyesno("Delete Profile", f"Delete profile '{name}'?", parent=self)
        if confirm:
            core.delete_profile(name)
            self._refresh_profiles_list()

    def _on_quick_update_with_default(self):
        """One-click update with default profile."""
        default_p = core.get_default_profile()
        self._apply_profile(default_p)
        self._switch_page("Firmware & Build")
        self._on_build_installer()

    # -----------------------------------------------------------------------
    # Logging and Concurrency Helpers
    # -----------------------------------------------------------------------

    def log(self, line: str):
        """Enqueue line to thread-safe log queue."""
        self.log_queue.put(line)

    def _poll_log_queue(self):
        """Drain log queue into log Text widget."""
        while not self.log_queue.empty():
            try:
                line = self.log_queue.get_nowait()
                self.log_text.configure(state="normal")
                self.log_text.insert(tk.END, line + "\n")
                self.log_text.see(tk.END)
                self.log_text.configure(state="disabled")
            except queue.Empty:
                break
        self._poll_timer = self.after(50, self._poll_log_queue)

    def destroy(self):
        """Cleanly cancel timers on shutdown."""
        if hasattr(self, "_poll_timer") and self._poll_timer:
            try:
                self.after_cancel(self._poll_timer)
            except Exception:
                pass
            self._poll_timer = None
        super().destroy()

    def _on_clear_log(self):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state="disabled")

    def _on_copy_log(self):
        content = self.log_text.get("1.0", tk.END)
        self.clipboard_clear()
        self.clipboard_append(content)

    def _set_busy(self, busy: bool, message: str = ""):
        self.busy = busy
        st = "disabled" if busy else "normal"
        self.btn_backup_now.configure(state=st)
        self.btn_build_installer.configure(state=st)
        self.btn_quick_update.configure(state=st)
        self.lbl_worker_busy.configure(text=message if busy else "")
        if not busy:
            self.btn_cancel_build.configure(state="disabled")


def main():
    app = CFLoaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
