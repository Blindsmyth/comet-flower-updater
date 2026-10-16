# Menu RE — Codex Astra — 2026-10-16

## Summary
Work in progress. Offline analysis only.

## B1. Entry from effects mode

## B2. Menu state machine and exit

## B3. Persistence and reserved storage

## B4. Insertion design and CALLP candidates

### Finding 1 - shared page constructor (B4; A1 cross-lead)
Confidence: confirmed for instructions/arguments; likely for constructor interpretation.
SETUP uses `c0167210: 1fda6c93 CALLP.S2 c0154564,B3` with A4=4,
B4=c0182bb0, A6=c0181558, B6=c01806b4 (SETUP), A8=0, B8=1
(`c01671f8..c0167220` loads). PWR/LCD uses `c01632cc: 1fe25493
CALLP.S2 c0154564,B3` with A4=4, B4=c0182c60, A6=c0181568,
B6=c01806dd, A8=0, B8=1 (`c01632b4..c01632dc`). Both CALLPs are
full 32-bit words; their low parallel bit is set and the argument packet must
remain intact when retargeting. These are concrete page-construction wrapper
candidates, not yet proved per-refresh draw hooks. B3 is the link register;
B14/B15 and ABI preserved registers must survive. Task context remains unproved.
Adjacent getters `c0167230 MVK 0x3788,A4; c0167234 MVKH c0180000,A4`
and `c01632ec MVK 0x37ac,A4; c01632f0 MVKH c0180000,A4` expose likely
page descriptors c0183788/c01837ac. This is a cross-lead for A1.
