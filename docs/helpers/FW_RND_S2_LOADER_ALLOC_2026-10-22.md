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

### F5. Hardware ground truth (CFM2P probe, header 0x58=2) matches slot-0 only, on every field (confirmed, from handoff)
From `HANDOFF_2026-10-22_FW_RND.md` / `docs/CF_MASTER_PROBE_2026-10-19.md`: the
CFM2P probe (declared header slot count 2) measured instance `0x11f03ad0`,
coef `0x11f00000`, state `0x11f013b0`, code `0xc01f41e0`, one work buffer
`0xc0226000` (529,200 B), with work buffers 1-4 reported empty. Every one
of those addresses is exactly slot 0's entry in the tables from F1/F3/F4
above — not slot 0 *and* slot 1. This is the strongest evidence in the
whole question: a measured 2-slot-header effect was given exactly one
slot's worth of resources at runtime. Confidence: confirmed (owner
hardware measurement, cross-checked against the static tables here).

### F6. ELF segment allocator failure is a refusal (abort + logged error code), not an overrun (confirmed, new)
Traced the PT_LOAD allocation call recon/14 names at `c0124368`
(`CALLP 0xc015f72c,B3`, inside the function containing `c01242bc`'s 48-byte
record build). The return value is checked immediately:
```
c012436c  ADD.L1 A0,A4,A4        ; combine allocator result
c012436e  MV.L1  A4,A0
c0124370  [A0] BNOP 0xc012438e,5 ; success: continue (zero segment, read file bytes)
c0124372  MV.L1X B10,A4          ; failure (falls through): reload module ptr
c012437a  STW A0,*A4[1]          ; A0=0, mark field failed
c0124380  CALLP 0xc016be80,B3    ; err_set_last_code
c0124384  MVK.L1 7,A4            ; error code 7
c0124388  BNOP 0xc0124578,4      ; abort: jump to function epilogue, skip load
```
`c016be80` is confirmed elsewhere as `err_set_last_code` (recon/map/00_library_kernel.md:191,
"48 CALLP callers including the heap allocator's out-of-block path").
On failure this code never reaches the segment-zeroing (`c015f780`) or
file-read (`c015f7a4`) steps recon/14 describes for the success path — it
branches past them to the epilogue. Confidence: confirmed.

### F7. The allocator's own out-of-space path uses the same error code 7 (confirmed, new)
Inside the custom allocator (`c0151190`, recon/14 section 2), the free-list
search (`c01511f8..c0151244`) that fails to find a fitting block lands at
`c0151274` with cursor `A11==0`:
```
c0151274  [!B0] BNOP 0xc01512b0,5   ; B0 = (A11!=0); free list exhausted -> here
c01512b0  CALLP 0xc016be80,B3       ; err_set_last_code
c01512b4  MVK.L1 7,A4               ; error code 7 (same code as F6)
```
This confirms the bound is enforced at the allocator level (not just by
the caller): requesting more than the remaining space in the 0xa000 region
returns a failure/null, which the caller in F6 then turns into an abort.
No path was found where the allocator silently returns a pointer past the
region's end. Confidence: confirmed.

### F8. No read of ZD2 header byte 0x58 (or any count-scaled size) found in the loader/module-creation code (not found, honest)
Searched the ELF/module loader address range the brief and recon/13/14 map
out (`c0122924..c0124fc0`, `c01453b4..c0146e18`, plus the allocator chain
`c015f72c/c0163af4/c0163ac0/c0151190` and the install routine `c0129680..
c0129cd0` read in F1/F2) for: a byte load at struct-offset `0x58`, or any
size value multiplied by a count before being passed to the allocator.
Found neither. Every size value feeding this path traces to either an ELF
PT_LOAD `memsz` (file-side, ELF header, not the ZD2 container header) or
the fixed per-slot tables in F1/F3/F4 (compile-time constants, not derived
from any parsed field). This means: *in the code paths this job covers*,
the ZD2 "slot count" byte at file offset 0x58 is not consulted to size or
multiply any allocation. If it is read anywhere in the firmware (e.g. for
the effect list / UI, which S1 owns), that is a separate code path this
job did not find and does not claim to rule out elsewhere in the binary.
Confidence: not found (searched the specific ranges listed; did not do an
exhaustive whole-binary search for every possible LDB/LDBU with imm=0x58,
which would match too much unrelated code to be useful).

### F9. Slot-in-use bookkeeping is a plain per-index byte flag, not a run of N flags (likely)
While reading the install routine (F1/F2) I found a flag write at
`c0129790`: `STW.D1T2 B0,*+A5[A4]` with `B0=1`, `A5=0xc01839f0`, `A4`=the
slot index — a single-slot "in use" flag, matching the hardware
observation (handoff: a header=2 effect left the *next* patch slot free
for another effect, i.e. the firmware's bookkeeping only marked the one
slot it was told to use). I did not trace every reader of this `0xc01839f0`
table (that would mean re-deriving the free-slot search algorithm in full,
out of scope for the time budget), so I call this "likely" rather than
confirmed: it is consistent with, but not an exhaustive proof of, "only
one flag is ever set per effect regardless of header 0x58."

## Answers

### Question 2 — how slot count maps to memory
**Answer (confirmed):** a header-N effect does NOT get N times the
resources. Code/const heap (`0xa000`=40 KiB), coefficient buffer (`0x348`),
state buffer (`0x2a0`), and one SDRAM work buffer (`0x81330`=529,200 B) are
all fixed, compile-time, 5-entry tables indexed purely by which of the 5
physical loader slots the effect is assigned to — never by the ZD2
header's slot-count byte (0x58). The loader only ever touches the single
slot's table row (F1, F3, F4); no code path was found that reads header
0x58 or loops the allocation by a count (F8); and the owner's own hardware
probe of a header=2 effect (F5) measured exactly one slot's addresses, not
two, with the "next" work buffer still empty. A multi-slot effect declares
a bigger number in its header, but the firmware currently just... doesn't
act on it for memory purposes. (Whatever *does* act on it — the effect
list/slot-fit check that hides header=5 but shows header=2 — is a separate
code path; see S1's report, not found by this job.)

**40 KiB bound, refusal vs overrun (confirmed):** enforced twice —
once inside the generic allocator (F7, error code 7 on free-list
exhaustion) and once by the ELF segment-loading caller that checks the
allocator's return value and aborts the module load on failure (F6, same
error code 7, jumps past the zero-fill/file-read steps to the function
epilogue). This is a clean refusal: an oversize effect's load attempt
fails and is logged, it does not overrun into the next slot's physically
adjacent heap region.

**Can a firmware patch give a multi-slot effect N x 40 KiB? (likely,
with real risk):** physically plausible, logically nontrivial.
- *Why plausible:* F4 shows the 5 code heaps (`c01f4000..c0226000`) and
  the 5 work buffers (`c0226000..c04abff0`) are each one contiguous SDRAM
  range with no gaps between adjacent slots' regions. Nothing in the
  physical memory map blocks giving slot n a `size = N*0xa000` heap
  instead of `0xa000` (same for the work buffer, `N*0x81330`).
- *What has to change:* (1) the compile-time size table `c01839c0` (and/or
  the heap-init call site `c0129740`/`c0164a80`) would need to compute
  `N*0xa000` for the chosen slot instead of reading the fixed table, with
  N coming from the ZD2 header — i.e. new logic, not a toggle, since today
  nothing reads that header field here (F8); (2) the slot-availability
  bookkeeping (F9, the `0xc01839f0` flag table and whatever free-slot
  search reads it — not fully traced by this job) must mark the next N-1
  slots "in use" too, or a second effect placed there will silently
  collide with the first effect's now-widened heap — this is the real
  risk, a silent SDRAM corruption bug if done half-way; (3) state/coef/
  instance tables (F3) and work-buffer descriptors (F4) are separate
  fixed tables and would need the same N-slot treatment independently —
  missing one of them (e.g. widening code but not state) would leave the
  effect's extra code slots unable to get their own instance/state,
  defeating the point. **Patch site:** the size-table read at
  `c0164a80`/`c01839c0` (code heap), the equivalent calls for
  state/coef (`c014fea0`/`c0165e98` initializers, per recon/14 section 4),
  work-buffer descriptor table (`c0183470`/`c014febc` per recon/14 section
  2), and the free-slot search this job did not fully trace (see F9).
  **Risk:** high if partial — the three tables (code, state/coef,
  work-buffer) and the slot-availability flags must all move in lockstep,
  and any one left single-slot-sized breaks the "proof" that N-slot
  resources were actually granted. Recommend prototyping with a debug
  probe effect (a header=2 build) and the pedal's existing MEMPRB-style
  readback before trusting this for CFMPRE/CF Master, per S2's own
  constraints (no pedal access from this job).

## Not checked / open leads
