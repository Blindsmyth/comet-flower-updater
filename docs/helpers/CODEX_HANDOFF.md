# Brief for Codex (Astra): Firmware Handoff & Next Objectives

Follow `docs/helpers/SAVE_PROTOCOL.md` exactly:
- Commit your report file after every finding (`recon/15_controls_midi.md` or `recon/16_audio_hw.md`).
- Scratch directory: `build/codex6/`.
- Static analysis only. Do not execute any pedal-flashing scripts.

---

## 1. Current State & What Was Just Completed

We are on branch `recon/audio-cache-patch`.

### L2 SRAM Slot 0 Residency Patch (`recon/16_audio_hw.md`)
The L2 cache shrink (128 KiB -> 64 KiB) and Slot 0 relocation to on-chip L2 SRAM (`0x11820000`) has been implemented, hardened, and verified in `patch_res1.py`:
- **Operation 1a (Early L2CFG init at `0x61008` / `c016d08c`)**: Replaced `f6 62 3c 00` with compact 16-bit instructions `27 44 05 fc` (`MVK.L2 2, B0; STW.D2T2 B0, *B15[3]`), cleanly setting L2=2 while preserving L1D=3.
- **Operation 1b (.fphead at `0x61018` / `c016d09c`)**: Updated bit 24 in the fetch-packet header (`00 00 d0 e0` -> `00 00 d0 e1`, mask `0001110b`), declaring Slot 3 as compact so the VLIW decoder executes both instructions without trapping.
- **Operation 2 (Late L2CFG table at `0x756b0` / `c0181728`)**: Overwrote `03 00 00 00` with `02 00 00 00`.
- **Operation 3 (Active Slot 0 base table in .cinit RLE stream at `0x77efd`)**: Overwrote `40 1f c0` with `00 82 11` inside the compressed stream (`1a 05 00 ...`). Decompressor independently verified to unpack `0x11820000` into `c01839a8` with zero stream shift.
- **Status**: The script `patch_res1.py` enforces input SHA-256 (`43060686...`), verifies an exact 9-byte diff, independently decompresses the .cinit stream, and atomically outputs `build/fw/res1_patched.bin` (SHA-256: `9E2CCC1B727672C250D431A8D88A1D5101105C5DB90EC7CFC8CA85799267C002`).

---

## 2. Your Objectives (Codex / Astra)

### Task A: Complete the USB MIDI Controller Implementation (`recon/15_controls_midi.md`)
You authored `recon/15_controls_midi.md` and laid out the blueprint in Section 6. Now turn that blueprint into concrete code / hooks:
1. **Startup Toggle Latch**:
   - Location: Interpose MainApp call at `c0134e14 -> c015d428`.
   - Sample a designated front-panel button (or footswitch held at power-up) via `c0156f00`.
   - Latch a 1-byte `g_controller_mode` flag in unused BSS / L2 space.
2. **MainApp Dispatcher Interception**:
   - Location: Hook call at `c0134df0 -> c0127fe0`.
   - When `g_controller_mode == 0`: Call `c0127fe0` as stock.
   - When `g_controller_mode == 1`: Consume the event at `*+B15[1]` (B15+4), map the event ID to a MIDI CC / PC, call `c01274cc(bytes, len)` to transmit over integrated USB0, and branch back to `c0134dc4` (skipping stock patch/menu dispatchers `c0134acc` and `c0134d04`).
3. **Rotary Encoders & Analog Interception**:
   - Knobs: Map events 25..28 (delta in word[2]) to CCs.
   - Expression Pedal: Intercept `c015ffd0 -> c014aef4` (A4 = 0..127 calibrated analog). When in controller mode, send CC and return without touching effect parameters.
4. **Concrete Machine Code & Trampoline Placement**:
   - Determine where the trampoline code will sit in memory (e.g. alignment padding at the end of Section 5 `0x636fc` or Section 6 `0x75aac`).
   - Calculate the exact TI C674x 32-bit instructions for the trampoline.

### Task B: Audit Effect Unload/Reload Quiescence (`recon/16_audio_hw.md`)
1. Trace the runtime patch-switching path (`c015f72c` / `c013398c`).
2. When the user changes patches on the pedal, does the firmware gate / mute `g_Swi_AudioProcess` before loading a new `.zd2` into Slot 0 at `0x11820000`?
3. Verify whether `c016e360` (L2 writeback-invalidate) or `c016b1c0` (L1PINV) is called during patch switching, and confirm whether any stale L1P instruction hazard exists when swapping effects.

### Task C: Updater Script Enablement (`tools/make_fs_restore_updater.py`)
1. `tools/make_fs_restore_updater.py` currently rejects firmware diffs outside `FW_CONST = (0x63708, 0x75aac)`.
2. Add a `--patch-fw` option that safely allows writing our 9-byte patched firmware (`build/fw/res1_patched.bin`) into flash `0x33000` while preserving emergency recovery.

---

## 3. Rules Reminder
- Static analysis only.
- Append findings with instruction addresses and confidence (`confirmed` / `likely` / `guess`) to `recon/15_controls_midi.md` or `recon/16_audio_hw.md`.
- Commit after every finding following `docs/helpers/SAVE_PROTOCOL.md`.
