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

MODEL_BYTE = 0x00  # recon/26 section 7: no write site found for this global in the exe;
                    # assumed 0, matching this project's device-id convention everywhere else.
HANDSHAKE_CMD = 0x60
ERASE_CMD = 0x0A
WRITE_CMD = 0x02
MAX_CHUNK = 0x1000  # the real updater never sends a write-chunk message larger than this


def num7(v, n):
    """n-byte 7-bit little-endian encoding (recon/26 section 5a)."""
    return bytes((v >> (7 * k)) & 0x7F for k in range(n))


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


def crc_field(data):
    """5-byte 7-bit-LE checksum field (recon/26 section 5c)."""
    return num7(binascii.crc32(data) ^ 0xFFFFFFFF, 5)


def build_handshake(model=MODEL_BYTE):
    """recon/26 section 2. Sent once before any erase/write stage by the real updater.
    Purpose, the fixed byte at offset 5 (0x30), and the meaning of the two numeric fields
    are unconfirmed; the bytes match the template read from the exe."""
    return (bytes([0xF0, 0x52, 0x00, model, HANDSHAKE_CMD, 0x30])
            + num7(0x27FFC, 5) + num7(4, 5) + bytes([0xF7]))


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
