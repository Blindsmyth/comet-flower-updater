# Round 4 briefs (Sonnet helpers, 2026-10-08)

Both helpers follow `docs/helpers/SAVE_PROTOCOL.md` exactly, including the
token-economy rules. Report first, then commit **that report file only** after
every finding. If the report exists, continue from the first item without
"Status: done". Static analysis and offline compiling only: never touch the
pedal, USB/MIDI devices, any `.exe`, `tools/pedal_g1.py` or `tools/patch_g1.py`.
Do not edit tools/, src/, firmware/, effects/ or other recon files; code goes
in your scratch folder and Claude integrates it.

Common inputs: `build/fw/map/main.dis` (format "ADDR WORD [||] OP ARGS"),
`build/fw/map/strings.txt`, `build/fw/res1_493412.bin`, TI tools in
`C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS/bin/` (cl6x, lnk6x, dis6x; see
`tools/make_controller_fw.py` for the exact compile/link flags that work),
the controller sources in `firmware/controller/`, and `recon/17_usb_midi_audio.md`,
`recon/18_round3.md`.

Free memory for new code: SDRAM `c01a0000..c01f4000` (recon/17 "Placement
in SDRAM"); the controller uses `c01a0000..c01a3fff`. Helper A may use
`c01a4000..c01a7fff`, helper B `c01a8000..c01affff`.

## Helper A: bounded MIDI transmit for controller mode
Report `recon/19_midi_tx.md`, scratch `build/sonnet4a/`.

Problem (recon/18 1.6, recon/17 A3): the controller calls the stock send
c01274cc directly from MainApp and the AD task. Its outer lock B14[161]
waits forever; a full 1024-byte ring drops bytes and hides partial writes.

1. Find how the firmware creates tasks and periodic work: SYS/BIOS
   Task_create / Clock / Swi constructors used at start-up (task descriptor
   tables such as c01800bc in recon/17 B4), and any existing periodic
   task or MainApp housekeeping (c01537f4 runs every MainApp loop pass) where
   a drain step could run. Recommend ONE place with evidence.
2. Find the ring's free-space test (c0149d80.., c0149de4) and whether a
   caller can check free space without taking a blocking lock.
3. Design and write C (and asm if needed) in `build/sonnet4a/`:
   producer side = latest value per CC plus a dirty bit, written by the hooks
   with no locks and no waits; consumer side = one drain step that sends at
   most N dirty CCs only when 3 bytes are free, never blocking. Compile it
   with cl6x for c01a4000 and check the disassembly for B14 use and calls.
   State clearly anything the consumer must call that can block.

## Helper B: USB audio "silence stream" prototype
Report `recon/20_usb_audio_proto.md`, scratch `build/sonnet4b/`.

recon/18 item 3 (3.1-3.6) gives a patch list for a first step: enumerate as
MIDI + UAC1 audio and stream zeros on isochronous IN endpoint 1.

1. Re-verify each 3.x claim you build on against main.dis (addresses and a
   short excerpt), marking any that do not hold.
2. Turn 3.6 into exact work items: every stock instruction or data word to
   change (address, old word, new word or new target), every new routine
   with its calling context (Hwi/Swi/task), and the descriptor bytes from
   recon/17 B5 placed in the SDRAM window.
3. Write the new routines in C/asm in `build/sonnet4b/`, compile for
   c01a8000, check the disassembly. Do not build a firmware image.
4. List what can only be proven on hardware (enumeration on Windows/macOS,
   timing in the SOF interrupt).
