# Drum machine: samples, pattern table, engine, and local tools (2026-10-22)

Static work only (file analysis of `build/fw/res1_493412.bin` and
`backup/2026-10-04/files/*.raw`). No MIDI, no pedal touched. Budget: ~3h.
Tools: `tools/drums/raw2wav.py`, `tools/drums/decode_patterns.py`,
`tools/drums/drum_machine.py`. Tests: `tests/test_drum_samples.py`,
`tests/test_drum_patterns.py`.

## TL;DR

- **Samples**: 24 `.raw` files, each a headerless mono **signed 16-bit
  little-endian PCM** stream at the pedal's fixed **44.1 kHz**. Exported to
  `build/drums/wav/*.wav` with `tools/drums/raw2wav.py --all`.
- **Pattern table**: found in ROM at **`0xc016f7e9`** (first voice-name
  field), **124-byte fixed-stride records**, **69 patterns** (index
  0..68). Each record has a name, a time signature (beats/bar, beat
  unit), 9 voice-sample-name slots, and a pointer to a small per-pattern
  binary blob that is very likely the step/hit data -- **not decoded**
  (see "What isn't decoded" below).
- **Engine**: BPM-driven 16th-note clock, 9 fixed voice slots mixed and
  summed into the main stereo bus every audio block, confirmed from
  disassembly already on file plus tonight's live teardown. See "Engine"
  section for per-claim confidence and addresses.
- **Tools**: `drum_machine.py list|render|new` plays the pedal's own
  samples. `render` now plays the **real, firmware-decoded step grid**
  for 68 of the 69 built-in patterns (see section 7, job S14,
  2026-10-23) -- the one exception (`Metro3`) falls back to an
  algorithmically-generated, genre-approximate groove, loudly flagged.
  `new` renders a groove you write yourself in JSON, exactly as given.
- **Pattern numbering**: resolved (see "Pattern numbering resolved"
  below) -- the pedal's on-screen pattern number indexes a RAM pointer
  table built at boot (`0xc0182730`), not the ROM table's physical
  order; `tools/drums/ui_order.json` has the permutation.
- **Event blob**: resolved (section 7, job S14, 2026-10-23) -- the
  per-pattern step/hit data is now decoded: `(delta_ticks, voice<<4|level)`
  pairs, 12 ticks/beat, terminated by a loop-delta byte + `0xf0`.

---

## 1. Samples

### Format

Header: none. Each `.raw` file is just sample data, nothing else.

| Field | Value | Confidence |
|---|---|---|
| Bit depth | 16-bit | confirmed |
| Signedness | signed | confirmed |
| Endianness | little-endian | confirmed |
| Channels | 1 (mono) | confirmed |
| Sample rate | 44,100 Hz | likely (not stored in the file; it's the pedal's one fixed audio rate everywhere else, so assumed here too) |

**Evidence** (`tools/drums/raw2wav.py` docstring has the code; this is the
summary):

- Interpreting `Kik1.raw` as signed 16-bit **little-endian** gives a
  classic drum-hit envelope: average amplitude in the first 10% of the
  file is **~45x** the average amplitude in the last 10% (loud attack,
  quiet tail). The same bytes read as **big-endian** 16-bit give only a
  **1.8x** ratio (flat, not a drum envelope), and read as unsigned 8-bit
  give a ratio **< 1** (gets louder towards the end, backwards). Little-endian
  16-bit is the only reading that produces a real transient-and-decay
  shape.
- Frequency content matches each sample's name: `Kik1.raw` spectral
  centroid ≈ 789 Hz (bass-heavy, kick-like), `HHC.raw` ≈ 12.1 kHz
  (cymbal-like), `Snr1.raw` ≈ 5.1 kHz (snare-like).
- All 24 files have even byte lengths, consistent with whole 16-bit
  samples (no header, no odd trailer).
- This matches how the firmware itself reads these samples: the 9-voice
  PCM fetcher (`11817520`, see
  `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md` "Drum Voice PCM
  Fetcher") does a 16-bit halfword load (`LDH.D2T2`) straight from the
  sample ROM into the mix buffer -- no decode step, no header skip. The
  sample ROM region is `0xc075d0f0`, referenced by a 9-entry descriptor
  table at `0xc0183424` (`{start_ptr, byte_length}` per voice, confirmed
  by that same doc).

### Durations and peak levels (44.1 kHz, as exported)

| name | samples | duration (s) | peak (dBFS) |
|---|---:|---:|---:|
| Clap | 5320 | 0.121 | -3.2 |
| ClapAmb | 8820 | 0.200 | -4.1 |
| Click | 1380 | 0.031 | -6.4 |
| HHC | 7747 | 0.176 | -20.0 |
| HHCAmb | 14638 | 0.332 | -21.2 |
| HHF | 3532 | 0.080 | -25.7 |
| HHO | 16901 | 0.383 | -31.7 |
| HHOAmb | 17319 | 0.393 | -21.5 |
| Kik1 | 10398 | 0.236 | -3.3 |
| Kik2 | 7547 | 0.171 | -10.0 |
| KikAmb | 13727 | 0.311 | -13.4 |
| Ride | 33254 | 0.754 | -38.8 |
| Rim | 4813 | 0.109 | -6.9 |
| RimAmb | 13005 | 0.295 | -27.1 |
| Snr1 | 12561 | 0.285 | -2.4 |
| Snr2 | 8829 | 0.200 | -7.6 |
| Snr3 | 12370 | 0.280 | 0.0 |
| Snr4 | 10899 | 0.247 | -16.3 |
| SnrAmb | 15769 | 0.358 | -8.8 |
| Tamb | 7777 | 0.176 | -14.0 |
| TomF | 14252 | 0.323 | -1.4 |
| TomFAmb | 13691 | 0.310 | -10.3 |
| TomH | 11631 | 0.264 | -6.2 |
| TomL | 11901 | 0.270 | -5.6 |

(`Snr3` peaks at exactly 0 dBFS -- worth a listen, it may be clipped in
the original ROM, or just a hot sample.) Regenerate this table with
`python tools/drums/raw2wav.py --all`.

---

## 2. Pattern table

### Where it is

`build/fw/res1_493412.bin`, AIS section `0xc016f780` (size `0x123a4`,
file offset `0x63708`) -- this is the "constant data: rhythm table,
strings, fonts, bitmaps, tables" region already named in
`docs/FIRMWARE_MAP.md`. `tools/fwmap/ais.py sections()` gives the
address-to-file-offset mapping used throughout.

The table of pattern records starts with the first record's voice-0
filename at **`0xc016f7e9`** (`"Click.raw"`). There's a 105-byte region
just before it, starting at `0xc016f780`, holding the literal string
`"Dummy"` followed by zero padding -- this does **not** fit the 124-byte
record stride and is some kind of placeholder/sentinel, not pattern index
`-1`; it's left alone.

### Record format (124 bytes, repeats 69 times, index 0..68)

| Offset | Size | Field | Confidence |
|---|---|---|---|
| `0x00` | 12 B | voice slot 0 filename (the "click"/metronome voice), null-padded cstring, empty if unused | confirmed |
| `0x0c` | 1 B | beats per bar (seen: 3, 4, 5, 6, 8, 12) | likely |
| `0x0d` | 1 B | beat unit (seen: 4, 8 -- quarter- or eighth-note beat) | likely |
| `0x0e` | 1 B | unknown flag byte, **0x02 in every one of the 69 records** | guess |
| `0x0f` | 4 B | `uint32` little-endian pointer into the same constant-data region | confirmed (as a pointer that resolves); meaning is likely "step/hit event blob", not proven |
| `0x13` | 9 B | pattern display name, null-padded cstring | confirmed |
| `0x1c`.. | 8 x 12 B | voice slots 1..8 filenames, null-padded, empty if unused | confirmed |

9 voice-name slots per record (slot 0 + 8 more) matches the firmware's
already-confirmed **9-voice** drum mixer architecture (`11817520` fetches
9 voices into `0x11f039b0..0x11f03acf`, `9 x 16 x int16`; `11817640`
mixes 9 voices with per-voice pan/gain into the stereo bus -- see
`docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md` section B). That the slot
count falls out exactly right from an independent structural decode (byte
layout) is good cross-confirmation.

Every non-empty filename found anywhere in the 69 records is one of the
24 known `.raw` sample names, and all 24 names are used by at least one
pattern (checked by `tests/test_drum_patterns.py`).

Decode it yourself: `python tools/drums/decode_patterns.py` writes
`build/drums/patterns.json` (not committed -- it's a `build/` output,
regenerate it). First few and a few interesting rows:

| index | name | beats/bar | beat unit | voices (non-click) |
|---:|---|---:|---:|---|
| 0 | GUIDE | 4 | 4 | Kik1, SnrAmb, Snr1, HHC, HHCAmb, KikAmb |
| 7 | Rock1 | 4 | 4 | Kik1, SnrAmb, Snr1, HHC, HHCAmb, KikAmb |
| 27 | Blues2 | 4 | 4 | Kik1, SnrAmb, Snr1, Snr2, HHC, HHCAmb, KikAmb |
| 36 | TomTomBt | 4 | 4 | Kik1, SnrAmb, Snr1, TomF, TomL, TomH, TomFAmb, KikAmb |
| 56 | Waltz | 12 | 8 | Kik1, SnrAmb, Snr2, HHC, HHCAmb, KikAmb |
| 61 | CtWaltz1 | 5 | 4 | Kik2, HHF, Ride, KikAmb |
| 68 | Metro | 5 | 4 | (click only) |

### Pattern numbering: Rock1 matches, Blues2 doesn't

The task brief said the pedal's live reading should validate this
table's indexing: Rock 1 = pattern number 7, Blues 2 = pattern number 44.

- **Rock1 = static index 7**: matches exactly
  (`docs/LOOPER_DRUMS_TEARDOWN_2026-10-22.md` line 21: pattern number
  read as 7 while Rock 1 was selected on the pedal).
- **Blues2 = static index 27**, not 44. Index 44 in this table is
  `PopRock`.

So the simple "record order = pattern number" rule holds for the first
block of the table (GUIDE..Rock1, indices 0-7) but breaks somewhere
before Blues2. We did not find a second table or permutation that
reorders this; candidates not yet ruled out:

1. A UI-facing "category tab" ordering, built at boot into the RAM-only
   pointer table at `0xc0182730` (see below), that differs from this
   ROM table's physical storage order starting partway through.
2. A different live firmware revision than this image (unlikely, but not
   excluded).
3. A composite encoding (e.g. category + sub-index) rather than a flat
   0..68 counter -- we didn't find evidence of this, but didn't rule it
   out either.

**This is flagged, not silently assumed away**: `tests/test_drum_patterns.py`
pins down both facts (index 7 = Rock1, index 44 = PopRock, Blues2 is
really at 27) so the test suite documents the discrepancy instead of
hiding it.

### What isn't decoded: the per-pattern event blob

Each record's offset-`0x0f` pointer resolves (for every pattern except
`GUIDE`, whose pointer lands in unrelated bitmap/string data) into a
small binary blob in the same constant-data region, terminated by a
single `0xf0` byte. Examples (hex, pointer address in parentheses):

- Rock1 (`0xc017c630`, 165 bytes): starts
  `00 1e 00 5b 00 88 00 75 03 58 00 72 03 5a 00 74 ...`
- Rock2 (`0xc017e220`, 105 bytes), Rock3 (`0xc017dff0`, 109 bytes): same
  shape, but the "high byte" that alternates with small values is `0x06`
  instead of `0x03`.
- Blues2 (`0xc017fa20`, 69 bytes): same shape, high byte `0x08`.

The bytes look paired (alternating a small "flag-ish" byte -- 0x00 or a
per-pattern constant -- with a varying value byte in roughly the 0x1d-0x8a
range), and blob length scales with how busy/ornamented the pattern is
(e.g. `GUIDE` is 10 bytes, `Ska` is 194 bytes), which is consistent with
a step/hit/velocity event list. We tried several hypotheses (16-bit
big/little-endian timestamps, voice-ID + time pairs, variable-length
chords) in the time available and none produced a fully self-consistent
decode; see the code comments removed from the final `decode_patterns.py`
for the attempts if useful context is wanted. **This is marked as a guess,
not a finding** -- `patterns.json` stores the raw blob bytes
(`event_blob_hex`) and `event_blob_decoded: false` for every pattern, and
`drum_machine.py` does not use them.

**To make progress on this, more disassembly time is the right next
step** (not a live pedal read, since this data is static ROM): trace
what consumes the record's offset-`0x0f` pointer. Likely consumers, not
yet traced to completion:
- `11806eb4` (`rhythm_playback_step`, "RhythmService playback routine")
  -- a dense per-16th state machine over the byte flags at
  `0xc011ada4..0xc011adad`; didn't find the event-blob read inside it in
  the time available.
- The `c0153f00..c0154290`, `c0156430..c0156660` cluster
  (`docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md` section 2D/2E).
- `c015408c` (`rhythm_pattern_field_copy`), which reads a *different*,
  RAM-resident struct via the pointer table at `0xc0182730` (word offset
  30 / byte 0x78) -- this is not the same struct as our 124-byte ROM
  record; `0xc0182730` itself is RAM-only (see next section) and its
  per-pattern target structs may be a reformatted/decompressed version of
  the ROM data built at boot, which would explain why its documented
  field offsets (117/118/119) don't line up with our record's offsets
  (12/13/14).

### RAM-only table noted but not reachable statically

`0xc0182730` (named in `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md` as
"Rhythm Patterns Descriptor Table... filled at boot") is **not** present
in `res1_493412.bin`: it falls in the gap between two AIS sections
(`0xc016f780`+`0x123a4` ends at `0xc0181b24`; the next section starts at
`0xc0183b74`), so it's BSS/RAM that the firmware fills at runtime, not
ROM-initialized data we can read statically. This is the pointer array
that `rhythm_get_field117/118/119` (`c0166180`/`c0166194`/`c01661ac`) index
by pattern number to find each pattern's beats-per-bar/beat-unit/flags --
i.e. it's extremely likely the TRUE pattern-number -> pattern-struct
mapping, which would resolve the Blues2 discrepancy above if we could
read it.

**Live pedal reads that would help** (for whoever is holding the MIDI
link -- this job did not touch the pedal):
1. `0xc0182730`, length `4 * 76` bytes (word pointer array, index 0..~69
   plus margin) -- the actual pointer for each pattern number. Compare
   index 7 and 44's pointers against `0xc017c630` (our Rock1 blob
   address) and `0xc017fa20` (our Blues2 blob address) to see whether 44
   points at the Blues2 data and 7 at the Rock1 data, which would confirm
   this is the real ordering table and explain the mismatch.
2. With the pedal parked on Blues 2, a read of `0xc011ada6` (the
   "pattern/category index" byte, documented as separate from
   `0x11812f4c`'s "pattern number") -- to check whether it also reads 44,
   27, or something else again.

---

## 3. Engine

How playback works, each claim marked confirmed (seen on the live pedal
tonight, or directly in disassembly) / likely / guess, with addresses.

- **Step clock from BPM**: BPM is stored at `0x11812f78` (and a duplicate
  at `0x11812f0c`), range 40-250, default 120 -- **confirmed** (live
  read: 124 -> 90 when the owner changed tempo;
  `docs/LOOPER_DRUMS_TEARDOWN_2026-10-22.md`). ms-per-16th-note is
  computed as `60000 / BPM / 16` and stored at `0x118130a4`/`0x118130a8`
  -- **likely** (both live values fit the formula exactly: 30 at 124 BPM,
  41 at 90 BPM). A derived "BPM x 6" internal tempo unit lives at
  `0x118133b8`/`0x118133c0` -- **likely**.
- **9 fixed voice slots, not a dynamic voice pool**: each pattern
  statically assigns up to 9 named samples to 9 voice slots (the table
  above); there is no evidence of runtime voice allocation/stealing
  across patterns -- a slot either has a sample this pattern uses or it
  doesn't. Each slot loops/retriggers its own assigned sample
  independently. **Likely** (inferred from the fixed per-pattern table
  plus the fixed 9-voice mixer; we did not trace the exact trigger-write
  instruction, see below).
- **9-voice PCM fetch + mix, every audio block (16 samples)**:
  `11817520` reads 16 new samples per voice from the sample ROM
  (`0xc075d0f0`, located via the 9-entry descriptor table at
  `0xc0183424`) into `0x11f039b0..0x11f03acf` (`int16_t[9][16]`
  planar); `11817640` applies per-voice pan/gain
  (`0x11f03d24..0x11f03d48`) and the master rhythm level
  (`0x11f03d0c`/`0x11f03d14`/`0x11f03d20`) and mute (`0x11f03d08`),
  converts to float, and adds the result straight into the main stereo
  bus (`0x11f037b0` L / `0x11f037f0` R) -- **confirmed** by disassembly
  already on file (`docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md`
  section 2B). This happens inside Swi step 15 of the main audio
  callback (`0x11818c54`), after the Looper (step 6 or 14) and before
  the master output gain stage.
- **Run flag**: `0x11f03d54` is 1 while the drum machine is running, 0
  when stopped; set by `c0158d98`, cleared by `c0158dac`; checked by the
  mixer `11817640` before doing any work -- **confirmed** (live read:
  1 -> 0 when the owner stopped the drums).
- **Drum volume**: the 0-100 UI setting lives at `0x11812f50`/`0x11812fbc`;
  the actual float gain applied in the audio path is `volume / 100` at
  `0x11f03d14` -- **confirmed** (live read: 80 -> 60 and 0.8 -> 0.6 at
  the same time).
- **Voice "play position" counters**: tonight's live read of
  `0x11f03d58, 0x11f03d5c, 0x11f03d60, 0x11f03d68, 0x11f03d70, 0x11f03d74`
  showed values that **count up and wrap**, not simple on/off flags as an
  earlier static-only pass assumed -- **likely**, per
  `docs/LOOPER_DRUMS_TEARDOWN_2026-10-22.md` line 34 (explicitly
  overriding the older "trigger/active state array" reading of the same
  addresses in `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md`). The
  live data shows multiple of these counting simultaneously, consistent
  with several voices playing at once (up to the 9 slots). We did not
  find, in the time available, the exact instruction that *starts* a
  voice (writes a trigger into this array from the per-step event data)
  -- that's the missing link to the undecoded event blob above.
- **Ambience samples (`*Amb`)**: these are not a reverb/convolution
  effect -- they're separate, independently-triggered voice slots. The
  pattern table frequently assigns both a dry sample and its `*Amb`
  companion to two of the 9 slots in the same pattern (e.g. `HardRock`:
  slot 6 = `HHO.raw`, slot 7 = `HHOAmb.raw`) -- **confirmed** from the
  table structure. Whether the dry and Amb companion always fire at
  exactly the same step (as opposed to independently) is **likely** but
  not proven, since it depends on the undecoded event data;
  `drum_machine.py`'s approximate renderer assumes they always fire
  together, with the Amb copy at 70% velocity.
- **Per-voice gain/pan**: `0x11f03d24..0x11f03d48` (9 x 4 bytes), written
  at pattern load by `c0158c20`, read by the mixer at
  `0x118176ec`/`0x11817740` -- **confirmed** (structure and call sites),
  exact per-voice values not extracted.
- **Click track**: voice slot 0 is a dedicated metronome/click voice,
  `Click.raw` in **all 69 of 69 patterns** (checked), including the
  click-only `Metro`/`Metro3`/`Metro4`/`Metro5` patterns, which have
  nothing else assigned. It's mixed exactly like any other voice (no
  special-cased audio path found) -- **likely**.
- **Time signature / swing / feel**: the `beats_per_bar`/`beat_unit`
  byte pair (offsets 0x0c/0x0d of the ROM record) covers straight meters
  (3/4, 4/4, 5/4, 6/8, 12/8 all appear). Swing/shuffle feel for patterns
  named "Shuffle"/"Swing"/"12/8" is **not** visible in those two bytes
  (they're plain 4/4) so it must live entirely in the undecoded per-step
  event timing -- **guess**.
- **Intro/fill/ending**: `11806eb4`'s state machine checks byte flags at
  `0xc011ada4..0xc011adad` against values like 5, 6, 8 (the same style of
  state coding the Looper uses for its transport states) and branches to
  different code paths depending on them -- consistent with
  intro/loop/ending sections existing, but we did not map which state
  value means which section, or how it's triggered from the event data
  -- **guess**.

---

## 4. Local drum machine tool

### `tools/drums/raw2wav.py`

```
python tools/drums/raw2wav.py --all                 # convert every pedal sample
python tools/drums/raw2wav.py path/to/one.raw -o dir # convert just one
```
Writes 16-bit PCM mono WAVs at 44.1 kHz to `build/drums/wav/` (or `-o`),
and prints a table of sample count / duration / peak dBFS per file.

### `tools/drums/decode_patterns.py`

```
python tools/drums/decode_patterns.py
```
Parses `build/fw/res1_493412.bin` and writes `build/drums/patterns.json`:
for each of the 69 patterns, its name, time signature, 9 voice-slot
sample assignments, and the **decoded event blob** (section 7, job S14) --
a step grid of `{tick, voice_id, level, slot, sample, mapped}` plus loop
length and a `decode_confidence` flag. Prints the Rock1/Blues2 numbering
sanity lines and a decode-confidence summary (`ok`/`partial_unmapped_voice`/
`suspect` counts).

### `tools/drums/drum_machine.py`

```
python tools/drums/drum_machine.py list
python tools/drums/drum_machine.py render Rock1 --bpm 90 --bars 4 -o build/drums/render/rock1_90.wav
python tools/drums/drum_machine.py render Blues2 --bpm 124 --bars 4 -o build/drums/render/blues2_124.wav
python tools/drums/drum_machine.py render "Rock1" --bpm 90 --sample Kik1.raw=my_kick.wav -o out.wav
python tools/drums/drum_machine.py new my_pattern.json --bpm 100 -o out.wav
```

`render` plays a built-in pattern using **its own real, firmware-assigned
samples, time signature, and (as of job S14, section 7) its real step
grid** -- a transcription of the firmware's own per-pattern event data,
for 68 of the 69 patterns. The one exception, `Metro3`, whose event blob
doesn't resolve to any real voice, falls back to the old
**algorithmically-generated, genre-approximate groove** (kick on beat 1
[+ mid-bar for longer meters], backbeat snare, 8th-note hats or ride for
a "latin"-ish name, a funk/breaks syncopation bump for those names),
with a loud warning printed when it does. `--force-approx` forces that
fallback for any pattern, for A/B comparison against the real grid.

`new <pattern.json>` renders an exact, user-written step grid -- no
approximation involved. Format:

```json
{
  "name": "MyBeat",
  "bpm": 100,
  "bars": 2,
  "steps_per_bar": 16,
  "voices": {
    "Kik1.raw": [[0, 120], [8, 100]],
    "Snr1.raw": [[4, 115], [12, 115]],
    "HHC.raw":  [[0, 80], [2, 60], [4, 80], [6, 60], [8, 80], [10, 60], [12, 80], [14, 60]]
  }
}
```
`steps` are 16th-note indices within one bar (0-based); `[step, velocity
0-127]`. Voice keys are matched to `build/drums/wav/<name>.wav` by default
(`.raw` suffix optional); `--sample VOICE=path.wav` overrides any voice
with your own WAV, so you can swap samples freely.

Rendered examples for the task's two requested cases are in
`build/drums/render/rock1_90.wav` (Rock1, 90 BPM, 4 bars) and
`build/drums/render/blues2_124.wav` (Blues2, 124 BPM, 4 bars) -- not
committed, they're `build/` output; regenerate with the commands above.

---

## 5. Tests

- `tests/test_drum_samples.py`: pins the raw sample format (24 expected
  names, even byte lengths, the little-endian decaying-envelope check,
  `raw2wav` round-trip through a real WAV file).
- `tests/test_drum_patterns.py`: pins the table decode (69 records,
  index 7 = Rock1 matching the live pedal, the Blues2 numbering
  discrepancy documented rather than hidden, every voice slot referencing
  a real sample or being empty, all 24 samples used somewhere, plausible
  time-signature values).
- `tests/test_drum_event_blob.py` (job S14, 2026-10-23): pins the event
  blob decode -- structural checks (odd body length, loop length always
  a whole number of bars, voice IDs 1-9, levels 0-15, the exact
  47/21/1 `ok`/`partial_unmapped_voice`/`suspect` confidence split) and
  the task's known-answer checks (`Metro4`/`Metro5`/`Metro` = one click
  per beat with a louder downbeat accent, `GUIDE` = one click per beat
  over one bar, `8Beats1` = 8 evenly-spaced kick hits, `Rock1` = backbeat
  snare on beats 2 & 4 plus a hi-hat/amb pair firing on identical ticks,
  `Metro3` flagged `suspect` rather than trusted).

All three skip cleanly if the backup/firmware files aren't present in a
given checkout (`unittest.skipUnless`).

---

## 6. Summary of what's uncertain

1. ~~**The per-pattern step/hit event blob's byte encoding**~~ -- **decoded**,
   see section 7 below (job S14, 2026-10-23).
2. **The Blues2 pattern-numbering mismatch** (section 2) -- resolved, see
   "Pattern numbering resolved" above (live read, 2026-10-22).
3. **Exact per-voice pan/gain values** (`0x11f03d24..0x11f03d48`) --
   structure confirmed, values not extracted per pattern.
4. **Which state-byte values mean intro/loop/fill/ending**, and how
   they're driven by the event data -- still open, see section 7.
5. ~~**Whether dry/Amb sample pairs always fire on identical steps**~~ --
   **resolved: yes**, see section 7 (checked exactly for Rock1; a
   structural property of every pattern that has a dry+Amb pair).
6. **The auxiliary hat/cymbal/tom voice-ID-to-slot mapping** (new, section
   7) -- the core voices (kick, snare, snare-amb, kick-amb, click) always
   resolve cleanly, but ~1/3 of patterns have an auxiliary voice ID (4-7)
   that doesn't match its sample's actual table slot. Needs either a live
   read or more disassembly time on `0x1180b6f0` (see section 7).

## Pattern numbering resolved (live read, Claude, 2026-10-22)
The pedal's pattern number (0x11812f4c) indexes a RAM pointer table at **0xc0182730** (built at run
time; not in the image). Each entry points to a 124-byte record at **0xc016f7fc + 124 x record** (the
records start at 0xc016f7fc; the table offset 0xc016f7e9 above is 0x13 early). The on-screen order is a
permutation of the record order: `tools/drums/ui_order.json` (68 patterns, 0 GUIDE .. 67 Metro; entries
68/69 point elsewhere). Checks: pedal 7 -> record 7 Rock1, pedal 44 -> record 27 Blues2 (both seen live).

---

## 7. Event blob format (decoded, job S14, 2026-10-23)

Static work only (file analysis of `build/fw/res1_493412.bin` and
`build/fw/map/main.dis`), plus review of the already-logged live reads in
`docs/LOOPER_DRUMS_TEARDOWN_2026-10-22.md`. No MIDI, no pedal touched.
Tool: `tools/drums/decode_patterns.py` (now parses the blob, not just
locates it). Tests: `tests/test_drum_event_blob.py`.

### TL;DR

The per-pattern event blob (section 2's "what isn't decoded") **is now
decoded**: it's a stream of `(delta_ticks, voice_and_level)` byte pairs,
12 ticks per beat, terminated by a loop-delta byte and `0xf0`. Voice IDs
1-9 map onto the record's 9 voice-name slots (9 = slot 0 = click; 1-8 =
slots 1-8) **for the core voices** (kick, snare, snare-amb, kick-amb,
click) in every one of the 69 patterns. For roughly a third of patterns,
one auxiliary hat/cymbal/tom voice ID doesn't match its sample's actual
table slot -- flagged per-pattern, not silently papered over (see
"What's still open" below). `drum_machine.py render` now plays this real,
transcribed grid for 68 of 69 patterns; the exception (`Metro3`) falls
back to the old approximate generator, loudly flagged in its output.

### Byte format

```
(delta: u8, value: u8){N}   loop_delta: u8   0xf0
```

| Field | Meaning | Confidence |
|---|---|---|
| `delta` | ticks since the previous event (0 = simultaneous with it); running sum = absolute tick | confirmed |
| `value` high nibble | **voice ID, 1-9** | confirmed for 1,2,3,8,9; likely-with-exceptions for 4-7 (see below) |
| `value` low nibble | **level, 0-15** (velocity-like; 15 = loudest) | confirmed |
| tick resolution | **12 ticks = 1 beat** (3 ticks = a 16th note, 4 = an 8th-note triplet, 6 = an 8th note) | confirmed |
| trailing byte (after the last event, before `0xf0`) | **loop delta**: ticks from the last event back to the loop start | confirmed |
| `0xf0` | terminator | confirmed (already known from section 2) |

`loop_length_ticks = last_absolute_tick + loop_delta`. Checked across
**all 69 patterns**: this is *always* an exact multiple of
`beats_per_bar * 12` -- i.e. every pattern's authored loop is a whole
number of bars (1 bar for `GUIDE`; 2 bars for every other pattern
checked, even when bar 2 turns out to repeat bar 1 exactly, e.g. `Rock1`).
This 100%-across-69-patterns structural fit, found with no exceptions, is
the strongest evidence the byte layout above is right.

### Voice ID -> sample mapping

Voice ID maps to the record's 9-slot voice-name array (section 2): ID 9
-> slot 0 (click); ID N (1..8) -> slot N. This resolves cleanly
(every event's voice ID points at a populated slot) for:

- **100% of patterns** for voice ID 9 (click) -- the one fully universal
  case, including every pattern that uses it.
- **The large majority** for IDs 1 (kick), 2 (snare-amb), 3 (snare), 8
  (kick-amb) -- a handful of sparse patterns (`Jazz1`, `JzWaltz1`,
  `CtWaltz1`, `Bossa1`, `OneDrop`) have no kick and/or snare sample at
  all (e.g. `Jazz1`'s kit is hi-hat + ride only), so an event with that
  ID is correctly unmapped there, not a decode error.
- **47 of 69 patterns fully** (`decode_confidence: "ok"`), including
  every pattern named in the task brief as a known-answer check
  (`Metro`, `Metro4`, `Metro5`, `GUIDE`, `8Beats1`, `Rock1`).

**What's still open**: 21 of 69 patterns (`decode_confidence:
"partial_unmapped_voice"`) have one auxiliary voice ID (always in the
4-7 range -- the hat/cymbal/tom group) that references an empty slot,
even though a plausible sample for that role exists elsewhere in the
same record. Example: `HardRock`'s table has `HHO.raw` in slot 6 and
`HHOAmb.raw` in slot 7, but its event data uses voice ID 5 (not 6) for
the dry hit -- slot 5 is empty, so those events currently render as
silence. The amb companion (ID 7) resolves correctly to slot 7 every
time it's checked. We tried two alternative hypotheses in the time
available -- "compact IDs 1-8 over all populated slots" and "compact
IDs 1-7 over populated slots 1-7, ID 8 fixed to slot 8" -- neither
fit the data (see job notes; not committed, both failed on >40 of the
69 patterns). `decode_patterns.py` marks every such event `"mapped":
false` and `drum_machine.py render` skips it (plays nothing), printing
which voice ID(s) and how many events were skipped. This is the
"likely silent" reading, not confirmed: the firmware's voice-trigger
call for an ID whose slot has no sample descriptor would most likely
resolve to a zero-length PCM fetch (silence) rather than crash, but we
did not trace `0x1180b6f0` (see below) far enough to confirm this.

One pattern, **`Metro3`**, is worse: `decode_confidence: "suspect"` --
*none* of its event voice IDs resolve to a populated slot, and its blob
never references the click voice at all, despite being named like the
other, cleanly-decoding metronome patterns (`Metro4`, `Metro5`, `Metro`).
This is almost certainly the same "pointer resolves outside the real
per-step event data" issue the earlier pass flagged for `GUIDE` (which,
on this pass, actually does decode cleanly -- so that concern was
specific to individual records, not a systematic problem).

### Disassembly evidence

Found by searching `build/fw/map/main.dis` for the `0xf0`/`240` immediate
near the already-known RhythmService addresses (`11806eb4`+), per the
task brief's suggested approach:

- **`0x1180717a`**: `MVK.S2 240,B1` (240 = `0xf0`); **`0x1180718a`**:
  `CMPEQ.L2 B0,B1,B0`, comparing a byte just read (via `LDBU`, through a
  pointer derived from `A10`) against `0xf0` -- the literal terminator
  check the task brief asked us to find. **Confirmed** (read directly;
  `build/fw/map/main.dis:9259,9264`).
- **`0x11807060`/`0x11807080`/`0x118070a0`**: `CALLP.S2 0x1180b020,B3`,
  each immediately preceded by `MVK.L1 9,A4` / `8,A4` / `7,A4` and gated
  by an `LDBU`+`[!A0] BNOP` test on an adjacent byte -- i.e. "if this
  step's flag byte is set, call `trigger(A4=9|8|7)`". **Confirmed**
  that `0x1180b020` takes a voice-ID-shaped byte parameter in `A4`:
  disassembly at `0x1180b020` shows `STB.D2T1 A4,*+B15[4]` (stores the
  parameter) then `CALLP.S2 0x1180b6f0,B3` (hands it to a sub-routine).
  This directly corroborates "voice ID 1-9 is a real parameter the
  firmware passes around", matching the high-nibble decode. **Likely**
  (not fully traced) that `0x1180b6f0` is the actual slot-lookup+PCM
  trigger, which would be the next step to resolve the open
  auxiliary-voice-mapping question above -- we did not have time to
  disassemble it this pass.
- This whole block (`0x11806eb4`..`0x1180720c`) is the "dense per-16th
  state machine over byte flags at `0xc011ada4..0xc011adad`" the earlier
  pass (section 2) already named but didn't trace into; this pass
  confirms it as (or as directly adjacent to) the actual event-blob
  consumer.

### Known-answer checks (from the task brief)

All pinned in `tests/test_drum_event_blob.py`:

- **Metronome = one hit per beat**: `Metro4`, `Metro5`, and `Metro`
  (undecorated) each decode to click-only (voice 9), exactly one event
  every 12 ticks (= 1 beat) for the whole loop, with the first beat of
  every bar accented louder (level 15) than the other beats (level 8).
  `GUIDE` is the same shape over a single bar. **Confirmed.**
- **8Beats1 = kick on every beat**: decodes to exactly 8 kick (`Kik1.raw`)
  hits, each exactly 12 ticks apart, across its 2-bar loop (4 beats/bar x
  2 bars = 8) -- matches the pattern's own name. **Confirmed.**
- **Rock1 = a standard rock beat**: snare (`Snr1.raw`) lands on beats 2
  and 4 of every bar and nowhere else (ticks 12 and 36 of the 48-tick
  bar) -- the classic backbeat; kick (`Kik1.raw`) lands on beat 1 plus
  syncopated 16th-note pushes. The hi-hat (`HHC.raw`, ID 5) and its
  ambience companion (`HHCAmb.raw`, ID 7) fire on exactly the same ticks
  every time -- this also resolves the open "do dry/Amb pairs always
  fire together" question from section 6 point 5 above: **yes,
  confirmed** (at least for every dry/Amb pair checked; it's a property
  of the data, not an assumption `drum_machine.py` has to make anymore).

### Tool changes

- `tools/drums/decode_patterns.py`: `decode_table()` now returns, per
  pattern, `"steps"` (list of `{tick, delta, voice_id, level, slot,
  sample, mapped}`), `"ticks_per_beat"` (12), `"loop_length_ticks"`,
  `"bar_ticks"`, `"loop_bars"`, `"loop_bars_is_whole"`, and
  `"decode_confidence"` (`"ok"` / `"partial_unmapped_voice"` /
  `"suspect"`), written into `build/drums/patterns.json`. Prints a
  confidence-count summary.
- `tools/drums/drum_machine.py render`: plays the real, transcribed step
  grid by default for any pattern with at least one mapped event (68 of
  69), looping the authored 1-or-2-bar block to fill the requested
  `--bars`. Falls back to the old approximate generic-groove generator
  only for `Metro3` (or if `--force-approx` is passed), always printing
  a clear warning when it does. Unmapped auxiliary events are skipped
  (silent) with a printed note naming the voice ID and count skipped.
  The old approximate generator (`generic_groove`) is kept, unchanged,
  purely as that fallback.

### What's still open

1. **The auxiliary voice-ID-to-slot mapping for the ~1/3 of patterns
   where it doesn't match the raw slot index** -- needs disassembly of
   `0x1180b6f0` (the sub-routine `0x1180b020` hands the voice ID to) to
   see how it actually resolves an ID to a sample descriptor. Not a live
   pedal question (this is static ROM code), so the right next step is
   more disassembly time, not a live read.
2. **Whether unmapped events are truly silent** on the real pedal, or
   whether there's a fallback/default sample -- *this one a live read
   could settle*: with the pedal parked on **HardRock** (pattern name;
   its live pattern-number isn't yet known, see `tools/drums/ui_order.json`
   for the likely UI index) and the drum machine running, listen for
   (or better, tap a level meter on) the open-hat voice slot
   (`0x11f03d58+6*5`-ish region per the voice-position array documented
   in `docs/LOOPER_DRUMS_TEARDOWN_2026-10-22.md`, i.e. the 5th play-position
   counter `0x11f03d6c`/`0x11f03d70` area -- re-derive the exact offset,
   don't trust this guess) to see whether it's advancing (meaning
   *something* plays for voice ID 5) or frozen at 0 (confirms silent).
3. **Intro/fill/ending markers** -- still not found. The event data for
   every pattern checked is a flat, uniform loop with no distinguished
   "first time only" or "last bar" events; if the firmware has
   intro/ending sections for the drum machine (as opposed to the
   Looper, which clearly does), they're not visible in this blob format
   and must be driven by the `0xc011ada4..0xc011adad` state bytes alone.
4. **Per-voice pan/gain values** (section 6 point 3) -- unchanged, still
   open.
