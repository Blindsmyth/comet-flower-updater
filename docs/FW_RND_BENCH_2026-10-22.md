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

## Results so far (owner, 2026-10-22)
- CF M3 and CF M4 are listed; placing either gives **PROCESS OVERFLOW!! CHANGE EFFECT** (photos).
- CF Pre edit pages: 3 params per page, PAGE 1/4..4/4; `Dyn Sens / Dyn Out / Dyn On` read cleanly,
  `MuffSust / MuffTone / Muff Vol` run together.
- **CF BYPT (26b): the beep is heard while the effect is OFF; ON passes the guitar clean.** The firmware
  keeps calling a bypassed effect, so delay tails need no firmware patch (CF Delay `Tail`, Updater 27).
- **CF Rotary:** good alone in slot 1, good after a comp and a RAT, sound stable, and **passes the
  crash case**: CFM Pre, CF Delay, CF Hiwatt, CF Rotary, CF Delay (an effect after the rotary) runs with
  USB audio intact. RA200X's crash is solved by replacement.
- **Bench of that patch** (`ua_bench.py measure`, 6 s, 16,530 blocks, 0 lost; `build/bench/manual.md`):
  slot medians 29.2k / 5.7k / 23.4k / 5.1k / 7.4k cycles (CFM Pre, CF Delay, CF Hiwatt, CF Rotary,
  CF Delay + end-of-chain), maxima 43.7k / 17.0k / 37.5k / 15.9k / 19.1k; CPU 83.2 % average, peak 106.6 %
  of the 132,354-cycle block. CF Rotary costs about an empty slot's framework overhead.

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
5. Prediction from the firmware (docs/FW_RND_ANSWERS_2026-10-22.md, S8): CF M3 and CF M4 are listed and
   each shows as **one** slot (the UI's effect-width function is a stub returning 1). Optional check of the
   same thing with a stock effect: add a stock 2-slot amp (e.g. `BG MK1`, `MS 1959`) to an empty slot from
   the list; prediction: it also takes one slot (factory presets that show it double-width carry an
   explicit second-half marker).

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

## 6. Updater 27: slot watchdog + CF Delay tail + CFM Pre labels (after 26/26b; TEST build)
**Updater:** `build/fw_rnd_2026-10-22/GUITAR AUDIO 27 - bench watchdog + CF Delay tail + CFM Pre labels TEST.exe`
**SHA-256:** `7a4b7835e3397d3509f1a9099208addcb43a9063860733f2a6886cfd74d84f6f` (short `7a4b7835`).
Firmware `001c3a26` = bench firmware `6e20051c` plus the watchdog (`make_usb_audio_fw.py --watchdog`);
file system `fs_bench27.bin` (`d8fbc587`) = the 26b effects with the new CF Delay (`DLYX`, 4th knob `Tail`) and
CFM Pre relabelled after the photos (`Dyn Sens`, `Mf Sust`, `Fl Rate`, ... at most 7 letters).
A slot that takes more than 64k cycles per block for
16 blocks in a row (about 6 ms) is switched to a do-nothing function: that slot then passes the guitar dry
until you pick another effect for it or reload the patch. `tools/ua_bench.py` shows bypassed slots as
`tripped` (bit k = slot k+1).
1. Normal patches: nothing changes (no effect we have comes near 64k; the heaviest median is 31k).
2. **RA200X crash re-test:** CF Pre, Watt, RA200X, then one more effect. If RA200X's slot goes dry and
   USB audio keeps running, the crash was a cycle overrun and the watchdog contains it. If the pedal or USB
   still dies, RA200X faults (bad memory access), which only fixing the effect can cure.
3. Bench capture while doing step 2 shows the tripped bit.
4. **CF Delay tail** (only meaningful if step 5's CF BYPT beeped while OFF): CF Delay, Tail 1 (new default),
   Regen ~60. Play a note, switch the delay OFF: the repeats should ring out instead of stopping. Tail 0 =
   the old behaviour. Old saved patches with CF Delay load Tail 0.

## 7. Updater 28: CF Probe watch stream (replaces 27; TEST build)
**Updater:** `build/fw_rnd_2026-10-22/GUITAR AUDIO 28 - CF Probe watch + watchdog + 27 effects TEST.exe`
**SHA-256:** `e9e26f1e1e89f22a136a7ef4c8f88b748c880b555554f5b0416aca1f7b566985` (short `e9e26f1e`).
Firmware `efbf4466` = the bench firmware plus the watchdog and the **watch stream** (`make_usb_audio_fw.py
--probe --watchdog`); file system `fs_bench27.bin` (same effects as Updater 27). Everything in 27 works the
same, except USB channel 7 now carries the watch stream instead of the DI (channel 8 still carries the
bench timing frames). The firmware streams 32 looper/drum/master values live (CF Probe watch list v1).
1. Flash, connect, open nothing else on the USB audio device.
2. I run `tools/cf_probe.py watch --seconds 10 --csv ...` while you: start/stop the drum machine, change
   pattern and tempo, record/play/stop/overdub/undo a loop. Each action shows up as values changing.
3. All Updater 27 checks (CF Delay tail, CFM Pre labels, watchdog on RA200X) also apply here.

## 8. Updater 29: CF Probe link, SysEx + watch (replaces 28; TEST build)
**Updater:** `build/fw_rnd_2026-10-22/GUITAR AUDIO 29 - CF Probe link (SysEx peek + watch) + watchdog + 27 effects TEST.exe`
**SHA-256:** `b8979b5211f85b904c801b3e6afd829051d29c268cd2a2c45ee84f5ce3ae5030` (short `b8979b52`).
Firmware `d2af52c7` = Updater 28's firmware plus the SysEx hook (c0129324 -> cfp_sysex_thunk, header
c012933c), file system `fs_bench27.bin`. Everything in 27/28 works the same. New: the pedal answers
`tools/cf_probe.py` over USB MIDI:
- `ping` (link check), `peek <addr> [len]` / `dump <addr> <len> <file>` (RAM only), `watch-set <addr>...`
  (changes what channel 7 streams, no reflash), `watch` (records channel 7).
1. Flash, connect, close any editor that holds the MIDI port.
2. I run `tools/cf_probe.py ping`, then peeks and watches while you work the looper and the drum machine.
If MIDI stops answering or the pedal misbehaves on a stock editor action, reflash Updater 27: the hook
sits only in the MIDI task's end-of-SysEx path; audio does not pass through it.

## 9. Updater 30: CFM Pre 5-character labels (replaces 29; TEST build)
**Updater:** `build/fw_rnd_2026-10-22/GUITAR AUDIO 30 - CF Probe link + CFM Pre 5-char labels TEST.exe`
**SHA-256:** `243884b737923274d2f73314b2129b991968a4f9c89fc6ca834ba13388a01bb3` (short `243884b7`).
Same firmware as 29 (`d2af52c7`, CF Probe link + watchdog); file system `fs_bench30.bin` = fs_bench27 with
CFMPRE relabelled (DSens DOut DynOn | MSust MTone MVol | FRate FRang FColr | MufOn FMtx Level) and
header 0x58 = 1. Owner results on 29: CF Delay tail works; CFM Pre labels unreadable (live screenshot: 31 px
columns, 6 px font, so 5 characters max).

## 10. Updater 31: CF edit-page header (replaces 30; TEST build, 2026-10-23)
**Updater:** `build/fw_rnd_2026-10-22/GUITAR AUDIO 31 - CF Probe link + CF edit header TEST.exe`
**SHA-256:** `5299566686b3d21a67ac7a8fcb567b0c3b3f8bbc23179704af83b200003dbf1b` (short `52995666`).
Firmware `8ee11e29` = Updater 30's firmware (`d2af52c7`, reproduced byte for byte) plus `--cf-header`
(`make_controller_fw.py`): both CALLPs of the stock edit-page renderer c012e5a8 (c013c050, c0135b08) go
through `cf_edit_draw` (firmware/controller/cf_header.c), which runs the stock renderer, then replaces
the effect-name box with an inverted bar "CFM PRE><stage>" (pages DYNA COMP / MUFF FUZZ / MISTRESS /
OUTPUT). Only CFM Pre has a stage table; every other effect is drawn exactly as stock. File system
`fs_bench30.bin` (same effects as 30). Background: `docs/EDIT_SCREEN_TRACE_2026-10-23.md`. Recipe:
`make_controller_fw.py --base build/fw/res1_cf_usbname.bin --ui --cf-header --usb-product "Comet Flower
ZG1X4 MIDI" --usb-audio-name "Comet Flower Audio Bridge"` -> `make_usb_audio_fw.py --probe --watchdog` ->
`make_fs_restore_updater.py <v2.00 updater> "<name> TEST.exe" --test-controller-fw <fw> --image fs_bench30.bin`
(without `--cf-header` the same recipe gives Updater 30, `243884b7`).
1. Flash, select CFM Pre, page through 1/4..4/4: the header names the stage; screenshot each page
   (`tools/cf_probe.py screenshot`).
2. Turn knobs, switch effects and back, open/close Settings, Tuner, Rhythm/Looper: no stock "CFM Pre" box
   flashing through, no garbage, other effects look stock.
If anything looks wrong, reflash Updater 30.
**Result (owner, 2026-10-23):** flashed Updater 31, checked the screens on the pedal: header good.

## 11. Updater 32: CF WattL next to CF Watt (replaces 31; TEST build, 2026-10-23)
**Updater:** `build/fw_rnd_2026-10-22/GUITAR AUDIO 32 - CF edit header + CF WattL TEST.exe`
**SHA-256 (short):** `7015a3cb`. Firmware = Updater 31's (`8ee11e29`, edit header + CF Probe link +
watchdog). File system `fs_bench32.bin` (`541cd63f`) = fs_bench30 + `DR103L.ZD2` (`0d7155ad`, CF WattL,
id 04000f8a): the cheaper Hiwatt core (`effects/common/hiwatt_lite.h`, commit f232dee), same knobs and
sound as CF Watt (host bench: output within 8e-6, 36/36), static estimate -18 %.
1. Flash. Owner's CN patch as before: CFM Pre, CF Delay, CF Watt, CF Rotary, CF Delay. In USB audio mode,
   `tools/ua_bench.py run`: slot medians and peak (baseline: CF Watt slot 23.4k, peak 107 %).
2. Same patch with CF WattL in slot 3 (same knob values): bench again. Pass = lower slot median and peak.
3. By ear: Watt vs WattL, same settings, clean and cranked; they should be indistinguishable.

## 12. Updater 33: CPU budget meter (replaces 32; TEST build, 2026-10-23)
**Updater:** `build/fw_rnd_2026-10-22/GUITAR AUDIO 33 - CF header + CPU meter + CF WattL TEST.exe`
**SHA-256 (short):** `b29f89c8`. Firmware `a64a9e62` = `make_controller_fw.py ... --ui --cf-header` ->
`make_usb_audio_fw.py --probe --watchdog --cpu-meter`; file system `fs_bench32.bin` (CF WattL included).
Design: `docs/BUDGET_MODEL_2026-10-23.md`. Without the two new options the recipe still gives `d2af52c7`.
1. Flash. On the edit page of any effect the top right corner shows "NN%": the worst audio-block load of
   the last ~0.74 s (the bench's CPU % figure). CFM Pre's bar reads "PRE>DYNA COMP" etc. next to it.
2. Build the CN patch slot by slot and watch the number rise; open Settings/Tuner/Rhythm and come back: the
   meter must not draw on other screens, and must come back on the edit page.
3. Ceiling test (when convenient, USB audio mode for `ua_bench.py`): add probe10/probe30, raise Load until
   frames are lost or the screen freezes; note the meter just before.

## 13. Updater 34b: Updater 33 + PROBE10 / PROBE30 (replaces 33; TEST build, 2026-10-23)
**Updater:** `build/fw_rnd_2026-10-22/GUITAR AUDIO 34b - Updater 33 + PROBE10 PROBE30 listed TEST.exe`
**SHA-256 (short):** `d11591f9`. Firmware = Updater 33's (`a64a9e62`, `build/cf_header/res1_cf_meter.bin`;
the recipe reproduces 33 `b29f89c8` byte for byte). File system `fs_bench34.bin` (`8565379b`) =
`make_g1_image.py fs_bench32.bin fs_bench34.bin build/PROBE10.ZD2 build/PROBE30.ZD2`: both files AND their
effect-list entries (FLST_SEQ.ZT2, 149 -> 151; PROBE 10 id 07000f83 dspload 10, PROBE 30 id 07000f82
dspload 30, SFX group next to CF BypTest).
**Updater 34 (`f7fe7443`, deleted) was broken:** files added with g1fs.build_image alone, no effect-list
entry, so the pedal did not list them (owner). Always add effects with `make_g1_image.py`.
Steps: as section 12, then the ceiling test: PROBE 10 / PROBE 30 "Load" knob = Load x 200 dependent
multiply-adds per block; raise it until frames are lost / the screen freezes and note the meter.

## 14. 0.34.2: 34b + build number on the start-up screen (TEST build, 2026-10-23)
**Updater:** `build/fw_rnd_2026-10-22/GUITAR AUDIO 0.34.2 - Updater 33 + probes + build-number splash TEST.exe`
**SHA-256 (short):** `1907a6e2`. Same firmware (`a64a9e62`) and FS (`fs_bench34.bin`) as 34b, plus the presets
region 0x28000 = `build/fw/cfupd_res85.bin` (the CF presets, same as before) with the start-up screen
"CF-ZGX4 / TEST 0.34.2" (`tools/make_splash.py`). Stages: 0x28000 presets, 0x102000 FS, 0x33000 firmware.
Version list: `docs/BUILDS.md`. Live patches (0x0C0000) are not touched.
1. Flash; at power-on the screen after the logo reads "CF-ZGX4 / TEST 0.34.2".
2. Then section 12's steps and the ceiling test with PROBE 10 / PROBE 30.
3. Ceiling test, automated read-out: `tools/ceiling_test.py watch --csv build/ceiling.csv` reads the meter
   over MIDI (~4 per second: peak %, mean %, per-slot kcycles) while the owner turns PROBE Load by hand;
   it stops and reports by itself on a freeze (AUDIO STALL = MIDI alive, audio counter stopped; NO REPLY =
   pedal frozen) with the highest reading and the last readings. Hands-free: `ceiling_test.py set 3 2 50`
   (Zoom param-edit SysEx, unconfirmed on this pedal: check the knob moves), then
   `ceiling_test.py ramp <slot> --step 5 --hold 2`.

### 0.34.2 ceiling test, first result (owner, 2026-10-23)
PROBE 10: Load 33 -> meter 49-50 %; at Load ~40 it "froze" and the meter fell to 8 %. PROBE 30: Load ~40 ->
55-60 %, then the same. Reading: the slot **watchdog** (64k cycles/block for 16 blocks = 48 % of the 132354-cycle
block) cut the probe slot to dry; 8 % = the rest of the patch still running. So this is our watchdog limit,
not the hardware ceiling (the bench saw a 107 % peak on the CN patch without a crash). Load -> about 1.27 %
per step (~1.7k cycles). Next: PROBE 10 + PROBE 30 in two slots, each below Load ~35, raised in turns, with
`ceiling_test.py watch`; open question: did screen/knobs stay alive (watchdog) or did the pedal lock up?

### 0.34.2 ceiling test, two slots (owner + probe link, 2026-10-23)
PROBE 30 slot 1 Load 35 (58.5k cycles) + PROBE 10 slot 2, turned up slowly: at Load 33 (55.3k) the pedal
stopped responding (owner: screen, knobs, everything). Probe link at the same time (`build/ceiling.csv`,
3 min): MIDI still answers, audio loop runs at the full 2756 blocks/s (44.1 kHz / 16), busy mean 91.9 %,
peak 93-95 % (max 95.3 %), no watchdog trip. So the DSP keeps up; the **control side starves** (UI task:
screen and knobs get no CPU time once the audio Swi + other interrupts leave none). At PROBE 10 = 32
(~90.6 % mean) the pedal was still usable.
**Usable ceiling: about 90 % on the meter (busy mean ~90 %); 92 % = control lock-up.** Next: meter warning
from 88-90 %; re-declare CF dspload from measured cost so Zoom's gate stops a patch before ~88 %.
