# CFMPRE Labels Cut to 5 Characters (Job F6)

## Status
running

## Findings

### Baseline Setup and Rationale
- **Claim**: The Zoom G1 Four effect edit screen draws labels centered in 31 px columns using a fixed 6 px pitch font (`docs/FW_RND_ANSWERS_2026-10-22.md` Q7). Consequently, labels of 5 characters (30 px) fit within the column width, whereas labels of 6 or more characters spill into adjacent columns. CFMPRE previously used labels of up to 8 characters. Job F6 cuts all 12 parameter labels to <= 5 characters while keeping the order, maximums, defaults, and explanations unchanged.
- **Evidence**:
  - `docs/FW_RND_ANSWERS_2026-10-22.md` lines 173-180 (Q7): column pitch 31 px at `0xc0181508` (`17, 48, 79, 110`), 5x7 font `c011d4d8` with fixed 6 px advance (`ADD 6` at `c011d524`).
  - `docs/helpers/FW_RND_BRIEF4_2026-10-22.md` lines 9-23.
- **Confidence**: Confirmed.

## Answers

- **Can a firmware patch change it?**:
  No firmware patch is necessary. Label width constraints are handled by keeping parameter names <= 5 characters in `manifest.json`.
- **Patch site + plan + risk**:
  N/A. Handled cleanly at the effect manifest and kernel level.

## Not checked / open leads
- Awaiting manifest modification, kernel macro update, build, slot memory check, and test suite execution.
