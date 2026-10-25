"""Comet Flower Firmware Flasher GUI (Razor 1911 / Modeler Style).

Implements a classic demogroup keygen/patcher interface with:
- Modeler palette tokens from VirtualPedalBoardEngine (Source/ModelerStyle.h)
- Razor 1911 ASCII art title banner & NFO viewer
- CRT green/cyan terminal well for live flashing telemetry
- Retro block-style animated progress bar
- Continuous bottom marquee / sine scroller
- 8-bit chiptune synthesizer background music playing Comfortably Numb Solo 2 chords (Bm - A - G - Em)
- Latest Comet Flower firmware v0.34.9 payload BAKED IN directly to the executable
"""

import json
import os
from pathlib import Path
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

import cf_flasher as flasher
import cf_keygen_music as keygen_music

# --- VirtualPedalBoardEngine Palette (Source/ModelerStyle.h) ---
BG_DARK = "#0a0b0c"
BG_PANEL = "#131519"
BG_WELL = "#050506"
COLOR_AMBER = "#ffb547"
COLOR_AMBER_DEEP = "#8a6120"
COLOR_CYAN = "#52c6f5"
COLOR_GREEN = "#3fcf8e"
COLOR_RED = "#ff5d57"
COLOR_MAGENTA = "#f277b8"
COLOR_TEXT1 = "#f3f0ea"
COLOR_TEXT2 = "#a9a69f"
COLOR_TEXT3 = "#6f6d68"
COLOR_BORDER = "#2b2d31"

ASCII_BANNER = r"""
 ██████╗ ██████╗ ███╗   ███╗███████╗████████╗    ███████╗██╗     ██╗    ██╗██████╗ 
██╔════╝██╔═══██╗████╗ ████║██╔════╝╚══██╔══╝    ██╔════╝██║     ██║    ██║██╔══██╗
██║     ██║   ██║██╔████╔██║█████╗     ██║       █████╗  ██║     ██║ █╗ ██║██████╔╝
██║     ██║   ██║██║╚██╔╝██║██╔══╝     ██║       ██╔══╝  ██║     ██║███╗██║██╔══██╗
╚██████╗╚██████╔╝██║ ╚═╝ ██║███████╗   ██║       ██║     ███████╗╚███╔███╔╝██║  ██║
 ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝   ╚═╝       ╚═╝     ╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝
"""

NFO_TEXT = """
┌────────────────────────────────────────────────────────────────────────┐
│     COMET FLOWER LABS 1911 // 2026 SPECIAL HARDWARE RELEASE            │
│     ZOOM G1 / G1X FOUR FIRMWARE UNLEASHED & STANDALONE FLASHER         │
└────────────────────────────────────────────────────────────────────────┘

[RELEASE INFO]
  Supplier .....: Comet Flower Labs     Release Type ..: Firmware Unlocker
  Target HW ....: Zoom G1X / G1 Four    OS ............: Windows / C6745
  DSP Clock ....: TMS320C6745 @ 300MHz  Protection ....: AIS / CRC / res5
  Cracker ......: Comet Flower Demogroup & AI Synthesis Division
  Music ........: Comfortably Numb Solo 2 Changes (Bm - A - G - Em)

[RELEASE NOTES]
  Completely independent firmware flashing tool! Zoom's proprietary
  updater is no longer required. Flashes native MIDI SysEx wire protocol:

  * Latest Comet Flower Firmware v0.34.9 BAKED DIRECTLY IN
  * 5 Real Effect Slots with Unlocked Cycle Allocation (Gate 230 -> 340)
  * Circuit-Exact DSP Suite: '74 Violet Big Muff (12nF C10 audited),
    Hiwatt DR103 Custom 100, Comet Flower Preamp, Comet Flower Delay
    with True Spillover Tail, Comet Flower Rotary, Comet Flower 808
  * Custom Visual Identity: res5 Bootloader Bud Logo, 16-Frame Bloom
    Startup Animation, Comet Flower Edit Header & Realtime CPU Meter
  * Injected Comet Flower Probe SysEx Backdoor: Live RAM peek/poke & telemetry

[GREETS]
  Razor 1911 * Fairlight * Paradox * Deviance * Reloaded * Hoodlum * Skid Row
──────────────────────────────────────────────────────────────────────────
[+] COMET FLOWER LABS - EXPAND YOUR HARDWARE - RESPECT THE SCENE [+]
"""

SCROLLER_MESSAGE = (
    "*** COMET FLOWER LABS 1911 *** COMET FLOWER ZOOM G1X-FOUR UNLEASHED STANDALONE FLASHER *** "
    "5 REAL EFFECT SLOTS *** VIOLET MUFF 12nF C10 AUDITED *** HIWATT DR103 *** "
    "COMET FLOWER PREAMP *** COMET FLOWER DELAY TAIL *** CYCLE GATE 340% UNLOCKED *** "
    "ZERO ZOOM BINARIES *** BAKED-IN FIRMWARE v0.34.9 *** "
    "MUSIC: COMFORTABLY NUMB SOLO 2 PROGRESSION (Bm - A - G - Em) *** "
    "GREETS TO: RAZOR 1911 * FAIRLIGHT * PARADOX * DEVIANCE * RELOADED * HOODLUM *** "
)


def get_bundled_payload_path(filename: str) -> Optional[Path]:
    """Resolves a file from PyInstaller bundle, tools/payload, or repo build directories."""
    # 1. PyInstaller single-file bundle extraction directory
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass_p = Path(sys._MEIPASS) / "payload" / filename
        if meipass_p.is_file():
            return meipass_p

    # 2. Local tools/payload directory
    local_payload = REPO_ROOT / "tools" / "payload" / filename
    if local_payload.is_file():
        return local_payload

    # 3. Fallback to build locations
    fallback_map = {
        "firmware_0349.bin": REPO_ROOT / "build" / "fw_rnd_2026-10-22" / "res1_0348.bin",
        "fs_0349.bin": REPO_ROOT / "build" / "fw_rnd_2026-10-22" / "fs_bench349.bin",
        "presets_0349.bin": REPO_ROOT / "build" / "fw_rnd_2026-10-22" / "res2_0349.bin",
    }
    fb = fallback_map.get(filename)
    if fb and fb.is_file():
        return fb
    return None


class FlasherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Comet Flower Labs 1911 // Zoom G1X Four Unleashed")
        self.root.geometry("740x740")
        self.root.minsize(700, 700)
        self.root.configure(bg=BG_DARK)

        self.music = keygen_music.KeygenMusicPlayer()
        self.is_flashing = False

        self._resolve_baked_in_payload()
        self._build_ui()
        self._start_marquee()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _resolve_baked_in_payload(self):
        self.baked_fw = get_bundled_payload_path("firmware_0349.bin")
        self.baked_fs = get_bundled_payload_path("fs_0349.bin")
        self.baked_presets = get_bundled_payload_path("presets_0349.bin")

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=BG_WELL, background=BG_PANEL, foreground=COLOR_TEXT1)

        # 1. Header Frame (Banner + Subtitle)
        header_frame = tk.Frame(self.root, bg=BG_DARK)
        header_frame.pack(fill=tk.X, padx=12, pady=(8, 0))

        banner_lbl = tk.Label(
            header_frame,
            text=ASCII_BANNER.strip("\n"),
            font=("Consolas", 7, "bold"),
            fg=COLOR_AMBER,
            bg=BG_DARK,
            justify=tk.CENTER,
        )
        banner_lbl.pack()

        sub_lbl = tk.Label(
            header_frame,
            text="[+] RAZOR 1911 DEMOGROUP STYLE  ///  COMET FLOWER FIRMWARE FLASHER [+]",
            font=("Consolas", 8, "bold"),
            fg=COLOR_CYAN,
            bg=BG_DARK,
        )
        sub_lbl.pack(pady=(2, 6))

        # 2. Hardware / Port Status Strip
        status_frame = tk.Frame(self.root, bg=BG_PANEL, bd=1, relief=tk.SOLID, highlightbackground=COLOR_BORDER)
        status_frame.pack(fill=tk.X, padx=14, pady=4)

        tk.Label(
            status_frame,
            text=" TARGET: ",
            font=("Consolas", 8, "bold"),
            fg=COLOR_TEXT2,
            bg=BG_PANEL,
        ).pack(side=tk.LEFT, padx=4, pady=4)

        tk.Label(
            status_frame,
            text="ZOOM G1 / G1X FOUR (TMS320C6745 @ 300MHz)",
            font=("Consolas", 8, "bold"),
            fg=COLOR_TEXT1,
            bg=BG_PANEL,
        ).pack(side=tk.LEFT)

        self.port_status_lbl = tk.Label(
            status_frame,
            text="[● SCANNING PORTS]",
            font=("Consolas", 8, "bold"),
            fg=COLOR_AMBER,
            bg=BG_PANEL,
        )
        self.port_status_lbl.pack(side=tk.RIGHT, padx=8)

        # 3. Payloads Box (Baked-in vs Custom)
        self.payload_box = tk.LabelFrame(
            self.root,
            text=" [ COMET FLOWER BAKED-IN FIRMWARE PAYLOAD (v0.34.9) ] ",
            font=("Consolas", 8, "bold"),
            fg=COLOR_AMBER,
            bg=BG_PANEL,
            bd=1,
            relief=tk.SOLID,
        )
        self.payload_box.pack(fill=tk.X, padx=14, pady=6)

        # Baked-in badges
        self.baked_info_frame = tk.Frame(self.payload_box, bg=BG_PANEL)
        self.baked_info_frame.pack(fill=tk.X, padx=8, pady=4)

        tk.Label(
            self.baked_info_frame,
            text="● FIRMWARE  : Comet Flower Kernel v0.34.9 (523 KB) [Violet Muff 12nF, CFM Pre, 340% Gate]",
            font=("Consolas", 8, "bold"),
            fg=COLOR_GREEN,
            bg=BG_PANEL,
            anchor="w",
        ).pack(fill=tk.X, pady=1)

        tk.Label(
            self.baked_info_frame,
            text="● FILESYSTEM: Comet Flower Effect Suite (3.1 MB) [Circuit-Exact Models & Custom Icons]",
            font=("Consolas", 8, "bold"),
            fg=COLOR_GREEN,
            bg=BG_PANEL,
            anchor="w",
        ).pack(fill=tk.X, pady=1)

        tk.Label(
            self.baked_info_frame,
            text="● PRESETS   : Comet Flower Presets & Bloom Splash (45 KB) [0x028000 Partition]",
            font=("Consolas", 8, "bold"),
            fg=COLOR_GREEN,
            bg=BG_PANEL,
            anchor="w",
        ).pack(fill=tk.X, pady=1)

        # Override toggle
        self.override_var = tk.BooleanVar(value=False)
        override_chk = tk.Checkbutton(
            self.payload_box,
            text="Override with custom external files",
            variable=self.override_var,
            font=("Consolas", 8),
            fg=COLOR_TEXT2,
            bg=BG_PANEL,
            selectcolor=BG_WELL,
            activebackground=BG_PANEL,
            activeforeground=COLOR_AMBER,
            command=self._toggle_override_ui,
        )
        override_chk.pack(anchor="w", padx=6, pady=(4, 2))

        # Custom inputs container (initially hidden)
        self.custom_frame = tk.Frame(self.payload_box, bg=BG_PANEL)

        self.fw_var = tk.StringVar(value=str(self.baked_fw) if self.baked_fw else "")
        self._create_path_row(self.custom_frame, "0x033000 MAIN FW :", self.fw_var, "*.bin")

        self.fs_var = tk.StringVar(value=str(self.baked_fs) if self.baked_fs else "")
        self._create_path_row(self.custom_frame, "0x102000 EFFECT FS:", self.fs_var, "*.bin")

        self.preset_var = tk.StringVar(value=str(self.baked_presets) if self.baked_presets else "")
        self._create_path_row(self.custom_frame, "0x028000 PRESETS  :", self.preset_var, "*.bin")

        # 4. Action Buttons Bar
        btn_frame = tk.Frame(self.root, bg=BG_DARK)
        btn_frame.pack(fill=tk.X, padx=14, pady=6)

        self.flash_btn = tk.Button(
            btn_frame,
            text="⚡ FLASH TARGET",
            font=("Consolas", 10, "bold"),
            bg=COLOR_AMBER,
            fg=BG_DARK,
            activebackground="#ffd185",
            activeforeground=BG_DARK,
            bd=0,
            padx=16,
            pady=6,
            cursor="hand2",
            command=self._on_flash_click,
        )
        self.flash_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.dryrun_btn = tk.Button(
            btn_frame,
            text="🔍 DRY RUN",
            font=("Consolas", 9, "bold"),
            bg=BG_PANEL,
            fg=COLOR_CYAN,
            activebackground=COLOR_BORDER,
            activeforeground=COLOR_CYAN,
            bd=1,
            relief=tk.SOLID,
            padx=12,
            pady=6,
            cursor="hand2",
            command=self._on_dryrun_click,
        )
        self.dryrun_btn.pack(side=tk.LEFT, padx=4)

        self.rescan_btn = tk.Button(
            btn_frame,
            text="🔄 RESCAN",
            font=("Consolas", 9, "bold"),
            bg=BG_PANEL,
            fg=COLOR_TEXT2,
            activebackground=COLOR_BORDER,
            activeforeground=COLOR_TEXT1,
            bd=1,
            relief=tk.SOLID,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._rescan_ports,
        )
        self.rescan_btn.pack(side=tk.LEFT, padx=4)

        self.music_btn = tk.Button(
            btn_frame,
            text="♫ MUSIC: OFF",
            font=("Consolas", 9, "bold"),
            bg=BG_PANEL,
            fg=COLOR_TEXT3,
            activebackground=COLOR_BORDER,
            activeforeground=COLOR_CYAN,
            bd=1,
            relief=tk.SOLID,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._toggle_music,
        )
        self.music_btn.pack(side=tk.RIGHT, padx=4)

        self.nfo_btn = tk.Button(
            btn_frame,
            text="ℹ NFO",
            font=("Consolas", 9, "bold"),
            bg=BG_PANEL,
            fg=COLOR_MAGENTA,
            activebackground=COLOR_BORDER,
            activeforeground=COLOR_MAGENTA,
            bd=1,
            relief=tk.SOLID,
            padx=10,
            pady=6,
            cursor="hand2",
            command=self._show_nfo,
        )
        self.nfo_btn.pack(side=tk.RIGHT, padx=4)

        # 5. Progress Display
        prog_frame = tk.Frame(self.root, bg=BG_DARK)
        prog_frame.pack(fill=tk.X, padx=14, pady=(2, 4))

        self.prog_label = tk.Label(
            prog_frame,
            text="STANDBY: Ready for transmission.",
            font=("Consolas", 8),
            fg=COLOR_TEXT2,
            bg=BG_DARK,
            anchor="w",
        )
        self.prog_label.pack(fill=tk.X)

        self.prog_bar_lbl = tk.Label(
            prog_frame,
            text="[" + "░" * 50 + "] 0.0%",
            font=("Consolas", 9, "bold"),
            fg=COLOR_CYAN,
            bg=BG_DARK,
            anchor="w",
        )
        self.prog_bar_lbl.pack(fill=tk.X, pady=(2, 0))

        # 6. CRT Terminal Well
        term_frame = tk.LabelFrame(
            self.root,
            text=" [ TELEMETRY // WINMM MIDI WIRE LOG ] ",
            font=("Consolas", 8, "bold"),
            fg=COLOR_GREEN,
            bg=BG_DARK,
            bd=1,
            relief=tk.SOLID,
        )
        term_frame.pack(fill=tk.BOTH, expand=True, padx=14, pady=4)

        self.term_text = tk.Text(
            term_frame,
            bg=BG_WELL,
            fg=COLOR_GREEN,
            insertbackground=COLOR_GREEN,
            font=("Consolas", 9),
            bd=0,
            padx=8,
            pady=8,
            wrap=tk.WORD,
        )
        self.term_text.pack(fill=tk.BOTH, expand=True)

        # 7. Bottom Marquee Scroller
        marquee_frame = tk.Frame(self.root, bg=BG_WELL, bd=1, relief=tk.SOLID)
        marquee_frame.pack(fill=tk.X, padx=14, pady=(4, 8))

        self.marquee_lbl = tk.Label(
            marquee_frame,
            text="",
            font=("Consolas", 8, "bold"),
            fg=COLOR_AMBER,
            bg=BG_WELL,
            anchor="w",
        )
        self.marquee_lbl.pack(fill=tk.X, padx=4, pady=2)

        # Initial logging
        self._log("[+] COMET FLOWER UNLEASHED FLASHER v1.0 [RAZOR 1911 STYLE]")
        self._log("[+] VirtualPedalBoardEngine Modeler Palette Active.")
        self._log("[+] Comfortably Numb Solo 2 Music Synthesizer Engine Ready.")
        self._log("[+] Baked-in Payload: Comet Flower Firmware v0.34.9.")
        self._rescan_ports()

    def _toggle_override_ui(self):
        if self.override_var.get():
            self.custom_frame.pack(fill=tk.X, padx=4, pady=4)
        else:
            self.custom_frame.pack_forget()

    def _create_path_row(self, parent, label_text, var, filter_ext):
        row = tk.Frame(parent, bg=BG_PANEL)
        row.pack(fill=tk.X, padx=6, pady=3)

        lbl = tk.Label(
            row,
            text=label_text,
            font=("Consolas", 8, "bold"),
            fg=COLOR_TEXT1,
            bg=BG_PANEL,
            width=18,
            anchor="w",
        )
        lbl.pack(side=tk.LEFT)

        entry = tk.Entry(
            row,
            textvariable=var,
            font=("Consolas", 8),
            bg=BG_WELL,
            fg=COLOR_CYAN,
            insertbackground=COLOR_CYAN,
            bd=1,
            relief=tk.SOLID,
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        def browse():
            p = filedialog.askopenfilename(
                title=f"Select {label_text}",
                filetypes=[("Binary files", filter_ext), ("All files", "*.*")],
                initialdir=str(REPO_ROOT / "build"),
            )
            if p:
                var.set(p)

        btn = tk.Button(
            row,
            text="...",
            font=("Consolas", 8, "bold"),
            bg=BG_PANEL,
            fg=COLOR_TEXT2,
            bd=1,
            relief=tk.SOLID,
            command=browse,
            width=3,
        )
        btn.pack(side=tk.RIGHT)

    def _rescan_ports(self):
        try:
            import mido

            inputs = mido.get_input_names()
            found = False
            for p in inputs:
                if any(p.startswith(prefix) for prefix in flasher.DEFAULT_PORT_PREFIXES):
                    found = True
                    self.port_status_lbl.config(
                        text=f"[● DETECTED: {p}]",
                        fg=COLOR_GREEN,
                    )
                    self._log(f"[+] Found update-mode port: {p}")
                    break
            if not found:
                self.port_status_lbl.config(
                    text="[● NO PEDAL DETECTED]",
                    fg=COLOR_RED,
                )
                self._log("[!] No pedal port detected. Connect USB while holding both footswitches.")
        except Exception as e:
            self.port_status_lbl.config(text="[● MIDI ERROR]", fg=COLOR_RED)
            self._log(f"[!] Port scan error: {e}")

    def _toggle_music(self):
        playing = self.music.toggle()
        if playing:
            self.music_btn.config(text="♫ MUSIC: ON", fg=COLOR_CYAN)
            self._log("[♫] Playing Comfortably Numb Solo 2 Chiptune (Bm - A - G - Em).")
        else:
            self.music_btn.config(text="♫ MUSIC: OFF", fg=COLOR_TEXT3)
            self._log("[♫] Music stopped.")

    def _show_nfo(self):
        nfo_win = tk.Toplevel(self.root)
        nfo_win.title("NFO // Comet Flower Labs 1911")
        nfo_win.geometry("640x520")
        nfo_win.configure(bg=BG_DARK)

        txt = tk.Text(
            nfo_win,
            bg=BG_WELL,
            fg=COLOR_TEXT1,
            font=("Consolas", 8),
            bd=0,
            padx=10,
            pady=10,
        )
        txt.pack(fill=tk.BOTH, expand=True)
        txt.insert(tk.END, NFO_TEXT.strip("\n"))
        txt.config(state=tk.DISABLED)

    def _start_marquee(self):
        self._marquee_idx = 0
        self._update_marquee()

    def _update_marquee(self):
        display_len = 90
        text = SCROLLER_MESSAGE
        idx = self._marquee_idx % len(text)
        view = (text + text)[idx : idx + display_len]
        self.marquee_lbl.config(text=view)
        self._marquee_idx = (self._marquee_idx + 1) % len(text)
        self.root.after(100, self._update_marquee)

    def _log(self, text: str):
        self.term_text.insert(tk.END, text + "\n")
        self.term_text.see(tk.END)

    def _update_progress(self, desc: str, op: str, frac: float):
        percent = frac * 100
        bars = int(frac * 50)
        bar_str = "[" + "█" * bars + "░" * (50 - bars) + f"] {percent:5.1f}%"
        self.root.after(0, lambda: self._apply_progress(desc, op, bar_str))

    def _apply_progress(self, desc: str, op: str, bar_str: str):
        self.prog_label.config(text=f"ACTIVE: {desc} ({op.upper()})")
        self.prog_bar_lbl.config(text=bar_str)

    def _get_active_payload_paths(self):
        if not self.override_var.get():
            return self.baked_fw, self.baked_fs, self.baked_presets
        fw = Path(self.fw_var.get()) if self.fw_var.get() else None
        fs = Path(self.fs_var.get()) if self.fs_var.get() else None
        pr = Path(self.preset_var.get()) if self.preset_var.get() else None
        return fw, fs, pr

    def _on_dryrun_click(self):
        fw, fs, pr = self._get_active_payload_paths()

        self._log("\n--- [ DRY RUN VALIDATION ] ---")
        try:
            stages = flasher.plan_stages_from_files(firmware_path=fw, fs_image_path=fs, presets_path=pr)
            for s in stages:
                flasher.check_stage_safety(s)
                sz = f"size {len(s.data):,} B" if s.data else f"size 0x{s.size:X}"
                self._log(f"  [OK] {s.description:28s} : {s.op_name.upper()} 0x{s.addr:06X} ({sz})")
            self._log("[+] All stages validated and safety certified. Safe to flash.")
            messagebox.showinfo("Dry Run Passed", f"Preflight passed: {len(stages)} stage(s) approved!")
        except Exception as e:
            self._log(f"[!] Validation failed: {e}")
            messagebox.showerror("Validation Error", str(e))

    def _on_flash_click(self):
        if self.is_flashing:
            return

        fw, fs, pr = self._get_active_payload_paths()

        if not any([fw, fs, pr]):
            messagebox.showwarning("No Files", "Please select at least one file to flash.")
            return

        try:
            stages = flasher.plan_stages_from_files(firmware_path=fw, fs_image_path=fs, presets_path=pr)
            for s in stages:
                flasher.check_stage_safety(s)
        except Exception as e:
            messagebox.showerror("Safety Error", f"Cannot flash: {e}")
            return

        source_desc = "BAKED-IN Comet Flower Firmware v0.34.9" if not self.override_var.get() else "Custom External Files"
        confirm = messagebox.askyesno(
            "Confirm Flash",
            f"Ready to flash Comet Flower Firmware ({source_desc}) across {len(stages)} stages.\n\n"
            "Ensure the pedal is in UPDATE MODE (hold both footswitches while connecting USB power).\n"
            "DO NOT disconnect USB during transmission.\n\n"
            "Proceed with flash?",
        )
        if not confirm:
            return

        self.is_flashing = True
        self.flash_btn.config(state=tk.DISABLED, bg=BG_PANEL, fg=COLOR_TEXT3)
        self.dryrun_btn.config(state=tk.DISABLED)

        t = threading.Thread(target=self._run_flash_thread, args=(stages,), daemon=True)
        t.start()

    def _run_flash_thread(self, stages):
        session = flasher.FlasherSession(verbose=False, log_fn=lambda m: self.root.after(0, lambda: self._log(m)))
        try:
            session.connect()
            session.run_stages(
                stages,
                progress_cb=lambda desc, op, frac: self._update_progress(desc, op, frac),
            )
            self.root.after(0, lambda: messagebox.showinfo("Success", "Flashing completed successfully!"))
        except Exception as e:
            self.root.after(0, lambda: self._log(f"[!] FLASH ERROR: {e}"))
            self.root.after(0, lambda: messagebox.showerror("Flash Error", str(e)))
        finally:
            session.close()
            self.is_flashing = False
            self.root.after(0, self._restore_buttons)

    def _restore_buttons(self):
        self.flash_btn.config(state=tk.NORMAL, bg=COLOR_AMBER, fg=BG_DARK)
        self.dryrun_btn.config(state=tk.NORMAL)
        self.prog_label.config(text="STANDBY: Flash complete or idle.")

    def _on_close(self):
        self.music.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = FlasherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
