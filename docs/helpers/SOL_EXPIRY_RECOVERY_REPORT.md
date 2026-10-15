# TX abort poll-expiry recovery

Static analysis of the pinned `build/fw/map/main.dis`. No device or executable
was accessed, no firmware was changed, and nothing was pushed.

## 1. The `c0120550` B4=1 path

**Finding 1 (confirmed).** With the abort's arguments B4=1, A6=1 and B6=N,
`c0120550` selects the TX record at `0xc011297c + 0x2a8*N`.  It always
recycles the supplied descriptor to free queue 28 at `c0120618..0622`, but
first conditionally accounts a completion and can submit another hardware
descriptor.  The mechanical branch truth table is:

| Predicate, in evaluation order | Effect before recycle |
|---|---|
| record field [2] != 0 | none |
| field [2] == 0 and field [5] <= 0 | none |
| field [2] == 0 and old field [5] > 1 | store field [5] = old-1 |
| field [2] == 0 and old field [5] == 1, field [3] == 1 | store field [5]=0 and field [3]=0; call `c01200f4` |
| same, field [3] == 2 | store field [5]=0 and field [3]=3; do not call `c01200f4` |
| same, field [3] neither 1 nor 2 | store field [5]=0; leave field [3] unchanged |
| any of the last three rows, then field [6] != 0 | call `c01204b4(N)`, the TX cache-writeback/build/submit chain |

Thus **yes**, an abort can resubmit a buffer to hardware: each descriptor
drained at `c0120790..0796` has these exact B4/A6 values, and the final-count,
field-[6]-nonzero row reaches `c01204b4`.  The `STW` at `c01205f0` is in the
delay slots of the `c01205ee` branch and therefore executes whether the new
count is zero or nonzero.

Evidence (field [2] and outstanding-count gates):

```text
c01205e0       400c ||        LDW.D1T1      *A4[2],A0
c01205e2       a72a    [ A0]  BNOP.S1       0xc0120618,5
c01205e6       a01c           LDW.D1T1      *A4[5],A1
c01205e8       10a6           CMPLT.L1      0,A1,A0
c01205ea       a73a    [!A0]  BNOP.S1       0xc0120618,5
c01205ec       ec80           ADD.L1        A1,-1,A0
c01205ee       872a    [ A0]  BNOP.S1       0xc0120618,4
c01205f0       a004           STW.D1T1      A0,*A4[5]
```

Evidence (pending-state transition and restart):

```text
c01205f2       601c           LDW.D1T1      *A4[3],A1
c01205f4       20a6           CMPEQ.L1      1,A1,A0
c01205f6       a4ea    [ A0]  BNOP.S1       0xc0120606,5
c01205f8       40a6           CMPEQ.L1      2,A1,A0
c01205fa       a5ba    [!A0]  BNOP.S1       0xc012060c,5
c0120602       6426           MVK.L1        3,A0
c0120604       6004           STW.D1T1      A0,*A4[3]
c0120606       0426           MVK.L1        0,A0
```

```text
c0120608       6004           STW.D1T1      A0,*A4[3]
c012060a       af5b           CALLP.S2      0xc01200f4,B3
c012060c       8406           MV.L1         A8,A4
c012060e       c00c           LDW.D1T1      *A4[6],A0
c0120612       a33a    [!A0]  BNOP.S1       0xc0120618,5
c0120614       eb5b           CALLP.S2      0xc01204b4,B3
c0120616       9346 ||        MV.L1X        B6,A4
c0120618   1ffe8e13           CALLP.S2      0xc011fa70,B3
```

Confidence: **confirmed**.

## 2. In-flight descriptors after expiry

**Finding 2 (confirmed, with one likely semantic label).** A host packet
descriptor already owned by TX DMA returns to **queue 24**, not queue 25.
`c0120250` copies template word [1] into descriptor word 2's low 12-bit return
queue field; for N=1..4 that template word is 24.  Queue 25 is selected later
in TXGCR for the separate teardown descriptor.  Therefore the Hwi's
`c011faa0(24)` call consumes the late host descriptor, while the type-16 path
at `c011fab8..fb6e` handles it.  It is not handled by the abort's queue-25
drain.

Evidence (return queue placed in descriptor word 2):

```text
c01202c6       218c           LDW.D1T1      *A7[1],A0
c01202c8       0b27           CMPEQ.L2      0,B6,B1
c01202cc       7483           SHL.S2        B1,0x13,B1
c01202d0   00029408           EXTU.S1       A0,20,20,A0
c01202d4       14a8           OR.L1X        A0,B1,A0
c01202d6       5d02 ||        SHL.S1        A2,0x1a,A2
c01202d8       4428           OR.L1         A2,A0,A0
c01202da       4005           STW.D2T1      A0,*B4[2]
```

The type-16 consumer extracts a slot number 1..4, locates the TX record at
`0xc011297c + 0x2a8*N`, and gates its data write on field [2] being nonzero
and field [9] not being positive (`c011fb20..fb38`).  It then uses field [9]
and field [8] to choose (with wrap to zero) one word from the per-slot array
at record+360, loads the destination pointer from field [7], and stores that
word through the pointer.  Calling this a completion/result write is
**likely**; the load/store and addresses are confirmed.

Evidence (the actual state/buffer write):

```text
c011fb4a       390d           LDW.D2T2      *B6[9],B0
c011fb4c       191d           LDW.D2T2      *B6[8],B1
c011fb50       2431           ADD.L2        B0,1,B3
c011fb52       6c89           CMPLT.L2      B3,B1,B0
c011fb54   2010a120    [ B0]  BNOP.S1       0xc011fb60,5
c011fb60   03147c42           ADDAW.D2      B5,B3,B6
c011fb68       f0dd ||        LDW.D2T2      *B5[7],B5
c011fb6e       1085           STW.D2T2      B0,*B5[0]
```

This consumer never calls `c0120550` and never stores field [5], so it cannot
double-decrement the abort's outstanding count.  Conversely, the abort only
runs `c0120550` on descriptors it actually pops from the submit queue; the
already-DMA-owned descriptor is absent from that queue.  The late queue-24
consumer therefore does not touch a buffer that the abort accounted as freed
through `c0120550`.  It **can** touch whatever pointer is in field [7] when
the late completion is consumed; whether that pointer can already name a new
buffer is answered by the next-submit analysis below.

Confidence: **confirmed** for queue routing, counter non-interaction and the
store; **likely** for the store's higher-level completion/result meaning.

## 3. Per-slot state left by the abort

## 4. Later re-initialization

## 5. Verdict
