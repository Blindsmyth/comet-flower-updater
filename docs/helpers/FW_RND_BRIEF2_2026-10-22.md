# Firmware R&D follow-up brief, 2026-10-22 (jobs F3, F4, S6, S7)

Follows `docs/FW_RND_ANSWERS_2026-10-22.md` (read its Q1, Q3, Q5, Q7, Q8 and
"Recommended order"). The hard rules of `docs/helpers/FW_RND_BRIEF_2026-10-22.md`
apply (no pedal, SAVE_PROTOCOL, commit only your own files, never push,
utf-8 in Python, confidence words, honest "not done"). Differences: build
jobs may also edit the effect folder and files named in their job, and may
run `bash tools/build_g1.sh` (it writes `build/<FILE>.ZD2`). Never build
or touch updater images (`tools/make_g1_image.py`), never edit `tools/` or
`effects/common/` unless your job names the file. Commit your effect folder
plus your report together after each verified step (named files only).
Also run `.venv/Scripts/python.exe -m pytest tests -q` at the end and report
the result (do not fix unrelated failures; list them).

Useful: `tools/build_g1.sh <effect-dir> <icon-label>` (see its header),
`tools/check_slot_mem.py` (40 KiB rule), `tools/c6x_cycles.py` /
`tools/c6x_loop_report.py` (static cycles, loop bounds), `tools/stack_depth.py`
(stack frame), `docs/DSP_RULES.md` (all rules; no C `switch`; ELF image 0
must be drawn), ZD2 header survey script `build/fw_rnd/F2/zd2_survey.py`.
Stomphacks generates `sh_params.h` from the manifest: param `name` "Muff Sust"
becomes `SH_PARAM_MUFF_SUST`, index = manifest order.

## F3 - CF M3 / CF M4 slot-count probes (Gemini 3.8 Flash)
Report: `docs/helpers/FW_RND_F3_M3M4_FLASH_2026-10-22.md`. Edit only
`effects/cfm3/`, `effects/cfm4/` (new) and the report.
Purpose: test the firmware ceiling found at c0129908 (header 0x58 must be
<= 4). Copy `effects/cfm2/` to `effects/cfm3/` and `effects/cfm4/`
(rename the .c file to cfm3.c / cfm4.c and the manifest `kernel`). Change
ONLY: name/display "CF M3" / "CF M4", filename `CFM3P` / `CFM4P`, id
`07000f8e` / `07000f8f`, `g1_slots` 3 / 4, and the description's slot
number (keep "Never save it in a patch."). Build both (icon label `CF M3`
/ `CF M4`). Verify with the survey script or a few lines of Python: header
0x58 = 3 / 4, every other header byte equal to CFM2P's except the fields
that must differ (name, id, checksum, sizes); list each differing offset.
check_slot_mem passes. Report a table: file, size, 0x58, id, dspload.

## F4 - CFMPRE page re-layout, one stage per page (Gemini 3.8 Flash)
Report: `docs/helpers/FW_RND_F4_CFMPRE_FLASH_2026-10-22.md`. Edit only
`effects/cfm_pre/manifest.json`, `effects/cfm_pre/cfm_pre.c`, the report.
The pedal shows 3 params per page. New order and labels (all <= 8 chars;
stock maximum is 8), keeping every param's max, default and explanation
exactly as now (only order and label change):
  page 1 Dyna:     `Dyn Sens` (was Dyna Sens), `Dyn Out` (Dyna Out), `Dyn On` (Dyna On)
  page 2 Muff:     `MuffSust` (Muff Sust), `MuffTone` (Muff Tone), `Muff Vol` (Muff Vol)
  page 3 Mistress: `MistRate` (Mist Rate), `MistRang` (Mist Rang), `MistColr` (Mist Colr)
  page 4 Switches: `Muff On` (Muff On), `Mist Mtx` (Mist Mtrx), `Level` (Pre Level)
In cfm_pre.c change ONLY the `SH_PARAM_*` macro names to the new generated
names (e.g. `SH_PARAM_DYN_SENS`; check the generated sh_params.h in the
build output for the exact spelling). No other code change. Check: the EDTB
patch fields 6..8 (0-based 5..7, here MuffTone, Muff Vol, MistRate) are only
8 bits wide, so their max must be <= 255: confirm. Build (icon label
`CFM Pre`), check_slot_mem passes, header 0x58 still 2. Report old -> new
index table and the before/after .text size.

## S6 - CF Rotary: simple mono rotary replacing RA200X (Sonnet)
Report: `docs/helpers/FW_RND_S6_ROTARY_2026-10-22.md`. New folder
`effects/rotx/` (filename `ROTX`, id `06000f8a`, name/display `CF Rotary`),
plus a host test `tests/host/rotx_test.cpp` + `tests/host/build_rotx_test.bat`
(copy the pattern of the CE2/Delay block tests). Do not edit effects/ra200x.
Why: RA200X gives no audio and crashes USB audio when effects follow it;
answers doc Q5 ranks its data-dependent MNA solver loops (14.1k cycles vs 4k
expected) first. Requirements:
- Leaf kernel in the proven style of `effects/ce2x/ce2x.c` / `effects/delayx`:
  every loop has a fixed trip count (c6x_loop_report shows no unbounded
  loops), no calls inside the audio function, frame as small as possible
  (report stack_depth; target 0, must be < 256 B), no `switch`, no division
  or libm in the per-sample loop (tables or polynomials).
- Mono in, and the same signal on ch B as ch A out (write both: A at
  `eff[i]`, B at `eff[i + SH_CH_B_OFFSET]`, as CE2X does; say what CE2X and
  DLYX do and follow it).
- Sound: horn+drum Leslie-style: crossover (~800 Hz, 1-pole or 2nd-order),
  horn path with Doppler (short modulated delay, fractional, linear interp)
  and amplitude modulation, drum path with AM only, slow/fast speeds with
  separate horn/drum acceleration (horn fast ~6.7 Hz slow ~0.8 Hz, drum a
  bit slower and with longer ramp). Params (<= 4, labels <= 8 chars, max <=
  255): `Speed` (0 slow,1 fast, max 1), `Depth` (100), `Ramp` (100), `Mix`
  (100). Parameter smoothing; no zipper noise.
- Budget: static estimate < 5,000 cycles per 16-sample block (c6x_cycles);
  dspload declared on Zoom's scale `7 + 3 x kcycles` (round up).
- State: what fits in state_bytes (<= 392) in state; the delay line in the
  slot work buffer (see how CE2X/DLYX get it, guard word like
  `SH_STATE_GUARD`), with a sane fallback if the work buffer is absent.
- Host test: finite output (no NaN/Inf) for silence, full-scale sine and
  noise at every param corner over 10 s; speed ramp reaches the target;
  output level within 3 dB of input at Mix 100 Depth 0. Build and pass it.
- Build with tools/build_g1.sh (icon label `CF ROT`), check_slot_mem passes.
Report: design, cycles, stack, loop report, test results, dspload.

## S7 - Locate the LCD effect-edit screen (Sonnet)
Report: `docs/helpers/FW_RND_S7_EDITSCREEN_2026-10-22.md`. Static RE only.
S5 (`docs/helpers/FW_RND_S5_MENU_2026-10-22.md`) found that 11807eb8 /
11808360 are MIDI/USB string code, not the screen. Find the code in the
UpdateUI task (c013c754) or MainApp (c0134e10) that draws the effect edit
screen when the user turns a knob or pages through an effect's params:
where it reads the param descriptors (c012afe0, the 56-byte record, label at
+0), how many params it shows per page and what decides it (watch for the
4 knobs on 1-slot effects vs 9 on 2-slot ones; header 0x58 or param count),
which font/glyph routine draws the label (fonts: MENU_RE_ARGON_2026-10-16.md,
recon/10) and the pixel width per column, so the max label length before
clipping. Approach: start from callers of c012afe0 (and its siblings
c012b008/c012b048) that are reached from UpdateUI/MainApp
(`tools/fwmap/subsystems.py` output build/fw/map/subsystems.tsv), then down
to the glyph calls. Answer each with patch site, plan, risk.
