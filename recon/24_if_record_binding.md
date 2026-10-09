# USB Handler Record Binding to Interfaces

## 1. Meaning of `A4=6` and `c015afa0` arguments

### Finding 1.1 — `c015afa0` has only two live arguments

`c015afa0` is a tail-like veneer which forwards the incoming `A4` and `B4`
unchanged through `c0138a6c` to `c015c6b4`.  Thus its full live argument list
is `A4=registration selector`, `B4=record pointer (or 0 to remove that
selector)`.  `A6`, `B6`, `A8`, `B8`, and `B10` are **not** arguments to this
function: `c015afa8..afaa` restore/return, `c015afac` is the next function's
entry, and only that next function reads those registers at
`c015afb4..afc8`.  **Confidence: confirmed.**

```text
c015afa0 STW   B3,*B15--[2]
c015afa4 CALLP c0138a6c,B3
c015afa8 LDW   *++B15[2],B3
c015afaa BNOP  B3,5
c015afac CALLP c016e020,A3       ; next function / prologue
c015afb4 MV    A4,A2 || MV A6,A0 ; its argument saves begin here
```

### Finding 1.2 — selector 6 means this interface/endpoint handler-map class

`6` is a registry selector/type tag.  `c015c6b4` stores it in word 0 of an
8-byte registry entry and, on the `B4=0` path, finds and removes entries whose
word 0 equals the incoming selector.  During map reconstruction it passes that
stored selector to `c015c66c`, whose only accepted selector is 6.  It is
therefore neither `bInterfaceNumber` (the stock record serves interfaces 0
and 1), nor a USB class code, nor a count.  The exact SDK enum name is not
recoverable from these inputs.  **Confidence: confirmed** for tag semantics;
**likely** for the descriptive name “interface/endpoint handler-map class.”

```text
c015c6e8 LDW   *A4[0],A0
c015c6ec CMPEQ A0,A2,A0          ; registry tag == requested tag
c015c6f2 STW   0,*A4[0]          ; remove matching 8-byte entry
c015c760 CALLP c015c66c,B3
c015c762 LDW   *A7[0],A4         ; replay stored selector
c015c672 CMPEQ 6,A0,A0           ; only selector 6 is accepted
```

## 2. Registration tables

## 3. Record lookup by recipient and `wIndex`

## 4. Uses of the other record words

## 5. USB audio registration recipe
