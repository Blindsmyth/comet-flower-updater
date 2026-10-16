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

### Finding 3 - page state and descriptor dispatch (B2)
Confidence: confirmed. MainApp's screen selector is the word c011ad8c:
`c0156e80 MVK 0xffffad8c,A4; c0156e84 MVKH c0110000,A4;
c0156e88 LDW *A4[0],A4`. It is distinct from the current menu descriptor
pointer at B14[120] (byte offset 0x1e0). `c0149664` resolves page ID via
c01495c0, compares the result to B14[120], invokes old descriptor word[5]
(exit), writes new pointer (`c0149698 STW A0,*+B14[120]`), and invokes
new word[4] (entry). `c01497f4..c0149808` returns descriptor word[0],
or 0xfff if absent. Table c018413c maps ID 10 -> c0149608 -> c0167230
-> c0183788 (SETUP), ID 11 -> c0149600 -> c01632ec -> c01837ac (PWR/LCD).
MainApp screen IDs 4 and 7 both route to c0149840: c01840c8/c01840d4
contain c0134b44; `c0134b44 CALLP c0149840` forwards the event pointer.
This handler forwards events through descriptor word[8]: `c014990a LDW
*B4[8],B0; c0149910 B B0; c0149918 MV A10,A4`. Thus a descriptor
callback replacement can intercept values without editing the generic dispatcher.
Events 6/7 trigger the exit test (`c014980e ADD A0,-6,A0; c0149810
CMPLTU 1,A0,A0`); IDs other than 0,1,9 allow exit (`c0149824..9836`).
The taken exit arm `c01498f4 CALLP c0149820` leads to c0149924, then
`c0149934 CALLP c0156e8c; c0149938 CALLP c0135b70`. Physical switch
legends and the exact restored screen require the producer/transition trace.

### Finding 4 - direct knob-to-item edits and reusable records (B2/B4)
Confidence: confirmed dispatch/layout; likely semantic names for callbacks.
SETUP handler c01671ac accepts only event IDs 25..28 (`c01671b0 SUB
A0,0x19,A0; c01671b4 CMPLTU 3,A0,A0`). Its full-word candidate hook is
`c01671c8: 1fc4f113 CALLP c0149948,B3`, with A4=4 (count), B4=event
pointer, A6=c0182bb0 (records), loaded by c01671c4..71d2. MainApp context
follows descriptor word[8] dispatch in Finding 3; the final descriptor contents
still need initializer recovery to close that linkage. No current-item cursor
is needed for this path: index=event[0]-25, record stride 0x2c (`c0149954
SUB B0,0x19,B0; c0149978 MVK 0x2c,B0; c0149980 MPYLI B0,B4,B1:B0`).
Generic editor calls record word[8] without an explicit argument (getter),
then `c01499a8: 10135893 CALLP c0153464` with A4=word[6], B4=event;
adds that result to old value (`c01499b2 ADD A0,A4,A1`), calls c01418ec
with A4=sum, B4=word[5], A6=word[6], B6=0 (likely clamp/range), and
compares old/new at c01499cc. On difference it calls word[9], then word[10],
both with A4=new value (`c01499d2 LDW *A4[9],A0; c01499d8 B A0;
c01499e4 MV A11,A4; c01499ea LDW *A4[10],A0; c01499f8 MV A11,A4`).
Success returns 1, unchanged/missing getter returns 0 (`c0149a00..9a08`).
Prefer a cloned 4-record table with one record's label/range/getter/setter/
post-change callbacks replaced, passed to BOTH page draw and edit wrappers.
This avoids a fifth knob/item and leaves stock records untouched. Exact range
semantics and redraw callback ownership remain to be verified below.
