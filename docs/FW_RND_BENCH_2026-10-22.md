# Owner test protocol — Updater 26 (2026-10-22)

**Updater:** `build/fw_rnd_2026-10-22/GUITAR AUDIO 26 - bench + CF M3-M4 probes + CF Rotary + CFMPRE pages TEST.exe`
**SHA-256:** `cc8714b5737153aefba552872e13886303522beb4a44d891a8f31463651e60cc` (short `cc8714b5`)
**Firmware:** bench USB firmware `6e20051c` (unchanged from Updater 25; ch 8 = timing frames for `tools/ua_bench.py`)
**File system:** `build/fw_rnd_2026-10-22/fs_bench26.bin` (`d15e6c6b`): Updater 25's image plus
`CFM3P`, `CFM4P`, `ROTX` and the re-laid-out `CFMPRE` (53 files, 26 installed).
Stages: file system 0x102000 and main firmware 0x033000 only (boot program, presets untouched).
Recipe (reproduces Updater 25 byte for byte with its own image): `make_g1_image.py --replace build/CFMPRE.ZD2
fs_c6745_bench25.bin fs_bench26.bin build/CFM3P.ZD2 build/CFM4P.ZD2 build/ROTX.ZD2` then
`make_fs_restore_updater.py <v2.00 updater> "<name> TEST.exe" --test-controller-fw
build/cf_bench_2026-10-17/res1_cf_usb_bench.bin --image fs_bench26.bin`.

Background: `docs/FW_RND_ANSWERS_2026-10-22.md`.

## 1. Flash
Same as Updater 25: hold both footswitches while connecting USB, run the updater, Execute, wait for
`Complete!`, reconnect.

## 2. Slot-count ceiling (CF M3 / CF M4) — never save these in a patch
The firmware rejects a slot count above 4 when it reads an effect file (c0129908).
Prediction: **CF M3 and CF M4 appear in the effect list; CF M5 still does not.**
1. Open the effect list and look for `CF M3`, `CF M4`, `CF M5`. Note which are offered.
2. If offered: put CF M3 in slot 1 of an empty patch. Note how many slots the screen shows as used and
   whether more effects can still be added after it. Same for CF M4.
3. Optional: Mode 1 tone report as for CF M2 (`tools/decode_memprobe.py`); expected: slot-0 resources only.
4. Leave the patch without saving.

## 3. CFMPRE page layout (photos wanted)
New order, one stage per page: `Dyn Sens / Dyn Out / Dyn On`, `MuffSust / MuffTone / Muff Vol`,
`MistRate / MistRang / MistColr`, `Muff On / Mist Mtx / Level`. Labels are now 8 characters or fewer.
1. Put CF Pre in slot 1 and page through its parameters.
2. **Photograph each page.** This settles how many params a page shows and whether 8-char labels clip;
   the static analysis did not find the screen code that decides it.
3. Note: an old saved patch with CFMPRE now has its knobs in the old order (values land on other params).

## 4. CF Rotary (replaces RA200X for now)
`CF Rotary` (ROTX): mono horn/drum rotary, params Speed (0 slow / 1 fast), Depth, Ramp, Mix.
No stack use, about 2.8k cycles static estimate, declared load 16.
1. Alone in slot 1: audio passes; Speed 0 -> 1 ramps up, Ramp sets how slowly.
2. **Crash test:** CF Pre, Watt (or Delay), CF Rotary, then add one more effect after it. RA200X crashed
   USB audio here; CF Rotary should not. Watch the USB audio stream and the screen.
3. Bench: `tools/ua_bench.py run` with CF Pre + Delay + Watt + CF Rotary; report the slot medians
   (expected CF Rotary well under 5k).

## Report back
- Which of CF M3 / M4 / M5 are offered, and slots shown used.
- Photos of the CF Pre pages.
- CF Rotary: sound OK?, crash test result, bench numbers.
