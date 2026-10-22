# Firmware R&D answers, 2026-10-22 (for the 2026-10-23 deep work)

Answers to the 8 questions in `HANDOFF_2026-10-22_FW_RND.md`. Static
analysis only. Helper reports (with full evidence) in `docs/helpers/`:
F1 citation digest `FW_RND_DIGEST_FLASH_2026-10-22.md`, F2 ZD2 survey
`FW_RND_ZD2_SURVEY_FLASH_2026-10-22.md` (script `build/fw_rnd/F2/zd2_survey.py`),
S1 `FW_RND_S1_LIST_PARAMS`, S2 `FW_RND_S2_LOADER_ALLOC`, S3 `FW_RND_S3_SWI`,
S4 `FW_RND_S4_FAULT`, S5 `FW_RND_S5_MENU` (all `_2026-10-22.md`). Claude
re-checked the key instructions marked **(Claude)**.

## Address map

| what | address | confidence |
|---|---|---|
| ZD2 header validation (in `effect_slot_load_unload` c01297a0); header copied to `B15+40` | c01298d4..c012990c | confirmed (Claude) |
| target-family check: header 0x0c `AND 2` | c01298f4..c0129900 | confirmed (Claude) |
| **slot-count ceiling: header 0x58 (`*+B15[128]`) `CMPLTU 4` -> reject** | c0129904..c012990c, reject c0129b40 | confirmed (Claude) |
| size ceiling `B10 > 5<<15` (0x28000 = 160 KiB, likely file/blob size) | c01298e0..c01298f0 | likely |
| Process Overflow gate, dspload sum < 230.0f | c0141ad8..c0141b60 | confirmed (S1, matches DSP_RULES) |
| slot resource lookups by slot index (no count) | c0129734 -> c0164a8c, c0129740 -> c0164a80 | confirmed (Claude) |
| code/const heap 0xa000 per slot, table | c01839c0 (heap c01f4000 + n*0xa000) | confirmed |
| work buffer 0x81330 (529,200 B) per slot, descriptors | c0183470, c014febc (c0226000 + n*0x81330, end c04abff0) | confirmed |
| state 0x2a0 / knob table 0x348 per slot init | c014fea0, c0165e98 | confirmed |
| slot "in use" byte flags | c01839f0 | likely |
| heap allocator, out of memory -> error 7, clean refusal | c0151190 (c0151274), caller c0124368/c01242bc -> c0124578 | confirmed (S2) |
| effects' stack: shared Hwi/Swi stack | 0x118134a8..0x11816468 (12 KiB) | confirmed region, likely use |
| just below the stack: slot callback table, peripheral pointers | 0x118133e0, 0x1181329c..0x118134a4 | confirmed |
| stack monitor touching the stack's low end | c016c7ec, c016c844 | confirmed reads (recon/16 C7); role likely SYS/BIOS idle check |
| audio Swi slot loop | 11818ba0 (dispatch ~11818bec..c44) | confirmed (recon/16, chunk_19) |
| stereo bus A / B (B = A + SH_CH_B_OFFSET) | 0x11f037b0 / 0x11f037f0 | confirmed |
| TX-pack sources producer, then output ring (USB tap) | 118186e0 -> 11f038b0/11f038f0 -> 11f03630/11f036b0 | confirmed (S3) |
| param descriptor accessor (56-byte ELF param record, label at +0) | c012afe0 (pointer table 0xc0064404 + slot*36) | confirmed (S5) |
| `4*c012af98() - r` page math + row text (NOT the LCD screen: reached only from the MIDI/USB string builder 11803514 / 1180af78) | 11807eb8, 11808360, 118082f8 | confirmed callers (S5, Claude) |
| LCD effect-edit screen (knob -> name/value/page) | not found | open |
| menu screen switch / descriptor table | c0149664 / c01495c0 (0xc018413c) | confirmed (Argon 10-16) |

## Answers

### Q1. Slot limit and effect list
- **Why 5 is hidden and 2 offered: a hard ceiling of 4 at file parse,
  c0129908 `CMPLTU.L2 0x4,B0,B0; [B0] B c0129b40`.** B0 is `LDBU *+B15[128]`;
  the same block reads the header's target byte `0x0c` as `B15[13]`
  (byte +52), so the header copy starts at B15+40 and +128 is header byte
  **0x58** (Claude, from the offsets). An effect with 0x58 > 4 fails
  validation, so it never becomes a listed effect. It is a flat ceiling,
  not a check against free slots in the patch.
- **Prediction:** header 3 and 4 pass this check. The picker that filters by
  free slots (if any) was not found (S1).
- Stock corpus (F2): 0x58 is only ever 1 (82 effects) or 2 (16: 1U amps,
  Gt GEQ 7, PhaseDly, TapeEcho3). Stock 2-slot effects use the next patch
  slot as id 0x1 "second half" (recon/04:33). Our CFMPRE (2) did NOT take
  the next slot on screen; why (who writes the id 0x1 filler) is open.
- **But header N buys no resources (Q2).** Raising the ceiling only lets
  the file load; a 5-slot effect would still get one slot's code heap,
  state and work buffer.
- **Patch:** c0129908 `CMPLTU 0x4` -> `0x5` (the 5-bit constant field of one
  32-bit word; recompute the fetch-packet header if any bits shift; file
  offset per `tools/make_usb_audio_fw.py`). Risk low for the check itself;
  unknown for what a value of 5 does in the slot reservation and UI code.
  Cheaper first test, no firmware patch: build CF M3 / CF M4 (header 3 and
  4) and see whether the list offers them.

### Q2. How slot count maps to memory
- **One slot's resources, always (confirmed, three sources agree: static
  tables, the c0129734/c0129740 lookups with one scalar index, the CFM2P
  probe).** Code+const 40 KiB (0xa000) heap at c01f4000 + n*0xa000; knob/coef
  table 0x348 at 11f00000 + n*0x348; state 0x2a0 at 11f013b0 + n*0x2a0; one
  SDRAM work buffer 0x81330 (529,200 B) at c0226000 + n*0x81330. n is the
  physical slot (0..4). Nothing in the loader reads header 0x58 (S2
  searched c0122924..c0124fc0 and c01453b4..c0146e18).
- 40 KiB overflow is a **clean refusal** (allocator error 7, loader skips
  zero-fill and read), not an overrun.
- The 5 code heaps then the 5 work buffers are one contiguous SDRAM range
  c01f4000..c04abff0, so slot n+1's heap physically follows slot n's.
- **Patch to give a header-N effect N x 40 KiB:** feasible in principle but
  three tables (c01839c0 heap, c014fea0/c0165e98 state/coef, c0183470/
  c014febc work buffers) and the in-use flags c01839f0 would have to change
  together; a partial patch lets two effects overlap silently. **High
  risk; not recommended now.** Practical route: split a chain across
  physical slots (each stage its own 40 KiB), which the CN chain does.

### Q3. Per-effect limits
- **40 KiB:** the fixed 0xa000 per-slot heap (Q2). Not per-effect configurable.
- **12 params: not a firmware constant (S1 found none).** It comes from the
  patch record: the EDTB slot entry is 24 bytes with 12 packed fields
  `[12,12,12,12,12,8,8,8,12,12,12,12]` bits (`tools/g1presets.py:26`) and
  the stomphacks maximum. More than 12 would change the patch format:
  not patchable without breaking patch storage. Note params 6-8 are only
  8 bits (max 255).
- **Params per page: the LCD code that sets it is not located.** The
  `4*c012af98() - r` function at 11807eb8 (named fxparam_page_size in
  chunk_01) is only reached from the MIDI/USB string builder (callers
  11807f0e, 1180af78 -> 11803514; fact sheets call the cluster
  `usbstr_builder*`), so it is not the screen layout (S5, Claude checked
  the callers). Hard facts are the stock corpus (F2, checked by Claude):
  1-slot effects have exactly 4 knobs, 2-slot effects exactly 9 (padded
  with `Dummy` records). Treat 4 per 1-slot effect and 9 per 2-slot effect
  as the proven-safe layouts; 12 (CFMPRE) is outside anything stock does.

### Q4. Stack
- Effects run on the **shared Hwi/Swi stack 0x118134a8..0x11816468
  (12 KiB, L2)**; the probe saw B15 = 0x11816140 inside an effect. The Swi
  path above the effect uses about 808 B, so the nominal headroom is about
  11 KiB. **The 1536 B limit in DSP_RULES is our own margin** (DR103's
  1428 B plus slack), not a firmware or toolchain rule; `allow_stack` is not
  checked by any tool.
- Overflow runs down into the **slot callback table 0x118133e0 and the
  peripheral pointer block 0x1181329c..0x118134a4**, which the Swi reads on
  its next slot call: an overflow would very likely jump to garbage, not
  just glitch.
- The firmware reads the stack's low end at c016c7ec/c016c844 (SYS/BIOS
  stack check, likely in idle): it detects an overflow afterwards, it does
  not prevent it. SYS/BIOS `E_stackOverflow` strings exist.
- RA200X's frame is **1064 B** (S4, from its ELF) — below DR103's proven
  1428 B, so stack size is not its fault.

### Q5. Fault handling (RA200X, USB crash)
- No per-slot isolation: one core, one shared stack, audio Swi (prio 15)
  above the USB Swi (prio 13); every slot's buffers are adjacent L1D/L2.
  The c64p SYS/BIOS Exception module is linked; its handler policy (halt?)
  was not traced. An effect that wedges or faults the core takes USB down
  with it; the USB driver itself is not the victim of a direct write as far
  as found (the USB tap reads the final ring, two stages after the slots).
- What is unique about RA200X (S4, compared with CE2X, Delay, DR103,
  Mistress): channel-B writes and state in instance[3] are **not** unique
  (CE2X and Delay do both safely). It is the only kernel with
  **data-dependent loop trip counts (20 loops, inlined MNA solver)** and it
  measured 14.1k cycles vs 4k expected. Ranked: (1) likely: unbounded or
  pathological solver iterations blowing the block budget, worse with more
  effects after it; (2) a fault (bad float state, e.g. NaN/denormal
  feedback, or an exception) wedging the core: plausible, not proven;
  (3) stack: rejected (1064 B); (4) ch-B overrun: rejected (bounds correct).
  "No audio" itself: guess, a numerical bug in the solver output that the
  clamp zeroes; not traced line by line.
- **Containment patch idea (S4):** in the slot dispatch loop, time each
  slot (TSCL) and auto-bypass a slot that exceeds k x its declared budget;
  optionally a guard word at the stack's low end checked after each slot.
  Cost: a few cycles per slot. Risk: insertion in hand-scheduled L2 code with
  delay slots; false positives on legitimately heavy effects. Longer-term;
  **first replace RA200X** with the simple mono rotary (handoff plan).

### Q6. Load and overflow
- **No deadline check, counter or skip logic in the audio Swi (S3 read the
  whole chunk_19 call order).** The only protection is the EDMA ping-pong:
  RX unpack / TX pack pick the inactive half by comparing the live PaRAM
  address (recon/16 C4). A late block races the DMA, so audio is torn or
  repeated with no warning; that matches 105% peaks with 0 reported lost
  frames (the USB loss counter does not see it).
- USB audio survives a short overrun (USB Swi just runs late); a sustained
  overrun starves the lower-priority USB Swi (likely the "driver crash" path
  together with Q5). The admission gate is only the declared dspload sum
  (< 230), not measured cycles.

### Q7. Display / menu
- **Labels:** each param's label is the 12-byte field at offset 0 of its
  56-byte ELF param record (11 chars + NUL), read through c012afe0 (S5,
  confirmed; matches F2's parser). Labels are per param, so "different
  labels per page" needs no firmware patch: each page shows its own params'
  labels. Stock labels are at most 8 chars (`D57:D421`); CFMPRE uses eight
  9-char labels. How many pixels / chars the effect screen shows before
  clipping: **not located** (only the Settings menu's 3x5 / 5x7 fonts and
  ~31 px columns are known). Keep labels at 8 chars or fewer until a
  hardware photo shows otherwise.
- **The LCD effect-edit draw code was not found** (S5's biggest open gap;
  the cluster earlier thought to be it is MIDI/USB, see Q3).
- **Sub-menu:** the Settings-menu mechanism is real and reusable:
  c0149664(screen_id) switches screens via the 36-byte descriptor table at
  c01495c0 / 0xc018413c; dormant screen IDs 1 and 5 sit in writable RAM
  (Argon 10-16, addresses verified by S5). Not shown to be the same system
  the effect-param screen uses, so a per-effect sub-menu (one effect
  holding a chain) is a medium-size patch with an unknown entry point.
  Lower-risk alternative: one stage per page with a stage-name param.

### Q8. Stereo bus
- One fixed bus pair, A 0x11f037b0, B 0x11f037f0 (= A + SH_CH_B_OFFSET),
  handed unchanged to slots 0..4 in order. Later slots read whatever an
  earlier slot wrote to B. A and B stay separate through 118186e0
  (clamp/filter/pack) into the output ring 11f03630/11f036b0, which is the
  USB tap point (confirmed, S3). **A mid-chain stereo write is safe for the
  plumbing**; a later mono effect that only processes A leaves B as it was
  (so a mono effect after a stereo one must either process or copy B).

## Recommended order (fits `tools/make_public_usb_audio_patch.py` /
`tools/make_usb_audio_fw.py`; main partition 0x33000 only; owner flashes)
1. **No firmware change:** replace RA200X with the leaf mono rotary
   (< 5k cycles, no stack). Re-lay out CFMPRE pages: one stage per page,
   labels of 8 chars or fewer; photograph the edit screen on the pedal to
   settle the page size and clipping (Q3/Q7).
2. **No firmware change, one test updater:** CF M3 and CF M4 probe effects
   (header 3 and 4) to confirm the c0129908 ceiling and see what the patch
   screen does with 3/4-slot effects.
3. **One-word patch:** c0129908 `CMPLTU 4` -> `5`, only if step 2 shows
   values up to 4 behave; low value on its own since resources stay at one
   slot (Q2).
4. **Diagnostic patch (test updater only):** per-slot TSCL timing written to
   a debug cell readable by the bench, to measure real per-slot cost and
   overruns (precondition for the watchdog).
5. **Watchdog / auto-bypass in the slot loop** (Q5), after step 4's numbers.
6. Multi-slot resource widening (Q2): not recommended; split chains across
   slots instead.

## Open leads
- The LCD effect-edit screen code (params per page, label font/width): not
  located (S5). Next RE target if page layout matters.
- The effect picker (what the list offers per slot) and who writes the id
  0x1 "second half" for 2-slot effects: not located (S1).
- SYS/BIOS exception handler policy and vector table: not traced (S4).
- What the B10 > 160 KiB check at c01298e6 measures.
- RA200X solver numerics (mna_ss.h): not traced line by line.
