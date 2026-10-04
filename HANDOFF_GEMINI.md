# Handoff to Gemini — Zoom .ZD2 Patch Editor

You are taking over from a previous Claude Code session that ran out of context. **Nothing has been built yet** — the scaffold step was interrupted before any files were created. You are starting from scratch.

## Read first
- `HANDOFF.md` (in this same directory) — the full project brief from the owner. Read it end-to-end before doing anything. It defines goals, phases, layout, constraints, and what NOT to do.

## Current state of the working directory
`C:\Users\z\Documents\zoom project\` contains exactly two items:
- `HANDOFF.md` — the original brief
- `NYC_MUFF.ZD2` — the test sample file (Big Muff fuzz patch, single effect, ~minimal structure)

That's it. No `zd2tools/` repo yet, no `recon/`, no scaffold. You start at zero.

## What the previous session intended to do (use as your task list)
1. **Phase 1 — Recon.** Hex-dump and analyze `NYC_MUFF.ZD2`. Save raw outputs and write `zd2tools/recon/01_initial_analysis.md` with file size, magic bytes, strings + offsets, header-layout hypothesis, checksum suspicion, and `TODO:` open questions.
2. **Phase 1.5 — Prior art.** Read `zoom-zt2`, `zoom-ms-utils`, and forks on GitHub. Note agreement / disagreement / extensions in your recon doc. Don't copy code — write fresh, cite sources.
3. **Phase 2 — Scaffold.** Create the `zd2tools/` Python package per the directory tree in `HANDOFF.md` Phase 2. MIT license. Python 3.11+. `dataclasses`, `pytest`, `ruff`, `mypy`, GitHub Actions CI. Pick `click` or `typer` and document the choice in `DECISIONS.md`.
4. **Phase 3 — Parser MVP + CLI `zd2 inspect` + golden-file pytest.** No writer yet.
5. **Phase 4 — `FORMAT.md` spec, `README.md`, `DECISIONS.md`, `IDEAS.md`.**

## Platform notes (important — different from the brief's bash examples)
- Host is **Windows 10 / PowerShell**. The brief shows `stat`, `file`, `xxd`, `strings` — those are POSIX. Substitutes:
  - `xxd` → `Format-Hex NYC_MUFF.ZD2` in PowerShell, or write a 5-line Python script that does `for i, b in enumerate(data): ...`. Python is more reliable cross-platform — recommend using it.
  - `stat` → `Get-Item NYC_MUFF.ZD2 | Select-Object Length, LastWriteTime`
  - `file` → no direct equivalent; just inspect magic bytes yourself
  - `strings` → write a Python one-liner that scans for runs of ≥4 printable ASCII bytes
- Git Bash *may* be available via the Bash tool, but Python is the safer bet since the project is Python anyway.

## Hard constraints (from `HANDOFF.md` — do not violate)
- **Do not flash, modify, or test against a real device.** File analysis only.
- **Do not commit `NYC_MUFF.ZD2`.** Add `samples/*.ZD2` to `.gitignore`. Write `samples/README.md` explaining users supply their own.
- **Do not implement the writer yet.** Parser + inspect only.
- **Do not build a GUI.** CLI + library.
- **Do not hardcode effect-specific knowledge** (e.g., "param 3 of effect 0x42 is drive") into the parser. That belongs in a separate runtime-loaded data file.
- **Do not guess in `FORMAT.md`.** Mark uncertain fields with `?` or `TODO`.
- **Do not add features the owner didn't request.** Park ideas in `IDEAS.md`.
- If you find signed/encrypted regions, **stop and flag for the owner** — do not attempt circumvention.

## What the owner will review tonight
1. `recon/01_initial_analysis.md`
2. Repo scaffold structure
3. `FORMAT.md` skeleton with confidently-identified fields
4. Draft `README.md` (pitch, install, roadmap)
5. `DECISIONS.md` listing your judgment calls (parser library, CLI framework, etc.) for sanity-check

## If you get stuck
Write up findings, list specific blocking questions, and stop. Do not codify guesses as facts. The owner returns this evening.

Good luck.
