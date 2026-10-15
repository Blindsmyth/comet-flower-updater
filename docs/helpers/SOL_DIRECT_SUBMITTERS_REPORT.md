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

## 3. Does it update field [5]?

## 4. Endpoint/direction

## 5. Verdict
