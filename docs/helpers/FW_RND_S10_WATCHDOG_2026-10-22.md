# S10 - Slot watchdog design on top of the bench hook (design only)

## Status
done

## Findings

### Finding 1: the slot loop and the veneer hook, re-verified independently in main.dis
**Confirmed**, re-disassembled `build/fw/map/main.dis` lines ~18270-18333 myself
(not just trusted from the brief):
```
11818be0  MVK.S2 0x33e0,B4 / MVKH.S2 0x11810000,B4 ; B11 = 0x118133e0 (slot callback table)
11818bec  [B0] BNOP.S1 0x11818c44,5     ; tuner-mute skip of the whole loop
11818bfc  MVK.L2 0,B10                 ; B10 = slot index k, k=0 start (c0184e00+102*4=0xc0184f98)
11818c00  ADDKPC.S2 0x11818c04,B3,0
11818c04  CALLP.S2 0x11818eb0,B3       ; <-- the veneer (ua_slot_enter after BENCH_PATCHES retarget)
11818c08  MV.L1 A4,A10                 ; veneer's return value (A4) kept as the slot's context ptr
11818c0c  LDW.D2T2 *+B11[B10],B5       ; B5 = per-slot kernel fn ptr, table B11[k] = 0x118133e0+4k
...
11818c16  BNOP.S2 B5,0                 ; call the slot k kernel (branch+link via B3/ADDKPC at 11818c18)
11818c20  LDW *+B14[102],B4 / ADD 1,B4,B10  ; k++
11818c28  CMPGT.L2 5,B10,B0            ; loop while k<5
11818c2c  [B0] B.S1 0x11818c00         ; back to top (next slot's veneer call)
```
So the veneer at `11818eb0` runs **once per slot, immediately before that
slot's kernel function pointer is fetched from the table at
`0x118133e0 + 4*k`** and before the kernel is called. Its return value (A4)
is architecturally required (it becomes the context pointer A10/B4 passed
into the kernel), so any replacement must keep returning the same value
the stock veneer did (`UA_SLOT_CTX = 0x11f03b48`, confirmed from
`firmware/usb_audio_proto/usb_audio_tap.c:337-346`, comment at line 335-336
citing the stock target `c01502cc: MVK/MVKH A4; BNOP B3,5`).

### Finding 2: the existing bench hook already computes exactly the per-slot duration a watchdog needs
**Confirmed by direct code read**, `firmware/usb_audio_proto/usb_audio_tap.c:337-346`
(`ua_slot_enter`) stamps `ua_bench_t[UA_B_S0+k] = TSCL()` on every slot entry
(`k = *(volatile int*)0xc0184f98`, the same B10/slot-index cell the loop above
uses), and `ua_bench_build()` (lines 498-515, called from `ua_tx_pack_tap`
at line 518-522, once per block) already derives
`v[k] = t[S0+k+1] - t[S0+k]` for k=0..3 and `v[4] = t[POST] - t[S0+4]` --
i.e. **slot k's wall-clock cycle cost is already computed today**, just for
USB telemetry (channel 8 bench frame), not for any runtime decision. This is
the natural value to feed a watchdog threshold check; no new timestamp
capture is needed, only a new consumer of the same deltas.

### Finding 3: extending ua_slot_enter (and ua_bench_build) touches zero hand-scheduled Swi code
**Confirmed (by construction), likely (as the key risk-reduction choice).**
`ua_slot_enter`/`ua_bench_build` are plain C functions, reached only via the
veneer's `BNOP B3,5` into a normal C-ABI callee (per `make_usb_audio_fw.py`
`BENCH_PATCHES`, only the veneer's two 16-bit MVK/MVKH constant halfwords at
`11818eb0`/`+4` change -- the call site `11818c04` and the loop at
`11818bec..c2c` are untouched). This means a watchdog built entirely inside
`ua_slot_enter`/`ua_bench_build` (reading/writing ordinary C statics, plus
one pointer write into RAM described in Finding 4) **never needs to insert
instructions into the hand-scheduled, software-pipelined slot loop itself**,
which is exactly the risk S4's own containment proposal flagged ("insertion
in hand-scheduled L2 code with delay slots" -- `docs/helpers/FW_RND_S4_FAULT_2026-10-22.md`
line ~263). This is the central design choice of this report: do the
timing/decision/mitigation entirely in the C hook, never touch 11818b00-c80.

### Finding 4: the slot callback table (0x118133e0 + 4k) is writable RAM, and overwriting one entry is the cheapest bypass mechanism
**Likely.** The table lives in the same contiguous L2 region as the shared
Hwi/Swi stack (`0x118133e0` vs. stack `0x118134a8..0x11816468`, both already
confirmed addresses per `docs/FW_RND_ANSWERS_2026-10-22.md`'s address map
"just below the stack: slot callback table, peripheral pointers"), which is
plain L2 SRAM (read/write at the CPU's own privilege level, no MMU/MPU
protection scheme was found anywhere in this reading). I did not find an
explicit store instruction to `0x118133e0+4k` in `main.dis` within my time
budget (828 hits for the shared `0x11810000` MVKH base alone, too many to
scan individually; the loader functions `c0146e18`/`c01453b4` from S2's
loader range are called repeatedly near `c0133b30`/`c0136760` and are a
likely place this table is populated per slot at patch-load time, not
independently confirmed which exact store does it). Confidence is "likely"
(not confirmed) that the table is written once per patch/slot (re)load and
left alone during normal block processing, based on: (a) it must be
initialized somewhere for the stock loop to work at all, (b) nothing in the
audio Swi's own slot loop (Finding 1) writes it, only reads it. Design
implication: a watchdog can overwrite one 4-byte entry at
`0x118133e0+4*k` to redirect slot k's *next* call to a bypass stub, and
this survives across blocks until the next patch/slot (re)load naturally
rewrites the whole table back to the loaded effect's real pointer (self-
healing on patch reload; no permanent state needed elsewhere).

### Finding 5: dspload-derived cycle budgets are self-declared bookkeeping, not firmware-verified -- usable only as a loose cap
**Confirmed (the mechanism), likely (as a design caveat).** The brief's
`7 + 3 x kcycles` scale is `docs/DSP_RULES.md:80` ("fitted to the
2026-10-18 bench... HW100 21.9k -> 72.7 vs 71.16 declared; TS Drive 10.3k ->
37.9 vs 39.37; COMP 2.3k -> 13.9 vs 13.94"); the same file's history also
cites a competing fit from an earlier date ("dspload = 3.7 x measured cold
kernel kcycles", `recon/04_hardware_log.md` line 74-area, cited via S1/earlier
notes), so the two fits disagree by roughly 2x at the same cycle count --
this value has never been firmware-enforced (`docs/FW_RND_ANSWERS_2026-10-22.md`
Q6: "the only protection is the EDMA ping-pong... not measured cycles... the
admission gate is only the declared dspload sum (< 230), not measured
cycles"), so it is only as good as the honesty/accuracy of whoever set the
ZD2's `dspload` field (`tools/zd2_set_dspload.py` changes only that float +
CRC, independent of the kernel). A per-slot declared-dspload budget is
therefore a **coarse, author-supplied** ceiling, not a measured one -- fine
as a generous safety cap (large multiplier) but not trustworthy as a tight
one. The Process-Overflow sum's own per-slot fetch is `c012edcc` (named/called
from `c0141ae8` inside the sum loop, `docs/helpers/FW_RND_S1_LIST_PARAMS_2026-10-22.md`
Finding 1), confirming a function already exists that reads a given slot's
declared dspload float and could be called once at patch-load time to seed
the watchdog's per-slot budget table (not inside the realtime hook).

### Finding 6: the real SYS/BIOS c64p exception dispatcher is found and disassembled (goes further than S4's gap)
**Confirmed (the function exists and its early structure), likely (its final
policy).** `grep -n "EFR\|IERR\|NRP\|ECR\b" build/fw/map/main.dis` turns up a
dense cluster at `c01625e0..c0162710` that I disassembled in full
(`main.dis` lines 116755-116845). It is unmistakably a compiled
`ti.sysbios.family.c64p.Exception` dispatcher:
```
c01625e4  MVC.S2 EFR,B1 ; CMPEQ 1,B1,B1 ; [B1] B.S2 NRP      ; early-exit #1 (return from NMI)
c0162608  MVC NTSR,B0 ; MVC IERR,B1 ; SHR2 B0,5,B0 ; XOR B0,B1,B0
c0162618  [!B0] MVC NRP,B0                                    ; early-exit #2
c0162620  MVC ISTP,B1 ; XOR B1,B0,B0 ; CLR B0,5,9,B0
c016262c  MVC EFR,B1 ; SUB B1,0x2,B0(cond) ; [!B0] B.S2 NRP   ; early-exit #3
c0162640  [!B0] MVC B1,ECR                                    ; else: record exception cause in ECR
...
c0162654  LDW *+A1[0],B15   ; A1 = 0xc0181fa8 -> switch SP to a SEPARATE exception stack
c0162660..c01626cc            ; full save: A0-A31, B0-B31 (every GP register)
c01626d0  MVC EFR,B0 / MVC IERR,B1 -> push             ; plus EFR, IERR, ITSR, NTSR, IRP, NRP,
c01626dc..c0162708                                        AMR, SSR, ILC, RILC  (the full ExcContext)
c016270c  MVC B0,AMR (=0)    ; DINT at c016274c
c0162730  B.S2 0xc0140e20 (call, ADDKPC sets return)    ; helper: re-reads EFR/NRP/NTSR (likely
                                                           Exception_decode/log -- matches strings
                                                           c01723d7 "use ROV or set enablePrint=true"
                                                           and c017243b "E_exceptionMax: pc=.., sp=..")
c0162750  BNOP.S2 B10,5      ; ***indirect jump*** (no return address set) through a function
                               pointer read from RAM cell 0xc0181f90 (loaded at c016272c)
```
Reached from two sites, `c0166430` and `c01689b0`, both `[!A0] B.S1 0xc0162460`
(a plain conditional branch, not a CALLP) -- consistent with an interrupt
vector stub shape (ISR entries are typically wired as branches, not normal
calls), though I did not trace back further to an actual ISTP-relative
vector table to prove these two sites ARE the hardware vector entries
themselves (open lead). `c0162460` is the function's prologue (register
save) immediately preceding the EFR cluster.

### Finding 7: the final handler target (cell 0xc0181f90) is zero-initialized RAM not present in the flashed image -- final policy not directly provable from this image alone
**Confirmed (the cell is absent from the binary), likely (what it probably
resolves to).** Ran `tools/fwmap/ais.py` `sections()` against
`build/fw/res1_493412.bin` and looked up VMA `0xc0181f90`: **no loaded
section contains this address** (my script found zero matching sections),
meaning it is pure `.bss` -- its contents are not shipped in the flash
image and must be written by XDC/SYS-BIOS startup code at boot, which I did
not locate (only reads of `0x1f90`/`0x1f94` were found in `main.dis`, no
writes -- consistent with a data-driven `.cinit` unpack table rather than
an explicit `STW` instruction, which would need a different search
strategy I did not have budget for). I therefore **cannot directly prove**
which function this cell ends up holding. What I CAN say: the jump at
`c0162750` is an unconditional `BNOP` with no `ADDKPC`/return-address setup
beforehand (unlike the call to `c0140e20` two lines earlier, which does set
one) -- i.e. **this is a true tail jump, not a call that returns into the
dispatcher**. Nothing in the traced path afterward restores the saved
register context or resumes the original Swi. This matches the textbook
SYS/BIOS pattern (`Exception_m_dispatch` -> build `ExcContext` -> call the
decode/log hook -> jump through the configured `System.exceptionFxn`,
whose stock default is `System_exceptionSpin`, an infinite loop) far more
than it matches any kind of per-task resume. Combined with the production
hint in the adjacent string (`"...or set enablePrint = true"`, implying it
ships `false`), I rate **"halts/spins the whole core on an unrecovered
exception" as likely, not confirmed** -- the same honest gap S4 flagged
(`recon/25_boot_safety.md:107`), but now backed by an actual disassembled
dispatcher rather than only the module-linkage strings.

### Finding 8: the exception path, even if it is "halt", is architecturally separate from (and not addressed by) the cycle-based watchdog
**Confirmed (by construction of both mechanisms).** The TSCL-based slot
watchdog proposed below only runs *between* slot calls (inside
`ua_slot_enter`, Finding 1). A genuine illegal-memory/illegal-instruction
fault happens **inside** a slot kernel's call and (per Finding 6/7) is
caught by this SYS/BIOS path instead, which -- if it is indeed
"spin forever" -- never returns control to `ua_slot_enter` for the next
slot at all. So the two containment ideas in the brief (TSCL watchdog vs.
exception handling) protect against **different failure classes**: "too
slow but otherwise valid" (watchdog can catch it, between calls) vs.
"illegal operation / bad address" (only the exception path sees it, and
that path's own policy, not my hook, decides what happens next). A design
that wanted the exception path itself to "catch a fault and bypass just
that slot" would need to replace the cell at `0xc0181f90` (or whatever
ultimately writes it) with a custom recovery routine that, instead of
spinning, identifies the faulting PC/slot from the saved `ExcContext` and
performs a non-standard partial unwind back into the audio Swi's loop at a
known-good resume point (e.g. `11818c20`, the per-slot loop-continue
address from Finding 1) -- a substantially deeper, higher-risk change than
the TSCL watchdog, and **not recommended within this job's scope** (listed
only as a longer-term idea under Open leads).

## Answers

### Watchdog design (per-slot cycle watchdog, built entirely on the existing bench hook)

**Hook points (both already proven to compile/link, Findings 1-4):**
1. `ua_slot_enter()` (`firmware/usb_audio_proto/usb_audio_tap.c:337`) --
   called by the stock veneer at `11818eb0` immediately before each slot's
   kernel pointer is fetched (Finding 1). Unchanged duty: stamp
   `ua_bench_t[S0+k]`. New duty: if `fault_flag[k]` is set, overwrite the
   callback-table entry for slot k (`*(u32*)(0x118133e0 + 4*k)`, Finding 4)
   with a bypass-stub address, on every entry while the flag is set (cheap,
   and self-correcting if anything else ever rewrites the table between
   calls -- not verified not to happen, so re-applying every call is the
   safe default rather than a one-time patch).
2. `ua_bench_build()` / `ua_tx_pack_tap()` (lines 498-522) -- already
   computes each slot's just-finished duration `v[k]` once per block
   (Finding 2). New duty: compare `v[k]` against that slot's budget, update
   a consecutive-overrun counter, and decide whether to set `fault_flag[k]`
   for the *next* block.

**Pseudo-C:**
```c
/* seeded once per patch/slot load from c012edcc(slot)'s declared dspload,
   NOT from inside the audio Swi -- Finding 5 */
static u32 slot_budget_cycles[5];   /* = max(((dspload-7)/3)*1000, FIXED_MIN) */
static u32 overrun_count[5];
static u8  fault_flag[5];
#define WATCHDOG_MULT   4           /* generous: dspload is self-declared, Finding 5 */
#define WATCHDOG_NBLOCKS 8          /* consecutive blocks before tripping */

void *ua_slot_enter(void) {              /* unchanged stamp, Finding 1/2 */
    u32 t = TSCL();
    u32 k = UA_SLOT_INDEX;
    if (k < 5u) {
        ua_bench_t[UA_B_S0 + k] = t;
        ua_bench_mask |= 1u << k;
        if (fault_flag[k])                                  /* NEW */
            *(volatile u32 *)(0x118133e0u + 4u*k) = (u32)bypass_stub;
    }
    return UA_SLOT_CTX;
}

static void watchdog_check(void) {       /* called at end of ua_bench_build */
    u32 k;
    for (k = 0; k < 5u; k++) {
        u32 dur = /* v[k], already computed */;
        if (dur > WATCHDOG_MULT * slot_budget_cycles[k]) {
            if (++overrun_count[k] >= WATCHDOG_NBLOCKS) {
                fault_flag[k] = 1;
                watchdog_status |= (1u << k);   /* for screen/MIDI, see below */
            }
        } else {
            overrun_count[k] = 0;               /* reset on a good block */
        }
    }
}
```

**Cost:** per slot per block: 1 subtraction + 1 compare + 1
increment/reset (watchdog_check, once per block, 5 slots = ~15-20
instructions total) +, only while a fault is latched, 1 extra RAM write in
`ua_slot_enter` (cheap, conditional on a flag that is 0 in the healthy
case). Against block costs the project has already measured in the
tens-of-thousands of cycles range (DR103's first build: ~224k/16-sample
block, `docs/DSP_RULES.md:9`; RA200X measured 14.1k, `FW_RND_ANSWERS` Q5),
this is well under 0.1% overhead in the healthy path, and is implemented
entirely in the already-proven C hook (Finding 3) -- no edits to the
hand-scheduled Swi loop at `11818b00-c80`.

**Failure modes:**
- **False positive on a legitimately heavy but valid block** (e.g. a
  "fresh" first-frame init spike, matching RA200X's own `fresh ? 3 : 1`
  derive cost, `FW_RND_S4_FAULT_2026-10-22.md` F4) -- mitigated by requiring
  `WATCHDOG_NBLOCKS` consecutive overruns (brief's own "N blocks in a row"),
  and by excluding the first few blocks after a patch/slot (re)load from
  counting (that data was not traced to confirm how to detect "just
  loaded" from inside the hook; a simple option is a small countdown
  seeded at load time, visible to the loader code S2 found).
- **dspload-derived budget is untrustworthy on its own** (Finding 5: two
  disagreeing historical fits, self-declared, never firmware-verified) --
  mitigated by the large multiplier, and a **recommended alternative**:
  seed `slot_budget_cycles[k]` from an **auto-measured baseline** (e.g. the
  median of that slot's own first ~32 blocks after load, already visible to
  `ua_bench_build`) instead of trusting the ZD2 field at all. This avoids a
  misdeclared `dspload` ever making the watchdog too tight or too loose. Not
  implemented here (design-only); flagged as the stronger long-term choice.
- **Multi-slot effects (CF M3/CF M4/CFMPRE, S8's area):** bypassing only
  the SECOND physical slot of a multi-slot effect that expects both halves
  to run together every block could desync shared state between halves --
  this watchdog treats each physical slot independently and does **not**
  know about S8's "second half" filler-id relationship. Cross-reference:
  this is a real risk for multi-slot effects specifically, not evaluated
  further here (S8's domain).
- **No ready-made "do-nothing" stub with the right calling convention was
  located.** The kernel call expects a context pointer (A10/B4, Finding 1)
  and presumably returns nothing used by the loop; I did not find an
  existing function in the firmware with exactly this leaf signature that
  does nothing. A real implementation would add a tiny (8-16 B) stub placed
  in the slot's own already-allocated 40 KiB code heap
  (`c01f4000 + k*0xa000`, confirmed region per `docs/FW_RND_ANSWERS_2026-10-22.md`
  Q2) -- no new global allocation needed, but not built or verified here
  (design only, per the job's hard rule).
- **The table-write mitigation and the exception path are unrelated**
  (Finding 8): this design does nothing for an illegal-memory/illegal-op
  fault that lands in SYS/BIOS's own exception dispatcher before
  `ua_slot_enter` ever runs again.
- **"Flag it for the screen/MIDI"**: a `watchdog_status` bitmask (5 bits,
  one per slot) is cheap to produce (shown above), but **no path from any
  RAM flag to the pedal's physical screen or MIDI output was located** by
  this job or by S1-S9 (S5's report: "the LCD effect-edit draw code was not
  found"; `FW_RND_ANSWERS` Q7). I can only confirm *where* the flag would
  live (e.g. spare bits 16-31 of the existing bench frame word
  `ua_bench_frame[1]`, `usb_audio_tap.c:509`, currently unused, if riding on
  the bench build; or a new fixed RAM cell for a production build), not how
  a menu/MIDI consumer would read it -- open lead.
- **UA_BENCH-gated vs. shippable:** today's `ua_slot_enter`/`ua_bench_build`
  are compiled only under `UA_BENCH`/`UA_STEMS` (diagnostic bench build,
  `tests/test_usb_audio_bench.py`), likely stripped from any release
  firmware. A shippable watchdog would reuse the *same mechanism* (retarget
  the `11818eb0` veneer, same table-write trick) via a new, always-on
  handler function -- not literally the bench telemetry arrays, which are
  diagnostic-only. Noting this distinction so the design isn't mistaken for
  something already shipping.

**How to test on the bench (never the pedal, per hard rules):**
1. Add a synthetic "slow slot" test kernel (or temporarily lower one real
   slot's `slot_budget_cycles` entry) to force a controlled trip under
   `tests/test_usb_audio_bench.py`'s harness; verify `fault_flag[k]` sets
   only after `WATCHDOG_NBLOCKS` consecutive bad blocks, not on one spike.
2. Verify the mitigation takes effect on the **next** block: read the
   existing bench-frame slot-duration gap (`UA_B_S0+k+1 - UA_B_S0+k`,
   Finding 2) over the USB channel-8 telemetry and confirm it drops to the
   bypass stub's near-zero cost once tripped.
3. Confirm the other 4 slots and USB audio continue with no dropout
   (reuse the existing frame-loss counter already read by the bench).
4. Regression: replay the existing stock bench chains (CFMPRE, Delay, Watt,
   RA200X/CF Rotary) that the 2026-10-18/22 benches already measured within
   normal bounds, and confirm **zero** false trips over a representative
   session.
5. Only after all of the above pass on the bench would this go into a
   test updater for the owner to flash -- explicitly outside this job's
   scope (design only).

### Exception handling policy (summary answer)
**SYS/BIOS's C674x `Exception` module IS linked and its dispatcher was
found and disassembled** (Findings 6-7): on a CPU exception it switches to
a dedicated exception stack, saves the *entire* register file plus
EFR/IERR/ITSR/NTSR/IRP/NRP/AMR/SSR/ILC/RILC into a full `ExcContext`, calls
a decode/log helper (`c0140e20`, matching the module's own "enablePrint"/
"E_exceptionMax: pc=.., sp=.." strings), and then performs an **unconditional
tail jump** (not a call, no later return/restore seen) through a function
pointer held in a `.bss` cell (`0xc0181f90`) whose static value is not
present in the flashed image and was not traced to its write site. This
pattern matches SYS/BIOS's default exception policy (`System_exceptionSpin`,
an infinite halt loop) far more than any per-task resume, so **"halts" is
likely, "reset" or "continue the faulted task" is not supported by anything
I traced**, and remains **not fully confirmed** -- the single biggest open
item, same gap S4 flagged, now with an actual dispatcher trace instead of
only linkage strings. **A fault inside a slot's kernel body (illegal
memory/instruction) would NOT be caught and bypassed by the TSCL watchdog
above** -- that watchdog only observes gaps *between* slot calls; a true
exception is handled (or not) entirely by this separate SYS/BIOS path
first, and if that path's end state is indeed "spin forever", the whole
core -- not just one slot -- stops, which independently supports S4's and
the handoff's "a bad effect crashes USB audio" observation as a side effect
of a whole-core halt. Making the exception path itself slot-selective
(catch, identify the faulting slot from the saved context, resume the Swi
loop at `11818c20` instead of spinning) is a substantially larger, riskier
change than the cycle watchdog and is **not recommended within this job's
design** -- listed only as a longer-term idea below.

## Not checked / open leads
- **The exact write site(s) that populate the slot callback table
  (`0x118133e0 + 4*k`)** were not pinpointed (828 hits on the shared
  `0x11810000` MVKH base were too many to scan in budget); I infer "written
  once at patch/slot load, read-only during block processing" from
  structural reasoning (Finding 4), not a confirmed store instruction.
- **The actual function pointer resolved from `0xc0181f90`** (the
  exception dispatcher's final jump target) was not found -- it is pure
  `.bss`, set by boot/XDC startup code I did not trace (Finding 7). This is
  the one fact that would upgrade "likely halts" to "confirmed halts" (or
  refute it).
- **Whether `c0166430`/`c01689b0` (the two callers of the exception
  dispatcher) are themselves the hardware NMI/exception vector-table
  entries**, or one more level of indirection away from them, was not
  traced (would need the ISTP-relative vector table itself).
- **A ready-made "do-nothing" stub with the slot-kernel calling
  convention** was not found in the current firmware; a real
  implementation needs a small new one (not built here, design only).
- **Auto-baseline budget seeding** (recommended alternative to the
  dspload-derived cap, under Failure modes) was designed in prose only, not
  worked out in pseudo-code or tested.
- Did not re-verify S8's "second-slot filler id 0x1" mechanics myself; the
  multi-slot bypass risk above is reasoned from S8's job description in
  the brief, not independently traced in this job.
- Per the hard rules, nothing here was built, packaged, flashed, or run on
  the pedal; no tools or firmware files were edited.
