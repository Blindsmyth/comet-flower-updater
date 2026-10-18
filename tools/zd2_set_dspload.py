"""Change only the declared DSP load of a .ZD2 (the INFO block's float at +16) and its CRC.

    python tools/zd2_set_dspload.py <in.ZD2> <out.ZD2> <load>

The pedal sums the declared loads of the five slots and refuses a patch at 230.0 or more
("PROCESS OVERFLOW": main firmware c0141ad8..c0141b60, MVKH 0x43660000 = 230.0f, CMPLTSP).
For an effect that is already released, change the number without rebuilding its code:
every other byte stays as it is, and the result is re-parsed and its CRC checked.
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from zd2tools.parser import HEADER_SIZE, TRAILER_SIZE, parse_zd2, zd2_crc  # noqa: E402


def info_offset(data):
    """File offset of the INFO block's payload (tagged blocks tile from the header to the trailer)."""
    off, end = HEADER_SIZE, len(data) - TRAILER_SIZE
    while off + 8 <= end:
        tag = data[off:off + 4]
        n = struct.unpack_from("<I", data, off + 4)[0]
        if tag == b"INFO":
            return off + 8
        off += 8 + n
    raise ValueError("no INFO block")


def set_load(data, load):
    out = bytearray(data)
    p = info_offset(data) + 16
    struct.pack_into("<f", out, p, float(load))
    struct.pack_into("<I", out, 8, zd2_crc(bytes(out)))
    changed = [i for i in range(len(out)) if out[i] != data[i]]
    if any(not (8 <= i < 12 or p <= i < p + 4) for i in changed):
        raise ValueError("unexpected change outside the load and the CRC")
    z = parse_zd2(bytes(out))
    if abs(z.info.dspload - float(load)) > 1e-6 or zd2_crc(bytes(out)) != struct.unpack_from("<I", out, 8)[0]:
        raise ValueError("re-parse failed")
    return bytes(out)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    src = Path(sys.argv[1]).read_bytes()
    old = parse_zd2(src).info.dspload
    Path(sys.argv[2]).write_bytes(set_load(src, float(sys.argv[3])))
    print("%s: dspload %.2f -> %.2f (only the load and the CRC changed)" % (sys.argv[1], old, float(sys.argv[3])))
