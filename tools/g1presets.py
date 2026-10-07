#!/usr/bin/env python3
"""Inspect and blank the G1X FOUR v2.00 factory-presets resource.

    python tools/g1presets.py list <res2.bin>
    python tools/g1presets.py blank <res2.bin> <out.bin> [--name Empty] [--set 10="CF test"]...
    python tools/g1presets.py verify <original.bin> <out.bin> [--name Empty] [--set N=NAME]...

blank copies Zoom's own empty patch (factory records 41..50: no effects, no
description, default patch parameters) into all 50 records, with --name as
the patch name. The start-up screen and the region trailer stay
byte-identical. No checksum has been identified; see
recon/08_factory_presets.md.
"""
import argparse
import struct
import sys
from pathlib import Path

SIZE = 0xB000
START = 0x200
COUNT = 50
STRIDE = 736
END = START + COUNT * STRIDE
SLOTS = 5
EMPTY_SLOT = b"\x01" + bytes(23)
TAGS = (b"TXJ1", b"TXE1", b"EDTB", b"PPRM")


def require(ok, message):
    if not ok:
        raise ValueError(message)


def u32(data, offset):
    return struct.unpack_from("<I", data, offset)[0]


def records(data):
    """Parse active PTCF chunks; retain each entire 736-byte allocation."""
    require(len(data) == SIZE, "region must be exactly %#x bytes" % SIZE)
    result = []
    for index in range(COUNT):
        offset = START + index * STRIDE
        raw = bytes(data[offset:offset + STRIDE])
        prefix = "record %d: " % (index + 1)
        require(raw[:4] == b"PTCF", prefix + "missing PTCF")
        length = u32(raw, 4)
        require(56 <= length <= STRIDE and length % 4 == 0,
                prefix + "invalid PTCF length")
        require(u32(raw, 8) == 1, prefix + "unsupported version")
        require(u32(raw, 12) == SLOTS, prefix + "expected five slots")
        require(raw[16:26] == b"\x20" + bytes(9),
                prefix + "unexpected fixed header")

        name_raw = raw[26:36]
        name = name_raw.rstrip(b" \x00")
        require(all(32 <= b <= 126 for b in name),
                prefix + "unsupported name encoding")
        pad = b"\x00" if name_raw.endswith(b"\x00") else b" "
        require(name_raw[len(name):] == pad * (10 - len(name)),
                prefix + "mixed name padding")

        chunks = []
        pos = 56
        while pos < length:
            require(pos + 8 <= length, prefix + "truncated chunk header")
            tag = raw[pos:pos + 4]
            size = u32(raw, pos + 4)
            require(size % 4 == 0 and pos + 8 + size <= length,
                    prefix + "invalid chunk size")
            chunks.append((tag, pos + 8, size))
            pos += 8 + size
        require(tuple(c[0] for c in chunks) == TAGS,
                prefix + "unexpected chunk sequence")
        require(chunks[2][2] == SLOTS * 24,
                prefix + "unexpected EDTB size")
        require(chunks[3][2] == 12, prefix + "unexpected PPRM size")

        result.append({
            "index": index + 1,
            "offset": offset,
            "length": length,
            "raw": raw,
            "name": name.decode("ascii"),
            "pad": pad,
            "ids": struct.unpack_from("<5I", raw, 36),
            "chunks": tuple(chunks),
            "edtb": chunks[2][1],
        })
    return result


def name_bytes(name):
    try:
        encoded = name.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError("name must be printable ASCII") from None
    require(1 <= len(encoded) <= 10,
            "name must contain 1..10 ASCII characters")
    require(all(32 <= b <= 126 for b in encoded),
            "name must be printable ASCII")
    return encoded


def template(parsed):
    """Zoom's own empty patch: the first record with no effects and no text."""
    for record in parsed:
        txj, txe, edtb = record["chunks"][:3]
        if (record["ids"] == (0,) * SLOTS and txj[2] == 0 and txe[2] == 0 and
                record["raw"][edtb[1]:edtb[1] + edtb[2]] == EMPTY_SLOT * SLOTS):
            return record
    raise ValueError("input has no factory empty record to copy")


def expected(record, name):
    """The template's whole allocation with its name set to `name`."""
    raw = bytearray(record["raw"])
    raw[26:36] = name_bytes(name).ljust(10, record["pad"])
    return bytes(raw)


def names_for(name, overrides):
    """Patch names 1..COUNT: `name`, except overrides {patch number: name}."""
    require(all(1 <= n <= COUNT for n in overrides), "--set patch numbers are 1..%d" % COUNT)
    return [overrides.get(i + 1, name) for i in range(COUNT)]


def verify(original, output, name="Empty", overrides=None):
    """Re-parse and check every record is the empty template with its
    expected name and nothing outside the records changed."""
    tpl = template(records(original))
    names = names_for(name, overrides or {})
    after = records(output)
    require(original[:START] == output[:START], "splash changed")
    require(original[END:] == output[END:], "region trailer changed")
    for i, record in enumerate(after):
        require(record["raw"] == expected(tpl, names[i]),
                "record %d: not the empty template named %r" % (record["index"], names[i]))
    return len(after)


def blank(data, name="Empty", overrides=None):
    tpl = template(records(data))
    names = names_for(name, overrides or {})
    output = data[:START] + b"".join(expected(tpl, n) for n in names) + data[END:]
    verify(data, output, name, overrides)
    return output


def parse_sets(items):
    out = {}
    for item in items or []:
        number, _, label = item.partition("=")
        require(number.isdigit() and label, "--set takes N=NAME")
        out[int(number)] = label
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="list all 50 factory records")
    listing.add_argument("input")
    for command in ("blank", "verify"):
        sub = commands.add_parser(command)
        sub.add_argument("input")
        sub.add_argument("output")
        sub.add_argument("--name", default="Empty")
        sub.add_argument("--set", action="append", metavar="N=NAME",
                         help="give patch N (1..50) its own name")
    args = parser.parse_args(argv)

    try:
        original = Path(args.input).read_bytes()
        if args.command == "list":
            for record in records(original):
                print("%02d  %-10s  %s" % (
                    record["index"], record["name"],
                    " ".join("%08x" % value for value in record["ids"])))
        elif args.command == "blank":
            require(Path(args.input).resolve() != Path(args.output).resolve(),
                    "input and output must be different files")
            sets = parse_sets(args.set)
            output = blank(original, args.name, sets)
            Path(args.output).write_bytes(output)
            count = verify(original, Path(args.output).read_bytes(), args.name, sets)
            print("wrote %s: %d empty records, verified" %
                  (args.output, count))
        else:
            count = verify(original, Path(args.output).read_bytes(), args.name,
                           parse_sets(args.set))
            print("%d empty records; layout and untouched bytes verified" %
                  count)
        return 0
    except (OSError, ValueError) as error:
        print("FAIL: %s" % error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
