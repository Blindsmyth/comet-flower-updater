# TX ring-mode slots and ring starter

Static analysis of `build/fw/map/main.dis` and `build/fw/map/refs.txt`, with names from `recon/map/chunk_*.md` used only through grep. No device, pedal, or executable was accessed; no firmware was changed; nothing was pushed.

## 1. Writers of TX field [2]

**Finding 1a (confirmed, negative result).** An exhaustive search for a direct address-constant
write to any of the 5 field-[2] addresses (`0xc0112984`, `0xc0112c2c`, `0xc0112ed4`, `0xc011317c`,
`0xc0113424` = `TX+8+0x2a8*N` for N=0..4) plus a 20-instruction computed-base scan
(`build/sol_txmode/scan_tx_field2.py`, tracks MVK/MVKH/ADD/SUB/MPY32 chains and flags any STW whose
resolved address matches `TX+8+0x2a8*n`) found **no instruction anywhere that stores a nonzero value
to field [2]**. Every direct hit on these 5 addresses is either a read (c011fb04/fb0e, c011fbf4,
c0121f24/f74/fc8, c0122018 family — see Finding 1b and §4) or belongs to the unrelated 168-byte-stride
"iostate" table family (c0121290, c0121b00, c012124c, c0121aa8, c015f4b8) that happens to share the
same base address by coincidence of memory layout, not the same struct.

**Finding 1c (confidence: confirmed).** `scan_tx_field2.py`'s only positive hit is `c011feba`, inside
`usb_ep_tables_clear_all` (`c011fe70`): a **zero**-store to field [2] of slot 1, repeated for slots 2-4
by a loop (confirmed independently by the existing `recon/17` quote in chunk_02.md: "680-byte increments
and bound 4"). Slot 0's field [2] is not touched by this function (it only zeroes slot 0's *last* 7
words, an unrelated boundary case). `c011fe70` runs from USB controller init (`c0122260`) and from the
USB error/shutdown path (`c011ff28`).

```text
c011fe74       MVK.S1   0x2c08,A4         ; A4 = 0xc0112c08 = TX+0x28c
c011fe78       MVKH.S1  0xc0110000,A4
c011fea4       MV.L2X   A4,B6             ; B6 = 0xc0112c08 (fixed anchor)
c011feb2       MV.L1    A1,A0
c011feb4       MVK.L1   0,A1              ; A1 = 0
c011feba       STW.D2T1 A1,*B6[9]         ; store 0 to B6+36 = 0xc0112c2c = TX+8+0x2a8*1 = field[2] slot 1
c011ff10   [B0]BNOP.S1  0xc011feb4,4      ; loop back while A3<4 (B6 advanced by 680/iter in delay slot)
```

**Net conclusion for Q1:** the only field-[2] writer found *clears* it (forces counted mode) for
slots 1-4 at init/shutdown. No code sets it nonzero, so — on the evidence available in this
disassembly — **ring mode is never entered at runtime in this firmware image**; see §4-§5.
Whether some slot's field [2] starts nonzero in the as-loaded `.data` image (rather than via a
runtime store) is **unknown** — that would require inspecting the ELF's initialized-data section,
which is outside this brief's stated inputs (`main.dis`/`refs.txt`/`recon/map/chunk_*.md`).


## 2. Caller of the kick `c0120c44`

**Finding 2a (confidence: confirmed).** `c0120c44` is a genuine standalone function, not a fallthrough
tail: the instruction immediately before it (`c0120c3c`/`c0120c40`) is `BNOP.S2 B3,5`, a real return
from the *previous* routine, and `c0120c44` opens with its own prologue `STW.D2T2 B3,*B15--[2]`. A
search of the whole disassembly for the low halfword `0x0c44` (as an MVK/MVKH operand pair), for the
literal `0xc0120c44`, and in `refs.txt` found **zero** hits of any kind — no `CALLP`, no address
constant, no `.word` table entry.

```text
c0120c3c   .fphead  ...  (end of prior routine)
c0120c40       BNOP.S2  B3,5              ; prior routine's real return
c0120c44       STW.D2T2 B3,*B15--[2]      ; c0120c44's own prologue — not reached by fallthrough
```

**Conclusion for Q2: unknown/unreachable in this disassembly.** `c0120c44` has no visible caller
anywhere in `main.dis` or `refs.txt`. Either it is dead code in this build, or it is reached by a
mechanism this static view cannot see (e.g. a function-pointer table stored as data rather than code).
This matches the existing `recon/map/chunk_02.md` entry for `c0120c44` ("no CALLP or address-constant
caller found") and Codex's partial Finding 2a in the companion report.

**Finding 2b (confidence: confirmed — full body trace, new).** Tracing `c0120c44` end-to-end: it is a
**ring-mode-only** operation. It returns the shared error code `0xffff8ad0` immediately if the masked
channel (`A4 & 0xF`) is 0, *or* if the target slot's field [2] is 0 (counted mode). Only when field [2]
is nonzero does it look at field [9]; if field [9] is exactly -1 it calls `c0120b2c`
(`usb_tx_desc_prepare`) to start the chain, otherwise it just stores the caller's value into field [5]
and returns.

```text
c0120c6c       LDW.D2T2  *+B4[2],B0        ; B0 = field[2] (mode) of record_base(channel)
c0120c70   [!B0]BNOP.S1  0xc0120c80,5      ; mode==0 (counted) -> skip to error return 0xffff8ad0
c0120c74       LDW.D2T2  *B4[9],B0         ; B0 = field[9] (ring index)
c0120c8c       CMPEQ.L2  -1,B0,B0          ; exactly -1 ?
c0120c90  [!B0]BNOP.S1   0xc0120c98,5      ; not -1 -> just stored field[5] above, return 0 (no (re)kick)
c0120c94       CALLP.S2  0xc0120b2c,B3     ; -1 (idle) -> start the chain via usb_tx_desc_prepare
```


## 3. Ring setup

**Finding 3a (confidence: likely).** The ring's length and index live in the *top-level* record's own
field [8] and field [9] (`record_base(N)+32` / `+36`), not in a separate sub-struct header at
`record+0x168` — the ring *array* starts at `record+0x168`, but its length/index bookkeeping is the
same field [8]/[9] the rest of the record uses. This is traced inside the completion-queue handler
`c011faa0` (part of the function housing the queue-24/25 pop loop, called from the USB ISR `c011fc8c`
per chunk_02.md). For a slot number `B1` pulled from the popped queue entry (masked to range 1-4, see
§4), after confirming field [2] != 0 (ring mode) and field [9] >= 0 (not idle), it computes the next
ring slot, wrapping at field [8] (length), and copies that ring entry through a pointer stored in
field [7]:

```text
c011fb4a   LDW.D2T2  *B6[9],B0      ; B0 = field[9] = current ring index   (B6 = record_base(B1))
c011fb4c   LDW.D2T2  *B6[8],B1      ; B1 = field[8] = ring length
c011fb50   ADD.L2    B0,1,B3        ; B3 = index+1
c011fb52   CMPLT.L2  B3,B1,B0       ; (index+1 < length) ?
c011fb54 [B0]BNOP.S1 0xc011fb60,5   ; yes -> keep B3; no -> B3 falls to...
c011fb58   MVK.L2    0,B3           ; ...wrap to 0
c011fb60   ADDAW.D2  B5,B3,B6       ; B6 = record_base(B1) + 4*B3
c011fb64   ADDK.S2   360,B6         ; B6 += 0x168  => ring entry at the new (wrapped) index
c011fb68   LDW.D2T2  *B5[7],B5  ||  ; B5 = field[7] (an indirection-target pointer)
c011fb6a   LDW.D2T2  *B6[0],B0      ; B0 = ring[new_index]
c011fb6e   STW.D2T2  B0,*B5[0]      ; *(field[7])[0] = ring[new_index]  -- hands the fetched entry off
```

This single step **does not store the new index (B3) back to field [9]**; within this 0xc011fb28-fb6e
window the index advance looks like it is computed but not committed, so either the commit happens
on a path not shown here or this is a read-ahead/peek rather than the actual advance. Flagging as
**unknown** which routine (if any) persists the new index — `c01219d0`/`c0121960` (the brief's other
ring-resubmit candidates) were not traced in this pass; budget ran out before reaching them.

**Finding 3b (confidence: likely).** The same field [2] value gates both this ring-advance block and
the downstream completion-queue routing in the same function: right after this block (at `c011fb70`),
a *second*, independently-reloaded copy of field [2] decides whether the completion is pushed onto
queue 34 (`A4=34`, ring path) or onto a per-slot queue number from the caller (`A4=A6`, counted path)
— matching the brief's "queue-34 completion resubmits" model exactly.

**Finding 3c (confidence: unknown).** No instruction was found that writes the ring *array contents*
(buffer pointers at `record+0x168+4*k`) or that initializes field [8] (length) to a specific nonzero
value for any slot. `c011fd40`/`c01204b4`/`c01216c4`/`c01218d8` (the brief's candidates) were checked:
`c011fd40` touches a *different*, 168-byte-stride table (confirmed in chunk_02.md), not this ring;
`c01216c4` and `c01218d8` (see below) increment the top-level field [8]/[10] by a transfer-size delta
on every completion — bookkeeping, not ring initialization.

```text
c01216e0   LDW.D2T2  *B4[10],B0     ; B4 = record_base(4)+stride*N  (c01216a8's own routine)
c01216e2   ADD.L2X   B0,A3,B0       ; += A3 (a caller-supplied delta, likely bytes transferred)
c01216e4   STW.D2T2  B0,*B4[10]
c01216e6   LDW.D2T2  *B4[8],B0
c01216ea   STW.D2T1  A0,*B4[8]      ; field[8] += A3 too (same delta, parallel counter)
```

So field [8] appears to be **dual-purpose by mode**: a fixed ring length in ring mode, but a running
signed byte/credit counter in counted mode (also checked for going negative and cleared, with error
codes 130-133 reported, by the per-endpoint poll in §4's Finding 4a) — consistent, but not proof the
two uses never collide.


## 4. Which slots use which mode

## 5. Verdict for USB audio
