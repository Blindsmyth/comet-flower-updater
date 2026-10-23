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
| 0.34.2 | 0.34.2 | 1907a6e2 | a64a9e62 | fs_bench34 | 34b + build-number start-up screen | **flash this** |
