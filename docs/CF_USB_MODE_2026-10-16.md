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

## Long run (tap build de0925d4, hub), take `build/ua_takes/longrun_20261016_hum.wav` (2026-10-16 evening)

5 min, WASAPI exclusive, nothing played (input = 60/180 Hz mains hum at -34 dBFS rms, L == R).
13,230,000 frames in 300.1 s wall time (full rate; the 0.1 s is stream start). One zero run: the 89-frame
priming at the start, none after. The old click count (668) is the hum's own waveform, not defects. A
linear-prediction residual scan (order 24, 8192-frame blocks, > 12 x MAD) finds 3 outliers at 4,786,658 and
5,140,620: smooth ~4 kHz bursts over ~12 samples (input pops), not steps. **0 dropouts in 5 min.**

Static CPU estimate for the tap (from `build/usb_audio_tap/usb_audio.dis`): Swi copy SPLOOP ii 14 x 16 frames
~250 cycles/block; SOF Hwi ring loop ii 6 x 45 frames ~300 cycles/ms ~110/block plus entry. About 0.4 % of the
132,354-cycle block; ClkT confirmation still open.

## Port 13 Code 10: what is ruled out (evening)

- **Not a missing ZLP:** the configuration descriptor is 192 B = 3 x 64, but Zoom's EP0 path queues an explicit
  zero-length 4th packet when the reply is shorter than wLength (Astra, `docs/helpers/USB_OPT_ASTRA_2026-10-16.md` A1:
  c015b330..b342 keeps the transfer pending, c0121142..114a writes TXPKTRDY|DATAEND for the 0-byte packet).
  Unknown descriptor types (BOS etc.) STALL, which is legal.
- **Not a dead first request:** Windows' device list has `USB\VID_1686&PID_04A1\5&DC4A972&0&13` (the composite
  device on port 13) first installed 14:57:38 today (run 8, streamed) and present again 15:55-16:33 (the Code 10
  attempt). The port-13 "Device Descriptor Request Failed" entry dates from 2026-10-10. So the Code 10 hit the
  composite device after its descriptors were read: start-up (SET_CONFIGURATION / usbccgp), not the first fetch.
- Still open: reproduce with the tap build on port 13; if it repeats, compare SET_CONFIGURATION handling and xHCI
  bandwidth (the hub path goes through a TT, the root port does not).

Level chain (Astra A2): the tap follows the digital master volume (`MVOL`, float 11f03e34 applied at 11818d60)
and the patch level (c011acd4 at 11817bd4). USB level therefore follows the pedal's volume setting; the -27 dBFS
guitar peak is most likely a low master volume, not the tap's scaling.

## Stream-start splice and the tap2 build (evening)

Argon's linear-prediction detector (`ua_capture.py`, `docs/helpers/USB_OPT_ARGON_2026-10-16.md`; verified: 0 false
events on the 10 s takes) found **one splice in the 5-min take at frame 217** (signal steps 471 -> 18). 217 = 89
priming frames + 128 = `UA_TAP_PRIME`. Cause (tap code, reproduced on the host): when the host polls late after
alt 1, every SOF finds TxPktRdy set and returned before the priming logic; the Swi filled the ring, overran
(dropping the *newest* blocks), and priming on the newest stored 128 frames joined them to frames stored after
the overrun. Seen in 1 of 3 takes; once per stream open, ~3 ms in.

Fix (`usb_audio_tap.c`, busy-SOF path, consumer side so `ring_rd` keeps one writer): while not primed, or when a
stall has filled the ring to within 2 blocks, trim to the newest `UA_TAP_PRIME` frames and un-prime. A single busy
SOF while primed changes nothing. New host tests: late host at start, 20 ms stall mid-stream (re-primes, each
stretch contiguous), single busy SOF (stays primed); the first two failed before the fix. 369 tests pass
(`tests/`, `tools/test_usb_audio_proto.py`, `tools/test_ua_capture_glitch.py`).

| Updater | SHA-256 (start) | Firmware |
|---|---|---|
| **USB audio tap2** `build/cf_usb_audio_tap2_2026-10-16/` (desktop: `GUITAR AUDIO 2 - Comet Flower USB tap2 TEST.exe`) | `d6e62256` | `72e97df5` |

Same pipeline as tap (`make_controller_fw.py --base build/fw/res1_cf_usbname.bin --ui --usb-product "Comet Flower
ZG1X4 MIDI"`, `make_usb_audio_fw.py --tap`, `make_fs_restore_updater.py --test-controller-fw … --presets
build/fw/cfupd_res85.bin --image build/cf_release_2026-10-16/fs_cf.bin`); rebuilding the old source with it gives
`32afe08d` / `de0925d4` exactly, so tap2 differs only by the fix. **Not flashed yet.** Check after flashing:
open the stream ~20 times (`ua_capture.py --seconds 3` in a loop) and look for a lost-frame event near frame 217.

Baseline on the old tap build (de0925d4), 15 stream opens x 3 s (`build/ua_takes/starts_tap1/`): **splice at
frame 217 in 1 of 15** (s9), as predicted. s1 instead shows frames 935..1798 = an exact copy of 71..934
(priming zeros included): the capture side delivered its first 864-frame buffer twice. The pedal cannot do that
(256-frame ring, priming is never re-sent), so it is a PortAudio/WASAPI start artifact, not a stream defect.
Repeat the same 15 opens on tap2 to confirm the fix.

## Port 13 Code 10 pinned: the pedal STALLs SET_CONFIGURATION (USB trace, 19:12)

`tools/usb_etw_trace.ps1` (elevated; usbhub3 + UCX + xHCI ETW, restarts the device) on tap2, port 13
(`PCIROOT(0)#PCI(1400)#USBROOT(0)#USB(13)`, ACPI HS13, a motherboard root port; the hub sits on root port 2).
Trace `build/usb_etw/usb_20261016_191227.etl`. Per attempt, 3 attempts then Code 10 (0xC0000001):
GET_DESCRIPTOR(device, 64) ok -> reset -> GET_DESCRIPTOR(device, 18) ok -> **SET_CONFIGURATION(1): USBD
0xC0000004 (STALL PID)** 4 ms later -> "Device Control Transfer Error" -> re-enumerate. Windows used its cached
configuration descriptor (3 "Descriptor Validation Warning"s, status 0x50) and did not re-fetch it.

Stock SET_CONFIGURATION c0135660: builder (our veneer, A4 = 2, always returns 0) -> find bConfigurationValue ->
c01357c8 per interface (return ignored) -> **c015af48(128, ...) status ACK, which posts to the USB task queue
c01387f0 (A4 = 4) and returns its result**; c0135744..c013575a: any result other than 0 / 0xffff8a63 is returned
-> STALL. c015c804 always returns 0. So the STALL is a failed post of the status stage, not a descriptor check.
Next: power on WITHOUT slot 1 (USB-audio off, all stock paths) on port 13: if that also fails, it is stock Zoom
behaviour on this port; if it works, our layer makes the queue busy. Then RE c01387f0's error returns.

## Port 13: normal mode works; fix candidate tap3 (2026-10-17, past midnight)

Replug trace on port 13 without slot 1 (`build/usb_etw/usb_20261016_200752.etl`): 101-byte stock configuration,
SET_CONFIGURATION accepted, MIDI up. So only USB-audio mode fails there. Windows reads the configuration with
**wLength 255**; our 192 = 3 x 64 reply is the only one that ends through Zoom's zero-length-packet path
(stock 101 bytes ends with a short packet), and the next SET_CONFIGURATION is the request that STALLs. Working
hypothesis: after that path EP0 stays busy (c01387f0: EP0 record word 1 set -> post fails -> STALL), and on a
root port the next request comes too soon (13 ms in the normal-mode trace); the hub is slower. Not proved
statically; the hardware test decides.

Fix candidate: the Type I format descriptor lists 44.1 kHz as a continuous range 44100..44100 (bSamFreqType 0,
14 bytes), so wTotalLength = 195, not a multiple of 64. Tests pin `wTotalLength % 64 != 0` and the new format;
validator offsets shifted by 3. 370 tests pass.

| Updater | SHA-256 (start) | Firmware |
|---|---|---|
| **USB audio tap3** `build/cf_usb_audio_tap3_2026-10-17/` (desktop: `GUITAR AUDIO 3 - Comet Flower USB tap3 TEST.exe`) | `393d1112` | `dcf7cb50` |

tap3 = tap2 (start-splice fix) + the 195-byte descriptor; 19 bytes differ from tap2. Test: flash, power on holding
slot 1 **directly on port 13**; expect "Line (Comet Flower ZG1X4 MIDI)" and no Code 10. If Windows still shows
Code 10, run `tools/usb_etw_trace.ps1 -WaitSeconds 120` across a replug.

## tap3 on hardware (2026-10-17): port 13 Code 10 fixed

Owner flashed tap3 (`393d1112`). On the hub (10:05) it enumerated and streamed. **Directly on motherboard root
port 13 (`Port_#0013.Hub_#0003`, USB Root Hub (USB 3.0)) at 10:48:50 in USB-audio mode: composite device OK,
MI_00 MIDI and MI_02 audio OK, no Code 10** (tap2 failed there every time). 10 s take `build/ua_takes/tap3_port13.wav`:
full rate (441,000 frames in 10.1 s). So the 192-byte (3 x 64) configuration descriptor was the cause, as
hypothesised: keep wTotalLength % 64 != 0 (pinned by a test). Windows also accepted the continuous-range format.
Splice check (15 opens) still needs a take with signal (guitar plugged in): quiet takes are skipped.

Host side (owner's VPB app, its `startup_audio_log.txt`): dropout prompts came from the app, not the stream:
device xruns at 48 kHz / 480 samples (pedal input 44.1 kHz on its own clock, speakers 48 kHz on another, Windows
shared mode bridges them), and DSP xruns after the buffer was lowered to 132 samples with a 9-effect chain.
Advice: buffer >= 256-480, speakers at 44.1 kHz. Real fix later: a USB playback endpoint so in/out share the pedal clock.

Splice check on tap3, port 13, owner strumming (Bm-G-F#-Em loop), 15 opens x 3 s (`build/ua_takes/starts_tap3/`):
levels -22..-28 dBFS rms, peaks to -3.5 dBFS, no clipping; priming 89 frames each; **no event near frame 217 in
any open** (tap1: 1 in 15). The LP detector flagged 14-89 "lost frames" per take in clusters at strum attacks;
inspected spots are smooth (no steps): false positives on real playing. Retune: docs/helpers/GLITCH_TUNE_BRIEF_2026-10-17.md.

## tap4: USB left = wet, right = dry input (2026-10-17)

Owner: use the two channels separately: one for the processed sound, the other for the input. tap4 sends
**left = processed output** (TX left 11f038b0, stock pack math, as before) and **right = dry guitar input**: RX
unpack 11818b20 (called at 11818bb0 in the same Swi, before the tap) stores SMPY32(codec word, 0x80000000), the
negated full-scale int32 sample, for the left ADC (MIC3L, guitar jack) at 11f03730 and the right ADC at
11f03770; the tap sends the high half of 11f03730 (same polarity as the wet path, which processes that value).
Compiled check: ua_tx_pack_tap loads A4 = 11f038b0, B4 = 11f03730. Host tests: right = dry, TX right ignored.
370 tests pass.

| Updater | SHA-256 (start) | Firmware |
|---|---|---|
| **USB audio tap4 (wet L / dry R)** `build/cf_usb_audio_tap4_2026-10-17/` (desktop: `GUITAR AUDIO 4 - Comet Flower USB tap4 wet-dry TEST.exe`) | `e85eb5b4` | `7f39b55a` |

Unproved on hardware: that 11f03730 still holds this block's input at TX time (nothing found rewriting it),
that the guitar is on the left ADC, and the DI level (ADC PGA 0 dB). Check: a take with a patch whose sound
clearly differs from the DI (e.g. heavy drive) and confirm R is the clean guitar, in time with L.
`ua_capture.py` still analyses L == R takes as one signal; per-channel analysis for wet/dry takes is next.

## 8-channel tap build (2026-10-17): find out what the internal buses carry

Owner kept stereo (tap4 wet/dry superseded, never flashed) and wants the drum machine and looper as their own
channels. The audio Swi never renders rhythm or looper itself; the patch-level stage 11817a90 adds two internal
mix buses to the chain output: 11f03830/11f03870 (stereo, added directly) and 11f03930 (mono, x gain c011acd0);
11f03970 is a third published bus with no consumer found (docs/helpers/RHYTHM_LOOPER_TAP_2026-10-17.md). Their
producer is unknown, so the 8-channel build sends them and a take tells what they carry.

`make_usb_audio_fw.py --tap8` (`UA_NCH=8`): 1-2 pedal output L/R (stock pack math, as tap3), 3 left ADC (DI,
11f03730 high half), 4 right ADC (11f03770), 5-6 bus 11f03830/70, 7 bus 11f03930, 8 bus 11f03970 (float,
1.0 = full scale, SPINT x 2^31 high half). Descriptor: 8 channels, wMaxPacketSize 720, wTotalLength 195
(% 64 != 0); EP1 TXMAXP 720, FIFO 2 x 1024 B at 0x140 (TXFIFOSZ 0x17; stock uses 0x000..0x13f). Ring 256 frames
x 4 words. All sources read-only, after the stock code finished them this block. The 2-channel build is
unchanged: rebuilt from this source it is byte-identical to tap3 (`dcf7cb50`). Host tests
`tests/test_usb_audio_tap8.py` (descriptor, FIFO, packet order of all 8, float scaling, priming silence width,
drift -1000/+10000 ppm continuity). Static cost: the 8-channel copy loop is not software-pipelined (volatile
reads), estimate < 1 % of a block with the SOF writes; ClkT measurement still owed.

| Updater | SHA-256 (start) | Firmware |
|---|---|---|
| **USB audio 8ch** `build/cf_usb_audio_8ch_2026-10-17/` (desktop: `GUITAR AUDIO 5 - Comet Flower USB 8ch TEST.exe`) | `e9b56839` | `7a4cef2a` |

Test: flash, power on holding slot 1 (hub and port 13), Windows should list an 8-channel "Line (Comet Flower ZG1X4
MIDI)". Record with `tools/ua_capture8.py --seconds 30` while (a) playing, (b) running the drum machine, (c)
recording and playing a loop. The report prints per-channel level and which channels resemble each other.

### 8ch on hardware (13:29, port 13): no go in Reaper and the owner's modeler

Enumerates fine (composite, MI_00, MI_02 OK). The pedal's capture endpoint `{c0c8d579…}` kept a stored format of
**2 ch**, 44.1 kHz, 16 bit, mask 0x3; PortAudio lists 8 inputs for MME / DirectSound / WDM-KS but 2 for WASAPI;
8-channel opens fail in WASAPI exclusive ("Invalid number of channels"), MME ("invalid parameter", error 11) and
WDM-KS. Cause (likely): wChannelConfig named only L|R for 8 channels, so Windows built a 2-channel format.
Fix **8ch-b**: wChannelConfig 0x00ff (eight positions, 7.1 layout) for 8 channels, 0x0003 kept for 2 (the
2-channel build is still byte-identical to tap3). Test pins popcount(wChannelConfig) == bNrChannels.

| Updater | SHA-256 (start) | Firmware |
|---|---|---|
| **USB audio 8ch-b** (desktop: `GUITAR AUDIO 6 - Comet Flower USB 8ch-b TEST.exe`) | `3f290e3e` | `18840d2a` |

After flashing, Windows may keep the stale 2-channel endpoint format: remove the MI_02 device node
(elevated `pnputil /remove-device`) and rescan so the endpoint is rebuilt.

### 8ch-b on hardware (14:12 flash, port 13): works after Windows forgets the old endpoint

Windows kept the endpoint's stored 2-channel format after the descriptor changed. Elevated `pnputil
/remove-device` on the composite, MI_00 and MI_02 nodes plus `/scan-devices` rebuilt it: new capture endpoint
`{b9554f77…}`, format 8 ch, 44.1 kHz, 16 bit, mask 0x063f. MME, DirectSound, WASAPI and WDM-KS list 8 inputs.
`ua_capture8.py` 10 s idle take `build/ua_takes/take8_20261017_142434.wav`: 441,000 frames in 10.1 s on all 8.
Idle levels: ch1-2 -83 dBFS, ch3 = ch4 -88.7 dBFS (right ADC looks like the same jack), **ch5-6 exactly zero**,
ch7-8 -88.9 dBFS input-like noise. Lesson: **after any descriptor change, remove the device nodes so Windows
rebuilds the endpoint**; apps (Reaper, VPB) must reopen the device.

### First 8-channel identifying take (`build/ua_takes/take8_identify.wav`, 30 s, owner playing)
- ch1 = ch2 (out), -16 dBFS rms, **peak 0 dBFS, 1374 clipped samples**: output level too hot for USB.
  Out correlates 0.999 with the DI: this patch is nearly clean.
- **ch3 == ch4 sample for sample**: the right ADC carries the same guitar jack (both pins wired together, or
  the codec duplicates it). Channel 4 is free for another use.
- **ch5-6 (bus 11f03830/70): exactly zero for all 30 s.**
- **ch7 == ch8** (buses 11f03930 and 11f03970 identical): -36 dBFS, only 0.19 correlated with the DI, band-pass
  shape relative to the DI (-28 dB at 100 Hz, -9 dB at 1 kHz, -37 dB at 12 kHz), dips every ~10 s, weak
  0.75 s envelope period. Not a copy of the input. Identity open: exported `build/ua_takes/listen_bus3930.wav`
  (normalised) for the owner to listen. What the owner ran during the take (drums, looper) to be confirmed.

## Device-name label from firmware: 8ch "named" build (2026-10-17)

Windows has no field for per-channel names in WASAPI/MME (UAC1 iChannelNames applies only to channels without a
spatial position, and Windows needed all eight positions, mask 0x00ff), so the label goes in the device name.
Zoom's string builder c0161008 hands out records for strings 0-4; 3 and 4 both point at c017f41c, a stock empty
string (0x302) referenced only by c0161020 and never requested by Windows. `make_controller_fw.py
--usb-audio-name` repoints that record at our text (same checks as --usb-product; 1..62 ASCII, never 31, so the
reply is never a multiple of 64), and the 8-channel descriptor sets IF2 iInterface = 3 (`UA_AUDIO_STRING`).
`make_usb_audio_fw.py --tap8` refuses a base without the string. Name: `CF8 Out1-2 DI3-4 BusA5-6 BusB7-8`;
expected endpoint "Line (CF8 Out1-2 DI3-4 BusA5-6 BusB7-8)". Tests: tests/test_usb_string3.py. Base without the
option unchanged (168d8790).

| Updater | SHA-256 (start) | Firmware |
|---|---|---|
| **USB audio 8ch named** (desktop: `GUITAR AUDIO 7 - Comet Flower USB 8ch named TEST.exe`) | `504707d6` | `e329eed8` |

After flashing: remove the device nodes again so Windows re-reads the names.

### 8ch named build on hardware: owner listening test (2026-10-17)
After the replug Windows shows `CF8 Out1-2 DI3-4 BusA5-6 BusB7-8` and `Line (CF8 Out1-2 DI3-4 BusA5-6 BusB7-8)`
(both OK): the firmware device-name label works.
Owner, by ear, with effects, drums and looper all running (corrected in a second report the same day):
- **ch1-2: full pedal mix (effects + looper + drums)**, hottest. The TX tap already carries the full output, so
  the "move the tap to the packed TX buffer" item is not needed.
- **ch3-4 (11f03730/70): the same full mix, quieter than 1-2.** So these are *not* the ADC/dry input: most likely
  the mix before the master level stage. Consistent with the first take (ch1 vs ch3 corr 0.999).
- ch5-6: silent.
- **ch7-8 (11f03930/70): clean DI**, no effects, drums or looper even with all of them on. This is the dry input
  for re-amping. (Measured earlier as band-passed vs ch3; with ch3 now known to be the mix, that comparison was
  mix-vs-DI, not DI-vs-DI.)
Consequence: the device-name label `CF8 Out1-2 DI3-4 BusA5-6 BusB7-8` is wrong for 3-4 and 7-8; a renamed build
needs a new updater and flash. ua_channels.json and the REAPER template are updated.

## Renamed: "Comet Flower Audio Bridge" (2026-10-17)

Owner asked for a plain device name; the channel layout lives in `tools/ua_channels.json` and the REAPER template.
Same 8-channel tap as the named build, only string 3 changed. Recipe (reproduces `e329eed8`/`504707d6` byte for
byte with the old name; use `.venv/Scripts/python.exe`, the system Python lacks pefile):
`make_controller_fw.py --base build/fw/res1_cf_usbname.bin --ui --usb-product "Comet Flower ZG1X4 MIDI"
--usb-audio-name "Comet Flower Audio Bridge"` -> `make_usb_audio_fw.py --tap8` -> `make_fs_restore_updater.py
<v2.00 updater> "<name> TEST.exe" --test-controller-fw <fw> --presets build/fw/cfupd_res85.bin
--image build/cf_release_2026-10-16/fs_cf.bin`. 299 tests pass.

| Updater | SHA-256 (start) | Firmware |
|---|---|---|
| **USB Audio Bridge** `build/cf_usb_audio_bridge_2026-10-17/` (desktop: `GUITAR AUDIO 8 - Comet Flower USB Audio Bridge TEST.exe`) | `d76d634b` | `46eddead` |

Expected endpoint: `Line (Comet Flower Audio Bridge)`. After flashing, remove the MI_00/MI_02 device nodes and
rescan (or replug) so Windows re-reads the name.

## Stems build: drums alone on 5-6, looper alone on 8 (2026-10-17)

Source of the addresses: Argon's static pass `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md` (brief
`DRUMS_LOOPER_BRIEF_2026-10-17.md`), checked by Claude against main.dis. **Correction to Argon:** the drum
mixer's gain cell is **11f03d1c** (A18 = 11f03d54 - 0x48 + 0x38 - 0x24 - 4, 118176ec/11817718/11817720/11817740),
not 11f03d08.
- Drums: 11817640 (called at 11818d64 inside 11818d60, Swi step 15). Rhythm flag 11f03d54 set: bus 11f037b0/f0
  = (bus + drum) x m (11817878/11817898 add, 118178b0/118178d0 x *11f03d1c). Flag clear: bus untouched.
- Looper: 118164c0 via dispatcher 11818e60 at 11818bc0 (A4 = 0, Pre) and 11818c50 (A4 = 1, Post); adds its mono
  playback to both channels with a level/fade factor (11816db8.., MPYSP after the add).
- Also explains the listening test: 11f03730/70 are rewritten from the bus by 11818428 (step 16) before
  the output stage 118186e0 makes 11f038b0/f0 (x4 shift at 11818790), so 3-4 = the mix before that stage;
  11f03930 is a copy of the conditioned input made at step 7 (118183d0), so 7-8 = clean DI.

Taps (`make_usb_audio_fw.py --stems`, `UA_STEMS` in usb_audio_tap.c):
- `ua_drums_tap` (veneer 11818d4c..d58, dead padding after the BNOP at 11818d48; CALLP 11818d64 retargeted):
  rhythm on -> save bus, zero it, run the stock mixer, keep bus as the stem (drum x m), bus = saved x m + stem
  (= stock (saved + drum) x m; bit-identical for m = 1). Rhythm off -> stock call, stem 0.
- `ua_looper_tap(pos)` (veneer 11818e84..e90 after the BNOP at 11818e80; both dispatcher calls retargeted):
  stem += bus after - bus before (left). Exact while the looper's factor is 1; during a fade the stem carries
  (factor - 1) x bus. Main audio untouched. Cleared after each TX block.
- Layout: 1-2 out, 3-4 mix (quieter), **5-6 drums L/R**, 7 DI, **8 looper** (float, 1.0 = full scale, pre master).
  Map `tools/ua_channels_stems.json`; REAPER template `Comet Flower Stems.RPP` (desktop).
- Packager: the TEST path recognises the stems layer by the 11818d64 site; every call must reach its own veneer
  and every veneer must point into the USB section (tests/test_usb_audio_candidate.py). Host tests
  tests/test_usb_audio_stems.py. The 8ch and Audio Bridge builds still reproduce (e329eed8, 46eddead). 306 tests pass.
- Not measured: CPU cost (three 16-sample loops + 32 float copies per block, small) and the drum/looper levels.

| Updater | SHA-256 (start) | Firmware |
|---|---|---|
| **USB Audio Bridge stems** `build/cf_usb_audio_stems_2026-10-17/` (desktop: `GUITAR AUDIO 9 - Comet Flower USB Audio Bridge stems TEST.exe`) | `b9f7f449` | `cd5f3715` |

Test: flash, replug, record with the stems template; drums on 5-6 only, looper on 8 only, guitar absent from both
(except during looper fades), and 1-2 sound exactly as before.

## FX build: no USB clipping on 1-2, guitar FX alone on 3-4 (2026-10-17)

Why 1-2 were hot: take8_identify ch1 / ch3 = x2.16 (+6.7 dB), corr 0.999 = exactly the TX pack's converter
gain SMPY32(x, 0x4534fd79) then SSHL 2 (0.5407 x 4) applied after the output stage 118186e0; 3-4 were read before
it. `--fx` (UA_STEMS + UA_FX):
- **1-2** = the output stage's words 11f038b0/f0, high half, *without* that gain: full mix, 6.7 dB below the old
  1-2, no clipping from the pack. The pedal's analog output is unchanged (the stock pack still runs).
- **3-4 = guitar FX** (stereo): copied inside `ua_looper_tap` on the Post call (11818c50) before the looper runs,
  i.e. after the slot loop, patch level 11817a90 and 11818ea0; before the Post looper, drums and master level.
  A Pre looper plays through the effects, so it is in 3-4 too. No new hook.
- 5-6 drums, 7 DI, 8 looper as in `--stems`. Map `tools/ua_channels_fx.json`, template `Comet Flower FX.RPP`.
- Stems, FX, drums and looper are pre master level; 1-2 are post master.
- Earlier builds still reproduce (e329eed8, 46eddead, cd5f3715). Host tests: the stem tests run again on the FX
  build plus FX layout and Pre/Post cases.

| Updater | SHA-256 (start) | Firmware |
|---|---|---|
| **USB Audio Bridge FX** `build/cf_usb_audio_fx_2026-10-17/` (desktop: `GUITAR AUDIO 10 - Comet Flower USB Audio Bridge FX TEST.exe`) | `9414881f` | `d9eb45e2` |

Supersedes the stems build for flashing (same stems, two pairs improved). Per-slot taps: Argon brief
`docs/helpers/SLOT_TAP_BRIEF_2026-10-17.md` running.

## 10-channel Audio Bridge: every pair usable (2026-10-18)

Owner: on the bench firmware, 7-8 as a stereo pair gave the DI plus a squeal (ch 8 = CPU timing frames). Chosen
layout: **1-2 mix (output words without the x2.16 converter gain), 3-4 guitar FX, 5-6 drums, 7-8 DI (same on both),
9-10 looper (same on both)**; the timing frames stay in the separate 8-channel bench build (`--bench`).
`make_usb_audio_fw.py --tap10` (`UA_NCH=10`, FX layout + stems hooks, no bench): wChannelConfig 0x03ff (10
positions; Windows needs every channel positioned), wMaxPacketSize 900 (<= 1023, one 1024 B FIFO bank), 5 ring
words per frame, the SOF loop sends the 5th word. Descriptor length still 195. All earlier builds reproduce
(e329eed8, 46eddead, cd5f3715, d9eb45e2, 6e20051c). Host tests tests/test_usb_audio_tap10.py. Map
`tools/ua_channels_10.json`, REAPER template `Comet Flower 10ch.RPP` (5 stereo tracks), CF Monitor follows the
pedal's channel count (10 or 8). Device name "Comet Flower Audio Bridge" (confirmed in Windows with updater 17).

| Updater | SHA-256 (start) | Firmware | Effects |
|---|---|---|---|
| **Audio Bridge 10ch** `build/cf_usb10_2026-10-18/` (desktop: `GUITAR AUDIO 18 - Audio Bridge 10ch TEST.exe`) | `6689f536` | `0865f954` | `fs_cfloads.bin` (calibrated loads, as updater 17) |

Windows sees a new channel count: remove the device's MI_00/MI_02 nodes and rescan, or replug, so it rebuilds the
endpoint (as with 2 -> 8). Bench measurements need the bench updater (17).

### 10ch on hardware (2026-10-18): Windows keeps the old 8-channel endpoint format
Updater 18 enumerates: MME, DirectSound and WDM-KS show 10 channels, **WASAPI shows 8** (endpoint
{5ff4606e-...} property {f19f064d-...},0 = WAVEFORMATEXTENSIBLE 8 ch, mask 0x063f; key owned by SYSTEM).
Removing MI_00/MI_02 and even the SWD endpoint node and rescanning (elevated pnputil) did **not** reset it: the
endpoint keeps its GUID and properties. Opening 8 channels then fails ("Invalid device", PaErrorCode -9996).
Fix: Sound settings > Recording > Line (Comet Flower Audio Bridge) > Properties > Advanced > Default Format:
choose the 10 channel entry (the audio service rewrites the property). CF Monitor now detects the mismatch.
**Correction (same day):** not only WASAPI. Every API fails to open the 10-channel stream at any channel count
(MME/DirectSound/WDM-KS "Unanticipated host error", WASAPI "Invalid number of channels"/"Invalid device"); pedal on
xHCI root port 14 (no hub), no system-log errors. Suspect: wChannelConfig 0x03ff (UAC1 L R C LFE Ls Rs Lc Rc **S Sl**,
no Sr). Rebuilt with the symmetric **0x06ff** (0x00ff of the working 8-ch build + Sl Sr). Fallback `--pairs8`: the
proven 8-channel descriptor with 1-2 mix, 3-4 guitar FX, 5-6 drums, 7-8 DI on both (no looper).

| Updater | SHA-256 (start) | Firmware |
|---|---|---|
| `GUITAR AUDIO 19A - 10ch (mask 6ff) TEST.exe` (`build/cf_usb10b_2026-10-18/`) | `f2cabc10` | `14821e92` |
| `GUITAR AUDIO 19B - 8ch pairs (fallback) TEST.exe` | `c7407821` | `cbc28a4a` |
Updater 18 (`6689f536`, mask 0x03ff) withdrawn. Both new ones: calibrated-loads effects. After flashing A, the
endpoint may still carry the stale 8-ch format: CF Monitor falls back to WDM-KS and says so.

### 19A on hardware (2026-10-18, later): 10 channels do not open, 8 is the ceiling
Read back from the hub (IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION, no driver needed): the pedal runs 19A,
config 195 bytes, input terminal wChannelConfig **0x06ff**, 10 ch 16 bit 44.1 kHz, EP 0x81 iso async
wMaxPacketSize 900, bInterval 1, **full speed** (root port 13). Still every API fails to open (MME/DS
"Unanticipated host error", WASAPI "Invalid number of channels"/"Invalid device", WDM-KS "Invalid device" at
10/8/2 channels; nothing else holds the device; no System-log events). So the mask was not the cause. The only
differences from the working 8 ch descriptor are the channel count and the 900 B packet, and the firmware side
(FIFO 0x17 at 0x140) is identical for 8 and 10. Most likely the host refuses that much full-speed iso audio
(usbaudio.sys is commonly quoted at 8 ch x 16 bit at full speed: 768 B/ms). Not proven (needs an elevated ETW
USB trace), but 10 ch at full speed is shelved: **flash 19B** (`c7407821`, proven 8 ch descriptor: 1-2 mix,
3-4 guitar FX, 5-6 drums, 7-8 DI, no timing frames on 7-8). The looper stem would need a pair swapped out.

### Back to 8 channels (2026-10-18, late): channel 8 choices
19B was never flashed (pedal not in update mode); owner rolled back to updater 17 (bench, 8 ch read back from the hub,
stream opens). Ch 8 timing frames spoil 7-8 as a stereo DI, so two non-bench 8 ch builds with the calibrated-loads
effects (`build/cf_loads_2026-10-18/fs_cfloads.bin`):

| Desktop | SHA-256 (start) | Firmware | 7 / 8 |
|---|---|---|---|
| `GUITAR AUDIO 20A - DI on 7 and 8 TEST.exe` (= 19B) | `c7407821` | `cbc28a4a` (`--pairs8`) | DI / DI |
| `GUITAR AUDIO 20B - looper on 8 TEST.exe` (`build/cf_usb_looper8_2026-10-18/`) | `7830391d` | `d9eb45e2` (`--fx`, = updater 10's fw) | DI / looper |

Recipe (reproduces 19B byte for byte): `make_controller_fw.py --base build/fw/res1_cf_usbname.bin --ui --usb-product
"Comet Flower ZG1X4 MIDI" --usb-audio-name "Comet Flower Audio Bridge" --out ctl.bin` -> `make_usb_audio_fw.py
--base ctl.bin --pairs8|--fx` -> `make_fs_restore_updater.py <v2.00 updater> "<name> TEST.exe" --test-controller-fw
<fw> --presets build/fw/cfupd_res85.bin --image build/cf_loads_2026-10-18/fs_cfloads.bin`. Bench = updater 17 only.
**20B flashed (2026-10-18, late):** hub read-back 8 ch / 0x00ff, stream opens (WASAPI 8 ch). Idle take: 1-4 and 7 at
noise floor (<= 7 LSB), 5-6 and 8 at +-1 LSB (empty drums / looper), no timing frames. Owner: "that works".
