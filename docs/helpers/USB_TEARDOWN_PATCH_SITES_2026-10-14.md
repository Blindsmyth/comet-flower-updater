# USB teardown diagnostic: patch-site feasibility (first pass) — 2026-10-14

Author: Claude (offline, from `build/fw/map/main.dis`; no Argon reply was used). **DO_NOT_FLASH.**
Everything below is my own instruction-level decode. Items marked (UNVERIFIED) have not been cross-checked.

## 1. Corrections/clarifications to earlier docs (decoded this pass)

`c011fa20(q)` is a queue **pop**, not a count:
- `c011fa20..fa2c`: reads the queue-pop register at `0x01e00000 + 16*q + 4*0x1803` (word `*A4[A5]`).
- `c011fa34..fa50`: `A1 = reg & ~0xf`; if `A1 < 0xc87b9000` returns **-1** (empty), else returns
  `(A1 - 0xc87b9000) >> 5` = **descriptor index** (descriptors are 32 B each, base `c87b9000`).
- Callers test `CMPGT 0,A4,A0` (i.e. A4 < 0) => `A0 != 0` means *empty*.

`c011fa54(idx)` (`c011fa54..fa6c`) returns `type == 16` where `type = word0[31:27]` of
descriptor `c87b9000 + 32*idx`.

`c0120550(idx, B4, A6, B6=slot)` is the recycle helper called with `B4=0, A6=1, B6=A10(slot)` at `c0120748..0750`.

## 2. What the abort drain loop really does (c0120734..c0120762)

```text
c0120734  A4 = pop(A14)           ; A14 = *(c01805d0 + 12*N - 4)  (queue id from template, UNVERIFIED which word)
c0120740  if empty -> c0120764
c0120744  c011fa54(idx)           ; type test, result discarded (A4 overwritten at c012074a)
c0120748  c0120550(idx,0,1,slot)  ; recycle EVERY popped entry
c0120754  A4 = pop(A14); [!A0] loop to c0120744
```
So, once reached, it drains the whole queue `A14` and recycles every entry **regardless of type or channel**.
Type-19 teardown descriptors popped here are recycled with no association check. That matches the
ownership gap described in USB_TEARDOWN_DECISION; this decode narrows it: the discarded value is the
`type==16` result of `c011fa54`, and the loop is unconditional-until-empty.

Reaching `c0120734` implies the preceding bounded poll (`c0120716..0728`, limit A6=128 at `c01206fa`) did
not expire: expiry takes `[!A0] BNOP c0120764` at `c0120732` (A0 = A1<A6). The poll writes the teardown
request word (`A3`, bit `A9=1<<(N-1)`, `EXTU A0,28,11`) to `0x01e0001c`(UNVERIFIED address: ADDAW A2,7 with A2=0x01e00000)
inside the branch delay slot each iteration (`c0120720`) and once more at `c012072e`.

## 3. Which sites can be hooked (HOOKS pattern needs a **32-bit** CALLP word)

| Site | Instruction | Width | Retargetable by HOOKS? | Use |
|---|---|---|---|---|
| `c0120734` | CALLP `c011fa20` (A4=A14) | 32-bit | yes | log "poll did not expire" + pop result |
| `c0120744` | CALLP `c011fa54` | 32-bit | **yes — best site** | log idx, descriptor word0, slot (A10) just before recycle |
| `c0120754` | CALLP `c011fa20` | 32-bit | yes | log next pop |
| `c0120780` / `c0120798` | CALLP `c011fa20` (late drain, A4=A11) | 32-bit | yes | log late-drain pops |
| `c0120748` | CALLP `c0120550` | 16-bit compact | **no** (no room to retarget) | — |
| `c0120732`, `c0120764` | BNOP / MV | 16-bit | no | expiry itself is NOT directly hookable |

Expiry can only be inferred: a request without a following `c0120734` event.

## 4. Thunk contract for the `c0120744` site (proposed, not implemented)

- On entry A4 = idx (also in A3), A10 = endpoint slot (callee-saved), B3 = return address into the abort routine.
- Thunk may clobber only A0, A1, B31-style scratch it saves; must preserve A3, A4, A10, B3 and tail-call `c011fa54`
  so its return value reaches `c0120748`'s packet as before (stock behaviour unchanged).
- No kernel calls: this is task context, but the Hwi may run the same consumer — trace writes must be single-word
  stores into a fixed ring in `.ctl_state` with an index increment that tolerates preemption (write entry, then publish index).
- Record: `{seq, site_id, slot, idx, word0 = *(c87b9000+32*idx), TSCL}` = 16 B/entry; ring of 24 entries = 384 B (<= 512 B).
- Sticky fault code: set if `word0[31:27] == 19` is recycled at this site (the ownership gap actually occurring).

## 5. Unproved / next

1. Meaning of the `A14` template word (which queue it selects for N=4) — decode `c0120658..0674` fully.
2. The Hwi consumer body `c011faa0` (not read this pass) — where it records or moves type-19 entries; needed for a second trace site.
3. Writer of `0x01e0001c` and whether repeated writes in the poll loop are harmless (UNVERIFIED).
4. Free payload space and `HOOKS` row additions in `tools/make_controller_fw.py` (needs word + AIS offset lookup for `c0120744`).
5. Tests: extend `tests/` to assert the new hook row decodes to the new symbol and the stock word is unchanged elsewhere.

## 6. Addendum (second pass, same day) � resolved items

Resolved "Unproved" 1, 2, 3, 4 from section 5 (decode from `main.dis`; still no hardware run):

1. **Template words.** For slot N, template words are at `c01805c4+12N` (word0), `c01805c8+12N` (word1), `c01805cc+12N` (word2).
   Stored for MIDI N=4 = `{22,24,25}` (per USB_TEARDOWN_DECISION). The abort poll/drain uses **word2 = 25**
   (`c0120674` LDW `*-B4[1]` -> A14; same word gives `A8 = 1<<25` at `c012068c..0698`). The late drain uses word0 = 22
   (`c0120778`). So the drain loop at `c0120734..0762` is on queue **25 (shared TX teardown queue)**.
2. **Poll.** `c0120716..0728`: reads pending register `0x01e04090` (`15<<21` + `0x4090` from `c01206f4..06f8`) and tests bit 25;
   while clear it re-writes teardown request word A3 to `0x01e0001c` (`ADDAW A2,7`) and loops up to 128 times
   (`c01206fa`: A6=128). Expiry (A1==128) skips the drain via `c0120732 [!A0] BNOP c0120764`.
3. **Hwi consumer `c011faa0(q)`.** Pops queue q (`c011fa20`), runs the type test (`c011fa54`). If type != 16 it jumps to
   `c011fb70` with A7=0 and pushes the descriptor to **queue 32** (`c011fb74` -> `c011fa70(32)`); if type == 16 it
   further inspects word1 `[31:27]` (must be 1..5), looks up per-channel state, and pushes to queue 34 or 32
   (`c011fb72..fb80`). Therefore a type-19 teardown descriptor reaching the Hwi first is **moved to queue 32 and never
   appears in queue 25 for the abort poll** � the poll then runs to expiry. This is the control-flow race; whether it
   occurs on hardware is still unmeasured.
4. **Hook row.** `c0120744` file offset `0x146c0`, stock word `1ffe6292`, target `c011fa54` (verified by decode; also
   `c0120734 @0x146b0 1ffe6013`, `c0120754 @0x146d0 1ffe5c13`, `c0120780 @0x146fc`, `c0120798 @0x14714` all decode to
   `c011fa20`).

## 7. Implemented: offline diagnostic candidate (observer only)

- `firmware/controller/controller_diag.c` (ring of 24x16 B + header = 400 B in `.ctl_state`, sticky fault bits),
  `controller_diag_hooks.asm` (80-byte register-preserving thunk, tail-calls `c011fa54`), `controller_diag.cmd`.
- Build: `python tools/make_controller_fw.py --diag-teardown --out build/controller/diag_teardown_candidate.bin`
  (separate object dir `build/controller/diag/`; payload 3648 B vs 2880 B lifecycle). Lifecycle build is byte-identical
  to before (SHA `3e7f5236...28b9`). `DIAG_HOOKS` is not in `HOOKS`, so `make_fs_restore_updater.py` and
  `verify_controller_candidate.py` do not accept it. It is **not** an updater input.
- Fault bits: `0x1` type-19 popped+recycled by the abort drain, `0x2` channel mismatch (mapping `slot-1` verified only
  for slot 4), `0x4` ring wrapped.
- Limits: this site only sees entries the abort loop pops. A teardown moved to queue 32 by the Hwi (item 3) is *not*
  observed here � a second observer in the Hwi consumer or at the queue-32 consumer (`c0121a18..24`) would be needed.
  Stack gate still open: thunk adds 80 B + the C callee frame to the abort path.
