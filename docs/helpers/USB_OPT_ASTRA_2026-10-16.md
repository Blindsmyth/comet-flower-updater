# USB optimization: Astra (2026-10-16)

## Summary

Work in progress.

## A1. EP0 zero-length packet

## A2. Tap position in the level chain

## A3. 24-bit FIFO feasibility
### A1 finding 1: descriptor length and completion flag (confirmed)
The configuration handler clips wTotalLength to wLength, gathers descriptor bytes into c0109fb0, and passes an equality flag to c015af48. For 192 versus 255 this flag is zero; lower-layer behavior is traced next.
Evidence: c013506c `LDHU *A5[1],B3`; c0135070 `LDHU *A7[3],B5`; c0135076 `CMPGTU B3,B0,B0`; c0135080 `EXTU B5,16,16,B3` (only if requested length is smaller); c01350ca `STB B0,*B4++[1]`; c0135108 `MV B3,A6`; c013510a `CMPEQ B5,B3,B1`; c013510c `CALLP c015af48,B3` with c0135110 `MV B1,B6`, A4=128, A8=-2, B8=0, A10=0. The c0122380 access mentioned in the brief is a setup FIFO **read**, not the reply write (`LDW *A4[0],A1`).
