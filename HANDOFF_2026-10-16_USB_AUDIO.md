# Handoff 2026-10-16 (evening): USB audio works

Supersedes the queue in `HANDOFF_2026-10-16.md` for USB audio. Full run log with numbers:
`docs/CF_USB_MODE_2026-10-16.md` (runs 1-9). Commits this session: `5bd958c..b536eba` (not pushed).

## State

**The pedal streams its real output to the PC over USB, clean.** Owner flashed the tap TEST build
(`de0925d4…`) and confirmed "successful". Claude's check (`build/ua_takes/take_20261016_170441.wav`, WASAPI
exclusive): real audio, full rate (441,000 frames in 10.1 s of wall time, i.e. nothing dropped), L == R,
-42 dBFS rms / -27 dBFS peak (owner's playing level unknown; see open item 2).

How it is turned on: power on holding **slot 1** (B4). COMET FLOWER page: STAT ON, HOST > 0. Windows shows
**"Line (Comet Flower ZG1X4 MIDI)"** under Recording; the MIDI port stays. USB mode is never remembered:
a normal power-on is plain effects mode.

## What was wrong (and fixed), in order

| Run | Symptom | Cause | Fix (commit) |
|---|---|---|---|
| 3 | STAT ON, no Windows input | usbaudio bound MI_02, but the capture endpoint was hidden (DeviceState 0x10000001): input terminal 0x0601 "Analog connector" | terminal 0x0603 "Line connector" (`5bd958c`) |
| 5-8 | real audio "static / garbled", later "in and out" | 8-63 % of USB packets reached the host empty or cut to 1-2 frames; pedal side clean (every packet loaded, no UnderRun, no missed SOF) | — (diagnosed with the pattern builds) |
| 9 | variants build compared FIFO set-ups in one take | POWER.ISOUpdate on: 81 % delivered; single buffer: 50 % (pedal overruns); **double buffer + ISOUpdate off: 99.9 %** | `usb_audio_set_alt(1)` clears ISOUpdate (`b536eba`) |

The ISOUpdate loss is host-condition dependent (the owner's VPBE take of the same build lost ~0 with it on, Claude's
exclusive capture lost 19 %); with it off every take so far was clean.

## Builds (owner use only: they contain Zoom's firmware code)

| Folder (`build/…_2026-10-16/`) | Updater SHA-256 | What |
|---|---|---|
| `cf_usb_audio_tap` | `de0925d4` | **current**: real audio out (fw `32afe08d`). Desktop copy: `GUITAR AUDIO - Comet Flower USB tap TEST.exe` |
| `cf_usb_mode` | `54e157b2` | silence stream (fw `a79a305c`) |
| `cf_usb_audio_variants` | `7e2a9961` | diag: test pattern + pedal counters, cycles 4 FIFO set-ups every 4 s |
| `cf_usb_audio_pattern` | `e3cdc633` | diag: test pattern + counters, old set-up (ISOUpdate on). Superseded by variants |

All packaged with `--test-controller-fw` on `make_controller_fw.py --base build/fw/res1_cf_usbname.bin --ui
--usb-product "Comet Flower ZG1X4 MIDI"`, presets `build/fw/cfupd_res85.bin`, image
`build/cf_release_2026-10-16/fs_cf.bin`. Rebuild = those + `make_usb_audio_fw.py [--tap | --tap-pattern]`.

**Pitfall (cost two flashes):** the variants/pattern folders sit next to the tap folder and their names look
alike. The test tone means a diag build is on the pedal. Check: `ua_capture.py` reports "pattern take".

## Tools added

- `tools/ua_capture.py`: records the pedal input in WASAPI exclusive mode (no Windows mixer, no dither);
  `--wav` analyses an existing take; `--list` lists inputs. Pattern takes: every lost/repeated/inserted/
  corrupt frame, plus the pedal's in-band counters (packets loaded vs received, TxPktRdy skips, UnderRun,
  missed frames, ring fill, TXCSR, loss per FIFO variant). Guitar takes: level, clipping, zero runs, clicks.
  Needs `sounddevice` (installed in `.venv`). Takes go to `build/ua_takes/`.
- `make_usb_audio_fw.py --tap-pattern`: the tap build with the test signal (L = frame counter, R = 1002 Hz
  sine by full count, diag word in each packet's first frame). VPBE takes (float32, shared mode) convert
  exactly: `round(x * 32768)` then `ua_capture.analyse_pattern`.
- Claude can read Windows' view directly: `Get-PnpDevice` (VID_1686&PID_04A1, MI_02 = audio), the MMDevices
  Capture registry (DeviceState), parent hub via DEVPKEY_Device_Parent.

## Open items (next session)

1. **Motherboard root port 13: Windows Code 10** (0xC0000001, HOST 34) with the variants build, after two power
   cycles; the same pedal enumerates on the GL850G hub. Earlier the diag build streamed on a root port
   (run 8). Try the tap build on another motherboard port; if Code 10 repeats, compare descriptor fetch counts.
   Restarting the device needs admin (`pnputil /restart-device`).
2. **Level:** guitar take peaked at -27 dBFS. Have the owner play loud and record with `ua_capture.py`; if the
   peak stays far below 0 dBFS, check the tap's high-half truncation vs the stock pack scaling
   (`usb_audio_tap.c` `ua_tap_sample`).
3. **Long-run check:** 5-10 min take with the tap build (clicks, zero runs, ring underruns). For a sample-exact
   check flash the variants build and look at variant 0 only (it now is the shipping set-up).
4. **The 1-frame repeat+gap pairs** seen in runs 6-8 (a frame replaced by its predecessor, ~4/s). Not seen per
   variant yet; check in a variant-0 pattern take.
5. **Owner design wishes (later):** MIDI port hidden from the host until the pedal is in MIDI mode (Learn finding
   nothing outside MIDI mode is intended); MIDI and USB-audio modes from the settings menu (menu item exists:
   COMET FLOWER page, knob 2 USB OFF/AUDIO, software replug, not yet hardware-tested).
6. CPU budget: measure the tap's per-block cost with CF ClkT alongside a full 5-slot patch before calling USB
   audio "release".
7. Release path: the strict packager still refuses the audio layer; decide when USB audio graduates from TEST.

## Pedal / PC facts learned

- The pedal normally sits behind a Genesys GL850G hub (`USB\VID_05E3&PID_0608`, single TT) on the USB 3.0 root,
  shared with a TP-Link Wi-Fi adapter, a Bluetooth adapter and a Logitech receiver. Works with the fix.
- Windows hides capture endpoints whose input terminal is 0x0601; 0x0603 shows as "Line (…)".
- MUSB EP1 here: FIFO 0x140, 2 x 256 B (TXFIFOSZ 0x15), TXMAXP 180, POWER.ISOUpdate must be off; TXCSR at SOF
  reads 0x0002 (one bank queued) in steady state.
- C674x payload rules: a `switch` became a jump table in `.switch`, which the build refuses ("needs run-time
  support"): use an array. `/` and `%` were avoided up front (they may call RTS divide helpers, which the
  payload does not link; not tested): use countdowns. The build check catches both.

## Update, late evening (optimisation pass)

Details: `docs/CF_USB_MODE_2026-10-16.md` (last four sections), helper reports `docs/helpers/USB_OPT_*_2026-10-16.md`.
- 5-min long run on tap: full rate, 0 dropouts. Tap CPU (static) ~0.4 % of a block.
- **Start-splice bug fixed** (1 in ~15 stream opens: host polls late, ring overran, splice 128 frames in):
  **tap2 TEST updater `d6e62256`** (fw `72e97df5`), desktop `GUITAR AUDIO 2 - Comet Flower USB tap2 TEST.exe`.
  Not flashed yet. After flashing: 15 x 3 s opens into `build/ua_takes/starts_tap2/`, expect no event at ~217.
- `ua_capture.py` now has Argon's linear-prediction defect detector (lost / repeat / zero / jump, "N defects in M min");
  a normal take can now prove "no dropouts". A host-side first-buffer replay (exact copy, priming included) can occur
  at stream start: not the pedal.
- Port 13 Code 10: not the ZLP case (stock EP0 sends one) and not the first descriptor fetch; the composite
  device failed at start-up. Retest on port 13 with tap2.
- Level: USB follows the digital master volume (MVOL) and patch level (both before the tap). Turn master up to record.
- 24-bit option: EP1 2 x 512 B fits at 0x140 unchanged (stock uses 320 B of 4 KB FIFO RAM). Not built; owner's call.
- Astra (Codex) capped until 22:28 2026-10-16.

## Update, 2026-10-17 ~00:30: port 13 cause and tap3

Port 13 Code 10 = the pedal STALLs SET_CONFIGURATION in USB-audio mode only (USB ETW traces, `tools/usb_etw_trace.ps1`).
Suspect: our 192-byte (3 x 64) configuration descriptor sends Windows' wLength-255 read through the stock ZLP ending.
**tap3 TEST updater `393d1112`** (desktop `GUITAR AUDIO 3 - Comet Flower USB tap3 TEST.exe`) = tap2 + a 195-byte
descriptor. Not flashed yet. Test on port 13 with slot 1 held; then the 15-open splice check with the guitar cable
plugged in (quiet takes are now reported "too quiet to judge").
