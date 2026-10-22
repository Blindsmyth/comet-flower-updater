# S10 - Slot watchdog design on top of the bench hook (design only)

## Status
running

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

## Answers

## Not checked / open leads
