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

## 2. Arguments and globals

## 3. The critical section

## 4. Callees

## 5. For USB audio

## 6. Proposed map row
