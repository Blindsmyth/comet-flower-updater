# Hardcoded-5-slot inventory, main firmware (Sonnet, 2026-10-23)

Static analysis only. Scope: every place OUTSIDE the already-analyzed PTCF
storage format (`docs/helpers/CF_STORAGE_SONNET_2026-10-23.md`, Q3) that
assumes exactly 5 effect slots per patch. Goal: size a 6-(maybe 7-)slot
firmware job.

Method: grep `build/codex6/main-all.dis` for the literal `5` in compare/loop
contexts (`CMPGT`, `CMPLT`, `CMPGTU`, `CMPLTU`, `MVK 5,`), for stride `0x54`
(84, slot struct size) and `0xa000` (40 KiB slot heap size), and for the
specific addresses already named in the brief; read each hit's surrounding
function (<=60 lines) to classify it. Table columns: Address | Function |
What it does with "5" | Category | Change needed | Size | Confidence.

## Summary

(filled incrementally; running counts by category go here)

## Audio

## Memory

## Patch load

(brief re-list only; full detail already in CF_STORAGE_SONNET_2026-10-23.md Q3)

## UI

## MIDI/editor

## Other

## Plan

## Status

STATUS: in progress
