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

## 5. Updater 26b: bypass-call probe (after the steps above)
**Updater:** `build/fw_rnd_2026-10-22/GUITAR AUDIO 26b - bench + Updater 26 + CF BypTest TEST.exe`
**SHA-256:** `30c1fc595b829abfb70f5dbeeb39d1f3ca6722bcc8a1f4d9c4cb76b61d227ba7` (short `30c1fc59`); file system
`fs_bench26b.bin` (`e4aa8cbf`) = fs_bench26 plus `BYPT.ZD2`. Same firmware and stages as 26.
Question: does the firmware still call an effect that is switched OFF? (Decides whether a CF delay can
ring out its tail after bypass with no firmware patch; docs/helpers/FW_RND_S9_BYPASS_2026-10-22.md.)
1. Put `CF BYPT` in slot 1 of an empty patch (Beep 30). Play: with it ON the guitar is unchanged.
2. Switch it OFF. **A quiet 880 Hz beep while OFF = the firmware keeps calling it** (tails possible).
   No beep while OFF = it is not called when bypassed (tails need a patch).
3. Optional: move it to slot 3 with other effects around it; same check. Never save it in a patch.

## 6. Updater 27: slot watchdog (after 26/26b; TEST build)
**Updater:** `build/fw_rnd_2026-10-22/GUITAR AUDIO 27 - bench watchdog + Updater 26b effects TEST.exe`
**SHA-256:** `30eb32d4d5c71bcc2a42ab0f48b463650247f6671f26fc4d27face22219b3b3e` (short `30eb32d4`).
Firmware `001c3a26` = bench firmware `6e20051c` plus the watchdog (`make_usb_audio_fw.py --watchdog`);
file system `fs_bench26b.bin` (same effects as 26b). A slot that takes more than 64k cycles per block for
16 blocks in a row (about 6 ms) is switched to a do-nothing function: that slot then passes the guitar dry
until you pick another effect for it or reload the patch. `tools/ua_bench.py` shows bypassed slots as
`tripped` (bit k = slot k+1).
1. Normal patches: nothing changes (no effect we have comes near 64k; the heaviest median is 31k).
2. **RA200X crash re-test:** CF Pre, Watt, RA200X, then one more effect. If RA200X's slot goes dry and
   USB audio keeps running, the crash was a cycle overrun and the watchdog contains it. If the pedal or USB
   still dies, RA200X faults (bad memory access), which only fixing the effect can cure.
3. Bench capture while doing step 2 shows the tripped bit.
