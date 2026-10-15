# TX ring-mode slots and ring starter

> **Claude review (2026-10-15).** This report was filled in by a Sonnet subagent after Codex hit its cap.
> - **Confirmed: field [2] is only ever written 0.** At `c011feba`, `STW A1(=0),*B6[9]` with
>   B6 = `0xc0112c08` (`c011fe74/78`, `c011fea4`) targets `0xc0112c2c` = slot 1 field [2]
>   (`0xc0112984 + 0x2a8`). No TX record address lies in any `main.elf` section, so the image has no
>   non-zero initializer. **Ring mode is dormant in stock**: both its checks always take the counted branch.
> - **Correction.** "`c011fd40` is a different 168-byte-stride table" is wrong. `MVK 168` followed by
>   `SET A0,9,9` is 0x2a8, and `c011fd5a` forms the TX record base. `c011fd40` clears [6]..[8] and
>   sets [9] = -1 on the same TX record (see the review in SOL_EXPIRY_RECOVERY_REPORT).
> - **The open item in §3 is answered elsewhere.** The ring index is committed to [9] by case D at
>   `c0121988`/`c0121996` (SOL_DIRECT_SUBMITTERS_REPORT §2b), not by `c011faa0`.
> - **Consequences.**
>   - The ring-mode double-chain risk is moot for stock.
>   - The counted-mode findings (deferral, liveness) cover every live TX path.
>   - For USB audio, the dormant ring machinery is a candidate base: an ISO stream would set [2]
>     non-zero, fill record+0x168, set [8] and [9] = -1, then kick `c0120c44`. Its entry layout and the
>     slot-to-endpoint mapping are unresolved (see recon/23_cppi_iso.md).

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

**Finding 4a (confidence: likely).** An undocumented function around `c0121f24`-`c0122044` (not in
`recon/map/chunk_02.md` — new) explicitly, individually checks field [2] for **slots 4, 3, 2, 1 in
that order** (unrolled, one block per slot; slot 0 is not part of this pattern). Each block: if
field [2] != 0 (ring mode), skip the slot entirely; if field [2] == 0 (counted) and field [8] is
negative, clear field [8] to 0 and report a slot-specific error code (132/131/130/129 for
slots 4/3/2/1), then fall through to a shared per-slot status write. The branch polarity is explicit
below so it is not inverted:

```text
c0121f24   MVK.S1   0x3424,A4         ; A4 = field[2] addr of slot 4
c0121f2c   LDW.D1T1 *A4[0],A0         ; A0 = field[2] value
c0121f2e [A0]BNOP.S1 0xc0121f4c,5     ; A0 != 0 (ring mode) -> skip this slot's error check entirely
c0121f30   LDW.D1T1 *A4[8],A0         ; (only when A0==0, counted) A0 = field[8]
c0121f32   CMPGT.L1 0,A0,A0           ; (0 > field8) i.e. field8 negative?
c0121f34[!A0]BNOP.S1 0xc0121f4c,5     ; not negative -> skip the clear+report
c0121f3a   MVK.L1   7,A0              ; negative -> report code 7 ... and 132 (slot 4's code) below
```
(Same shape repeats at `c0121f74` for slot 3 with `0x317c`/code 131, `c0121fc8` for slot 2 with
`0x2ed4`/code 130, `c0122018` for slot 1 with `0x2c2c`/code 129.)

**Finding 4b (confidence: likely).** The completion-queue handler `c011faa0` (§3, Finding 3a) reads
field [2] dynamically for a slot number extracted from the popped CPPI queue entry
(`SHRU B0,0x1b,B1`), range-checked to `1 <= B1 < 5` before the field-[2] lookup — so slots 1-4 are the
only ones this dynamic path ever touches too.

```text
c011fac4   SHL.S2    B4,0x5,B0
c011fad0   CMPLT.L2  0,B1,B0        ; B1 > 0 ?
c011fad4[!B0]BNOP.S1  0xc011fb70,5  ; B1<=0 -> bail (slot 0 excluded)
c011fad8   CMPGT.L2  5,B1,B0        ; B1 < 5 ?
c011fae0[!B0]BNOP.S1  0xc011fb70,5  ; B1>=5 -> bail
```

**Finding 4c (confidence: likely, ties to §1).** Slot 0 never appears in either the static per-slot
mode check (4a) or the dynamic one (4b) — it is handled by separate EP0-control-transfer logic
elsewhere, consistent with it being the USB control endpoint rather than a TX/RX data slot. Because
no code anywhere sets field [2] nonzero (§1, Finding 1a/1c), **the mode checks in both 4a and 4b
currently always take the "counted" branch at runtime for slots 1-4** — the ring-mode branches in
both functions are live, reachable code, but dead in practice for this firmware image. The brief's
assumption that slot 4 = MIDI IN and slot 1 = the ISO audio IN endpoint could not be confirmed or
refuted from `main.dis`/`refs.txt`/chunk docs alone (no naming evidence tying slot numbers to USB
endpoint/class roles was found in this pass) — **unknown**.


## 5. Verdict for USB audio

**Verdict (confidence: likely, synthesized from §1-§4).** A complete stock ring-mode TX chain exists
in the code and is reachable — the mode branch, the kick, and the completion-driven resubmit are all
real, live instructions, not stubs — but **no slot currently runs in ring mode**, because nothing in
this firmware image ever stores a nonzero value into any slot's field [2] (§1). So an ISO IN stream
cannot simply "turn on" ring mode on an existing slot; it would need to be switched on by a patch.

What reusing it would require, concretely:
1. **Pick a slot in {1,2,3,4}** (0 is excluded from all mode logic, §4). Slot identity-to-USB-role
   (which one is audio, which is MIDI) is **unknown** from this pass — not established in
   `recon/map/chunk_*.md` and not inferable from the instructions traced here.
2. **Set that slot's field [2] nonzero**, once, after any call to `usb_ep_tables_clear_all` (`c011fe70`,
   §1) — that function will zero it again on every controller (re)init, so the write must happen
   after init, or that clear path must be special-cased for the chosen slot.
3. **Populate the ring array** at `record_base(N)+0x168` with buffer-pointer entries (content/layout of
   an entry beyond "a value copied through field [7]" was not determined — §3, Finding 3a).
4. **Set field [8]** to the ring length (entry count) and **field [9] to -1** (idle) so the first call
   to the kick `c0120c44` performs the initial `usb_tx_desc_prepare` (§2, Finding 2b); each subsequent
   queue-34 completion then advances the index and resubmits via the `c011faa0` logic (§3).
5. **Set field [7]** to point at wherever the fetched ring entry should land for the next submit step
   — this pass did not trace what consumes that location downstream.
6. Resolve the open item from Finding 3a: confirm where (if anywhere) the advanced ring index actually
   gets written back to field [9], since the window traced here computes it but does not visibly store
   it — needed before relying on this path for real traffic.

Everything needed to **drive** a ring chain (kick, advance, completion routing) is present and
reachable; what's missing/unverified is (a) a working field [9]-write to commit the index advance,
(b) the ring entry's actual field layout, and (c) which physical slot corresponds to the USB-audio ISO
IN endpoint. None of (a)-(c) were resolved in this pass.

