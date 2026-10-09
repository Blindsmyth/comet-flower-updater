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

### Finding 2.1 — registry, pointer vector, and ownership maps

The structures are:

| address | layout | writer / contents |
|---|---|---|
| `c011aa18` | 3 words, indexed by slot 0..2 | handler-record pointers; `c015c66c` writes `record` at `[slot]`, and `c015c804` returns this base to dispatchers |
| `c011aa28` | 3 entries × 8 bytes | persistent registry entries `{selector, record_pointer}`; allocated/removed/compacted by `c015c6b4` |
| `c011aa40` | 32 words | endpoint-address ownership map; values are slot indices or `-1` |
| `c011aac0` | 6 addressable words | interface-number ownership map; values are slot indices or `-1` |

The three-entry capacity follows both the `MVK 3` registry scan/replay and the
slot values generated at `c015c764` (0, 1, 2).  **Confidence: confirmed.**

```text
c015c6c4 MVK   c011aa28,B0
c015c6d2 MVK   3,B0             ; three 8-byte registry entries
c015c6e0 LDNDW *A4(0),A1:A0
c015c6f8 ADD   A4,8,A4
c015c754 MVK   3,A2             ; replay three entries
c015c764 ADD   B1,1,A6          ; replay slot 0, then 1, then 2
c015c698 MVK   c011aa18,A5
c015c6a4 STW   B0,*A5[A4]       ; record_pointer[slot]
```

For selector 6, stock `c015c66c` hard-codes four ownership writes: endpoint
map index 3 (`c011aa4c`, EP3 OUT), endpoint map index 20 (`c011aa90`, EP4 IN),
and interface-map indices 0 and 1 (`c011aac0`/`c011aac4`).  All four receive
the current slot index.  **Confidence: confirmed.**

```text
c015c684 STW   A4,*c011aa4c     ; endpoint-map[3] = slot
c015c686 MVK   68,B4
c015c688 ADD   B4,A5,B4
c015c68a STW   A4,*B4           ; endpoint-map[20] = slot (aa4c+68=aa90)
c015c68c MVK   c011aac0,B4
c015c694 MV    A4,A5
c015c696 STDW  A5:A4,*B4        ; interface-map[0]=[1]=slot
```

`c015c620` fills the endpoint map with `-1` using `SPLOOPD` with ILC 28,
which is 32 iterations under the specified ILC+4 rule.  Interface lookup
accepts indices 0..5, but its reset uses ILC 1 and therefore writes only five
words (indices 0..4); index 5 is not explicitly reset here.  This is a stock
edge-case/bug, immaterial to IF2/IF3 but relevant to the nominal six-entry
capacity.  `c011aa18` is cleared to zero before registry replay.
**Confidence: confirmed.**

```text
c015c622 MVK     32,B0
c015c628 ADD     B0,-4,B0       ; ILC=28; SPLOOPD => 32 stores
c015c630 SPLOOPD 1
c015c638 MVK     c011aac0,A4
c015c640 MVK     1,B0           ; ILC=1; SPLOOPD => 5 stores
c015c648 SPLOOPD 1
c015c7d8 CMPGT   6,A1,A0        ; interface indices 0..5 accepted
```

## 3. Record lookup by recipient and `wIndex`

## 4. Uses of the other record words

## 5. USB audio registration recipe
