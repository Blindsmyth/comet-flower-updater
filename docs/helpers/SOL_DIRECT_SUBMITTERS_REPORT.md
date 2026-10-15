# Ungated TX submitters `c0120c14` and `c01219d0`

Static analysis of `build/fw/map/main.dis`. No device or executable was accessed, no firmware was changed, and nothing was pushed.

## 1. Enclosing routines

**Finding 1a (confirmed routine/callers; likely name and absence of indirect references).** The submit at `c0120c14` is inside the routine starting at the stack-saving prologue `c0120b2c`, named `usb_tx_desc_prepare` in `recon/map/chunk_02.md`. Its complete set of direct `CALLP` callers in `main.dis` is `c0120c94` and `c01219e8`. A whole-file search for the entry address and its low half (`c0120b2c`, `0x0b2c`) found no address-constant or table reference, so none is visible in this disassembly.

```text
c0120b2c       31f7           STW.D2T2      B3,*B15--[2]
c0120b2e       0a46           MV.L1         A4,A16
c0120b30       0c32           MVK.S1        168,A0
c0120b32       2822           SET.S1        A0,9,9,A0
c0120b34   00c00800           MPY32.M1      A0,A16,A1
```

```text
c0120c8c       20a7           CMPEQ.L2      -1,B0,B0
c0120c8e       a24a    [!B0]  BNOP.S1       0xc0120c98,5
c0120c94       eadb           CALLP.S2      0xc0120b2c,B3
c0120c96       9086 ||        MV.L1         A2,A4
```

```text
c01219e0   1ffdbd13           CALLP.S2      0xc01207c8,B3
c01219e4   02240fd8 ||        MV.L1         A9,A4
c01219e8   1ffe2993           CALLP.S2      0xc0120b2c,B3
c01219ec       8486 ||        MV.L1         A9,A4
c01219ee       71f7           LDW.D2T2      *++B15[2],B3
```

Confidence: **confirmed** for the boundary and direct callers; **likely** for the semantic name and absence of indirect references.

**Finding 1b (confirmed routine/caller; likely name and absence of indirect references).** The submit at `c01219d0` is inside the routine starting at prologue `c0121960`, named `usb_queue_service_case_d` in `recon/map/chunk_02.md`. Its sole direct caller is `c0121b38`, within `c01219f4`'s event-dispatch body. A whole-file search for `c0121960` and `0x1960` found no code-address constant or table reference: the apparent `c0166a18` low-half match is completed with `MVKH 0xc0180000` at `c0166a24`, hence denotes data address `0xc0181960`, not this code entry.

```text
c0121960       31f7           STW.D2T2      B3,*B15--[2]
c0121962       2646           MV.L1         A4,A9
c0121964       0c32           MVK.S1        168,A0
c0121966       2822           SET.S1        A0,9,9,A0
c0121968   03240570           MPYLI.M1      A0,A9,A7:A6
```

```text
c0121b30       e023           SET.S2        B0,7,7,B0
c0121b32       9587 ||        MV.L2X        A11,B4
c0121b34       1005           STW.D2T2      B0,*B4[0]
c0121b36       a50a           BNOP.S1       0xc0121b48,5
c0121b38       e41b           CALLP.S2      0xc0121960,B3
c0121b3a       8506 ||        MV.L1         A10,A4
```

```text
c0166a18   240cb02a || [ B0]  MVK.S2        0x1960,B8
c0166a24   24600c6b || [ B0]  MVKH.S2       0xc0180000,B8
c0166a30   222002e4 || [ B0]  LDW.D2T1      *+B8[0],A4
```

Confidence: **confirmed** for the boundary, sole direct caller, and rejection of the `0xc0181960` false match; **likely** for the semantic name and absence of other indirect references.

## 2. Gate

**Finding 2a (confirmed).** On the `c0120c44` caller route, `c0120c14` is reached exactly when the masked slot is nonzero, TX field [2] is nonzero, the pre-call TX field [9] is exactly `-1`, and the caller-supplied `B4` value (stored into field [5] at `c0120c88`) is nonzero. Thus this route does depend on fields [9] and [5], but field [5] is a positive trigger, not a `field[5] == 0` ownership gate. It has no field-[3] or queue-state predicate before the call.

| Predicate | Result |
|---|---|
| slot = 0 or field [2] = 0 | error return; no submit |
| field [9] >= 0 | error return; no field-[5] store; no submit |
| field [9] < 0 but field [9] != -1 | store caller `B4` to field [5], return without submit |
| field [9] = -1, caller `B4` = 0 | call `c0120b2c`, whose field-[5] test returns without submit |
| field [9] = -1, caller `B4` != 0 | reach `c0120c14` |

```text
c0120c6c   001042e6           LDW.D2T2      *+B4[2],B0
c0120c70   3010a120    [!B0]  BNOP.S1       0xc0120c80,5
c0120c74       380d           LDW.D2T2      *B4[9],B0
c0120c76       5027           CMPGT.L2      0,B0,B0
c0120c78   2014a120    [ B0]  BNOP.S1       0xc0120c88,5
```

Here `CMPGT 0,field[9]` means `field[9] < 0`; the `[B0]` branch enters the negative-state path.

```text
c0120c88       b015           STW.D2T2      B1,*B4[5]
c0120c8a       380d           LDW.D2T2      *B4[9],B0
c0120c8c   0003ea5a           CMPEQ.L2      -1,B0,B0
c0120c90   300ca120    [!B0]  BNOP.S1       0xc0120c98,5
c0120c94       eadb           CALLP.S2      0xc0120b2c,B3
```

```text
c0120b5a       9487           MV.L2X        A9,B4
c0120b60       a00d           LDW.D2T1      *B4[5],A0
c0120b64       db7a    [!A0]  BNOP.S1       0xc0120c3a,5
```

Confidence: **confirmed**.

**Finding 2b (confirmed).** `c01219d0` uses the upstream queue-event route detailed in Finding 2c through the case-D call at `c0121b38`: valid popped type-16 descriptor, slot 1..4, `A15 != 0`, and TX field [2] != 0. Within `c0121960`, it reaches the submit exactly when TX field [9] is nonnegative. Field [8] controls only whether the incremented ring index wraps to zero. There is no field-[5] or field-[3] predicate, and the earlier `c0120550` call cannot change field [5] on this route because field [2] is nonzero. Queue 28 availability is tested only inside `c0120250` (`c0120260..0270`), after this call site has been reached.

| Case-D state | Result |
|---|---|
| field [9] < 0 | branch to reset path at `c01219d8`; no `c01219d0` submit |
| field [9] >= 0, incremented index < field [8] | store incremented index; reach `c01219d0` |
| field [9] >= 0, incremented index >= field [8] | wrap field [9] to zero; reach `c01219d0` |
| any field [5] or field [3] value on either nonnegative row | unchanged gate result |

```text
c0121978       389d           LDW.D2T2      *B5[9],B1
c012197a       50a7           CMPGT.L2      0,B1,B0
c0121980   202ca120    [ B0]  BNOP.S1       0xc01219d8,5
c0121984       18ad           LDW.D2T2      *B5[8],B2
c0121986       2481           ADD.L2        B1,1,B0
c0121988       3885           STW.D2T2      B0,*B5[9]
```

```text
c012198c   00080afa           CMPLT.L2      B0,B2,B0
c0121990   200ca120    [ B0]  BNOP.S1       0xc0121998,5
c0121994       0427           MVK.L2        0,B0
c0121996       3885           STW.D2T2      B0,*B5[9]
c0121998       388d           LDW.D2T2      *B5[9],B0
```

```text
c01219c4       586d           LDW.D2T2      *B4[10],B6
c01219c6       0081           ADD.L2        B0,B1,B0
c01219c8       9487           MV.L2X        A9,B4
c01219ca       2040           ADD.L1        A1,A0,A4
c01219d0   1ffd1213 ||        CALLP.S2      0xc0120250,B3
c01219d4       d056 ||        MV.D1X        B0,A6
```

Confidence: **confirmed**.

**Finding 2c (confirmed).** The other route to `c0120c14` begins in `c01219f4` and is queue-driven. It requires a nonempty input queue (`c011fa20` returns an index >= 0), a type-16 descriptor (`c011fa54` true), extracted slot 1..4, incoming dispatch flag `A15 != 0`, and TX field [2] != 0. The dispatcher calls `c0120550` first, but that routine skips all field-[5] accounting when field [2] != 0. In `c0121960`, entry field [9] < 0 skips `c01219d0`, runs `c01207c8` (which resets I/O field [9] to `-1` and clears TX field [3]), then calls `c0120b2c`; its final gate is again only field [5] != 0. Field [3] is written, not tested. Therefore this route reaches `c0120c14` for any positive/nonzero field [5], even though that same value can denote an outstanding count.

| Queue-event predicates after a valid type-16 pop | Result |
|---|---|
| slot outside 1..4 | no case-D call |
| `A15 == 0` | RX-side dispatch, no case-D call |
| `A15 != 0`, TX field [2] = 0 | case C/state-update path, no case-D call |
| `A15 != 0`, TX field [2] != 0, field [9] >= 0 | case D reaches `c01219d0`, not `c0120c14` |
| same, field [9] < 0, field [5] = 0 | reset path calls `c0120b2c`, which returns without submit |
| same, field [9] < 0, field [5] != 0 | reset path reaches `c0120c14` |

```text
c0121a94       0626           MVK.L1        0,A4
c0121a96       0786           MV.L1         A15,A0
c0121a98       ae2a    [ A0]  BNOP.S1       0xc0121af0,5
c0121af0       0c33           MVK.S2        168,B0
c0121b00   0014c228           MVK.S1        0x2984,A0
c0121b04   006008e8           MVKH.S1       0xc0110000,A0
```

```text
c0121a04   1ffc0412           CALLP.S2      0xc011fa20,B3
c0121a08       5226           CMPGT.L1      0,A4,A0
c0121a0a       833a    [!A0]  BNOP.S1       0xc0121a18,4
c0121a10   00a48120           BNOP.S1       0xc0121b48,4
c0121a18   1ffc0a92           CALLP.S2      0xc011fa54,B3
c0121a20       0246           MV.L1         A4,A0
c0121a22       a32a    [ A0]  BNOP.S1       0xc0121a38,5
```

```text
c0121b00   0014c228           MVK.S1        0x2984,A0
c0121b04   006008e8           MVKH.S1       0xc0110000,A0
c0121b0a       1050           ADD.L1X       A0,B0,A5
c0121b0c       008c           LDW.D1T1      *A5[0],A0
c0121b10       a72a    [ A0]  BNOP.S1       0xc0121b38,5
c0121b38       e41b           CALLP.S2      0xc0121960,B3
```

`0xc0112984 + 0x2a8*N` is TX field [2]. On the required nonzero row, `c0120550` takes its first branch and cannot decrement field [5]:

```text
c01205e0       400c ||        LDW.D1T1      *A4[2],A0
c01205e2       a72a    [ A0]  BNOP.S1       0xc0120618,5
c01205e6       a01c           LDW.D1T1      *A4[5],A1
c01205e8       10a6           CMPLT.L1      0,A1,A0
```

```text
c0121978       389d           LDW.D2T2      *B5[9],B1
c012197a       50a7           CMPGT.L2      0,B1,B0
c0121980   202ca120    [ B0]  BNOP.S1       0xc01219d8,5
c01219d8   1ffd8d12           CALLP.S2      0xc0120628,B3
c01219e0   1ffdbd13           CALLP.S2      0xc01207c8,B3
c01219e8   1ffe2993           CALLP.S2      0xc0120b2c,B3
```

Confidence: **confirmed**.

## 3. Does it update field [5]?

**Finding 3a (confirmed).** A successful `c0120c14` submit does **not** increment TX field [5]. `c0120250` returns zero on success (`c0120324`); the zero row falls through at `c0120c28`, stores field [3] = 3 and calls `c01200f4`. Both success and failure then execute `c0120c38`, which sets field [5] to zero. This is the opposite of the normal post-success increment at `c01204aa..04ae`.

```text
c0120318   1ffeee13           CALLP.S2      0xc011fa70,B3
c0120320       01cc ||        LDW.D1T1      *A7[0],A4
c0120322       83c7 ||        MV.L2         B7,B4
c0120324       0626           MVK.L1        0,A4
```

```text
c0120c26       0246           MV.L1         A4,A0
c0120c28       a2aa    [ A0]  BNOP.S1       0xc0120c34,5
c0120c2c       6013 ||        MVK.S2        3,B0
c0120c2e       7005           STW.D2T2      B0,*B4[3]
c0120c30   1ffe9a92           CALLP.S2      0xc01200f4,B3
c0120c34       9487           MV.L2X        A9,B4
c0120c36       1407           MV.L2X        A8,B0
c0120c38       b005           STW.D2T2      B0,*B4[5]
```

For comparison, the ordinary wrapper increments only after `c0120250` returns success:

```text
c01204a2       0246           MV.L1         A4,A0
c01204a4       a54a    [ A0]  BNOP.S1       0xc01204b0,5
c01204aa       b00d           LDW.D2T2      *B4[5],B0
c01204ac       2401           ADD.L2        B0,1,B0
c01204ae       b005           STW.D2T2      B0,*B4[5]
```

The descriptor still returns through queue 24, then the Hwi forwards it to queue 32 when field [2] is zero or queue 34 when field [2] is nonzero. The `c01219f4` consumer calls `c0120550`, but that function decrements only if field [2] == 0 and signed field [5] > 0. Consequently this descriptor has no dedicated count: with field [5] still zero it is ignored; if another operation has made the aggregate positive, its return can decrement that aggregate instead. The positive-only guard prevents this path from making field [5] negative or wrapping through zero, but it does not prevent undercount or cross-accounting.

```text
c011fb70       03c6           MV.L1         A7,A0
c011fb72       a36a    [ A0]  BNOP.S1       0xc011fb7a,5
c011fb74       f11b           CALLP.S2      0xc011fa70,B3
c011fb76       8346 ||        MV.L1         A6,A4
c011fb7a       f11b           CALLP.S2      0xc011fa70,B3
c011fb80       4232 ||        MVK.S1        34,A4
```

```text
c01205e0       400c ||        LDW.D1T1      *A4[2],A0
c01205e2       a72a    [ A0]  BNOP.S1       0xc0120618,5
c01205e6       a01c           LDW.D1T1      *A4[5],A1
c01205e8       10a6           CMPLT.L1      0,A1,A0
c01205ea       a73a    [!A0]  BNOP.S1       0xc0120618,5
c01205ec       ec80           ADD.L1        A1,-1,A0
c01205f0       a004           STW.D1T1      A0,*A4[5]
```

Confidence: **confirmed**.

**Finding 3b (confirmed).** A successful `c01219d0` submit also does **not** increment field [5]. The next instruction is an unconditional branch to the epilogue, so the `c0120250` result is ignored and there is no post-success state update at all. Its completion follows the same queue 24 -> 32/34 -> `c0120550` path described above. Because submission required field [2] != 0, an unchanged field [2] routes the return to queue 34 and makes `c0120550` skip field [5]. If field [2] becomes zero before Hwi/consumer processing, the return may decrement whatever positive aggregate is then present; zero or negative values are skipped. It therefore cannot drive field [5] negative or wrap through zero, but the newly submitted descriptor is uncounted and can be cross-accounted against another positive value.

```text
c01219c8       9487           MV.L2X        A9,B4
c01219ca       2040           ADD.L1        A1,A0,A4
c01219cc   04000029 ||        MVK.S1        0x0000,A8
c01219d0   1ffd1213 ||        CALLP.S2      0xc0120250,B3
c01219d4       d056 ||        MV.D1X        B0,A6
c01219d6       a5ca           BNOP.S1       0xc01219ee,5
c01219ee       71f7           LDW.D2T2      *++B15[2],B3
```

The Hwi's queue choice is controlled by the live field [2] value loaded into `A7`:

```text
c011fb0c       2040           ADD.L1        A1,A0,A4
c011fb0e       007c           LDW.D1T1      *A4[0],A7
c011fb70       03c6           MV.L1         A7,A0
c011fb72       a36a    [ A0]  BNOP.S1       0xc011fb7a,5
c011fb74       f11b           CALLP.S2      0xc011fa70,B3
c011fb76       8346 ||        MV.L1         A6,A4
c011fb7a       f11b           CALLP.S2      0xc011fa70,B3
c011fb80       4232 ||        MVK.S1        34,A4
```

Confidence: **confirmed**.

## 4. Endpoint/direction

**Finding 4 (confirmed direction/range and ZLP capability; likely MIDI semantic label).** Both sites are generic **TX/device-to-host data** paths over the valid non-EP0 software-slot domain 1..4, not RX refill paths. `c0120b2c` derives the `0xc011297c + 0x2a8*N` TX record from slot `N`; `c0121960` names that base directly. Both sites index the TX template array at `0xc01805c4 + 12*N` and call the common descriptor builder. The event route explicitly enforces slot 1..4 at `c0121a84..90`; the untraced kick rejects slot zero at `c0120c50` but has no visible upper-bound check, so it relies on its caller to honor the 1..4 table domain. Slot 4 is included but not special: its template at `c01805f4` submits to queue 22 and returns normally to queue 24. Per the established endpoint map supplied with this investigation, slot 4 is MIDI IN, so these sites can transmit MIDI IN data but also serve TX slots 1..3.

```text
c0120c4c   0001ef58           AND.L1        15,A0,A0
c0120c50   d020a120    [!A0]  BNOP.S1       0xc0120c80,5
c0121a84       1507           MV.L2X        A10,B0
c0121a86       1027           CMPLT.L2      0,B0,B0
c0121a88   3063a120    [!B0]  BNOP.S1       0xc0121b46,5
c0121a8c   00289ada           CMPLT.L2X     4,A10,B0
c0121a90   2063a120    [ B0]  BNOP.S1       0xc0121b46,5
```

```text
c0120b30       0c32           MVK.S1        168,A0
c0120b32       2822           SET.S1        A0,9,9,A0
c0120b34   00c00800           MPY32.M1      A0,A16,A1
c0120b38   0016042a           MVK.S2        0x2c08,B0
c0120b40   006008ea           MVKH.S2       0xc0110000,B0
c0120b44       8c12           MVK.S1        140,A0
c0120b4a       2822           SET.S1        A0,9,9,A0
c0120b4c   048012f8           SUB.L1X       B0,A0,A9
```

Here `SET 168,9,9` produces `0x2a8`, and the second `SET`-derived constant is `0x28c`, so `A9 = 0xc0112c08 + 0x2a8*N - 0x28c = 0xc011297c + 0x2a8*N`.

```text
c0121964       0c32           MVK.S1        168,A0
c0121966       2822           SET.S1        A0,9,9,A0
c0121968   03240570           MPYLI.M1      A0,A9,A7:A6
c012196c   0014be2a           MVK.S2        0x297c,B0
c0121970   006008ea           MVKH.S2       0xc0110000,B0
c0121976       1351           ADD.L2X       B0,A6,B5
```

```text
c01805d0   00000010           .word 0x00000010
c01805d4   00000018           .word 0x00000018
c01805d8   00000019           .word 0x00000019
c01805e8   00000014           .word 0x00000014
c01805ec   00000018           .word 0x00000018
c01805f0   00000019           .word 0x00000019
c01805f4   00000016           .word 0x00000016
c01805f8   00000018           .word 0x00000018
```

The last omitted word of slot 4 is teardown-return queue 25 at `c01805fc`; the shown slot-4 words are submit queue 22 and normal-return queue 24.

```text
c01202c6       218c           LDW.D1T1      *A7[1],A0
c01202d0   00029408           EXTU.S1       A0,20,20,A0
c01202d4       14a8           OR.L1X        A0,B1,A0
c01202da       4005           STW.D2T1      A0,*B4[2]
c0120320       01cc ||        LDW.D1T1      *A7[0],A4
c0120322       83c7 ||        MV.L2         B7,B4
```

Neither call site requires a positive length. Both load TX field [10] into `B6`; `c0120250` masks that value into descriptor word 0 without a zero test. Therefore these are data-descriptor paths that can also emit a zero-length packet when field [10] is zero, rather than dedicated ZLP routines.

```text
c0120c0e       c06d           LDW.D2T1      *B4[6],A6
c0120c14   1ffeca13           CALLP.S2      0xc0120250,B3
c0120c18       586d ||        LDW.D2T2      *B4[10],B6
c01219c4       586d           LDW.D2T2      *B4[10],B6
c01219d0   1ffd1213 ||        CALLP.S2      0xc0120250,B3
```

```text
c0120252       a347           MV.L2         B6,B5
c01202b0   01154a0a           EXTU.S2       B5,10,10,B2
c01202b4   000bff8a           SET.S2        B2,31,31,B0
c01202b8   001002f6           STW.D2T2      B0,*+B4[0]
```

Confidence: **confirmed** for TX table, slot range, queue values and lack of a length gate; **likely** for the higher-level MIDI IN label inherited from the endpoint map.

## 5. Verdict

**Finding 5 (confirmed mechanics; verdict unknown for both sites).**

- **`c0120c14`: unknown.** Its visible `c01219f4 -> c0121960 -> c0120b2c` route is completion-driven: queue 34 is popped before the routine runs, so the descriptor that triggered that route is no longer DMA-owned. However, the other immediate caller is the hidden-start kick `c0120c44`, for which no direct caller or code-address/table reference was found. That kick overwrites field [5] and submits when field [9] is `-1`; `c011fd40` can set field [9] to `-1` without touching field [5], exactly the state left by the corrected expiry scenario while a descriptor may remain owned. If this untraced kick is invoked in that state, it can submit concurrently; the static call/reference evidence does not establish whether it is invoked. Therefore neither “yes, reachable” nor “no, impossible” is proved.
- **`c01219d0`: unknown.** Its sole caller is reached from the queue-34 consumer (`c01221a0` calls `c01219f4` with `A4=1`), so the particular descriptor that caused the event has returned from DMA. This proves it does not overlap that descriptor. But the site ignores field [5], and no checked predicate proves that a *second* descriptor for the same slot cannot remain DMA-owned. The public enqueue's one-at-a-time invariant is insufficient once `c0120c14` can create an uncounted descriptor. No concrete fully referenced trigger proves such a two-descriptor state, so “yes” is also not established.

Evidence that the TX event body is invoked on queue 34 with nonzero `A4` (becoming `A15`):

```text
c012219a       4233           MVK.S2        34,B4
c01221a0   1fff0a93           CALLP.S2      0xc01219f4,B3
c01221a4       2626 ||        MVK.L1        1,A4
c01221a6       c68e ||        MV.S1         A13,A6
c01221a8       d607 ||        MV.L2X        A12,B6
```

Evidence that the consumer pops/tests the already-returned queue entry before dispatch:

```text
c01219fa       e646           MV.L1         A4,A15
c0121a02       9256 ||        MV.D1X        B4,A4
c0121a04   1ffc0412           CALLP.S2      0xc011fa20,B3
c0121a18   1ffc0a92           CALLP.S2      0xc011fa54,B3
c0121a22       a32a    [ A0]  BNOP.S1       0xc0121a38,5
```

Evidence that the reset writes fields [6], [7], [8] and [9], but not outstanding field [5]:

```text
c011fd60       0426 ||        MVK.L1        0,A0
c011fd62       c005           STW.D2T1      A0,*B4[6]
c011fd64       e005           STW.D2T1      A0,*B4[7]
c011fd68       1825           STW.D2T2      B2,*B4[8]
c011fd74       fca7 ||        MVK.L2        -1,B1
c011fd80       3815 ||        STW.D2T2      B1,*B4[9]
```

Confidence: **confirmed** for the queue-before-dispatch ordering, reset stores, and absence of a local field-[5] gate; **unknown** for actual concurrent ownership because the kick trigger and global uniqueness invariant are not recoverable from the visible references.
