# Handoff 2026-10-15: offline work while the pedal is away

Start here. The owner is working remotely and has **no pedal access**. All work
is offline. **DO_NOT_FLASH applies to everything:** never run an updater, never
write to the pedal. Never commit `.agents/` or `bridge/`.

Earlier context (read only if needed):
[HANDOFF_2026-10-14_LEAD.md](HANDOFF_2026-10-14_LEAD.md) (status table, continue
list) and [ROADMAP.md](ROADMAP.md).

## Baseline

- Python: `.venv/Scripts/python.exe`. Run the tests with
  `.venv/Scripts/python.exe -m pytest tests tools/test_usb_audio_proto.py -q`.
  **226 passed, 615 subtests.** Never leave the suite red.
- Lifecycle controller candidate SHA-256: `3e7f5236…28b9`. It must stay
  byte-identical; `tests/test_diag_readback.py` rebuilds it and checks the hash.
- Commit small and often, on `master`. Do not push unless the owner asks.

## Feature status

| Feature | Offline state | Next hardware step (owner) |
|---|---|---|
| USB MIDI controller (B1) | The 7-hook lifecycle build is verified. The USB abort review is complete (below). | Run the diag build first, then the MIDI test. |
| USB audio (C) | Silence candidate: two reviews; the STRING bug was fixed and review 2 found no bug. Real-audio tap candidate built (`--tap`, 17 tests). | Enumeration test after B1 passes, then the tap test. |
| Effects, 5 slots (B2/D) | CF 808/RAT/Muff/TS exist. DR103 redesigned: it fits, ~36k static. Budget very likely 132.4k cycles per block; 50.6k is busy cycles (TSCL stops in IDLE). CF ClkT is built to confirm. | Run CF ClkT (`docs/CYCLE_BUDGET_2026-10-15.md`), then a full patch. |
| Slot-0 residency (B4) | The patch is ready and hash-pinned. | Heavy-effect test. |
| Patch tool (E) | Not started. | — |

## What was done on 2026-10-15

USB abort obligations (`docs/helpers/USB_ABORT_OWNERSHIP_2026-10-14.md`), all
statically closed or narrowed:

- **TX template writers:** no instruction writes the table. The abort tail drains
  the submit queue. (`USB_TX_TEMPLATE_WRITERS_2026-10-15.md`)
- **Hwi coexistence:** every queue-25 descriptor has a single owner on every path.
  The abort most likely runs with GIE=1. (`USB_HWI_COEXISTENCE`, `USB_ABORT_ENTRY_IRQ`)
- **q25 association:** a wrong match requires a prior expired poll. All aborts
  run in the single UsbTask; op 8 is the host's CLEAR_FEATURE(HALT) on EP 0x84.
  (`USB_Q25_ASSOCIATION`, `GEMINI_OP8_REPORT`, `GEMINI_TASK_INSTANCES_REPORT`)
- **Expiry recovery:** no premature buffer reuse; the enqueue defers while
  field [5] != 0. There is one **liveness risk**: a descriptor that never
  returns stalls that slot's TX permanently. (Claude review in
  `SOL_EXPIRY_RECOVERY_REPORT.md`)
- **TX field [2]:** it selects counted or ring mode. Ring mode is dormant in stock.
  (`SOL_DIRECT_SUBMITTERS_REPORT`, `SOL_TX_MODE_REPORT` reviews)

Diagnostic build (`tools/make_controller_fw.py --diag-teardown`):

- **MIDI readback:** pressing both footswitches streams the ring, the TX outstanding
  counts and the **worker stack high-water mark** as CCs. Capture with
  `tools/capture_ctl_diag.py`, decode with `tools/decode_ctl_diag.py --cc-log`.
  Owner procedure: `docs/helpers/OWNER_DIAG_TEST_PREP_2026-10-15.md`.

USB audio silence candidate (`tools/make_usb_audio_fw.py`,
[docs/USB_AUDIO_SILENCE_CANDIDATE_2026-10-15.md](docs/USB_AUDIO_SILENCE_CANDIDATE_2026-10-15.md)):

- 11 patches plus a 2.4 KB payload at `c01a8000`. It layers on stock or on the
  controller candidate.
- The descriptors pass the strict validator `tools/uac1_validate.py`, including
  the Windows legacy grouping check (it should appear as two functions).
- Review: `docs/helpers/REVIEW_USB_AUDIO_CANDIDATE.md`, with Claude's response.

## Session 2 (2026-10-15 afternoon): queue items 1-3 done

- **1. Done.** Review 2 (Sonnet; Codex was capped): `docs/helpers/REVIEW2_USB_AUDIO_CANDIDATE.md`.
  No bug found. The Claude review corrects one claim: the callers do branch on the
  veneer's A4 (0 = success). It also adds one low RISK: nothing resets the stream
  state on SET_CONFIGURATION or bus reset.
- **2. Done.** Real-audio tap: `docs/USB_AUDIO_TAP_CANDIDATE_2026-10-15.md`,
  `make_usb_audio_fw.py --tap`. A veneer at `11818c88` (dead padding) and the CALLP at
  `11818c64` call `ua_tx_pack_tap`. The samples are recomputed from the planar inputs
  `11f038b0`/`11f038f0`. An SPSC ring feeds async 44/45 pacing by fill level. The
  silence image is byte-identical (`bfee93d1…`).
- **3. Done (static); one pedal run left.** `docs/CYCLE_BUDGET_2026-10-15.md`. Stock
  sets PDCCMD = 0x1FFFF (GEMPD) at boot. The existing DR103 and Probe data rule out a
  139.5 MHz core, so the budget is about 132.4k cycles per block. CF ClkT
  (`effects/clkt`, `build/CLKT.ZD2`) settles it: compare TSCL per block at Load 0
  and Load 50 against the 19.2 MHz TIMER64P0.
- Tests: **226 passed**.

## Session 3 (2026-10-15 evening): queue item 6, DR103 redesign done offline

`docs/DR103_REDESIGN_2026-10-15.md`.

- **Memory: it fits.** 34,640 of 40,960 slot bytes; it was 51,464.
  - The networks are derived per block by generated straight-line code
    (`tools/gen_hw_nets.py`), so the knob tables are gone.
  - `.text` 28,320 of 30,720 B; frame 1,404 B.
- **Cost: ~36k cycles per block static.** The first build measured ~224k.
  The NFB loop (~16.7k) is now most of it.
- **Sound: the 16x bench is equal or better.** Worst case 16.30 dB / -46.0 dB.
  The bench now has `rates` / `masks` variants.
- **Build:** `ZD2_TEXT_EXTRA=12288 bash tools/build_g1.sh hiwatt "CF DR103" "HIWATT/DR103"`.
- **Pedal step (owner, after CF ClkT):** DR103D cost run, then CF DR103 alone.
- Tests: 226 pytest pass. Host checks pass: netgen, kernel, ADAA, nets, accuracy.

## Offline work queue (in order)

1. **Second independent review of the USB audio candidate** (Codex Sol, medium).
   Focus on the code changed after the first review: the descriptor-veneer
   delegation (`firmware/usb_audio_proto/usb_audio_hooks.asm`), `ua_map_thunk`
   and the IF3 callback. Write a brief in `docs/helpers/`. Its output goes to
   `docs/helpers/REVIEW2_USB_AUDIO_CANDIDATE.md`.
2. **Real-audio tap (ROADMAP C3, recon/21 S1).** Design and build, offline:
   - Copy the finished 128-byte TX half (`11818c64` / `11818aa0`; buffers
     `11f03630` / `11f036b0`) into a bounded ring.
   - Have the SOF tick send 44/45 frames from it, with underrun counting and no spin.
   - Extend the host harness tests first. Keep the silence build reproducible.
   - Open issues: the codec-to-USB clock drift policy, and the conversion from
     32-bit samples to 16-bit.
3. **Cycle-budget discrepancy (Phase D blocker).** CF MuffT measured about 50.6k
   TSCL cycles per block, while Probe Load implied 96–102k. Resolve the block
   period and clock statically, then design a measurement that gives one
   unambiguous number on the next pedal run.
4. **Counted-mode liveness fix (optional, decide after the diag run).** If the
   diag shows field [5] stuck, design a named fix candidate, for example clearing
   [5] on reset when queue 24 is empty. Do not build it before the evidence exists.
5. **Stack gate (static).** Continue from the 60 reviewed extents
   (`docs/helpers/STACK_CONTINUATION_2026-10-14.md`). The diag watermark will
   give a measured value. Static work remains useful, but a measured number is
   the faster route.
6. ~~**DR103 redesign**~~ done offline (session 3). Pedal measurement pending.
   Option if cycles are short: return to the straight-line tail
   (-2.6k cycles), once ~2 KB of code is freed.
7. **Patch tool (Phase E)** groundwork: it converts the owner's own v2.00
   updater and redistributes no Zoom binaries.
8. **NAM feasibility (owner question, 2026-10-15).**
   - Standard WaveNet NAM does not fit: compute and state are far over the limits.
   - Small LSTM captures (hidden size ~12-16) look plausible: an estimated
     15-30k cycles per block, ~128 B of state, a few KB of weights.
   - First step: a host LSTM kernel and its bench, then a static cycle count.
   - "Loading" means converting a `.nam` file into the const blob of an
     update-mode image. Never install over MIDI.

Open owner decisions: which JUCE effects should fill the 5 slots, and the
amp model (Tweed 5E3 is undecided).

## Helper usage (owner's standing instruction: use helpers in parallel, keep working yourself)

- **Codex Sol:**
  `codex exec -m gpt-5.6-sol -c model_reasoning_effort=medium "<task>" < /dev/null`.
  Run one Codex job at a time. It hit its cap on 2026-10-15 (reset around 12:58).
  Sol inverts `[B0]`/`[!B0]` predicates; check every truth table it gives.
- **Antigravity:**
  `agy -p "<task>" --dangerously-skip-permissions --model "Gemini 3.8 Flash (High)"`.
  Gemini 3.1 Pro is gone. Gemini is good for surveys and test-gated tooling.
- **On a Codex cap:** use an Agent subagent with `model: sonnet` and the same
  brief. Sonnet did good review work today: it found the STRING bug. It also got
  one table stride wrong, so verify its claims too.
- Every helper gets a brief in `docs/helpers/` and follows
  `docs/helpers/SAVE_PROTOCOL.md`, committing its own report only. Claude
  verifies every claim against `build/fw/map/main.dis` before relying on it.
  Add a "Claude review" block to the report.

## Pitfalls learned today

- `MVK 0xffff9000` + `MVKH 0xc87b0000` = `0xc87b9000`. MVKH *replaces* the high half.
- Stock call sites often have p-bit = 1, because arguments are set in parallel
  with the CALLP. Keep the p-bit when retargeting. A CALLP written over another
  instruction must have p = 0.
- A 16-bit compact CALLP cannot be retargeted. Overwrite a 32-bit instruction
  in the callee instead, and pin the single-caller and continuation assumption
  with a test.
- `ua_glue.c` and `ua_glue.asm` both produce `ua_glue.obj`. Give source files
  distinct stems.
- On Windows, a loaded host DLL is locked. `tools/test_usb_audio_proto.py` now
  builds a uniquely named DLL for each process.
