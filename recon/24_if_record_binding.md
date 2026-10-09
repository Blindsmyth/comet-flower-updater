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

### Finding 3.1 — two-stage lookup; `wIndex` is the key, not a descriptor walk

The SETUP decoder extracts `recipient = bmRequestType & 0x1f` and admits
recipients 1..3 to the registered-handler path.  It asks `c015c804` for the
record-pointer-vector base, then calls `c015c788(&slot, recipient, wIndex)`;
the halfword at stack-scaled `[8]` is SETUP byte offset 4, i.e. `wIndex`.
On success it resolves `record = record_vector[slot]` and calls
`record[3]` (+12).  **Confidence: confirmed.**

```text
c01359f4 LDBU  *+B15[12],B0     ; bmRequestType
c01359f8 EXTU  B0,27,27,B1      ; recipient (low five bits)
c0135a18 CALLP c015c804,B3      ; record-vector base -> stack +8
c0135a28 CALLP c015c788,B3
c0135a2c LDHU  *+B15[8],A6      ; scaled HU address = stack+16 = wIndex
c0135a34 MV    A11,B4           ; recipient
c0135a46 LDW   *B4[B5],B0       ; record_vector[slot]
c0135a52 LDW   *B4[3],B0        ; callback at +12
```

Truth table for `c015c788`:

| recipient | key derived from `wIndex` | table | result |
|---:|---|---|---|
| 1 (interface) | low byte, required `< 6` | `c011aac0[key]` | slot on non-`-1`; otherwise `ffff8acc` |
| 2 (endpoint) | `(wIndex & 0x0f) + (bit7 ? 16 : 0)`, required `< 32` | `c011aa40[key]` | slot on non-`-1`; otherwise `ffff8acc` |
| 3 (other) | none | none | always `ffff8acc` |

**Confidence: confirmed.**

```text
c015c790 CMPEQ 1,B1,B0          ; interface recipient
c015c7d4 EXTU  A1,24,24,A1      ; low byte of wIndex
c015c7d8 CMPGT 6,A1,A0
c015c7e4 MVK   c011aac0,A5
c015c798 CMPEQ 2,B1,B0          ; endpoint recipient
c015c7a4 EXTU  A1,24,31,A0      ; endpoint-direction bit
c015c7b0 AND   A1,15,A0
c015c7c0 MVK   c011aa40,A5
```

No configuration descriptor is consulted in this lookup.  The descriptor's
`bInterfaceNumber` matters only because the host copies that value into
`wIndex`; routing itself is a direct lookup in the fixed ownership map.  The
stock selector-6 writer populates only interface keys 0 and 1, so IF2/IF3
cannot be reached until map entries 2 and 3 are populated.  **Confidence:
confirmed.**

## 4. Uses of the other record words

### Finding 4.1 — field call sites and safe-stub requirements

| record field | stock target | observed use | requirement for new IF2/IF3 record |
|---|---|---|---|
| +0 | `c0151ecc` | no load/call found in any of the six `c015c804` consumers | return-0 stub is safe |
| +4 | `c0151e80` | no load/call found in any of the six `c015c804` consumers | return-0 stub is safe |
| +8 | `c0151ff4` | lifecycle/event hook, called while walking every non-null record | non-null return-0 stub unless audio needs these events |
| +12 | `c0151ed0` | SETUP request callback selected by recipient/`wIndex` | IF-specific request callback |
| +16 | `c0151e84` | endpoint-descriptor hook selected through endpoint ownership | non-null return-0 stub is safe if custom audio code owns EP1 setup |

The stock +0 and +4 targets themselves are exactly return-zero stubs.
**Confidence: confirmed.**

```text
c0151e80 MVK  0,A4             ; +4
c0151e82 BNOP B3,5
c0151ecc MVK  0,A4             ; +0
c0151ece BNOP B3,5
```

The +8 hook is loaded as `record[2]` in four walkers.  Their observed first
arguments are event codes 0 (`c015e8f4`), 1 (`c015e990`), 2 (`c015ea38`),
and 3 (`c0135798`); the calls skip a null field.  Event 3 also receives the
SET_CONFIGURATION `wValue` in `B4`.  Exact SDK event names for codes 0..2
are not recoverable here.  **Confidence: confirmed** for calling convention
and codes; **guess** for the generic label “lifecycle/event.”

```text
c015e8e4 LDW   *B5[2],B0       ; record +8
c015e8ec BNOP  B0,0
c015e8f0 ADDKPC c015e8f8,B3,2
c015e8f4 MVK   0,A4
c015e980 LDW   *B5[2],B0
c015e98c ADDKPC c015e994,B3,2
c015e990 MVK   1,A4
```

The +16 hook is called while configuring each endpoint descriptor.  It gets
`A4=bEndpointAddress`, `B4=bmAttributes`, and `A6=wMaxPacketSize` (the latter
two loads use access-size-scaled descriptor offsets).  **Confidence:
confirmed.**

```text
c01358d2 LDBU  *A4[2],A6       ; endpoint-address key for lookup
c01358f2 LDW   *B4[4],B0       ; record +16
c0135900 MV    A11,A4          ; endpoint descriptor
c0135902 LDBU  *A4[3],B4       ; bmAttributes
c0135904 LDHU  *+A4[2],A6      ; wMaxPacketSize (byte offset 4)
c013590a LDBU  *A4[2],A4       ; bEndpointAddress
c013590c ADDKPC c0135910,B3,3  ; indirect call
```

## 5. USB audio registration recipe

### Finding 5.1 — exact registration sequence and required map-writer patch

Create two five-word records:

```text
IF2 record = { ret0, ret0, ret0, ac_request_callback, ret0 }
IF3 record = { ret0, ret0, ret0, as_request_callback, ret0 }
```

Using a return-zero +8 lifecycle stub and +16 endpoint stub is safe for the
planned design in which the audio patch owns stream state and EP1 setup.  If
later code needs USB lifecycle notification, replace +8; its calling
convention is documented in §4.  **Confidence: confirmed** for dispatch
safety; **likely** for sufficiency with the planned custom EP1 path.

In task context, immediately after the successful `c0152410`/`usbmidi_open`
call returns at `c0145158`, call, in this order:

```text
c015afa0(A4=6, B4=&IF2_record)   ; must return 0; allocates slot 1
c015afa0(A4=6, B4=&IF3_record)   ; must return 0; allocates slot 2
```

The existing MIDI registration has already allocated slot 0 through
`c0152410 -> c01520f4(0) -> c01521a8`.  Check each return against zero and
abort USB bring-up on `ffff8a5c`.  This hook is before `c016ab70` calls
`c015af18`, whose worker path asserts POWER.SOFTCONN (as established in
`recon/21` §3.2), so all records and maps exist before enumeration.
**Confidence: confirmed.**

```text
c0145158 CALLP c0152410,B3      ; installs stock MIDI record
c0145164 MV    A4,A0            ; registration result is available here
c016ab78 CALLP c0159758,B3      ; task-side MIDI/open path containing above
c016ab80 CALLP c015af18,B3      ; USB worker/soft-connect follows
c0120e10 MVK   0x0401,A4
c0120e14 MVKH  0x01e00000,A4    ; POWER register address
c0120e1a SET   A0,6,6,A0        ; SOFTCONN bit
c0120e20 STB   A0,*A4[0]
```

Those two calls are **not sufficient without patching `c015c66c`**.  Stock
code writes IF0 and IF1 on every selector-6 replay, so the last registration
would otherwise make both interfaces point to slot 2.  Replace its fixed
ownership writes with this slot-dependent mapping while retaining the
existing `record_vector[slot] = record` write:

```text
slot 0: interface_map[0]=0; interface_map[1]=0;
        endpoint_map[3]=0; endpoint_map[20]=0     ; stock MIDI
slot 1: interface_map[2]=1                         ; AudioControl IF2
slot 2: interface_map[3]=2                         ; AudioStreaming IF3
all:    record_vector[slot]=record
```

This makes recipient-1 SETUP packets with `wIndex=2` resolve slot 1 and call
IF2 `record[3]`, while `wIndex=3` resolves slot 2 and calls IF3 `record[3]`.
It also survives `c015c6b4`'s normal reset-and-replay because replay supplies
slot numbers 0, 1, 2 in registry order.  Registration order is therefore a
required invariant.  `c015afa0(6,0)` removes all selector-6 entries, not one
individual record.  **Confidence: confirmed.**

```text
c015c684 STW   slot,*c011aa4c   ; stock fixed EP3 ownership
c015c68a STW   slot,*c011aa90   ; stock fixed EP4 ownership
c015c696 STDW  slot:slot,*c011aac0 ; stock fixed IF0/IF1 ownership
c015c6a4 STW   record,*c011aa18[slot]
```

No capacity increase is needed: the registry and record vector have exactly
three usable slots, consumed by MIDI, IF2, and IF3.  A fourth record would
require enlarging the `c011aa28` registry, the `c011aa18` pointer vector, and
the three-entry scan/replay bounds in `c015c6b4`; this patch does not need
that.  Within the binding path, the only IF0/IF1 hard-code is the `STDW` at
`c015c696`; `c015c788` itself accepts interface keys 0..5 and does not encode
0/1.  **Confidence: confirmed.**
