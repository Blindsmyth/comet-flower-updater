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

### Finding 5 - recovered runtime descriptors and SETUP callbacks (B2/B4)
Confidence: confirmed, decoded from cinit load c0185260 -> run c0181b28
(size 0x2049), handler 1/RLE24. Decoder adapted read-only from the existing
build/agy5/cinit.py; output confined to astra_menu. This closes Finding 4's
missing descriptor link. Evidence for consumers: c0149698 stores descriptor,
c01496a4 loads entry word[4], c0149910 calls event word[8], and c01499d2
loads setter word[9]. Exact descriptor words:

| Address | Words (ascending addresses, 4-byte stride) |
|---|---|
| c0183788 | 0000000a c017eb48 c017e848 c017e548 c01671da 00000000 c01671f6 c01671a0 c01671ac |
| c01837ac | 0000000b c017eba8 c017e8a8 c017e5a8 c0163296 00000000 c01632b2 c0163258 c0163268 |

SETUP record summaries (each 0x2c bytes; word[3]/[4] label, [5]/[6]
min/max, [7] formatter, [8] getter, [9] setter, [10] post-change):

| Record | Label pointers | Min/max | Formatter | Getter | Setter | Post-change |
|---|---|---|---|---|---|---|
| c0182bb0 | c0180690 / 0 | 40/250 | 0 | 11805e64 | 0 | c016716c |
| c0182bdc | c0180694 / c0180699 | 0/1 | c0167178 | 11805ec4 | c0168488 | 0 |
| c0182c08 | c018069e / c01806a3 | 0/1 | c0167178 | 11805e2c | 11805bb0 | c0167160 |
| c0182c34 | c01806aa / c01806af | 0/1 | c0167178 | 11805f30 | 11805d0c | 0 |

All records word[0]=index 0..3 and word[1]/[2]=0xfff. Min/max semantics
are confirmed by `c0141900 CMPGT B5,A3,B0` (lower clamp) and `c0141908
CMPGT A3,A2,A0` (upper clamp), with B6=0 from c01499c4. SETUP entry
c01671da clears four bytes at c00be5c4 (`c01671e4 CALLP c0167b00`),
so these are page-local state, not evidence of a saved settings buffer.

### Finding 6 - settings RAM, dirty comparison and save/load boundary (B3)
Confidence: confirmed for buffers/calls; persistence backend not yet traced.
Live settings start at 11812f74; last-saved comparison image is 11812f08.
`118060e4 MVK 0x6c,B0; 118060f8 LDBU *A4[0],A1; 118060fa LDBU
*B4[0],B1; 11806100 CMPEQ A1,B1,A0` compares 108 bytes, returning
0 if equal / 1 if different at 11806114. PRE-SELECT setter `11805bc0
STW A0,*A4[0]` uses 11812f8c; BANK HOLD setter `11805d18 STW A0,*A4[0]`
uses 11812fd0; AUTO SAVE getter `11805ecc LDW *A4[0],A4` uses 11812f80.
These are 32-bit settings fields, not isolated spare bytes.
Save helper c01548d8 serializes the input buffer (`c01548e8 CALLP c01548c0`),
calls `c01548f0: 10358813 CALLP c016f520` with A4=50, B4=stack+8,
and copies 108 bytes to 11812f08 (`c015490c CALLP c016d4c0`). It is
called after a dirty check when leaving/changing screen (`c0156d18 CALLP
c016f3d0; c0156d28 CALLP c01548d8`, A4=11812f74), also at c0134a44.
Load helper c0154934 calls `c0154948 CALLP c016f510` with A4=50,
B4=stack+8, then c0154918 to unpack into the destination. Thus 50 is a
logical persistent record key, not yet a file name or flash address.
Validation c0154960 uses 26 records at c01823f8, each min/max/default/count:
`c01549a8 CMPLTU A1,A0,A0; c01549aa CMPGTU A1,B3,A1; c01549b4
STW A0,*A5[0]` replaces out-of-range values with defaults. A new MODE
value in an existing boolean field would be clamped unless this policy changes.
No byte is proved reserved or safe to own by this finding.

### Finding 7 - entry, page selection, exit and draw context (B1/B2/B4)
Confidence: confirmed for event IDs and code; physical panel legend unproved.
From effect/stomp screen ID 0, MainApp c0134acc selects c01308e4 via
c01840b8=c0134b94 (`c0134b94 CALLP c01308e4`). Event 6 maps via
c0183e64=c01309b6 to c0130748 (`c01309b6 CALLP c0130748`). When
c0155328(0/1) gates are clear and c011abf8 is zero, `c0130780 CALLP
c0156d68` with A4=4 enters menu screen 4. It is a single normal-button event,
not the two-foot event 4. Screen 1 also accepts event 6: c0183ec4=c0148fe2
-> c0148ea0 -> `c0148ef8 CALLP c0156d68`, A4=4, subject to its guards.
Producer identification from prior recon/15 is GPIO4 high transition (event 6),
paired with low event 5; panel label and pressed polarity remain unproved,
so this report does not claim a named physical gesture from the event ID alone.
Screen transition writes c011ad8c (`c0156d82 STW B0,*A4[0]`), dispatches
screen 4 via c018436c=c0156de0 -> c01496d0, which clears the old descriptor
(ID 0xfff), selects page 0, the SETTING chooser (c01833dc).
Chooser handler c0157bac maps events 12,14,16,18,20 to c0157ae8 via
c0184190/4198/41a0/41a8/41b0. `c0157b24 CALLP c0149664` loads
page ID from c0181350[event[2]], whose five words are 4,6,7,10,11.
Thus effect button indices 3/4 choose SETUP/PWR-LCD. Exact producer
index/legend mapping still needs verification. Alternate chooser page ID 1
uses c0181368={5,9,3,8,12}. Return exits use events 6/7 as Finding 3;
`c0156e8e CALLP c0156e64; c0156e90 CALLP c0156d68` restores the
screen recorded at c011ad94 (`c0156e6c LDW *A4[0],A4`).
There is also bounded page stepping c0149a90: sign(A4) adds +1/-1 to page,
clamps 2..12 (`c0149ab0 CMPGT 2,A4; c0149ab8 CMPLT 12,A4`) and calls
c0149664 at c0149ac4. Caller c0164870 needs producer context before
attributing that path to a particular physical control.
Draw task chain is now closed: UpdateUI c013c754 -> c013c0c8 ->
c013c060; screen 4/7 table c01843ac/c01843b8 -> c013c090 -> c013bfe0;
`c013bfe4: 101b5112 CALLP c0149a68` invokes current descriptor word[6]
(`c0149a7a LDW *B4[6],B0; c0149a84 B B0`). For SETUP this is c01671f6,
so Finding 1's c0167210 is a redraw hook in UpdateUI, not just an initializer.
