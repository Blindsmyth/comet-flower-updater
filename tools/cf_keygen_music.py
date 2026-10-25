"""Retro Keygen Chiptune Player for Comet Flower Updater (Razor 1911 Style).

Plays an authentic demoscene-style 8-bit / tracker arpeggiated loop in the background
using the default Windows MIDI Wavetable Synth (channel 0 square wave lead, channel 1 synth bass).
Supports loading custom user compositions from music_track.json with built-in fallback.
Zero external audio files required.
"""

import json
from pathlib import Path
import sys
import threading
import time
from typing import Optional


class KeygenMusicPlayer:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._outport = None
        self._available = False
        self._is_playing = False
        self._init_synth()

    def _init_synth(self):
        try:
            import mido

            out_names = mido.get_output_names()
            target_port = None
            for name in out_names:
                if any(k in name.lower() for k in ("wavetable", "synth", "microsoft")):
                    target_port = name
                    break
            if target_port:
                self._port_name = target_port
                self._available = True
            else:
                self._port_name = None
                self._available = False
        except Exception:
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    def start(self):
        if not self._available or self._is_playing:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._play_loop, daemon=True)
        self._is_playing = True
        self._thread.start()

    def stop(self):
        if not self._is_playing:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        self._silence_all()
        self._is_playing = False

    def toggle(self) -> bool:
        if self._is_playing:
            self.stop()
        else:
            self.start()
        return self._is_playing

    def _silence_all(self):
        if self._outport:
            try:
                import mido

                for ch in (0, 1):
                    self._outport.send(mido.Message("control_change", channel=ch, control=120, value=0))
                    self._outport.send(mido.Message("control_change", channel=ch, control=123, value=0))
                self._outport.close()
            except Exception:
                pass
            self._outport = None

    def _play_loop(self):
        import mido

        try:
            self._outport = mido.open_output(self._port_name)
            
            # Default fallback track (Chiptune loop)
            lead_prog = 80
            bass_prog = 38
            step = 0.120
            bass_pattern = [1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 0]

            arp_cycle = [
                # Bar 1: Bm
                (47, [59, 62, 66, 71, 66, 62, 59, 62, 66, 71, 74, 73, 71, 69, 66, 62]),
                # Bar 2: A
                (45, [57, 61, 64, 69, 64, 61, 57, 61, 64, 69, 73, 71, 69, 67, 64, 61]),
                # Bar 3: G
                (43, [55, 59, 62, 67, 62, 59, 55, 59, 62, 67, 71, 69, 67, 66, 62, 59]),
                # Bar 4: Em
                (40, [52, 55, 59, 64, 59, 55, 52, 55, 59, 64, 67, 66, 64, 62, 59, 55]),
            ]

            lead_cycle = [
                (47, [71, 71, 71, 74, 74, 74, 76, 76, 74, 74, 71, 71, 69, 71, 74, 71]),
                (45, [69, 69, 69, 73, 73, 73, 71, 69, 69, 69, 64, 64, 67, 69, 71, 69]),
                (43, [67, 67, 67, 71, 71, 74, 74, 76, 79, 79, 76, 74, 71, 69, 67, 71]),
                (40, [64, 64, 64, 67, 67, 69, 71, 74, 71, 69, 67, 64, 62, 64, 67, 64]),
            ]

            all_bars = arp_cycle + lead_cycle

            # Check if custom user track was generated
            try:
                base = Path(sys._MEIPASS) / "payload" if getattr(sys, "frozen", False) else Path(__file__).resolve().parent / "payload"
                track_file = base / "music_track.json"
                if track_file.is_file():
                    track_data = json.loads(track_file.read_text(encoding="utf-8"))
                    lead_prog = track_data.get("lead_program", 80)
                    bass_prog = track_data.get("bass_program", 38)
                    step = track_data.get("step_duration", 0.120)
                    if "bars" in track_data:
                        custom_bars = []
                        for b in track_data["bars"]:
                            custom_bars.append((b["root"], b["notes"]))
                        if custom_bars:
                            all_bars = custom_bars
            except Exception:
                pass

            self._outport.send(mido.Message("program_change", channel=0, program=lead_prog))
            self._outport.send(mido.Message("program_change", channel=1, program=bass_prog))

            while not self._stop_event.is_set():
                for root_note, lead_notes in all_bars:
                    for i in range(16):
                        if self._stop_event.is_set():
                            break
                        lead_n = lead_notes[i]
                        bass_on = bass_pattern[i]
                        bass_n = root_note if bass_on else None

                        if bass_n:
                            self._outport.send(mido.Message("note_on", channel=1, note=bass_n, velocity=100))
                        if lead_n:
                            self._outport.send(mido.Message("note_on", channel=0, note=lead_n, velocity=88))

                        time.sleep(step * 0.82)

                        if bass_n:
                            self._outport.send(mido.Message("note_off", channel=1, note=bass_n))
                        if lead_n:
                            self._outport.send(mido.Message("note_off", channel=0, note=lead_n))

                        time.sleep(step * 0.18)
        except Exception:
            pass
        finally:
            self._silence_all()
            self._is_playing = False
