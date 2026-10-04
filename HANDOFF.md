# Project Handoff: Open-Source Zoom .ZD2 Patch Editor

## Context

You are picking up an open-source project to build tooling around Zoom's `.ZD2` patch file format, used by the Zoom **G1 Four / G1X Four / B1 Four / A1 Four** ("MS-series" firmware family) multi-effects pedals. The end-user goal is a clean, modern editor + documented format spec that improves on existing community tools.

The project owner is at their day job. Do the foundational work now so they can review and iterate when they're back. **Do not attempt to flash, modify, or test against a real device** — that requires the owner's hardware. Stick to file analysis, spec drafting, and tooling scaffold.

## What's already known (don't re-derive these)

- `.ZD2` is a binary container holding a single patch (one effect with parameters, or a chain of effects depending on the device).
- The file is a fixed header + effect blocks. Effect IDs reference effects baked into the pedal firmware — **a .ZD2 cannot define new DSP**, only configure existing effects.
- Prior art exists: search GitHub for `zoom-zt2`, `zoom-ms-utils`, and forks. Read these before writing parser code. Cite them in the README.
- The test file is `NYC_MUFF.ZD2` — a Big Muff fuzz clone patch. Single effect, minimal structure, ideal first specimen.

## Phase 1 — Recon (do this first)

Place the test `.ZD2` file at `samples/NYC_MUFF.ZD2` in the repo (the owner will provide it; if not present yet, scaffold and stub).

Run and save the output of each to `recon/` as a Markdown file `recon/01_initial_analysis.md`:

```bash
stat samples/NYC_MUFF.ZD2
file samples/NYC_MUFF.ZD2
xxd samples/NYC_MUFF.ZD2 | tee recon/hexdump_full.txt
xxd samples/NYC_MUFF.ZD2 | head -40
xxd samples/NYC_MUFF.ZD2 | tail -10
strings -n 4 samples/NYC_MUFF.ZD2
```

In `recon/01_initial_analysis.md` document:
- Exact file size in bytes
- Magic bytes (first 4–8 bytes — likely `PTCF` or similar ASCII tag)
- Any human-readable strings found and their byte offsets
- Your hypothesis for the header layout (offset, length, field-name, type)
- Any obvious checksum/CRC at the end of the file
- Open questions (mark with `TODO:`)

Compare your findings against `zoom-zt2` source on GitHub. Note where you agree, disagree, or extend. Don't copy code — read for understanding, then write fresh.

## Phase 2 — Project scaffold

Set up a Python package with this layout:

```
zd2tools/
├── README.md
├── LICENSE              # MIT
├── FORMAT.md            # The spec — start as skeleton, fill as you learn
├── pyproject.toml
├── .github/workflows/ci.yml
├── src/zd2tools/
│   ├── __init__.py
│   ├── parser.py        # bytes -> dataclass
│   ├── writer.py        # dataclass -> bytes
│   ├── models.py        # dataclasses for header, effect block, etc.
│   └── cli.py           # `zd2 inspect file.zd2`, `zd2 dump file.zd2`
├── tests/
│   ├── test_parser.py
│   └── fixtures/        # symlink or copy of samples/
├── samples/
│   └── NYC_MUFF.ZD2
└── recon/               # raw RE notes, hex dumps, scratch
```

Use:
- Python 3.11+
- `dataclasses` for models, no heavy deps for the core parser
- `click` or `typer` for the CLI (pick one, document choice)
- `pytest` for tests
- `ruff` for lint, `mypy` for types
- GitHub Actions: lint + test on push

## Phase 3 — Parser MVP

Implement `parser.py` to:
1. Read the magic bytes and validate
2. Extract the patch name (likely a length-prefixed or null-terminated ASCII/UTF-8 string)
3. Extract the effect ID(s) and parameter block(s)
4. Return a structured `Patch` dataclass

Implement `cli.py` so `zd2 inspect samples/NYC_MUFF.ZD2` prints a human-readable dump.

**Do not implement the writer yet.** Round-tripping requires confidence in the format that we don't have. Get parsing solid first.

Write tests using `NYC_MUFF.ZD2` as a fixture. Tests should be golden-file style: parse, assert specific bytes-at-offset and field values.

## Phase 4 — FORMAT.md spec

Write `FORMAT.md` as a standalone document. Structure:

```
# Zoom .ZD2 Patch File Format

## Status
Reverse-engineered, partial. Last verified against firmware version <X>.

## File layout
| Offset | Length | Field | Type | Notes |
|--------|--------|-------|------|-------|

## Effect block
...

## Known effect IDs
| ID | Name | Category | Parameters |

## Open questions
- ...

## References
- zoom-zt2: https://...
- (other prior art)
```

Aim for the spec to be useful **standalone**, citable by other projects.

## Constraints and rules

- **MIT license.** Note in README that this is unaffiliated with Zoom Corporation, all trademarks belong to their owners, and the format is reverse-engineered for interoperability (which is legally protected in most jurisdictions under fair use / interop exceptions, but not legal advice).
- **No firmware extraction, no DRM circumvention.** If you discover the format includes signed/encrypted regions, stop and flag it for the owner. We're working with user patch files, not firmware.
- **Do not commit the test `.ZD2`** without confirmation it's safe to redistribute. Stock factory patches are the user's possession but Zoom may consider them copyrightable. Put samples in `.gitignore` for now and add a `samples/README.md` explaining how users supply their own.
- **Credit prior art** in the README. Notoriety comes from being a good citizen of the RE community, not from claiming originality.

## What the owner wants reviewed when they return

1. `recon/01_initial_analysis.md` — your read of the binary structure
2. The repo scaffold (just structure, not all implementation)
3. `FORMAT.md` skeleton with whatever fields are confidently identified
4. A draft `README.md` with project pitch, install instructions, and a roadmap section
5. A list of decisions you made that the owner should sanity-check (parser library choices, CLI framework, etc.) — put this in `DECISIONS.md`

## What NOT to do

- Don't build a GUI yet. CLI + library first.
- Don't implement the writer / file modification yet.
- Don't try to upload anything to the device or simulate USB protocol.
- Don't write effect-specific knowledge into the parser (e.g., "param 3 of effect 0x42 is drive amount"). That belongs in a separate data file, loaded at runtime, so contributors can extend it without touching code.
- Don't add features the owner didn't ask for. If you have ideas, put them in `IDEAS.md` for review.

## If you get stuck

If hex analysis is ambiguous and you can't progress without a second sample file or device access, write up what you found, list specific questions, and stop. Don't guess and codify guesses as facts in `FORMAT.md` — mark uncertain fields explicitly with `?` or `TODO`.

Good luck. The owner will check progress this evening.
