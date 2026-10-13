"""Pure MIDI mapping and state module for G1X Four controller monitoring.

Defines the 17 hardware controls, parses incoming CC messages, tracks live
state, supports name customization, Learn mode, JSON persistence, and CSV export.
No GUI or MIDI port operations are performed here.
"""

from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple, Union


class ControlKind(str, Enum):
    BUTTON = "button"
    CONTINUOUS = "continuous"


@dataclass(frozen=True)
class ControlDef:
    cid: str
    default_name: str
    cc: int
    kind: ControlKind
    channel: int = 0  # MIDI channel 1 is 0 in 0-indexed systems
    pin_desc: str = ""


# The 17 standard controls on the G1X Four controller firmware
DEFAULT_CONTROLS: Tuple[ControlDef, ...] = (
    ControlDef("fs_0", "Footswitch GPIO3", 20, ControlKind.BUTTON, 0, "GPIO3 / Event 0..1"),
    ControlDef("fs_1", "Footswitch GPIO5", 21, ControlKind.BUTTON, 0, "GPIO5 / Event 2..3"),
    ControlDef("btn_0", "Button 0 (GPIO 4)", 22, ControlKind.BUTTON, 0, "Panel button bit 0"),
    ControlDef("btn_1", "Button 1 (GPIO 2)", 23, ControlKind.BUTTON, 0, "Panel button bit 1"),
    ControlDef("btn_2", "Button 2 (GPIO 6)", 24, ControlKind.BUTTON, 0, "Panel button bit 2"),
    ControlDef("btn_3", "Button 3 (GPIO 27)", 25, ControlKind.BUTTON, 0, "Panel button bit 3"),
    ControlDef("btn_4", "Button 4 (GPIO 24)", 26, ControlKind.BUTTON, 0, "Panel button bit 4"),
    ControlDef("btn_5", "Button 5 (GPIO 26)", 27, ControlKind.BUTTON, 0, "Panel button bit 5"),
    ControlDef("btn_6", "Button 6 (GPIO 37)", 28, ControlKind.BUTTON, 0, "Panel button bit 6"),
    ControlDef("btn_7", "Button 7 (GPIO 38)", 29, ControlKind.BUTTON, 0, "Panel button bit 7"),
    ControlDef("btn_8", "Button 8 (GPIO 86)", 30, ControlKind.BUTTON, 0, "Panel button bit 8"),
    ControlDef("btn_9", "Button 9 (GPIO 0)", 31, ControlKind.BUTTON, 0, "Entry button bit 9"),
    ControlDef("knob_1", "Knob 1", 40, ControlKind.CONTINUOUS, 0, "Encoder 1 / Event 25"),
    ControlDef("knob_2", "Knob 2", 41, ControlKind.CONTINUOUS, 0, "Encoder 2 / Event 26"),
    ControlDef("knob_3", "Knob 3", 42, ControlKind.CONTINUOUS, 0, "Encoder 3 / Event 27"),
    ControlDef("knob_4", "Knob 4", 43, ControlKind.CONTINUOUS, 0, "Encoder 4 / Event 28"),
    ControlDef("expr", "Expression Pedal", 11, ControlKind.CONTINUOUS, 0, "Calibrated AD / Event 42"),
)


@dataclass
class ControlEvent:
    timestamp: float
    cid: str
    cc: int
    value: int
    control_name: str
    display_value: str
    raw_bytes: str


class MidiStateManager:
    """Manages control state, naming, learn mode, and message dispatch."""

    def __init__(self, controls: Tuple[ControlDef, ...] = DEFAULT_CONTROLS):
        self.controls: Tuple[ControlDef, ...] = controls
        self.controls_by_cid: Dict[str, ControlDef] = {c.cid: c for c in controls}
        self.cc_to_cid: Dict[int, str] = {c.cc: c.cid for c in controls}
        self.custom_names: Dict[str, str] = {}
        self.values: Dict[str, int] = {
            c.cid: (64 if c.kind == ControlKind.CONTINUOUS and c.cid.startswith("knob") else 0)
            for c in controls
        }
        self.pressed: Dict[str, bool] = {c.cid: False for c in controls}
        self.learn_target_cid: Optional[str] = None

    def get_name(self, cid: str) -> str:
        if cid in self.custom_names and self.custom_names[cid].strip():
            return self.custom_names[cid].strip()
        ctrl = self.controls_by_cid.get(cid)
        return ctrl.default_name if ctrl else cid

    def get_cc(self, cid: str) -> Optional[int]:
        return next((cc for cc, mapped_cid in self.cc_to_cid.items() if mapped_cid == cid), None)

    def set_name(self, cid: str, name: str) -> None:
        if cid in self.controls_by_cid:
            self.custom_names[cid] = name.strip()

    def start_learn(self, cid: str) -> None:
        if cid in self.controls_by_cid:
            self.learn_target_cid = cid

    def cancel_learn(self) -> None:
        self.learn_target_cid = None

    def process_raw(self, cc: int, value: int, timestamp: Optional[float] = None, channel: int = 0) -> Optional[ControlEvent]:
        """Process firmware CCs on MIDI channel 1 (zero-indexed channel 0)."""
        # Other channels remain raw in the GUI, including while Learn is armed.
        if channel != 0:
            return None
        ts = time.monotonic() if timestamp is None else timestamp
        raw_hex = f"B{channel:X} {cc:02X} {value:02X}"

        # If in Learn mode, bind incoming CC to the targeted control ID
        if self.learn_target_cid:
            target_cid = self.learn_target_cid
            self.learn_target_cid = None

            # A control and a CC each have at most one active binding.
            self.cc_to_cid = {
                existing_cc: cid for existing_cc, cid in self.cc_to_cid.items()
                if cid != target_cid and existing_cc != cc
            }
            self.cc_to_cid[cc] = target_cid

            ctrl = self.controls_by_cid[target_cid]
            self.values[target_cid] = value
            if ctrl.kind == ControlKind.BUTTON:
                self.pressed[target_cid] = (value >= 64)
                disp = "PRESSED" if self.pressed[target_cid] else "RELEASED"
            else:
                disp = str(value)

            return ControlEvent(
                timestamp=ts,
                cid=target_cid,
                cc=cc,
                value=value,
                control_name=self.get_name(target_cid),
                display_value=f"{disp} (LEARNED CC {cc})",
                raw_bytes=raw_hex,
            )

        cid = self.cc_to_cid.get(cc)
        if not cid:
            # Unmapped CC message
            return ControlEvent(
                timestamp=ts,
                cid=f"unmapped_cc_{cc}",
                cc=cc,
                value=value,
                control_name=f"Unmapped CC {cc}",
                display_value=str(value),
                raw_bytes=raw_hex,
            )

        ctrl = self.controls_by_cid[cid]
        self.values[cid] = value
        if ctrl.kind == ControlKind.BUTTON:
            self.pressed[cid] = (value >= 64)
            disp = "PRESSED" if self.pressed[cid] else "RELEASED"
        else:
            disp = str(value)

        return ControlEvent(
            timestamp=ts,
            cid=cid,
            cc=cc,
            value=value,
            control_name=self.get_name(cid),
            display_value=disp,
            raw_bytes=raw_hex,
        )

    def process_mido_message(self, msg: Any, timestamp: Optional[float] = None) -> Optional[ControlEvent]:
        """Parse mido Message object if it is a Control Change."""
        if getattr(msg, "type", None) == "control_change":
            cc = int(msg.control)
            val = int(msg.value)
            ch = int(getattr(msg, "channel", 0))
            return self.process_raw(cc, val, timestamp=timestamp, channel=ch)
        return None

    def save_names(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data: Dict[str, Any] = {cid: self.custom_names.get(cid, "") for cid in self.controls_by_cid}
        data["_cc_bindings"] = {cid: self.get_cc(cid) for cid in self.controls_by_cid}
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load_names(self, path: Union[str, Path]) -> bool:
        p = Path(path)
        if not p.is_file():
            return False
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                for cid, name in data.items():
                    if cid in self.controls_by_cid and isinstance(name, str):
                        self.custom_names[cid] = name.strip()
                bindings = data.get("_cc_bindings")
                if isinstance(bindings, dict) and set(bindings) == set(self.controls_by_cid):
                    active = [cc for cc in bindings.values() if cc is not None]
                    if (all(type(cc) is int and 0 <= cc <= 127 for cc in active)
                            and len(active) == len(set(active))):
                        self.cc_to_cid = {
                            cc: cid for cid, cc in bindings.items() if cc is not None
                        }
                return True
        except Exception:
            pass
        return False

    def export_csv(self, path: Union[str, Path]) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        lines = ["Index,Control_ID,Name,CC,Type,Pin_Desc"]
        for idx, c in enumerate(self.controls):
            name = self.get_name(c.cid).replace('"', '""')
            cc = self.get_cc(c.cid)
            lines.append(f'{idx},{c.cid},"{name}",{cc if cc is not None else ""},{c.kind.value},"{c.pin_desc}"')
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def simulation_sequence() -> List[Tuple[int, int]]:
        """Standard test/simulation sequence exercising buttons, knobs, and expression."""
        return [
            (20, 127),  # Footswitch Left Press
            (20, 0),    # Footswitch Left Release
            (21, 127),  # Footswitch Right Press
            (21, 0),    # Footswitch Right Release
            (22, 127),  # Button 0 Press
            (22, 0),    # Button 0 Release
            (31, 127),  # Button 9 (GPIO0) Press
            (31, 0),    # Button 9 (GPIO0) Release
            (40, 72),   # Knob 1 moved to 72
            (41, 100),  # Knob 2 moved to 100
            (42, 32),   # Knob 3 moved to 32
            (43, 0),    # Knob 4 moved to 0
            (11, 64),   # Expression half
            (11, 127),  # Expression toe down
            (11, 0),    # Expression heel down
        ]
