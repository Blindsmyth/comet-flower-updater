# S12: SysEx command hook - verification of F8 Flash report

## Status
done

## Findings

### 1. c0128e54 (midi_cmd_dispatch) has exactly one caller: c0129324 (confirmed)
`grep -n 'c0128e54' build/fw/map/main.dis` over the whole 153793-line file returns only
two lines: its own entry (`c0128e54 01bc54f6 STW.D2T2 B3,*B15--[2]`, line 39779) and
the call site `c0129324 b35b CALLP.S2 0xc0128e54,B3` (line 40169). I also grepped for
any register-indirect path: there is no `MVK`/`MVKH` pair anywhere in main.dis that
constructs the literal `0xc0128e54` into a register for a `B`/`CALLP reg` call (checked
`grep -n '0x8e54,\|0xc0128e54'`, and scanned every line containing the substring
`8e54` across the file -- all other hits are coincidental byte patterns inside
unrelated raw instruction words, e.g. `MVK 0x1ca8,A1` whose hex encoding happens to
contain `8e54`, not an operand of that value). F8's claim is CONFIRMED.

Caveat: `recon/map/chunk_04.md:74,80` names the "caller" as `c0129276`
(`midi_rx_state_dispatch_entry`), not `c0129324`. This is not a contradiction, just a
different granularity: `c0129276` is one of 5 jump-table targets *inside* the same
contiguous MIDI-task loop that also contains the literal `CALLP` instruction at
`c0129324`; recon's fact-sheet pass attributed the call to the enclosing table-target
symbol rather than the exact instruction address. The physical `CALLP` opcode is only
ever at `c0129324` (confirmed by direct disassembly, see Finding 3).

### 2. State-machine jump table at 0xc01844a8 (confirmed) -- corrects F8's state/address mapping
The 5-state table is real data, found directly in main.dis:
```
c01844a8   c0129242   .word 0xc0129242   ; state 0 (manufacturer)
c01844ac   c0129214   .word 0xc0129214   ; state 1 (device ID)
c01844b0   c0129276   .word 0xc0129276   ; state 2
c01844b4   c01291f0   .word 0xc01291f0   ; state 3 (payload)
c01844b8   c01291ce   .word 0xc01291ce   ; state 4 (Universal SysEx branch)
```
Dispatch code (`c01291b0..c01291cc`): `B5 = 0xc01844a8; B1 = *(B5 + state*4); branch B1`.
This matches F8's table base and state0/1/3 addresses exactly. But **state 2
(`c0129276`) does NOT store the model byte to `*+B14[166]`** as F8 claimed -- its whole
body is just `state++; *B14[43]=0; goto c012932c` (increment parser state, reset the
payload byte counter, exit). The actual `STB A0,*+B14[166]` instruction is at
`c0129158`, which runs *unconditionally for every received byte* (before any state
check), not specifically inside the state-2 handler. Confirmed by grepping all of
main.dis for `B14\[166\]`: it is written exactly once (`c0129158`) and **never read
anywhere in the file**. So this field is a dead/write-only scratch byte, not a
persisted "model ID" used later by any reply builder. Confidence: confirmed (grep +
direct disassembly).

### 3. CORRECTION: the 0x1180ff20/1024B payload buffer is reached only for external command byte 0x64 (100), not generically for "cmd>=9" -- an unused "free" command's payload bytes are silently dropped by stock code
Traced `c0127cf4` (per-payload-byte handler, called from state 3 at `c01291f8` with
`A4=byte, B4=byte_count`) for the subsequent-byte case (`count>1`, i.e. not the command
byte itself):
```
c0127d08  LDHU *+0xc0183b60,A5         ; A5 = stored command byte
c0127d14  CMPLTU 0x9,A5,A0             ; A5>9 ?
c0127d18  [!A0] BNOP 0xc0127d4c,5      ; A5<=9 -> 0..9 function-ptr table @0xc0183b74
c0127d1a..d028  (A5-40) unsigned <= 7? -> 0xc0127d60 (2nd table @0xc0183b9c, cmds 40..47)
c0127d2a..d044  A5==69 -> c0127da2 ; A5==70 -> c0127d94 ; A5==96 -> c0127d88 ; A5==100 -> c0127d78
c0127d48  BNOP 0xc0127f58,5            ; UNCONDITIONAL fallthrough: return, no storage call
```
`c0127d78` is `CALLP 0xc016f760,B3`, and `c016f760` is a plain 3-instruction veneer:
```
c016f760  MVK 0x3010,B31; MVKH 0x11800000,B31; B.S2 B31   ; -> 0x11803010
```
i.e. it branches straight into the exact byte-store routine F8 quoted (`11803010`,
bounds-checks the running index against 1024 and stores to `0x1180ff20 + index`).
**This path is taken only when the stored command byte equals exactly 100 (0x64)** --
confirmed by the explicit `CMPEQ A5,100-literal,A0` at `c0127d40/c0127d44` immediately
before the branch to `c0127d78`. For every command byte that is NOT in {0..9, 40..47,
69, 70, 96, 100} -- which includes F8's proposed free command `0x70` (112 decimal) --
execution falls through to `c0127d48`'s unconditional `BNOP 0xc0127f58,5`, which is
simply `c0127cf4`'s epilogue (pop return address, return). **No byte is stored
anywhere.** So under stock code, sending `F0 52 00 6E 70 <payload...> F7` would have
its command byte preserved at `0xc0183b60` (Finding 4) but every byte after it
silently discarded; `0x1180ff20` would still hold whatever an *unrelated* command 0x64
message last left there, not our payload. Confidence: confirmed (direct disassembly
of `c0127cf4`, `c0127d78`, `c016f760`, and the `11803010` store routine, all cited
above). This directly contradicts F8 Finding 2's claim that "bulk commands (cmd >= 9
...) jump to 11803010" -- that routing is specific to cmd==100, not a `cmd>=9`
default.

Consequence for the hook design: picking an unused command byte and relying on stock
code to buffer its payload at `0x1180ff20` **does not work** as F8 assumed. A usable
fix (not yet encoded/sized -- left as an open lead below) is a second, 1-word patch at
`c0127d48` (currently `010ca120 BNOP.S1 0xc0127f58,5`) redirecting its target from
`0xc0127f58` to `0xc0127d78`, so every otherwise-unmatched command's subsequent bytes
also land harmlessly in the same 1024 B scratch buffer (B14[38] stays 0 for them
either way, so stock dispatch still drops the message -- see Finding 5).

### 4. Command byte global 0xc0183b60 is a halfword and IS stored for unknown commands too (confirmed); B14[n] addressing is not uniformly "+4n"
`c0127df0` (entered when `count==1`, i.e. unconditionally for the FIRST payload byte of
every message, via `c0127d00 CMPEQ 1,B1,B0; [B0] BNOP 0xc0127df0,5`):
```
c0127df0  MVK 0x3b60,A7; MVKH 0xc0180000,A7   ; A7 = 0xc0183b60
c0127df8  STH.D1T1 A1,*A7[0]                  ; unconditional, BEFORE any recognition
c0127e00  [!A1] BNOP 0xc0127f0a,5             ; recognition cascade starts here
```
The `STH` at `c0127df8` runs before any comparison against `A1` (the command byte), so
yes -- the raw byte is stored at `0xc0183b60` for every command value including
unrecognized ones (e.g. 0x70). Confirmed.

Important nuance for anyone recomputing addresses from the brief's formula ("B14[n] =
0xc0184e00 + 4n"): that formula is only correct for **word-width** accesses (`LDW`/
`STW`), which is what applies to the length counter `B14[43]` (used exclusively with
`LDW`/`STW` in this function, e.g. `c01291b4 LDW *+B14[43],B3`, `c01291d0 STW B4,*+B14
[43]`) -- so `B14[43] = 0xc0184e00 + 4*43 = 0xc0184eac` is correct as claimed. But the
parser's single-byte flags (`B14[164]` f0/f7 flag, `B14[165]` manufacturer ID, `B14
[166]` dead scratch, `B14[167]` state, `B14[168]` device ID) are all accessed with
`LDBU`/`STB` (byte-width), where the disassembler's `*+B14[n]` offset is `n` **bytes**,
not `n*4`. E.g. `B14[165]` as a byte op is `0xc0184e00+165 = 0xc0184ea9`, a completely
different address from `B14[165]` accessed via `LDW` elsewhere in the firmware (offset
`165*4=660 -> 0xc01850a4`, seen in unrelated functions at `11806e84`, `c013ac78`,
etc. -- confirmed by grep, these are different physical bytes that only coincidentally
share the index "165" in the disassembly notation). Anyone patching near these fields
must check the instruction's operand width before applying the `+4n` formula.

### 5. B14[38] (internal command ID) is unconditionally zeroed after EVERY dispatch, recognized or not (confirmed) -- no stale-value risk for a repeated unknown command
Read `c0128e54` in full (`c0128e54`..`c0129114`, 193 instructions). Every one of the
20+ `CMPEQ`-guarded branches, after calling its specific handler, lands on the single
shared exit `c01290ec` (either by an explicit `BNOP 0xc01290ec,5` or by falling
straight into it, e.g. `c01290e8`'s handler is immediately followed by `c01290ec`).
`c01290ec` itself always falls through to:
```
c0129104  LDW *+B14[139],A4        ; (|| with the CALLP above it)
c0129108  MVK 0,B0
c012910c  STW B0,*+B14[38]         ; B14[38] = 0, unconditionally, every message
c0129110  LDW *++B15[2],B3
c0129114  BNOP B3,5                ; return to c0129328 (resumes the byte-read loop)
```
So regardless of whether the just-finished message was recognized or not, `B14[38]`
is guaranteed to be 0 again before the next message's first payload byte is
processed. This confirms F8's "no error reply, silent drop" claim and additionally
rules out a possible edge case I checked for: a stale nonzero `B14[38]` from a prior
recognized command could NOT leak into a later unrecognized command's dispatch.
Confidence: confirmed, full-body read cited above.

### 6. Manufacturer/device/model checks: model and device bytes are NOT validated at all; only the manufacturer byte gates entry to state 3 (confirmed, corrects/extends F8)
State 0 (`c0129242`, manufacturer): accepts only `0x52` (Zoom) or `0x7E` (Universal);
any other byte resets state back to 0 (`STB 0,*B14[164]; STB 0,*B14[167]`) -- the
message is aborted, never reaches state 3. Confirmed by direct read.

State 1 (`c0129214`, device ID): `STB.D2T1 A6,*+B14[168]` stores the device byte
**unconditionally, with no value check whatsoever** -- then checks the previously
stored manufacturer byte (`B6`) against `0x52`: if Zoom, state becomes 2; if not
(i.e. the `0x7E` Universal path), state jumps straight to 4, skipping the model-ID
state entirely. There is no comparison instruction anywhere against `B14[168]`/the
device byte in this function. Grepping the whole file for `B14\[168\]` shows exactly
one write (`c0129214`) and one unrelated read in a completely different function
(`c015f244`, outside the SysEx receive path). So: **any device ID byte 0x00-0x7F is
accepted**, not just `0x00` -- F8 only confirmed `0x00` works but didn't check (and
this session now confirms) that the device ID is simply never validated.

State 2 (`c0129276`, reached for any Zoom-manufacturer message): body is only
`state=state+1; B14[43]=0; goto c012932c` -- **no comparison against the model byte at
all.** So a model byte of `0x6e` (G1X Four) reaches state 3, but so would any other
value; model ID is likewise unchecked in the inbound parser.

Net: `F0 52 00 6E ... F7` (manufacturer Zoom, device 0, model G1X Four) reaches state
3 as F8 claimed (confirmed), but this is not because the firmware validated the model
or device bytes -- it reaches state 3 because *nothing* checks them; only the
manufacturer byte gates progression past state 0.

### 7. Reply path c01274cc: signature, a real caller, and limits (confirmed)
Direct read of `c01274cc`:
```
c01274cc  CALLP 0xc016e020,A3        ; (c674x compiler-inserted prologue stub)
c01274d2  MV.S1 A4,A10 (|| MV.L1X B4,A11)   ; save A4 (buf) and B4 (len)
c01274d4  CALLP 0xc0150b20,B3 ; LDW *+B14[161],A4 ; MVK -1,B4   -> bios_sem_pend(B14[161], -1)
c01274e4  CALLP 0xc0144dc8,B3 ; A4=0 (port), B4=buf(A10), A6=len(A11)  -> transport
c01274f0  CALLP 0xc01628e0,B3 ; LDW *+B14[161],A4                      -> sem_post(B14[161])
c01274f8  CALLP 0xc016e000,A3        ; epilogue stub
```
This confirms `void c01274cc(uint8_t *buf /*A4*/, uint32_t len /*B4*/)`, blocking
indefinitely (`-1` timeout) on mutex `B14[161]` before queuing bytes, matching F8.

Verified one real stock caller end to end, `c0127500` (the "copy f0 52 00 00 00 00 f7
from 0xc0181880" reply builder named in Brief 5):
```
c0127500  STW B3,*B15--[4]                 ; prologue
c0127508  B4 = 0xc0181880  (template base, MVK 0x1880/MVKH 0xc0180000)
c0127510..c0127528  copy 7 template bytes into a stack buffer at A4=B15+8
c012752c  load model-ID byte from *0xc0183b48 and patch it into the stack buffer
c0127540  patch in the status/arg byte (from caller's A1) at offset 13
c0127548  CALLP 0xc01274cc,B3  ||  MVK.L2 7,B4     ; B4=7 fills the call's delay slot
```
So `c0127500(arg)` builds a 7-byte `F0 52 00 <model> ... F7`-shaped reply on the stack
and calls `c01274cc(buf, 7)` -- directly confirming the `(A4=buf,B4=len)` convention
with real values. `c0127500` itself is called from inside `c0128e54`'s handlers (e.g.
`c012906c`, `c0129084`, `c01290a8`, etc. -- all MIDI-task-context code), i.e. exactly
the context our hook would run in. Confirmed 24 total call sites of `c01274cc`
(grepped), all inside the c0127xxx-c012dxxx MIDI/editor region plus c0129xxx (the MIDI
task itself) -- consistent with "Task context only" (no Hwi/Swi caller found).

Not independently confirmed: F8's specific claim of ring-buffer base address
`0xc0117b28`. I verified the **logic** (`c0149d84 SET A0,10,10,A0` -> 1024; `c0149d86
CMPLT A1,A0,A0` checks index<1024) which is consistent with a ~1024-entry ring and the
claimed 1024-byte max, but grepping main.dis for `0x17b28`/`c0117b28` found no hit (the
base address is likely built from an MVKH/MVK pair whose immediate fields didn't
happen to echo that literal in a directly greppable form within the window I read).
Treat the exact base address as **not independently verified this session**; the
1024-byte cap and blocking-mutex behavior ARE confirmed via the logic above.

### 8. Hook site: c0129324 is a compact 16-bit CALLP+BNOP pair, NOT a standard 32-bit CALLP -- this changes which option is actually easy to patch with existing tooling
Direct bytes at the call site:
```
c0129320   0000a43e   STB.D2T2  B0,*+B14[164]      ; full 32-bit instruction
c0129324       b35b   CALLP.S2  0xc0128e54,B3      ; 16-bit compact instruction
c0129326       a18a   BNOP.S1   0xc012932c,5       ; 16-bit compact instruction (same fetch slot)
c0129328   0000a43e   STB.D2T2  B0,*+B14[164]
```
`c0129324`/`c0129326` together occupy ONE 32-bit fetch slot (`0xa18ab35b`) as a pair of
16-bit "compact" instructions -- confirmed by the leading whitespace-only address
column in main.dis (this disassembler's convention for marking a 16-bit compact
instruction that shares a 4-byte slot with its neighbour, vs. the full 8-hex-digit word
shown for 32-bit instructions like the `STB`s bracketing it).

I checked how this codebase's own patch tooling redirects `CALLP`s
(`tools/make_controller_fw.py`):
```python
def callp_target(addr, word):
    cst = (word >> 7) & 0x1fffff
    if cst & 0x100000: cst -= 0x200000
    return (addr & ~0x1f) + 4 * cst

def callp_retarget(addr, word, target):
    disp = (target - (addr & ~0x1f)) // 4
    ...
    new = (word & ~(0x1fffff << 7)) | ((disp & 0x1fffff) << 7)
```
This extracts a 21-bit signed displacement from bits [27:7] of a **32-bit** CALLP
encoding, PC-relative to the enclosing 32-byte fetch-packet group. It assumes the word
it is given is already in that 32-bit format. The compact 16-bit encoding at
`c0129324` (`b35b`) is a completely different bit layout (whole instruction fits in 16
bits, so its displacement field is necessarily much narrower than 21 bits) -- feeding
`0xa18ab35b` into `callp_target()`/`callp_retarget()` as-is would misinterpret the
compact bit pattern as if it were the 32-bit field layout and silently compute a wrong
target. So neither this repo's existing `callp_target`/`callp_retarget` helper, nor an
in-place "just edit the displacement bits" patch, can be used directly on the compact
pair at `c0129324`/`c0129326`.

However, this repo already has, and uses, the right technique for exactly this
situation: `tools/make_usb_audio_fw.py`'s `"callp_over"` patch kind. Example already in
production use there: site `0xc015c674`, whose **stock word is not a CALLP at all**
(`d026a120`, a conditional `BNOP`) -- the tool does not try to edit that word's bits;
it **replaces the whole word** with `CALLP_S2_TEMPLATE = 0x1050c512` (a canned,
unconditional, non-parallel 32-bit `CALLP.S2`) and then calls `ctl.callp_retarget(vma,
CALLP_S2_TEMPLATE, target)` to fill in the real displacement. The same recipe applies
directly to `c0129324`: overwrite the full 32-bit slot `c0129324..c0129327` (both
compact halfwords at once) with `callp_retarget(0xc0129324, CALLP_S2_TEMPLATE,
<hook_addr>)`. Both original compact instructions are unconditional (no predicate
shown in the disassembly), so no predicate semantics are lost. Our hook function
receives control with `B3` already set to the return address (`0xc0129328`, the next
fetch packet -- CALLP's standard behavior) by the CALLP itself; for "not mine"
messages it can simply `CALLP 0xc0128e54,B3` itself (replicating exactly what stock
did) and finish with its own `BNOP B3,5`, which lands back at `0xc0129328` and
continues the byte-read loop exactly as stock would have. Confidence: confirmed (code
read directly from `tools/make_controller_fw.py` and `tools/make_usb_audio_fw.py`).

### 9. Recommendation: Option A via "callp_over" at c0129324, not Option B (dispatcher-entry replacement)
F8 recommended Option B (patching `c0128e54`'s entry) "for patch tool simplicity,"
reasoning that it avoids touching the compact fetch packet. Having read both sites,
that reasoning is backwards given what tooling already exists:
- `c0128e54`'s entry word (`c0128e54 01bc54f6 STW.D2T2 B3,*B15--[2]`) is a plain 32-bit
  `STW` function prologue, not a `CALLP` at all. Redirecting it requires inserting a
  multi-instruction veneer (MVK/MVKH/B, like the `TAP_VENEER`/`UI_HOOKS` pattern this
  repo uses elsewhere for non-CALLP sites), which overwrites **at least 2 words**
  (the `STW` prologue and the following `LDW *+B14[38],B2`), and our hook would then
  have to manually replicate the `STW B3,*B15--[2]` stack-frame push that it
  destroyed, since `c0128e54`'s own epilogue (`c0129110 LDW *++B15[2],B3`) still
  expects that frame if stock dispatch is ever re-entered past the overwritten
  prologue.
- `c0129324` is the sole call site (Finding 1) and, despite being compact-encoded, is
  a clean single-word `"callp_over"` target using a pattern already proven in this
  exact codebase (Finding 8). It touches exactly one 32-bit-aligned slot, needs no
  veneer, and needs no change to `c0128e54` itself.
**Recommendation: patch the full 32-bit word at `0xc0129324` with
`callp_retarget(0xc0129324, CALLP_S2_TEMPLATE, <hook_addr>)` (the `callp_over`
technique)**, not Option B. Confidence: likely (sound given the two sites' actual
encodings and the existing tooling's capabilities, but the hook function itself and
its interaction with Finding 3's payload-capture gap are not yet built/tested).

## Answers

### (1) MIDI task F7 handling / sole caller of c0128e54
F7 (EOX) is handled at `c0129320` (`STB 0,*B14[164]`) immediately followed by
`c0129324 CALLP.S2 0xc0128e54,B3` inside the MIDI task's main byte-read loop
(`c0129118`). Whole-file grep plus a scan for register-indirect construction of
`0xc0128e54` found exactly one call, at `c0129324` -- **confirmed**. (recon's
`chunk_04.md` attributes the call to the enclosing symbol `c0129276` by table-target
granularity, not a second call site -- see Finding 1.) Can a patch change it: yes,
it's a single instruction/word; risk is low since it's the only caller. Patch site:
`0xc0129324`, see Answer 5.

### (2) Command byte, payload buffer, length variable, unknown-command storage
- Command byte: halfword at `0xc0183b60`, stored unconditionally (even for unknown
  commands like `0x70`) by `c0127df0`/`c0127df8` before any recognition check --
  **confirmed**.
- Length variable: `*+B14[43] - 1` is correct for the word-indexed field
  (`0xc0184e00 + 4*43 = 0xc0184eac`), confirmed by direct `LDW`/`STW` use throughout
  the state machine. **Caveat (confirmed)**: the brief's generic formula
  `B14[n]=0xc0184e00+4n` does NOT hold for the byte-width parser flags `B14[164..168]`,
  which are addressed as `0xc0184e00+n` (byte offset, not `n*4`) -- see Finding 4.
- Payload buffer: `0x1180ff20`, max 1024 B, overflow-checked -- confirmed the routine
  exists and matches F8's excerpt exactly. **But (confirmed, corrects F8): raw payload
  bytes are only ever routed there when the stored command byte equals exactly 0x64
  (100 decimal)**, via `c0127d78 -> c016f760 (veneer) -> 0x11803010`. Any other
  command value, including an arbitrary "free"/unused one like `0x70`, has its
  payload bytes silently dropped by `c0127cf4`'s unconditional fallthrough return at
  `c0127d48` -- nothing is stored at `0x1180ff20` for it. See Finding 3 for the full
  trace and a proposed (unsized) companion patch.
- `B14[38]` (internal command id) is unconditionally zeroed after every dispatch
  (Finding 5, confirmed), so there's no cross-message stale-value risk for a repeated
  unknown command.

### (3) Manufacturer/device/model checks
A message with device `0x00` and model `0x6e` does reach state 3 -- **confirmed** --
but not because those values are validated. **Confirmed/extended beyond F8**: the
device-ID byte (`B14[168]`) is stored with *no value check at all* (any byte 0x00-0x7F
is accepted), and the model byte is likewise never compared against anything (state
2's handler, `c0129276`, only increments the state and resets the counter). The ONLY
gate is the manufacturer byte at state 0: must be exactly `0x52` (Zoom, -> state 1->2)
or `0x7E` (Universal, -> state 1->4, bypassing the model-ID state); any other
manufacturer byte aborts the message back to state 0. F8's claimed storage target for
the model byte, `*+B14[166]`, is written unconditionally for every byte (not
specifically by the state-2 handler) and is never read anywhere in main.dis -- it is
dead/write-only, not a usable "stored model ID."

### (4) Reply path c01274cc
Signature confirmed by direct disassembly: `void c01274cc(uint8_t *buf /*A4*/,
uint32_t len /*B4*/)`. Verified end-to-end against a real stock caller, `c0127500`
(builds a 7-byte `F0 52 00 <model> .. .. F7`-style reply on the stack, then
`CALLP 0xc01274cc,B3 || MVK.L2 7,B4`). It blocks (BIOS_WAIT_FOREVER) on mutex
`B14[161]` via `c0150b20`/`c01628e0`, queues into a ring via `c0144dc8`, and does not
wait for USB-wire completion. Confirmed 24 call sites, all inside the MIDI/editor
command region (c0127xxx-c012dxxx) or the MIDI task itself (c0129xxx) -- consistent
with Task-context-only use, matching F8. Max bytes per call: 1024, confirmed via the
ring's `SET A0,10,10,A0`(1024)/`CMPLT` index-bound logic; the claimed exact ring base
address `0xc0117b28` was NOT independently found by grep this session (not confirmed,
not refuted).

### (5) Best hook: recommend "callp_over" at c0129324, not dispatcher-entry replacement
Recommended patch: replace the full 32-bit word at `0xc0129324` (currently the compact
pair `b35b`/`a18a` = `CALLP.S2 0xc0128e54,B3` + `BNOP.S1 0xc012932c,5`) with
`ctl.callp_retarget(0xc0129324, CALLP_S2_TEMPLATE, <cf_probe_hook_addr>)` using the
`"callp_over"` technique already in production in `tools/make_usb_audio_fw.py`
(precedent: site `0xc015c674`). This is a single-word, single-site patch requiring no
veneer and no change to `c0128e54`. Rejected: F8's "Option B" (patching `c0128e54`'s
`STW` prologue) -- that word is not a CALLP, is incompatible with the existing
`callp_retarget` helper, and would need a >=2-word MVK/MVKH/B veneer plus manual
replication of the stack-frame push it would destroy. Risk: low for the call-site
patch itself; the unresolved risk is Finding 3 (payload capture for an arbitrary free
command needs an additional, not-yet-sized patch at `c0127d48`).

## Not checked / open leads
- The exact TX ring-buffer base address `0xc0117b28` claimed by F8 for `c01274cc`'s
  transport -- the bound-check logic was confirmed but the literal base address was
  not independently located in main.dis this session.
- The exact bit encoding/size of the companion patch needed at `c0127d48` (currently
  `010ca120 BNOP.S1 0xc0127f58,5`) to redirect unmatched commands' payload bytes into
  the existing `0x1180ff20` store path (Finding 3) -- identified as necessary but not
  encoded or sized.
- F8's claimed file offsets (`0x0001d2a0` for `c0129324`, `0x0001cdd4` for `c0128e54`)
  inside `build/fw/res1_493412.bin` were not independently verified. A rough check
  using the one documented VMA<->offset anchor in `tools/make_controller_fw.py`
  (`USB_STR3`'s `CONST_DATA[0] + addr - 0xc016f780`) gave a value ~12 bytes off from
  the one HOOKS-table data point I could cross-check (`0xc0134e14 -> 0x28d90`
  stated vs. `0x28d9c` computed), so that single-anchor formula is not reliable for
  verifying file offsets outside the const-data region; the next job should use
  `make_controller_fw.py`'s own `ais_commands()` walker against the real binary
  instead of a linear formula.
- Did not build, assemble, or test an actual `cf_probe_hook_addr` veneer; this report
  only verifies the hook *site* and *encoding technique*, not a working hook binary.
- Did not examine the 0-9 function-pointer table at `0xc0183b74` or the 40-47 table at
  `0xc0183b9c` in detail (only confirmed they exist and are distinct from the
  `0x1180ff20` path) -- out of scope for the free-command question but may matter if
  a later job wants to reuse one of those command slots instead of adding a new
  branch.
