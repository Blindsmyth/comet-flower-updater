# Brief for Codex: stock drives, second pass (numbers, not names)

Context: read `recon/11_stock_drives.md` first, especially the "Review by
Claude" box at the top. A first pass (Gemini) identified each drive's parts
from symbol names. Your job is the part it skipped: turn the binaries' data
into verified numbers. Also read `recon/05_ts_drive_vs_green808.md` (the
method, done for TS Drive) and `docs/DSP_RULES.md`.

Effects: `backup/2026-10-04/files/*.ZD2`, group 3 (list in recon/11).
Extract with `.venv/Scripts/zd2 extract <file> build/codex2/<NAME>`;
disassemble with `C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS/bin/dis6x.exe`
(write UTF-8 output; the first pass's .dis files are UTF-16).

## Work, in this priority order
Do it for TS_DRIVE, GOLD_DRV, ZEN_DRV, DIST_1, NYC_MUFF, SQUEAK first (the
owner's likely rebuild candidates), then the rest if there is budget.

1. **Oversampling, verified.** Read each `*_OVS_COE_bn/an` table from the
   ELF data (find the symbol's section and offset, decode float32 or
   float64 as the code loads them). Compute the filter's response (python
   with numpy/scipy is available in `.venv`): order, -3 dB and -60 dB
   points as a fraction of its own sample rate. From the loop structure
   (how many times the clipper runs per input sample) state the factor.
2. **Knob tables, decoded.** Decode every `*_tbl` / `*_TBL` the effect
   uses into numbers, and say what each maps (knob position → gain in dB,
   frequency in Hz, Q...). Match them to the PRME parameter names.
3. **Clipper.** For `*_CLIPPER_KAWAOD` (and ToneBender's `_TR`), write the
   transfer function as math, with each effect's own parameter values.
   Plot or tabulate y(x) for x in [-2, 2]; note asymmetry.
4. **Cost.** Per-block cycle estimate from the loop structure: SPLOOP ii ×
   (trip count + stages − 1) per loop, times the loops per block (16
   samples, ×oversampling where it applies). Say where branches make this
   uncertain. `tools/c6x_cycles.py` works on dis6x listings too only if
   the format matches; check before relying on it.
5. Correct anything in recon/11 that your numbers contradict.

## Output
- Append a section `## Second pass (Codex): verified numbers` to
  `recon/11_stock_drives.md`, one subsection per effect, plus a summary
  table: effect, oversampling factor, filter corners, clipper asymmetry,
  estimated cycles/block, confidence.
- Small helper scripts may go in `build/codex2/` (gitignored); put any
  that are worth keeping in `tools/fwmap/` only if they are general.
- Stop when done or out of budget; say what is unfinished.

## Hard rules
- **Never touch the pedal**: no MIDI ports; do not run `tools/pedal_g1.py`,
  `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  `make_fs_restore_updater.py`, or any `.exe` other than dis6x.
- Analysis only: nothing of Zoom's code or tables goes into `effects/`.
- Edit only `recon/11_stock_drives.md`, `build/codex2/`, `tools/fwmap/`.
- No git commits or pushes; Claude reviews and commits.
