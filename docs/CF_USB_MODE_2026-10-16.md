# USB-audio mode: TEST build (2026-10-16)

Folder: `build/cf_usb_mode_2026-10-16/` (owner use only: it contains Zoom's firmware code).

| File | SHA-256 (start) | Contents |
|---|---|---|
| `Comet Flower G1X4 Updater (USB mode TEST build).exe` | `54e157b264584eee` | Menu candidate + USB-audio silence layer |
| `res1_cf_usb_mode.bin` | `a79a305ced6c1cac` | `make_controller_fw.py --ui --usb-product …` then `make_usb_audio_fw.py` |

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

Owner notes from run 3: VPB still sees the MIDI port, but Learn detects nothing outside MIDI mode. That is
intended: the pedal sends controller MIDI only in MIDI mode. Owner wish for later: the MIDI port should not
be visible to the host at all until the pedal is set to MIDI mode.

## Fourth run (build 6d8c936a): the input shows and records

Owner: "Line (Comet Flower ZG1X4 MIDI)" appears in Windows and in the app. Claude recorded 3 s from it on
the owner's PC (`ffmpeg -f dshow`): it opened without error, 44.1 kHz stereo 16-bit, ran in real time.
Samples: 0 or ±1, spread evenly over both channels (77 % zero). That is dither from the Windows audio
engine on a zero signal, so the stream reads as silence, as designed. The pedal side does not show whether
the SOF packets were sent (the `set_alts` counter is not on the page), so "silence from our packets" and
"Windows fills a stream that gets no packets" cannot be told apart here. Next: the tap build, where real
audio settles it.

## Fifth run (tap build c270cb83): real audio arrives, "static or garbled"

Owner: the pedal's sound comes through, static or garbled. Two takes on the owner's PC:
- ffmpeg/dshow (shared mode), 6 s: 60 Hz hum, about -55 dBFS, steady (probably not playing).
- `tools/ua_capture.py` (WASAPI exclusive, no Windows processing), 10 s, `build/ua_takes/take_20261016_140553.wav`:
  rms -54 dBFS, peak 263 of 32767, L == R, 120 Hz strongest, smooth waveform; 252 clicks (2nd-difference
  outliers), spacing 44..18567 frames. Whether the owner was playing is not confirmed.

If that take had playing in it, the level is about 2^8 too low, i.e. the planar words at 11f038b0/f0 are not
full-scale int32 as assumed, and the 16-bit high half keeps only ~9 bits (heavy quantisation would sound
"garbled"). To be confirmed with a take recorded while playing.

## Diagnostic pattern build (owner request: exact breakup analysis)

`build/cf_usb_audio_pattern_2026-10-16/Comet Flower G1X4 Updater (USB audio pattern TEST build).exe`
(`0581631d…`, firmware `526a3a0b…`): `make_usb_audio_fw.py --tap-pattern`. Same patches as the tap build; the
Swi stores a known signal instead of the audio: left = frame counter, right = 1002 Hz sine indexed by the counter
(never 0, so all-zero frames are padding). A block dropped on overrun still advances the counter. PC side:
`tools/ua_capture.py` records in WASAPI exclusive mode and lists every gap (frames lost), repeat, inserted padding
and corrupt frame with spacing, and the effective rate. The normal tap build is unchanged (`74de4495…`).
Tests: `tests/test_usb_audio_pattern.py` (analyser on synthetic faults; the pattern C on the host, steady stream clean,
overrun = 16-frame gaps; same patch sites as the tap).

## Sixth run (pattern build 0581631d), take `build/ua_takes/take_20261016_142020.wav`

20 s, WASAPI exclusive. No corrupt frames, no 16-frame (overrun) gaps, one start-up padding run. **8.4 % of frames
lost as whole USB packets**: 1679 gaps, mostly 44 (x1349) or 45 frames, also 88/132/176 (2-4 packets in a row);
most common rhythm "3 packets received, 1 lost"; bursty over time (14..214 losses per second). Also 86 single-frame
repeat + gap pairs (one frame replaced by its predecessor). The pedal produces 44.1 kHz (counter advance =
received + lost); the loss is between the pedal's FIFO load and Windows. Earlier "48 kHz" reading in chat was a
mistake (frames sent over frames received, not over time).

Why a loaded packet disappears is not visible from the PC side, so the pattern build now carries pedal-side
counters in-band (first frame of each packet, right channel, `(tag << 13) | value`): packets loaded, SOFs skipped
with TxPktRdy set, TXCSR UnderRun seen, USB frames with no tick (FRAME register), ring fill, overruns, underruns,
raw TXCSR. `ua_capture.py` decodes them ("pedal diag" lines) and compares packets loaded vs received.
Analyser fixes in this pass: the sine phase follows the full frame count (65536 % 44 = 20), so the analyser
unwraps the counter and searches the 11 possible starting wrap offsets.

## Seventh run (pattern diag build e3cdc633), take `build/ua_takes/take_20261016_145225.wav`

Owner: tone comes "in and out". 882,000 frames took ~58 s of wall time. Pedal-side counters (in-band):
**57,848 packets loaded, 21,398 received: 63 % lost after loading.** During the take: 0 SOFs skipped, 0 TXCSR
UnderRun, 0 USB frames without a tick, 0 overruns, 0 underruns; ring fill 68..84; TXCSR = 0x0002 at every SOF
(FIFONotEmpty, TxPktRdy clear: one bank queued, one free). The pedal side is clean; the loss is on the bus or host.
Received packets come in a 4 ms rhythm (here mostly 1 of 4; run 6 mostly 3 of 4).

**Host path:** the pedal is behind a Genesys GL850G hub (`USB\VID_05E3&PID_0608`, single TT) on the USB 3.0 root,
sharing it with a TP-Link Wi-Fi adapter, a Bluetooth adapter and a Logitech receiver. Full-speed isochronous through
a busy single-TT hub is the prime suspect. Next: pedal directly on a PC port, same build, same capture.

## Eighth run (diag build e3cdc633, pedal on a motherboard USB 3.0 root port), take `take_20261016_145840.wav`

Direct on `USB Root Hub (USB 3.0)`: still **44 % lost** (40,304 loaded, 22,438 received), no rhythm. Pedal counters
clean again (0 skips, 0 UnderRun, 0 frame skips, TXCSR 0x0002 every SOF). Raw frames show packets that arrive
**truncated to their first 1-2 frames** (4-8 bytes), e.g. a diag frame alone and then the next packet 45 counts
later. Noise destroys whole packets; a clean short packet means the controller sent a bank that was still being
loaded. Loss also grew from 8 % (tap build) to 44-63 % when the diag build added a little work per tick. Working
hypothesis: a race between the SOF-tick FIFO load and the host's IN token in this FIFO set-up (double-buffered,
ISOUpdate on). The hub likely adds to it but is not the cause.

## Variants build (one capture compares FIFO set-ups)

`build/cf_usb_audio_variants_2026-10-16/Comet Flower G1X4 Updater (USB audio variants TEST build).exe`
(`74f779cb…`, firmware `87cef306…`): the pattern diag build, but the endpoint-1 set-up cycles every 4 s
through 0 double+ISOUpdate (as now), 1 single+ISOUpdate, 2 double without ISOUpdate, 3 single without, reconfigured
inside the USB interrupt (INDEX saved/restored, FIFO flushed twice). Diag tags changed: 3 = variant << 11 | frame
skips, 5 = ticks in an unchanged frame, 6 = overruns << 7 | underruns (older takes decode wrongly with the new
analyser on those tags). `ua_capture.py` prints loaded / received / lost per variant. Record >= 32 s.

## Ninth run (variants build 74f779cb, through the hub), take `take_20261016_163531.wav`

(First try on motherboard root port 13: Windows Code 10, 0xC0000001, HOST 34, after two power cycles. Back on the
hub it enumerated (HOST 22). Port 13 left as an open puzzle.) 40 s, delivered audio per FIFO set-up:

| Variant (as numbered in 74f779cb) | Delivered | Lost |
|---|---|---|
| 0 double buffer, ISOUpdate on (all builds so far) | 81.1 % | 18.8 % as USB packets |
| 1 single buffer, ISOUpdate on | 50.5 % | 49.5 % pedal overrun (TxPktRdy busy at SOF) |
| **2 double buffer, ISOUpdate off** | **99.9 %** | 0.1 % (the set-up switches) |
| 3 single buffer, ISOUpdate off | 50.5 % | 49.5 % pedal overrun |

**Fix:** `usb_audio_set_alt(1)` now clears POWER.ISOUpdate (was: set). All three TEST builds rebuilt:

| Updater | SHA-256 (start) | Firmware |
|---|---|---|
| USB mode (silence) `build/cf_usb_mode_2026-10-16/` | `54e157b2` | `a79a305c` |
| **USB audio tap (guitar)** `build/cf_usb_audio_tap_2026-10-16/` | `de0925d4` | `32afe08d` |
| Variants diag `build/cf_usb_audio_variants_2026-10-16/` | `7e2a9961` | `3294331f` |

The variants build now numbers 0 = double + ISOUpdate off (the new default), bit 1 = ISOUpdate on. Next: tap build
with guitar, `ua_capture.py` audio take (expect no clicks), then a pattern check on the hub and a direct port.
