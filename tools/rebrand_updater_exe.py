"""Rebrand the host-side cosmetic text in a Zoom G1X Four updater .exe to Comet Flower.

    python tools/rebrand_updater_exe.py <src updater.exe> <dst.exe>

Same-length UTF-16 text substitution only (every other patch in this project follows this
discipline: never resize a PE structure, only overwrite bytes within it) -- the version info
block, one About-dialog string, and one string-table entry. Verified byte-for-byte: every
changed byte falls inside one of the six targeted spans, nothing else in the file moves.

This is purely the Windows program's own cosmetic chrome (About box, file properties,
window text) -- it never touches anything that gets written to the pedal (firmware,
graphics, file system, or the stage table from recon/26), and it does not touch the boot
program's own USB descriptor strings (the "ZOOM G Series" MIDI port name shown while the
pedal itself is in update mode) -- that is owned by the pedal's res5 boot program, a much
higher-risk region to edit for a purely cosmetic change (recon/25_boot_safety.md section 6).
The real fix for that is finishing the from-scratch flashing tool (recon/26,
tools/update_mode.py) so no Zoom-derived exe is involved at all.

Every (file_offset, char_count, null_terminated) triple below is specific to the exact x86
code+resource layout of "ZOOM G1X FOUR System v2.00 Updater.exe" -- the same in every updater
.exe this repo has ever built, since we've only ever edited its embedded BIN resources
(firmware/graphics/fs), never its own code or other resources. If Zoom ever ships a different
updater version, re-derive these offsets (see recon/26's method note for the general approach:
locate the resource via pefile's DIRECTORY_ENTRY_RESOURCE, then parse VS_VERSIONINFO /
STRINGTABLE / DIALOGEX structurally rather than guessing).
"""
import sys
from pathlib import Path

# (file_offset, exact_char_count, null_terminated, replacement_text)
PATCHES = [
    (4184984, 17, True, "Comet Flower Labs"),                                  # VERSION CompanyName
    (4185216, 43, True, "(C) Comet Flower Labs. All rights reserved."),        # VERSION LegalCopyright
    (4185336, 8, True, "Comet FX"),                                            # VERSION ProductName
    (4178056, 34, False, "About Comet Flower Updater(&A)..."),                 # STRINGTABLE id 101 (help text)
    (0x3FBA4E, 22, True, "About Comet Flower Upd"),                            # DIALOG 100: about-box caption
    (0x3FBADC, 57, True, "Copyright (C) Comet Flower Labs. All rights reserved."),  # DIALOG 100: static text
]


def fit(text, n):
    if len(text) > n:
        raise ValueError("%r is %d chars, need exactly %d" % (text, len(text), n))
    return text + " " * (n - len(text))


def rebrand(data):
    """Returns a new bytes object with every PATCHES entry applied and verified."""
    out = bytearray(data)
    for off, n, null_terminated, text in PATCHES:
        encoded = fit(text, n).encode("utf-16le")
        if len(encoded) != n * 2:
            raise AssertionError("encoding length mismatch for %r" % text)
        out[off:off + n * 2] = encoded
        if null_terminated:
            term = out[off + n * 2:off + n * 2 + 2]
            if term != b"\x00\x00":
                raise AssertionError(
                    "expected an intact null terminator after %r at %#x, found %r"
                    % (text, off, term))
    return bytes(out)


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    src, dst = Path(argv[0]), Path(argv[1])
    data = src.read_bytes()
    out = rebrand(data)
    diffs = sum(1 for a, b in zip(data, out) if a != b)
    dst.write_bytes(out)
    print("wrote %s (%d bytes changed)" % (dst, diffs))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
