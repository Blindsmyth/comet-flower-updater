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

**Finding 8 — confirmed.** The real wrapper has four logical basic blocks:
`c014a58c..c014a5ac` (save registers, build the 24-byte temporary, test
input word +4), `c014a5ae..c014a5cc` (zero arguments, dispatch through
`c016b5c0`, copy its result), `c014a5d0` (error value -5), and the merge/
return block `c014a5d2..c014a5d8`.  The `BNOP c014a5d2` at `c014a5cc` has
five delay cycles and therefore does not execute the error-value instruction
at `c014a5d0`; the conditional `BNOP` at `c014a5ac` lands on it.

```text
c014a5ac [A0] BNOP.S1 c014a5d0,5
c014a5b0 CALLP.S2 c016b5c0,B3
c014a5c8 MV.L1    A4,A0
c014a5cc BNOP.S1  c014a5d2,5
c014a5d0 MVK.L1   -5,A0
c014a5d2 MV.L1    A0,A4
c014a5d8 CALLP.S1 c016e000,A3
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

**Finding 6 — confirmed (types by access width; semantic labels likely).**
The four alleged `c014a58c` globals are scalars used by hidden `c014a5e0`,
not endpoint/interface records:

- `c01819bc`: one 32-bit callback pointer, loaded only at `c014a5f8` and
  invoked indirectly at `c014aac4..c014aad0` when non-null.  `refs.txt` has
  no other materialization.
- `c0181ae4`: unsigned 16-bit enable/state flag.  References are
  `c014a614` and `c014ed10`; hidden `c014a5e0` uses it as a boolean selecting
  one accounting-field group.
- `c0181ae8`: unsigned 16-bit flag/mask.  References are `c014a624`,
  `c014ed84`, `c014edcc`, `c014edf4`; hidden `c014a5e0` uses its nonzero
  state and `c014ed00` ANDs it with other masks.
- `c0181f74`: 32-bit mode enum/state, loaded at `c014a620` and dispatched
  as values 0/1/2 (other values take the default).  Other `refs.txt`
  users are `c0140e7c`, `c0144944`, `c0144978`, `c014b690`, `c0150d98`,
  `c01526ac`, `c015a0cc`, `c015e0ac`, `c0161298`, and `c016404c`; the first
  of these stores value 3.  No member offsets are used at any of these four
  addresses, so describing them as structured objects would be wrong.

```text
c014a5f8 LDW.D2T1  *B4[0],A10       ; callback
c014a620 LDW.D1T1  *A5[0],A1        ; 32-bit mode
c014a622 LDHU.D2T2 *B4[0],B4        ; 16-bit flag
c014a62c LDHU.D1T1 *A3[0],A3        ; 16-bit mask
c014a638 CMPEQ.L1  1,A1,A2
c014a648 [A1] CMPEQ.L1 2,A1,A0
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

**Finding 7 — confirmed.** Hidden `c014a5e0`'s first critical section is
`c014a608..c014a750`.  `c016e460` is not a lock/dispatch wrapper: it returns
the CPU `TSCL` cycle counter in `A4`.  With base `S=0xc0182130`, the section
always performs `S[2] += now-S[26]; S[26]=now`, and conditionally performs:

- mode 0 and `c0181ae4 != 0`: `S[19] += now-S[14]; S[14]=now`;
- mode 1 and `c0181ae8 != 0`: `S[10] += now-S[5]; S[5]=now`;
- mode 2 and `c0181aec != 0`: set `S[1]=now`; a table lookup through
  `c01820ec`, indexed by `S[0]`, can additionally add `now-old_S[1]` to the
  selected record's word 4.

Other mode values receive only the common `S[26]/S[2]` update.  No link
pointer is written and no list is linked in this section.  The timestamp/
accounting interpretation is **likely**; the loads, stores, and arithmetic
above are confirmed.

```text
c014a608 DINT
c014a60c CALLP.S2 c016e460,B3       ; A4 = TSCL
c014a734 LDW.D1T1 *+A14[26],A3
c014a738 LDW.D1T1 *+A14[2],A5
c014a740 STW.D1T1 A4,*+A14[26]
c014a746 SUB.L1   A4,A3,A3
c014a748 ADD.L1   A3,A5,A3
c014a750 MVC.S2   B10,CSR
```

**Finding 9 — confirmed except where marked.** The second hidden critical
section is `c014a778..c014a830`.  It reads `S[24]`, `S[25]`, `S[27]`, and
`S[2]`, uses the larger of `S[24]/S[25]`, performs multiply/shift scaling
with constant `0x640`, may call map-confirmed `c0168580` (`rts_udiv32`),
writes the resulting normalized value to `S[28]` (byte offset `0x70`), then
zeros `S[27]` and `S[2]`.  This is counter normalization/rollover **likely**;
the exact high-level formula across the compiler's two branch-to-division
paths is open.  Recovering that formula requires either decompilation with
correct C6000 branch-delay modeling or the original library source; the
field effects themselves are confirmed.

```text
c014a778 DINT
c014a780 LDW.D1T1 *+A14[27],A3
c014a784 LDW.D1T1 *+A14[2],A0
c014a7e0 [A1] B.S1 c0168580
c014a820 STW.D1T1 A4,*+A3[0]        ; A3 = S + 0x70
c014a810 STW.D1T1 A3,*+A14[27]      ; A3 = 0 here
c014a814 STW.D1T1 A3,*+A14[2]
c014a830 MVC.S2   B5,CSR
```

**Finding 10 — confirmed.** When `c0181aec != 0`, hidden `c014a5e0` calls
map-named `c0161200` (`cfg_locked_dispatch`) on `S + *c0181998`, then walks
a circular/sentinel list whose sentinel is `S + *c018199c` and whose next
link is node word 0.  It does **not** link or unlink nodes.  For each selected
record it may call `c016a420` (map name `cfg_option_resolve_dispatch`), then
enters `c014a968..c014a994`: reads `TSCL`, moves record word 4 to word 3,
sets word 4 to zero, moves the old word 5 delta into word 2, and stores the
new timestamp in word 5.  The walk advances with `B10 = B10[0]` and stops at
the sentinel.  The record selection expression is confirmed as
`*((*node[6])[14] + S[0])`; its source-level type is missing.

```text
c014a890 CMPEQ.L2X B10,A3,B0         ; head == sentinel
c014a8a0 [!B0] LDW.D2T2 *+B10[6],B5
c014a8d4 LDW.D2T1 *+B5[B4],A15      ; selected record
c014a968 DINT
c014a974 LDW.D1T1 *+A15[5],A3
c014a980 STW.D1T1 A6,*+A15[4]       ; zero
c014a984 STW.D1T1 A4,*+A15[5]       ; now
c014a998 LDW.D2T2 *+B10[0],B10      ; next
```

**Finding 11 — confirmed.** After the walk (or immediately when
`c0181aec == 0`), the hidden routine increments `S[23]`, then its final
critical section `c014aa0c..c014aa68` reads `TSCL` and snapshots two
conditional accounting groups.  If saved `c0181ae8 != 0`, it performs
`S[8]=now-S[11]; S[9]=S[10]; S[10]=0; S[11]=now`.  If saved
`c0181ae4 != 0`, it performs
`S[17]=now-S[20]; S[18]=S[19]; S[19]=0; S[20]=now`.  CSR is restored before
any subsequent config/callback dispatch.

```text
c014aa08 STW.D1T1 A3,*+A14[23]      ; incremented before DINT
c014aa0c DINT
c014aa10 B.S1     c016e460           ; TSCL
c014aa40 [B0] STW.D1T1 A4,*+A14[11]
c014aa44 [A0] STW.D1T1 A4,*+A14[20]
c014aa60 [B0] STW.D1T1 A6,*+A14[10]
c014aa64 [A0] STW.D1T1 A6,*+A14[19]
c014aa68 MVC.S2   B10,CSR
```

## 4. Callees

**Finding 5 — confirmed.** The direct callees of the real `c014a58c` are:

- `c016e020` / `c016e000`: map-documented register save/restore helpers.
- `c016e6e0`: a veneer to hidden `c016ba40`; with incoming `B4=0` the
  veneer's branch-delay slots substitute `B4=0xc0181180`.  Here it builds a
  24-byte temporary record at `SP+4`, with size/offset argument `B6=8`.
- `c016b5c0`, map name `pend_then_dispatch_0e80_d980`: consumes that
  temporary record via descriptor `0xc0180e80`, generic core `c015a520`, and
  handler `c016d980`.  Its return is the wrapper's return on this path.

The available map has no row/name for hidden `c016ba40`; exactly identifying
the temporary record's library type would require the missing library symbol
or type information.  Its field writes are clear, but calling it an endpoint
record would be an unsupported guess.

```text
c014a594 CALLP.S2 c016e6e0,B3
c014a598 || ADD.L1X 4,B15,A4
c014a5a0 || MVK.D2  0,B4
c014a5a2 || MVK.S1  24,A6
c014a5a4 || MVK.L2  8,B6
c014a5b0 CALLP.S2 c016b5c0,B3
```

## 5. For USB audio

## 6. Proposed map row
