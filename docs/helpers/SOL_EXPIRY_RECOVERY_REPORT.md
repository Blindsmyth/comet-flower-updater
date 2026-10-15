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

**Finding 2a (confirmed).** The Hwi is not the end of the type-16 lifecycle.
At `c011fb70..fb80` it forwards the descriptor to queue 32 when TX field [2]
is zero, or queue 34 when field [2] is nonzero.  The deferred consumer
`c01219f4` recognizes type 16 and calls `c0120550` with B4=1 and B6 equal to
the descriptor's extracted slot.  Consequently the late in-flight descriptor
does eventually decrement field [5] exactly once.  The abort did not account
that descriptor, so this is not a double decrement.  If this decrement reaches
zero and a buffer is staged in field [6], `c0120550` may resubmit it—but only
after the old descriptor has returned from DMA.

Evidence (deferred type-16 accounting):

```text
c0121a18   1ffc0a92           CALLP.S2      0xc011fa54,B3
c0121a20       0246           MV.L1         A4,A0
c0121a22       a32a    [ A0]  BNOP.S1       0xc0121a38,5
c0121a74   1ffd5e13           CALLP.S2      0xc0120550,B3
c0121a78       2627 ||        MVK.L2        1,B4
c0121a7a       c786 ||        MV.L1         A15,A6
c0121a80       d517 ||        MV.D2X        A10,B6
c0121a82       814e ||        MV.S1         A2,A4
```

Confidence: **confirmed**.

Confidence: **confirmed** for queue routing, counter non-interaction and the
store; **likely** for the store's higher-level completion/result meaning.

## 3. Per-slot state left by the abort

**Finding 3 (confirmed).** The expiry path does not have a distinct software
state cleanup.  At entry, the abort saves TX-record field [3].  If it was
zero, it writes 1 and calls `c01200f4`; at the common tail it writes 0 and
calls `c01200f4` only when the saved value was zero.  If the original value
was nonzero, both writes/calls are skipped.  Thus the abort's own temporary
busy/pending marker is restored on both observed-pending and expired paths.
`c01200f4` scans the fixed per-slot pending table and rewrites its aggregate
MMIO bitmap (`c0120124..01ac`), so the 0->1 and 1->0 transitions are reflected
in that projection.

Evidence (save and conditional 0->1 transition):

```text
c01206c2       00c1           ADD.L2        B0,B1,B4
c01206c4   027ec052           ADDK.S2       -640,B4
c01206c8       102d           LDW.D2T2      *B4[0],B2
c01206ca       b546           MV.L1X        B2,A13
c01206d8       7446           MV.L1X        B0,A11
c01206da       700d ||        LDW.D2T2      *B4[3],B0
c01206e0   2006a120    [ B0]  BNOP.S1       0xc01206ec,5
c01206e8       7005           STW.D2T2      B0,*B4[3]
```

Evidence (common conditional restoration, reached from `c0120732` expiry):

```text
c0120732       a8ba    [!A0]  BNOP.S1       0xc0120764,5
c0120764       0686           MV.L1         A13,A0
c0120766       a22a    [ A0]  BNOP.S1       0xc0120770,5
c0120768       9587           MV.L2X        A11,B4
c012076a       0013 ||        MVK.S2        0,B0
c012076c       7005           STW.D2T2      B0,*B4[3]
c012076e       995b           CALLP.S2      0xc01200f4,B3
c0120770       0786           MV.L1         A15,A0
```

The outstanding count field [5] is decremented only for descriptors popped
from the submit queue.  A DMA-owned host descriptor is absent, so after an
expired abort its count remains represented (for the simple one-in-flight
case, field [5] remains 1).  That is internally consistent, not a false
free/count decrement.  Field [3] may also undergo the normal `c0120550`
state transitions described in Finding 1 while queued entries are drained;
there is no expiry-only variant.

Crucially, the subsequent descriptor submitters do not use field [3], the
pending projection, or DMA ownership as a gate:

- `c0120484 -> c0120250` clamps the requested length against field [0], then
  submits; on success `c01204aa..04ae` increments field [5].
- `c0120c00 -> c0120250` loads field [6] and field [10] and submits directly.
- `c01219a4 -> c01219d0 -> c0120250` computes a buffer address/length and
  submits directly.
- `c0120250` itself only requires a descriptor from free queue 28
  (`c012025a..0270`).

The public TX-buffer enqueue does check field [2] (enabled/configured), but
after storing the caller's pointer and length in fields [6]/[7], a **nonzero**
outstanding count causes it to call `c01204b4`; it does not wait for the old
DMA owner to return:

```text
c0120f84       500d           LDW.D2T2      *B4[2],B0
c0120f88   300aa120    [!B0]  BNOP.S1       0xc0120f94,5
c0120f94       d015           STW.D2T2      B1,*B4[6]
c0120f96       e015           STW.D2T1      A1,*B4[7]
c0120f98       b00d           LDW.D2T2      *B4[5],B0
c0120fa0   2004a120    [ B0]  BNOP.S1       0xc0120fa8,5
c0120fa4   1ffea292           CALLP.S2      0xc01204b4,B3
c0120fa8       0626           MVK.L1        0,A4
```

So no reviewed software field is demonstrably arithmetically inconsistent
solely because the poll expired.  What remains inconsistent with the abort's
completed/re-enabled external state is the still-live DMA ownership that the
count records but the submission gates do not honor.

Confidence: **confirmed**.

## 4. Later re-initialization

**Finding 4 (confirmed).** `c0121224` is direction-selective, not a complete
zeroing of all five helper-owned tables.  For a nonzero TX endpoint it first
calls `c0120650`, then reads TX field [2].  If field [2] is zero it calls
`c011fd98`; otherwise it calls `c011fd40`.  Neither helper clears TX field
[2], field [3], or outstanding field [5]:

- `c011fd98` clears TX fields [6] through [11].
- `c011fd40` clears TX fields [6] through [8], writes/clears additional
  per-slot scratch/ring storage starting at TX-record offsets 0x28 and 0x168,
  and does not store fields [2], [3], or [5].
- On the RX branch, `c011fe20` clears RX fields [6] through [11] when RX
  field [2] is zero; `c011fdc8` is the RX analogue of `c011fd40` otherwise.
- The RX branch then always calls `c011fe4c`, which clears fields [1] through
  [4] of the separate 17-word-stride table at `0xc0114150`.

Evidence (TX selection occurs only after the same possibly-expiring abort):

```text
c0121280   1ffe7a13           CALLP.S2      0xc0120650,B3
c0121284       8506 ||        MV.L1         A10,A4
c0121290   0014c22a           MVK.S2        0x2984,B0
c012129a       1341           ADD.L2X       B0,A6,B4
c01212a0       100d           LDW.D2T2      *B4[0],B0
c01212a4   2008a120    [ B0]  BNOP.S1       0xc01212b0,5
c01212a8   1ffd5f13           CALLP.S2      0xc011fd98,B3
c01212b0   1ffd5413           CALLP.S2      0xc011fd40,B3
```

Evidence (`c011fd98`'s complete TX-record store set):

```text
c011fdb0       1341           ADD.L2X       B0,A6,B4
c011fdb2       d015           STW.D2T2      B1,*B4[6]
c011fdb6       f005           STW.D2T2      B0,*B4[7]
c011fdb8       1815           STW.D2T2      B1,*B4[8]
c011fdba       3805           STW.D2T2      B0,*B4[9]
c011fdc0       5805           STW.D2T2      B0,*B4[10]
c011fdc2       7805           STW.D2T2      B0,*B4[11]
c011fdc4   008ca362           BNOP.S2       B3,5
```

`c0120dd0` (resume) resets even less software state: it writes the interrupt
enable register, calls an outside helper, loops over channels 1..4 calling
the RX/TX channel-config builders with no teardown request, and sets POWER
bit 6.  It contains no per-slot SRAM store at all.  In particular it clears
none of fields [2], [3], [5], [6], or [7].

Evidence (the resume loop's only relevant calls):

```text
c0120dec       0726           MVK.L1        0,A6
c0120df0   1fff5513           CALLP.S2      0xc0120888,B3
c0120df4       2627 ||        MVK.L2        1,B4
c0120df6       24c0 ||        ADD.L1        A1,1,A4
c0120e00   1ffe7c13           CALLP.S2      0xc01201e0,B3
c0120e04       83c6 ||        MV.L1         A7,A4
c0120e06       2627 ||        MVK.L2        1,B4
c0120e0c       9e2a    [ A0]  BNOP.S1       0xc0120df0,4
```

Accordingly, neither later full endpoint reset nor resume proves that a TX
descriptor left in flight by an expired abort has returned.  Full reset
clears the saved buffer fields while retaining the outstanding count;
resume leaves all of them as-is.

Confidence: **confirmed**.

## 5. Verdict
