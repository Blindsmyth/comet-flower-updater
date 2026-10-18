# Brief for Argon (agy): where the G1X Four keeps its live patches, and how to write them (2026-10-17)

Goal (owner chose "option C"): put test patches into the pedal's **live** patch store without a factory reset,
so the automated CPU bench (tools/ua_bench.py, docs/CF_BENCH_2026-10-17.md) can run. Static analysis only.

## Rules
- Read first: `docs/helpers/SAVE_PROTOCOL.md`, `docs/helpers/FWMAP.md` Pitfalls, `recon/08_factory_presets.md`,
  `recon/15_controls_midi.md` (USB-MIDI/SysEx path), `recon/04_hardware_log.md` rows of 2026-10-04..06.
- Disassembly `build/fw/map/main.dis` (stock v2.00 main firmware, load c0... / L2 1181...); tools `tools/fwmap/`.
- Never touch the pedal, MIDI tools, any `.exe`; never push. Edit only your report.
- **First action:** create `docs/helpers/PATCH_STORE_ARGON_2026-10-17.md`, commit it (that file only), append +
  commit after every finding. Last line when done: `STATUS: done`.
- Quote instruction addresses for every claim; mark `confirmed` / `likely` / `guess`. Recompute every derived
  address and show the arithmetic (a past report had one wrong derived cell). Watch predicated instructions.

## Hardware facts (2026-10-17, CF firmware = stock + controller/USB layers; the patch code is stock)
- Zoom's editor SysEx over USB-MIDI (zoom-zt2 `zoomzt2.py`): `52 00 6e 52` PC mode on, `46` patch download,
  `45` patch upload (bank/location, 7-bit packed 760-byte ZPTC, CRC32), `64 13` current-patch dump (works),
  `64 12 01 ...` current-patch upload (**ignored, no reply**), Program Change (**ignored**, PC mode on or off).
- **`45`/`46` read and write the factory-preset region** (flash 0x28000, 0xB000 bytes, 50 x 736-byte records,
  recon/08): location 10 reads "CF test", exactly as our presets image; writes persist across power cycles; the
  pedal's own patch 10 / 40-42 still show "Empty" (owner, after a reboot).
- But on **2026-10-04** a `46` backup returned the owner's live patches (`backup/2026-10-04/patches/`, e.g. 50
  "comfy numb", 6-entry ZPTCs): so `46` once read the live store. Something differs (state, mode, or the
  factory region happening to match then): find out what selects the source.
- recon/04 2026-10-06: live patches are believed to sit in flash **0x0C0000-0x102000**, which no updater stage
  writes; a factory reset copies factory presets into them. The main firmware's region table is at image offset
  0x77C82 (FS at 0x102000 + 0x2FE000).

## Tasks (in order; save after each)
1. **Region table**: decode the table at 0x77C82 fully (every region: base, size, purpose). Confirm the live
   patch region's base/size.
2. **Live store format**: the routines that load patch N on selection and at boot, and the store/save routine
   (the pedal saves on edit when AUTO SAVE is on, and via its STORE function). Record layout, per-record header,
   checksum/CRC, slot count field, any wear-levelling, journal or generation counter, erase granularity (sector
   size of the flash routines).
3. **SysEx `45`/`46` handlers**: find them (the SysEx dispatch, recon/15) and say which store they hit and
   under which condition (mode flags, a "current bank" variable...). Also list every SysEx command the
   dispatcher accepts (opcode -> handler -> one-line purpose), especially any **store / save / select patch /
   reload** command.
4. **Factory reset**: the copy routine factory -> live (proves the live format from the factory one).
5. **Recommendation**: the cheapest way to get N generated patches live: (a) a SysEx sequence the stock firmware
   already accepts, (b) an update-mode stage writing the live region (exact bytes/CRC to produce), or (c) a
   tiny firmware hook. Say what the pedal test would be.

## Done =
Report with the region table, the live format, the SysEx dispatch table and the 45/46 source condition, the
factory-reset copy, and a concrete recommendation. `STATUS: done`.
