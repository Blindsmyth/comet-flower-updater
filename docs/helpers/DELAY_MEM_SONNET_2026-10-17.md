# DELAY_MEM_SONNET: per-slot large work buffer for CF Delay (2026-10-17)

Written by Claude Sonnet 5, answering docs/helpers/DELAY_MEM_BRIEF_2026-10-17.md.
Offline static analysis only (main.dis disassembly + ZD2/ELF parsing with
existing tools/src helpers + dis6x). Nothing on the pedal was touched.

## Summary
D1 (confirmed): framework loop `c014fea0` (called once, see D4) writes
`instance[3]` = address of a 12-byte `{base,end,size}` descriptor at
`c0183470+12*slot`, for all 5 slots unconditionally; descriptor values point
at the fixed, contiguous 0x81330-byte SDRAM regions recon/14 already found.
D2 (confirmed, 2 stock effects cross-checked): DELAY_3S and ANDLY_3S both
read `*+A4[3]` at `.text+0x668` in their process function, then dereference
`desc[0..2]` as `base/end/size` for a textbook circular buffer (wrap by
`±size` against `end`). No framework "request" call exists — the pointer is
pre-populated. D3 (confirmed): no ZD2 header/INFO field and no store in
`Dll_Delay`'s entry-table constructor declares a buffer need; any effect in
any slot gets `instance[3]` regardless. D4 (likely, pedal test needed): the
zeroing (`c0164a98`) and wiring (`c014fea0`) both run from one straight-line
boot-time init block (`c016bee0`), called once from what looks like a
boot-state dispatcher, not per patch/slot load — so a freshly loaded effect
should NOT assume the buffer is clean. Buffers are not shared between slots.
A 6th, disjoint 0x2b1100-byte descriptor (`c01834ac`) is read by unrelated
code, likely the looper (guess) but confirmed to be unreachable via any
effect's `instance[3]`. D5: our effects already use the matching
`void **instance` convention, so a CF effect needs only to read
`instance[3]` and walk `base/end/size`; hard ceiling 0x81330 B = 3.0177 s
mono @44.1 kHz. Open items for a pedal test: boot-vs-per-load zeroing
timing, descriptor field order, the looper buffer's real owner, and an
end-to-end check that a CF-built effect's own `instance[3]` is valid and
slot-correct on real hardware.

## D1. Where are the per-slot large work buffers?

**Confirmed (static).** recon/14 section 2 already establishes the five fixed
0x81330-byte SDRAM regions and their 12-byte `{base,end,size}` descriptors at
`c0183470 + 12*slot`: bases `c0226000, c02a7330, c0328660, c03a9990,
c042acc0`. I re-derived who *installs* and *zeroes* them:

- **Zeroing, confirmed:** `c0164a98` (called once, see D4) zeroes each base
  for 0x81330 bytes (recon/14, re-checked: consistent with the contiguous
  bases — `end = base` of the next slot exactly, e.g. `0xc0226000 + 0x81330 =
  0xc02a7330`, which is slot 1's base; this cross-check between the
  framework-side descriptor table and the effect-side wraparound logic in D2
  raises the descriptor layout from "confirmed from data" to "confirmed from
  data + confirmed from effect code behavior").
- **Installation into the per-slot instance, confirmed by instruction trace:**
  function `c014fea0` (called once from `c016bef8`, see D4) runs a
  software-pipelined loop of exactly 5 iterations (`MVK.L2 5,B0` /
  `MVC.S2 B0,ILC` at `c014fed0`/`c014fed6`) over the effect-instance table at
  `11f03ad0 + 20*slot` (confirmed table base, matches recon/14 section 4).
  Per iteration it does (addresses from `build/fw/map/main.dis`):
  ```
  c014feec  STW.D2T2  B0,*B4++[5]   ; B4 starts at instance_base+12 (word[3]);
                                      stores B0, then B4 += 20 bytes (next inst.)
  c014fef8  ADD.L2    12,B0,B0      ; B0 (the stored value) += 12 (descriptor
                                      stride) for the next iteration
  ```
  B0 is seeded from the OLD value of B4 at `c014fed8` (`MV.D2 B4,B0`), and B4
  itself was set to `0xc0183470` at `c014fec8`/`c014fe c8` (`MVK.S2 0x3470,B4`
  + `MVKH.S2 0xc0180000,B4`). So **instance word[3] (byte offset 12) of every
  one of the 5 slots is unconditionally set to the ADDRESS of that slot's
  12-byte descriptor** (`0xc0183470`, `0xc018347c`, `0xc0183488`,
  `0xc0183494`, `0xc01834a0` for slots 0..4) — not a pointer to the big buffer
  itself, but a pointer to the descriptor that in turn holds
  `{base,end,size}`. Confidence: **confirmed** (direct instruction trace of a
  fixed, unconditional 5-iteration loop with no effect/flag check at all,
  cross-checked against two different stock effects in D2).
- **Always present for all 5 slots, confirmed:** the loop above has no
  conditional branch, no test of any effect-declared field, and runs exactly
  5 times regardless of what (if anything) is loaded into a slot. Combined
  with the unconditional `c0164a98` zeroing (also a fixed 5-iteration pass,
  recon/14), the buffers are reserved and wired for every slot all the time,
  not allocated on request. Confidence: **confirmed**.

## D2. How does DELAY_3S get the pointer?

**Confirmed**, by disassembling the effect's own code. Extracted
`backup/2026-10-04/files/DELAY_3S.ZD2`'s `DATA` block (15333 bytes, ELF
magic, CRC-valid per `src/zd2tools/parser.py`) to
`build/scratch/sonnet_delaymem/DELAY_3S.elf` and ran the repo's permitted
`dis6x` (`C:/Users/z/ti/ti-cgt-c6000_8.5.0.LTS/bin/dis6x.exe`, the same CGT
path `tools/make_controller_fw.py`'s `CGT` constant points at) ->
`DELAY_3S.dis`. Addresses below are offsets into this effect's own `.text`
(it starts at vaddr 0 in the ELF; at runtime it is relocated into whichever
slot's 40 KiB SDRAM code region is holding this effect — recon/14 section 1).

The process function `Fx_DLY_Delay` (`.text+0x620`, called with `A4`=effect
instance, matching our own effects' `void **instance` convention in
`effects/common/hiwatt_kernel.h`/`effects/ratx/ratx.c`) contains, inside its
main software-pipelined audio loop:
```
.text+0668  [ ]^   LDW.D1T1  *+A4[3],A27     ; A27 = instance[3] = address of
                                                this slot's 12-byte descriptor
...
.text+0868  [A0]   LDW.D1T1  *+A27[2],A7     ; A7  = descriptor[2] = "size" (conditional: only on underflow)
.text+0874         LDW.D1T2  *+A27[0],B5     ; B5  = descriptor[0] = "base"
.text+0898         LDW.D1T1  *+A27[1],A3     ; A3  = descriptor[1] = "end"
.text+089c         LDW.D1T1  *+A27[2],A5     ; A5  = descriptor[2] = "size" (second use, for read-side wrap)
```
and uses them as a classic circular buffer:
```
.text+085c  SUB.S1   A26,0x4,A26      ; write cursor -= 4 bytes (one sample)
.text+0860  CMPGT.L1 0,A26,A0         ; A0 = (cursor < 0)?
.text+0880 [A0] ADD.L1 A7,A26,A26     ; if underflowed, cursor += size  (wrap)
.text+0888  ADD.S2X  B5,A26,B5        ; absolute write addr = base + cursor
.text+088c  STW.D2T2 B6,*+B5[0]       ; write new sample
.text+08a4  ADDAW.D2 B5,B6,B6         ; tap1 addr = write_addr + tapOffset1*4
.text+08a8  ADDAW.D2 B5,B7,B5         ; tap2 addr = write_addr + tapOffset2*4
.text+08ac  CMPLTU.L2X B5,A3,B1       ; tap2 < end ?
.text+08ae  CMPGTU.L1X A3,B6,A0       ; end > tap1 ?
.text+08b4 [!B1] SUB.L2X B5,A5,B5     ; if tap2 >= end, tap2 -= size (wrap)
.text+08c4 [!A0] SUB.L1X B6,A5,A3     ; if tap1 >= end, tap1 -= size (wrap)
.text+08c8  LDW.D2T2 *+B5[0],B7       ; read tap2 sample
.text+08cc  LDW.D1T1 *+A3[0],A3       ; read tap1 sample
```
So: **DELAY_3S gets the pointer from its own instance argument, word offset
3 (`instance[3]` / `*+A4[3]`)**, exactly where the framework (D1) put the
descriptor address. It then dereferences that descriptor's three words
(`base`, `end`, `size`) itself on every sample; there is **no separate
framework call** the effect makes to "get" or "request" the buffer — it is
simply already present in the instance struct the framework passes to every
callback. Confidence: **confirmed** for the mechanism (direct disassembly);
the exact semantics of the two taps (tap1/tap2, likely the wet/feedback read
positions for a single delay line, not stereo) are **likely** but not traced
further since they are not needed to answer the brief's memory questions.

**Cross-check (raises confidence to confirmed-general, not a DELAY_3S
fluke):** disassembled `ANDLY_3S.ZD2` (analog delay) the same way. Its
`Fx_ANDLY`-equivalent process function has the **identical** instruction at
the **identical offset**: `.text+0668  LDW.D1T1 *+A4[3],A27`. The two
stock delay effects share this exact compiled sequence, so this is the
general per-slot delay-buffer access pattern for the delay family, not a
one-off.

**Framework side (the other half, already in recon/14, re-verified in D1):**
the pointer is supplied by `c014fea0` (called once from `c016bef8`) writing
`*+B4[3]`-equivalent (`instance+12`) for all 5 slots before any effect runs;
DELAY_3S never calls into the framework to obtain it — it is pre-populated.

## D3. Does the effect file declare it needs the buffer?

**Confirmed: no.** Checked both places an effect file could plausibly
declare a memory need:

1. **ZD2 container header/INFO block.** Parsed all four delay-family ZD2
   files with `src/zd2tools/parser.py` (existing helper, tagged-block
   format). The `INFO` block (20 bytes) for all four is: word0=0 (effect
   class "normal", per `src/zd2tools/models.py`'s `ZD2Info.word0` comment),
   an 8-byte group-name string `"DLYDELAY"`, and a float `dspload` (declared
   CPU %: 13.74 for DELAY_3S/ANDLY_3S, 17.43 TAPEECHO, 19.07 MODDELAY — a
   trusted-but-unverified CPU budget per `models.py`'s comment, nothing about
   memory). No field anywhere in `ZD2Header` or `ZD2Info` encodes a work-
   buffer size or a "needs large buffer" flag. Confidence: **confirmed**
   (direct parse of all 4 delay ZD2 files' INFO blocks).
2. **The effect's own `Dll_Delay` entry-table constructor**
   (`DELAY_3S.dis` `.text+0xbec`). This is the function the loader calls once
   to populate the 36-byte per-slot "entry" struct (recon/14 section 3; a
   *different* struct from the 20-byte "instance" struct discussed in
   D1/D2). Traced every store it makes:
   ```
   .text+0c00  STB.D1T1 A0,*A4[0]      ; entry[0] (byte)  = 6
   .text+0c02  STW.D1T2 B0,*A4[1]      ; entry[1] (word)  = 0x80000000 (ptr to .const param table "Delay")
   .text+0c14  STW.D1T1 A1,*A4[3]      ; entry[3] (word)  = 0x80000150 (ptr to effectTypeImageInfo)
   .text+0c16  STW.D1T2 B1,*A4[6]      ; entry[6] (word)  = 0x00000104 = Fx_DLY_Delay_time_edit  (callback)
   .text+0c20  STW.D1T1 A2,*+A4[5]     ; entry[5] (word)  = 0x00000024 = Fx_DLY_Delay_tapmuteMute (callback)
   ```
   `entry[7]`/`entry[8]` are left untouched (zero-cleared by the loader per
   recon/14 section 3, `c0129d80..9daa`). Every field that *is* set is
   either a byte flag, a `.const` table pointer, or a callback function
   address (consistent with recon/14's confirmed correction that entry[5..8]
   are callbacks, not size requests) — **none of them is a numeric size or a
   "give me the big buffer" flag**. Confidence: **confirmed** (full
   instruction-level trace of `Dll_Delay`, every store accounted for).

**What happens for an effect that does not declare it / can any effect use
it:** since D1 shows the framework writes `instance[3]` unconditionally for
every slot regardless of what Dll_<Name> does, and D3 shows there is no
flag anywhere an effect could opt in or out of, **any effect loaded into any
slot automatically has `instance[3]` pointing at that slot's live
0x81330-byte descriptor** — an effect that ignores it (e.g. a plain gain
effect) simply never reads/writes that SDRAM region, and nothing checks
whether it "declared" an intent to use it. Confidence: **confirmed** (follows
directly from the unconditional D1 loop + the absence of any gating field
found in D3).

## D4. Lifetime: zeroed on load? shared/other writers?

**Likely: zeroed once at power-on, NOT on every patch/slot change.** Traced
the call chain upward from the zeroing routine `c0164a98` and the
instance-wiring routine `c014fea0` (both in `build/fw/map/main.dis`):

- Both are called, back-to-back with ~15 other init calls, from a single
  straight-line function at `c016bee0..c016bf2c` (no loop, no branch between
  the calls — `c016bef4 CALLP c0165e98` [5-slot state/coeff memset, recon/14
  confirmed], `c016bef8 CALLP c014fea0` [instance wiring, D1], ...,
  `c016bf14 CALLP c0164a98` [0x81330 zeroing, recon/14 confirmed]). This
  function is called from exactly **one** site: `c015d4b4`.
- `c015d4b4` sits inside a larger function (entered at `c015d428`, called
  once from `c0134e14`) that looks like a boot-stage dispatcher: it tests a
  state value against 7 (`CMPEQ.L1 7,A4,A0` at `c015d4a0`) before running a
  short sequence that ends by calling the `c016bee0` init block unconditionally.
- `c0134e14` itself sits inside a polling loop (`c0134dc0`..`c0134e1c`) that
  compares a state variable to 42 and loops back on itself
  (`CMPEQ.L2 B0,B1,B0` / `[B0] BNOP.S1 0xc0134dc4,5` at `c0134de4`/`dec`)
  while that state persists, falling through to the one-time init path
  (`c0134df0`→...→`c015d428`) only when the state changes away from 42, then
  looping back to the top (`c0134e18 CALLP c0134db8`). This is consistent
  with a boot/state-machine dispatcher executing a particular state's
  handler once per transition, not per patch load.
- This matches recon/14's own treatment of the neighboring `c0165e98`
  five-slot memset (coefficients/state) as "static startup configuration",
  not re-verified per load.

Confidence: **likely**, not confirmed — I did not trace all the way back to
the reset vector, and I did not find (or look hard for) a second call site
reached specifically on "load new patch" or "change slot's effect". Given
the call sites found, the simplest reading is a single boot-time
initialization; **this is exactly the kind of claim the brief flags as
needing a pedal test** (see D5).

**Consequence if true:** loading a *different* effect into a slot does
**not** re-zero that slot's 0x81330 buffer. DELAY_3S's own `Fx_DLY_Delay_init`
(`.text+0x580`, traced in full) only initializes `instance[1]` (copies 0x80
default coefficients from `.const` `_Fx_DLY_Delay_Coe` at `.text+0x3ec`) and
part of `instance[2]` (two memsets, 16 and 52 bytes, i.e. ≤68 bytes of state)
— it never touches the big buffer or its write cursor's absolute content.
So a freshly-loaded delay effect inherits whatever was last written into
that slot's SDRAM region by the previous effect/patch; the first
buffer-length's worth of playback may include stale samples until the
write cursor has wrapped once. This is an audible-click-or-residual-noise
risk worth a pedal test, not a correctness bug.

**Not shared between slots:** the five bases (`c0226000, c02a7330,
c0328660, c03a9990, c042acc0`) are distinct, contiguous, non-overlapping
0x81330 regions (confirmed in D1/D2's cross-check), and each slot's
`instance[3]` only ever points at its own slot's descriptor — slot N's
effect cannot reach slot M's buffer through this mechanism.

**A separate, larger buffer exists and is NOT part of this mechanism —
likely the looper, ownership not confirmed.** The descriptor table at
`c0183470` has a 6th 12-byte entry right after the five slot entries, at
`c01834ac`: base `c04abff0`, size `0x2b1100` (~2.8 MB; recon/14 flagged this
but left ownership open). The 5-iteration loop in `c014fea0` (D1) never
reaches this 6th entry (`ILC`=4, i.e. exactly 5 iterations). I found
different code reading it:
```
c0139ae0  MVK.S1   0x34ac,A4
c0139ae4  MVKH.S1  0xc0180000,A4
c0139ae8  LDW.D1T1 *+A4[0],A0     ; A0 = descriptor[0] = base = c04abff0
```
followed by storing derived addresses into an unrelated `0xc0110000+`
region. This is clearly a different subsystem from the per-slot effect
instance wiring. Given its size (far larger than any single 3 s delay line,
and matching nothing in the 5-slot effect machinery), **the looper is a
reasonable guess** for its owner, but I did not identify the enclosing
function by name or confirm this on the pedal. Confidence: **guess** for
"who owns it"; **confirmed** that it is a disjoint buffer not reachable via
any effect's `instance[3]`.

## D5. Recipe for a CF effect

Our own effects (`effects/ratx/ratx.c`, `effects/common/hiwatt_kernel.h`,
`effects/common/mp_timing.h`) already declare their audio-process function
exactly as `void SH_AUDIO_FN(void **instance, void **ctx)`, with
`instance[1]`/`instance[2]` used as coefficient/state pointers — i.e. our
build already uses the same word-array convention the framework and
DELAY_3S use for `A4`. This means **no new framework plumbing is needed**;
the per-slot descriptor is already sitting in the instance array the
framework hands us. Minimal steps for a CF Delay:

1. In the process function, read `instance[3]` (no cast needed beyond
   `uint32_t *desc = (uint32_t *)instance[3];` or an equivalent struct
   pointer) — this is already non-NULL and valid for every slot, for every
   effect, with no registration step (D1/D3). **Confirmed.**
2. Treat `desc[0]`/`desc[1]`/`desc[2]` as `base`/`end`/`size` (byte
   addresses/byte count), matching stock DELAY_3S/ANDLY_3S (D2, cross-checked
   on two stock effects). **Confirmed.**
3. Keep a running write-cursor as a *negative byte offset* from `base`
   (stock pattern: decrement by 4 per sample, add `size` when it goes
   negative) rather than an absolute pointer; this is what stock state
   (`instance[2]`) is used for. Compute the absolute write address as
   `base + cursor` and store. **Confirmed pattern**, though the exact cursor
   representation (why negative-growing rather than positive) is not
   necessary to replicate — any wraparound scheme keeping the address within
   `[base, end)` and using `size` as the wrap modulus will work, since that
   is the invariant the stock code maintains.
4. For any read tap, compute `write_addr + tap_offset*4`, then wrap by
   subtracting `size` if the result is `>= end` (stock pattern, D2).
5. Budget: **0x81330 bytes = 532,272 bytes = 133,068 samples (32-bit
   words)** is the hard per-slot ceiling (recon/14, confirmed from the fixed
   zeroing loop and the contiguous-base cross-check in D1). At 44.1 kHz
   that is exactly 3.0177 s mono — i.e. "DELAY_3S" is sized to almost
   exactly fill the buffer (44100*3*4 = 529200; the buffer is slightly larger,
   532272, leaving ~3072 bytes/768 samples of headroom, enough for e.g. a
   couple of extra tap/interpolation guard samples but not for a second
   independent full-length line). A longer "modulation line" effect must
   fit within this same 0x81330 ceiling; it is a fixed, non-negotiable
   size (no bigger buffer is reachable this way — D4's 0x2b1100 buffer is a
   different, disjoint allocation with no demonstrated path for an effect
   to reach it).
6. **Do not assume the buffer is zero/clean at effect init.** D4's "likely"
   boot-only-zeroing finding means a freshly-loaded slot may contain stale
   SDRAM content from whatever was there before (previous effect, previous
   patch, or power-on zero if nothing has run there yet). Stock DELAY_3S's
   own `Fx_DLY_Delay_init` does not zero the big buffer either, so this is
   evidently an accepted stock behavior (presumably inaudible after it wraps
   once), but a careful implementation could optionally self-zero its
   working region on init (at the cost of extra init-time cycles) if an
   audible first-pass artifact matters for the use case.
7. Nothing needs to be added to the ZD2 header/INFO block or to the
   `Dll_<Name>` entry-table constructor to "request" the buffer (D3) — only
   the normal entry[0]/[1]/[entry-callback] fields our `tools/build_g1.sh`
   pipeline already emits are needed; the loader does not gate the
   buffer behind any such field.

**What stays unproved / what a pedal test would prove:**
- **D4 boot-vs-per-load timing** is the single biggest open item: load CF
  MEMPRB (or a custom probe) into a slot, write a known byte pattern across
  that slot's 0x81330 region from one patch, switch to a different patch (or
  load a different effect into the same slot) without power-cycling, then
  read the region back. If the pattern survives, the "zeroed once at boot
  only" claim is confirmed; if it is cleared, there is a per-load zero this
  static trace missed.
- **Descriptor field order** (`base, end, size` vs. some other order) is
  inferred from how DELAY_3S's code uses the three words, not from an
  explicit struct definition; a probe that dumps `instance[3]` and its
  pointee on the pedal (CF MEMPRB-style) alongside the known stock bases
  would nail this down numerically.
- **The 0x2b1100/looper buffer's real owner** (D4) is a guess; a pedal test
  that engages the looper and checks whether `c04abff0..c075d0f0` is being
  written would confirm or refute it.
- **Whether `instance[3]` round-trips correctly for a CF-built effect**
  (i.e., whether our `tools/build_g1.sh` output, loaded via the normal ZD2
  path, really does arrive with a valid, slot-correct `instance[3]`) is the
  most directly actionable pedal test: build a minimal effect that writes a
  known pattern through `instance[3]` in `init` and reads it back in
  `process`, confirming both the pointer's validity and that it differs
  correctly slot-to-slot.
