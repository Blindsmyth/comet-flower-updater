"""Update-mode SysEx message builders (host side).

Reverse-engineered by static analysis of the x86 "ZOOM G1X FOUR System v2.00 Updater.exe"
(not the pedal's own firmware) -- full derivation, confirmed byte layouts, and open gaps in
recon/26_update_mode_protocol.md. These are the exact messages that updater sends over plain
MIDI SysEx while the pedal is in update mode (hold both footswitches at power-on); it uses no
vendor USB driver, only WINMM's midiOut*/midiIn*.

Message-building only. No MIDI I/O, nothing here has been tried against real hardware, and
there is deliberately no send loop: the pedal's reply/ack format (recon/26 section 7) is not
yet known, so a blind send loop could not tell success from failure. Treat every function
here as an unverified candidate until checked against a real captured update-mode session.

    python tools/update_mode.py erase <addr> <size>
    python tools/update_mode.py write <addr> <file> [<chunk size, default 0x1000>]

Both print the hex of every message that would be sent, for comparison against a real
capture -- they do not open a MIDI port.
"""
import binascii
import sys
from pathlib import Path

MODEL_BYTE = 0x6E  # recon/26 section 2 & 8: populated at runtime by memcpy(0x44bc0c, id_reply+6, 4)
                    # at 0x4047dd from the Universal Identity Reply (6e 00 0d 00 for G1X FOUR).
ENTER_CMD = 0x01
EXIT_CMD = 0x04
ACK_CMD = 0x00
HANDSHAKE_CMD = 0x60  # Flash Read command (0x60 0x30 <addr:5B> <size:5B>)
ERASE_CMD = 0x0A
WRITE_CMD = 0x02
MAX_CHUNK = 0x1000  # the real updater never sends a write-chunk message larger than this


def num7(v, n):
    """n-byte 7-bit little-endian encoding (recon/26 section 5a)."""
    return bytes((v >> (7 * k)) & 0x7F for k in range(n))


def num7_decode(buf):
    """Inverse of num7 (recon/26 section 5a / 0x403e70): 5-byte 7-bit-LE (top byte masked 0x0F)."""
    v = 0
    for k, b in enumerate(buf):
        mask = 0x0F if k == 4 else 0x7F
        v |= (b & mask) << (7 * k)
    return v


def pack7(data):
    """7-bit MIDI-safe pack: one MSB-collector byte per group of up to 7 source bytes,
    byte k's bit 7 -> collector bit (6 - k) (recon/26 section 5b; bit-for-bit identical to
    zoom-zt2's own pack(), see tests/test_update_mode.py)."""
    out = bytearray()
    for i in range(0, len(data), 7):
        group = data[i:i + 7]
        hi = 0
        for k, b in enumerate(group):
            hi |= (b & 0x80) >> (k + 1)
        out.append(hi)
        out.extend(b & 0x7F for b in group)
    return bytes(out)


def packed_len_for(raw_len):
    """Exact packed byte length for `raw_len` unpacked bytes (matches 0x40403b..0x40406d)."""
    q, r = divmod(raw_len, 7)
    return q * 8 + (r + 1 if r else 0)


def unpack7(packed, raw_len=None):
    """7-bit unpack (matches 0x401180): inverse of pack7."""
    out = bytearray()
    i = 0
    n = len(packed)
    while i < n:
        hi = packed[i]
        group = packed[i + 1:i + 8]
        for k, b in enumerate(group):
            out.append((b & 0x7F) | (((hi >> (6 - k)) & 1) << 7))
            if raw_len is not None and len(out) >= raw_len:
                return bytes(out)
        i += 1 + len(group)
    return bytes(out)


def crc_field(data):
    """5-byte 7-bit-LE checksum field (recon/26 section 5c)."""
    return num7(binascii.crc32(data) ^ 0xFFFFFFFF, 5)


def build_identity_inquiry():
    """Universal MIDI Device Inquiry sent at start of update session (0x4046ac, .data 0x4490a0)."""
    return bytes([0xF0, 0x7E, 0x00, 0x06, 0x01, 0xF7])


def build_enter_session(model=MODEL_BYTE):
    """Enter programming / firmware-update session (0x4049a2, .data 0x4490c0)."""
    return bytes([0xF0, 0x52, 0x00, model, ENTER_CMD, 0xF7])


def build_exit_session(model=MODEL_BYTE):
    """Exit programming / firmware-update session (0x404c15, .data 0x4490e0)."""
    return bytes([0xF0, 0x52, 0x00, model, EXIT_CMD, 0xF7])


def build_flash_read(addr, size, model=MODEL_BYTE):
    """recon/26 section 2: read `size` bytes from flash `addr` (cmd 0x60, subcmd 0x30)."""
    return (bytes([0xF0, 0x52, 0x00, model, HANDSHAKE_CMD, 0x30])
            + num7(addr, 5) + num7(size, 5) + bytes([0xF7]))


def build_handshake(model=MODEL_BYTE):
    """recon/26 section 2: the pre-loop boot-version read at 0x27FFC (4 bytes, '1.00')."""
    return build_flash_read(0x27FFC, 4, model=model)


def parse_reply(msg, model=MODEL_BYTE):
    """Decode a pedal SysEx reply using the exact dispatch rules of 0x403ee0 (recon/26 section 7).

    Returns a dict with:
      - 'type': 'identity' | 'status' | 'write_ack' | 'read_data' | 'unknown'
      - 'status': integer status written to `this+0x2138` (0 = OK, 0x0B = not in update mode,
                  non-zero = error/NACK)
      - plus type-specific fields ('device_id' for identity, 'data' for read_data).
    """
    msg = bytes(msg)
    if len(msg) < 6 or msg[0] != 0xF0 or msg[-1] != 0xF7:
        raise ValueError("not a complete SysEx frame")
    if msg[1] == 0x7E:
        if msg[3] == 0x06 and msg[4] == 0x02 and len(msg) >= 11:
            return {"type": "identity", "status": 0, "device_id": bytes(msg[6:10])}
        return {"type": "unknown", "status": 1}
    if msg[1] != 0x52:
        raise ValueError("unexpected manufacturer byte: %#x" % msg[1])
    cmd = msg[4]
    if cmd == ACK_CMD:
        if len(msg) < 7:
            raise ValueError("truncated status frame")
        return {"type": "status", "status": msg[5]}
    if cmd == WRITE_CMD:
        return {"type": "write_ack", "status": 0}
    if cmd == HANDSHAKE_CMD:
        if len(msg) < 17 or msg[5] != 0x04 or msg[6] != 0x30:
            return {"type": "read_data", "status": 1, "data": b""}
        raw_len = msg[9] | (msg[10] << 7)
        plen = packed_len_for(raw_len)
        crc_off = 11 + plen
        if len(msg) < crc_off + 6:
            return {"type": "read_data", "status": 1, "data": b""}
        data = unpack7(msg[11:crc_off], raw_len)
        expected_crc = binascii.crc32(data) ^ 0xFFFFFFFF
        received_crc = num7_decode(msg[crc_off:crc_off + 5])
        status = 0 if expected_crc == received_crc else 1
        return {"type": "read_data", "status": status, "data": data, "crc_ok": status == 0}
    return {"type": "unknown", "status": 1}


def build_erase(addr, size, model=MODEL_BYTE):
    """recon/26 section 3: erase `size` bytes starting at flash `addr`."""
    return (bytes([0xF0, 0x52, 0x00, model, ERASE_CMD])
            + num7(addr, 5) + num7(size, 5) + bytes([0xF7]))


def build_write_chunk(addr, data, model=MODEL_BYTE):
    """recon/26 section 4: write one chunk (<= MAX_CHUNK bytes) of raw data at flash `addr`."""
    if len(data) > MAX_CHUNK:
        raise ValueError("chunk too large: %d > %#x" % (len(data), MAX_CHUNK))
    return (bytes([0xF0, 0x52, 0x00, model, WRITE_CMD])
            + num7(addr, 5) + num7(len(data), 2) + pack7(data) + crc_field(data) + bytes([0xF7]))


def write_chunks(addr, data, chunk=MAX_CHUNK, model=MODEL_BYTE):
    """Every write-chunk message needed to send `data` starting at flash `addr`, in order."""
    for i in range(0, len(data), chunk):
        yield build_write_chunk(addr + i, data[i:i + chunk], model)


def main(argv):
    if len(argv) == 3 and argv[0] == "erase":
        msg = build_erase(int(argv[1], 0), int(argv[2], 0))
        print(msg.hex(" "))
        return 0
    if len(argv) in (3, 4) and argv[0] == "write":
        addr = int(argv[1], 0)
        data = Path(argv[2]).read_bytes()
        chunk = int(argv[3], 0) if len(argv) == 4 else MAX_CHUNK
        for msg in write_chunks(addr, data, chunk):
            print(msg.hex(" "))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
