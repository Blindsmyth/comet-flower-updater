"""Comet Flower Music Studio (Sony ACID Pro Keygen / Digital Insanity Style).

An interactive chiptune tracker & music generator styled after the classic
Sony ACID Pro 4.0 - 7.0 Keygens by Digital Insanity (DI).

Features:
- Authentic Digital Insanity keygen UI: steel-blue metallic theme, product selector,
  beveled readouts, and classic action buttons.
- 4-bar / 16-step chiptune tracker & chord sequencer.
- Real-time synthesizer playback with live playhead indicator.
- Sound patch selectors (Square wave, Sawtooth, Synth Bass, Lead).
- "Save to Updater": Directly saves your custom track into the Comet Flower Updater!
- Presets: Classic Keygen Anthem, Outro Solo Chords, Cyberpunk Minor, Demodrive.
"""

import json
from pathlib import Path
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
PAYLOAD_DIR = REPO_ROOT / "tools" / "payload"

# --- Classic Sony ACID / Digital Insanity Keygen Palette ---
DI_BG_DARK = "#12151b"
DI_BG_PANEL = "#1a1f27"
DI_BG_WELL = "#0a0c10"
DI_BORDER = "#2c3545"
DI_BORDER_BEVEL = "#3d495c"
DI_TEXT_WHITE = "#e8ecf2"
DI_TEXT_MUTED = "#8894a6"
DI_GREEN_KEYGEN = "#00ff66"
DI_CYAN_ACCENT = "#00d4ff"
DI_AMBER_ACCENT = "#ffaa00"
DI_BTN_BG = "#242c38"
DI_BTN_ACTIVE = "#313b4c"

# Standard MIDI Note Numbers
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

CHORD_DEFINITIONS: Dict[str, Tuple[int, List[int]]] = {
    # Name: (root_midi_bass, [root_mid, 3rd_mid, 5th_mid])
    "Bm": (47, [59, 62, 66]),
    "A": (45, [57, 61, 64]),
    "G": (43, [55, 59, 62]),
    "Em": (40, [52, 55, 59]),
    "Am": (45, [57, 60, 64]),
    "F": (41, [53, 57, 60]),
    "C": (48, [60, 64, 67]),
    "Dm": (50, [62, 65, 69]),
    "E": (40, [52, 56, 59]),
    "D": (50, [62, 66, 69]),
}

PRESETS = {
    "Classic Outro (Bm - A - G - Em)": {
        "bpm": 125,
        "lead_prog": 80,
        "bass_prog": 38,
        "chords": ["Bm", "A", "G", "Em"],
        "pattern": "Arp & Lead",
    },
    "Demoscene Anthem (Am - F - C - G)": {
        "bpm": 130,
        "lead_prog": 80,
        "bass_prog": 39,
        "chords": ["Am", "F", "C", "G"],
        "pattern": "Fast Arpeggio",
    },
    "Cyberpunk Drive (Dm - Bb - F - C)": {
        "bpm": 136,
        "lead_prog": 81,
        "bass_prog": 38,
        "chords": ["Dm", "G", "C", "Am"],
        "pattern": "High Melodic",
    },
}


class MusicMakerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Comet Flower Music Studio - Sony ACID Keygen Style")
        self.root.geometry("720x680")
        self.root.minsize(680, 640)
        self.root.configure(bg=DI_BG_DARK)

        self._outport = None
        self._is_playing = False
        self._stop_event = threading.Event()
        self._play_thread: Optional[threading.Thread] = None
        self.active_step = -1

        self._init_midi()
        self._build_ui()
        self._load_preset("Classic Outro (Bm - A - G - Em)")

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _init_midi(self):
        try:
            import mido

            outs = mido.get_output_names()
            target = None
            for o in outs:
                if any(k in o.lower() for k in ("wavetable", "synth", "microsoft")):
                    target = o
                    break
            self.midi_port_name = target or (outs[0] if outs else None)
        except Exception:
            self.midi_port_name = None

    def _build_ui(self):
        # 1. Top Sony ACID / Digital Insanity Header Banner
        top_banner = tk.Frame(self.root, bg=DI_BG_PANEL, bd=1, relief=tk.SOLID, highlightbackground=DI_BORDER)
        top_banner.pack(fill=tk.X, padx=10, pady=(10, 4))

        tk.Label(
            top_banner,
            text="DIGITAL INSANITY // COMET FLOWER MUSIC ENGINE",
            font=("Lucida Console", 10, "bold"),
            fg=DI_CYAN_ACCENT,
            bg=DI_BG_PANEL,
            anchor="w",
        ).pack(fill=tk.X, padx=8, pady=(6, 2))

        tk.Label(
            top_banner,
            text="SONY ACID PRO CHIPTUNE GENERATOR & TRACKER v1.0",
            font=("Lucida Console", 8),
            fg=DI_TEXT_MUTED,
            bg=DI_BG_PANEL,
            anchor="w",
        ).pack(fill=tk.X, padx=8, pady=(0, 6))

        # 2. Main Inset Container (Classic Keygen Box)
        main_box = tk.LabelFrame(
            self.root,
            text=" [ GENERATOR CONTROL & PRESETS ] ",
            font=("Lucida Console", 8, "bold"),
            fg=DI_AMBER_ACCENT,
            bg=DI_BG_PANEL,
            bd=1,
            relief=tk.SOLID,
        )
        main_box.pack(fill=tk.X, padx=10, pady=4)

        # Product Name Dropdown (Signature DI Look)
        row_prod = tk.Frame(main_box, bg=DI_BG_PANEL)
        row_prod.pack(fill=tk.X, padx=8, pady=4)

        tk.Label(
            row_prod,
            text="Product / Preset:",
            font=("Lucida Console", 8, "bold"),
            fg=DI_TEXT_WHITE,
            bg=DI_BG_PANEL,
            width=18,
            anchor="w",
        ).pack(side=tk.LEFT)

        self.preset_combo = ttk.Combobox(
            row_prod,
            values=list(PRESETS.keys()),
            state="readonly",
            font=("Lucida Console", 8),
        )
        self.preset_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.preset_combo.bind("<<ComboboxSelected>>", lambda e: self._load_preset(self.preset_combo.get()))

        # Machine ID / Target Synth
        row_mid = tk.Frame(main_box, bg=DI_BG_PANEL)
        row_mid.pack(fill=tk.X, padx=8, pady=4)

        tk.Label(
            row_mid,
            text="Output Device   :",
            font=("Lucida Console", 8, "bold"),
            fg=DI_TEXT_WHITE,
            bg=DI_BG_PANEL,
            width=18,
            anchor="w",
        ).pack(side=tk.LEFT)

        mid_entry = tk.Entry(
            row_mid,
            font=("Lucida Console", 8),
            bg=DI_BG_WELL,
            fg=DI_GREEN_KEYGEN,
            bd=1,
            relief=tk.SOLID,
        )
        mid_entry.insert(0, self.midi_port_name or "Microsoft GS Wavetable Synth")
        mid_entry.config(state="readonly")
        mid_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        # 3. Synth Sound Settings Strip
        synth_strip = tk.Frame(main_box, bg=DI_BG_PANEL)
        synth_strip.pack(fill=tk.X, padx=8, pady=4)

        tk.Label(synth_strip, text="Lead Sound:", font=("Lucida Console", 8), fg=DI_TEXT_MUTED, bg=DI_BG_PANEL).pack(side=tk.LEFT)
        self.lead_prog_var = tk.IntVar(value=80)
        lead_combo = ttk.Combobox(
            synth_strip,
            values=["Square Lead (80)", "Saw Lead (81)", "Calliope (82)", "Chiffer (83)", "Charang (84)"],
            state="readonly",
            width=16,
            font=("Lucida Console", 8),
        )
        lead_combo.current(0)
        lead_combo.pack(side=tk.LEFT, padx=(4, 12))
        lead_combo.bind("<<ComboboxSelected>>", lambda e: self.lead_prog_var.set(80 + lead_combo.current()))

        tk.Label(synth_strip, text="Bass Sound:", font=("Lucida Console", 8), fg=DI_TEXT_MUTED, bg=DI_BG_PANEL).pack(side=tk.LEFT)
        self.bass_prog_var = tk.IntVar(value=38)
        bass_combo = ttk.Combobox(
            synth_strip,
            values=["Synth Bass 1 (38)", "Synth Bass 2 (39)", "Slap Bass (36)", "Electric Bass (33)"],
            state="readonly",
            width=16,
            font=("Lucida Console", 8),
        )
        bass_combo.current(0)
        bass_combo.pack(side=tk.LEFT, padx=(4, 12))
        bass_combo.bind("<<ComboboxSelected>>", lambda e: self.bass_prog_var.set([38, 39, 36, 33][bass_combo.current()]))

        tk.Label(synth_strip, text="BPM:", font=("Lucida Console", 8), fg=DI_TEXT_MUTED, bg=DI_BG_PANEL).pack(side=tk.LEFT)
        self.bpm_var = tk.IntVar(value=125)
        bpm_spin = tk.Spinbox(synth_strip, from_=80, to=160, textvariable=self.bpm_var, width=5, font=("Lucida Console", 8))
        bpm_spin.pack(side=tk.LEFT, padx=4)

        # 4. Chord Progression Bars Section
        chord_box = tk.LabelFrame(
            self.root,
            text=" [ 4-BAR CHORD PROGRESSION SEQUENCE ] ",
            font=("Lucida Console", 8, "bold"),
            fg=DI_CYAN_ACCENT,
            bg=DI_BG_PANEL,
            bd=1,
            relief=tk.SOLID,
        )
        chord_box.pack(fill=tk.X, padx=10, pady=4)

        self.chord_vars = [tk.StringVar(value="Bm"), tk.StringVar(value="A"), tk.StringVar(value="G"), tk.StringVar(value="Em")]
        chord_row = tk.Frame(chord_box, bg=DI_BG_PANEL)
        chord_row.pack(fill=tk.X, padx=8, pady=6)

        for i in range(4):
            bar_frame = tk.Frame(chord_row, bg=DI_BG_PANEL, bd=1, relief=tk.SOLID, highlightbackground=DI_BORDER)
            bar_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

            tk.Label(
                bar_frame,
                text=f"BAR {i + 1}",
                font=("Lucida Console", 8, "bold"),
                fg=DI_AMBER_ACCENT,
                bg=DI_BG_PANEL,
            ).pack(pady=(2, 0))

            cb = ttk.Combobox(
                bar_frame,
                values=list(CHORD_DEFINITIONS.keys()),
                textvariable=self.chord_vars[i],
                state="readonly",
                width=6,
                font=("Lucida Console", 9, "bold"),
            )
            cb.pack(pady=4)

        # 5. Step Visualizer / Sequencer Grid
        seq_box = tk.LabelFrame(
            self.root,
            text=" [ 16-STEP CHIPTUNE PLAYHEAD ] ",
            font=("Lucida Console", 8, "bold"),
            fg=DI_GREEN_KEYGEN,
            bg=DI_BG_PANEL,
            bd=1,
            relief=tk.SOLID,
        )
        seq_box.pack(fill=tk.X, padx=10, pady=4)

        grid_row = tk.Frame(seq_box, bg=DI_BG_WELL, bd=1, relief=tk.SOLID)
        grid_row.pack(fill=tk.X, padx=8, pady=6)

        self.step_labels: List[tk.Label] = []
        for s in range(16):
            lbl = tk.Label(
                grid_row,
                text=f"{s + 1:02d}",
                font=("Lucida Console", 7, "bold"),
                fg=DI_TEXT_MUTED,
                bg=DI_BG_WELL,
                width=3,
                height=2,
                bd=1,
                relief=tk.FLAT,
            )
            lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=2)
            self.step_labels.append(lbl)

        # 6. Action Controls Bar (Classic DI Style Buttons)
        ctrl_frame = tk.Frame(self.root, bg=DI_BG_DARK)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=8)

        self.play_btn = tk.Button(
            ctrl_frame,
            text="▶ PLAY",
            font=("Lucida Console", 9, "bold"),
            bg=DI_GREEN_KEYGEN,
            fg=DI_BG_DARK,
            activebackground="#33ff88",
            activeforeground=DI_BG_DARK,
            bd=1,
            relief=tk.RAISED,
            padx=14,
            pady=4,
            cursor="hand2",
            command=self._toggle_playback,
        )
        self.play_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.save_btn = tk.Button(
            ctrl_frame,
            text="💾 SAVE TO UPDATER",
            font=("Lucida Console", 9, "bold"),
            bg=DI_AMBER_ACCENT,
            fg=DI_BG_DARK,
            activebackground="#ffcc44",
            activeforeground=DI_BG_DARK,
            bd=1,
            relief=tk.RAISED,
            padx=14,
            pady=4,
            cursor="hand2",
            command=self._save_to_updater,
        )
        self.save_btn.pack(side=tk.LEFT, padx=6)

        # 7. Telemetry / Status Box
        log_box = tk.LabelFrame(
            self.root,
            text=" [ ACID TRACKER LOG ] ",
            font=("Lucida Console", 8, "bold"),
            fg=DI_TEXT_MUTED,
            bg=DI_BG_DARK,
            bd=1,
            relief=tk.SOLID,
        )
        log_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=(2, 8))

        self.log_text = tk.Text(
            log_box,
            bg=DI_BG_WELL,
            fg=DI_GREEN_KEYGEN,
            font=("Lucida Console", 8),
            bd=0,
            padx=8,
            pady=6,
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self._log("[+] Digital Insanity / Sony ACID Keygen Music Studio Loaded.")
        self._log(f"[+] MIDI Synth Connected: {self.midi_port_name or 'Default'}")
        self._log("[+] Select chords, adjust BPM, and click [▶ PLAY] to preview.")

    def _log(self, text: str):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def _load_preset(self, name: str):
        p = PRESETS.get(name)
        if not p:
            return
        self.bpm_var.set(p["bpm"])
        self.lead_prog_var.set(p["lead_prog"])
        self.bass_prog_var.set(p["bass_prog"])
        for i in range(4):
            self.chord_vars[i].set(p["chords"][i])
        self._log(f"[+] Loaded preset: {name} ({' -> '.join(p['chords'])})")

    def _toggle_playback(self):
        if self._is_playing:
            self._stop_playback()
        else:
            self._start_playback()

    def _start_playback(self):
        if self._is_playing:
            return
        self._stop_event.clear()
        self._is_playing = True
        self.play_btn.config(text="■ STOP", bg="#ff3344", fg="#ffffff")
        self._play_thread = threading.Thread(target=self._synth_loop, daemon=True)
        self._play_thread.start()
        self._log("[♫] Playback started.")

    def _stop_playback(self):
        if not self._is_playing:
            return
        self._stop_event.set()
        self._is_playing = False
        self.play_btn.config(text="▶ PLAY", bg=DI_GREEN_KEYGEN, fg=DI_BG_DARK)
        self._reset_step_lights()
        self._log("[♫] Playback stopped.")

    def _reset_step_lights(self):
        for lbl in self.step_labels:
            lbl.config(bg=DI_BG_WELL, fg=DI_TEXT_MUTED)

    def _synth_loop(self):
        import mido

        try:
            outport = mido.open_output(self.midi_port_name)
            step_dur = 60.0 / (self.bpm_var.get() * 4)

            outport.send(mido.Message("program_change", channel=0, program=self.lead_prog_var.get()))
            outport.send(mido.Message("program_change", channel=1, program=self.bass_prog_var.get()))

            bass_hits = [1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0]

            while not self._stop_event.is_set():
                for bar_idx in range(4):
                    chord_name = self.chord_vars[bar_idx].get()
                    root_bass, triad = CHORD_DEFINITIONS.get(chord_name, (45, [57, 60, 64]))
                    # Generate 16-step arpeggio pattern for this chord
                    r, m3, p5 = triad
                    pattern_lead = [r, m3, p5, r + 12, p5, m3, r, m3, p5, r + 12, r + 15, r + 14, r + 12, p5 + 12, p5, m3]

                    for s in range(16):
                        if self._stop_event.is_set():
                            break

                        self.root.after(0, lambda st=s: self._highlight_step(st))

                        lead_n = pattern_lead[s]
                        bass_n = root_bass if bass_hits[s] else None

                        if bass_n:
                            outport.send(mido.Message("note_on", channel=1, note=bass_n, velocity=100))
                        outport.send(mido.Message("note_on", channel=0, note=lead_n, velocity=88))

                        time.sleep(step_dur * 0.82)

                        if bass_n:
                            outport.send(mido.Message("note_off", channel=1, note=bass_n))
                        outport.send(mido.Message("note_off", channel=0, note=lead_n))

                        time.sleep(step_dur * 0.18)

            # Silence on stop
            for ch in (0, 1):
                outport.send(mido.Message("control_change", channel=ch, control=120, value=0))
                outport.send(mido.Message("control_change", channel=ch, control=123, value=0))
            outport.close()
        except Exception as e:
            self.root.after(0, lambda err=e: self._log(f"[!] Synth error: {err}"))
        finally:
            self.root.after(0, self._reset_step_lights)

    def _highlight_step(self, step_idx: int):
        for i, lbl in enumerate(self.step_labels):
            if i == step_idx:
                lbl.config(bg=DI_CYAN_ACCENT, fg=DI_BG_DARK)
            else:
                lbl.config(bg=DI_BG_WELL, fg=DI_TEXT_MUTED)

    def _save_to_updater(self):
        PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
        track_path = PAYLOAD_DIR / "music_track.json"

        bars_data = []
        bass_hits = [1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0]

        for i in range(4):
            chord_name = self.chord_vars[i].get()
            root_bass, triad = CHORD_DEFINITIONS.get(chord_name, (45, [57, 60, 64]))
            r, m3, p5 = triad
            # 16-step arpeggio pattern
            notes = [r, m3, p5, r + 12, p5, m3, r, m3, p5, r + 12, r + 15, r + 14, r + 12, p5 + 12, p5, m3]
            bars_data.append({"chord": chord_name, "root": root_bass, "notes": notes})

        # Add second cycle (melodic variation)
        for i in range(4):
            chord_name = self.chord_vars[i].get()
            root_bass, triad = CHORD_DEFINITIONS.get(chord_name, (45, [57, 60, 64]))
            r, m3, p5 = triad
            notes = [r + 12, r + 12, r + 12, r + 15, r + 15, r + 15, r + 17, r + 17, r + 15, r + 15, r + 12, r + 12, p5 + 12, r + 12, r + 15, r + 12]
            bars_data.append({"chord": chord_name, "root": root_bass, "notes": notes})

        step_dur = 60.0 / (self.bpm_var.get() * 4)

        data = {
            "title": "Custom User Chiptune Anthem",
            "bpm": self.bpm_var.get(),
            "step_duration": step_dur,
            "lead_program": self.lead_prog_var.get(),
            "bass_program": self.bass_prog_var.get(),
            "bars": bars_data,
        }

        track_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._log(f"[+] Saved track to: {track_path}")
        messagebox.showinfo(
            "Saved to Updater",
            "Your custom music track has been saved!\n\n"
            "The Comet Flower Updater will now play your custom composition.",
        )

    def _on_close(self):
        self._stop_playback()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = MusicMakerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
