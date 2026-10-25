"""Tests for tools/cf_flasher.py.

Simulates the pedal's update-mode MIDI SysEx interface with a mock loopback harness,
verifying device inquiry, session handshake, erase, write, retry logic, normal-mode
detection, and safety barriers without requiring physical hardware.
"""

from collections import deque
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import cf_flasher as flasher
import update_mode as um


class MockMidiMessage:
    def __init__(self, raw_bytes):
        self.type = "sysex"
        # mido provides msg.data without framing, msg.bin() with framing
        self.raw = bytes(raw_bytes)
        self.data = list(self.raw[1:-1])

    def bin(self):
        return bytearray(self.raw)


class MockMidiPort:
    def __init__(self):
        self.inbox = deque()
        self.sent_messages = []
        self.closed = False

    def send(self, msg):
        self.sent_messages.append(bytes(msg.bin()))

    def poll(self):
        if self.inbox:
            raw = self.inbox.popleft()
            return MockMidiMessage(raw)
        return None

    def close(self):
        self.closed = True


class SafetyTests(unittest.TestCase):
    def test_blocks_boot_write_by_default(self):
        stage = flasher.FlashStage(2, 0x000000, 0, data=b"bad boot data")
        with self.assertRaises(flasher.SafetyViolationError):
            flasher.check_stage_safety(stage, allow_boot_write=False)

    def test_allows_boot_write_when_explicit(self):
        stage = flasher.FlashStage(2, 0x000000, 0, data=b"approved boot logo")
        flasher.check_stage_safety(stage, allow_boot_write=True)

    def test_blocks_settings_sector_write(self):
        stage = flasher.FlashStage(1, 0x0BF000, 0x1000)
        with self.assertRaises(flasher.SafetyViolationError):
            flasher.check_stage_safety(stage, allow_boot_write=True)

    def test_allows_normal_firmware_and_fs_stages(self):
        fw_erase = flasher.FlashStage(1, flasher.FLASH_FW_ADDR, flasher.FLASH_FW_SIZE)
        fw_write = flasher.FlashStage(2, flasher.FLASH_FW_ADDR, 0, data=b"\x00" * 1024)
        fs_erase = flasher.FlashStage(1, flasher.FLASH_FS_ADDR, flasher.FLASH_FS_SIZE)
        fs_write = flasher.FlashStage(2, flasher.FLASH_FS_ADDR, 0, data=b"\x00" * 1024)

        for s in [fw_erase, fw_write, fs_erase, fs_write]:
            flasher.check_stage_safety(s)


class FlasherSessionProtocolTests(unittest.TestCase):
    def setUp(self):
        self.inport = MockMidiPort()
        self.outport = MockMidiPort()
        self.session = flasher.FlasherSession(
            inport=self.inport,
            outport=self.outport,
            verbose=False,
        )

    def test_device_inquiry_identifies_model(self):
        # Universal Identity Reply: family/member 6E 00 0D 00 (G1X Four)
        identity_reply = bytes([
            0xF0, 0x7E, 0x00, 0x06, 0x02, 0x52, 0x6E, 0x00, 0x0D, 0x00,
            0x32, 0x2E, 0x30, 0x30, 0xF7
        ])
        self.inport.inbox.append(identity_reply)

        dev_id = self.session.identify_device()
        self.assertEqual(dev_id, bytes([0x6E, 0x00, 0x0D, 0x00]))
        self.assertEqual(self.session.model_byte, 0x6E)
        self.assertEqual(len(self.outport.sent_messages), 1)
        self.assertEqual(self.outport.sent_messages[0], um.build_identity_inquiry())

    def test_enter_session_success(self):
        ack_reply = bytes([0xF0, 0x52, 0x00, 0x6E, 0x00, 0x00, 0xF7])
        self.inport.inbox.append(ack_reply)

        self.session.enter_session()
        self.assertEqual(self.outport.sent_messages[-1], um.build_enter_session(0x6E))

    def test_enter_session_detects_normal_mode(self):
        # Status 0x0B = pedal in normal mode, not update mode
        normal_mode_reply = bytes([0xF0, 0x52, 0x00, 0x6E, 0x00, 0x0B, 0xF7])
        self.inport.inbox.append(normal_mode_reply)

        with self.assertRaises(flasher.NotInUpdateModeError):
            self.session.enter_session()

    def test_verify_boot_version(self):
        payload = b"1.00"
        packed = um.pack7(payload)
        crc = um.crc_field(payload)
        read_reply = (
            bytes([0xF0, 0x52, 0x00, 0x6E, 0x60, 0x04, 0x30, 0x00, 0x00])
            + bytes([len(payload) & 0x7F, 0])
            + packed
            + crc
            + bytes([0xF7])
        )
        self.inport.inbox.append(read_reply)

        ver = self.session.verify_boot_version()
        self.assertEqual(ver, "1.00")
        self.assertEqual(self.outport.sent_messages[-1], um.build_handshake(0x6E))

    def test_erase_region(self):
        ack_reply = bytes([0xF0, 0x52, 0x00, 0x6E, 0x00, 0x00, 0xF7])
        self.inport.inbox.append(ack_reply)

        self.session.erase_region(0x033000, 0x08C000)
        self.assertEqual(self.outport.sent_messages[-1], um.build_erase(0x033000, 0x08C000, 0x6E))

    def test_write_data_chunking_and_ack(self):
        data = b"X" * 5000  # Requires 2 chunks (4096 + 904 bytes)
        ack_reply1 = bytes([0xF0, 0x52, 0x00, 0x6E, 0x00, 0x00, 0xF7])
        ack_reply2 = bytes([0xF0, 0x52, 0x00, 0x6E, 0x02, 0x00, 0xF7])
        self.inport.inbox.append(ack_reply1)
        self.inport.inbox.append(ack_reply2)

        self.session.write_data(0x033000, data, chunk_size=4096)
        self.assertEqual(len(self.outport.sent_messages), 2)
        # Check chunk 1 address
        self.assertEqual(self.outport.sent_messages[0], um.build_write_chunk(0x033000, data[:4096], 0x6E))
        # Check chunk 2 address
        self.assertEqual(self.outport.sent_messages[1], um.build_write_chunk(0x033000 + 4096, data[4096:], 0x6E))

    def test_full_pipeline_mock(self):
        # 1. Inquiry reply
        self.inport.inbox.append(bytes([
            0xF0, 0x7E, 0x00, 0x06, 0x02, 0x52, 0x6E, 0x00, 0x0D, 0x00,
            0x32, 0x2E, 0x30, 0x30, 0xF7
        ]))
        # 2. Enter session ACK
        self.inport.inbox.append(bytes([0xF0, 0x52, 0x00, 0x6E, 0x00, 0x00, 0xF7]))
        # 3. Boot read reply
        payload = b"1.00"
        self.inport.inbox.append(
            bytes([0xF0, 0x52, 0x00, 0x6E, 0x60, 0x04, 0x30, 0x00, 0x00])
            + bytes([len(payload), 0])
            + um.pack7(payload)
            + um.crc_field(payload)
            + bytes([0xF7])
        )
        # 4. Erase ACK
        self.inport.inbox.append(bytes([0xF0, 0x52, 0x00, 0x6E, 0x00, 0x00, 0xF7]))
        # 5. Write ACK
        self.inport.inbox.append(bytes([0xF0, 0x52, 0x00, 0x6E, 0x00, 0x00, 0xF7]))
        # 6. Exit session ACK
        self.inport.inbox.append(bytes([0xF0, 0x52, 0x00, 0x6E, 0x00, 0x00, 0xF7]))

        stages = [
            flasher.FlashStage(1, 0x033000, 0x1000, description="Erase test"),
            flasher.FlashStage(2, 0x033000, 0, data=b"A" * 100, description="Write test"),
        ]
        self.session.run_stages(stages)

        # Confirm exit session was sent
        self.assertEqual(self.outport.sent_messages[-1], um.build_exit_session(0x6E))


if __name__ == "__main__":
    unittest.main()
