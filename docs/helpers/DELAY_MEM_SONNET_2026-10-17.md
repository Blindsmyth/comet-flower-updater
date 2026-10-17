# DELAY_MEM_SONNET: per-slot large work buffer for CF Delay (2026-10-17)

Written by Claude Sonnet 5, answering docs/helpers/DELAY_MEM_BRIEF_2026-10-17.md.
Offline static analysis only (main.dis disassembly + ZD2/ELF parsing with
existing tools/src helpers + dis6x). Nothing on the pedal was touched.

## Summary
(filled in last)

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

## D4. Lifetime: zeroed on load? shared/other writers?

## D5. Recipe for a CF effect
