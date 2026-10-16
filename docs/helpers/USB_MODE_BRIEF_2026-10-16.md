# Brief: USB-audio mode as a selectable mode (2026-10-16)

Owner request: USB audio out is a mode of its own, chosen by a button held at power-up **and** from our
MODE item on the COMET FLOWER settings page (FX / MIDI / USB). The pedal always boots in FX unless a
start-up button is held. Background: docs/USB_AUDIO_SILENCE_CANDIDATE_2026-10-15.md (the silence
candidate, `tools/make_usb_audio_fw.py`, glue `firmware/usb_audio/`), docs/CF_MENU_PAGE_2026-10-16.md,
firmware/controller/controller.c (`controller_start` at hook c0134e14; switch bitmap via READ_SWITCHES,
bit 9 = GPIO0 = Rhythm = events 23/24; events are 5 + 2*bit (press) / +1 (release) for the 10 buttons,
0..3 footswitches, 25..28 knobs).

Rules: docs/helpers/SAVE_PROTOCOL.md; offline only; never touch the pedal/MIDI/updaters; edit only your
report and scratch folder; every claim with address + instruction text + confidence.
Disassembly `build/fw/map/main.dis`, refs `build/fw/map/refs.txt`, prior USB recon in
docs/helpers/USB_* and docs/helpers/REVIEW*_USB_AUDIO_CANDIDATE.md.

## Codex Astra -> `docs/helpers/USB_MODE_ASTRA_2026-10-16.md`, scratch `build/scratch/astra_usb/`
U1. **Ordering at boot.** Our flag is set in `controller_start` (MainApp start-up, hook c0134e14). The audio
    glue reads it in the descriptor builder (GET_DESCRIPTOR, after connect) and in `ua_usbmidi_open`
    (hook c0145158). Which task runs c0145158 and the soft-connect (c015af18 per recon/24 5.1), at what
    priority, created where, relative to MainApp's c0134e14? Is c0134e14 guaranteed to run before
    c0145158? If not, where is the earliest safe place to latch the start-up button before USB opens?
U2. **Software disconnect / reconnect.** For a run-time FX/MIDI <-> USB switch the host must re-enumerate.
    Find the stock soft-connect/disconnect writes (MUSB POWER SOFTCONN, c015af18 and any disconnect path,
    e.g. on update/reset or cable events), what USB stack state is (re)initialised on reconnect (slot
    registrations c015afa0, record vector c011aa18, ownership map c011aac0, endpoint maps, alt array
    c011a1b0, CPPI queues), and whether usbmidi_open runs again. Propose the smallest safe sequence:
    disconnect -> flip flag -> reconnect, in which context (task, never Hwi), and what must be reset so
    IF2/IF3 are (de)registered consistently. State what stays unproved.
U3. If a full re-open is needed, list the stock functions and their contexts; flag any lock/semaphore.

## Argon (agy) -> `docs/helpers/USB_MODE_ARGON_2026-10-16.md`, scratch `build/scratch/argon_usb/`
A1. **What each button event does in stock, on the main effect screen** (MainApp ui mode 0, handler table
    c01840b8 -> c0134b94 / c01308e4 and anything reached from it): for every event id 0..28 give the stock
    action (e.g. opens SETTING, next patch, tuner, rhythm, looper, effect select, type change). Use that to
    infer the physical control for each id, confidence-tagged. Especially: which ids are the arrow / scroll
    buttons, and which button (not bit 9) is safest to hold at power-up for USB mode (no stock start-up
    meaning, e.g. not a factory/test or update combination: check the start-up code c0156f00 and res5
    update-mode checks for button combinations).
A2. The bit -> GPIO/pin mapping in the switch scan (READ_SWITCHES, c0156f00 and its helpers), as a table.

Both: Summary (<= 15 lines) at the top when done.
