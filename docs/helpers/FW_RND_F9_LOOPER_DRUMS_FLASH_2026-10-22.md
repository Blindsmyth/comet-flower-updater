# FW R&D F9: Looper and Drum Machine Prior Knowledge Citation Index

## Status
running (Section 1: Looper Subsystem complete)

## Findings

### 1. Looper Subsystem Prior Knowledge

This section compiles all previously verified facts, addresses, buffers, hooks, and UI/task entry points for the G1 Four / G1X Four Looper engine. All citations reference established repository documentation and disassembly chunk analyses; no new disassembly conclusions are introduced.

#### A. State Variables
| Address / Register | Size & Type | Meaning / Role | Confidence | Source File & Line |
|---|---|---|---|---|
| `0x11f03ed0` | 2 × 4 B (8 B) function ptr table | **Looper Pre/Post Dispatch Table**: `11f03ed0[0]` = Pre-effect function pointer; `11f03ed0[1]` = Post-effect function pointer. At boot, both are set to `0xc016d180` (no-op return). When looper is active, `c016a8e0` installs `0x118164c0` into `11f03ed0[A4]` where `A4 = 0` (Pre) or `A4 = 1` (Post). | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:15-16,46-47`; `docs/CF_USB_MODE_2026-10-16.md:481`; `docs/helpers/SLOT_TAP_ARGON_2026-10-17.md:133-134,260-262` |
| `0x11f03c58` | 4 B uint32 | **Looper Bypass / Active Flag**: `*(0x11f03c58) == 0` means Looper is bypassed/inactive (skips SDRAM read/write loops in `118164c0` and exits early at `11816516`/`118165ba`); `!= 0` means active. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:17,74,166` |
| `0x11f03c54` | 4 B float | **Looper Fade-out Multiplier**: Multiplies playback signal during looper stop/fade transitions; sits at `1.0f` during normal playback and ramps to `0.0f` during fade out. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:132` |
| `0x11f03e38` | 4 B float | **Looper Playback Level Ramp**: Active playback gain cell read at `118166c4`/`11816cbc` (`*++B13[1]`, where `B13 = 11f03e38 - 4`); smoothed representation of `11f03c64`/`11f03cd8`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:74` |
| `0x11f03c64` | 4 B float | **Looper Level Target / Gain Cell**: Target gain value for the looper volume smoother. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:74` |
| `0x11f03cd8` | 4 B uint32 / float | **Looper Raw Parameter Value**: Unsmoothed parameter input driving the level ramp. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:74` |
| `0xc011aca8` | 4 B ptr | **Looper Primary SDRAM Arena Base Pointer**: Holds base address of active loop buffer (`0xc04abff0`); initialized by `c0139af6`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:50`; `recon/map/chunk_07.md` |
| `0xc011acac` | 4 B ptr | **Looper Arena End Pointer**: Holds end boundary `0xc04abff0 + 0x2b110 = 0xc04d7100`; initialized by `c0139b08`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:51` |
| `0xc011acb0` | 4 B uint32 | **Looper Capacity Offset**: Loop capacity offset `0x0002b110` (~32 seconds 16-bit 44.1 kHz); initialized by `c0139b0e`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:52` |
| `0xc011acb4` | 4 B ptr | **Looper Write / Boundary Pointer**: Record boundary pointer in SDRAM (`0xc04abff0 + 0x2b110`); initialized by `c0139b18`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:53` |
| `0xc011acc0` | 4 B ptr | **Looper Undo Arena Pointer**: Base pointer for secondary / undo loop buffer; initialized by `c0139b50`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:54` |
| `0xc01834ac` | 4 B ptr | **Static SDRAM Looper Base Global**: Holds `0xc04abff0`; read by initialization routine `c0139ae8`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:49` |
| `*+B14[108]` (`c0184e00 + 0xd8`) | 2 B uint16 | **Looper Transport State / Flags**: Active transport state (0 = stopped, 1 = play/resume, 4 = recording active, 5 = armed/starting, 6 = stopping/resetting, 0x100 = state guard); manipulated by `c013b164`, `c013b1f4`, `c013b220`, `c013b244`, `c013b280`. | confirmed | `recon/map/chunk_07.md:200,209`; `recon/map/chunk_08.md:17-21,205` |
| `*+B14[109]` (`c0184e00 + 0xda`) | 2 B uint16 | **Looper Mirror Transport State**: Shadow copy of previous transport state. | likely | `recon/map/chunk_08.md:65,205` |
| `*+B14[110]` (`c0184e00 + 0xdc`) | 2 B uint16 | **Looper Mode / Snapshot Flags**: Snapshots flags for mode gating (states 0, 4, 5, 8). | confirmed | `recon/map/chunk_07.md:169,173,200`; `recon/map/chunk_08.md:19` |
| `*+B14[76]` (`c0184e00 + 0x4c`) | 1 B uint8 | **Transport Update Latch**: Reset to 0 by `c013b184` on transition from state 5 to 6. | confirmed | `recon/map/chunk_07.md:179` |
| `*+B14[172]` (`c0184e00 + 0x2b0`) | 4 B object ptr | **LooperUI Event Queue / Mailbox**: Event mailbox handle read by `c013abc8` (`looper_event_receive`) and drained by `c013b108` (`looper_event_drain`). | likely | `recon/map/chunk_07.md:168,178,201` |
| `*+B14[59]`, `*+B14[111]` | 1 B / 2 B | **Looper Transport Status Latches**: Tested and set by `c015d5c0..c015d7c0`. | likely | `recon/map/chunk_15.md:236` |

#### B. Buffers
| Buffer Name / Location | Base Address | Size | Format / Structure | Role & Lifecycle | Confidence | Source File & Line |
|---|---|---|---|---|---|---|
| **SDRAM Primary Loop Arena** | `0xc04abff0` | `0x2b1100` B (~2.82 MB, ~32 sec) | 16-bit signed PCM (`int16_t` mono, 44.1 kHz) | Main looper circular recording/playback storage. Read via `LDH.D1T1 *+A3[0]` at `118167dc`, written via `STH` at `1181677c`. Offset advanced by `+2` bytes per sample. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:48-55`; `docs/helpers/DRUMS_LOOPER_BRIEF_2026-10-17.md:38` |
| **Mono Recording Capture Staging** | `0x11f03730` & `0x11f03770` | 64 B each (16 samples) | Dual-mono 32-bit signed int (`int32_t[16]`) | First loop of `118164c0` (`118165c4..11816676`) converts float inputs from `11f037b0`/`11f037f0` to int32 in `11f03730`/`11f03770`, then sums them `(L>>1) + (R>>1)` at `118166d4..118166f4` to produce mono recording input to SDRAM. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:17-18,55` |
| **Per-Block Isolated Playback Stack (int32)** | `B15 + 8` (`SP + 8`) | 64 B (16 samples) | 32-bit signed mono int (`int32_t[16]`, Q31, post-volume ramp) | SDRAM playback loop in `118164c0` (`118166d0..11816d24`) writes 16 scaled playback samples sequentially to `*B12++[1]` where `B12 = B15 + 8` (`11816d18 STW.D2T2 B7,*B12++[1]`). Intact at `11816cf0`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:57-62,130-131,164,188` |
| **Per-Block Isolated Playback Stack (float)** | `B15 + 72` (`SP + 72`) | 64 B (16 samples) | 32-bit mono float (`float[16]`, `[-1.0, +1.0)`) | Converted from `B15 + 8` via `INTSP` × $2^{-31}$ (`0x30000000`) and stored to `*A17++[1]` (`A17 = B15 + 72`) at `11816db0..11816ed0`. Intact from `11816e34` until epilogue `11816f28`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:63,131,165,188` |
| **Output Mix Bus Destination** | `0x11f037b0` (L) & `0x11f037f0` (R) | 64 B each (16 samples) | Planar stereo float (`float[2][16]`) | `118164c0` mixing loop (`11816d40..11816f54`) adds the mono playback samples from `B15 + 72` identically to both Left `11f037b0` and Right `11f037f0` via `ADDSP` (`11816db8..11816e1c`). | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:18,63-73,135` |

#### C. Audio-Path Hooks
- **DSP Engine Entry (`118164c0`)**: Resides in L2 SRAM (`0x118164c0..0x11816f54`, 2,708 bytes). Performs input clamping, mono conversion, SDRAM read/write circular addressing, level scaling, and float re-conversion and summing into `11f037b0`/`11f037f0` (`docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:14-18`).
- **Audio Swi Dispatcher (`11818e60`)**: In L2 SRAM. Loads `11f03ed0[A4]` and executes `B.S2X A0` (`11818e6c..11818e70`).
- **Swi Call Points in `11818ba0`**:
  - **Step 6 (`0x11818bc0`)**: `CALLP 0x11818e60` with `A4 = 0` (Pre-effects mode). Looper playback enters *before* Slot 0 and is processed by the effect chain (`docs/helpers/SLOT_TAP_ARGON_2026-10-17.md:133-134,261`).
  - **Step 14 (`0x11818c50`)**: `CALLP 0x11818e60` with `A4 = 1` (Post-effects mode). Looper playback enters *after* Slot 4 and master EQ, before Drums (Step 15) and Master Output Stage (`docs/helpers/SLOT_TAP_ARGON_2026-10-17.md:262-263`).
- **USB Audio Stem Tap Hook**: In `--stems` firmware (`tools/make_usb_audio_fw.py`), the `ua_looper_tap(pos)` veneer is installed at `11818e84..11818e90` (dead padding after `BNOP` at `11818e80`), retargeting both `CALLP 11818e60` calls. Computes `stem += bus_after - bus_before` on the Left channel to extract the pure looper signal onto USB Audio channel 8 (`docs/CF_USB_MODE_2026-10-16.md:481,491-494`; `tools/ua_channels_stems.json:ch8`).

#### D. UI / Task Entry Points
- **`c013b38c` (`LooperUI` Task Entry / `looper_event_table_dispatch`)**: Main event pump task for Looper. Receives event code from queue via `c013abc0(A4=-1)`. If code > 20, tail-calls `event_dispatch_108_109` (`c013b590`); otherwise dispatches via 21-entry function pointer table at `0xc0183fcc[code]` (`docs/FIRMWARE_MAP.md:66`; `docs/helpers/FWMAP.md:24`; `recon/map/chunk_08.md:46,201`).
- **`c013abc0` (`looper_event_receive`)**: Receives an event byte from mailbox `B14[172]`, returning default 22 if queue empty (`recon/map/chunk_07.md:168`).
- **`c013ac04` (`looper_record_action_dispatch`)**: Dispatches record/capture transitions based on looper flags and mode (`recon/map/chunk_07.md:169`).
- **`c013ad78` (`looper_play_action_dispatch`)**: State-dependent play/resume transitions (`recon/map/chunk_07.md:170`).
- **`c013ae48` (`looper_stop_reset_dispatch`)**: Transport stop and reset handler (`recon/map/chunk_07.md:171`).
- **`c013af08` (`looper_stop_action_dispatch`)**: Action resolver for stop/reset (`recon/map/chunk_07.md:174`).
- **`c013b064` / `c013b080`**: `looper_transition_set_bit1` and `looper_transition_mode2` (`recon/map/chunk_07.md:175-176`).
- **`c013b098` (`looper_transition_guard_dispatch`)**: Gates stop and mode transitions using state masks (`recon/map/chunk_07.md:177`).
- **`c013b104` (`looper_event_drain`)**: Drains and discards all pending events in `B14[172]` (`recon/map/chunk_07.md:178`).
- **`c013b164` (`looper_state5_to6`)**: Transitions state from 5 to 6, clears `B14[76]`, resets transport ramps via `c01398f4` (`recon/map/chunk_07.md:179`).
- **`c013b194` (`looper_state4_transition`)**: State 4 transitions (`recon/map/chunk_07.md:180`).
- **`c013b1d4` (`looper_start_if_state5`)**: Gated transport start in state 5 (`recon/map/chunk_07.md:181`).
- **`c013b1f4` / `c013b220` / `c013b244` / `c013b280`**: State guards (`looper_state_guard_5714`, `looper_state_guard_5700`, `looper_state_guard_multi`, `looper_state_guard_dispatch1`) enforcing state checks before calling transport helpers (`recon/map/chunk_08.md:17-20`).
- **`c013b2a0` / `c013b2e8`**: `looper_transport_classify` and `looper_transport_dispatch` (`recon/map/chunk_08.md:21,45`).
- **`c013b590` (`event_dispatch_108_109`)**: Common event exit dispatcher reached by all 21 table slots (`recon/map/chunk_08.md:64`).

#### E. Pattern / Tempo / Control Tables
- **LooperUI Button Event Jump Table (`0xc0183fcc..0xc0184020`)**: 21-entry word array (`0..20`) mapping event codes to handlers: `c013b578` (slot 0), `c013b558` (1), `c013b540` (2), `c013b524` (3), `c013b508` (4), `c013b4ec` (5), `c013b4d0` (6), `c013b4b4` (7), `c013b498` (8), `c013b480` (9), `c013b464` (10), `c013b444` (11), `c013b424` (12), `c013b404` (13), `c013b3fa` (14), `c013b3e4` (15), `c013b3b8` (16) (`recon/map/chunk_08.md:46-64,201`).
- **Looper Arena Global Init Sequence**: `c0139ae0..c0139b6c` dereferences pointer table entry at `c01834ac` to bind `c011aca8..c011acc0` (`docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:49-55`).
- **UI Mode Predicates**: `c0150340` (`mode_is_looper_pred`) returns 1 if mode index == 1 (Looper mode); `c0150588` (`ui_loop_rhythm_row_render`) renders looper/rhythm settings rows (`recon/map/chunk_12.md:42,49`).

## Answers

## Not checked / open leads
