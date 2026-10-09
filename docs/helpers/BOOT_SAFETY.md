# Brief: boot/update program (res5) safety read

Follow `docs/helpers/SAVE_PROTOCOL.md` (including Token economy) exactly.
- Report: **`recon/25_boot_safety.md`**. Create it with the headings below,
  commit it, then commit THAT FILE ONLY after every finding.
- Scratch: `build/boot_safety/`. **Static only.** Never touch the pedal,
  MIDI/USB devices, flash tools or any .exe; never push.

## Why
Before the owner runs test images on the pedal we must know exactly how the
recovery path works, and whether any image we install could damage it.
The boot/update program (res5) decides between update mode and normal
boot; update mode is how a bricked pedal was recovered on 2026-10-06
(docs/RECOVERY_G1.md).

## Inputs
- `build/codex7/boot.dis` (dis6x of res5; sections listed by
  `grep -n '^TEXT Section\|^DATA Section'`), `build/fw/res5_163840.bin`.
- Known so far (recon/15 "Startup decision in the boot program"): c020a4d0
  decides; c022ba0c(0)/(1) read the footswitches; both low and buttons
  GPIO0,27,24,26,37,38,86,2,4,6 high -> c0201404 (update mode); otherwise
  normal load c020a568 -> c022ba40; c022baac..c022bac8 is the normal AIS load
  of main firmware (recon/15, recon/17).
- recon/07 (hardware: IS25LP032 SPI flash, CN2 header), docs/RECOVERY_G1.md,
  `tools/make_fs_restore_updater.py` and `tools/make_g1_image.py` (what our
  update images contain; read, do not run).

## Questions (report sections)
1. **Boot decision.** c020a4d0 in full: every path, every GPIO read, and any
   other condition (flags in flash, a "bad firmware" marker, a checksum) that
   can force update mode or normal boot.
2. **Normal load and failure.** How res1 (main firmware) is located in flash
   and loaded (c022ba40 .. c022bac8): checksum or signature checks? What
   happens if res1 is corrupt or does not return: is there a fallback to
   update mode, a watchdog, or a hang?
3. **Update mode (c0201404).** What it runs (USB? which protocol), what it
   writes to flash: which address ranges, erase/write/verify steps, and any
   check of the incoming image. **Can update mode overwrite res5 itself?**
4. **Flash layout.** Every flash address range res5 touches (SPI commands:
   look for the SPI peripheral base and command bytes such as 0x02 page
   program, 0x20/0xd8 erase, 0x03 read). Where res5 itself lives, where res1
   and the file system live.
5. **Main-firmware reach.** grep main firmware (`build/fw/map/main.dis`) for
   the same SPI peripheral and erase/program commands: can normal firmware
   erase or write the res5 region? Which functions (map names from
   `recon/map/`)?
6. **Verdict for pedal tests.** What can and cannot brick the pedal beyond
   update-mode recovery, and the checks to run before each test image (for
   example: our images never contain res5, the boot sector is untouched).

Every claim: instruction address, short excerpt (≤ 8 lines), confidence
(confirmed / likely / guess). C6000 pitfalls: a CALLP to a c016e0XX-style
save/restore helper is not logic; `[!B0] B X` / `[B0] B Y` pairs take exactly
one; an ADDKPC in delay slots makes a call; BNOP n leaves 5-n delay slots;
MVK sets the low 16 bits sign-extended, MVKH the high 16.
