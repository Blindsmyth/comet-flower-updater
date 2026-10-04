# Future Ideas

## Exporting Metadata
- Implement `zd2 dump <file> --json` to export the `PRMJ` (JSON) and `INFO` blocks to a structured file for easier reading.

## Icon Extraction
- Add a command to extract the `ICON` block and save it as a `.bmp` or `.png` file. The format likely matches the screen dimensions (e.g., 128x32 or similar).

## Parameter Editing
- Once the writer is implemented, allow users to modify default parameter values in the `PRMJ` block (though this might be risky without knowing how the DSP code in `DATA` uses them).

## Support for .ZT2
- Add parsing for `.ZT2` (Effect List) files to allow users to see how effects are grouped on their pedal.

## Automatic Checksum Validation
- Implement the CRC32 algorithm (Poly 0x104C11DB7) to validate files before parsing and ensure they haven't been corrupted.
