# Menu RE � Codex Astra � 2026-10-16

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

### Finding 2 - ELF mapping boundary (all sections)
Confidence: confirmed from ELF section headers and instruction cross-check.
The brief's offset+c010c0c0 rule validates SETUP at file offset 745f4, but
must not be extrapolated beyond that section. Section sc016f780 has VA
c016f780, file offset 636c0, size 123a4 (ends c0181b24); sc0183b74 has
VA c0183b74, file offset 75a64, delta c010e110. c0182bb0 and c0183788
are not backed by either ELF section; their initialization requires another
source/initializer trace. No raw words from a guessed offset are evidence.
Instruction anchor: `c01495cc MVK 0x413c,A5; c01495d0 MVKH c0180000,A5;
c01495d4 LDW *A5[A4],A0; c01495d8 BNOP A0,5`. The disassembly's
`c018413c .word c0149658` validates the dispatch table's correct mapping.
