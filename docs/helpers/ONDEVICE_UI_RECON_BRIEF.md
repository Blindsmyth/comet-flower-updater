# Brief: on-device UI recon for controller mode and USB audio (2026-10-15)

Read `docs/helpers/SAVE_PROTOCOL.md` first and follow it. Your report goes to
`docs/helpers/ONDEVICE_UI_RECON_REPORT.md`; create it first, with the section
headings below. Commit only that file. OFFLINE ONLY: never run an updater and
never touch the pedal.

Inputs: `build/fw/map/main.dis` (dis6x of the v2.00 main firmware),
`build/fw/map/refs.txt`, `build/fw/map/bitmaps.txt`, `recon/10_firmware_capabilities.md`
(display map, fonts, the draw routine `c011c508`), `recon/15_controls_midi.md`,
`recon/18_round3.md` §2 (the controller dispatch gate),
`firmware/controller/controller.c` (the 7 hooks of the controller candidate).
Scratch folder: `build/ui_recon/`.

## Why

The owner wants the pedal itself to show what it is doing in USB MIDI
controller mode and in USB audio mode: a mode banner, CC feedback,
USB connection and stream state. Today the controller candidate skips the
MainApp handlers, *including their screen actions* (recon/18 §2), so the
screen probably stays on a stale patch display. Neither candidate draws anything.

## Questions (answer in order, each with addresses and a confidence)

1. **Screen selection, `c01595e8`.** It calls `c0127fe0` (also the MainApp dispatch
   target hooked by `controller_dispatch`) and `c0148af4`, then picks
   `c015942c`, `c01594f0` or `c01594c8` (the PC MODE bitmap `c0178ee0`, full
   screen). Find who calls `c01595e8`, in which task, and what condition shows
   PC MODE. Is it the editor/PC connection state? Note that `c01594c8` tests its
   own A4 before drawing; explain this.
2. **LCD ownership and flush.** Which task writes the framebuffer and which pushes it
   to the panel (UpdateUI `c013c754`? a periodic refresh?)? Is there a
   lock? Can code running in the MainApp task or the MIDI worker request a redraw safely
   (for example by posting an event that UpdateUI handles), or must drawing happen inside UpdateUI?
   What does `ctx` (`*(B14+122*4)`) point to?
3. **Text drawing.** Give the signatures of the string and glyph routines (`c011e898..`,
   `c011ebc8`, `c011ec48`, `c016c360` looks like a formatter). Which font is used
   for small status text? Give a minimal call sequence that draws one short line.
4. **In controller mode** (dispatch gated, `controller_dispatch` returns
   without calling the stock handlers): what is on screen after boot, and does any
   periodic path still redraw it (recon/18: housekeeping `c01537f4` still runs)?
5. **LEDs.** Does the G1X Four drive any LED from firmware (footswitch/effect-on
   LEDs, if fitted)? If so, which routine and which GPIO? If there are none, say so.
6. **Hook proposal.** The smallest safe way to show (a) a "MIDI CTRL" banner at
   controller-mode entry, (b) the last CC number and value, and (c) USB state
   (not connected / connected / audio streaming). Name the hook site, the execution
   context and what must not be called from it. Design only, no build.

Sol: check every `[B0]`/`[!B0]` predicate you quote against the instruction.
State the truth table explicitly where a branch decides something.
