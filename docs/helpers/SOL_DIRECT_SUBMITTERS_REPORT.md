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

## 2. Gate

## 3. Does it update field [5]?

## 4. Endpoint/direction

## 5. Verdict
