# MIDI Monitor & Control Naming (M0..M2)

Record of implementation and validation for the receive-only MIDI monitor with nameable controls (`tools/cf_midi_monitor.py` and `tools/cf_midi_mapping.py`), following `docs/helpers/SOL_BUILD_UPDATER.md` Part C and `docs/helpers/GEMINI_NEXT.md`.

## M0. Survey of midi_listen_g1.py & 17 Controller Controls

### 1. Port Selection Survey (`tools/midi_listen_g1.py`)
`tools/midi_listen_g1.py` searches for a port prefix `ZOOM G` using `mido.get_input_names()`:
```python
PREFIX = "ZOOM G"

def find(names):
    hits = [n for n in names if n.startswith(PREFIX)]
    if not hits:
        sys.exit(f"no '{PREFIX}' MIDI port (pedal unplugged, or ToneLib holding it?)")
    return hits[0]
```
For `cf_midi_monitor`:
- It must **only** open input ports (`mido.open_input`).
- Under no circumstances will it open an output port (`mido.open_output`), call `.send()`, or instantiate `Output`.
- It will list all available input ports returned by `mido.get_input_names()`, auto-selecting the first port starting with `ZOOM G` if present, with a manual dropdown selector for any other port.

### 2. Inventory of the 17 Controls
All messages arrive on MIDI Channel 1 (status `0xB0`):

| Index | Control ID | Default Label | CC | Values | Physical Description / Pin |
|---|---|---|---|---|---|
| 0 | `fs_0` | Footswitch Left | 20 | 127 press, 0 release | Footswitch (GPIO3 / event 0..1) |
| 1 | `fs_1` | Footswitch Right | 21 | 127 press, 0 release | Footswitch (GPIO5 / event 2..3) |
| 2 | `btn_0` | Button 0 (GPIO 4) | 22 | 127 press, 0 release | Panel button (bitmap bit 0, GPIO 4) |
| 3 | `btn_1` | Button 1 (GPIO 2) | 23 | 127 press, 0 release | Panel button (bitmap bit 1, GPIO 2) |
| 4 | `btn_2` | Button 2 (GPIO 6) | 24 | 127 press, 0 release | Panel button (bitmap bit 2, GPIO 6) |
| 5 | `btn_3` | Button 3 (GPIO 27) | 25 | 127 press, 0 release | Panel button (bitmap bit 3, GPIO 27) |
| 6 | `btn_4` | Button 4 (GPIO 24) | 26 | 127 press, 0 release | Panel button (bitmap bit 4, GPIO 24) |
| 7 | `btn_5` | Button 5 (GPIO 26) | 27 | 127 press, 0 release | Panel button (bitmap bit 5, GPIO 26) |
| 8 | `btn_6` | Button 6 (GPIO 37) | 28 | 127 press, 0 release | Panel button (bitmap bit 6, GPIO 37) |
| 9 | `btn_7` | Button 7 (GPIO 38) | 29 | 127 press, 0 release | Panel button (bitmap bit 7, GPIO 38) |
| 10 | `btn_8` | Button 8 (GPIO 86) | 30 | 127 press, 0 release | Panel button (bitmap bit 8, GPIO 86) |
| 11 | `btn_9` | Button 9 (GPIO 0) | 31 | 127 press, 0 release | Mode-entry button (bitmap bit 9, GPIO 0, Rhythm/Looper) |
| 12 | `knob_1` | Knob 1 | 40 | 0..127 | Parameter encoder 1 (event 25) |
| 13 | `knob_2` | Knob 2 | 41 | 0..127 | Parameter encoder 2 (event 26) |
| 14 | `knob_3` | Knob 3 | 42 | 0..127 | Parameter encoder 3 (event 27) |
| 15 | `knob_4` | Knob 4 | 43 | 0..127 | Parameter encoder 4 (event 28) |
| 16 | `expr` | Expression Pedal | 11 | 0..127 | Calibrated expression (event 42) |

---
