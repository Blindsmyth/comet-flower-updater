# Looper and drum machine teardown (live, CF Probe link)

Read from the running pedal with `tools/cf_probe.py` (Updater 29, MIDI mode, 2026-10-22 night).
Each row: address, what we saw, the meaning we draw, confidence. "seen" = measured on the pedal.
Snapshots: `build/probe/snap_<name>.json` (`build/probe/snap.py`: L2 data 0x11810000+0x6000,
L1D 0x11f00000+0x4000, SDRAM data 0xc0100000+0x1adc0, init data 0xc0183b74+0x34b0; 5 s per snapshot).

## Drum machine

State at snapshot `drums_on_blues2_124_v80` (owner: drums on, pattern Blues 2, 124 BPM, volume 80).

| address | seen | meaning | confidence |
|---|---|---|---|
| 0x11812f78, 0x11812f0c | 124 -> 90 when the owner set 90 | **tempo, BPM** (two copies) | confirmed (seen) |
| 0x118130a4, 0x118130a8 | 30 -> 41 | ms per 16th note (60000 / BPM / 16) | likely (both values fit) |
| 0x118133b8, 0x118133c0 | 744 -> 540 | BPM x 6 (internal tempo unit) | likely (both fit exactly) |
| 0x118133b0, 0x118133bc | recomputed on the tempo change | timing accumulators | guess |
| 0x11812f50, 0x11812fbc | 80 -> 60 when the owner set volume 60 | **drum volume setting, 0..100** (two copies, 0x6c apart) | confirmed (seen) |
| 0x11f03d14 | float 0.8 -> 0.6 at the same time | drum gain used by the audio path = volume / 100 | confirmed (seen) |
| 0x11812f5c | 80, unchanged by the volume change | something else that was 80 | seen |
| 0x11812f4c, 0x11812fb8 | 44 -> 7 when the owner went Blues 2 -> Rock 1 | **pattern number** (Blues 2 = 44, Rock 1 = 7; two copies) | confirmed (seen) |
| 0x11812f40..f80 / 0x11812fac..fec | pattern, volume, tempo in both | rhythm settings, two copies 0x6c apart (live + saved?) | likely |
| 0xc01181e8 | 124 at the first snapshot | another tempo copy? (not in the diff) | guess |
| 0x1181320c | +~1 per ms, continuous | millisecond clock | likely |
| 0x118130ac, 0x118131bc, 0x11813230 | +0x1e4 (484) every beat | ms time of the latest beat (124 BPM = 484 ms) | likely |
| 0x11813098, 0x11813120 | 0 -> 1 -> 0 pulses, beat-spaced | hit/trigger flags | guess |
| 0x11f03d58, 5c, 60, 68, 70, 74 | count up and wrap, per voice | sample play positions of the voices (NOT on/off flags as watch list v1 assumed) | likely |
| 0x11f03d64, 6c, 78 | count up steadily | voice sample addresses or long counters | guess |
| 0x118133ac | counts up fast, always | free-running counter (not drum specific) | seen |
| 0xc011ada4 | changes every read, idle too | counter (NOT the pattern index of watch list v1) | seen |

**LCD framebuffer: 0x11800000, 512 B** (128 x 32, 4 pages x 128 column bytes, bit 0 = top row). It
redraws when the screen changes; `tools/cf_probe.py screenshot [--png f]` renders it. First shot (rhythm
screen): `RHYTHM` title, `PATTERN Count BPM VOLUME` / `Rock 1 On 090 60` — matches the pedal.

Side effects of the probe itself (ignore in diffs): MIDI TX ring around 0xc0117d60 holds our
CFPR replies; 0x11815a00.. is stack; 0x11f039b0.. audio buffers.

## Looper

Not started yet.
