# FW R&D F9: Looper and Drum Machine Prior Knowledge Citation Index

## Status
done

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

---

### 2. Drum Machine / Rhythm Subsystem Prior Knowledge

This section compiles all previously verified facts, addresses, buffers, hooks, tasks, and pattern/tempo tables for the G1 Four / G1X Four Drum Machine (Rhythm) engine.

#### A. State Variables
| Address / Register | Size & Type | Meaning / Role | Confidence | Source File & Line |
|---|---|---|---|---|
| `0x11f03d54` | 4 B uint32 | **Rhythm Enable / Active Flag**: `1` = rhythm running/on, `0` = rhythm stopped/off. Set by `c0158d98`, cleared by `c0158dac`. Tested at `11817644`/`1181766c` by `11817640`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:80`; `docs/CF_USB_MODE_2026-10-16.md:479`; `recon/map/chunk_14.md:c0158d98,c0158dac` |
| `0x11f03d58..0x11f03d78` | 9 × 4 B (36 B) uint32 array | **9-Voice Trigger / Active State Array**: `11f03d58[v]` (`v=0..8`) holds trigger/active state for drum voice `v`. Written by `c0158c30`, checked by `11817550` in PCM sample fetcher `11817520`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:85`; `recon/map/chunk_14.md:c0158c30` |
| `0xc0183840..0xc0183860` | 9 × 4 B (36 B) ptr array | **9-Voice Current Sample Read Pointers**: `c0183840[v]` (`v=0..8`) tracks current byte address in sample ROM for voice `v`. Advanced by `+2` bytes/sample (`+32` bytes/block) at `1181758c`/`118175a4`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:85-86` |
| `0xc0183424..0xc0183468` | 9 × 8 B (72 B) struct array | **9-Voice Sample Descriptor Table**: `c0183424 + 8*v` holds `{start_ptr, byte_length}` for voice `v`. Points into sample ROM `0xc075d0f0`. Initialized by `c015f4b8..c015f5e0`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:85` |
| `0x11f03d24..0x11f03d48` | 9 × 4 B (36 B) float/int array | **9-Voice Pan / Gain Coefficients**: Per-voice pan and volume scalers. Written by `c0158c20`, read by `118176ec`/`11817740`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:100`; `recon/map/chunk_14.md:c0158c20` |
| `0x11f03d1c` | 4 B float | **Rhythm Master Output Gain Cell**: Multiplier applied to stereo drum mix before adding to audio bus (`A18 = 11f03d54 - 0x48 + 0x38 - 0x24 - 4`, at `118176ec`/`11817718`/`11817720`/`11817740`, multiplied at `118178b0`/`118178d0`). | confirmed | `docs/CF_USB_MODE_2026-10-16.md:476-477,480` |
| `0x11f03d08` | 4 B float | **Rhythm Mute / Pass Multiplier**: `1.0f` when unmuted, `0.0f` when muted; multiplied at `118178a4`/`118178bc`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:137-139` |
| `0x11f03d0c` | 4 B float | **Rhythm Level Setting Raw Gain**: Read by `c0158c44`, initialized to float `0x44306666` (~706.0f) by `c0158c84`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:100`; `recon/map/chunk_14.md:c0158c44,c0158c84` |
| `0x11f03d14` | 4 B float | **Rhythm Field Level Ramp**: Level smoother cell; initialized to float `0x44306666` by `c0158cd0`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:100`; `recon/map/chunk_14.md:c0158cd0` |
| `0x11f03d20` | 4 B float | **Rhythm Level Scaler Cell**: Scaler read by `B18[0]` in `11817838`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:100` |
| `0x11812f78` | 4 B uint32 | **System BPM / Tempo Setting**: Range `40..250`, default `120`. Stored at struct offset `+0x04` in persisted system settings block `0x11812f74`. Schema record 1 at `c0182408`. Getter `11805e64`, setter `11805bf8`. | confirmed | `docs/helpers/MENU_RE_ARGON_2026-10-16.md:196-205` |
| `0x118133b4` | 1 B uint8 | **Transport Run Flag Byte**: Set to `1` by `c0167400` `transport_run_flag_set`, cleared to `0` by `c0167478` `transport_run_flag_clear`, queried by `c01674b8` `transport_run_flag_get` (called by `c013ad54`) and `11809f54` `RepeatEventHandler`. | likely | `recon/map/chunk_16.md:164,168` |
| `0x118133bc` | 4 B uint32 | **Rhythm Clock Word / Beat Accumulator**: Software beat accumulator; queried by `1180a070` `rhythm_clock_word_bc_get`, updated by `c0167410` `transport_timing_sub`. | likely | `recon/map/chunk_01.md:121`; `recon/map/chunk_16.md:165` |
| `0xc011ada6` | 1 B uint8 | **Pattern / Category Index**: Active rhythm pattern index; cleared by `c0153f24`, checked by `c01540e4`. | confirmed | `recon/map/chunk_13.md:c0153f24,c01540e4` |
| `0xc011ada7` | 1 B uint8 | **Rhythm State Byte A**: Queried by `c0153f00`, cleared by `c0153f24`. | confirmed | `recon/map/chunk_13.md:c0153f00` |
| `0xc011ada8` | 1 B uint8 | **Rhythm State Byte B**: Cleared by `c0153f24`. | confirmed | `recon/map/chunk_13.md:c0153f24` |
| `0xc011ada9` | 1 B uint8 | **Pattern Active / Transport Running Flag**: `1` = running, `0` = stopped; checked by `c0154180`, cleared by `c0153fbc`, `c0153fe8`. | confirmed | `recon/map/chunk_13.md:c0153fbc,c0153fe8,c0154180` |
| `0xc011adaa` | 1 B uint8 | **Rhythm Event Latch Byte**: Set by `c015414c`, cleared by `c0153f44`. | confirmed | `recon/map/chunk_13.md:c015414c` |
| `0xc011adad` | 1 B uint8 | **Rhythm State Byte C**: Queried by `c0153f0c`, cleared by `c0153f24`. | confirmed | `recon/map/chunk_13.md:c0153f0c` |
| `*+B14[184]` (`c0184e00 + 0x2e0`) | 4 B uint32 | **Rhythm Render-Active Flag**: Written by `c0153f18`, bit 31 tested by `c0158df8`. | confirmed | `recon/map/chunk_13.md:c0153f18,c0158df8` |
| `*+B14[208]` (`c0184e00 + 0x340`) | 1 B uint8 | **Rhythm Render Flag A**: `1` on start `c0153fa8`/`c0153fbc`, `0` on stop `c0153fe8`. | confirmed | `recon/map/chunk_13.md:c0153fa8,c0153fe8` |
| `*+B14[209]` (`c0184e00 + 0x344`) | 1 B uint8 | **Rhythm Render Flag B**: `0` on start `c0153fa8`/`c0153fbc`, `1` on `c0154020`, `0` on stop `c0153fe8`. | confirmed | `recon/map/chunk_13.md:c0153fa8,c0154020` |
| `0x1181191c` | 2 B uint16 | **Configured Pattern Count**: Fetched by `c0156488` via `1181191c`/`c0140258`. | confirmed | `recon/map/chunk_13.md:c0156488` |

#### B. Buffers
| Buffer Name / Location | Base Address | Size | Format / Structure | Role & Lifecycle | Confidence | Source File & Line |
|---|---|---|---|---|---|---|
| **Raw 9-Voice PCM Buffer** | `0x11f039b0..0x11f03acf` | 288 B (9 × 32 B) | Planar signed 16-bit PCM (`int16_t[9][16]`) | Populated every block by `11817520`. Each voice occupies 32 bytes (16 samples). Remains intact at TX pack time `11818c64` because nothing overwrites it after `11817640`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:86-87,134,189` |
| **Drum Sample ROM** | `0xc075d0f0` | Variable | 16-bit linear PCM | ROM-resident sample library referenced by descriptor table `c0183424`. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:85` |
| **Output Mix Bus Destination** | `0x11f037b0` (L) & `0x11f037f0` (R) | 64 B each (16 samples) | Planar stereo float (`float[2][16]`) | Panned stereo drum mix is added in place at `11817878` (L) and `11817898` (R) into the active effect/looper bus before master output scaling. | confirmed | `docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:22,100-114` |

#### C. Audio-Path Hooks
- **Audio Swi Call Point**: Swi Step 15 at `0x11818c54` executes `CALLP.S2 0x11818d60,B3` (`docs/helpers/DRUMS_LOOPER_ARGON_2026-10-17.md:22,79`).
- **Drum Mixer Invocation (`11818d64`)**: First instruction of `11818d60` is `CALLP.S2 0x11817640,B3`.
- **Drum Engine Pipeline (`11817640`)**:
  1. Checks enable flag `*(0x11f03d54)`. If zero, skips processing and returns immediately (`1181766c..118176d8`).
  2. If non-zero, branches to `11817520` (9-voice sample fetcher), which populates `11f039b0..11f03acf` from sample ROM `c075d0f0` (`11817694`).
  3. Executes stereo panner and accumulator loop (`118176e8..11817934`): loads 9 voices from `11f039b0` with 32-byte stride, scales by pan/gain cells `11f03d24..11f03d48`, converts to float (`INTSP` × $2^{-31}$), and adds directly into `11f037b0[i]` (`11817878`) and `11f037f0[i]` (`11817898`).
  4. Multiplies by master rhythm gain `11f03d1c` (`118178b0`/`118178d0`).
- **USB Audio Stem Tap Hook**: In `--stems` firmware (`tools/make_usb_audio_fw.py`), veneer `ua_drums_tap` at `11818d4c..11818d58` replaces `CALLP 11818d64`. Saves `11f037b0`/`11f037f0`, zeroes them, runs stock mixer `11817640` to render isolated stereo drums, copies drums to USB channels 5-6, and restores `bus = saved + stem` (`docs/CF_USB_MODE_2026-10-16.md:479-490`; `tools/ua_channels_stems.json:ch5-6`).

#### D. UI / Task Entry Points
- **`c016aac0` (`RhythmService` Task Entry / `event_flag_pump`)**: Dedicated OS task entry for drum machine; drains pending-event bitmask from `B14[165]` via `c0144580` (`docs/FIRMWARE_MAP.md:65`; `docs/helpers/FWMAP.md:24`; `recon/map/chunk_17.md:41`).
- **`11806ce0` (`rhythm_ui_update_dispatch`)**: 468-byte dispatcher linking RhythmService, MIDI, and MainApp (`recon/map/chunk_00.md:198`).
- **`11806eb4` (`rhythm_playback_step`)**: 600-byte RhythmService playback routine (`recon/map/chunk_00.md:199`).
- **`11809f00` (`rhythm_clock_accumulate`)**: Software beat clock driven by hardware timer (`recon/map/chunk_01.md:120`).
- **`1180a0a0` (`ui_rhythm_display_by_mode`)**: Selects rhythm display based on current mode (`recon/map/chunk_01.md:123`).
- **`c0150844` / `c015096c` (`rhythm_popup_open_and_notify` / `rhythm_menu_popup_open_flagged`)**: Opens rhythm menu popup (`recon/map/chunk_12.md`).
- **`c015402c` (`rhythm_pattern_update_step`)**: Steps pattern state; reads event queue results (`recon/map/chunk_13.md:c015402c`).
- **`c015408c` (`rhythm_pattern_field_copy`)**: Copies pattern fields after fetching queue data (`recon/map/chunk_13.md:c015408c`).
- **`c0154180` (`rhythm_transport_step`)**: Steps transport when `ada9` flag is set (`recon/map/chunk_13.md:c0154180`).
- **`c0156430` / `c0156478` (`rhythm_menu_item_render` / `rhythm_menu_item_render_dispatch`)**: Renders rhythm menu items (`recon/map/chunk_13.md:c0156430,c0156478`).
- **`c01565b8` / `c0156648` / `c0156660` (`rhythm_pattern_menu_draw`, `rhythm_pattern_menu_entry_a/b`)**: Top-level pattern-selection menu render cluster (`recon/map/chunk_13.md:c01565b8..c0156660`).
- **`c0158dc0` (`rhythm_ui_update_dispatch_gated`)**: Synchronized UI update gated by semaphore `B14[155]` (`recon/map/chunk_14.md:c0158dc0`).
- **`c0158df8` / `c0158e4c` / `c0158e8c`**: Gated and unconditional UI refresh helpers (`recon/map/chunk_14.md`).

#### E. Pattern / Tempo Tables
- **Rhythm Patterns Descriptor Table (`0xc0182730`)**: RAM-resident table filled at boot holding descriptors for all 68 built-in patterns. Read by `c01661ac` (`rhythm_pattern_table_get`), `c0166194` (`rhythm_get_field117`), `c0166180` (`rhythm_get_field118`), `c0166258` (`rhythm_get_field119`), `c015408c` / `c0158c58` (`docs/helpers/FWMAP.md:28`; `recon/map/00_library_kernel.md:128,374`; `recon/map/chunk_13.md:169`; `recon/map/chunk_16.md:129-133`).
  - **Record Structure per Pattern `A4`**:
    - `table_c0182730[A4] + 117` (`0x75`): Beats per measure (`3`, `4`, `5`, `6`, `8`, `12`).
    - `table_c0182730[A4] + 118` (`0x76`): Beat unit / note value (`4` for quarter notes, `8` for eighth notes).
    - `table_c0182730[A4] + 119` (`0x77`): Pattern flags / render mode byte.
- **Time-Signature Word Table**: Decoded by `c01661b8` (`rhythm_timesig_word_get`) mapping `[118]` and `[117]` to meter configuration words:
  - `0xc0183960`: 3/4
  - `0xc0183964`: 4/4 (standard default)
  - `0xc0183968`: 5/4
  - `0xc018396c`: 6/8
  - `0xc0183970`: 8/8
  - `0xc0183974`: 12/8
  (`recon/map/chunk_16.md:132`).
- **Rhythm Field Dispatch Table (`0xc0183f6c..0xc0183fc8`)**: Jump table dispatching tempo/pattern edits:
  - `c0149556` -> `c0149180` (`rhythm_tempo_scale_apply_locked`)
  - `c014958a` -> `c01492ac` (`rhythm_tempo_field_apply_locked`)
  - `c0149592` -> `c01493a8` (`rhythm_tap_tempo_update`)
  - `c014959a` -> `c0149434` (`rhythm_midi_tempo_apply`)
  (`recon/map/chunk_10.md:149-169,191`).
- **Pattern Variant Setter Table (`0xc0184020..0xc0184038`)**: 7-entry function pointer table calling `c0153654..c0153722` (`recon/map/chunk_13.md:c0153654..c0153722`).
- **System Settings BPM Schema Record (`0xc0182408`)**: Record 1 in schema table `0xc01823f8..0xc0182598`. Validates BPM range `40..250` with default `120` (`docs/helpers/MENU_RE_ARGON_2026-10-16.md:197,205`).

---

### 3. Telemetry Watch List v1

This table specifies exactly 32 high-value runtime variables suitable for live streaming over USB MIDI SysEx probe packets or real-time USB audio telemetry frames.

| Index | Target Address | Size & Type | Name / Field | Expected Value Range | Telemetry Rationale |
|---|---|---|---|---|---|
| **1** | `0x11f03c58` | 4 B uint32 | `looper_active` | `0` (bypassed) or `1` (active) | Immediate verification of looper DSP engine engagement |
| **2** | `0x11f03c54` | 4 B float | `looper_fade` | `0.0f` to `1.0f` | Tracks stop/fade-out envelope transitions |
| **3** | `0x11f03e38` | 4 B float | `looper_vol_ramp` | `0.0f` to `1.0f` | Active playback level after smoothing |
| **4** | `0x11f03c64` | 4 B float | `looper_vol_target` | `0.0f` to `1.0f` | Target looper playback level from UI/SysEx |
| **5** | `0x11f03cd8` | 4 B uint32 | `looper_vol_param` | `0` to `100` | Raw knob/setting value for looper level |
| **6** | `0x11f03ed0` | 4 B ptr | `looper_ptr_pre` | `0xc016d180` (idle) or `0x118164c0` (active) | Confirms whether Pre-effects looper hook is active |
| **7** | `0x11f03ed4` | 4 B ptr | `looper_ptr_post` | `0xc016d180` (idle) or `0x118164c0` (active) | Confirms whether Post-effects looper hook is active |
| **8** | `0xc011aca8` | 4 B ptr | `looper_arena_base` | `0xc04abff0` (fixed) | Verifies base SDRAM allocation pointer integrity |
| **9** | `0xc011acac` | 4 B ptr | `looper_arena_end` | `0xc04d7100` (fixed) | Verifies allocated loop capacity boundary |
| **10** | `0xc011acb0` | 4 B uint32 | `looper_capacity` | `0x0002b110` (~32 s) | Declared loop length capacity |
| **11** | `0xc011acb4` | 4 B ptr | `looper_write_ptr` | `0xc04abff0` .. `0xc04d7100` | Real-time circular record position in SDRAM |
| **12** | `0xc011acc0` | 4 B ptr | `looper_undo_ptr` | `0xc04abff0` .. `0xc0500000` | Real-time undo/secondary buffer pointer |
| **13** | `0xc0184fb0` | 2 B uint16 | `looper_transport_state` | `0` (stop), `1` (play), `4` (rec), `5` (arm), `6` (trans) | Tracks internal state machine transitions (`B14[108]`) |
| **14** | `0xc0184fb4` | 2 B uint16 | `looper_transport_mirror` | `0` .. `6` | Prior transport state (`B14[109]`) |
| **15** | `0xc0184fb8` | 2 B uint16 | `looper_transport_flags` | `0` .. `0x0100` | Mode/guard bitflags (`B14[110]`) |
| **16** | `0x11f03d54` | 4 B uint32 | `rhythm_active` | `0` (stopped) or `1` (running) | Immediate check of drum machine DSP playback |
| **17** | `0x11f03d1c` | 4 B float | `rhythm_gain_master` | `0.0f` to `2.0f` (nominal `1.0f`) | Rhythm master multiplier applied to stereo drum mix |
| **18** | `0x11f03d08` | 4 B float | `rhythm_mute_mult` | `0.0f` (muted) or `1.0f` (unmuted) | Rhythm mute state multiplier |
| **19** | `0x11f03d0c` | 4 B float | `rhythm_level_raw` | `0.0f` to `1000.0f` (default `0x44306666`) | Raw drum volume level cell |
| **20** | `0x11f03d14` | 4 B float | `rhythm_level_ramp` | `0.0f` to `1000.0f` (default `0x44306666`) | Smoothed drum volume level cell |
| **21** | `0x11f03d58` | 4 B uint32 | `drum_voice0_active` | `0` (idle) or `1` (playing) | Trigger status of Kick/Voice 0 |
| **22** | `0x11f03d5c` | 4 B uint32 | `drum_voice1_active` | `0` (idle) or `1` (playing) | Trigger status of Snare/Voice 1 |
| **23** | `0x11f03d60` | 4 B uint32 | `drum_voice2_active` | `0` (idle) or `1` (playing) | Trigger status of Hi-Hat/Voice 2 |
| **24** | `0x11812f78` | 4 B uint32 | `system_bpm` | `40` to `250` (default `120`) | Active global tempo in BPM |
| **25** | `0x118133b4` | 1 B uint8 | `transport_run_flag` | `0` (stopped) or `1` (running) | Global transport run flag |
| **26** | `0x118133bc` | 4 B uint32 | `rhythm_clock_word` | `0` .. `0xffffffff` | Beat clock tick accumulator |
| **27** | `0xc011ada6` | 1 B uint8 | `rhythm_pattern_idx` | `0` to `67` | Currently selected rhythm pattern index |
| **28** | `0xc011ada9` | 1 B uint8 | `rhythm_running_flag` | `0` (stopped) or `1` (running) | UI/Service pattern-active flag |
| **29** | `0x1181191c` | 2 B uint16 | `rhythm_pattern_count` | `68` | Total pattern count reported by firmware configuration |
| **30** | `0x11f03e34` | 4 B float | `audio_master_gain` | `0.0f` to `2.0f` (nominal `1.0f`) | Swi Step 15 master volume multiplier |
| **31** | `0x11812f74` | 4 B uint32 | `system_mvol` | `0` to `120` (default `100`) | Global Master Volume setting (MVOL) |
| **32** | `0x1180312c` | 4 B uint32 | `system_mute_mask` | `0` (unmuted) or `0x80000000` (muted) | Master mute/reload flag bitmask |

---

## Answers

### Summary for Brief 5 (Job F9)
1. **Looper Subsystem**:
   - **State Variables**: Function pointer dispatch table at `0x11f03ed0` (`11f03ed0[0]` Pre, `11f03ed0[1]` Post); bypass flag `0x11f03c58`; fade multiplier `0x11f03c54`; volume ramps and cells `0x11f03e38`, `0x11f03c64`, `0x11f03cd8`; SDRAM arena pointers `0xc011aca8..0xc011acc0` and static global `0xc01834ac`; transport state machine variables `*+B14[108]`, `[109]`, `[110]`, `[76]`, and queue handle `B14[172]`.
   - **Buffers**: Circular SDRAM buffer at `0xc04abff0` (size `0x2b1100` B, ~32 s 16-bit 44.1 kHz mono PCM); dual-mono input capture at `11f03730`/`11f03770`; isolated playback stack buffers at `B15 + 8` (`int32_t[16]`) and `B15 + 72` (`float[16]`); summed output mix bus at `11f037b0` (L) and `11f037f0` (R).
   - **Audio-Path Hooks**: DSP engine `118164c0` called via dispatcher `11818e60` at Step 6 (`11818bc0`, Pre) or Step 14 (`11818c50`, Post); USB stem tap installed via padding veneer `11818e84..11818e90`.
   - **UI / Task Entry Points**: `LooperUI` task entry `c013b38c`; event receiver `c013abc0`; action dispatchers `c013ac04`, `c013ad78`, `c013ae48`, `c013af08`; state guards `c013b1f4..c013b280`.
   - **Tables**: 21-entry button jump table at `0xc0183fcc..0xc0184020`.

2. **Drum Machine / Rhythm Subsystem**:
   - **State Variables**: Rhythm enable flag `0x11f03d54`; 9-voice trigger array `0x11f03d58..0x11f03d78`; 9-voice read pointers `0xc0183840..0xc0183860` and sample descriptors `0xc0183424..0xc0183468`; per-voice pan/gain `0x11f03d24..0x11f03d48`; master gain cell `0x11f03d1c`; mute multiplier `0x11f03d08`; level ramps `0x11f03d0c`, `0x11f03d14`, `0x11f03d20`; global BPM at `0x11812f78`; transport flag `0x118133b4` and clock word `0x118133bc`; UI state block `0xc011ada4..0xc011adad`; render flags `B14[184]`, `[208]`, `[209]`.
   - **Buffers**: Planar 9-voice raw PCM buffer at `0x11f039b0..0x11f03acf` (288 B); sample ROM at `0xc075d0f0`; stereo output bus at `11f037b0` (L) and `11f037f0` (R).
   - **Audio-Path Hooks**: Swi Step 15 `11818c54` calls `11818d60`, which calls mixer `11817640` at `11818d64`; USB stem tap installed via padding veneer `11818d4c..11818d58`.
   - **UI / Task Entry Points**: `RhythmService` task entry `c016aac0`; dispatchers `11806ce0`, `11806eb4`, `11809f00`, `1180a0a0`; menu handlers `c0150844`, `c015402c`, `c0154180`, `c0156430`, `c01565b8..c0156660`, `c0158dc0`.
   - **Tables**: 68-pattern descriptor table at `0xc0182730` (beats per bar at offset 117, beat unit at offset 118, flags at 119); time-signature lookup words `0xc0183960..0xc0183974`; dispatch table `0xc0183f6c..0xc0183fc8`; variant setters `0xc0184020..0xc0184038`; BPM schema record `0xc0182408`.

3. **Telemetry Watch List v1**:
   - 32 prioritized live streamable addresses compiled in Section 3, spanning looper state machine flags, buffer pointers, volume ramps, drum voice triggers, global tempo, transport accumulators, and master levels, with explicit expected ranges.

---

## Not checked / open leads
- Internal binary layouts of individual drum sample PCM waveforms inside sample ROM `0xc075d0f0` (start offsets and lengths are known via descriptor table `c0183424`, but raw sample rates, loop points, and compression format if any were not examined).
- Exact event payload encoding passed inside mailbox `B14[172]` from the footswitch/pad drivers into `LooperUI` (`c013abc0`).
- Detailed bitmask definitions of `*+B14[110]` beyond the tested state masks `{0, 4, 5, 8}`.
- Telemetry streaming packet transport protocol: whether watch list v1 addresses will be polled over USB MIDI SysEx queries (e.g. `F0 52 00 6e <cmd> <addr> <len> F7`) or packed into high-speed USB audio frames on unused channels.
