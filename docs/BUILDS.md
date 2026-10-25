# Test builds (version on the start-up screen)

Version = **0.\<updater number\>.\<rebuild\>**. From 0.34.2 on, every TEST updater shows it on the
start-up screen under "CF-ZGX4" (`tools/make_splash.py <version> <png>`, then
`make_fs_restore_updater.py ... --presets build/fw/cfupd_res85.bin --splash <png>`; the presets region is
the CF one, so only the start-up image changes). Bump the rebuild for any change, even FS-only.
Updater files: `build/fw_rnd_2026-10-22/`. Steps and details: `docs/FW_RND_BENCH_2026-10-22.md`.

| Version | Updater | SHA-256 | Firmware | FS image | What | Status |
|---|---|---|---|---|---|---|
| 0.31.0 | 31 | 52995666 | 8ee11e29 | fs_bench30 | CF Probe link + CF edit header | on pedal, approved |
| 0.32.0 | 32 | 7015a3cb | 8ee11e29 | fs_bench32 | + CF WattL | superseded |
| 0.33.0 | 33 | b29f89c8 | a64a9e62 | fs_bench32 | + CPU meter | superseded (no probes) |
| 0.34.0 | 34 | f7fe7443 | a64a9e62 | (broken) | + PROBE10/30 files, no effect-list entry | deleted |
| 0.34.1 | 34b | d11591f9 | a64a9e62 | fs_bench34 | probes listed | superseded by 0.34.2 |
| 0.34.2 | 0.34.2 | 1907a6e2 | a64a9e62 | fs_bench34 | 34b + build-number start-up screen | flashed; ceiling test (~90 %) |
| 0.34.3 | 0.34.3 | 69b52f9d | 55ae7d48 | fs_bench343 | meter inverted from 88 %, PROCESS OVERFLOW gate 230 -> 340, CF effects declare measured load | superseded by 0.34.6 (same content) |
| 0.34.4 | 0.34.4 | 826fd075 | f37ff113 | fs_bench343 | 0.34.3 + Comet Flower bloom start-up animation (replaces the CF logo) | not wanted (owner: keep the CF logo); do not flash |
| 0.34.5 | installer app | 1d909ff0 | f37ff113 | (= fs_bench343) | built by the Comet Flower Installer app; it picked the newest firmware = shelved 0.34.4 bloom: CF logo spot blank (frame 0 never advanced) | flashed by mistake; replace with 0.34.6 |
| 0.34.6 | 0.34.6 | cf4a8b9a | 55ae7d48 | fs_bench343 | = 0.34.3 content (CF logo back), start-up "TEST 0.34.6" | flashed: CF logo back (owner) |
| 0.34.7 | 0.34.7 | f3e9beae | d8068692 | fs_bench343 | 0.34.6 + timed bloom in place of the CF logo (plays from the bud to "COMET FLOWER", 70 ms a frame, ~0.8 s) | on pedal, superseded by 0.34.8 (same content otherwise) |
| 0.34.8 | 0.34.8 | 923dc9fb | c0b11d84 | fs_bench343 | 0.34.7 + CF Probe `'S'` op: select a stored patch (0..49) as the pedal's active patch over SysEx, `c012f878(idx,-1,1,1)` (docs/helpers/FW_RND_S12_SYSEX_HOOK_2026-10-22.md, docs/helpers/PATCH_STORE_ARGON_2026-10-17.md section 2.3/2.4). Fixes: stored-but-not-active patches (patch_g1.py write) had no remote way to become active -- stock firmware silently drops raw MIDI Program Change and the speculative `64 12` current-patch upload. Host: `tools/cf_probe.py select <1..50>`. Only usb_audio_tap.c/host_harness_tap.c/cf_probe.py changed; every stock-word hook is identical to 0.34.7's list | superseded by 0.34.9 (same firmware `c0b11d84`) |
| 0.34.9 | 0.34.9 | fdbadaf4 | c0b11d84 | fs_bench349 | 0.34.8 + C10=12nF Violet Muff tone-stack fix (`docs/MUFF_TARGET_SPEC_2026-10-23.md`) packaged into both `MUFFX.ZD2` (`CF Muff`, CRC `0x223ed201`, dspload 53) and `CFMPRE.ZD2` (`CFM Pre`, compact blob regenerated via `tools/gen_compact_muff_blob.py`, CRC `0x0b4f1329`, dspload 102) in `fs_bench349.bin` (`e33c5800`). Firmware identical to 0.34.8 (`c0b11d84`) | **flash this**: built, host-tested, not on pedal |

One-time, separate: `COMET FLOWER BOOT LOGO - bud - run once.exe` (`91c67870`, supersedes `052c94b2` which skipped the boot stages due to the `0x27FFC` `"1.00"` check at VA `0x403C4F`) replaces the boot program's
ZOOM logo with the bloom's bud, so 0.34.7+'s bloom continues from it (`tools/make_boot_logo_updater.py`; the one
boot-area write, see docs/FW_RND_BENCH_2026-10-22.md sections 17 and 19, and recon/26 section 2). Independent of the version above;
it stays through later TEST builds. The earlier "flower" version was never run and is deleted.
