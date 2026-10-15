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

**Finding 2b (confirmed).** The other route to `c0120c14` begins in `c01219f4` and is queue-driven. It requires a nonempty input queue (`c011fa20` returns an index >= 0), a type-16 descriptor (`c011fa54` true), extracted slot 1..4, incoming dispatch flag `A15 == 0`, and TX field [2] != 0. The dispatcher calls `c0120550` first, but that routine skips all field-[5] accounting when field [2] != 0. In `c0121960`, entry field [9] < 0 skips `c01219d0`, runs `c01207c8` (which resets I/O field [9] to `-1` and clears TX field [3]), then calls `c0120b2c`; its final gate is again only field [5] != 0. Field [3] is written, not tested. Therefore this route reaches `c0120c14` for any positive/nonzero field [5], even though that same value can denote an outstanding count.

| Queue-event predicates after a valid type-16 pop | Result |
|---|---|
| slot outside 1..4 | no case-D call |
| `A15 != 0` | RX-side dispatch, no case-D call |
| `A15 == 0`, TX field [2] = 0 | case C/state-update path, no case-D call |
| `A15 == 0`, TX field [2] != 0, field [9] >= 0 | case D reaches `c01219d0`, not `c0120c14` |
| same, field [9] < 0, field [5] = 0 | reset path calls `c0120b2c`, which returns without submit |
| same, field [9] < 0, field [5] != 0 | reset path reaches `c0120c14` |

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

## 4. Endpoint/direction

## 5. Verdict
