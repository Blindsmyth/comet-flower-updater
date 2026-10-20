# Owner Bench & Test Protocol — Updater 25 (2026-10-20)

**Updater Executable:** `build/c6745_bench_2026-10-20/GUITAR AUDIO 25 - bench + CF Master Preamp + probes + optimized rig TEST.exe`  
**Updater SHA-256:** `74535FD30EC557001B249B127C258E3F9954449E14BEAC5D8C3907634AA8286E` (short hash `74535fd3`)  
**Firmware:** Bench USB firmware `6e20051c` (ch 8 = CPU cycle timing frames for `tools/ua_bench.py`)  
**Filesystem:** `build/c6745_bench_2026-10-20/fs_c6745_bench25.bin` (50 files, 23 installed: includes `CFMPRE.ZD2`)

---

## Numbered Test Protocol

### Step 1: Flash Updater 25
1. Disconnect USB and power.
2. Hold down **both footswitches** (FS1 and FS2) while plugging in USB to enter `FIRMWARE UPDATE` mode.
3. Run `GUITAR AUDIO 25 - bench + CF Master Preamp + probes + optimized rig TEST.exe`.
4. Click **Execute** and wait for `Complete!`.
5. Reconnect USB while holding **Slot 1 button** to boot into USB audio / bench mode.

---

### Step 2: Multi-Slot Memory Probes (CFM2P, CFM5P)
*Goal: Determine if Zoom's slot allocator grants multi-slot effects a larger memory heap (> 40 KiB).*

1. In an empty patch, place **CFM2P** (2-slot memory probe) in slot 1.
2. Record ~5 seconds of audio from the pedal output or capture channel.
3. Place **CFM5P** (5-slot memory probe) in slot 1.
4. Record ~5 seconds of audio.
5. Run the tone decoder:
   ```cmd
   .venv\Scripts\python.exe tools\decode_memprobe.py <recorded_file.wav>
   ```
6. **Key Question Answered:** Does the probe report available memory = 40,960 B, 81,920 B, or 204,800 B?

---

### Step 3: Test CF Master Preamp Stage (CFMPRE)
*Goal: Verify real-time execution of the 2-slot Preamp stage on hardware.*

1. In an empty patch, place **CFM Pre** (`CFMPRE.ZD2`) in slot 1. It occupies 2 slots on screen.
2. Verify:
   - 12 active parameters appear across the pages (Muff Sust, Tone, Vol, On; Mist Rate, Rang, Colr, Mtrx; Dyna Sens, Out, On; Pre Level).
   - Audio plays cleanly through DynaComp $\to$ Big Muff $\to$ Electric Mistress.
   - Knobs respond smoothly without audio dropouts or DSP overload.

---

### Step 4: Bench Rebuilt Single-Slot Effects
Run `CF Bench - measure patch.cmd` (or `tools\ua_bench.py`) with each effect active alone in an empty patch at default knobs:

| Effect | Expected Cycles (Phase D Static) | Prior Measured (10-18) | Expected Result | Anomaly Flags |
|---|---|---|---|---|
| **CF RAT** (`RATX.ZD2`) | **~10.5k** | 16.0k | ≥ 30% reduction from stage-major loop | > 15.0k indicates cache miss |
| **CF 808** (`DRV808X.ZD2`) | **~11.8k** | 16.2k | ≥ 25% reduction from 128-trip vector | > 15.5k |
| **CF Watt 2x** (`DR103.ZD2`) | **~19.2k** default / **~23k** cranked | 20.6k default / 25.1k cranked | ~1.5k reduction from 2-pass tube split | > 26.0k |
| **CF RA200** (`RA200X.ZD2`) | **~4.0k** (steady) | (new) | Steady ~4k; slight surge only when turning Treble/Bass | Steady > 8k |
| **CFM Pre** (`CFMPRE.ZD2`) | **~28.5k** (all active) | (new) | Dyna (~7.8k) + Muff (~14.5k) + Mistress (~6.6k) | > 35k |

---

### Step 5: Ear Test & RA-200 / Gain Staging Calibration
1. **RA-200 Stereo Check:** Place CF RA200 in the MOD slot. Listen in stereo headphones or monitor speakers. L and R should reproduce the two distinct 120-degree mic angles.
2. **Rotor Speeds:** Test Rotor modes 0 (Bypass), 1 (Slow chorus, default 1.7 Hz modulation), and 2 (Fast tremolo/chorus, default 6.6 Hz).
3. **Gain Staging:** Chain `CFM Pre -> CF Delay -> CF Watt -> CF RA200`. Play a sustained *Comfortably Numb* lead line with patch level at 80. Verify output headroom and note whether any digital harshness or clipping occurs.

---

### Step 6: Feed Hardware Cycle Counts into dspload
Once hardware cycle counts are captured by `tools/ua_bench.py`:
```cmd
.venv\Scripts\python.exe tools/zd2_set_dspload.py build/RATX.ZD2 <measured_cycles>
.venv\Scripts\python.exe tools/zd2_set_dspload.py build/DRV808X.ZD2 <measured_cycles>
.venv\Scripts\python.exe tools/zd2_set_dspload.py build/DR103.ZD2 <measured_cycles>
.venv\Scripts\python.exe tools/zd2_set_dspload.py build/CFMPRE.ZD2 <measured_cycles>
```
