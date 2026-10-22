# S2 - Loader allocation for multi-slot effects

## Status
running

## Findings

### F1. Per-slot code/const heap lookup takes a single slot index, not a count (confirmed)
Building on recon/14 section 1 (tables `c01839a8`=base, `c01839c0`=size, 5 entries of
`c01f4000+n*0xa000`/`0xa000`). I traced the caller recon/14 names (`c0129724`): it is
inside a larger "install effect into slot" routine spanning `c0129680..c0129cd0+`
(two call sites found: `c013f8f4`, `c013fc90`). The relevant excerpt:
```
c012972a  MV.L1  A6,A11        ; A11 = slot index (from the free-slot search above)
c0129734  CALLP  0xc0164a8c,B3 ; base table lookup, arg A11
c0129740  CALLP  0xc0164a80,B3 ; size table lookup, arg A11
c0129758  CALLP  0xc01560f0,B3 ; ELF loader entry, dest base/size just computed
```
`A11` is a single scalar slot index; there is no loop here that calls the
base/size lookup more than once per effect, and no multiplication of the
returned `0xa000` by any count. Confidence: confirmed (own trace + recon/14).

### F2. The function's "count" parameter is a list shift direction, not a slot-count (confirmed, rules out an alternate theory)
The two callers of `c0129680` pass `B4 = -1` (`c013f8fa`) or `B4 = 1`
(`c013fc96`). Inside the function this value is added to a cursor
(`c012968e ADD.L1 A1,A4,A4`) that walks a byte table at `0xc0064528` and a
word table at `0xc0064f6c` (`c01296a0..c01296fc`, an `SPLOOPW` compare
loop) — a list insert/remove shift by one position, not a resource count.
I checked this because it was the only numeric "N" reaching the function
that install a new effect; it is unrelated to ZD2 header 0x58. Confidence:
confirmed (instruction trace).

### F3. State/coefficient/instance tables: fixed 5-entry, independent of header (confirmed, cites recon/14)
recon/14 section 4 already proves (clearing loop `c0165e98`, sizes `0x348`
and `0x2a0` fixed by `c0165ea0/a4`) that state and coefficient storage are
five fixed slots, addressed only by slot index:
coef `11f00000+n*0x348`, state `11f013b0+n*0x2a0`, instance
`11f03ad0+n*20`. I re-derived the arithmetic myself (each row's delta is
exactly `0x348`/`0x2a0`/`20`) — no header-driven widening is possible
without changing this cinit-initialized table itself. Confidence: confirmed.

### F4. Work-buffer descriptor table: fixed 5 entries of 0x81330 B, and the whole SDRAM region is one contiguous block (confirmed arithmetic, new)
recon/14 section 2 lists the work-buffer descriptor table
(`c0183470+12*slot`, bases `c0226000,c02a7330,c0328660,c03a9990,c042acc0`,
each `0x81330` B) and separately flags an "ownership not established"
region at `c01834ac` covering `c04abff0..c075d0f0` (size `0x2b1100`).
Arithmetic I ran: the five code heaps end exactly where the five work
buffers begin (`c01f4000 + 5*0xa000 = c0226000`, the first work-buffer
base), and the five work buffers end exactly where that "unestablished"
region starts (`c0226000 + 5*0x81330 = c04abff0`). So slots 0-4's code
heaps, then slots 0-4's work buffers, are ONE physically contiguous SDRAM
range with no gaps between slots. This matters for the patch question
below: widening slot n's code heap into slot n+1's (or n's work buffer
into n+1's) is not blocked by a memory-map hole, only by the fixed-table
initialization and the slot-availability bookkeeping. Confidence:
confirmed (arithmetic on recon/14's own confirmed numbers).

## Not checked / open leads
