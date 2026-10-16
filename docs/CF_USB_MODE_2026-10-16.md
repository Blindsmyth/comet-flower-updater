# USB-audio mode: TEST build (2026-10-16)

Folder: `build/cf_usb_mode_2026-10-16/` (owner use only: it contains Zoom's firmware code).

| File | SHA-256 (start) | Contents |
|---|---|---|
| `Comet Flower G1X4 Updater (USB mode TEST build).exe` | `821f42aad84f43cf` | Menu candidate + USB-audio silence layer |
| `res1_cf_usb_mode.bin` | `a9657f98c2671048` | `make_controller_fw.py --ui --usb-product …` then `make_usb_audio_fw.py` |

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

- **Start-up:** hold the button that shows as **B3** on the MIDI screen (switch bit 2, GPIO 6, events
  9/10) while powering on. That button has no stock start-up meaning (stock combos checked:
  c0140c8c, table c0180570). Never hold the 2nd button alone (bit 1: stock ALL INITIALIZE prompt).
- **Menu (experimental):** SETTING, turn a knob right, slot 1 (COMET FLOWER), knob 2 **USB: OFF/AUDIO**.
  The item appears only in this build. Changing it while USB is connected does a software replug
  (stock close c016ab58, 500 ms, stock open c016ab8c; the same pair the cable handler uses). If USB is
  not connected it only stores the choice for the next connection.

## Pedal / PC checklist

1. Normal power-on: everything as in the menu candidate; Windows sees only "Comet Flower ZG1X4 MIDI".
   MIDI works (VPB).
2. Power on holding B3: Windows should add an audio input device. In Sound settings > Recording, it
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
