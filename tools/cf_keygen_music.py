"""Retro Keygen Chiptune Player for Comet Flower Flasher (Razor 1911 Style).

Plays an authentic demoscene-style 8-bit / tracker arpeggiated loop in the background
using the default Windows MIDI Wavetable Synth (channel 0, synth square lead / synth bass).
Zero external audio files required.
"""

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
                    # All sound off / all notes off
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
            # Patch 80 = Lead 1 (square wave), Patch 38 = Synth Bass 1
            self._outport.send(mido.Message("program_change", channel=0, program=80))
            self._outport.send(mido.Message("program_change", channel=1, program=38))

            # Classic demoscene keygen progression: Am -> F -> C -> G
            # 16th-note arpeggios at ~130 BPM (~115ms per step)
            step_dur = 0.115

            # Patterns: tuples of (lead_note, bass_note)
            chords = [
                # Am (A2 bass, A C E A arpeggios)
                [(69, 45), (72, 45), (76, None), (81, None), (76, None), (72, None), (69, None), (72, 45)],
                # F (F2 bass, F A C F arpeggios)
                [(65, 41), (69, 41), (72, None), (77, None), (72, None), (69, None), (65, None), (69, 41)],
                # C (C2 bass, C E G C arpeggios)
                [(60, 48), (64, 48), (67, None), (72, None), (67, None), (64, None), (60, None), (64, 48)],
                # G (G2 bass, G B D G arpeggios)
                [(67, 43), (71, 43), (74, None), (79, None), (74, None), (71, None), (67, None), (71, 43)],
            ]

            while not self._stop_event.is_set():
                for chord in chords:
                    for lead, bass in chord:
                        if self._stop_event.is_set():
                            break
                        # Trigger Lead note
                        if lead:
                            self._outport.send(mido.Message("note_on", channel=0, note=lead, velocity=88))
                        # Trigger Bass note
                        if bass:
                            self._outport.send(mido.Message("note_on", channel=1, note=bass, velocity=105))

                        # Let ring for most of step
                        time.sleep(step_dur * 0.85)

                        # Note off
                        if lead:
                            self._outport.send(mido.Message("note_off", channel=0, note=lead))
                        if bass:
                            self._outport.send(mido.Message("note_off", channel=1, note=bass))

                        time.sleep(step_dur * 0.15)
        except Exception:
            pass
        finally:
            self._silence_all()
            self._is_playing = False
