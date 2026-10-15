# Owner-Run Test Preparation: USB Teardown Diagnostic Candidate — 2026-10-15

Author: Flash 3.8 / Antigravity.
**DO_NOT_FLASH remains in effect. Flashing or running updaters is strictly the owner's manual decision.**
This document outlines the test procedure, safety boundaries, memory extraction locations, and analysis steps for the offline teardown diagnostic candidate.

---

## 1. Scope & Candidate Identity

The diagnostic candidate is an **observer-only instrumented build** designed to record descriptor queue activity during USB endpoint aborts and teardowns. It does **not** claim to fix or alter the stock USB teardown race; it records ground-truth evidence of what occurs on physical C6745 hardware.

- **Source Files**:
  - `firmware/controller/controller_diag.c`: 24-entry circular buffer (`ctl_diag`) in `.ctl_state`, sticky fault flags, teardown and consumer counters.
  - `firmware/controller/controller_diag_hooks.asm`: Register-preserving thunks for both hook sites, tail-calling stock `c011fa54`.
  - `firmware/controller/controller_diag.cmd`: Retains `.text:diag_teardown` and `.text:diag_consumer`.
  - `tools/decode_ctl_diag.py`: Host decoding tool for memory dumps.
- **Hook Sites**:
  1. `0xc0120744` (file offset `0x146c0`, stock `1ffe6292`): inside the abort drain loop on queue 25 (`c0120734..0762`).
  2. `0xc0121a18` (file offset `0x15994`, stock `1ffc0a92`): inside the deferred queue 32..35 consumer `c01219f4`.
- **Offline Build Command**:
  ```powershell
  .venv/Scripts/python.exe tools/make_controller_fw.py --diag-teardown --out build/controller/diag_teardown_candidate.bin
  ```
- **Safety Boundary**:
  - `DIAG_HOOKS` are explicitly isolated from `HOOKS`.
  - `tools/make_fs_restore_updater.py` and `tools/verify_controller_candidate.py` **reject** this build because it does not match the 7-hook lifecycle manifest.
  - The standard lifecycle candidate (`build/controller/DO_NOT_FLASH_controller_lifecycle_candidate.exe`) remains byte-identical and untouched.

---

## 2. Memory Structure: `ctl_diag`

The diagnostic structure resides at a fixed address in SDRAM:
- **Base Address**: `0xc01a0b00` (mapped in `.ctl_state`, verified via `build/controller/diag/controller_diag.map`).
- **Total Size**: 408 bytes (`0x198` bytes, spans `0xc01a0b00..0xc01a0c97`; `ctl_state` follows at `0xc01a0c98`).
- **Magic**: `0x54444731` (`b"1GDT"` in little-endian ASCII).

### Structure Layout

| Offset | Field | Type | Description |
|---|---|---|---|
| `+0x00` | `magic` | `u32` | `0x54444731` (`TDG1`) |
| `+0x04` | `head` | `u32` | Total log writes (ring index = `head % 24`) |
| `+0x08` | `fault` | `u32` | Sticky OR of detected fault conditions |
| `+0x0c` | `teardown_seen` | `u32` | Total type-19 descriptors observed across both sites |
| `+0x10` | `consumer_pops` | `u32` | Total pops by queue 32..35 consumer (incl. type 16) |
| `+0x14` | `consumer_other`| `u32` | Pops with type != 16 (logged into ring) |
| `+0x18` | `e[0..23]` | `24 * 16B`| Array of 24 ring entries |

Each entry is 16 bytes:
- `tag` (`u32`): `(site << 24) | (aux << 16) | seq`:
  - `site`: `1` = abort drain (`0xc0120744`), `2` = queue consumer (`0xc0121a18`).
  - `aux`: endpoint slot (for site 1) or queue ID (for site 2).
  - `seq`: monotonically increasing event sequence counter.
- `idx` (`u32`): popped CPPI descriptor index (`0..N`).
- `word0` (`u32`): raw descriptor word 0 (contains packet type `[31:27]` and channel `[5:0]`).
- `tscl` (`u32`): hardware timestamp cycle counter (`TSCL`).

### Sticky Fault Bits

- `0x1` (`FAULT_TYPE19_RECYCLED`): Site 1 (abort drain loop) popped and recycled a type-19 teardown descriptor. (Direct proof of teardown recycling without association).
- `0x2` (`FAULT_CHANNEL_MISMATCH`): Site 1 popped a type-19 descriptor whose channel field does not match `(slot - 1)`.
- `0x4` (`FAULT_RING_WRAPPED`): More than 24 entries were logged, overwriting the oldest entries.
- `0x8` (`FAULT_TYPE19_CONSUMER`): Site 2 (deferred queue 32..35 consumer) popped and recycled a type-19 descriptor. (Proof of the Hwi -> queue 32 race).

---

## 3. Test Scenarios (Owner Procedure)

If the owner decides to run an instrumented session on hardware:

### Test Scenario A: Normal Controller Traffic (Baseline)
1. Boot pedal while holding **GPIO0 / Rhythm button** to enter Controller Mode.
2. Launch receive-only MIDI monitor:
   ```powershell
   .venv/Scripts/python.exe tools/cf_midi_monitor.py
   ```
3. Connect USB cable to host.
4. Exercise buttons, knobs, and expression pedal. Verify CC messages receive cleanly.
5. **Expected Diagnostic State**:
   - `fault == 0x00`
   - `teardown_seen == 0`
   - `consumer_pops` increments with traffic.
   - `consumer_other == 0` (normal type-16 packets are counted, not logged into the 24-entry ring).
   - Ring remains clean.

### Test Scenario B: Abrupt Disconnect (Endpoint Teardown Trigger)
1. While streaming active MIDI data (e.g. moving expression pedal continuously), physically unplug the USB cable or reset the host USB root port.
2. Allow 3–5 seconds for stock abort routine and teardown to execute.
3. Re-plug the USB cable.
4. Extract memory dump and decode `ctl_diag`.
5. **Expected Diagnostic State**:
   - If teardown was drained by abort loop: `site 1` entries present, `teardown_seen >= 1`.
   - If Hwi routed teardown to queue 32: `site 2` entries present with `type == 19`, `fault` bit `0x8` set.
   - If race occurred and abort loop popped unassociated descriptor: `fault` bit `0x1` set.

---

## 4. Host Decoding Procedure

Once a memory dump is obtained (either full SDRAM dump or a slice containing `0xc01a0b00`):

```powershell
# Format human-readable trace table:
.venv/Scripts/python.exe tools/decode_ctl_diag.py path/to/memory_dump.bin

# Or export JSON:
.venv/Scripts/python.exe tools/decode_ctl_diag.py path/to/memory_dump.bin --json > diag_report.json
```

The decoder automatically locates the `TDG1` magic, chronologically sorts the circular ring entries, translates types/channels, and displays any triggered sticky faults.
