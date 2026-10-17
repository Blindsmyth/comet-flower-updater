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

## D3. Does the effect file declare it needs the buffer?

## D4. Lifetime: zeroed on load? shared/other writers?

## D5. Recipe for a CF effect
