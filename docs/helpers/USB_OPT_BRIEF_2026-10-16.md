# Brief: USB audio "as good as it can be" (2026-10-16, evening)

State: the CF tap build streams the pedal's output to the PC over USB, clean (HANDOFF_2026-10-16_USB_AUDIO.md,
docs/CF_USB_MODE_2026-10-16.md). Our code: `firmware/usb_audio_proto/usb_audio.c` (descriptors, EP1 set-up,
alt switch) and `usb_audio_tap.c` (ring, SOF Hwi, Swi tap). Builder: `tools/make_usb_audio_fw.py`.
Capture/analysis tool: `tools/ua_capture.py`. Tests: `tools/test_usb_audio_proto.py` (run with `.venv/Scripts/python -m pytest`).

Rules for both helpers: **never** touch the pedal, MIDI ports, audio devices, updater `.exe` files or
`tools/*flash*`; never record audio. Edit only your own report, your scratch folder and the files your
section names. Follow docs/helpers/SAVE_PROTOCOL.md (report first, commit only your own files after each
finding, never push, never `git add -A`). Tag firmware claims with address + instruction text and a
confidence (confirmed / likely / guess). Put a "Summary" (<= 15 lines) at the top of your report when done.

## Astra (Codex, gpt-6-astra, medium) -> `docs/helpers/USB_OPT_ASTRA_2026-10-16.md`, scratch `build/scratch/astra_usbopt/`

Firmware inputs: `build/fw/map/main.dis` (TI C674x disassembly), `build/fw/map/main.elf`, `build/fw/map/refs.txt`
(`<insn addr> <reg> <value>` constant loads), `build/fw/map/strings.txt`. Prior USB RE: `recon/17_usb_midi_audio.md`,
`recon/18_round3.md`, `recon/20_usb_audio_proto.md`, `recon/21*` if present. Work in this order; save after each.

A1 (most important). **EP0 zero-length packet.** Our configuration descriptor is 192 bytes = exactly 3 x 64-byte
EP0 packets (`new_config_hdr`, wTotalLength 0xc0). Windows first asks for the configuration descriptor with
wLength 255. USB 2.0 8.5.3.2: if the reply is shorter than wLength and a multiple of wMaxPacketSize (64), the
device must end the data stage with a zero-length packet, or the host waits. Find Zoom's EP0 control-IN data path
(GET_DESCRIPTOR reply, clipping near c013506c..c01350ca, EP0 FIFO 0x01e00420 writes near c0122380, CSR0 writes
TXPKTRDY / DATAEND) and answer: does it ever send a ZLP when length % 64 == 0 and length < wLength? Quote the
instructions. If not: say what it does instead (sets DATAEND on the last full packet? then the host sees a
complete short transfer — fine — or leaves the host waiting?). On MUSB peripheral EP0 (SPRUFM9H), setting
DATAEND together with TXPKTRDY on the last packet ends the data stage; note exactly which bits are written.
Context: on a motherboard root port Windows gives Code 10 (0xC0000001) for this device; through a USB 2.0 hub
it works. Any other enumeration-timing hazard you see in this path (e.g. slow responses, STALL on
unknown requests such as GET_DESCRIPTOR device_qualifier / string index 0xEE / BOS / GET_STATUS) goes here too.

A2. **Where the tap sits in the level chain.** The tap reads the stock TX pack's planar inputs `11f038b0`/`11f038f0`
before the pack `11818aa0` (gain SSHL(SMPY32(x,0x4534fd79),2)). Is the output/master volume (and the patch
level) applied before those buffers (so USB level follows the volume knob) or after (in the codec / a later
stage)? Name the routine that applies the output volume and the variable it reads, if you can find it.

A3. **24-bit feasibility (FIFO budget).** 24-bit stereo at 45 frames/ms is 270 bytes/packet (32-bit container:
360). EP1 today: FIFO at 0x140, 2 x 256 B (TXFIFOSZ 0x15), TXMAXP 180. Map the USB0 FIFO RAM as stock
programs it (EP0, the MIDI endpoints RX3/TX4: addresses and sizes, `c01212e0`, `c012146e..14c6` repacker) and
say whether 2 x 512 B for EP1 fits without moving stock endpoints, and at which address.

## Argon (agy, Gemini 4 Argon) -> `docs/helpers/USB_OPT_ARGON_2026-10-16.md`, scratch `build/scratch/argon_usbopt/`

Goal: make `tools/ua_capture.py`'s analysis of normal (non-pattern) takes trustworthy, so a long take can
prove "no dropouts" without a diagnostic build.

Problem: the current click detector (second difference > threshold) flags normal waveform features. Real
example: `build/ua_takes/take_20261016_172545.wav` (10 s, nothing played: 60/180 Hz mains hum at -34 dBFS,
one 89-frame zero run at the start = stream priming) gets 16 "clicks", all false.

B1. Write a detector for the defects a USB stream can really have: lost frames (a gap of 1..45+ frames
spliced out), repeated frames, inserted zero frames / zero runs, and a sample jump. Suggested method:
linear prediction (order ~16-32, fitted per block of ~4096 frames, e.g. numpy least squares) and flag
residual outliers relative to the block's robust residual level (median absolute deviation); then merge
nearby flags into events. Leading zero run (priming) is reported separately, not as a defect.
B2. Tests in `tools/test_ua_capture_glitch.py` (pytest, numpy only, no audio devices): synthetic signals
(hum 60 Hz + harmonics + small noise; a guitar-like decaying pluck chain; silence with +-1 LSB noise),
inject each defect type at known places, assert it is found within +-2 frames, and assert zero false
events on the clean versions and on the real wav above (allowed to skip if the wav is missing).
B3. Wire it into `ua_capture.py` for non-pattern takes (keep the pattern-take path unchanged; keep the old
level / clipping lines), print one line per event type with count and positions (first 10), and add a
`--seconds` friendly summary: "N defects in M min". Must handle a 10-minute take (26.5 M samples) in under
~60 s and bounded memory (process in blocks).
Edit only `tools/ua_capture.py`, `tools/test_ua_capture_glitch.py`, your report, your scratch folder.
Run `.venv/Scripts/python -m pytest tools/test_ua_capture_glitch.py tools/test_usb_audio_proto.py -q` and
put the result in the report. You may run `ua_capture.py --wav <existing file>` (analysis only);
never run it without `--wav`.
