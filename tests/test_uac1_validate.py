"""Unittest suite for UAC1 + MIDI 1.0 configuration descriptor validator.

Verifies:
  1. Prototype real bytes (via host harness) validate with 0 violations.
  2. Hand-crafted known-good reference UAC1 configuration validates cleanly.
  3. One mutation test per check id (1..9), asserting only that check id fires.
"""

from __future__ import annotations

import ctypes
import unittest
from pathlib import Path

from tools.uac1_validate import validate, CHECK_IDS

# Discover host compiler / harness availability
try:
    from tools.test_usb_audio_proto import build_host_library
    _LIB = build_host_library()
    _LIB.host_reset()
    _LIB.usb_audio_copy_descriptors.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
    _LIB.usb_audio_copy_descriptors.restype = ctypes.c_uint
    HOST_COMPILER_AVAILABLE = True
except Exception:
    _LIB = None
    HOST_COMPILER_AVAILABLE = False


def get_prototype_bytes() -> bytes:
    """Obtain configuration descriptor bytes directly from the host C harness."""
    if not HOST_COMPILER_AVAILABLE or _LIB is None:
        raise RuntimeError("Host C compiler harness is not available")
    _LIB.host_reset()
    storage = (ctypes.c_ubyte * 520)()
    count = _LIB.usb_audio_copy_descriptors(ctypes.byref(storage, 0), 65535, 512)
    return bytes(storage[:count])


def build_reference_uac1() -> bytes:
    """Build a minimal valid UAC1 stereo 16-bit 44.1 kHz IN-only configuration (Linux f_uac1-style)."""
    # 0x00: Configuration Descriptor (9 bytes, wTotalLength = 100 = 0x0064, bNumInterfaces = 2)
    config = bytes([
        0x09, 0x02, 0x64, 0x00, 0x02, 0x01, 0x00, 0x80, 0x32
    ])
    # 0x09: Interface 0 Alt 0 - AudioControl (9 bytes, bNumEndpoints = 0)
    if0 = bytes([
        0x09, 0x04, 0x00, 0x00, 0x00, 0x01, 0x01, 0x00, 0x00
    ])
    # 0x12: AC Header Descriptor (9 bytes, wTotalLength = 30 = 0x001e, bInCollection = 1, baInterfaceNr = [1])
    ac_hdr = bytes([
        0x09, 0x24, 0x01, 0x00, 0x01, 0x1e, 0x00, 0x01, 0x01
    ])
    # 0x1b: Input Terminal (12 bytes, ID 1, Analog Connector 0x0601, 2 channels stereo)
    it1 = bytes([
        0x0c, 0x24, 0x02, 0x01, 0x01, 0x06, 0x00, 0x02, 0x03, 0x00, 0x00, 0x00
    ])
    # 0x27: Output Terminal (9 bytes, ID 2, USB Streaming 0x0101, bSourceID = 1)
    ot2 = bytes([
        0x09, 0x24, 0x03, 0x02, 0x01, 0x01, 0x00, 0x01, 0x00
    ])
    # 0x30: Interface 1 Alt 0 - AudioStreaming Idle (9 bytes, bNumEndpoints = 0)
    if1_alt0 = bytes([
        0x09, 0x04, 0x01, 0x00, 0x00, 0x01, 0x02, 0x00, 0x00
    ])
    # 0x39: Interface 1 Alt 1 - AudioStreaming Active (9 bytes, bNumEndpoints = 1)
    if1_alt1 = bytes([
        0x09, 0x04, 0x01, 0x01, 0x01, 0x01, 0x02, 0x00, 0x00
    ])
    # 0x42: AS General Descriptor (7 bytes, bTerminalLink = 2)
    as_gen = bytes([
        0x07, 0x24, 0x01, 0x02, 0x01, 0x01, 0x00
    ])
    # 0x49: Format Type I Descriptor (11 bytes, 2 ch, 2 B subframe, 16 bit, discrete 44.1 kHz)
    fmt_i = bytes([
        0x0b, 0x24, 0x02, 0x01, 0x02, 0x02, 0x10, 0x01, 0x44, 0xac, 0x00
    ])
    # 0x54: Standard Audio Isochronous IN Endpoint (9 bytes, EP 0x81, wMaxPacketSize = 180, bInterval = 1)
    iso_ep = bytes([
        0x09, 0x05, 0x81, 0x05, 0xb4, 0x00, 0x01, 0x00, 0x00
    ])
    # 0x5d: Class-Specific AS Isochronous Endpoint (7 bytes, EP_GENERAL)
    cs_ep = bytes([
        0x07, 0x25, 0x01, 0x00, 0x00, 0x00, 0x00
    ])
    return config + if0 + ac_hdr + it1 + ot2 + if1_alt0 + if1_alt1 + as_gen + fmt_i + iso_ep + cs_ep


# Static copy of prototype 192 bytes used as fallback for mutation tests if harness absent
STATIC_PROTO_BYTES = bytes.fromhex(
    "0902c00004010080fa"  # Config
    "090400000001010000"  # IF 0 Alt 0 (AC)
    "092401000109000101"  # CS AC Header
    "090401000201030000"  # IF 1 Alt 0 (MS)
    "07240100012500"      # CS MS Header
    "062402010a00"        # In Jack Emb
    "062402021e00"        # In Jack Ext
    "0924030114011e0100"  # Out Jack Emb
    "0924030228010a0100"  # Out Jack Ext
    "090503024000000000"  # Bulk Out EP
    "052501010a"          # CS EP
    "090584024000000000"  # Bulk In EP
    "0525010114"          # CS EP
    "090402000001010000"  # IF 2 Alt 0 (AC)
    "09240100011e000103"  # CS AC Header
    "0c2402010106000203000000"  # IT 1
    "092403020101000100"  # OT 2
    "090403000001020000"  # IF 3 Alt 0 (AS idle)
    "090403010101020000"  # IF 3 Alt 1 (AS active)
    "07240102010100"      # AS General
    "0b2402010202100144ac00"  # Format Type I
    "09058105b400010000"  # ISO EP 0x81
    "07250100000000"      # CS ISO EP
)


class TestUac1Validator(unittest.TestCase):
    """Validation test suite matching GEMINI_UAC1_VALIDATOR requirements."""

    def get_good_bytes(self) -> bytes:
        if HOST_COMPILER_AVAILABLE:
            return get_prototype_bytes()
        return STATIC_PROTO_BYTES

    @unittest.skipUnless(HOST_COMPILER_AVAILABLE, "Host C compiler not available")
    def test_prototype_real_bytes_validate_with_zero_violations(self):
        """The prototype's real bytes validate with zero violations."""
        data = get_prototype_bytes()
        violations = validate(data)
        self.assertEqual(violations, [], f"Prototype bytes produced violations: {violations}")

    def test_windows_groups_midi_and_audio_as_two_functions(self):
        """Windows legacy audio grouping (no IAD): {IF0 AC, IF1 MS} and {IF2 AC, IF3 AS}."""
        from tools.uac1_validate import windows_legacy_audio_collections as group
        self.assertEqual(group(self.get_good_bytes()), [[0, 1], [2, 3]])
        # Same-subclass neighbour starts a new collection; an IAD disables grouping.
        ac = bytes.fromhex("090400000001010000")
        ac1 = bytes.fromhex("090401000001010000")
        self.assertEqual(group(ac + ac1), [[0], [1]])
        self.assertEqual(group(bytes.fromhex("080b000201010000") + ac), [])

    def test_known_good_reference_validates_cleanly(self):
        """Hand-crafted minimal UAC1 stereo 16-bit 44.1 kHz IN-only configuration validates cleanly."""
        ref = build_reference_uac1()
        violations = validate(ref)
        self.assertEqual(violations, [], f"Reference UAC1 produced violations: {violations}")

    def test_mutation_check1_framing(self):
        """Mutation 1: Corrupt wTotalLength to trigger framing violation only."""
        good = bytearray(self.get_good_bytes())
        # Change wTotalLength byte 2 from 0xc0 (192) to 0xc1 (193)
        good[2] ^= 0x01
        violations = validate(good)
        check_ids = {v[0] for v in violations}
        self.assertEqual(check_ids, {"framing"}, f"Unexpected check_ids: {check_ids}")

    def test_mutation_check2_configuration(self):
        """Mutation 2: Clear bmAttributes bit 7 to trigger configuration violation only."""
        good = bytearray(self.get_good_bytes())
        # Clear bit 7 of bmAttributes (byte 7)
        good[7] &= 0x7f
        violations = validate(good)
        check_ids = {v[0] for v in violations}
        self.assertEqual(check_ids, {"configuration"}, f"Unexpected check_ids: {check_ids}")

    def test_mutation_check3_interfaces(self):
        """Mutation 3: Alter bNumEndpoints in interface 1 to trigger interfaces violation only."""
        good = bytearray(self.get_good_bytes())
        # Interface 1 descriptor is at offset 27 (byte 27..35); bNumEndpoints is byte 31 (value 2 -> 1)
        self.assertEqual(good[27], 9)
        self.assertEqual(good[29], 1)  # bInterfaceNumber
        good[31] = 1
        violations = validate(good)
        check_ids = {v[0] for v in violations}
        self.assertEqual(check_ids, {"interfaces"}, f"Unexpected check_ids: {check_ids}")

    def test_mutation_check4_audio_control(self):
        """Mutation 4: Alter AC header wTotalLength to trigger audio_control violation only."""
        good = bytearray(self.get_good_bytes())
        # uac_ac_header is at offset 110 (byte 110..118); wTotalLength is at 115..116 (value 0x001e)
        self.assertEqual(good[110:113], b"\x09\x24\x01")
        self.assertEqual(good[115], 0x1e)
        good[115] = 0x1f
        violations = validate(good)
        check_ids = {v[0] for v in violations}
        self.assertEqual(check_ids, {"audio_control"}, f"Unexpected check_ids: {check_ids}")

    def test_mutation_check5_terminals(self):
        """Mutation 5: Point bSourceID to nonexistent terminal to trigger terminals violation only."""
        good = bytearray(self.get_good_bytes())
        # uac_ot2 is at offset 131 (byte 131..139); bSourceID is at offset 138 (value 0x01)
        self.assertEqual(good[131:134], b"\x09\x24\x03")
        self.assertEqual(good[138], 0x01)
        good[138] = 0x99
        violations = validate(good)
        check_ids = {v[0] for v in violations}
        self.assertEqual(check_ids, {"terminals"}, f"Unexpected check_ids: {check_ids}")

    def test_mutation_check6_audio_streaming(self):
        """Mutation 6: Reduce wMaxPacketSize below required size to trigger audio_streaming violation only."""
        good = bytearray(self.get_good_bytes())
        # uac_ep1 is at offset 179 (byte 179..187); wMaxPacketSize is at 183..184 (value 180 = 0x00b4)
        self.assertEqual(good[179:181], b"\x09\x05")
        self.assertEqual(good[183], 0xb4)
        good[183] = 100
        good[184] = 0
        violations = validate(good)
        check_ids = {v[0] for v in violations}
        self.assertEqual(check_ids, {"audio_streaming"}, f"Unexpected check_ids: {check_ids}")

    def test_mutation_check7_midi_streaming(self):
        """Mutation 7: Alter MS header wTotalLength to trigger midi_streaming violation only."""
        good = bytearray(self.get_good_bytes())
        # stock_ms_header is at offset 36 (byte 36..42); wTotalLength is at 41..42 (value 37 = 0x0025)
        self.assertEqual(good[36:39], b"\x07\x24\x01")
        self.assertEqual(good[41], 0x25)
        good[41] = 0x24
        violations = validate(good)
        check_ids = {v[0] for v in violations}
        self.assertEqual(check_ids, {"midi_streaming"}, f"Unexpected check_ids: {check_ids}")

    def test_mutation_check8_endpoint_addresses(self):
        """Mutation 8: Duplicate endpoint address across interfaces to trigger endpoint_addresses violation only."""
        good = bytearray(self.get_good_bytes())
        # uac_ep1 is at offset 179; bEndpointAddress is at 181 (0x81). Interface 1 uses 0x84.
        self.assertEqual(good[181], 0x81)
        good[181] = 0x84
        violations = validate(good)
        check_ids = {v[0] for v in violations}
        self.assertEqual(check_ids, {"endpoint_addresses"}, f"Unexpected check_ids: {check_ids}")

    def test_mutation_check9_bandwidth(self):
        """Mutation 9: Set ISO wMaxPacketSize > 1023 to trigger bandwidth violation only."""
        good = bytearray(self.get_good_bytes())
        # uac_ep1 is at offset 179; wMaxPacketSize is at 183..184. Set to 1024 (0x0400).
        self.assertEqual(good[183], 0xb4)
        good[183] = 0x00
        good[184] = 0x04
        violations = validate(good)
        check_ids = {v[0] for v in violations}
        self.assertEqual(check_ids, {"bandwidth"}, f"Unexpected check_ids: {check_ids}")


if __name__ == "__main__":
    unittest.main()
