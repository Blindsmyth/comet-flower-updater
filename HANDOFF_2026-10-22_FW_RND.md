# Handoff 2026-10-22: Firmware R&D for effect building (slots, heap, stack, fault handling)

For the deep firmware work planned for Thursday 2026-10-23. It is one section of the full firmware teardown, written so the answers feed straight into it. Workspace: `c:\Users\z\Documents\zoom project`. Main firmware disassembly: `build/fw/map/main.dis`. Main firmware flash region: `0x33000`.

## Goal
Comfortably Numb tone in a box: a chain of Muff, Mistress, Delay, amp and rotary (see `docs/CN_CHAIN_SPEC_2026-10-21.md`). Effect building itself is now mostly predictable. These unknowns still force trial and error, or limit what one effect or one patch can do.

## What the hardware tests established (owner, Updaters 24 and 25, 2026-10-20/21)
- A patch has **5 slots**. The pedal refuses a patch whose declared `dspload` sum reaches 230 (`docs/DSP_RULES.md`, Process Overflow rule).
- Header byte `0x58` of a ZD2 is the slot count the effect claims. Single-stage effects use 1; `CFMPRE` 2; `CFM2P` 2; `CFM5P` 5.
- **CF M2 (header 2) loads and is listed.** On screen a 2-slot effect looked like one slot in the patch: a patch of `CFMPRE`, Delay, Watt and RA200 left slot 5 free, and an effect could still be added to slot 5.
- **CF M5 (header 5) is not offered in the effect list at all** (Updater 24 and 25, `CFM5P.ZD2` is in the image).
- CF M2 probe (`CFM2P`, Mode 1, decoded with `tools/decode_memprobe.py`, `build/probe_cfm2p_m1b*.wav`):
  - called 1.00 times per block, one instance;
  - `instance 0x11f03ad0`, `coef 0x11f00000`, `state 0x11f013b0` (on-chip L1D RAM);
  - work buffer `0xc0226000`, 529,200 B, slot 0; work buffers 1-4 empty;
  - code at `0xc01f41e0`, slot region 0;
  - all 12 knobs reach the DSP.
- Bench of `CFMPRE` + Delay + Watt + RA200 (slot 1 to 4): CPU 88.1% of a block on average, peak 105.2%, 0 lost frames. Medians: slot1 31.4k, slot2 7.4k, slot3 24.7k, slot4 14.1k (RA200, expected 4k), slot5 3.7k (empty slot).
- **`RA200X` alone: no audio.** With `CFMPRE` and Watt before it: no audio, and adding more effects after it **crashes the USB audio driver**. Host tests (`ra200_test`) pass. It is the only effect built with `allow_stack`, writes stereo into the bus (`SH_CH_B_OFFSET`) and keeps its state in the slot work buffer (`instance[3]`).

## Questions for the firmware R&D
1. **Slot limit and effect list.** Where does the firmware decide which effects the list offers? Why is a header-5 effect hidden while header-2 is offered? Is the limit the header value, the patch slot count, or something else? Can it be raised (up to 5, or beyond)?
2. **How slot count maps to memory.** Does a header-N effect get N times the 40 KiB code/const heap, or only 40 KiB? (`CFM2P` only showed the slot-0 code region.) What does the loader allocate for code, const, state, work buffer, and does a multi-slot effect also take the next slot's resources?
3. **Per-effect limits.** Where do the 40 KiB heap, the 12-param maximum and the 3-params-per-page limit come from? Can the param count and page layout be changed?
4. **Stack.** How large is the stack an effect runs on, and where? The documented stock maximum is 1536 B; DR103 uses 1428 B. What happens on overflow? `RA200X` uses the stack and has no measured frame size.
5. **Fault handling.** Why does a bad effect crash the USB audio driver (not only the audio path)? What shared state or memory does an overrun, bad stack or bad pointer corrupt, and can a failing effect be isolated or contained?
6. **Load and overflow.** What does the firmware do when a block exceeds its cycle budget (peak 105% was seen without a warning)? Does it drop audio, skip the block, or fault? Can USB audio survive it?
7. **Display/menu.** Can the effect menu use per-effect labels longer than the current font allows, change labels per page, or show a sub-menu for one effect (one effect holding a chain of stages)? Where is the menu code?
8. **Stereo bus.** How is the channel-B bus (`SH_CH_B_OFFSET`) consumed by later effects and the USB tap? Is stereo from a mid-chain effect safe?

## Deliverables wanted
- A written map (addresses in `main.dis`) of: effect list filter, slot-fit check, loader allocation (heap, stack, work buffer), param table limits, menu page layout, and the fault/overflow path.
- For each question: answer, evidence (disassembly lines), and whether a firmware patch can change it, with the patch plan and risk.
- A recommended order for patches that fit the existing firmware patch tool (`tools/make_public_usb_audio_patch.py`, `tools/make_usb_audio_fw.py`), keeping the non-destructive flashing rules (main partition `0x33000` only).

## Constraints
- Do not flash. Owner flashes. Never save a patch containing a probe effect. Keep every effect within `docs/DSP_RULES.md`.
- Python: `.venv\Scripts\python.exe`. TI CGT C6000: `C:\Users\z\ti\ti-cgt-c6000_8.5.0.LTS\bin\`.
- Updater with debug probes can be built after the answers (`tools/make_g1_image.py --replace`).

## Open on the effect side (not firmware)
- Replace `RA200X` with a simple mono rotary built in the proven leaf-kernel style (no stack, mono, under 5k cycles). The full RA-200 comes back after the answers above.
- `CFMPRE` pages must be re-laid out so each page is one stage (3 params per page).
- Delay tail on bypass, display label length, bench numbers per stage.

## Related files
`HANDOFF_2026-10-20.md`, `docs/CF_MASTER_PROBE_2026-10-19.md`, `docs/CF_MASTER_DESIGN.md`, `docs/CN_CHAIN_SPEC_2026-10-21.md`, `docs/DSP_RULES.md`, `effects/ra200x/ra200x.c`, `tools/decode_memprobe.py`, `build/bench/manual.md`.
