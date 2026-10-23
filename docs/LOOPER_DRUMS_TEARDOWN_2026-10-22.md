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
| 0x11f03d54 | 1 -> 0 when the owner stopped the drums | **drums running** | confirmed (seen) |
| 0x11f03d0c | float 1.0 -> 0 at stop | playback gain / run fade (not the volume) | likely |
| 0x118130a0 | 256 -> 0 at stop | timing state (running) | guess |
| 0x118130a4, a8 | 41 -> 0 at stop | the ms-per-16th cells are zero while stopped | seen |
| 0x11813098, 0x11813120 | pulsed with hits while playing, 1 when stopped | hit/stop flags | guess |
| 0x11f03de0..0x11f03e30 | twenty floats 1.0 -> 0 at stop | per-voice or per-step gains | guess |
| LCD | play indicator circle top right: filled while playing, hollow when stopped | | seen |
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

Screen (screenshot `docs/img/lcd_looper_open_2026-10-22.png`): `LOOPER` / `Time StopMode Post VOL` /
`MANUAL Instant Post 80`. Opening it set 0x11813098 / 0x11813120 to 64 and the ms-per-16th cells
0x118130a4/a8 back to 41 (the looper runs on the rhythm tempo clock).

After recording a loop and letting it play (snapshot `looper_playing`, poll 4 s):

| address | seen | meaning | confidence |
|---|---|---|---|
| 0x11f03c58 | 0 -> 1 | **looper active** | likely |
| 0x11f03c6c | 2,646,000 -> 407,584 for a ~5 s loop | **loop length in bytes** of 16-bit mono (407,584 B = 4.62 s); 2,646,000 B = the 30 s maximum | likely (owner: about 5 s) |
| 0x11f03c9c, 0x11f03ca0, 0x11f03ccc | advance ~88,000 per s (2 x 44,100) | byte offsets of play/record positions in a 16-bit buffer | likely |
| 0x11f03c94, 0x11f03cb0 | same rate, wrap sooner (~176 k, ~55 k) | positions inside a chunk / DMA window | guess |
| 0x11f03c7c, c80, 0x11f03d08 | 2.0f, 0x7fffffff, 0x7ffffffe | scale / limits set at record | guess |
| 0x11f03cd8..cec | random-looking, change every read | audio samples / filter state (NOT a volume parameter as watch list v1 had) | seen |

After an overdub pass (snapshot `looper_overdub`):

| address | seen | meaning | confidence |
|---|---|---|---|
| 0xc011ac00.. | every byte 0x14 -> 0x17 after the overdub, then 0..7 at stop | screen drawing scratch or waveform display data (it changes with the screen) | guess |
| 0x11f03e38..0x11f03e78 | 17 words 0x7fffffff -> 0 | meters / limits re-armed by the overdub | guess |

After stopping playback (snapshot `looper_stopped`; screen shows a large STOPPED and a Clear hint):

| address | seen | meaning | confidence |
|---|---|---|---|
| 0x11813250 | 0xf0 -> 0xfc when the loop started, 0xfc -> 0xf0 at stop | **looper state field** (0xf0 stopped, 0xfc playing) | likely |
| 0x11f03c80 | 0x7fffffff while playing -> 0 at stop | playing level / gate | guess |
| No undo | the G1X Four looper has no undo (owner) | the "undo pointer" of watch list v1 is wrong | seen |

Loop buffer (live reads after stop):

| address | seen | meaning | confidence |
|---|---|---|---|
| 0xc011acac | 0xc04d7100 | **loop buffer start** | likely (the loop audio is there) |
| 0xc011acc0 | 0xc075d0f0 | loop buffer end: 0xc04d7100 + 2,646,000 B = the 30 s maximum | likely |
| 0xc011aca8 | 0xc04abff0 | start of a 176,400 B (2 s) region before the loop buffer, right after the five effect work buffers; all zero after stop | guess (pre-roll / crossfade?) |
| 0xc011acb0 | 0x2b110 = 176,400 | size of that 2 s region | seen |

The 4.62 s loop (407,584 B at 0xc04d7100) dumps as a smooth 16-bit mono waveform at a very low
level (peak 25 of 32,767, about -62 dBFS): `build/probe/loop_take1.wav`, and +56 dB louder
`build/probe/loop_take1_normalised.wav`. Whether the level is a storage scale (0x11f03c7c = 2.0?) or
the take was quiet is open; the owner's ear decides if it is the loop.

After CLEAR (snapshot `looper_cleared`; screen back to the settings page, `docs/img/lcd_looper_cleared_2026-10-23.png`):

| address | seen | meaning | confidence |
|---|---|---|---|
| 0x11f03c58 | 1 -> 0 | looper active off | likely |
| 0x11f03c6c | 407,584 -> 2,646,000 | length back to the 30 s maximum (ready to record) | likely |
| 0x11f03c7c | 2.0 -> 0 | set at record, reset at clear | guess |
| 0x11f03c94, 9c, a0, cc | -> 256 / 254 / 256 / 256 | positions reset to the start | likely |
| 0x11f03e38.. | -> 0x666665ff (17 words) | refilled with a fixed pattern | seen |
| loop buffer 0xc04d7100 | old audio still there (peak 17) | clear resets counters only; it does not erase the buffer | seen |

## Looper state machine (summary)
0x11813250: 0xf0 idle/stopped, 0xfc playing (record/overdub states not yet caught: they last only
while the footswitch action runs; a poll during record would catch them). 0x11f03c58 active flag;
0x11f03c6c length in bytes (max 2,646,000 = 30 s of 16-bit mono at 44.1 kHz); positions advance 2 bytes
per sample; buffer 0xc04d7100..0xc075d0f0.
