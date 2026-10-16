# USB-audio mode: TEST build (2026-10-16)

Folder: `build/cf_usb_mode_2026-10-16/` (owner use only: it contains Zoom's firmware code).

| File | SHA-256 (start) | Contents |
|---|---|---|
| `Comet Flower G1X4 Updater (USB mode TEST build).exe` | `6d8c936aae847aaa` | Menu candidate + USB-audio silence layer |
| `res1_cf_usb_mode.bin` | `97c3a6d87b939941` | `make_controller_fw.py --ui --usb-product …` then `make_usb_audio_fw.py` |

Packaged with `--test-controller-fw` (the strict release path refuses the audio layer). Presets and
effects as in the release. **Not flashed. First hardware run of any USB-audio code.**

## What it is

Everything in `docs/CF_MENU_PAGE_2026-10-16.md` (settings page, slide, port name), plus the USB-audio
*silence* layer (`docs/USB_AUDIO_SILENCE_CANDIDATE_2026-10-15.md`): when USB mode is on, Windows should
see a second device function, a 2-channel 16-bit 44.1 kHz USB microphone ("Comet Flower ZG1X4 MIDI"
audio) that streams **silence**. Real pedal audio is the next step (the tap build) once this enumerates.

## Off unless chosen (the important part)

`ua_mode = {active, request, magic}` at c01a8000. `request` is set by the start-up button or the menu;
`active` is copied from it at each USB open (`ua_usbmidi_open`, hook c0145158), before the device
connects. While `active` is 0, every patch runs stock code: the descriptor veneer goes to the stock
builder for every type, IF2/IF3 are not registered, and the map thunk jumps back into the stock routine.
So with USB mode off this build should behave exactly like the menu candidate.

## How to turn it on

- **Start-up:** hold the **slot 1 button** ("B4" on the MIDI screen; switch bit 3, GPIO 27, events
  11/12) while powering on. A single slot button has no stock start-up meaning (stock combos checked:
  c0140c8c, table c0180570). **Never hold EDIT alone** (stock ALL INITIALIZE prompt, c0140a30) or
  SETTINGS alone (pedal calibration) at power-up.
- **Menu (experimental):** SETTING, turn a knob right, slot 1 (COMET FLOWER), knob 2 **USB: OFF/AUDIO**.
  The item appears only in this build. Changing it while USB is connected does a software replug
  (stock close c016ab58, 500 ms, stock open c016ab8c; the same pair the cable handler uses), with the
  switch task (which runs the cable handler and scans the buttons) parked at priority -1 for that window
  so a cable event cannot interleave (review R3). If USB is not connected it only stores the choice.

## Pedal / PC checklist

1. Normal power-on: everything as in the menu candidate; Windows sees only "Comet Flower ZG1X4 MIDI".
   MIDI works (VPB).
2. Power on holding slot 1: Windows should add an audio input device. In Sound settings > Recording, it
   should show; recording from it gives silence. MIDI still works.
3. Menu switch: with USB connected, set USB to AUDIO: the pedal should drop off and come back within a
   second or two with the audio device; set OFF: back to MIDI only. Note any freeze, error sound loop, or
   MIDI that stops working.
4. If anything misbehaves: power off and on normally (USB mode is never remembered).

## Known gaps

- PIO isochronous EP1 register use, the EP0 ACK convention for IF3, and host class binding are
  hardware-only unknowns (silence candidate doc, "Hardware-only unknowns").
- Live replug: recovery of in-flight USB transfers on a close while the host is connected is not
  proved offline (docs/helpers/USB_MODE_ASTRA_2026-10-16.md finding 6). The cable handler's extra steps
  (power/UI bookkeeping, event 43) are skipped on purpose; review in USB_MODE_REVIEW_ASTRA_2026-10-16.md.

## Review (Claude Sonnet, Codex capped): docs/helpers/USB_MODE_REVIEW_ASTRA_2026-10-16.md

- R1 off == stock: ok. R2 latch/registration consistency: ok (one residual: c016ab70 may connect
  without the open when a stock Hwi flag says so; not believed to break the invariant).
- R3 replug race with the cable handler: **fixed** (switch task parked during the replug).
- R4 the packager checks the layer's structure, not its code contents: by design (same as the
  controller payload; the payload is our own build, pinned by the tests and this doc's hashes).

## Owner's button map (2026-10-16, from the MIDI screen)

B1 SETTINGS, B2 EDIT, B4..B8 slot buttons 1..5, B10 Rhythm, FS1/FS2 footswitches, K1..K4 knobs, EXP.
Switch bits 2 and 8 (B3, B9) have no physical button; the pedal has no arrow buttons, so chooser
pages flip with the knobs only.

## First hardware run (2026-10-16, build 82737f77)

Owner: booted holding slot 1 into effects mode; COMET FLOWER page showed USB = AUDIO (the request was
read), but Windows showed nothing new. The page only showed the request, so the build was rebuilt
(`8088d23d`) with read-only status columns:

| Column | Shows |
|---|---|
| STAT (K3) | OFF; WAIT = requested, not latched by a USB open yet; ON = latched and IF2 + IF3 registered; ERR = latched, a registration failed |
| HOST (K4) | how many device/configuration descriptors the host fetched through our builder while active |

Reading them: WAIT -> the open hook never ran with the request (latch path); ERR -> registration
refused (c015afa0); ON with HOST 0 -> the host never asked our builder (another descriptor path, or
Windows reused cached data); ON with HOST > 0 but no device -> Windows rejected the configuration
(check Device Manager for a device with a warning sign, and Windows' USB event log).

## Second run (build 8088d23d): STAT ERR, HOST 14

The host fetched our descriptors (14 builds) but the second audio registration was refused: stock
c015c6b4 searches only registry slots 0..1 (`c015c718 MVK 2,A3`, reject ffff8a5c at c015c744), so with
MIDI in slot 0 only one more record fits. Fix (build `eff36a4e`): one audio record owns IF2 and IF3
(map thunk: slot 1 -> IF2 and IF3); its SETUP callback picks IF3 by wIndex (SETUP byte 4).

## Next build, prepared (not to flash until the silence build shows STAT ON and a Windows device)

`build/cf_usb_audio_tap_2026-10-16/Comet Flower G1X4 Updater (USB audio tap TEST build).exe` (`c270cb83…`,
firmware `74de4495…`): the same, with the real-audio tap (`docs/USB_AUDIO_TAP_CANDIDATE_2026-10-15.md`)
instead of silence: the pedal's final stereo output streams to the PC. The tap stores audio only while
the host has the stream open (IF3 alt 1, which needs USB mode active and registered); in FX mode its
cost per audio block is one extra branch and one test. The TEST packager now also accepts the tap layer
(its veneer in the dead padding at 11818c88 and the TX-pack call 11818c64, each checked).

## Third run (build eff36a4e): STAT ON, HOST 12, Windows hid the input

Registration now works. Windows (read on the owner's PC with `Get-PnpDevice`) bound the audio function:
`USB\VID_1686&PID_04A1&MI_02` "Comet Flower ZG1X4 MIDI", service `usbaudio`, no problem code. It also
created a capture endpoint, "Analog Connector (Comet Flower ZG1X4 MIDI)", but with DeviceState
`0x10000001` (active plus the hidden bit, the same bit MIDI devices' dummy "Internal AUX Jack"
endpoints carry), so Sound settings did not list it. The cause is the input terminal type 0x0601
("Analog connector"), which Windows does not show. Fix (build `6d8c936a`): terminal type 0x0603
("Line connector"), the type ordinary USB line inputs use; expected name "Line (Comet Flower ZG1X4 MIDI)".
One byte in the firmware; the rebuilt updater differs from `eff36a4e` in 2 bytes (that byte and a checksum).
The tap build was rebuilt the same way.

Owner notes from run 3: VPB still sees the MIDI port; MIDI input from the pedal did not work as
expected in this mode (details pending). Owner suggestion for later: disable MIDI while in audio mode
or effects mode.
