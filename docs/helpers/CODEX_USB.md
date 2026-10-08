# Brief for Codex (gpt-6-astra, medium): USB MIDI controller blockers and USB audio out

Follow `docs/helpers/SAVE_PROTOCOL.md` exactly.
- Report file: **`recon/17_usb_midi_audio.md`**. Create it first, with the
  section headings below, then commit it. Commit THAT FILE ONLY after every
  finding.
- Scratch folder: **`build/codex7/`** (scripts, dumps, candidate images).
  Never write anywhere else in the repository.
- **Static analysis only.** Never touch the pedal. Never run MIDI tools,
  `tools/pedal_g1.py`, `tools/patch_g1.py`, any updater `.exe` or anything
  that opens a USB device. Do not edit tools/, src/, effects/ or other recon files.
- Every finding gives the instruction addresses, a short disassembly excerpt,
  and a confidence: confirmed / likely / guess. If you can't close a question,
  write down exactly what is missing. Don't fill gaps with plausible claims.

## Inputs
- Main firmware AIS: `build/fw/res1_493412.bin`; full disassembly
  `build/fw/map/main.dis` (ELF `build/fw/map/main.elf`); AIS walker
  `build/fw/map/ais.py`; previous scratch `build/codex6/` (has `main-all.dis`,
  `ais.ps1`, the compiled controller prototype and `CONTROLLER_README.md`).
- Boot/update program: `build/fw/res5_163840.bin` (runs at c020xxxx..c022xxxx;
  normal AIS load at c022baac..c022bac8, recon/15). Disassemble it yourself.
- TI tools: `C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS/bin/dis6x.exe` (and cl6x).
- Background reading: `recon/15_controls_midi.md` (all of it, especially §6
  and the A2 section), `recon/16_audio_hw.md` (audio path, EDMA ping-pong,
  C10/C11 L2 residency), `recon/10_firmware_capabilities.md` (USB descriptors),
  `recon/14_effect_memory.md`.
- TI documents (fetch them if you can): SPRS377 (C6745/C6747 datasheet),
  SPRUFM9 (USB 2.0 OTG controller user guide for OMAP-L137/C674x),
  SPRUG82 (C674x cache user guide).

## Part A: close the USB MIDI controller-mode blockers

A1. **Is 1182a000.. writable when the boot program loads the main AIS?**
    Find every write to the cache registers (L2CFG 01840000, L1PCFG 01840020,
    L1DCFG 01840040, and MAR/L2 block ops) in res5, and anything the ROM
    bootloader does first. Decide whether an extra AIS section-load record
    targeting 1182a000 would land in SRAM, and whether its contents survive
    the main firmware's early L2CFG=2 write at c016d080 (SPRUG82: what
    happens to the part of L2 that stays SRAM when the L2 mode changes).
    Answer "yes / no / unknown because ...".
A2. **Are the three veneer caves free?** c0134e2c, c01333d0 and c0150b0c
    (recon/15 A2). Prove that no branch, call, table word, relocation or
    computed address points into any of them, or name what does.
A3. **Transmit backpressure.** Trace c01274cc and the MIDI ring/worker
    (c0149d40 ...). What happens when the ring is full: drop, block, or
    partial write? What is the ring size? Propose a coalescing rule for knob
    and expression CCs that never blocks the MainApp loop.
A4. If A1 and A2 both come out "yes": write `build/codex7/make_controller_image.py`.
    It must build a candidate AIS (input SHA-256 checked) with the 9-byte
    residency patch from `patch_res1.py`, an extra section-load record for
    the controller payload `build/codex6/controller-code.bin` at 1182a100,
    the state area, and the hook/veneer bytes from recon/15 A2. Verify the
    result by re-walking the AIS and disassembling the patched spots with
    dis6x. Only produce the file; never package it into an updater.
A5. List what can only be settled on the pedal (button/GPIO legend, knob
    direction, startup gesture) as a short owner test checklist.

## Part B: USB audio out (the pedal as a USB audio device)

The goal is a computer seeing the G1X Four as a class-compliant USB audio
source, playing the processed guitar signal, alongside the existing MIDI
interface. Full-speed only.

B1. **Current descriptors.** recon/10 found the device descriptor at
    res1 0x73364 and a 0x65-byte config whose interface/endpoint
    descriptors are built at runtime. Find the builder and reconstruct the
    exact bytes the host receives: interfaces, classes, endpoints, packet sizes.
B2. **USB0 endpoint FIFO use.** Decode how the firmware configures endpoints
    and FIFO RAM (sizes/addresses written to the controller). How much FIFO
    is free? Would an isochronous IN endpoint fit for 44.1 kHz stereo:
    16-bit (max 45 frames × 4 B = 180 B/ms) and 24-bit (270 B/ms)?
B3. **Where to tap the audio.** From recon/16, find the final output
    samples just before McASP0 transmit (the EDMA ping-pong buffer, per
    16-frame block). Name the address and the context (audio Swi / Hwi) where
    a copy into a USB ring buffer would go, and its cost per block.
B4. **USB servicing.** Find the USB interrupt/ISR and the task that handles
    endpoints. Does the firmware use the CPPI DMA or PIO for FIFO loads? How
    would 1 ms isochronous IN packets be fed (SOF interrupt or DMA)?
    Sync model: the codec is the clock master (44.1 kHz from the 19.2 MHz
    PLL), so the endpoint would be asynchronous IN, sending 44 or 45 frames
    per frame interval.
B5. **Verdict and plan.** Give feasibility (blocked / hard / doable) with
    reasons: free FIFO, CPU, code space (where the code would live), and a
    new config descriptor (MIDI + UAC1 audio streaming; class-compliant on
    Windows/macOS). Then list the minimal patch steps in order. No code is
    needed for Part B unless all the facts are in place.

Order of work: A1, A2, B1, B2, A3, B3, B4, B5, A4, A5. Save after each item.
