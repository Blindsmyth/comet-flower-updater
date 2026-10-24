# Brief for Gemini (agy): Big Muff target-spec research (2026-10-23)

Run in the background:
`agy -p "Read docs/helpers/GEMINI_MUFF_TARGET_SPEC_2026-10-23.md and do the task" --dangerously-skip-permissions --model gemini-3.8-flash-high`

This is a **web research task**, unlike the firmware-map work queue (`docs/helpers/GEMINI_NEXT.md`):
you need and are expected to use internet search for this one. Everything else about
discipline carries over: `docs/helpers/SAVE_PROTOCOL.md`'s report/commit-per-finding
procedure and confidence labelling, adapted below for sources instead of addresses. Static
only in a different sense here: never touch the pedal, any MIDI/USB device, or any `.exe` in
this repo; this is pure desk research, output is a markdown report.

## Context (why this task exists)
Owner wants a rigorous, graphable answer to "is our CF Muff effect actually more accurate
than Zoom's stock NYC_MUFF" — not a vibes/by-ear claim, a real comparison against the actual
hardware both effects claim to model. The two effects target **different historical units**
of the same pedal family, so get this distinction right, don't blur it:
- **CF Muff** (`effects/muffx/manifest.json`, kernel `effects/common/muff_g1.h`): claims to
  model the **1974 "Violet" Ram's Head Electro-Harmonix Big Muff Pi** — "asymmetric-rail Q1
  booster, two diode-and-560pF feedback clip stages (finite loop gain), exact tone network,
  recovery stage."
- **Zoom NYC_MUFF** (stock effect on the G1X Four): per this repo's own prior static analysis
  (`recon/11_stock_drives.md` lines ~129-137, ~544-584), models a Big Muff Pi with its own
  tone-stack tables (`Muff_Tone_LPF_Mix_tbl`, `Muff_Tone_HPF_Mix_tbl`, etc.) and sustain/level
  tables; the name and recon notes point at the **NYC reissue** Big Muff Pi, not the '74
  Violet Ram's Head. Treat this as **likely**, not confirmed — if your research finds
  anything that pins down exactly which Big Muff Zoom's own marketing/manual says NYC_MUFF
  emulates, that would raise it to confirmed; otherwise note it stays likely.

Both are real, well-documented vintage/reissue circuits with an active DIY/mod community
(diystompboxes.com, electrosmash.com, premierguitar.com, R.G. Keen's technical writing, Kit
Rae's Big Muff history page are all known-good source types for this — this project's own
`docs/CN_CHAIN_SPEC_2026-10-21.md` already leans on "Kit Rae numbers" informally and flags them
as unverified, which is exactly the gap this task should close with real citations).

## Task
Produce `docs/MUFF_TARGET_SPEC_2026-10-23.md` (create it FIRST with the section headings
below, before researching anything, per the save protocol) with, for **each** of the two
units separately:

1. **Circuit identification.** Confirm (with a cited source) which specific Big Muff Pi
   version/era each name refers to, including: production years, "transistor count" era
   (the famous Muff versions differ — triangle/ram's-head/pyramid/etc. are not
   interchangeable), and any well-known component differences from other Muff versions
   (clipping diode types, tone pot value, any added/removed stages).
2. **Component values** for the two things that actually drive sound: the clipping stages
   (diode type, e.g. 1N914 vs germanium vs other; feedback cap values around them) and the
   tone stack (the classic Muff tone network's R/C values — these vary across Muff versions
   and are exactly what makes each one sound different). Quote the schematic or a direct
   transcription of it, with a URL.
3. **Measured or simulated frequency response / transfer characteristic**, if findable:
   a tone-stack frequency response plot (even approximate, e.g. from a SPICE sim someone
   published, or a measured sweep), or numeric descriptions of the clipping transfer function
   (threshold voltages, asymmetry). Flag clearly whether a given number is from a real
   measurement/simulation (confirmed/likely) or from someone's verbal description with no
   data behind it (guess — still worth recording, just labelled honestly).
4. **A comparison table**: wherever the two units' real component values differ (tone R/C
   values, diode types, pre-gain structure), put them side by side so the eventual DSP
   comparison has concrete numeric targets, not just "sounds different."

## Rules (adapted from SAVE_PROTOCOL.md and GUESS_PASS.md for research instead of disassembly)
- Create the report file first with the four section headings above (plus "Open questions"),
  commit it empty/stubbed, then fill it in as you go.
- After every finding (a confirmed circuit ID, a component value, a found plot), append it
  to the report and commit **that file only**:
  `git add docs/MUFF_TARGET_SPEC_2026-10-23.md && git commit -m "muff target spec: <finding>" -m "Co-Authored-By: Gemini 3.8 Flash"`.
  Never `git add -A`/`git add .`, never commit anything else, never `git push`.
- **Every claim needs a URL you actually found**, quoted close enough that someone could
  verify it. Confidence: **confirmed** (a primary source — a schematic scan, a manufacturer
  spec, a measured/simulated plot) / **likely** (a well-regarded secondary source, e.g. a
  known Big-Muff historian's write-up, without you having seen the primary schematic
  yourself) / **guess** (forum hearsay, no real source, or your own inference). A wrong
  "confirmed" is the worst possible answer — if you can't verify something, leave it `guess`
  and say what's missing, exactly like the firmware recon docs in this repo do.
- Do not fabricate numbers to fill in a gap. An empty cell with "not found" beats a plausible-
  looking invented one.
- Scratch files (downloaded images, intermediate notes) go in `build/gemini_scratch/` only.
- Token economy: don't paste huge page dumps into your own context; summarize what you read
  and cite the URL. Budget is small.

## When done
Finish the report with an "Open questions" section: anything you looked for and could not
find a real source for, stated plainly, so this doesn't get mistaken for exhaustive later.
