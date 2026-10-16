# Brief: review the USB-audio mode gating (Codex Astra, 2026-10-16)

Review for correctness bugs only, offline. Commits: 480d98b (ua_mode gate in the descriptor veneer,
ua_usbmidi_open, map thunk stock fallback), 22c4092 (request/active/magic, latch in ua_usbmidi_open,
USB OFF/AUDIO menu item with software replug), and the latest commit (power-up button bit 2).
Files: firmware/usb_audio/{ua_glue.c,ua_thunks.asm,ua.cmd}, firmware/usb_audio_proto/usb_audio_hooks.asm,
firmware/controller/{controller.c,controller_menu.c}, tools/make_fs_restore_updater.py (strip_usb_audio).
Built output to inspect: build/usb_audio/usb_audio.dis, build/controller/ui/controller.dis, stock
build/fw/map/main.dis. Background: docs/helpers/USB_MODE_ASTRA_2026-10-16.md (your own report).

Questions, each answered with address + instruction evidence and a verdict (bug / ok / unproved):
R1. With ua_mode.active == 0, is every patched path byte-for-byte stock in behaviour? (veneer for all
    A4; ua_usbmidi_open; map thunk fallback to c015c678 / c015c6ac with B3 = c015c768 and A1 clobbered;
    SOF tick; anything else the layer patches.) Check the protected-load fetch packets in the dis.
R2. Latch: ua_mode.active = request at entry of ua_usbmidi_open. Is c0145158 on every path that later
    connects (boot, cable attach, any other open), and can a descriptor request ever see a value
    different from the registrations of the same connection?
R3. Software replug in controller_menu.c usb_set: USB_STATE 1181349c == 0 / USB_READY 118134a0 as the
    "USB open" test; c016ab58 then Task_sleep(500) via c014a28c then c016ab8c from MainApp's event
    dispatch. Deadlocks (MainApp waiting on itself, MIDI locks held by MainApp at that point, our
    controller worker hooks), re-entrancy with the cable handler (switch task, priority 9), and anything
    the cable handler does that we skip (1180b170, 11805eb4, 1180b160, event 43) that matters.
R4. strip_usb_audio: can a malformed image pass?
Write `docs/helpers/USB_MODE_REVIEW_ASTRA_2026-10-16.md`; commit only that file after each finding
(docs/helpers/SAVE_PROTOCOL.md). Never touch the pedal or updater files.
