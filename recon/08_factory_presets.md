# G1X FOUR factory presets

Inspected read-only on 2026-10-06:
`build/fw/res2_45056.bin`, updater resource 133 (0x85), flash
0x28000..0x32FFF, exactly 0xB000 bytes.

## Region layout

| Resource offset | Contents |
|---|---|
| 0x0000..0x01FF | 512-byte start-up screen |
| 0x0200..0x91BF | 50 allocations, each 736 (0x2E0) bytes |
| 0x91C0..0x9FFF | 0xFF padding |
| 0xA000..0xA013 | `6e000d0047315820495600000000000000000000` |
| 0xA014..0xAFFB | 0xFF padding |
| 0xAFFC..0xAFFF | ASCII `1.00` |

The metadata at 0xA000 includes ASCII `G1X IV`; the preceding
little-endian u16 values are 0x006E and 0x000D. Their meanings are
unconfirmed. Preserve all metadata.

## Active record format

Offsets below are relative to each 736-byte allocation.
All integer fields described here are little-endian.

| Offset | Size | Meaning / observation |
|---|---:|---|
| 0x00 | 4 | `PTCF` |
| 0x04 | 4 | Total active PTCF length, including header |
| 0x08 | 4 | 1, apparently format version |
| 0x0C | 4 | Slot count: 5 in every factory record |
| 0x10 | 10 | Constant `20 00 00 00 00 00 00 00 00 00` |
| 0x1A | 10 | Patch name |
| 0x24 | 20 | Five u32 effect IDs |
| 0x38 | variable | Length-delimited chunks |

Each chunk is a four-byte tag, u32 payload length, then payload.
The length excludes the eight-byte chunk header.

Every factory record has exactly this active chunk sequence:

1. TXJ1: Japanese description, variable length.
2. TXE1: English description, variable length.
3. EDTB: 120 bytes, five 24-byte slot entries.
4. PPRM: 12 bytes of patch parameters, preserved unchanged.

There is no active NAME chunk. Names occupy the fixed header.
Short names normally use ASCII spaces; record 28 (`HotSpice`) uses
two trailing NUL bytes. The blanker preserves each record's observed
padding style. Full ten-byte names have no padding.

Active PTCF lengths range from 220 to 440 bytes. Chunk traversal ends
exactly at the declared length. Everything from that endpoint to the
next 736-byte allocation is preserved, including stale effect-like
bytes and additional PPRM-looking sequences. Searching for tags across
the whole allocation would incorrectly treat these as active data.

## Empty slots and backups

Factory records 41..50 are already named `Empty` and contain five
empty slots each. All 50 examples agree:

- ID table entry: u32 zero.
- EDTB entry: byte 0x01 followed by 23 zero bytes.

This agrees with `tools/patch_g1.py make_blank()` and backup patch 30.
The EDTB entry is not 24 zero bytes.

All 50 backup ZPTC files are 760 bytes, but their slot counts differ:
19 have five slots, 30 have six, and one has seven. Backup patch 30
has five. Backup patches 5, 10 and 11 have active PTCF bytes identical
to the corresponding factory records. Do not infer slot count from
the backup file size or copy its allocation layout into this region.

Records 41..50 have identical active bytes (220 B: empty TXJ1 and TXE1,
five empty EDTB entries, Zoom's default PPRM); only their stale allocation
tails differ. `g1presets.py blank` therefore copies record 41's whole
736-byte allocation into all 50 records (name set by --name, default
`Empty`, the name Zoom itself uses). Every patch is then a patch Zoom
authored, so no record carries edited bytes the firmware has never seen.
The splash and the region trailer stay byte-identical.

## Checksum investigation

No checksum field was identified. The PTCF length equals the exact
end of the four active chunks; chunk lengths equal their payload
sizes. None of these lengths changes when blanking.

Read-only JavaScript probes tested twelve CRC32 configurations:

- IEEE polynomial, reflected (0xEDB88320).
- IEEE polynomial, non-reflected (0x04C11DB7).
- Castagnoli polynomial, reflected (0x82F63B78).
- For each: initial register 0 or 0xFFFFFFFF, final XOR 0 or
  0xFFFFFFFF.

For every record, tested body starts 0, 8, 16, 26, 36 and 56 against
ends at active length, active length minus 4, active length minus 20,
736 and 732. Searched every possible four-byte position in the
allocation for each result in both byte orders: no matches.

Also tested candidate fields at offsets 0, 4, 8, 12, 16, 20, 22,
each PPRM u32, the active endpoint, and 732. Where within the tested
extent, omitted or zeroed the candidate four bytes before calculating
the CRC over the active record or full allocation: no matches.

Region probes used starts 0 and 512, with endpoints 37312, 40960,
45052 and 45056, and searched all four-byte windows in the trailer
from 37312 onward, in both byte orders: no matches.

These are finite empirical checks, not proof of checksum absence.
A custom checksum, other coverage, other polynomial, or validation
stored outside this resource cannot be ruled out. Firmware validation
was not traced and no modified preset resource was tested on a pedal.
The proposed blanker therefore changes no presumed checksum fields.

## Verification and updater integration

`g1presets.py blank` re-parses its output and checks that all 50 records
are byte-identical to the named template, and that the splash and trailer
are unchanged (`tools/g1presets_test.py`, 23 checks).

`make_fs_restore_updater.py --presets FILE` requires exactly 0xB000
bytes and replaces resource 0x85. Optional --splash is applied afterward.
Either flag adds one erase/write pair for 0x28000 before the existing
file-system stages. Neither flag changes the boot program stages.
When both flags are absent, existing behavior is unchanged.

Decoded by Codex (read-only), applied and changed to the copy approach by
Claude. Not yet run on the pedal: the presets reach the patch memory only at
a factory reset after the update-mode install.
