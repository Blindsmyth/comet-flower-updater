# Looper and drum machine teardown (live, CF Probe link)

Read from the running pedal with `tools/cf_probe.py` (Updater 29, MIDI mode, 2026-10-22 night).
Each row: address, what we saw, the meaning we draw, confidence. "seen" = measured on the pedal.
Snapshots: `build/probe/snap_<name>.json` (`build/probe/snap.py`: L2 data 0x11810000+0x6000,
L1D 0x11f00000+0x4000, SDRAM data 0xc0100000+0x1adc0, init data 0xc0183b74+0x34b0; 5 s per snapshot).

## Drum machine

State at snapshot `drums_on_blues2_124_v80` (owner: drums on, pattern Blues 2, 124 BPM, volume 80).

| address | seen | meaning | confidence |
|---|---|---|---|
| 0x11812f78 | 124 | tempo, BPM | likely (matches; to confirm by changing tempo) |
| 0x11812f50, 0x11812f5c | 80, 80 | drum volume (two cells) | guess (to confirm by changing volume) |
| 0x11812f4c | 44 | pattern number (Blues 2?) | guess |
| 0x11812fb8..fc8 | 44, 80, .., 80 | second copy of the f4c..f5c block, 0x6c later | guess |
| 0x11812f0c, 0xc01181e8 | 124 | other tempo copies | guess |
| 0x1181320c | +~1 per ms, continuous | millisecond clock | likely |
| 0x118130ac, 0x118131bc, 0x11813230 | +0x1e4 (484) every beat | ms time of the latest beat (124 BPM = 484 ms) | likely |
| 0x11813098, 0x11813120 | 0 -> 1 -> 0 pulses, beat-spaced | hit/trigger flags | guess |
| 0x11f03d58, 5c, 60, 68, 70, 74 | count up and wrap, per voice | sample play positions of the voices (NOT on/off flags as watch list v1 assumed) | likely |
| 0x11f03d64, 6c, 78 | count up steadily | voice sample addresses or long counters | guess |
| 0x118133ac | counts up fast, always | free-running counter (not drum specific) | seen |
| 0xc011ada4 | changes every read, idle too | counter (NOT the pattern index of watch list v1) | seen |

## Looper

Not started yet.
