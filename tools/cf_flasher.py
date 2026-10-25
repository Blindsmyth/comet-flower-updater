"""Comet Flower Standalone Firmware Flasher for Zoom G1X Four / G1 Four.

Communicates directly with the pedal in firmware update mode (hold both footswitches
while connecting USB) using plain MIDI SysEx, completely replacing reliance on Zoom's
official x86 updater executable.

Protocol reverse-engineered and documented in recon/26_update_mode_protocol.md.
Safety invariants documented in recon/25_boot_safety.md.
"""

from dataclasses import dataclass
import sys
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Union

# Ensure tools/ directory is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

import update_mode as um

# Default MIDI port names used by the pedal in update mode (res5 bootloader)
DEFAULT_PORT_PREFIXES = ("ZOOM G Series", "ZOOM G", "Comet Flower")

# Flash memory layout (recon/25, recon/26)
FLASH_BOOT_ADDR = 0x000000
FLASH_BOOT_SIZE = 0x028000
FLASH_PRESET_ADDR = 0x028000
FLASH_PRESET_SIZE = 0x00B000
FLASH_FW_ADDR = 0x033000
FLASH_FW_SIZE = 0x08C000
FLASH_SETTINGS_ADDR = 0x0BF000
FLASH_SETTINGS_SIZE = 0x001000
FLASH_FS_ADDR = 0x102000
FLASH_FS_SIZE = 0x2FE000

PROTECTED_REGIONS = [
    (FLASH_BOOT_ADDR, FLASH_BOOT_ADDR + FLASH_BOOT_SIZE, "boot program (res5)"),
    (FLASH_SETTINGS_ADDR, FLASH_SETTINGS_ADDR + FLASH_SETTINGS_SIZE, "settings/signature sector"),
]


class FlasherError(Exception):
    """Base error for firmware flashing issues."""
    pass


class NotInUpdateModeError(FlasherError):
    """Raised when the pedal is connected in normal operating mode instead of update mode."""
    pass


class SafetyViolationError(FlasherError):
    """Raised when an erase or write targets a protected region without explicit approval."""
    pass


@dataclass
class FlashStage:
    op: int  # 1 = erase, 2 = write
    addr: int
    size: int  # size for erase
    data: Optional[bytes] = None  # payload for write
    description: str = ""

    @property
    def op_name(self) -> str:
        return "erase" if self.op == 1 else "write"

    @property
    def end_addr(self) -> int:
        if self.op == 1:
            return self.addr + self.size
        return self.addr + (len(self.data) if self.data else 0)


def check_stage_safety(stage: FlashStage, allow_boot_write: bool = False) -> None:
    """Verifies that a stage does not touch protected regions (recon/25)."""
    start = stage.addr
    end = stage.end_addr
    for p_lo, p_hi, name in PROTECTED_REGIONS:
        if start < p_hi and end > p_lo:
            if p_lo == FLASH_BOOT_ADDR and allow_boot_write:
                continue
            raise SafetyViolationError(
                f"Refusing {stage.op_name} at 0x{start:06X}..0x{end:06X}: "
                f"touches protected {name}. "
                f"Boot area writes require explicit permission."
            )


class FlasherSession:
    """Manages the update-mode SysEx connection, handshake, erase, and write pipeline."""

    def __init__(
        self,
        inport=None,
        outport=None,
        model_byte: int = um.MODEL_BYTE,
        verbose: bool = True,
        log_fn: Optional[Callable[[str], None]] = None,
    ):
        self.inport = inport
        self.outport = outport
        self.model_byte = model_byte
        self.verbose = verbose
        self.log = log_fn or (lambda msg: print(msg, flush=True) if self.verbose else None)
        self.device_info = {}

    def connect(self, port_name: Optional[str] = None) -> None:
        """Finds and opens the pedal MIDI in and out ports."""
        import mido

        inputs = mido.get_input_names()
        outputs = mido.get_output_names()

        def match_port(ports: List[str], target: Optional[str]) -> Optional[str]:
            if target:
                for p in ports:
                    if target.lower() in p.lower():
                        return p
                return None
            for prefix in DEFAULT_PORT_PREFIXES:
                for p in ports:
                    if p.startswith(prefix):
                        return p
            return None

        in_name = match_port(inputs, port_name)
        out_name = match_port(outputs, port_name)

        if not in_name or not out_name:
            raise FlasherError(
                f"Could not find Zoom/Comet Flower MIDI ports.\n"
                f"Available inputs: {inputs}\n"
                f"Available outputs: {outputs}\n"
                f"Make sure the pedal is powered on in update mode (hold both footswitches while connecting USB)."
            )

        self.log(f"Opening MIDI IN:  {in_name}")
        self.log(f"Opening MIDI OUT: {out_name}")
        self.inport = mido.open_input(in_name)
        self.outport = mido.open_output(out_name)

    def close(self) -> None:
        """Closes open MIDI ports."""
        if self.inport:
            try:
                self.inport.close()
            except Exception:
                pass
            self.inport = None
        if self.outport:
            try:
                self.outport.close()
            except Exception:
                pass
            self.outport = None

    def send_sysex(self, raw_bytes: bytes) -> None:
        """Sends a framed SysEx byte string (F0 ... F7)."""
        import mido

        if raw_bytes[0] != 0xF0 or raw_bytes[-1] != 0xF7:
            raise ValueError("send_sysex expects complete frame starting with F0 and ending with F7")
        # mido expects data without the F0/F7 framing
        msg = mido.Message("sysex", data=list(raw_bytes[1:-1]))
        self.outport.send(msg)

    def receive_reply(self, timeout_sec: float) -> Optional[dict]:
        """Polls for a matching SysEx reply until timeout."""
        deadline = time.monotonic() + timeout_sec
        while time.monotonic() < deadline:
            msg = self.inport.poll()
            if msg is not None and msg.type == "sysex":
                frame = bytes(msg.bin())
                try:
                    return um.parse_reply(frame, model=self.model_byte)
                except Exception:
                    # Ignore unrelated/corrupt SysEx frames
                    continue
            time.sleep(0.002)
        return None

    def send_and_wait(
        self,
        raw_bytes: bytes,
        timeout_sec: float = 1.0,
        retries: int = 0,
        retry_delay_sec: float = 0.1,
    ) -> dict:
        """Sends a SysEx message and awaits an ACK with optional retries."""
        attempts = 0
        while attempts <= retries:
            attempts += 1
            self.send_sysex(raw_bytes)
            reply = self.receive_reply(timeout_sec)
            if reply is not None:
                if reply.get("status") == 0:
                    return reply
                if reply.get("status") == 0x0B:
                    raise NotInUpdateModeError(
                        "Pedal returned status 0x0B: it is in normal operation mode, NOT firmware update mode.\n"
                        "To enter update mode: power off, hold down BOTH footswitches, and connect USB power."
                    )
            if attempts <= retries:
                time.sleep(retry_delay_sec)
        raise FlasherError(
            f"Timeout or NACK waiting for reply after {attempts} attempts ({timeout_sec}s timeout)."
        )

    def identify_device(self) -> bytes:
        """Sends Universal Device Inquiry (F0 7E 00 06 01 F7) and validates model."""
        self.log("Sending Universal Device Inquiry...")
        inquiry = um.build_identity_inquiry()
        # Identity reply can take a moment if pedal just started
        reply = self.send_and_wait(inquiry, timeout_sec=5.0, retries=2, retry_delay_sec=0.2)
        if reply.get("type") != "identity":
            raise FlasherError(f"Unexpected inquiry reply: {reply}")

        dev_id = reply["device_id"]
        self.device_info["device_id"] = dev_id.hex()
        # Byte 0 is MODEL_BYTE (0x6E for G1/G1X Four)
        self.model_byte = dev_id[0]
        self.log(f"Connected device ID: {dev_id.hex()} (Model byte: 0x{self.model_byte:02X})")
        return dev_id

    def enter_session(self) -> None:
        """Enters programming / firmware update session (0x01)."""
        self.log("Entering update session...")
        cmd = um.build_enter_session(model=self.model_byte)
        # Pedal replies with status 0x00 on success, or 0x0B if in normal mode
        reply = self.send_and_wait(cmd, timeout_sec=10.0, retries=1)
        if reply.get("status") != 0:
            raise FlasherError(f"Failed to enter update session: {reply}")
        # Official updater sleeps 500ms after entering session (recon/26 section 7)
        time.sleep(0.5)

    def verify_boot_version(self) -> str:
        """Reads the 4-byte boot version at 0x27FFC (recon/26 section 2)."""
        self.log("Reading boot program version at 0x27FFC...")
        read_cmd = um.build_handshake(model=self.model_byte)
        reply = self.send_and_wait(read_cmd, timeout_sec=5.0, retries=2)
        if reply.get("type") != "read_data" or not reply.get("crc_ok"):
            raise FlasherError(f"Boot version handshake read failed: {reply}")
        version_str = reply["data"].decode("ascii", errors="replace")
        self.log(f"Pedal boot version: {version_str!r}")
        self.device_info["boot_version"] = version_str
        return version_str

    def erase_region(
        self,
        addr: int,
        size: int,
        progress_cb: Optional[Callable[[str, float], None]] = None,
    ) -> None:
        """Sends erase command (0x0A) and awaits completion (up to 60s timeout, 6 retries)."""
        msg = um.build_erase(addr, size, model=self.model_byte)
        self.log(f"Erasing 0x{addr:06X} (size 0x{size:06X})...")
        if progress_cb:
            progress_cb("erasing", 0.0)

        # Erase of 3MB filesystem takes several seconds
        reply = self.send_and_wait(msg, timeout_sec=60.0, retries=6, retry_delay_sec=0.2)
        if reply.get("status") != 0:
            raise FlasherError(f"Erase failed at 0x{addr:06X}: {reply}")

        if progress_cb:
            progress_cb("erasing", 1.0)
        self.log(f"Erase complete: 0x{addr:06X}")

    def write_data(
        self,
        addr: int,
        data: bytes,
        chunk_size: int = um.MAX_CHUNK,
        progress_cb: Optional[Callable[[str, float], None]] = None,
    ) -> None:
        """Writes data in <= 4096-byte chunks with CRC32 checks (up to 30 retries per chunk)."""
        total = len(data)
        written = 0
        self.log(f"Writing 0x{addr:06X} ({total} bytes, {chunk_size} B/chunk)...")

        for offset in range(0, total, chunk_size):
            chunk = data[offset : offset + chunk_size]
            chunk_addr = addr + offset
            msg = um.build_write_chunk(chunk_addr, chunk, model=self.model_byte)

            # Each chunk write waits for ACK (cmd 0x02 or status 0)
            # Timeout is 1.0s, up to 30 retries with 100ms sleep (recon/26 section 7)
            reply = self.send_and_wait(msg, timeout_sec=1.0, retries=30, retry_delay_sec=0.1)
            if reply.get("status") != 0 and reply.get("type") not in ("status", "write_ack"):
                raise FlasherError(f"Write chunk failed at 0x{chunk_addr:06X}: {reply}")

            written += len(chunk)
            fraction = written / total
            if progress_cb:
                progress_cb("writing", fraction)
            if self.verbose and (offset % (chunk_size * 16) == 0 or written == total):
                self.log(f"  0x{chunk_addr:06X}: {written}/{total} bytes ({fraction * 100:.1f}%)")

        self.log(f"Write complete: 0x{addr:06X} ({total} bytes)")

    def exit_session(self) -> None:
        """Exits programming session (0x04) and reboots the pedal."""
        self.log("Exiting update session and restarting pedal...")
        cmd = um.build_exit_session(model=self.model_byte)
        try:
            self.send_and_wait(cmd, timeout_sec=10.0, retries=1)
        except Exception as e:
            # On exit, pedal may reboot immediately causing port close/timeout, which is normal
            self.log(f"Exit command sent ({e}); pedal rebooting.")

    def run_stages(
        self,
        stages: List[FlashStage],
        allow_boot_write: bool = False,
        progress_cb: Optional[Callable[[str, str, float], None]] = None,
    ) -> None:
        """Validates safety and executes all flash stages in order."""
        # 1. Preflight safety check on all stages before any MIDI transmission
        for stage in stages:
            check_stage_safety(stage, allow_boot_write=allow_boot_write)

        self.log(f"Preflight passed: {len(stages)} stage(s) approved for execution.")

        # 2. Handshake sequence
        self.identify_device()
        self.enter_session()
        self.verify_boot_version()

        # 3. Execution loop
        for idx, stage in enumerate(stages, 1):
            desc = stage.description or f"{stage.op_name} 0x{stage.addr:06X}"
            self.log(f"\n--- [Stage {idx}/{len(stages)}] {desc} ---")

            def stage_progress(op_str: str, frac: float):
                if progress_cb:
                    progress_cb(desc, op_str, frac)

            if stage.op == 1:
                self.erase_region(stage.addr, stage.size, progress_cb=stage_progress)
            elif stage.op == 2:
                if not stage.data:
                    raise FlasherError(f"Stage {idx} is write but has no data")
                self.write_data(stage.addr, stage.data, progress_cb=stage_progress)
            else:
                raise FlasherError(f"Unknown stage op: {stage.op}")

        # 4. Finalize
        self.exit_session()
        self.log("\n==========================================")
        self.log("Flashing completed successfully!")
        self.log("==========================================")


def plan_stages_from_files(
    firmware_path: Optional[Path] = None,
    fs_image_path: Optional[Path] = None,
    presets_path: Optional[Path] = None,
) -> List[FlashStage]:
    """Generates standard non-destructive flash stages from binary files."""
    stages = []

    # 1. Presets / Splash stage (0x028000)
    if presets_path and presets_path.is_file():
        data = presets_path.read_bytes()
        if len(data) > FLASH_PRESET_SIZE:
            raise ValueError(f"Presets file too large: {len(data)} > {FLASH_PRESET_SIZE}")
        stages.append(FlashStage(1, FLASH_PRESET_ADDR, FLASH_PRESET_SIZE, description="Erase Presets/Splash"))
        stages.append(FlashStage(2, FLASH_PRESET_ADDR, 0, data=data, description="Write Presets/Splash"))

    # 2. Main Firmware stage (0x033000)
    if firmware_path and firmware_path.is_file():
        data = firmware_path.read_bytes()
        if len(data) > FLASH_FW_SIZE:
            raise ValueError(f"Firmware file too large: {len(data)} > {FLASH_FW_SIZE}")
        stages.append(FlashStage(1, FLASH_FW_ADDR, FLASH_FW_SIZE, description="Erase Main Firmware"))
        stages.append(FlashStage(2, FLASH_FW_ADDR, 0, data=data, description="Write Main Firmware"))

    # 3. File System stage (0x102000)
    if fs_image_path and fs_image_path.is_file():
        data = fs_image_path.read_bytes()
        if len(data) > FLASH_FS_SIZE:
            raise ValueError(f"Filesystem image too large: {len(data)} > {FLASH_FS_SIZE}")
        stages.append(FlashStage(1, FLASH_FS_ADDR, FLASH_FS_SIZE, description="Erase Effect Filesystem"))
        stages.append(FlashStage(2, FLASH_FS_ADDR, 0, data=data, description="Write Effect Filesystem"))

    return stages


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Comet Flower Standalone Firmware Flasher (Native MIDI SysEx)"
    )
    parser.add_argument("--firmware", type=Path, help="Path to main firmware image (res1_*.bin)")
    parser.add_argument("--image", type=Path, help="Path to effect filesystem image (fs_*.bin)")
    parser.add_argument("--presets", type=Path, help="Path to presets/splash binary (res2_*.bin)")
    parser.add_argument("--port", type=str, help="Substring of the MIDI port name (default: auto-detect)")
    parser.add_argument("--allow-boot-write", action="store_true", help="Allow writing boot partition (HIGH RISK)")
    parser.add_argument("--dry-run", action="store_true", help="Validate files and safety without touching MIDI")

    args = parser.parse_args(argv)

    if not any([args.firmware, args.image, args.presets]):
        parser.print_help()
        print("\nError: Please provide at least one of --firmware, --image, or --presets.")
        return 2

    print("Comet Flower Standalone Flasher v1.0")
    print("------------------------------------")

    try:
        stages = plan_stages_from_files(
            firmware_path=args.firmware,
            fs_image_path=args.image,
            presets_path=args.presets,
        )
    except Exception as e:
        print(f"Error planning stages: {e}")
        return 1

    print(f"Planned {len(stages)} stage(s):")
    for s in stages:
        size_info = f"size {len(s.data):,} B" if s.data else f"size 0x{s.size:X}"
        print(f"  - {s.description:30s} : {s.op_name.upper()} 0x{s.addr:06X} ({size_info})")

    # Safety check
    try:
        for s in stages:
            check_stage_safety(s, allow_boot_write=args.allow_boot_write)
    except SafetyViolationError as e:
        print(f"\nSAFETY ABORT: {e}")
        return 1

    if args.dry_run:
        print("\nDry-run complete: all checks passed, no MIDI data sent.")
        return 0

    session = FlasherSession(verbose=True)
    try:
        session.connect(port_name=args.port)
        session.run_stages(stages, allow_boot_write=args.allow_boot_write)
        return 0
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 130
    except FlasherError as e:
        print(f"\nFLASHER ERROR: {e}")
        return 1
    except Exception as e:
        print(f"\nUNEXPECTED ERROR: {e}")
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
