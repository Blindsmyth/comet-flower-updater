# Handoff: Drum Machine Extraction, Engine Specification & Emulator/Editor

**Date:** 2026-10-23  
**Project:** Zoom G1X FOUR / Comet Flower Drum Machine Extraction  
**Author:** Pair Programming Assistant (Antigravity)  
**Status:** Complete, tested, and self-contained (28/28 unit tests passing)

---

## 1. Executive Summary

This handoff documents the reverse-engineered drum machine from the Zoom G1X FOUR (Argon DSP platform), including:
1. **24 extracted audio samples** (44.1 kHz, 16-bit signed little-endian mono PCM).
2. **69 built-in firmware patterns** with time signatures, voice slot assignments, and decoded micro-timing step grids.
3. **Device DSP parameters and mixer architecture** (9-voice planar mix bus, gain scaling, room ambience pairing, timing formulas).
4. **The Comet Flower Drum Studio** (`comet_flower_drums.html`): a standalone, zero-dependency Web Audio player, step sequencer, and offline WAV renderer with retro hardware styling.
5. **Python CLI toolchain** (`tools/drums/`): tools for raw PCM extraction, ROM decoding, pattern rendering, and user-pattern authoring.

---

## 2. File & Directory Inventory

```
zoom project/
├── comet_flower_drums.html          # Standalone, single-file HTML5/Web Audio emulator & editor (1.26 MB)
│                                    # (All 24 WAV samples and 69 pattern tables embedded as base64)
├── backup/2026-10-04/files/*.raw    # Original 24 raw 16-bit PCM dumps from device flash
├── build/drums/
│   ├── wav/*.wav                    # 24 converted 44.1 kHz 16-bit mono WAV samples
│   ├── patterns.json                # Complete decoded JSON dataset of all 69 ROM patterns
│   └── render/*.wav                 # Offline rendered sample WAVs (Rock1, Blues2, etc.)
├── tools/drums/
│   ├── comet_flower_drums.html      # Copy of the web studio in tools/drums/
│   ├── comet_flower_data.js         # Modular JavaScript data bundle (window.COMET_FLOWER_DATA)
│   ├── launch_comet_flower.py       # Python launcher (direct browser open or local HTTP server)
│   ├── build_web_assets.py          # Data pack generator (packs WAVs + patterns + logos into JS)
│   ├── generate_studio.py           # Single-file HTML generator
│   ├── raw2wav.py                   # Raw PCM to WAV batch converter & sample analyzer
│   ├── decode_patterns.py           # Firmware ROM table & event blob parser
│   ├── drum_machine.py              # CLI drum machine engine (list, render, new)
│   └── ui_order.json                # Pedal screen display order mapping (68 patterns)
├── assets/
│   ├── logo_comet_flower.png        # Authentic 92x16 2-page LCD bitmap font logo
│   └── splash_comet_flower.png      # 128x32 power-on splash graphic
└── tests/
    ├── test_drum_samples.py         # Validates raw sample format, PCM math, envelope decay
    ├── test_drum_patterns.py        # Validates ROM 124-byte record table, meters, voice slots
    ├── test_drum_event_blob.py      # Validates delta-tick decoding, loop lengths, accents
    └── test_comet_flower_studio.py  # Validates standalone HTML, data JS, and CLI roundtrip
```

---

## 3. Extracted Audio Samples

### 3.1 PCM Format
* **Bit Depth:** 16-bit
* **Signedness:** Signed (`int16_t`, $-32768$ to $+32767$)
* **Endianness:** Little-endian (`<h` in Python `struct`)
* **Channels:** 1 (Mono)
* **Sample Rate:** 44,100 Hz (44.1 kHz fixed hardware rate)
* **Header:** None (raw sample stream, loaded directly by DSP halfword load `LDH.D2T2` from ROM `0xc075d0f0`).

### 3.2 Sample Catalog (24 Instruments)

| Sample Name | Byte Size | Sample Count | Duration (s) | Peak (dBFS) | Kit Role | Companion Ambience |
|---|---|---|---|---|---|---|
| `Click.raw` | 2,760 | 1,380 | 0.031 | -6.4 | Metronome / Click | — |
| `Kik1.raw` | 20,796 | 10,398 | 0.236 | -3.3 | Punchy Rock/Pop Kick | `KikAmb.raw` |
| `Kik2.raw` | 15,094 | 7,547 | 0.171 | -10.0 | Acoustic / Jazz Kick | `KikAmb.raw` |
| `KikAmb.raw` | 27,454 | 13,727 | 0.311 | -13.4 | Room Mic Kick Decay | — |
| `Snr1.raw` | 25,122 | 12,561 | 0.285 | -2.4 | Main Acoustic Snare | `SnrAmb.raw` |
| `Snr2.raw` | 17,658 | 8,829 | 0.200 | -7.6 | Tight / Pop Snare | `SnrAmb.raw` |
| `Snr3.raw` | 24,740 | 12,370 | 0.280 | 0.0 | Hot / Heavy Snare | `SnrAmb.raw` |
| `Snr4.raw` | 21,798 | 10,899 | 0.247 | -16.3 | Soft / Rim-like Snare | `SnrAmb.raw` |
| `SnrAmb.raw` | 31,538 | 15,769 | 0.358 | -8.8 | Room Mic Snare Decay | — |
| `Rim.raw` | 9,626 | 4,813 | 0.109 | -6.9 | Sidestick / Rimshot | `RimAmb.raw` |
| `RimAmb.raw` | 26,010 | 13,005 | 0.295 | -27.1 | Room Mic Rim Decay | — |
| `Clap.raw` | 10,640 | 5,320 | 0.121 | -3.2 | Handclap | `ClapAmb.raw` |
| `ClapAmb.raw` | 17,640 | 8,820 | 0.200 | -4.1 | Room Mic Clap Decay | — |
| `HHC.raw` | 15,494 | 7,747 | 0.176 | -20.0 | Closed Hi-Hat | `HHCAmb.raw` |
| `HHCAmb.raw` | 29,276 | 14,638 | 0.332 | -21.2 | Room Mic Closed Hat | — |
| `HHO.raw` | 33,802 | 16,901 | 0.383 | -31.7 | Open Hi-Hat | `HHOAmb.raw` |
| `HHOAmb.raw` | 34,638 | 17,319 | 0.393 | -21.5 | Room Mic Open Hat | — |
| `HHF.raw` | 7,064 | 3,532 | 0.080 | -25.7 | Foot / Pedal Hi-Hat | — |
| `Ride.raw` | 66,508 | 33,254 | 0.754 | -38.8 | Ride Cymbal | — |
| `Tamb.raw` | 15,554 | 7,777 | 0.176 | -14.0 | Tambourine | — |
| `TomH.raw` | 23,262 | 11,631 | 0.264 | -6.2 | High Tom | — |
| `TomL.raw` | 23,802 | 11,901 | 0.270 | -5.6 | Low Tom | — |
| `TomF.raw` | 28,504 | 14,252 | 0.323 | -1.4 | Floor Tom | `TomFAmb.raw` |
| `TomFAmb.raw` | 27,382 | 13,691 | 0.310 | -10.3 | Room Mic Floor Tom | — |

### 3.3 Ambient Room Mic Pairing
In Zoom's firmware, ambient reverb is not computed via an expensive algorithmic reverb DSP kernel. Instead, dry samples and their ambient room-decay counterparts (`*Amb`) are assigned to separate voice slots and **triggered simultaneously on the exact same tick**. In the emulator, ambient companions default to 70–75% velocity relative to the dry hit.

---

## 4. Pattern Storage & Firmware Architecture

### 4.1 ROM Pattern Table (`0xc016f7fc`)
The firmware stores 69 pattern records in constant data space (`res1_493412.bin` AIS section `0xc016f780`).
* **Stride:** 124 bytes per record.
* **Count:** 69 patterns (indices 0..68).
* **Record Byte Layout:**

```
+-------------------------------------------------------------------------------------------------+
| Offset | Size | Type      | Field Name          | Description                                    |
|--------|------|-----------|---------------------|------------------------------------------------|
| 0x00   | 12 B | char[12]  | voice_slot_0        | Metronome voice (always "Click.raw\0")          |
| 0x0c   | 1 B  | uint8_t   | beats_per_bar       | Beats per bar (3, 4, 5, 6, 8, 12)             |
| 0x0d   | 1 B  | uint8_t   | beat_unit           | Beat unit (4 = quarter, 8 = eighth)           |
| 0x0e   | 1 B  | uint8_t   | flag_byte           | Fixed constant 0x02 across all 69 records      |
| 0x0f   | 4 B  | uint32_t  | event_ptr           | Little-endian pointer to per-pattern hit blob   |
| 0x13   | 9 B  | char[9]   | name                | Null-padded ASCII pattern name (e.g. "Rock1") |
| 0x1c   | 12 B | char[12]  | voice_slot_1        | Sample assigned to Slot 1 (e.g. "Kik1.raw")    |
| 0x28   | 12 B | char[12]  | voice_slot_2        | Sample assigned to Slot 2 (e.g. "SnrAmb.raw")  |
| 0x34   | 12 B | char[12]  | voice_slot_3        | Sample assigned to Slot 3 (e.g. "Snr1.raw")    |
| 0x40   | 12 B | char[12]  | voice_slot_4        | Sample assigned to Slot 4 (e.g. "Snr2.raw")    |
| 0x4c   | 12 B | char[12]  | voice_slot_5        | Sample assigned to Slot 5 (e.g. "HHC.raw")     |
| 0x58   | 12 B | char[12]  | voice_slot_6        | Sample assigned to Slot 6 (e.g. "HHO.raw")     |
| 0x64   | 12 B | char[12]  | voice_slot_7        | Sample assigned to Slot 7 (e.g. "HHCAmb.raw")  |
| 0x70   | 12 B | char[12]  | voice_slot_8        | Sample assigned to Slot 8 (e.g. "KikAmb.raw")  |
+-------------------------------------------------------------------------------------------------+
```

### 4.2 Pedal UI Order vs. ROM Order
At boot time, the pedal builds a pointer lookup table in RAM at **`0xc0182730`** (`tools/drums/ui_order.json`).
* Pattern `#07` (`Rock1`) maps to ROM record 7.
* Pattern `#44` (`Blues2`) maps to ROM record 27.
* UI Order covers 68 user-selectable patterns (00 `GUIDE` through 67 `Metro`).

### 4.3 Event Blob Encoding (Micro-Timing Hit List)
Each pattern's `event_ptr` points to a byte stream:
```
(delta_ticks: u8, value: u8){N}   loop_delta_ticks: u8   0xf0
```
* **`delta_ticks`**: Ticks since the previous event (0 = simultaneous chord hit). Running sum yields the absolute tick position.
* **`value` High Nibble (`value >> 4`)**: Voice ID (1 to 9).
  * `9`: Metronome Click (Slot 0).
  * `1`–`8`: Kit voice slots 1 through 8.
* **`value` Low Nibble (`value & 0x0f`)**: Step level / velocity (0 to 15).
* **Tick Resolution**: **12 ticks = 1 beat**.
  * 16th note = 3 ticks.
  * 8th-note triplet = 4 ticks.
  * 8th note = 6 ticks.
  * Quarter note = 12 ticks.
* **`loop_delta_ticks`**: Ticks from the final event back to the loop start.
* **`0xf0`**: Stream terminator byte.
* **Loop Length**: $\text{loop\_length\_ticks} = \text{last\_tick} + \text{loop\_delta\_ticks}$. This is **always** an exact multiple of $\text{beats\_per\_bar} \times 12$ (1 or 2 whole bars).

---

## 5. DSP Engine Parameters & Mathematics

| Parameter | Hardware Register | Value Range | Default | Audio Math / DSP Operation |
|---|---|---|---|---|
| **Master Tempo** | `0x11812f78` | 40 – 250 BPM | 120 BPM | $\text{ms\_per\_16th} = \frac{60000}{\text{BPM} \times 16}$<br>$\text{sec\_per\_tick} = \frac{60.0}{\text{BPM} \times 12}$ |
| **Drum Volume** | `0x11812f50` | 0 – 100 UI | 80 | $\text{gain} = \frac{\text{volume}}{100.0}$ applied at `0x11f03d14` |
| **Mixer Bus** | `0x11f039b0..0x11f03acf` | 9 slots | — | Planar buffer `int16_t[9][16]`, fetched every 16 samples by `11817520` |
| **Per-Voice Pan/Gain** | `0x11f03d24..0x11f03d48` | 9 x 4 bytes | — | Attenuation and stereo panning into L (`0x11f037b0`) and R (`0x11f037f0`) |
| **Voice Velocity** | Event low nibble | 0 – 15 | — | $\text{gain} = \frac{\text{level}}{15.0}$ (maps to MIDI velocity $\approx \text{round}(\frac{\text{level}}{15} \times 127)$) |
| **Metronome Accent** | Event at beat 0 | 15 vs 8 | — | Downbeat click is accented louder (Level 15) than other beats (Level 8) |
| **Run Flag** | `0x11f03d54` | 0 or 1 | 0 | 1 when running, 0 when stopped |

---

## 6. How to Import Into Another Project

Depending on your target stack, use one of the following three integration paths.

---

### Path A: Web / JavaScript / TypeScript (Web Audio API)
Ideal for Web apps, Electron, Tauri, React, Vue, Svelte, or VST Generative UI.

#### Step 1: Copy Assets
Copy either:
* Single modular JS: `tools/drums/comet_flower_data.js` (contains `window.COMET_FLOWER_DATA` with all 24 base64 WAVs and 69 patterns).
* Or raw files: `build/drums/wav/*.wav` and `build/drums/patterns.json`.

#### Step 2: Minimal Web Audio Player (< 40 Lines)
```javascript
import { COMET_FLOWER_DATA } from './comet_flower_data.js';

class ZoomDrumEngine {
  constructor() {
    this.ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 44100 });
    this.buffers = {};
    this.masterGain = this.ctx.createGain();
    this.masterGain.connect(this.ctx.destination);
  }

  async init() {
    for (const [key, sample] of Object.entries(COMET_FLOWER_DATA.samples)) {
      const binary = atob(sample.b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      this.buffers[key] = await this.ctx.decodeAudioData(bytes.buffer);
    }
  }

  playPattern(patternIndex = 7, bpm = 120, volume = 80) {
    const pat = COMET_FLOWER_DATA.patterns[patternIndex];
    this.masterGain.gain.value = volume / 100.0;
    const secPerTick = 60.0 / bpm / 12.0;
    const now = this.ctx.currentTime + 0.05;

    for (const ev of pat.steps) {
      if (!ev.mapped || !ev.sample) continue;
      const buf = this.buffers[ev.sample];
      if (!buf) continue;

      const src = this.ctx.createBufferSource();
      src.buffer = buf;

      const gain = this.ctx.createGain();
      gain.gain.value = ev.level / 15.0;

      src.connect(gain);
      gain.connect(this.masterGain);
      src.start(now + (ev.tick * secPerTick));
    }
  }
}
```

---

### Path B: Python Headless / CLI / DAW Exporter
Ideal for Python backends, machine learning pipelines, DAW script generators, or batch rendering.

#### Step 1: Copy Tools
Copy `tools/drums/drum_machine.py`, `tools/drums/raw2wav.py`, `tools/drums/decode_patterns.py`, and `build/drums/`.

#### Step 2: Authoring a New Pattern JSON
Create `my_beat.json`:
```json
{
  "name": "MyBeat",
  "bpm": 120,
  "bars": 2,
  "steps_per_bar": 16,
  "voices": {
    "Kik1.raw": [[0, 120], [8, 105], [10, 95]],
    "Snr1.raw": [[4, 115], [12, 115]],
    "HHC.raw":  [[0, 80], [2, 60], [4, 80], [6, 60], [8, 80], [10, 60], [12, 80], [14, 60]]
  }
}
```

#### Step 3: Render via CLI or Python Code
```bash
python tools/drums/drum_machine.py new my_beat.json --bpm 120 -o my_beat.wav
```
Or in Python:
```python
import json
from drum_machine import groove_from_json_voices, render, load_wav_mono_float, write_wav_mono_float

spec = json.load(open("my_beat.json"))
steps_per_bar, hits = groove_from_json_voices(spec["voices"], spec.get("steps_per_bar", 16))

sample_lookup = {
    name: load_wav_mono_float(f"build/drums/wav/{name.replace('.raw', '')}.wav")
    for name in hits
}

audio_float = render(steps_per_bar, spec["bpm"], spec["bars"], hits, sample_lookup)
write_wav_mono_float("rendered.wav", audio_float)
```

---

### Path C: C / C++ / JUCE Plugin / Embedded Microcontroller
Ideal for native plugins, Eurorack modules, or hardware drum machines.

```c
// Core Voice Descriptor
typedef struct {
    const int16_t* pcm_data;
    uint32_t length_samples;
    uint32_t current_pos;
    float gain;
    float pan_l;
    float pan_r;
    bool active;
} DrumVoice;

// Render 16-sample block (matching Zoom DSP hardware block size)
void render_drum_block(DrumVoice voices[9], float* out_l, float* out_r, float master_gain) {
    for (int i = 0; i < 16; i++) {
        float sum_l = 0.0f;
        float sum_r = 0.0f;

        for (int v = 0; v < 9; v++) {
            if (!voices[v].active) continue;
            if (voices[v].current_pos < voices[v].length_samples) {
                float sample = voices[v].pcm_data[voices[v].current_pos++] / 32768.0f;
                sum_l += sample * voices[v].gain * voices[v].pan_l;
                sum_r += sample * voices[v].gain * voices[v].pan_r;
            } else {
                voices[v].active = false;
            }
        }
        out_l[i] += sum_l * master_gain;
        out_r[i] += sum_r * master_gain;
    }
}
```

---

## 7. JSON Schemas

### 7.1 User Pattern JSON (`drum_machine.py new` format)
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ZoomUserPattern",
  "type": "object",
  "required": ["bpm", "bars", "steps_per_bar", "voices"],
  "properties": {
    "name": { "type": "string" },
    "bpm": { "type": "number", "minimum": 40, "maximum": 250 },
    "bars": { "type": "integer", "minimum": 1, "maximum": 16 },
    "steps_per_bar": { "type": "integer", "enum": [12, 16, 24, 32] },
    "voices": {
      "type": "object",
      "additionalProperties": {
        "type": "array",
        "items": {
          "type": "array",
          "items": [{ "type": "integer" }, { "type": "integer", "minimum": 0, "maximum": 127 }]
        }
      }
    }
  }
}
```

### 7.2 ROM Decoded Step Event Format (`patterns.json`)
```json
{
  "tick": 0,
  "delta": 0,
  "voice_id": 1,
  "level": 14,
  "slot": 1,
  "sample": "Kik1.raw",
  "mapped": true
}
```

---

## 8. Verification & Test Commands

Run the test suite to verify all sample envelopes, pattern tables, event blobs, and studio exports:
```powershell
pytest tests/test_drum_patterns.py tests/test_drum_samples.py tests/test_drum_event_blob.py tests/test_comet_flower_studio.py
```
*Current status:* **28 passed in 0.43s**.
