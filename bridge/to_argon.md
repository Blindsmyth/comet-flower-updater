# Request for Argon: patch-feasibility review for a USB teardown diagnostic (Zoom G1X Four)

## Context
TI C674x little-endian firmware, disassembly `build/fw/map/main.dis`, ELF `main.elf`. Our controller payload is loaded at
`c01a0000` (16 KiB reserved, 2880 B used) and reached via seven CALLP hooks (see HOOKS in `tools/make_controller_fw.py`:
each hook retargets an existing 32-bit CALLP word, preserving unit/parallel bits; displacement +-1M words).
DO_NOT_FLASH is in force; this is offline analysis only.

## Problem (from docs/helpers/USB_TEARDOWN_DECISION_2026-10-14.md and USB_ABORT_OWNERSHIP_2026-10-14.md)
Stock MIDI endpoint abort (software slot N, MIDI N=4, HW TX channel 3) requests a CPPI teardown, polls queue-25 pending
with a bounded count, then recycles the descriptor (`c0120744..0750`) ignoring the type-16 test result. Teardown
descriptors have word0 type[31:27]=19, TX/RX bit16 clear for TX, DMA id [15:10], channel [5:0]. The Hwi consumer
`c011faa0(24)`/`c011faa0(25)` (called at `c011fcb8..fcc2`) can run concurrently and may move a non-type-16 entry to
queue 32 (`c011fab6`, `c011fb70..78`) before deferred service recycles it (`c0121a18..24`). Abort wrapper mask at
`c011fd24` writes 0x01f71e1f (SOF bit 19 clear); rearm at `c0121576` writes 0x01ff1e1f. Late drain reads the submit
queue template `*(c01805c4+12*N)` at `c0120778`.

## Task (analysis only, no firmware edits)
Choose minimal-risk hook sites for a *diagnostic ownership candidate*:
1. Where to record (a) teardown request (slot, epoch), (b) a matching type-19 receipt (word0 fields above) as seen by
   the Hwi consumer before it can be recycled/moved, (c) poll expiry, (d) packet-buffer reuse after abort.
2. For each site: address, existing instruction word, whether it is a CALLP with free parallel/delay slots we can
   retarget (as HOOKS does), or whether a replaced-instruction trampoline is needed; which registers are live
   (A/B, callee-saved A10-A15,B10-B15, B3) and what a thunk may clobber; interrupt context (Hwi vs task) and thus
   whether it may touch kernel calls (must not in Hwi).
3. Fixed-size trace layout (<= 512 B, in `.ctl_state`): fields, index wrap, sticky fault code, max Hwi duration via TSCL.
4. State clearly what remains unproved. Tag every claim with address + instruction bytes. Do not claim the diagnostic fixes ownership.

## Disassembly: abort path c0120700..c01207b0
```text
c0120700       b502           SHL.S1        A2,0x15,A2
c0120702       0486 ||        MV.L1         A9,A0
c0120704   01838b09           EXTU.S1       A0,28,11,A3
c0120708       5050 ||        ADD.L1X       A2,B0,A5
c012070a       1347           MV.L2X        A6,B0
c012070c       04a6           MVK.L1        0,A1
c012070e       e406           MV.L1         A8,A7
c0120710   0208fd41 ||        ADDAW.D1      A2,0x7,A4
c0120714       96ce ||        MV.S1X        B5,A12
c0120716       008c           LDW.D1T1      *A5[0],A0
c0120718       e408           AND.L1        A7,A0,A0
c012071a       a56a    [ A0]  BNOP.S1       0xc012072a,5
c012071c   edb08081           .fphead       p, l, W, BU, br, nosat, 1101101b
c0120720       0034           STW.D1T1      A3,*A4[0]
c0120722       ec01           ADD.L2        B0,-1,B0
c0120724   2ffb8120    [ B0]  BNOP.S1       0xc0120716,4
c0120728       2490           ADD.L1        A1,1,A1
c012072a       9a12           MVK.S1        28,A4
c012072c       4240           ADD.L1        A2,A4,A4
c012072e       0034           STW.D1T1      A3,*A4[0]
c0120730       2f08           CMPLT.L1      A1,A6,A0
c0120732       a8ba    [!A0]  BNOP.S1       0xc0120764,5
c0120734   1ffe6013           CALLP.S2      0xc011fa20,B3
c0120738       8706 ||        MV.L1         A14,A4
c012073a       5226           CMPGT.L1      0,A4,A0
c012073c   eba08000           .fphead       n, l, W, BU, br, nosat, 1011101b
c0120740       84aa    [ A0]  BNOP.S1       0xc0120764,4
c0120742       6246           MV.L1         A4,A3
c0120744   1ffe6292           CALLP.S2      0xc011fa54,B3
c0120748       e11b           CALLP.S2      0xc0120550,B3
c012074a       81c6 ||        MV.L1         A3,A4
c012074c       0627 ||        MVK.L2        0,B4
c012074e       2312 ||        MVK.S1        1,A6
c0120750   032818f2 ||        MV.D2X        A10,B6
c0120754   1ffe5c13           CALLP.S2      0xc011fa20,B3
c0120758       8706 ||        MV.L1         A14,A4
c012075a       5226           CMPGT.L1      0,A4,A0
c012075c   e9a080f0           .fphead       n, l, W, BU, br, nosat, 1001101b
c0120760       9cba    [!A0]  BNOP.S1       0xc0120744,4
c0120762       6246           MV.L1         A4,A3
c0120764       0686           MV.L1         A13,A0
c0120766       a22a    [ A0]  BNOP.S1       0xc0120770,5
c0120768       9587           MV.L2X        A11,B4
c012076a       0013 ||        MVK.S2        0,B0
c012076c       7005           STW.D2T2      B0,*B4[3]
c012076e       995b           CALLP.S2      0xc01200f4,B3
c0120770       0786           MV.L1         A15,A0
c0120772       260e ||        MV.S1         A12,A1
c0120774   02002078           ADD.L1        A1,A0,A4
c0120778   05906064           LDW.D1T1      *-A4[3],A11
c012077c   e3f08110           .fphead       p, l, W, BU, br, nosat, 0011111b
c0120780   1ffe5413           CALLP.S2      0xc011fa20,B3
c0120784   022c0fd8 ||        MV.L1         A11,A4
c0120788   0600a358           MVK.L1        0,A12
c012078c       5226           CMPGT.L1      0,A4,A0
c012078e       a5aa    [ A0]  BNOP.S1       0xc01207ac,5
c0120790       2627           MVK.L2        1,B4
c0120792       d507           MV.L2X        A10,B6
c0120794       dd1b           CALLP.S2      0xc0120550,B3
c0120796       d246 ||        MV.L1X        B4,A6
c0120798   1ffe5413           CALLP.S2      0xc011fa20,B3
c012079c   e7008400           .fphead       n, l, W, BU, br, nosat, 0111000b
c01207a0   022c0fd8 ||        MV.L1         A11,A4
c01207a4   06302058           ADD.L1        1,A12,A12
c01207a8       5226           CMPGT.L1      0,A4,A0
c01207aa       be3a    [!A0]  BNOP.S1       0xc0120790,5
c01207ac       e89b           CALLP.S2      0xc0120628,B3
c01207ae       8506 ||        MV.L1         A10,A4
c01207b0       a41b           CALLP.S2      0xc01201e0,B3
```
## Disassembly: Hwi queue consumer c011faa0..c011fb90
```text
c011faa0       31f7           STW.D2T2      B3,*B15--[2]
c011faa2       6246           MV.L1         A4,A3
c011faa4       f81b           CALLP.S2      0xc011fa20,B3
c011faa6       5226           CMPGT.L1      0,A4,A0
c011faa8   c0778120    [ A0]  BNOP.S1       0xc011fb8e,4
c011faac       9247           MV.L2X        A4,B4
c011faae       0332           MVK.S1        32,A6
c011fab0       07a6           MVK.L1        0,A7
c011fab2       fb5b           CALLP.S2      0xc011fa54,B3
c011fab4       0246           MV.L1         A4,A0
c011fab6       da3a    [!A0]  BNOP.S1       0xc011fb70,5
c011fab8   00480228           MVK.S1        0xffff9004,A0
c011fabc   e7608000           .fphead       n, l, W, BU, br, nosat, 0111011b
c011fac0   00643de8           MVKH.S1       0xc87b0000,A0
c011fac4       a60b           SHL.S2        B4,0x5,B0
c011fac6       1051           ADD.L2X       B0,A0,B5
c011fac8       108d           LDW.D2T2      *B5[0],B0
c011faca       6c6e           NOP           4
c011facc   008369a2           SHRU.S2       B0,0x1b,B1
c011fad0   00040ada           CMPLT.L2      0,B1,B0
c011fad4   3058a120    [!B0]  BNOP.S1       0xc011fb70,5
c011fad8   0004a8da           CMPGT.L2      5,B1,B0
c011fadc   e0c00000           .fphead       n, l, W, BU, nobr, nosat, 0000110b
c011fae0   3024a120    [!B0]  BNOP.S1       0xc011fb70,5
c011fae4   00015428           MVK.S1        0x02a8,A0
c011fae8   00041800           MPY32.M1X     A0,B1,A0
c011faec   0016042a           MVK.S2        0x2c08,B0
c011faf0   006008ea           MVKH.S2       0xc0110000,B0
c011faf4   03800fda           MV.L2         B0,B7
c011faf8   0101462a           MVK.S2        0x028c,B2
c011fafc   0000107a           ADD.L2X       B0,A0,B0
c011fb00   028800fa           SUB.L2        B0,B2,B5
c011fb04   0094c228           MVK.S1        0x2984,A1
c011fb08   00e008e8           MVKH.S1       0xc0110000,A1
c011fb0c       2040           ADD.L1        A1,A0,A4
c011fb0e       007c           LDW.D1T1      *A4[0],A7
c011fb10   0001542a           MVK.S2        0x02a8,B0
c011fb14   01040572           MPYLI.M2      B0,B1,B3:B2
c011fb18       4c6e           NOP           3
c011fb1a       50e1           ADD.L2X       B2,A1,B6
c011fb1c   e9000000           .fphead       n, l, W, BU, nobr, nosat, 1001000b
c011fb20       110d           LDW.D2T2      *B6[0],B0
c011fb22       6c6e           NOP           4
c011fb24   3028a120    [!B0]  BNOP.S1       0xc011fb70,5
c011fb28   0308e07a           ADD.L2        B7,B2,B6
c011fb2c   037ecc52           ADDK.S2       -616,B6
c011fb30       110d           LDW.D2T2      *B6[0],B0
c011fb32       63c7           MV.L2         B7,B3
c011fb34       4c6e           NOP           3
c011fb36       5027           CMPGT.L2      0,B0,B0
c011fb38   2028a120    [ B0]  BNOP.S1       0xc011fb70,5
c011fb3c   e6200000           .fphead       n, l, W, BU, nobr, nosat, 0110001b
c011fb40   000c407b           ADD.L2        B2,B3,B0
c011fb44   0181462a ||        MVK.S2        0x028c,B3
c011fb48       09e1           SUB.L2        B0,B3,B6
c011fb4a       390d           LDW.D2T2      *B6[9],B0
c011fb4c       191d           LDW.D2T2      *B6[8],B1
c011fb4e       4c6e           NOP           3
c011fb50       2431           ADD.L2        B0,1,B3
c011fb52       6c89           CMPLT.L2      B3,B1,B0
c011fb54   2010a120    [ B0]  BNOP.S1       0xc011fb60,5
c011fb58   0180a35a           MVK.L2        0,B3
c011fb5c   e3800000           .fphead       n, l, W, BU, nobr, nosat, 0011100b
c011fb60   03147c42           ADDAW.D2      B5,B3,B6
c011fb64   0300b453           ADDK.S2       360,B6
c011fb68       f0dd ||        LDW.D2T2      *B5[7],B5
c011fb6a       110d           LDW.D2T2      *B6[0],B0
c011fb6c       6c6e           NOP           4
c011fb6e       1085           STW.D2T2      B0,*B5[0]
c011fb70       03c6           MV.L1         A7,A0
c011fb72       a36a    [ A0]  BNOP.S1       0xc011fb7a,5
c011fb74       f11b           CALLP.S2      0xc011fa70,B3
c011fb76       8346 ||        MV.L1         A6,A4
c011fb78       a44a           BNOP.S1       0xc011fb82,5
c011fb7a       f11b           CALLP.S2      0xc011fa70,B3
c011fb7c   ef80a400           .fphead       n, l, W, BU, br, nosat, 1111100b
c011fb80       4232 ||        MVK.S1        34,A4
c011fb82       ea1b           CALLP.S2      0xc011fa20,B3
c011fb84       81c6 ||        MV.L1         A3,A4
c011fb86       5226           CMPGT.L1      0,A4,A0
c011fb88   df988120    [!A0]  BNOP.S1       0xc011fab0,4
c011fb8c       9247           MV.L2X        A4,B4
c011fb8e       71f7           LDW.D2T2      *++B15[2],B3
c011fb90       6c6e           NOP           4
```
## Output format
Reply with a # FLASH_3.8_ACTION_PLAN section: numbered steps Flash 3.8 can execute (file edits to firmware/controller/*, tools/make_controller_fw.py HOOKS rows, tests to add), followed by an ## Evidence table (address | bytes | claim) and ## Unproved. Save-as target: bridge/from_argon/response.md.

