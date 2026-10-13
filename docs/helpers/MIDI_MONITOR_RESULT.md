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
| 0 | `fs_0` | Footswitch GPIO3 | 20 | 127 press, 0 release | Footswitch (GPIO3 / event 0..1; physical side unverified) |
| 1 | `fs_1` | Footswitch GPIO5 | 21 | 127 press, 0 release | Footswitch (GPIO5 / event 2..3; physical side unverified) |
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

## M1. Pure Mapping Module & Tests

Implemented:
- [`tools/cf_midi_mapping.py`](file:///c:/Users/z/Documents/zoom%20project/tools/cf_midi_mapping.py):
  - Defines the 17 hardware controls with IDs, default names, CC assignments, types, and GPIO descriptions.
  - State manager `MidiStateManager` tracking live values, button press/release, and custom naming.
  - Learn mode binding incoming CC messages to designated control IDs.
  - JSON persistence for custom control names.
  - CSV export for DAW / host MIDI mapping.
  - Deterministic simulation sequence exercising all controls.
  - Zero GUI and zero MIDI port opening calls.
- [`tests/test_midi_monitor.py`](file:///c:/Users/z/Documents/zoom%20project/tests/test_midi_monitor.py):
  - 9 unit tests covering all 17 controls, raw and mido CC decoding, naming persistence, CSV export, Learn mode, and safety verification.
  - All 9 tests passed. Full test suite: 86 passed.

## M2. Receive-Only GUI Application (`tools/cf_midi_monitor.py`)

Implemented:
- [`tools/cf_midi_monitor.py`](file:///c:/Users/z/Documents/zoom%20project/tools/cf_midi_monitor.py):
  - **Port Selector**: Enumerates input ports via `mido.get_input_names()`, prioritizing `ZOOM G` prefix. Connect/Disconnect toggle with background thread listening via non-blocking `iter_pending()`.
  - **Table View**: 17 rows corresponding to the physical controls, displaying Control ID, CC, User-Editable Name, Live State (PRESSED/RELEASED or continuous value), visual level bar, hardware pin/event mapping, and interactive "Learn" button.
  - **Live Feedback**: Row temporarily flashes green upon receiving an incoming message.
  - **Event Log**: Real-time scrolling text log showing millisecond-resolution timestamps, raw hex bytes (e.g. `B0 14 7F`), resolved custom control name, and value.
  - **Learn Mode**: Clicking "Learn" on any control engages Learn mode. The next incoming CC is bound to that control ID and persisted in the mapping.
  - **Inline Editing**: Double-clicking on any control name opens an edit dialog to rename the control.
  - **Persistence**: "Save Names" writes custom names to `build/loader/midi_names.json`. Existing names are loaded automatically on launch.
  - **DAW Export**: "Export CSV" writes a full mapping CSV (`Index,Control_ID,Name,CC,Type,Pin_Desc`) for host/DAW mapping.
  - **Offline Simulation**: "Simulate Test" dispatches standard 15-event test sequence exercising buttons, knobs, and expression pedal to verify UI responsiveness without hardware connected.
  - **Safety Compliance**: Static grep assertion verifies complete absence of `open_output`, `.send(`, `Output(`, and `pedal_g1`. The application is strictly receive-only.

### Hardware Validation Card (Owner Action Item)
When testing on the physical pedal with controller firmware:
1. Hold the entry button (`GPIO 0` / Rhythm-Looper button, CC 31) while powering on until the logo finishes displaying.
2. Launch `python tools/cf_midi_monitor.py`.
3. Select `ZOOM G Series` input port and click **Connect**.
4. Press each footswitch and panel button, rotate each encoder knob, and move the expression pedal one at a time.
5. Double-click each control row to name the physical legend on the pedal casing.
6. Click **Save Names** and **Export CSV**.

## Codex review — 2026-10-12

- The documented direct launch initially failed with `ModuleNotFoundError: tools`. The monitor now supports direct script launch as well as package import; a subprocess smoke test reached the window.
- Learn initially left the target's old CC active and saved/exported only default assignments. Learn now keeps one active binding per control and CC, stores bindings alongside names in the JSON file, and exports active bindings. Old name-only JSON files still load.
- The GPIO3/GPIO5 footswitch sides remain unverified. Their default labels now use GPIO names until the owner checks the physical pedal.
- Offline verification: 86 tests passed. Input-port behavior and physical legends still require the owner test above.

## Reconnect and channel fixes — 2026-10-13

- Each connection now owns a separate stop event and captures its input port in its worker. Disconnect permanently stops that session; a quick reconnect cannot revive the old worker or let it read the new port.
- Workers enqueue messages and errors without calling Tk. The GUI drains the queue on its own thread and rejects messages/errors from disconnected sessions. Closing cancels the queue timer; a backend read finishing later cannot touch the destroyed window.
- Only MIDI channel 1 (zero-indexed channel 0, status `B0`) can update the fixed firmware mapping or complete Learn. Messages on channels 2–16 appear as raw MIDI and leave control state, bindings and the armed Learn target untouched.
- Offline regression coverage now includes a fake-port GUI connection/dispatch test with real listener threads and stub widgets. It holds an old read open across reconnect, checks queued stale messages and late read errors are discarded, checks the new port has exactly one reader and its message is applied once, and verifies close cleanup. A channel regression exercises channels 2–16 and subsequent channel-1 Learn.
- Targeted validation: `.venv/Scripts/python.exe -m pytest tests/test_midi_monitor.py -q` — **11 passed, 2 subtests passed**. Tests use no MIDI hardware. Physical host behavior and control legends remain unverified.
