# Firmware R&D brief, 2026-10-22 (slots, heap, stack, faults, menu)

Source questions: `HANDOFF_2026-10-22_FW_RND.md` (read it first, it is short).
Workspace: `c:\Users\z\Documents\zoom project`. Python: `.venv\Scripts\python.exe`
(or `.venv/Scripts/python.exe` from bash). Pass `encoding="utf-8"` to every
`read_text`/`write_text`/`open` (default codepage here is cp1252).

## Hard rules (every job)
- Do not touch the pedal: no MIDI, no `tools/pedal_*`, `tools/patch_g1.py`,
  `midi_*`, no updater `.exe`, no USB tools. Static analysis only.
- Edit only your own report file (named in your job) and your scratch folder
  `build/fw_rnd/<job id>/`. Never edit other files, never the repo root.
- Follow `docs/helpers/SAVE_PROTOCOL.md`: create the report FIRST with the
  headings below, append after EVERY finding, commit THAT FILE ONLY
  (`git add <report>`; `git commit -m "FW RND <job>: <finding>"`). Never
  `git add -A`/`.`, never push. On `index.lock`, wait 10 s, retry.
- Token economy: never print whole files; `grep -n` with tight patterns,
  `sed -n 'a,bp'` windows of at most 60 lines. Big output goes to scratch.
- Every claim: evidence (instruction addresses + a short disassembly excerpt,
  or `file:line` for docs) and a confidence word: confirmed / likely / guess.
  "Not found" is a valid, useful answer. Do not fill gaps with plausible
  claims; say what you did not check.
- C6000 pitfalls (from past helper errors): branches take effect 5 packets
  later, so instructions in the 5 delay slots execute; values are often
  loaded in a delay slot; predicated pairs `[B0]`/`[!B0]` are easy to invert;
  do not fold code after a `c016e000`/`c016e020` epilogue into the function;
  `CALLP` and `B` via register are calls through A3/B3. Recompute every
  derived address (base + offset) yourself.

## Where things are
- Disassembly: `build/fw/map/main.dis` (`grep -n '^c0123456'` then a window).
  Firmware flash region of the main partition: 0x33000.
- Function rows: `grep -n '^| c0123456' recon/map/chunk_*.md`; fact sheets
  (callers/callees/strings) `build/fw/map/facts/chunk_NN.md`; MVK constants
  `build/fw/map/refs.txt`; strings `build/fw/map/strings.txt`.
- Map overview: `docs/FIRMWARE_MAP.md` (memory layout, tasks, subsystems).
- Loader and memory: `recon/13_effect_loader.md`, `recon/14_effect_memory.md`
  (slot regions 0xc01f4000 + n*0xa000, state 0x11f013b0 + n*0x2a0, knob table
  0x11f00000 + n*0x348; loader c0122924..c0124fc0, c01453b4..c0146e18).
- Audio Swi (5-slot loop): 11818ba0, chunk_19, `recon/16_audio_hw.md`,
  `recon/21_usb_audio_needs.md`. Stack studies: `docs/helpers/STACK_*.md`.
- Effects and rules: `docs/DSP_RULES.md` (Process Overflow rule: dspload sum
  230.0f, `MVKH 0x43660000`), `effects/*/`, `effects/ra200x/ra200x.c`.
- Hardware facts from the handoff: CFM2P (ZD2 header byte 0x58 = 2) gets only
  slot-0 resources (code 0xc01f41e0, state 0x11f013b0, coef 0x11f00000, one
  work buffer 0xc0226000 of 529,200 B); CFM5P (header 5) is not offered in
  the effect list at all.
- ZD2 files: stock `build/bench/stock/*.ZD2`, `backup/2026-10-04/files/`;
  ours `build/*.ZD2`. ZD2 builder/format: `tools/make_g1_image.py`, effect
  build `tools/build_g1.sh`, `recon/03_g1x4_corpus_audit.md`.

## Report layout (use these headings)
```
# <job title>
## Status   (one line: running / done / stopped at <step>)
## Findings (one ### per finding: claim, evidence, confidence)
## Answers  (per question you own: answer, can a firmware patch change it,
             patch site + plan + risk)
## Not checked / open leads
```

## Jobs

### F1 - Prior-knowledge digest (Gemini 3.8 Flash)
Report: `docs/helpers/FW_RND_DIGEST_FLASH_2026-10-22.md`.
For each of the handoff's 8 questions, collect what the repo ALREADY says:
search `recon/*.md`, `recon/map/*.md`, `docs/*.md`, `docs/helpers/*.md`.
For each question list every relevant statement as a bullet: the quote or
a one-line paraphrase, `file:line`, the addresses it names, and the
confidence word the source used. Then one line: "covered / partly / not
covered". Do NOT do new disassembly reading and do NOT add your own
conclusions; this is a citation index for the reverse engineers. Commit
after each question.

### F2 - ZD2 header and label survey (Gemini 3.8 Flash)
Report: `docs/helpers/FW_RND_ZD2_SURVEY_FLASH_2026-10-22.md`.
Write a script `build/fw_rnd/F2/zd2_survey.py` (read-only on the ZD2 files)
and put its full output in `build/fw_rnd/F2/`. Survey every ZD2 in
`build/bench/stock/` and `backup/2026-10-04/files/` (dedupe by name), plus
ours in `build/*.ZD2`:
1. Header bytes 0x00..0x7f: for each offset, the set of distinct values
   seen across stock files. Highlight 0x58 (slot count): list every stock
   effect whose 0x58 is not 1, with its name and value. Also record whatever
   field holds `dspload` (see `tools/zd2_set_dspload.py`).
2. Parameter info: per effect, the number of params, each param's label
   and its length in characters, max value. Report the longest label seen,
   the max param count seen, and any stock effect with more than 9 params.
   (Find how labels are stored by reading `tools/make_g1_image.py`,
   `tools/g1presets.py` and the effect build scripts; say where you found
   the format.)
3. Compare ours (CFMPRE, CFM2P, CFM5P, RA200X) against the stock ranges:
   any field where ours is outside every stock value is a lead; list them.
Keep the report to tables and facts; no speculation about firmware.

### S1 - Effect list filter, slot-count byte, param limits (Sonnet)
Report: `docs/helpers/FW_RND_S1_LIST_PARAMS_2026-10-22.md`. Questions 1 and 3.
Find the code that reads the ZD2/INFO field at header 0x58 (and whatever it
is called after parsing), follow it to the effect-list building code (which
effects are offered for a slot) and the slot-fit check. Explain why a value
of 5 is hidden and 2 is offered (e.g. a comparison against free slots, a
table, a hard max). Then the 12-param maximum and 3-params-per-page layout:
where the counts are bounded (loops, array sizes, MVK constants 12 / 3 / 4).
For each: the patch site (file offset = address mapping per
`tools/make_usb_audio_fw.py`) and what changing it would break.

### S2 - Loader allocation for multi-slot effects (Sonnet)
Report: `docs/helpers/FW_RND_S2_LOADER_ALLOC_2026-10-22.md`. Question 2.
Starting from recon/14, trace what the loader allocates per effect: code +
const (40 KiB slot region, fixed 0xa000?), state (0x2a0 per slot), knob
table (0x348), work buffers (the 529,200 B buffer for CFM2P: which heap,
which size field, how many buffers, the "work buffers 1-4"), stack. Does
the slot count byte change any size or make the loader claim the next slot's
region/state? Where is the 40 KiB checked (and is the error path a refusal
or an overrun)? Can a patch give a multi-slot effect N x 40 KiB?

### S3 - Audio Swi: stack, cycle overrun, stereo bus (Sonnet)
Report: `docs/helpers/FW_RND_S3_SWI_2026-10-22.md`. Questions 4, 6 and 8.
In the audio Swi (11818ba0, chunk_19) and its callers: which stack the
effects run on (address, size; recon/14 saw stack 0x11816140 in L2), how
much headroom stock effects leave (docs/helpers/STACK_*.md), what lies
just below the stack (what an overflow corrupts). Then what happens when a
block runs past its budget: is there a check, a counter, a skipped block,
an EDMA ping-pong overrun (recon/16 C3/C4)? Peak 105% was seen with no
warning. Then the channel-B bus (`SH_CH_B_OFFSET`, see `effects/common/`):
how the Swi passes buffers slot to slot, whether later slots and the USB
tap read channel B, and whether a mid-chain stereo write is safe.

### S4 - Fault containment: why a bad effect kills USB audio (Sonnet)
Report: `docs/helpers/FW_RND_S4_FAULT_2026-10-22.md`. Question 5.
`RA200X` (`effects/ra200x/`) gives no audio and, with more effects after it,
crashes the USB audio driver. Read its source and its built ELF
(`build/` ZD2 or the build output; `tools/stack_depth.py`) and list what it
does that no proven effect does: `allow_stack` frame size, stereo write to
channel B, state in `instance[3]` work buffer, any write whose address
could leave its own buffers. Then in the firmware: what is adjacent to each
region it writes (state 0x11f013b0+n*0x2a0, L1D buffers 0x11f03630..
0x11f037f0, the work buffer, the L2 stack) and which of those the USB audio
path reads (recon/20..24, `docs/USB_AUDIO_TAP_CANDIDATE_2026-10-15.md`,
`docs/CF_USB_MODE_2026-10-16.md`). Is there any exception/NMI handler
(C674x IERR/EFR, `NRP`)? Rank the likely crash mechanisms with evidence and
propose a containment patch (e.g. guard words, stack canary check in the
slot loop) with its cost and risk.
