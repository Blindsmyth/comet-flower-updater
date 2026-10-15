"""Tkinter desktop interface for CF Loader (tools/cf_loader/app.py).

Standard library only (tkinter + ttk).
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

from tools.cf_loader import core

REPO_ROOT = core.REPO_ROOT


class CFLoaderApp(tk.Tk):
    """Main application window for CF Loader."""

    def __init__(self):
        super().__init__()
        self.title("CF Loader - G1X Four Effects Loader")
        self.minsize(960, 640)
        self.geometry("1024x700")

        # Application state
        self.config_data = core.load_config()
        self.status_data = core.load_status()
        self.scanned_effects: List[core.EffectInfo] = []
        self.selected_filenames: Set[str] = set()
        self.active_worker: Optional[threading.Thread] = None
        self.worker_cancel_requested = False
        self.log_queue: queue.Queue = queue.Queue()

        # Options state
        self.official_updater_var = tk.StringVar(value=self.config_data.get("official_updater", ""))
        self.clean_mode_var = tk.BooleanVar(value=self.config_data.get("clean_mode", True))
        self.add_probe10_var = tk.BooleanVar(value=self.config_data.get("add_probe10", False))
        self.empty_patches_var = tk.BooleanVar(value=self.config_data.get("empty_patches", False))
        self.splash_path_var = tk.StringVar(value=self.config_data.get("splash_path", ""))
        self.keep_stock_var = tk.StringVar(value=self.config_data.get("keep_stock", ""))

        self._build_ui()
        self._poll_log_queue()

        # Initial library scan and pre-flight check
        self.rescan_library()
        self.refresh_preflight()

    # -----------------------------------------------------------------------
    # UI Construction
    # -----------------------------------------------------------------------

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        # Top banner / title
        header_frame = ttk.Frame(self, padding=(10, 8))
        header_frame.pack(fill=tk.X)
        ttk.Label(
            header_frame,
            text="Comet Flower Effects Loader (G1X Four)",
            font=("Segoe UI", 13, "bold"),
        ).pack(side=tk.LEFT)
        ttk.Label(
            header_frame,
            text="Safe update-mode flash engine",
            font=("Segoe UI", 9, "italic"),
            foreground="#555555",
        ).pack(side=tk.LEFT, padx=12)

        # Notebook tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.tab_library = ttk.Frame(self.notebook, padding=10)
        self.tab_build = ttk.Frame(self.notebook, padding=10)
        self.tab_test = ttk.Frame(self.notebook, padding=10)
        self.tab_recovery = ttk.Frame(self.notebook, padding=10)
        self.tab_log = ttk.Frame(self.notebook, padding=10)
        self.tab_advanced = ttk.Frame(self.notebook, padding=10)

        self.notebook.add(self.tab_library, text="Library")
        self.notebook.add(self.tab_build, text="Build image")
        self.notebook.add(self.tab_test, text="Test (Wizard)")
        self.notebook.add(self.tab_recovery, text="Recovery")
        self.notebook.add(self.tab_log, text="Log")
        self.notebook.add(self.tab_advanced, text="Advanced")

        self._init_library_tab()
        self._init_build_tab()
        self._init_test_tab()
        self._init_recovery_tab()
        self._init_log_tab()
        self._init_advanced_tab()

    # -----------------------------------------------------------------------
    # Tab 1: Library
    # -----------------------------------------------------------------------

    def _init_library_tab(self):
        desc = ttk.Label(
            self.tab_library,
            text="Effects built in build/*.ZD2. Select effects to package into the file-system image. "
            "Refuses effects exceeding 40 KiB slot heap or colliding with stock IDs.",
            wraplength=900,
        )
        desc.pack(anchor=tk.W, pady=(0, 6))

        # Table of effects
        cols = ("sel", "file", "name", "id", "size", "text", "state", "slot", "stage")
        self.lib_tree = ttk.Treeview(self.tab_library, columns=cols, show="headings", height=14)
        self.lib_tree.heading("sel", text="Select")
        self.lib_tree.heading("file", text="File")
        self.lib_tree.heading("name", text="Effect Name")
        self.lib_tree.heading("id", text="Effect ID")
        self.lib_tree.heading("size", text="File Size")
        self.lib_tree.heading("text", text=".text")
        self.lib_tree.heading("state", text="State")
        self.lib_tree.heading("slot", text="Slot Heap (40 KiB)")
        self.lib_tree.heading("stage", text="Stage")

        self.lib_tree.column("sel", width=55, anchor=tk.CENTER)
        self.lib_tree.column("file", width=95, anchor=tk.W)
        self.lib_tree.column("name", width=110, anchor=tk.W)
        self.lib_tree.column("id", width=95, anchor=tk.W)
        self.lib_tree.column("size", width=75, anchor=tk.E)
        self.lib_tree.column("text", width=70, anchor=tk.E)
        self.lib_tree.column("state", width=65, anchor=tk.E)
        self.lib_tree.column("slot", width=130, anchor=tk.W)
        self.lib_tree.column("stage", width=95, anchor=tk.CENTER)

        tree_scroll = ttk.Scrollbar(self.tab_library, orient=tk.VERTICAL, command=self.lib_tree.yview)
        self.lib_tree.configure(yscrollcommand=tree_scroll.set)

        self.lib_tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y, in_=self.lib_tree)

        self.lib_tree.bind("<Double-1>", self._on_tree_double_click)
        self.lib_tree.bind("<space>", self._on_tree_space_toggle)
        self.lib_tree.bind("<<TreeviewSelect>>", self._on_tree_select_changed)

        # Status & Safety banner
        self.stage_info_var = tk.StringVar(
            value="Status: built | in image | audio-pass | cost-measured | ok-save"
        )
        ttk.Label(
            self.tab_library,
            textvariable=self.stage_info_var,
            font=("Segoe UI", 9, "bold"),
            foreground="#333333",
        ).pack(anchor=tk.W, pady=(6, 2))

        self.safety_banner_var = tk.StringVar(
            value="[!] DO NOT save patches with unverified DIY effects on the pedal."
        )
        self.safety_banner_lbl = ttk.Label(
            self.tab_library,
            textvariable=self.safety_banner_var,
            font=("Segoe UI", 9, "bold"),
            foreground="#bb0000",
        )
        self.safety_banner_lbl.pack(anchor=tk.W, pady=(0, 6))

        # Bottom buttons
        btn_frame = ttk.Frame(self.tab_library)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Rescan build/", command=self.rescan_library).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Toggle Selection", command=self._toggle_selected_row).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="Inspect Details...", command=self._show_effect_details).pack(side=tk.LEFT, padx=4)

    # -----------------------------------------------------------------------
    # Tab 2: Build Image
    # -----------------------------------------------------------------------

    def _init_build_tab(self):
        # 1. Official updater selection
        f1 = ttk.LabelFrame(self.tab_build, text="1. Official Zoom Updater (v2.00 G1X FOUR)", padding=8)
        f1.pack(fill=tk.X, pady=(0, 8))

        row1 = ttk.Frame(f1)
        row1.pack(fill=tk.X)
        ttk.Entry(row1, textvariable=self.official_updater_var, width=70).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(row1, text="Browse...", command=self._browse_official_updater).pack(side=tk.RIGHT)

        self.updater_status_var = tk.StringVar(value="Not selected")
        self.updater_status_lbl = ttk.Label(f1, textvariable=self.updater_status_var, font=("Segoe UI", 9))
        self.updater_status_lbl.pack(anchor=tk.W, pady=(4, 0))

        # 2. Base filesystem configuration
        f2 = ttk.LabelFrame(self.tab_build, text="2. Base Filesystem & Options", padding=8)
        f2.pack(fill=tk.X, pady=(0, 8))

        ttk.Radiobutton(
            f2,
            text="Clean test environment: remove stock effects, keep system files (proven safe, compact directory)",
            variable=self.clean_mode_var,
            value=True,
            command=self.refresh_preflight,
        ).pack(anchor=tk.W)

        r_stock = ttk.Frame(f2)
        r_stock.pack(fill=tk.X, pady=2)
        ttk.Radiobutton(
            r_stock,
            text="Keep stock effects (enter comma-separated effects to keep, or leave empty for all):",
            variable=self.clean_mode_var,
            value=False,
            command=self.refresh_preflight,
        ).pack(side=tk.LEFT)
        ttk.Entry(r_stock, textvariable=self.keep_stock_var, width=30).pack(side=tk.LEFT, padx=6)

        opts_row = ttk.Frame(f2)
        opts_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Checkbutton(
            opts_row,
            text="Add PROBE10 (cost benchmark)",
            variable=self.add_probe10_var,
            command=self.refresh_preflight,
        ).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Checkbutton(
            opts_row,
            text="Empty patch presets (factory resource)",
            variable=self.empty_patches_var,
            command=self.refresh_preflight,
        ).pack(side=tk.LEFT, padx=(0, 15))

        splash_row = ttk.Frame(f2)
        splash_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(splash_row, text="Startup splash PNG (128x32, 1-bit, optional):").pack(side=tk.LEFT)
        ttk.Entry(splash_row, textvariable=self.splash_path_var, width=45).pack(side=tk.LEFT, padx=6)
        ttk.Button(splash_row, text="Browse...", command=self._browse_splash).pack(side=tk.LEFT)

        # 3. Pre-flight checks panel
        f3 = ttk.LabelFrame(self.tab_build, text="3. Pre-Flight Verification (7 Checks)", padding=8)
        f3.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self.preflight_text = tk.Text(f3, height=8, wrap=tk.WORD, font=("Consolas", 9), relief=tk.FLAT)
        self.preflight_text.pack(fill=tk.BOTH, expand=True)
        self.preflight_text.tag_config("pass", foreground="#007700")
        self.preflight_text.tag_config("fail", foreground="#cc0000", font=("Consolas", 9, "bold"))
        self.preflight_text.configure(state=tk.DISABLED)

        # 4. Action bar
        act_frame = ttk.Frame(self.tab_build)
        act_frame.pack(fill=tk.X)
        self.btn_build = ttk.Button(
            act_frame,
            text="Build Image and Patched Updater",
            command=self._start_build_image,
            style="Accent.TButton",
        )
        self.btn_build.pack(side=tk.LEFT, padx=4)

        ttk.Button(act_frame, text="Cancel Build", command=self._cancel_build).pack(side=tk.LEFT, padx=4)

        self.build_status_var = tk.StringVar(value="Ready")
        ttk.Label(act_frame, textvariable=self.build_status_var, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=10)

    # -----------------------------------------------------------------------
    # Tab 3: Test (Wizard)
    # -----------------------------------------------------------------------

    def _init_test_tab(self):
        desc = ttk.Label(
            self.tab_test,
            text="On-Pedal Test Wizard (DSP_RULES §4 and §5). Complete each step in order. "
            "Never save patches holding an effect that has not passed both audio and cost tests.",
            wraplength=900,
        )
        desc.pack(anchor=tk.W, pady=(0, 6))

        # Target effect selector
        sel_row = ttk.Frame(self.tab_test)
        sel_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(sel_row, text="Effect under test:").pack(side=tk.LEFT, padx=(0, 6))
        self.test_effect_combo = ttk.Combobox(sel_row, state="readonly", width=30)
        self.test_effect_combo.pack(side=tk.LEFT)
        self.test_effect_combo.bind("<<ComboboxSelected>>", self._on_test_effect_selected)

        # Wizard container
        wiz_frame = ttk.LabelFrame(self.tab_test, text="Test Checklist & Safety Protocol", padding=10)
        wiz_frame.pack(fill=tk.BOTH, expand=True, pady=4)

        self.chk_autosave_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            wiz_frame,
            text="1. Pedal AUTO SAVE is turned OFF (Global settings -> AUTO SAVE -> OFF)",
            variable=self.chk_autosave_var,
        ).pack(anchor=tk.W, pady=3)

        self.chk_updatemode_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            wiz_frame,
            text="2. Entered update mode: hold both footswitches while connecting USB ('FIRMWARE UPDATE' screen)",
            variable=self.chk_updatemode_var,
        ).pack(anchor=tk.W, pady=3)

        self.chk_flashed_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            wiz_frame,
            text="3. Flashed patched updater by hand: MIDI IN/OUT = 'ZOOM G Series' -> wait for 'Version update completed'",
            variable=self.chk_flashed_var,
        ).pack(anchor=tk.W, pady=3)

        self.chk_powercycled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            wiz_frame,
            text="4. Power cycle the pedal (unplug USB, plug back in). Boots to clean/normal screen",
            variable=self.chk_powercycled_var,
        ).pack(anchor=tk.W, pady=3)

        self.chk_alone_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            wiz_frame,
            text="5. Placed effect alone in an empty patch (no other effects in chain)",
            variable=self.chk_alone_var,
        ).pack(anchor=tk.W, pady=3)

        # Audio pass section
        audio_frame = ttk.LabelFrame(wiz_frame, text="6. Audio Pass Check", padding=6)
        audio_frame.pack(fill=tk.X, pady=6)
        ttk.Label(audio_frame, text="Audio passes cleanly with no stutter, glitch, or DC offset:").pack(side=tk.LEFT, padx=4)
        ttk.Button(audio_frame, text="Record Audio Pass", command=self._record_audio_pass).pack(side=tk.LEFT, padx=8)
        self.audio_status_lbl = ttk.Label(audio_frame, text="Not passed", foreground="#888888")
        self.audio_status_lbl.pack(side=tk.LEFT, padx=4)

        # Cost test section
        cost_frame = ttk.LabelFrame(wiz_frame, text="7. CPU measurement pending", padding=6)
        cost_frame.pack(fill=tk.X, pady=6)
        ttk.Label(
            cost_frame,
            text="Probe 10 freeze load does not yield a calibrated cycle cost.\n"
            "Record a direct TSCL measurement and validate the full patch before authorizing a save.",
        ).pack(anchor=tk.W)
        self.cost_result_var = tk.StringVar(value="No reading recorded")
        ttk.Label(cost_frame, textvariable=self.cost_result_var, font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)

        # Final approval section
        final_frame = ttk.LabelFrame(wiz_frame, text="8. Patch Save Authorization", padding=6)
        final_frame.pack(fill=tk.X, pady=6)
        self.btn_mark_ok = ttk.Button(
            final_frame,
            text="Authorize 'OK to Save Patches'",
            command=self._mark_ok_save,
            state=tk.DISABLED,
        )
        self.btn_mark_ok.pack(side=tk.LEFT, padx=6)
        self.test_warning_lbl = ttk.Label(
            final_frame,
            text="[!] Blocked: requires both audio pass and cost measurement.",
            foreground="#cc0000",
            font=("Segoe UI", 9, "bold"),
        )
        self.test_warning_lbl.pack(side=tk.LEFT, padx=6)

    # -----------------------------------------------------------------------
    # Tab 4: Recovery
    # -----------------------------------------------------------------------

    def _init_recovery_tab(self):
        desc = ttk.Label(
            self.tab_recovery,
            text="Pedal Recovery: Restore factory effect file system without touching boot program.\n"
            "Builds a safe restore updater from Zoom's official updater (proven on 2026-10-06 incident).",
            wraplength=900,
        )
        desc.pack(anchor=tk.W, pady=(0, 8))

        rec_btn_frame = ttk.Frame(self.tab_recovery)
        rec_btn_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(
            rec_btn_frame,
            text="Build Factory Restore Updater",
            command=self._start_build_restore,
            style="Accent.TButton",
        ).pack(side=tk.LEFT, padx=4)

        ttk.Button(rec_btn_frame, text="Cancel Build", command=self._cancel_build).pack(side=tk.LEFT, padx=4)
        self.rec_status_var = tk.StringVar(value="")
        ttk.Label(rec_btn_frame, textvariable=self.rec_status_var, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=10)

        # Numbered checklist from RECOVERY_G1.md
        f_steps = ttk.LabelFrame(self.tab_recovery, text="Recovery Procedure (RECOVERY_G1.md)", padding=8)
        f_steps.pack(fill=tk.BOTH, expand=True)

        steps_text = (
            "WHAT FIXED IT:\n"
            "1. Obtain Zoom's official 'ZOOM G1X FOUR System v2.00 Updater.exe' (from G1X_FOUR_v2.00_Win_E.zip).\n"
            "2. Click 'Build Factory Restore Updater' above.\n"
            "3. Enter update mode on the pedal: hold BOTH footswitches while connecting USB until 'FIRMWARE UPDATE' screen appears.\n"
            "4. Run the produced restore updater copy by hand. Select 'ZOOM G Series' for MIDI IN and OUT, then Execute.\n"
            "5. Do NOT disconnect until the screen shows 'Version update completed'.\n"
            "6. Unplug USB and power on normally. Pedal boots with factory effects.\n\n"
            "WHAT DOES NOT FIX IT:\n"
            "- Zoom's official updater without patch: writes boot/firmware only, never writes the effect file system.\n"
            "- Factory reset (hold MEMORY/STOMP/EDIT): resets patches only, does not touch the file system."
        )
        t = tk.Text(f_steps, height=12, wrap=tk.WORD, font=("Consolas", 9), relief=tk.FLAT)
        t.insert("1.0", steps_text)
        t.configure(state=tk.DISABLED)
        t.pack(fill=tk.BOTH, expand=True)

    # -----------------------------------------------------------------------
    # Tab 5: Log
    # -----------------------------------------------------------------------

    def _init_log_tab(self):
        desc = ttk.Label(
            self.tab_log,
            text="Subprocess execution log. Every command, output line, and exit code is recorded to build/loader/loader.log.",
        )
        desc.pack(anchor=tk.W, pady=(0, 6))

        self.log_text = tk.Text(self.tab_log, wrap=tk.WORD, font=("Consolas", 9), background="#1e1e1e", foreground="#d4d4d4")
        log_scroll = ttk.Scrollbar(self.tab_log, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y, in_=self.log_text)

        btn_row = ttk.Frame(self.tab_log)
        btn_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btn_row, text="Open Log File", command=self._open_log_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="Clear Log View", command=lambda: self.log_text.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=4)

    # -----------------------------------------------------------------------
    # Tab 6: Advanced (Backup)
    # -----------------------------------------------------------------------

    def _init_advanced_tab(self):
        warn_frame = ttk.LabelFrame(self.tab_advanced, text="CRITICAL HARDWARE WARNING", padding=10)
        warn_frame.pack(fill=tk.X, pady=(0, 10))

        warn_text = (
            "NOTICE (recon/07):\n"
            "The pedal's USB port is a delicate hand-soldered repair.\n"
            "DO NOT power-cycle the pedal if a backup or transfer stalls or times out!\n"
            "If stopped: Leave the pedal powered, re-plug USB only, then re-run to resume.\n"
            "Only backup_g1.py (read-only file dump) is offered here. No MIDI write functions exist."
        )
        ttk.Label(warn_frame, text=warn_text, foreground="#aa0000", font=("Segoe UI", 9, "bold")).pack(anchor=tk.W)

        self.confirm_backup_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            self.tab_advanced,
            text="I understand the DO-NOT-POWER-CYCLE rule and have a stable USB cable connected",
            variable=self.confirm_backup_var,
        ).pack(anchor=tk.W, pady=6)

        b_row = ttk.Frame(self.tab_advanced)
        b_row.pack(fill=tk.X, pady=6)
        ttk.Button(b_row, text="Run Read-Only Backup (backup_g1.py)", command=self._start_backup).pack(side=tk.LEFT, padx=4)
        self.backup_status_var = tk.StringVar(value="")
        ttk.Label(b_row, textvariable=self.backup_status_var, font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=8)

    # -----------------------------------------------------------------------
    # Library Operations
    # -----------------------------------------------------------------------

    def rescan_library(self):
        """Scan build/*.ZD2 and refresh the library tree."""
        self.scanned_effects = core.scan_library()
        self.status_data = core.load_status()

        # Preserve valid selections
        valid_filenames = {e.filename for e in self.scanned_effects if e.valid_for_selection}
        self.selected_filenames = self.selected_filenames.intersection(valid_filenames)

        # Clear tree
        for item in self.lib_tree.get_children():
            self.lib_tree.delete(item)

        for eff in self.scanned_effects:
            is_sel = eff.filename in self.selected_filenames
            sel_mark = "[x]" if is_sel else "[ ]"

            size_str = f"{eff.size / 1024:.1f}K"
            text_str = f"{eff.report.text_bytes / 1024:.1f}K" if eff.report.text_bytes else "-"
            state_str = str(eff.report.state_bytes) if eff.report.state_bytes else "-"

            if eff.has_oversize_sibling:
                slot_str = "OVERSIZE sibling"
            elif not eff.slot_ok:
                slot_str = f"OVER ({eff.slot_used} B)"
            else:
                slot_str = f"OK ({eff.slot_free} free)"

            stage = self.status_data.get(eff.filename, {}).get("stage", "built")

            iid = eff.filename
            self.lib_tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(sel_mark, eff.filename, eff.name, eff.id_hex, size_str, text_str, state_str, slot_str, stage),
            )

        # Update test combo box
        eff_names = [e.filename for e in self.scanned_effects]
        self.test_effect_combo["values"] = eff_names
        if eff_names and not self.test_effect_combo.get():
            self.test_effect_combo.current(0)
            self._on_test_effect_selected(None)

        self.refresh_preflight()

    def _on_tree_double_click(self, event):
        self._toggle_selected_row()

    def _on_tree_space_toggle(self, event):
        self._toggle_selected_row()

    def _toggle_selected_row(self):
        sel = self.lib_tree.selection()
        if not sel:
            return
        filename = sel[0]
        eff = next((e for e in self.scanned_effects if e.filename == filename), None)
        if not eff:
            return

        if filename in self.selected_filenames:
            self.selected_filenames.remove(filename)
        else:
            if not eff.valid_for_selection:
                reasons = "\n- ".join(eff.rejection_reasons)
                messagebox.showerror(
                    "Selection Refused",
                    f"Effect '{eff.filename}' cannot be selected:\n- {reasons}",
                )
                return
            self.selected_filenames.add(filename)

        # Refresh row display
        is_sel = filename in self.selected_filenames
        vals = list(self.lib_tree.item(filename, "values"))
        vals[0] = "[x]" if is_sel else "[ ]"
        self.lib_tree.item(filename, values=vals)

        self.refresh_preflight()

    def _on_tree_select_changed(self, event):
        sel = self.lib_tree.selection()
        if not sel:
            return
        filename = sel[0]
        stage = self.status_data.get(filename, {}).get("stage", "built")
        self.stage_info_var.set(
            f"Effect: {filename} | Stage: {stage.upper()} (built -> in image -> audio-pass -> cost-measured -> ok-save)"
        )
        self.safety_banner_var.set(
            f"[!] Save approval for '{filename}' is pending calibrated CPU and exact-artifact checks."
        )
        self.safety_banner_lbl.configure(foreground="#bb0000")

    def _show_effect_details(self):
        sel = self.lib_tree.selection()
        if not sel:
            messagebox.showinfo("Details", "Select an effect in the list first.")
            return
        filename = sel[0]
        eff = next((e for e in self.scanned_effects if e.filename == filename), None)
        if not eff:
            return

        status_entry = self.status_data.get(filename, {})
        lines = [
            f"File: {eff.filename} ({eff.path})",
            f"Effect Name: {eff.name}",
            f"Effect ID: {eff.id_hex}",
            f"Target: 0x{eff.target:x} (G1: {eff.is_g1_target})",
            f"Size: {eff.size:,} bytes",
            f"CRC32 valid: {eff.crc_ok}",
            f"Slot Memory: {eff.slot_used:,} / {core.SLOT_HEAP:,} bytes ({eff.slot_free:,} free, OK={eff.slot_ok})",
            f"Oversize sibling: {eff.has_oversize_sibling}",
            f".text budget: {eff.report.text_bytes or 'unknown'} bytes",
            f"State: {eff.report.state_bytes or 'unknown'} bytes",
            f"Lifecycle Stage: {status_entry.get('stage', 'built')}",
            f"Audio Passed: {status_entry.get('audio_passed', False)}",
            f"Cost Measured: {status_entry.get('cost_measured', False)} ({status_entry.get('measured_cost')} cycles)",
        ]
        if eff.rejection_reasons:
            lines.append("\nRejection Reasons:")
            for r in eff.rejection_reasons:
                lines.append(f"  * {r}")

        messagebox.showinfo(f"Details: {eff.filename}", "\n".join(lines))

    # -----------------------------------------------------------------------
    # Build Image & Pre-Flight
    # -----------------------------------------------------------------------

    def _browse_official_updater(self):
        path = filedialog.askopenfilename(
            title="Select Official Zoom G1X Four v2.00 Updater",
            filetypes=[("Executable", "*.exe"), ("All Files", "*.*")],
        )
        if path:
            self.official_updater_var.set(path)
            self.config_data["official_updater"] = path
            core.save_config(self.config_data)
            self.refresh_preflight()

    def _browse_splash(self):
        path = filedialog.askopenfilename(
            title="Select 128x32 1-bit Splash PNG",
            filetypes=[("PNG Image", "*.png"), ("All Files", "*.*")],
        )
        if path:
            self.splash_path_var.set(path)
            self.config_data["splash_path"] = path
            core.save_config(self.config_data)

    def refresh_preflight(self):
        """Run the 7 pre-flight checks and update UI."""
        updater_path = self.official_updater_var.get().strip() or None
        if updater_path:
            v = core.verify_official_updater(updater_path)
            if v.valid:
                self.updater_status_var.set(f"[PASS] {v.message} ({v.size:,} B, CRC32 {v.crc32})")
                self.updater_status_lbl.configure(foreground="#007700")
            else:
                self.updater_status_var.set(f"[FAIL] {v.message}")
                self.updater_status_lbl.configure(foreground="#cc0000")
        else:
            self.updater_status_var.set("No official updater selected")
            self.updater_status_lbl.configure(foreground="#666666")

        selected_effs = [e for e in self.scanned_effects if e.filename in self.selected_filenames]
        clean = self.clean_mode_var.get()

        keep_raw = self.keep_stock_var.get().strip()
        keep_tuple = tuple(x.strip().upper() for x in keep_raw.split(",") if x.strip())

        checks = core.run_preflight_checks(
            updater_path, selected_effs, clean=clean, keep_stock=keep_tuple,
            add_probe10=self.add_probe10_var.get()
        )

        all_ok = core.all_preflight_passed(checks)

        # Update text view
        self.preflight_text.configure(state=tk.NORMAL)
        self.preflight_text.delete("1.0", tk.END)
        for c in checks:
            tag = "pass" if c.passed else "fail"
            mark = "[PASS]" if c.passed else "[FAIL]"
            self.preflight_text.insert(tk.END, f"{mark} Check {c.check_num}: {c.title}\n", tag)
            self.preflight_text.insert(tk.END, f"       {c.message}\n")
        self.preflight_text.configure(state=tk.DISABLED)

        # Enable/disable Build button
        if all_ok:
            self.btn_build.configure(state=tk.NORMAL)
            self.build_status_var.set("All pre-flight checks green. Ready to build.")
        else:
            self.btn_build.configure(state=tk.DISABLED)
            self.build_status_var.set("Build blocked: one or more pre-flight checks failed.")

    def _cancel_build(self):
        self.worker_cancel_requested = True

    def _start_build_image(self):
        """Start building image in worker thread."""
        if self.active_worker and self.active_worker.is_alive():
            messagebox.showwarning("Busy", "A build task is already running.")
            return

        updater_path = self.official_updater_var.get().strip()
        selected_effs = [e for e in self.scanned_effects if e.filename in self.selected_filenames]
        clean = self.clean_mode_var.get()
        keep_raw = self.keep_stock_var.get().strip()
        keep_tuple = tuple(x.strip().upper() for x in keep_raw.split(",") if x.strip())
        probe10 = self.add_probe10_var.get()
        empty_patches = self.empty_patches_var.get()
        splash = self.splash_path_var.get().strip() or None

        self.worker_cancel_requested = False
        self.btn_build.configure(state=tk.DISABLED)
        self.build_status_var.set("Building image and patched updater...")

        def worker():
            try:
                out_dir = core.build_image_and_updater(
                    official_updater_path=updater_path,
                    selected_effects=selected_effs,
                    clean=clean,
                    keep_stock=keep_tuple,
                    add_probe10=probe10,
                    empty_patches=empty_patches,
                    splash_png=splash,
                    on_output=lambda l: self.log_queue.put(l),
                    is_cancelled=lambda: self.worker_cancel_requested,
                )
                self.log_queue.put(f"[COMPLETE] Build succeeded: {out_dir}")
                self.after(0, lambda: self._on_build_completed(out_dir))
            except Exception as e:
                self.log_queue.put(f"[ERROR] Build failed: {e}")
                self.after(0, lambda error=str(e): self._on_build_failed(error))

        self.active_worker = threading.Thread(target=worker, daemon=True)
        self.active_worker.start()

    def _on_build_completed(self, out_dir: Path):
        self.build_status_var.set(f"Built successfully: {out_dir.name}")
        self.rescan_library()
        messagebox.showinfo(
            "Build Complete",
            f"Patched updater built successfully in:\n{out_dir}\n\n"
            "The app will NEVER launch the updater automatically.\n"
            "Open the folder, put pedal in update mode, and flash manually following the checklist in the Test tab.",
        )
        # Open Explorer
        try:
            os.startfile(str(out_dir))
        except Exception:
            pass

    def _on_build_failed(self, err_msg: str):
        self.build_status_var.set("Build failed.")
        self.refresh_preflight()
        messagebox.showerror("Build Error", f"Failed to build image:\n{err_msg}")

    # -----------------------------------------------------------------------
    # Test Tab Operations
    # -----------------------------------------------------------------------

    def _on_test_effect_selected(self, event):
        eff_name = self.test_effect_combo.get()
        if not eff_name:
            return
        status_entry = self.status_data.get(eff_name, {})
        stage = status_entry.get("stage", "built")

        # Audio status
        if status_entry.get("audio_passed"):
            self.audio_status_lbl.configure(text="[PASS] Audio verified", foreground="#007700")
        else:
            self.audio_status_lbl.configure(text="Not passed", foreground="#888888")

        # Cost status
        cost = status_entry.get("measured_cost")
        if cost is not None:
            self.cost_result_var.set(f"Measured: {cost:,} cycles")
        else:
            self.cost_result_var.set("No reading recorded")

        # Approval button state
        self.btn_mark_ok.configure(state=tk.DISABLED)
        self.test_warning_lbl.configure(
            text="[!] Save approval pending calibrated CPU and exact-artifact checks.",
            foreground="#cc0000",
        )

    def _record_audio_pass(self):
        eff_name = self.test_effect_combo.get()
        if not eff_name:
            messagebox.showwarning("Test", "Select an effect under test first.")
            return

        core.update_effect_stage(eff_name, "audio-pass", notes="Audio check passed on pedal")
        self.status_data = core.load_status()
        self._on_test_effect_selected(None)
        self.rescan_library()
        messagebox.showinfo("Audio Pass", f"Recorded 'audio-pass' for {eff_name}.")

    def _mark_ok_save(self):
        eff_name = self.test_effect_combo.get()
        if not eff_name:
            return

        try:
            core.update_effect_stage(eff_name, "ok-save", notes="Fully verified on hardware")
            self.status_data = core.load_status()
            self._on_test_effect_selected(None)
            self.rescan_library()
            messagebox.showinfo(
                "Authorized",
                f"Effect '{eff_name}' is now marked OK to save in patches on the pedal!",
            )
        except ValueError as e:
            messagebox.showerror("Gating Error", str(e))

    # -----------------------------------------------------------------------
    # Recovery Operations
    # -----------------------------------------------------------------------

    def _start_build_restore(self):
        if self.active_worker and self.active_worker.is_alive():
            messagebox.showwarning("Busy", "A build task is already running.")
            return
        self.worker_cancel_requested = False
        updater_path = self.official_updater_var.get().strip()
        if not updater_path:
            messagebox.showerror("Recovery", "Select the official Zoom updater in the 'Build image' tab first.")
            return

        self.rec_status_var.set("Building factory restore updater...")

        def worker():
            try:
                out_dir = core.build_factory_restore_updater(
                    official_updater_path=updater_path,
                    on_output=lambda l: self.log_queue.put(l),
                    is_cancelled=lambda: self.worker_cancel_requested,
                )
                self.log_queue.put(f"[COMPLETE] Factory restore updater built: {out_dir}")
                self.after(0, lambda: self._on_restore_completed(out_dir))
            except Exception as e:
                self.log_queue.put(f"[ERROR] Restore build failed: {e}")
                self.after(0, lambda error=str(e): self._on_restore_failed(error))

        self.active_worker = threading.Thread(target=worker, daemon=True)
        self.active_worker.start()

    def _on_restore_completed(self, out_dir: Path):
        self.rec_status_var.set("Restore updater ready.")
        messagebox.showinfo(
            "Restore Updater Ready",
            f"Factory restore updater created in:\n{out_dir}\n\n"
            "Hold both footswitches while connecting USB, then run the restore updater by hand.",
        )
        try:
            os.startfile(str(out_dir))
        except Exception:
            pass

    def _on_restore_failed(self, err_msg: str):
        self.rec_status_var.set("Restore build failed.")
        messagebox.showerror("Recovery Error", f"Failed to build restore updater:\n{err_msg}")

    # -----------------------------------------------------------------------
    # Advanced (Backup) Operations
    # -----------------------------------------------------------------------

    def _start_backup(self):
        if not self.confirm_backup_var.get():
            messagebox.showerror(
                "Confirmation Required",
                "You must check the confirmation box acknowledging the DO-NOT-POWER-CYCLE rule before running a backup.",
            )
            return

        if not messagebox.askyesno(
            "Confirm Read-Only Backup",
            "This opens the pedal connection for a read-only backup. "
            "DO NOT power-cycle the pedal if the backup stalls or times out. Continue?",
        ):
            return

        out_dir = core.create_output_folder("backup_")

        py = str(core.get_python_exe())
        cmd = [py, str(REPO_ROOT / "tools" / "backup_g1.py"), str(out_dir)]

        self.backup_status_var.set("Running backup_g1.py...")

        def worker():
            try:
                res = core.run_tool(cmd, on_output=lambda l: self.log_queue.put(l), timeout=600.0)
                if res.exit_code == 0:
                    self.after(0, lambda: messagebox.showinfo("Backup", f"Backup completed successfully in:\n{out_dir}"))
                elif res.exit_code == 1:
                    self.after(
                        0,
                        lambda: messagebox.showerror(
                            "Backup Error",
                            "Backup failed: No 'ZOOM G' port found (line 105).\n"
                            "Is ToneLib or another editor open, or is the USB cable disconnected?",
                        ),
                    )
                elif res.exit_code == 2:
                    self.after(
                        0,
                        lambda: messagebox.showerror(
                            "Backup Error",
                            "Backup failed: Invalid argument count (line 95-97).",
                        ),
                    )
                elif res.exit_code == 3:
                    self.after(
                        0,
                        lambda: messagebox.showerror(
                            "Backup Incomplete",
                            "Backup incomplete: Registered effects missing from walk.",
                        ),
                    )
                elif res.exit_code == 4:
                    self.after(
                        0,
                        lambda: messagebox.showerror(
                            "Backup Timeout",
                            "Backup stopped: Pedal stopped replying.\n"
                            "DO NOT power-cycle the pedal! Leave it powered, re-plug USB only, and re-run.",
                        ),
                    )
                else:
                    self.after(0, lambda: messagebox.showerror("Backup", f"Backup finished with exit code {res.exit_code}."))
            except Exception as e:
                self.after(0, lambda error=str(e): messagebox.showerror("Backup Error", error))
            finally:
                self.after(0, lambda: self.backup_status_var.set(""))

        threading.Thread(target=worker, daemon=True).start()

    # -----------------------------------------------------------------------
    # Log Operations
    # -----------------------------------------------------------------------

    def _poll_log_queue(self):
        """Poll incoming log lines from worker threads."""
        while not self.log_queue.empty():
            line = self.log_queue.get_nowait()
            self.log_text.insert(tk.END, line + "\n")
            self.log_text.see(tk.END)
        self.after(100, self._poll_log_queue)

    def _open_log_file(self):
        log_path = REPO_ROOT / "build" / "loader" / "loader.log"
        if log_path.exists():
            try:
                os.startfile(str(log_path))
            except Exception:
                messagebox.showinfo("Log", f"Log file located at: {log_path}")
        else:
            messagebox.showinfo("Log", "Log file does not exist yet.")


def main():
    app = CFLoaderApp()
    app.mainloop()


if __name__ == "__main__":
    main()
