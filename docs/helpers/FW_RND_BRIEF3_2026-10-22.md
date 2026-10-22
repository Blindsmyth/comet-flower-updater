# Firmware R&D brief 3, 2026-10-22 (jobs S8, S9, S10, F5) — while the owner tests Updater 26

Context: `docs/FW_RND_ANSWERS_2026-10-22.md` (read it whole; it is the current
truth) and the test the owner is running now, `docs/FW_RND_BENCH_2026-10-22.md`.
Hard rules, tools and C6000 pitfalls: `docs/helpers/FW_RND_BRIEF_2026-10-22.md`
(static analysis only, no pedal, SAVE_PROTOCOL: report first, commit THAT
FILE ONLY after every finding, never push, scratch in `build/fw_rnd/<job>/`,
confidence words with disassembly evidence, "not found" is fine).
Address -> file offset of the main firmware: `tools/fwmap/ais.py`
(`sections()` gives (load addr, size, file offset)) on `build/fw/res1_493412.bin`.

## S8 - Slot occupancy of multi-slot effects (Sonnet)
Report `docs/helpers/FW_RND_S8_OCCUPANCY_2026-10-22.md`. Purpose: predict and
then explain what the owner sees with CF M3 / CF M4 (header 0x58 = 3 / 4).
- Stock 2-slot effects store id 0x1 in the next patch slot ("second half",
  recon/04:33, EDTB records `tools/g1presets.py`). Find who writes that
  filler and who reads it: patch load/save, slot insert/delete, the list of
  effects offered for a slot (the effect picker; S1 did not find it:
  `docs/helpers/FW_RND_S1_LIST_PARAMS_2026-10-22.md` lists what is ruled out),
  the "in use" flags c01839f0 (S2). Does anything use header 0x58 after
  c0129908 (search loads of the stored header byte / effect-info struct)?
- Why did CFMPRE (header 2) not take the next slot on screen (handoff)?
  Compare a stock 2-slot amp's path: is the occupancy decided from the
  header, the effect id range, the param count, or the icon width (47/50 px)?
- Prediction table for header 1..5: listed?, slots shown used, slots still
  free, what the Process Overflow sum (c0141ad8) counts.

## S9 - Bypass path and delay tails (Sonnet)
Report `docs/helpers/FW_RND_S9_BYPASS_2026-10-22.md`. Purpose: can a CF delay
keep its tail ringing after it is switched off, as the CN chain needs?
- In the audio Swi slot loop (11818ba0, slot call ~11818c04, veneer 11818eb0)
  and the param path: when an effect is OFF, is its audio function still
  called each block? How is `coef[SH_COEFF_BYPASS]` (coef[0], the "fade"
  our kernels mix with) produced: a ramp 0..1 over how many blocks, written
  where (knob table 11f00000 + n*0x348), by which function?
- Does the firmware ever skip the call, or call a different (bypass)
  function, e.g. the ZD2 "BYPASS"/"BPS" blocks (strings near c0129b40)?
- Answer: with the current firmware, can a kernel implement a tail
  (process with input muted while coef[0] = 0)? If the call is skipped, what
  is the smallest patch to keep calling it, and its cost.
- Look at how a stock delay (DELAY_3S / TPEC3_3S in build/bench/stock or
  backup/2026-10-04/files, disassemble its ELF like S4 did) uses coef[0], if
  quick.

## S10 - Slot watchdog design on top of the bench hook (Sonnet)
Report `docs/helpers/FW_RND_S10_WATCHDOG_2026-10-22.md`. Design only: do NOT
build or package firmware.
- The bench firmware already re-aims the slot veneer 11818eb0 (called before
  each slot by the loop at 11818c04) to `ua_slot_enter`
  (`firmware/usb_audio_proto/usb_audio_tap.c`, `tools/make_usb_audio_fw.py`
  BENCH_PATCHES, `tests/test_usb_audio_bench.py`). Read how it times slots.
- Design a watchdog: per slot, keep the measured cycles; if a slot exceeds a
  limit (e.g. k x its declared dspload on Zoom's scale `7 + 3 x kcycles`, or a
  fixed cap) for N blocks in a row, bypass it (how: skip its call, or force
  its fade/bypass state the firmware's own way, see S9's area but do not
  wait for S9) and flag it for the screen/MIDI. Give the exact hook points,
  pseudo-C, cycle cost, failure modes and how to test it on the bench.
- Also: SYS/BIOS exception handling. Find the C674x exception vector / NMI
  handler and what it does (Exception module strings in
  build/fw/map/strings.txt ~610-680, IERR read at c015cce0, EFR/NRP
  register use in main.dis: `grep -n "EFR\|IERR\|NRP\|ECR" main.dis`).
  Halt, reset, or continue? Could a fault in one slot be caught and the slot
  bypassed instead?

## F5 - Label column width data (Gemini 3.8 Flash)
Report `docs/helpers/FW_RND_F5_LABELWIDTH_FLASH_2026-10-22.md`. Data
extraction only, no conclusions about code paths.
1. Write `build/fw_rnd/F5/dump.py`: map address -> file offset with
   `tools/fwmap/ais.py` sections() on `build/fw/res1_493412.bin`, and dump
   the 256 bytes at 0xc0181508 (S7's undecoded column-width table) as bytes,
   16-bit and 32-bit little-endian words; flag values that look like pixel
   x positions or widths (0..128) and pointers (0xc0xxxxxx / 0x118xxxxx).
2. Glyph advance widths of the 5x7 font drawn by c011d4d8: find its glyph
   table (see `docs/helpers/MENU_RE_ARGON_2026-10-16.md`,
   `recon/10_firmware_capabilities.md`, `build/fw/map/glyphs.py`,
   `tools/fwmap/glyphs.py`, font PNGs in build/fw/map/); report the advance
   per character (fixed 6 px or proportional) for A-Z a-z 0-9 space and . :
3. Table: for column widths of 24, 30, 31, 32, 42 and 64 px, how many
   characters of that font fit, and the pixel width of every CFMPRE and CF
   Rotary label (`effects/cfm_pre/manifest.json`, `effects/rotx/manifest.json`)
   and of the longest stock label `D57:D421`.
Commit the report after each step.
