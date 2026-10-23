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
| 0.34.6 | 0.34.6 | cf4a8b9a | 55ae7d48 | fs_bench343 | = 0.34.3 content (CF logo back), start-up "TEST 0.34.6" | **flash this** |

One-time, separate: `COMET FLOWER BOOT LOGO - flower - run once.exe` (`85176b9e`) replaces the boot program's ZOOM logo with a flower (`tools/make_boot_logo_updater.py`; the one boot-area write, see docs/FW_RND_BENCH_2026-10-22.md section 17). Independent of the version above; stays through later TEST builds.
