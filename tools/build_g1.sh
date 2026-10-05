#!/usr/bin/env bash
# Build effects/<name> with stomphacks, then retarget it for the G1 Four.
#   tools/build_g1.sh <name> <icon-label> [<slot-pic text, e.g. GREEN/808>]
# Output: build/<FILENAME>.ZD2 (G1 form) plus the stomphacks REPORT.md.
# stomphacks breaks on paths with spaces, so the build runs in its checkout.
set -euo pipefail
NAME="$1"; LABEL="$2"; PIC="${3:-$2}"
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
LAB="${ZOOMLAB:-/c/Users/z/zoomlab/stomphacks}"
export ZOOM_TI_CGT="${ZOOM_TI_CGT:-C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS}"

FILE="$(grep -o '"filename": *"[^"]*"' "$PROJ/effects/$NAME/manifest.json" | cut -d'"' -f4)"
EFFECT="$(grep -o '"name": *"[^"]*"' "$PROJ/effects/$NAME/manifest.json" | head -1 | cut -d'"' -f4 | tr -d ' ')"
# Every stock G1 effect exports Dll_<Name> in .dynsym. stomphacks omits it
# (the MS Plus loader is name-blind); export it so we match G1 stock. Needs
# the ZD2_EXTRA_LNK_FLAGS hook in stomphacks tools/build_zd2_from_asm.sh.
export ZD2_EXTRA_LNK_FLAGS="--export=Dll_$EFFECT"
# G1 plain effects use up to 392 B of contiguous state without declaring it
# (stock NYC Muff: 4 + 388; recon/06). stomphacks caps at 192 (MS Plus proof);
# its local ZD2_STATE_BYTES_MAX hook raises the cap for G1 builds.
export ZD2_STATE_BYTES_MAX=392

rm -rf "$LAB/effects/$NAME"
cp -r "$PROJ/effects/$NAME" "$LAB/effects/$NAME"
cp "$PROJ"/effects/common/*.h "$LAB/effects/$NAME/"   # shared DSP headers
( cd "$LAB" && .venv/Scripts/python.exe tools/zd2_make_effect.py "effects/$NAME/manifest.json" | tail -12 )
mkdir -p "$PROJ/build"
cp "$LAB/effects/$NAME/build/REPORT.md" "$PROJ/build/$FILE.REPORT.md"
"$PROJ/.venv/Scripts/zd2" g1-retarget "$LAB/effects/$NAME/build/$FILE.ZD2" "$PROJ/build/$FILE.ZD2" --label "$LABEL" --pic "$PIC"
