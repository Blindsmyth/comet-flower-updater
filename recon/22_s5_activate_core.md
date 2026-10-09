# c014a58c activation core analysis

## 1. Structure

**Finding 1 — confirmed.** The map's 1,396-byte `c014a58c` extent contains
two functions.  The public entry `c014a58c` ends at the save/restore-helper
call at `c014a5d8`; `c014a5e0` is a separate hidden entry, reached by a
conditional direct branch at `c015fd68`.  Therefore none of the DINT/list
logic beginning at `c014a5e0` belongs to `c014a58c`.

```text
c014a5d0 MVK.L1   -5,A0
c014a5d2 MV.L1    A0,A4
c014a5d8 CALLP.S1 c016e000,A3       ; restore/return helper
c014a5e0 STW.D2T1 A11,*B15--[2]     ; hidden function prologue
...
c015fd68 [!A0] B.S1 c014a5e0        ; external entry reference
```

**Finding 2 — confirmed.** `c014a58c` has two exits.  If the word at input
`A4+4` is nonzero it returns `A4 = -5`.  Otherwise it invokes `c016b5c0`
and returns that callee's `A4` unchanged.  The stronger old claim that the
success path is necessarily zero is not proved here; that would require
closing the generic dispatch reached through `c016b5c0`.

```text
c014a5a8 LDW.D1T1 *A4[1],A0         ; byte offset +4
c014a5ac [A0] BNOP.S1 c014a5d0,5
c014a5b0 CALLP.S2 c016b5c0,B3
c014a5cc BNOP.S1  c014a5d2,5
c014a5d0 MVK.L1   -5,A0
c014a5d2 MV.L1    A0,A4
```

## 2. Arguments and globals

**Finding 3 — confirmed.** The sole direct caller at `c0149f78` passes
`A4 = 0xc0180534`.  Entry `B4` and `A6` are not arguments: `c014a58c`
overwrites both in the parallel setup for its first call before reading
either.  Only the descriptor/control pointer in `A4` survives in `A10`.

```text
c0149f74 MVK.S1   0x0534,A4
c0149f78 CALLP.S2 c014a58c,B3
c0149f80 MVKH.S1  0xc0180000,A4
c014a592 MV.L1    A4,A10
c014a5a0 MVK.D2   0,B4
c014a5a2 MVK.S1   24,A6
```

**Finding 4 — confirmed.** `c014a58c` touches none of
`c01819bc/c0181ae4/c0181ae8/c0181f74` and contains no DINT/RINT region.
Those accesses are all after the hidden start `c014a5e0`.  Consequently the
brief's critical-section and global questions apply to that separate routine,
not to USB interface activation.

```text
c014a5d8 CALLP.S1 c016e000,A3       ; c014a58c ends
c014a5e0 STW.D2T1 A11,*B15--[2]     ; separate entry
c014a5f0 MVK.S2   0x19bc,B4
c014a5f8 LDW.D2T1 *B4[0],A10
c014a608 DINT
c014a60c CALLP.S2 c016e460,B3
```

## 3. The critical section

There is no critical section in `c014a58c`.  For completeness, the sections
formerly attributed to it are analyzed below under the hidden `c014a5e0`
entry.

## 4. Callees

## 5. For USB audio

## 6. Proposed map row
