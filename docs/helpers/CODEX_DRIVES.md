# Brief for Codex: study Zoom's stock drive effects

You are helping on a project that writes new DSP effects for a Zoom G1X Four
guitar pedal (TI C6745 DSP). Read `HANDOFF_2026-10-06.md` (§00 and §4–§5),
`docs/DSP_RULES.md` and `recon/05_ts_drive_vs_green808.md` first. recon/05 is
the model for this work: it analysed Zoom's TS Drive from its binary.

## Goal
Find out, for each stock drive effect, how Zoom built it and where a better
"CF" (Comet Flower) version could improve on it: less aliasing, a more
faithful circuit, better response to playing dynamics, within the pedal's
CPU budget. The owner will choose which ones to rebuild from your report.

## The 14 stock drives (group 3), files in `backup/2026-10-04/files/`
TS_DRIVE (39.37), GOLD_DRV (52.50), SWEETDRV (70.75), ZEN_DRV (45.11),
TB_MK15 (50.04), RCBOOST (37.73), REDCRUNC (43.88), BGTHRTTL (66.85),
DIST_1 (36.30), DISTPLUS (31.79), NYC_MUFF (34.86), VIOLETDS (34.04),
SQUEAK (31.37), ACOSIM (31.99). The number is the declared dspload.

## Method (per effect)
1. `.venv/Scripts/zd2 inspect <file>`; `.venv/Scripts/zd2 extract <file> build/codex/<NAME>`
   gives DATA.elf, PRME, TXE1... (see `extracted/NYC_MUFF/` for the layout). Parameter names and ranges come from PRME/TXE1.
2. Disassemble DATA.elf with
   `C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS/bin/dis6x.exe`. The ELFs keep their
   symbol tables (function and table names, as in recon/05).
3. Identify: oversampling (factor, filter order/type), the clipper (shape,
   symmetric or not, piecewise / table / tanh-like), the pre- and post-EQ and
   the tone control, the knob tables (decode their numbers), the per-sample
   work.
4. Static cycle estimate per 16-sample block with `tools/c6x_cycles.py`
   (only reliable for branch-free loops; say when a loop branches).
5. Verdict: what a circuit-level CF version would do better, its likely
   cost against the ≤ 80k cycles/block budget, and a priority (1–3).

## Output
- `recon/11_stock_drives.md`: one section per effect in the recon/05 style
  (table of part / evidence / reading), then a ranking table of improvement
  candidates and a list of on-pedal measurements that would confirm the
  static findings (sweeps, aliasing tones; the owner records the pedal at
  44.1 kHz, right channel).
- Scratch files only under `build/codex/` (gitignored).
- Go as far as you can: all 14 if possible, in the order listed. If you run
  out, say clearly which ones are done.

## Hard rules
- **Never touch the pedal**: do not open MIDI ports, do not run
  `tools/pedal_g1.py`, `patch_g1.py`, `backup_g1.py`, `midi_listen_g1.py`,
  or any `.exe` in `build/fw/` or Downloads.
- Analysis only: do not copy Zoom's code or tables into `effects/`. Numbers
  belong in the report, described in your own words.
- Do not edit files outside `recon/11_stock_drives.md` and `build/codex/`.
- No git commits or pushes; Claude reviews and commits.
- Finish with a short summary: done / not done / surprises.
