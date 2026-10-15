# Review: USB audio silence-stream candidate (2026-10-15)

> **Claude response (2026-10-15).**
> - **STRING bug: confirmed and fixed.** `c0135258` passes A4 = A10 (type 3), and `c01352a4` reads
>   `{len, .., ptr}` records. The veneer now handles only A4 ∈ {1, 2}, the same `A4-1 <= 1` test the
>   stock builder makes at `c0160ee2..ee6`. Every other value tail-branches to `c0160ec0` before any
>   register or the stack is touched. Regression tests are in `tests/test_usb_audio_candidate.py`.
> - **Types 6/7: your "self-heals" reading did not hold.** Stock sends A4 = 6/7 to `c0161002`, which
>   returns an empty array, so a full-speed-only device STALLs DEVICE_QUALIFIER and
>   OTHER_SPEED_CONFIGURATION. The old veneer would have answered them; the fix keeps the stock behaviour.
> - **B4 speed selector (`c0160ef4`).** The two stock header pairs, `c017f3dc/c017f400` and
>   `c017f3ee/c017f40a`, are byte-identical, so ignoring B4 is safe.
> - **B31 in `ua_ep0_ack`: not a risk.** B16–B31 are caller-saved (scratch) under the C6000 EABI.
> - **SOF tick register use: not a risk.** If cl6x uses a callee-saved register it saves it itself, and
>   the Hwi caller is stock EABI C code that already assumes scratch registers are clobbered.

Reviewed against `build/fw/map/main.dis` (stock) and `build/usb_audio/usb_audio.dis`
(candidate, rebuilt with `tools/make_usb_audio_fw.py`). Scope: correctness only,
per docs/USB_AUDIO_SILENCE_CANDIDATE_2026-10-15.md and the brief's 7 checklist
items. No file under review was edited; no hardware/pedal/.exe was touched.

## Headline finding

**BUG (severe): GET_DESCRIPTOR(STRING) is broken, including LANGID (index 0),
which essentially every USB host requests immediately during enumeration.**
One of the 7 retargeted `CALLP c0160ec0` sites (`c0135258`) is reached only
for descriptor type 3 (STRING), where stock's builder does not fill the
24/25-slot fragment-pointer array at all — it writes a structurally different
5-entry table of 8-byte `{len, type, _, _, payload_ptr}` records. The veneer
ignores the type argument and always returns `desc_ptrs` (plain pointers to
raw descriptor bytes). The caller then reads `desc_ptrs[0]` (`device_desc`)
as if it were one of those 8-byte records, loading bytes 4-7 of `device_desc`
(0x00,0x00,0x00,0x40) as a "payload pointer" (0x40000000) and byte 0 (0x12)
as a copy length, then copies from that bogus address. See item 5 for the
full trace. This likely hangs/faults the DSP or returns garbage on the first
string request — not just "USB audio doesn't work," but enumeration itself.

Everything else reviewed (items 1, 2, 3, 4, 6) checked out correct, including
two cases I initially suspected were bugs and traced to confirmed non-issues
(OTHER_SPEED_CONFIGURATION type-field and DEVICE_QUALIFIER fields — stock's
*caller* patches those bytes after the builder/veneer runs, independent of
which builder supplied the base array).

---

## 1. `ua_map_thunk` (`firmware/usb_audio/ua_thunks.asm`)

**Entry register state — OK.** Traced the call site `c015c760` (16-bit
CALLP) precisely: its bundled delay-slot packet sets A4=selector (replayed
from storage), A6=slot, B4=record, all in parallel with the CALLP itself.
`c015c66c`'s own entry packet (also parallel) then does A0←A4, A4←A6, B0←B4,
so by the gate at `c015c674` the state is exactly A0=(selector==6 boolean
input... actually A0=selector itself until c015c672's CMPEQ turns it into the
boolean), A4=slot, B0=record — matches the thunk's assumption.
```text
c015c760  CALLP.S2  0xc015c66c,B3
c015c762| LDW *A7[0],A4   ; A4 = selector
c015c764| ADD B1,1,A6     ; A6 = slot
c015c766| MV.L2X A0,B4    ; B4 = record
c015c66c  MV.L1 A4,A0 || MV.S1 A6,A4 || MV.L2 B4,B0
c015c672  CMPEQ.L1 6,A0,A0
```

**Return to `c015c768` and other paths — OK.** `grep` of `main.dis` for
`c015c66c` finds exactly one reference (`c015c760`'s CALLP); same for the
raw address as a possible data/jump-table constant (`ffffc66c` low-half
pattern: zero hits). `c015c768` is confirmed as the real post-call
continuation: `c0135a46`-style walking code there (`ADD.L2 B1,1,B1` then
`CMPEQ.L1 0,A4,A0` testing the call's own A4 return value) only makes sense
once `c015c66c` has actually returned, and the CALLP's own encoded return
address is exactly this point (no other code lies between the CALLP's
bundled delay slot and `c015c768`).

**Caller's live registers survive — OK**, with one benign divergence: on
exit the thunk sets A4 directly (0 or 0xffff8a5c) without going through A0
the way stock does (stock always ends with A0==A4). The caller's first use
of A0 after return is `c015c76a CMPEQ.L1 0,A4,A0`, which **overwrites** A0
before ever reading it, so the different final A0 value is never observed.
B0/B4 (callee's inputs) are not read by the caller after the call either.

**Map writes for slot 0 — OK, byte-for-byte match.** Compared directly
against stock:
```text
stock: c015c684 STW A4,*0xc011aa4c[0]      ; EP3 OUT = slot
       c015c68a STW A4,*0xc011aa4c[17]     ; EP 0x84 IN = slot (base+68)
       c015c696 STDW A5:A4,*0xc011aac0[0]  ; IF0=IF1=slot
       c015c6a4 STW B0,*0xc011aa18[A4]     ; record_vector[slot]=record
thunk: STW A4,*A5[0]/[1] @0xc011aac0 (IF0/IF1=0), @0xc011aa4c[0]/[17]
       (EP3/EP0x84=0), STW B0,*0xc011aa18[A4] (record_vector[slot]=record)
```
Slot 1→`interface_map[2]`=1 (0xc011aac8) and slot 2→`interface_map[3]`=2
(0xc011aacc) match recon/24 §5.1's prescribed mapping exactly.

One structural point worth recording as **RISK, not a bug**: the patch
replaces a *conditional* `[!A0] BNOP` with an *unconditional* `CALLP.S2`.
This is safe here only because (a) CALLP does not disturb A0/A4/B0 in its
own bundled delay slot (confirmed empirically from `c015c760`'s own bundle,
and the template is explicitly "non-parallel"), and (b) the thunk re-does
the `[!A0]` test itself at entry. I could not fully resolve C6x's general
delay-slot execution rule for a plain (non-auto-stalling) branch purely from
static reading — the design sidesteps the question by making the predicate
test happen *inside* the callee rather than relying on the overwritten
instruction's original delay-slot behavior, which is sound regardless of how
that ambiguity resolves.

## 2. `ua_ep0_ack` (`firmware/usb_audio/ua_thunks.asm`)

**OK — exact register match.** Compared against the MIDI SET_INTERFACE ACK
at `c0151f5a..c0151f74`:
```text
stock: B4=0 (f5a), A4=128,A6=0,B6=0,A8=-2,B8=0,A10=0 (f60-f74, all one bundle)
ours:  MVK 128,A4 / MVK 0,B4 / MVK 0,A6 / MVK 0,B6 / MVK 0,A10 / MVK -2,A8 / MVK 0,B8
```
All 7 registers match. Confirmed against `c015af48`'s own body (`c015af4c..
af58`, a parallel bundle of `MV`s) that it genuinely consumes all 7 as
inputs (A1←A6, B2←B6, A3←A8, B1←B8, **A5←A10**, B4←A4, B0←B4) — A10 is a
real argument here, not incidental. `ua_ep0_ack` saves/restores A10 (and B3)
around the call, correctly treating A10 as callee-saved per EABI while still
overwriting it with the required argument value for the duration of the call.
No other register is read by `c015af48` that isn't set.

**Minor RISK, not exercised today:** `ua_ep0_ack` clobbers the extended
register B31 (used to hold the branch target) without saving/restoring it,
and does not preserve B4/A6/B6/A8/B8 either (all legitimately caller-saved
under EABI, so that part is fine). Checked the actual compiled caller
(`ua_if3_request` in `build/usb_audio/usb_audio.dis` c01a8440+): it keeps
only B10/B11 live across the call and saves/restores both correctly, so B31
is not live at any current call site. This is latent fragility (a future
recompile that allocates B31 in the caller would be silently broken), not an
active bug in this build.

## 3. `ua_if3_request` / `ua_if2_request` (`firmware/usb_audio/ua_glue.c`)

**Calling convention (A4=type, B4=&setup) — OK, confirmed in `c01359e4`'s
dispatcher:**
```text
c0135a06  AND.L2 96,B0,B0        ; type = bmRequestType & 0x60
c0135a0a  MV.L1X B0,A10
c0135a68  ADD.L2 12,B15,B4       ; B4 = &setup (8 raw SETUP bytes)
c0135a6c| MV.L1 A10,A4           ; A4 = type
c0135a60  B.S2 B0                ; calls record[3] (the registered callback)
```

**Return codes — OK.** `0xffff8a5b` ("not handled") is checked at
`c0135a80..a86`: when `type==0` (standard) it falls to the standard table
(`c0135a90..aaa`, which is `c0180210`, landing on `c0134e68`/`c0135940` for
bRequest 10/11); when `type!=0` it instead falls to the STALL path
`c0135ab4..c4` (`CALLP c0120ef8`, `MVK 0x80,A4`, `MVK 1,B4`). `ua_if2_request`
unconditionally returning NOT_HANDLED is therefore correct for a
no-controls AudioControl interface: standard requests go to the (harmless,
no-endpoint) table path, class/vendor requests STALL — spec-compliant
behavior for an interface with no class-specific support.

**`alt[3]` write matches stock — OK.** Stock's `c0135940` SET_INTERFACE does
`c013596e STB A0,*A4[A5]` with A5=0xc011a1b0 (byte array indexed by
interface number). `ua_if3_request`'s `ALT_ARRAY[AS_INTERFACE] = (u8)alt`
uses the same base and `AS_INTERFACE=3`; the compiled code confirms the
literal address: `c01a8494 MVK.S1 0xffffa1b3,A3` = 0xc011a1b0+3. GET_INTERFACE
(`c0134e8c`, reached via NOT_HANDLED fallthrough for bRequest 10) reads from
the exact same array/index, so it transparently returns whatever
`ua_if3_request` last wrote.

**Configured-flag check (B14[11]) — checked, not missing in a meaningful
sense.** Stock's *generic table* SET_INTERFACE does check it:
```text
c0135948  LDW B0,*+B14[11]         ; configured flag
c0135950  [B0] BNOP .. c013595c,5  ; configured -> do the real work
c0135954  BNOP .. c0135980,4       ; not configured -> error, no ACK
```
`ua_if3_request` does not replicate this. But the existing, shipped **MIDI**
record callback (`c0151ed0`) has the identical property: its own bRequest-11
handler (`c0151ee4..c0151f8c`) never touches B14[11] either. Since both
MIDI's and IF3's record callbacks run *before* the generic table and
intercept bRequest 11 entirely, the omission is consistent, pre-existing
precedent for this exact interception mechanism, not a regression introduced
by this candidate. Verdict: **OK** (matches established, working MIDI
behavior; a real-world trigger would require a non-compliant host sending
SET_INTERFACE before SET_CONFIGURATION, which stock's own MIDI path is
equally exposed to today).

## 4. `ua_usbmidi_open` (`firmware/usb_audio/ua_glue.c`)

**A4-only argument — OK.** Confirmed at the call site: `c0145154 MVK
0x4c0c,A4` / `c0145160 MVKH 0xc0140000,A4` (parallel with the CALLP at
`c0145158`) is the *only* register set up before the call; B4 at that point
holds an unrelated leftover value from earlier code, never read by
`c0152410`/`ua_usbmidi_open`.

**`c015afa0(6, record)` convention — OK**, confirmed directly in the
compiled `ua_usbmidi_open` (`build/usb_audio/usb_audio.dis` c01a84e0+):
```text
c01a850e| MVK.L1 6,A4            ; selector = 6
c01a8510| MVKH.S2 0xc01a0000,B4  ; B4 = &ua_if2_record
c01a8520 [!A0] B.S2X A11         ; A11 = 0xc015afa0
```
and again for `ua_if3_record` at `c01a853c/8540`. Matches `A4=selector,
B4=record` exactly.

**Caller's use of the result — OK.** `ua_usbmidi_open` always returns `r`
(stock `usbmidi_open`'s own return value) regardless of whether the
subsequent IF2/IF3 registration succeeds — confirmed in the compiled tail
(`$C$L3`/`c01a856c`: `MV.L1 A12,A4` where A12 was saved as `r` right after
the stock call, on *both* the early-exit and success paths). The caller at
`c0145164..66` only inspects this value (skip the follow-on `c0144f74` init
call on nonzero), so behavior is unchanged for both success and failure of
the *original* MIDI open. A MIDI-open success with IF2/IF3 registration
failure is silently absorbed (audio interfaces just don't register; MIDI
still works) — acceptable degradation, not a correctness bug.

## 5. Descriptor veneer (all 7 `CALLP c0160ec0` sites)

Traced each site's caller and, where the type argument varies, what the
*caller* does with the result — not just what the builder does.

| site | reached from | A4 passed | caller post-processing | verdict |
|---|---|---|---|---|
| `c0135568`,`c0135694`,`c01357e4`,`c0152514` | various (incl. `usb_interface_altsetting_configure` at `c01357c8`) | fixed `MVK 2,A4` | none needed (always wants CONFIGURATION) | **OK** |
| `c0135014` | GET_DESCRIPTOR dispatch table `0xc0184410`, index 1 (type 2, CONFIG) **and** index 6 (type 7, OTHER_SPEED_CONFIG; `table[6]==table[1]==0xc0134fe4`) | `A4=A10`=2 or 7 | `c01350f8..c0135106`: if `A10==7`, directly overwrites response-buffer byte 1 (bDescriptorType) with 7, *after* the copy, independent of the builder | **OK** — verified the caller patches the type field itself |
| `c0135168` | same table, index 0 (type 1, DEVICE) **and** index 5 (type 6, DEVICE_QUALIFIER; `table[5]==table[0]==0xc0135138`) | `A4=A10`=1 or 6 | `c0135200..0135218`: if `A10==6`, overwrites response bytes 0,1,8,9 (bLength=10, bDescriptorType=6, bNumConfigurations copied from the matched entry's own byte 17, bReserved=0) | **OK** — same self-healing pattern, and `device_desc[17]` (0x01) is exactly `bNumConfigurations`, matching the standard DEVICE layout the fixup assumes |
| `c0135258` | table index 2 (type 3, **STRING**) | `A4=A10`=3 | *none* — no fixup exists or is possible for variable-length string data | **BUG**, see below |

Stock `c0160ec0`'s own internal branch on A4==3 (`c0160eea CMPEQ 3,A4,A0` /
`c0160eec [A0] BNOP c0161008,5`) writes a completely different 5-entry
table of 8-byte records (`c0161008..0161038`, writing ROM pointers
`0xc017f414/41c/424/42c` via `STDW`), not the 14/24-slot fragment array the
general path and the veneer both build. The post-call walker for this
specific site (`c01352a4..c01352b8`) assumes that shape:
```text
c01352a4  LDW.D1T1  *A4[1],A5     ; A5 = entry+4  (payload pointer)
c01352a6  LDBU.D1T1 *A4[0],A0     ; A0 = entry+0  (length byte)
c01352b8  LDB.D1T1  *+A4[1],A1    ; A1 = entry+1  (type byte)
```
The veneer instead always writes `desc_ptrs` (plain pointers straight at raw
descriptor bytes: `desc_ptrs[0]=device_desc`, 18 bytes starting
`0x12,0x01,0x10,0x01,0x00,0x00,0x00,0x40,...`). For string index 0 (LANGID —
the first thing virtually every host requests), the index-matching loop
(`c0135280..c0135298`, counter `B1` vs. requested index `A12`) immediately
matches `desc_ptrs[0]`, so `A4` = `&device_desc` is fed straight into the
code above: it reads `device_desc` bytes 4-7 (`00 00 00 40`) as a 32-bit
"payload pointer" (**0x40000000**) and byte 0 (`0x12`=18) as a byte count,
then copies 18 bytes from address 0x40000000 into the EP0 response buffer.
This is almost certainly an invalid/unmapped DSP address. **BUG (severe,
concrete failure): GET_DESCRIPTOR(STRING, index 0) reads from a
bogus/attacker-uncontrolled address derived from `device_desc`'s own bytes,
likely a bus fault/hang, at minimum garbage LANGID data, on essentially
every real enumeration attempt.** This breaks the device far beyond "no USB
audio" — it is reached through the shared string-descriptor path that MIDI
enumeration also depends on.

## 6. SOF hook (`c016f770`/`c016f774` → `usb_audio_sof_tick`)

**Single caller — OK**, confirmed by `grep`: only `c011fcb4 CALLP.S2
0xc016f770,B3` references `c016f770` anywhere in `main.dis`.

**Hwi-safety of calling an EABI C function — OK, verified against the
actual compiled output**, not just assumed. `usb_audio_sof_tick`
(`build/usb_audio/usb_audio.dis` c01a8000-c01a80c8) uses only A0, A3, A4,
A31, B0, B1, B4-B8 — none of A10-A15/B10-B15, and it never touches B15
(no stack frame at all). The enclosing ISR (`c011fc8c`) reads **A10** again
at `c011fcd8` and **A11** again at `c011fccc`, both *after* the SOF-hook call
returns (`c011fcb4`); since the hook's compiled body never writes either
register, there is no corruption. No added stack depth in the Hwi path.
```text
c011fcb4  CALLP.S2  0xc016f770,B3     ; our hook, via the retargeted trampoline
c011fcb8  CALLP.S2  0xc011faa0,B3 || MVK.S1 24,A4   ; next ISR work, fresh A4
c011fccc  MV.L2X    A11,B0            ; ISR re-reads A11 — confirmed untouched by sof_tick
c011fcd8  MV.L1     A10,A0            ; ISR re-reads A10 — confirmed untouched by sof_tick
```

**RISK, not exercised today:** this safety is incidental to the current
`--opt_level=2` compile of a small leaf-shaped function, not an enforced
contract. `usb_audio_sof_tick` is an ordinary EABI C function with no
interrupt-safe/register-budget attribute; a future rebuild (different
optimization level, an added local, structural changes to the source) could
silently start using A10-A15/B10-B15 or B15-relative stack slots, and the
compiler would not warn that this breaks the calling Hwi's assumptions.
Nothing in the toolchain enforces "this function may only use scratch
registers and no stack."

**Trampoline patch mechanics — OK.** The patch only rewrites the two
immediate-field words (`mvk_lo`/`mvk_hi` in `tools/make_usb_audio_fw.py`),
leaving `c016f778 B.S2 B31` untouched; `B3` set by the `CALLP` at `c011fcb4`
passes through the trampoline unmodified (it's a plain register branch, not
a call), so `usb_audio_sof_tick`'s own `BNOP B3,3`/`BNOP B3,2` returns
correctly to `c011fcb8`.

## 7. Anything else that would break enumeration or MIDI

The item 5 STRING-descriptor bug (section 5 above) is the dominant answer
here — it is reached on a path MIDI's own enumeration depends on just as
much as audio's, since string descriptors are not interface-specific.

No other enumeration- or MIDI-affecting issue was found. Specifically
checked and ruled out:
- `usb_interface_altsetting_configure` (`c01357c8`, used by both
  SET_CONFIGURATION and, in principle, a non-intercepted SET_INTERFACE) gets
  its descriptor list through `c01357e4`, one of the 7 patched sites — so it
  correctly sees the new 4-interface/192-byte set, not a stale 2-interface
  one. No separate, unpatched call site was found for it.
- Registration-order invariant (MIDI slot 0 before IF2/IF3 slots 1/2) is
  preserved: `ua_usbmidi_open` only attempts IF2 registration after the
  stock MIDI open succeeds, and only attempts IF3 after IF2 succeeds,
  matching recon/24 §5.1's required ordering exactly.
- The GET/SET_INTERFACE standard-table words (`c0180238`/`c018023c`) are
  untouched, as the candidate's own plan requires (P7 in recon/20 §2.6) —
  confirmed no patch in `tools/make_usb_audio_fw.py`'s `PATCHES` list touches
  them.

## Summary of verdicts

| # | item | verdict |
|---|---|---|
| 1 | `ua_map_thunk` entry/return/clobber/slot-0 writes | OK (one documented RISK: relies on CALLP's delay-slot behavior being benign, argued but not exhaustively proven) |
| 2 | `ua_ep0_ack` register set vs. `c0151f5a..c0151f8c` | OK (one low-priority RISK: B31 not saved/restored, unexercised today) |
| 3 | `ua_if2_request`/`ua_if3_request` convention, return codes, `alt[3]`, configured-flag | OK (configured-flag omission verified consistent with existing MIDI behavior, not a regression) |
| 4 | `ua_usbmidi_open` argument convention, registration, caller handling | OK |
| 5 | Descriptor veneer, all 7 call sites | **BUG** at `c0135258` (STRING, type 3) — breaks GET_DESCRIPTOR(STRING) including LANGID; OK at the other 6 sites (type 2/7 and 1/6 self-healed by caller-side byte fixups, verified directly) |
| 6 | SOF hook retarget and Hwi safety | OK, verified against the actual compiled registers used (one RISK: incidental, not enforced, safety) |
| 7 | Other enumeration/MIDI breakage | Covered by item 5's finding; nothing else found |
