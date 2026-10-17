# Brief: how stock Zoom delays get their delay-line memory (2026-10-17)

Goal: a CF Delay (and longer modulation lines) for the G1X Four. The slot image heap is 40 KiB
(docs/DSP_RULES.md), far too small for a 0.5-3 s delay line. recon/14 section 2 lists a fixed
**per-slot large work buffer of 0x81330 bytes** (= 3 s x 44100 x 4 B, exactly a DELAY_3S line), "fixed
descriptor, no general allocator established". We need the mechanism by which a stock delay effect
obtains and uses that buffer, precisely enough that our own effect can do the same.

Offline only. Never touch the pedal, MIDI/audio devices, updater .exe files or `tools/*flash*`. Edit only
your report and scratch folder. Follow docs/helpers/SAVE_PROTOCOL.md (report first, commit only your report
after each finding, never push). Tag every claim with address + instruction text + confidence.

## Inputs
- Stock effect files: `backup/2026-10-04/files/DELAY_3S.ZD2` (plain 3 s delay, the main target),
  `ANDLY_3S.ZD2`, `TAPEECHO.ZD2`, `MODDELAY.ZD2`. Format: docs/FORMAT.md, recon/13_effect_loader.md
  (ELF inside the ZD2; existing tools in `tools/` parse it: look for zd2/elf helpers before writing new ones;
  TI `dis6x` is at the CGT path used by tools/make_usb_audio_fw.py `ctl.CGT`).
- Framework: `build/fw/map/main.dis`, `build/fw/map/refs.txt`, recon/14_effect_memory.md (sections 2-4:
  per-slot coefficients 0x348, state 0x2a0, large work buffers 0x81330; entry[5]..[8] are callbacks with
  instance A4 and service ctx B4), recon/13.
- Our effects for comparison of the calling convention: `effects/ratx/`, `effects/common/`.

## Questions (in order; save after each)
D1. Where are the per-slot large work buffers (base per slot, how computed) and who writes their
    descriptor? Are they always present for all 5 slots or reserved only when an effect asks?
D2. How does DELAY_3S's code get the pointer: an argument of its process/init function, a field of the
    instance/service context (which offset), a framework call (which address/symbol)? Quote DELAY_3S's
    own instructions that load it, and the framework side that supplies it.
D3. Does the effect file declare that it needs the buffer (a flag/size in the effect header, symbol, entry
    field)? What happens for an effect that does not declare it; can any effect use it?
D4. Lifetime: is the buffer zeroed on patch load / slot change? Who else may write it (shared between slots,
    used by the looper/other features)?
D5. Recipe: the exact minimal steps a CF effect (our build in tools/build_g1.sh) must take to use the
    buffer, and the size it can rely on. Note what stays unproved and what one pedal test would prove it.
Finish with a Summary (<= 15 lines) at the top.
