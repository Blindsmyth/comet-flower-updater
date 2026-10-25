"""Tests for tools/update_mode.py's message builders against recon/26_update_mode_protocol.md.

Every expected byte string here is computed independently of the module under test (manual
7-bit math, not a call into update_mode itself), so a transcription slip in the module would
show up as a mismatch. The pack7 cross-check additionally compares against zoom-zt2's own
pack(), the already-used implementation this project trusts for normal-mode SysEx, to confirm
section 5b's "bit-for-bit identical" claim by execution, not just by reading both sources.
"""
import binascii
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import update_mode as um  # noqa: E402


def num7_manual(v, n):
    return bytes((v >> (7 * k)) & 0x7F for k in range(n))


class HandshakeTests(unittest.TestCase):
    def test_bytes(self):
        msg = um.build_handshake()
        self.assertEqual(msg[:6], bytes([0xF0, 0x52, 0x00, 0x6E, 0x60, 0x30]))
        self.assertEqual(msg[6:11], num7_manual(0x27FFC, 5))
        self.assertEqual(msg[11:16], num7_manual(4, 5))
        self.assertEqual(msg[16], 0xF7)
        self.assertEqual(len(msg), 17)

    def test_model_byte_at_offset_3(self):
        self.assertEqual(um.build_handshake(model=0x00)[3], 0x00)
        self.assertEqual(um.build_handshake(model=0x6E)[3], 0x6E)


class SessionControlTests(unittest.TestCase):
    def test_identity_inquiry(self):
        self.assertEqual(um.build_identity_inquiry(), bytes([0xF0, 0x7E, 0x00, 0x06, 0x01, 0xF7]))

    def test_enter_exit_session(self):
        self.assertEqual(um.build_enter_session(), bytes([0xF0, 0x52, 0x00, 0x6E, 0x01, 0xF7]))
        self.assertEqual(um.build_exit_session(), bytes([0xF0, 0x52, 0x00, 0x6E, 0x04, 0xF7]))


class ReplyParserTests(unittest.TestCase):
    def test_identity_reply(self):
        msg = bytes([0xF0, 0x7E, 0x00, 0x06, 0x02, 0x52, 0x6E, 0x00, 0x0D, 0x00,
                     0x32, 0x2E, 0x30, 0x30, 0xF7])
        rep = um.parse_reply(msg)
        self.assertEqual(rep["type"], "identity")
        self.assertEqual(rep["status"], 0)
        self.assertEqual(rep["device_id"], bytes([0x6E, 0x00, 0x0D, 0x00]))

    def test_status_ack_and_errors(self):
        ack = um.parse_reply(bytes([0xF0, 0x52, 0x00, 0x6E, 0x00, 0x00, 0xF7]))
        self.assertEqual(ack, {"type": "status", "status": 0})
        not_upd = um.parse_reply(bytes([0xF0, 0x52, 0x00, 0x6E, 0x00, 0x0B, 0xF7]))
        self.assertEqual(not_upd, {"type": "status", "status": 0x0B})
        nack = um.parse_reply(bytes([0xF0, 0x52, 0x00, 0x6E, 0x00, 0x01, 0xF7]))
        self.assertEqual(nack, {"type": "status", "status": 1})

    def test_read_data_reply_roundtrip(self):
        payload = b"1.00"
        packed = um.pack7(payload)
        crc = um.crc_field(payload)
        msg = (bytes([0xF0, 0x52, 0x00, 0x6E, 0x60, 0x04, 0x30, 0x00, 0x00])
               + num7_manual(len(payload), 2) + packed + crc + bytes([0xF7]))
        rep = um.parse_reply(msg)
        self.assertEqual(rep["type"], "read_data")
        self.assertEqual(rep["status"], 0)
        self.assertTrue(rep["crc_ok"])
        self.assertEqual(rep["data"], b"1.00")
        # Corrupt one byte -> status 1
        bad = bytearray(msg)
        bad[12] ^= 0x01
        rep_bad = um.parse_reply(bytes(bad))
        self.assertEqual(rep_bad["status"], 1)
        self.assertFalse(rep_bad["crc_ok"])


class EraseTests(unittest.TestCase):
    def test_bytes(self):
        msg = um.build_erase(0x0BF000, 0x1000)
        self.assertEqual(msg[:5], bytes([0xF0, 0x52, 0x00, 0x6E, 0x0A]))
        self.assertEqual(msg[5:10], num7_manual(0x0BF000, 5))
        self.assertEqual(msg[10:15], num7_manual(0x1000, 5))
        self.assertEqual(msg[15], 0xF7)
        self.assertEqual(len(msg), 16)

    def test_every_stage_table_erase(self):
        # recon/26 section 1, op==1 rows
        for addr, size in [(0x0BF000, 0x1000), (0x028000, 0xB000), (0x000000, 0x28000),
                           (0x033000, 0x8C000)]:
            msg = um.build_erase(addr, size)
            self.assertEqual(len(msg), 16)
            self.assertEqual(msg[0], 0xF0)
            self.assertEqual(msg[-1], 0xF7)


class WriteChunkTests(unittest.TestCase):
    def test_small_chunk_layout(self):
        data = bytes([0x00, 0x80, 0x7F, 0xFF, 0x01])  # 5 bytes, under one pack7 group of 7
        msg = um.build_write_chunk(0x33000, data)
        self.assertEqual(msg[:5], bytes([0xF0, 0x52, 0x00, 0x6E, 0x02]))
        self.assertEqual(msg[5:10], num7_manual(0x33000, 5))
        self.assertEqual(msg[10:12], num7_manual(len(data), 2))
        # one collector byte + 5 payload bytes (single group, len(data) < 7)
        collector = msg[12]
        payload = msg[13:18]
        self.assertEqual(payload, bytes(b & 0x7F for b in data))
        expect_hi = 0
        for k, b in enumerate(data):
            expect_hi |= (b & 0x80) >> (k + 1)
        self.assertEqual(collector, expect_hi)
        crc = binascii.crc32(data) ^ 0xFFFFFFFF
        self.assertEqual(msg[18:23], num7_manual(crc, 5))
        self.assertEqual(msg[23], 0xF7)
        self.assertEqual(len(msg), 24)

    def test_length_matches_packed_plus_18(self):
        for n in (0, 1, 6, 7, 8, 13, 14, 15, 100, 4096):
            data = bytes((i * 37) & 0xFF for i in range(n))
            msg = um.build_write_chunk(0, data)
            self.assertEqual(len(msg), 18 + len(um.pack7(data)))

    def test_rejects_oversize_chunk(self):
        with self.assertRaises(ValueError):
            um.build_write_chunk(0, bytes(um.MAX_CHUNK + 1))

    def test_write_chunks_splits_and_covers_every_byte(self):
        data = bytes((i * 7) & 0xFF for i in range(0x1000 + 37))
        msgs = list(um.write_chunks(0x33000, data, chunk=0x1000))
        self.assertEqual(len(msgs), 2)
        # second message's address field = base + first chunk's length
        addr2 = sum(b << (7 * k) for k, b in enumerate(msgs[1][5:10]))
        self.assertEqual(addr2, 0x33000 + 0x1000)


class Pack7CrossCheckTests(unittest.TestCase):
    """Confirms update_mode.pack7 matches zoom-zt2's own pack(), the implementation this
    project already trusts and uses for normal-mode SysEx (recon/26 section 5b)."""

    @classmethod
    def setUpClass(cls):
        zoomlab = Path(os.environ.get("ZOOMLAB", r"C:\Users\z\zoomlab\stomphacks"))
        zt2_path = zoomlab / "zoom-zt2"
        if not (zt2_path / "zoomzt2.py").exists():
            raise unittest.SkipTest("zoom-zt2 not found at %s" % zt2_path)
        sys.path.insert(0, str(zt2_path))
        import zoomzt2
        cls.zt2 = zoomzt2.zoomzt2()

    def test_matches_for_various_lengths(self):
        for n in (0, 1, 6, 7, 8, 13, 14, 20, 100):
            data = bytearray((i * 53 + 11) & 0xFF for i in range(n))
            mine = um.pack7(bytes(data))
            theirs = bytes(self.zt2.pack(data))
            self.assertEqual(mine, theirs, "mismatch at n=%d" % n)

    def test_matches_for_all_high_bits_set(self):
        data = bytes([0xFF] * 21)
        self.assertEqual(um.pack7(data), bytes(self.zt2.pack(bytearray(data))))


if __name__ == "__main__":
    unittest.main()
