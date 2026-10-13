#!/usr/bin/env python3
"""Receive-only MIDI monitor with nameable controls for Zoom G1X Four controller mode.

  python tools/cf_midi_monitor.py

Monitors Control Change (CC) messages from the G1X Four custom controller firmware,
displays a live table for the 17 physical controls (footswitches, buttons, knobs,
expression pedal), supports naming controls, Learn mode, CSV export, and offline simulation.

SAFETY RULE: Receive-only. This application never opens an output port and never sends MIDI messages.
"""

import csv
from datetime import datetime
import json
from pathlib import Path
from queue import Empty, Queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Any, Dict, Optional

try:
    import mido
except ImportError:
    mido = None

try:
    from tools.cf_midi_mapping import ControlEvent, ControlKind, MidiStateManager
except ModuleNotFoundError as exc:
    if exc.name != "tools":
        raise
    # Running `python tools/cf_midi_monitor.py` puts tools/, not its parent,
    # on sys.path. Keep the documented direct launch working.
    from cf_midi_mapping import ControlEvent, ControlKind, MidiStateManager

PORT_PREFIX = "ZOOM G"
DEFAULT_NAMES_PATH = Path(__file__).resolve().parents[1] / "build" / "loader" / "midi_names.json"


class MidiMonitorApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Comet Flower ZG1X4 - MIDI Controller Monitor")
        self.root.geometry("960x700")
        self.root.minsize(800, 560)

        self.state_mgr = MidiStateManager()
        self.input_port: Optional[Any] = None
        self.listen_thread: Optional[threading.Thread] = None
        self.stop_listening = threading.Event()
        self.incoming = Queue()
        self.highlight_timers: Dict[str, str] = {}

        # Load existing names if present
        if DEFAULT_NAMES_PATH.is_file():
            self.state_mgr.load_names(DEFAULT_NAMES_PATH)

        self._build_ui()
        self._refresh_ports()
        self.incoming_timer = self.root.after(10, self._poll_incoming)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # 1. Top Bar: Port selector and controls
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="MIDI In Port:").pack(side=tk.LEFT, padx=(0, 5))
        self.port_combo = ttk.Combobox(top_frame, width=35, state="readonly")
        self.port_combo.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_refresh = ttk.Button(top_frame, text="Refresh", command=self._refresh_ports)
        self.btn_refresh.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_connect = ttk.Button(top_frame, text="Connect", command=self._toggle_connection)
        self.btn_connect.pack(side=tk.LEFT, padx=(0, 15))

        self.btn_simulate = ttk.Button(top_frame, text="Simulate Test", command=self._run_simulation)
        self.btn_simulate.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_save_names = ttk.Button(top_frame, text="Save Names", command=self._save_names)
        self.btn_save_names.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_export_csv = ttk.Button(top_frame, text="Export CSV", command=self._export_csv)
        self.btn_export_csv.pack(side=tk.LEFT, padx=(0, 5))

        # 2. Main Table: 17 Controls
        table_frame = ttk.LabelFrame(self.root, text="Controls (17 Physical Inputs)", padding=5)
        table_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        cols = ("cid", "cc", "name", "state", "bar", "pin", "action")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=17)
        self.tree.heading("cid", text="ID")
        self.tree.heading("cc", text="CC")
        self.tree.heading("name", text="Assigned Name (Double Click to Edit)")
        self.tree.heading("state", text="Live State")
        self.tree.heading("bar", text="Level")
        self.tree.heading("pin", text="Hardware Mapping")
        self.tree.heading("action", text="Learn")

        self.tree.column("cid", width=60, anchor=tk.CENTER)
        self.tree.column("cc", width=50, anchor=tk.CENTER)
        self.tree.column("name", width=260, anchor=tk.W)
        self.tree.column("state", width=110, anchor=tk.CENTER)
        self.tree.column("bar", width=120, anchor=tk.W)
        self.tree.column("pin", width=200, anchor=tk.W)
        self.tree.column("action", width=80, anchor=tk.CENTER)

        tree_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure("active", background="#d4edda")
        self.tree.tag_configure("normal", background="#ffffff")
        self.tree.tag_configure("learning", background="#fff3cd")

        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.tree.bind("<ButtonRelease-1>", self._on_tree_click)

        # Populate tree rows
        self._populate_table()

        # 3. Bottom: Event log
        log_frame = ttk.LabelFrame(self.root, text="Live Event Log", padding=5)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        self.log_text = tk.Text(log_frame, height=8, wrap=tk.NONE, font=("Consolas", 9))
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 4. Status Bar
        self.status_var = tk.StringVar(value="Ready. Select MIDI port to listen.")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=3)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def _populate_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for c in self.state_mgr.controls:
            current_val = self.state_mgr.values.get(c.cid, 0)
            if c.kind == ControlKind.BUTTON:
                st_text = "PRESSED" if self.state_mgr.pressed.get(c.cid, False) else "RELEASED"
                bar_text = "[=====]" if self.state_mgr.pressed.get(c.cid, False) else "[     ]"
            else:
                st_text = str(current_val)
                bar_len = int((current_val / 127.0) * 10)
                bar_text = "[" + "#" * bar_len + " " * (10 - bar_len) + f"] {current_val}"

            self.tree.insert(
                "",
                tk.END,
                iid=c.cid,
                values=(
                    c.cid,
                    f"CC {self.state_mgr.get_cc(c.cid)}" if self.state_mgr.get_cc(c.cid) is not None else "Unbound",
                    self.state_mgr.get_name(c.cid),
                    st_text,
                    bar_text,
                    c.pin_desc,
                    "Learn",
                ),
                tags=("normal",),
            )

    def _refresh_ports(self):
        if mido is None:
            self.port_combo["values"] = ["mido library not installed"]
            self.port_combo.current(0)
            return

        try:
            names = mido.get_input_names()
            self.port_combo["values"] = names
            if names:
                # Prioritize Zoom G port
                zoom_ports = [n for n in names if n.startswith(PORT_PREFIX)]
                if zoom_ports:
                    self.port_combo.set(zoom_ports[0])
                else:
                    self.port_combo.current(0)
            else:
                self.port_combo.set("")
        except Exception as e:
            self.port_combo["values"] = []
            self.status_var.set(f"Error enumerating ports: {e}")

    def _toggle_connection(self):
        if self.input_port is not None:
            self._disconnect_port()
        else:
            self._connect_port()

    def _connect_port(self):
        port_name = self.port_combo.get()
        if not port_name:
            messagebox.showwarning("No Port", "Please select a valid input MIDI port.")
            return

        if mido is None:
            messagebox.showerror("Missing mido", "The mido library is required for live monitoring.")
            return

        try:
            self.input_port = mido.open_input(port_name)
            # Never clear an old session's event: its worker may still be in a
            # backend read while the owner disconnects and reconnects.
            self.stop_listening = threading.Event()
            self.listen_thread = threading.Thread(
                target=self._listen_worker,
                args=(self.input_port, self.stop_listening), daemon=True,
            )
            self.listen_thread.start()

            self.btn_connect.configure(text="Disconnect")
            self.port_combo.configure(state="disabled")
            self.btn_refresh.configure(state="disabled")
            self.status_var.set(f"Connected to input port: {port_name} (Receive Only)")
            self._log_line(f"--- Connected to input port: {port_name} ---")
        except Exception as e:
            self.stop_listening.set()
            if self.input_port is not None:
                try:
                    self.input_port.close()
                except Exception:
                    pass
            self.input_port = None
            messagebox.showerror("Connection Error", f"Failed to open port '{port_name}': {e}")

    def _disconnect_port(self):
        self.stop_listening.set()
        if self.input_port is not None:
            try:
                self.input_port.close()
            except Exception:
                pass
            self.input_port = None

        self.btn_connect.configure(text="Connect")
        self.port_combo.configure(state="readonly")
        self.btn_refresh.configure(state="normal")
        self.status_var.set("Disconnected.")
        self._log_line("--- Disconnected ---")

    def _listen_worker(self, port, stop):
        while not stop.is_set():
            try:
                for msg in port.iter_pending():
                    if stop.is_set():
                        return
                    self.incoming.put((stop, "message", msg))
            except Exception as e:
                self.incoming.put((stop, "error", str(e)))
                break
            stop.wait(0.005)

    def _poll_incoming(self):
        # Only the Tk thread touches widgets or mapping state. Reject both
        # messages and errors queued by disconnected sessions.
        for _ in range(256):
            try:
                stop, kind, payload = self.incoming.get_nowait()
            except Empty:
                break
            if stop is not self.stop_listening or stop.is_set():
                continue
            if kind == "message":
                self._handle_incoming_mido(payload)
            else:
                self._log_line(f"MIDI read error: {payload}")
        self.incoming_timer = self.root.after(10, self._poll_incoming)

    def _handle_incoming_mido(self, msg):
        ev = self.state_mgr.process_mido_message(msg)
        if ev:
            self._apply_event(ev)
        else:
            self._log_line(f"Raw MIDI: {msg}")

    def _apply_event(self, ev: ControlEvent):
        # Learn can unbind a previous row, so refresh every displayed CC.
        for control in self.state_mgr.controls:
            cc = self.state_mgr.get_cc(control.cid)
            self.tree.set(control.cid, "cc", f"CC {cc}" if cc is not None else "Unbound")
        # Update row if mapped
        if ev.cid in self.tree.get_children():
            ctrl = self.state_mgr.controls_by_cid.get(ev.cid)
            if ctrl and ctrl.kind == ControlKind.BUTTON:
                st_text = "PRESSED" if self.state_mgr.pressed.get(ev.cid, False) else "RELEASED"
                bar_text = "[=====]" if self.state_mgr.pressed.get(ev.cid, False) else "[     ]"
            else:
                st_text = str(ev.value)
                bar_len = int((ev.value / 127.0) * 10)
                bar_text = "[" + "#" * bar_len + " " * (10 - bar_len) + f"] {ev.value}"

            self.tree.set(ev.cid, "state", st_text)
            self.tree.set(ev.cid, "bar", bar_text)
            self.tree.set(ev.cid, "name", self.state_mgr.get_name(ev.cid))

            # Flash row green
            self.tree.item(ev.cid, tags=("active",))
            if ev.cid in self.highlight_timers:
                self.root.after_cancel(self.highlight_timers[ev.cid])
            self.highlight_timers[ev.cid] = self.root.after(
                350, lambda c=ev.cid: self.tree.item(c, tags=("normal",))
            )

        # Log event
        now_str = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_msg = f"[{now_str}]  {ev.raw_bytes}  |  {ev.control_name} ({ev.cid}) -> {ev.display_value}"
        self._log_line(log_msg)

        if self.state_mgr.learn_target_cid is None:
            self.status_var.set(f"Last received: {ev.control_name} ({ev.raw_bytes}) = {ev.display_value}")

    def _log_line(self, text: str):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def _on_tree_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree.identify_column(event.x)
        item = self.tree.identify_row(event.y)
        if not item:
            return

        # Column #7 is Learn button
        if col == "#7":
            self._start_learn(item)

    def _start_learn(self, cid: str):
        self.state_mgr.start_learn(cid)
        ctrl_name = self.state_mgr.get_name(cid)
        self.status_var.set(f"LEARNING: Touch/move control on pedal to bind to '{ctrl_name}' (ID: {cid})...")
        self.tree.item(cid, tags=("learning",))
        self._log_line(f"--- Learn mode activated for {ctrl_name} ({cid}) ---")

    def _on_tree_double_click(self, event):
        item = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not item or col != "#3":  # Double-click on Name column
            return

        old_name = self.state_mgr.get_name(item)
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Control Name")
        dialog.geometry("380x130")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=f"Custom name for {item}:").pack(padx=10, pady=(15, 5), anchor=tk.W)
        entry = ttk.Entry(dialog, width=40)
        entry.insert(0, old_name)
        entry.pack(padx=10, pady=5)
        entry.focus()

        def confirm():
            new_name = entry.get().strip()
            if new_name:
                self.state_mgr.set_name(item, new_name)
                self.tree.set(item, "name", new_name)
            dialog.destroy()

        btn_box = ttk.Frame(dialog)
        btn_box.pack(pady=10)
        ttk.Button(btn_box, text="Save", command=confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_box, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
        dialog.bind("<Return>", lambda e: confirm())
        dialog.bind("<Escape>", lambda e: dialog.destroy())

    def _save_names(self):
        try:
            self.state_mgr.save_names(DEFAULT_NAMES_PATH)
            messagebox.showinfo("Saved", f"Names saved to {DEFAULT_NAMES_PATH}")
            self.status_var.set(f"Names saved to {DEFAULT_NAMES_PATH.name}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save names: {e}")

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export DAW Control Mapping CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            try:
                self.state_mgr.export_csv(path)
                messagebox.showinfo("Export Complete", f"Exported CSV mapping to {path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export CSV: {e}")

    def _run_simulation(self):
        """Simulate feeding test messages to verify UI reactivity."""
        self._log_line("--- Running Offline Simulation Sequence ---")
        seq = MidiStateManager.simulation_sequence()

        def sim_thread():
            for cc, val in seq:
                ev = self.state_mgr.process_raw(cc, val)
                if ev:
                    self.root.after(0, self._apply_event, ev)
                time.sleep(0.08)
            self.root.after(0, self.status_var.set, "Simulation complete. 15 events processed.")

        threading.Thread(target=sim_thread, daemon=True).start()

    def _on_close(self):
        self._disconnect_port()
        self.root.after_cancel(self.incoming_timer)
        self.root.destroy()


def main():
    root = tk.Tk()
    app = MidiMonitorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
