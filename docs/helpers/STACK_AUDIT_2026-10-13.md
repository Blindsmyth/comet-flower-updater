# Worker task stack audit — 2026-10-13

Offline instruction audit of `build/fw/map/main.dis` and the generation candidate
ELF. The stack gate remains open. No device operation or updater execution.

## Lifecycle-candidate continuation

Current identity and reproduction are in
[the lifecycle build record](../CONTROLLER_LIFECYCLE_CANDIDATE_2026-10-13.md).
Its reset and new worker-creation hooks are tail branches with **zero actual
SP adjustment**, preserving incoming A4 and B3. The old reset wrapper's 24-byte
frame and added event-post path no longer apply. Controller-mode MainApp/AD
publication now has no event post; only the worker self-post remains. The worker
frame is still 72 bytes and its timeout is now 10 Clock ticks.

### Interrupt-stack reservation confirmed

`c0163e80` loads `c0181fb8`. Instructions `c0163e94..3eb4` construct
`(0x11813468 + 0x3000) & ~7 = 0x11816468` and store that top pointer in word 6.
Word 5 is initialized to -1 for startup; the switch helper's zero/nonzero saved-SP
protocol described below governs later execution. The reserved region is
documented independently by the AIS/cinit inventory in `recon/16_audio_hw.md`
section C7: `118134a8..118164a8` (12 KiB). Do not reclaim that memory or infer
that its whole reservation is available from the slightly lower configured top.
Capacity is now traced; maximum nested usage is still unmeasured/unbounded.

### Kernel paths that invalidate a catalog-only bound

- Finite wait `c0144580` constructs a clock object on its own stack using
  `c016a240` (56-byte frame), `c015a520` (48-byte frame) and
  `c016ba40` (40-byte frame for parameter copy/merge). Added to the known
  320-byte subtotal, this is a visible **464-byte** chain before copy-helper
  callees or preemption. It is another partial chain, not a maximum.
- `c015a020..a294` is the clock initialization entry reached by `c016a240`;
  it has a 40-byte frame. The catalog does not identify this hidden entry.
- `c015de40..e054` is the task scheduler entry reached from `c016b7c0`;
  it has a 48-byte frame, calls switch hooks and reaches the 48-byte context
  switch at `c016aec0`. It also has an idle callback at `c01817ac` (current
  image target `c016cc00`). Separate entry `c015e060` follows it.
- `c0162be0..2d5a` places a task on its ready queue, has a 32-byte frame and
  invokes registered ready hooks. It is not simply an assertion logger.
  Separate diagnostic-related entry `c0162d60` follows it.
- The current candidate's actual AIS data (not just the stock listing) has two
  task hook records at `c0180630`, selected by count/pointer at `c0181860`:
  `{0,0,0,c0160660,0,0}` and
  `{c016e960,c0163460,0,c01690c0,0,c015cf20}`. Ready-hook fields [2] are zero;
  switch-hook fields [3] are nonzero. `c0160660` checks stack sentinels and may
  enter the error dispatcher `c015a7a0`; `c01690c0` performs timing accounting.
  Their normal and failure paths must be distinguished, not omitted wholesale.
- AIS reads also confirm the worker descriptor (`entry=c0149d40`, priority 25,
  size 0x800) and enabled stack fill. Generic diagnostic masks at `c018007c`
  and `c018012c` are 0x90/0x390, but their meaning is bit-specific; nonzero
  values do not prove every diagnostic branch is enabled or disabled.

Remaining stack work is now concentrated on these finite-wait/scheduler/hook
paths, indirect diagnostics, vector entry and the existing USB drain subtree.
No arithmetic using the partial subtotals establishes a safe margin.

## Allocation path

The worker requests a **2048-byte stack**. This is now traced beyond the nearby
descriptor word; it is not a measurement of runtime spare space.

| Evidence | Meaning |
|---|---|
| `c0149fa4..fac` | Pass `c0180510` to `c014a400` |
| `c0180518/51c/520` | Entry `c0149d40`, priority 25, stack request `0x800` |
| `c014a432..436` | Copy descriptor word 4 to caller `SP+72` |
| `c014a46a..478` | Pass params at `SP+40` in B6 to `c0165920` |
| `c0165938/5964` | Forward incoming B6 params through A3 to A8 for `c015a520` normalization |
| `c015a644..660`, `c016ba40` | Copy/merge params into the caller's temporary record |
| `c0165980..599c` | Call `c0152600` with normalized params in A6 (`SP+4`) and error record in B6 |
| `c015260c/260e` | Save params in B10, error record in A10 |
| `c0152860..2870` | Load normalized params word 8 (the stack-size field) into B11; zero selects a default |
| `c0152878..28d0` | Use supplied stack pointer or allocate aligned stack; store size/base in task words 7/8 |
| `c015298c` | Initialize task context through `c015f800` |

`c016db40` is **not** a task allocator or frame initializer. Its entire body
checks a global state and an input object's word 3. Following that target alone
would not establish stack capacity. Catalog names are hypotheses, so instruction
flow takes precedence.

## Stack fill and initial context

`c015f820` calls `c016b140` with the task object. That helper:

- Reads the fill-enable halfword at `c0181ac4`, whose image value is 1.
- Reads task word 7 as byte count and word 8 as stack base.
- Writes byte `0xBE` across the stack at `c016b170..17a` when enabled.
- Calls `c016d5c0` with `base + size - 8`, constructing the initial task frame;
  `c016e0e0` is the bootstrap return target.

This establishes an image-configured stack-fill mechanism and a future route
to a high-water measurement. It does not read a live sentinel, prove that the
configuration stays enabled, or show a runtime watermark. Initial-frame bytes
are consumed/restored by bootstrap and must not simply be subtracted again
from every steady-state call depth.

`c016aec0` is a task context switch: it decrements the outgoing SP by **48 bytes**,
stores it through A4, loads the incoming SP through B4, and restores the incoming
register frame. Include it on paths that actually reach a switch; do not add
it indiscriminately to every call or double-count the bootstrap layout.

## Corrected known wait depth

| Live frame | Bytes |
|---|---:|
| Stock worker `c0149d40` (`STW B3,*B15--[2]`) | 8 |
| Candidate `controller_worker_wait` | 72 |
| Stock event wait save helper | 56 |
| Lower wait `c0144580` | 184 |
| **Known subtotal from task entry** | **320** |

The earlier partial note incorrectly called the stock worker frame 72 bytes.
The wrapper itself is 72; the stock caller is 8. The prior 312-byte subtotal
was measured from wrapper entry, so the corrected task-entry subtotal is 320.
It excludes deeper calls and preemption. The reset hook's 24-byte frame belongs
to its caller's context and is not automatically part of the worker wait chain.

## Interrupt stack switch found; task-stack cost remains

The full interrupt-entry path at `c015ec80` saves registers and special registers
before dispatching through `c01557c0`:

1. `c015ec80` decrements SP by 8; `c015ec88` aligns it down to 8 bytes;
   `c015ec8c` subtracts another 264. This uses **272 bytes plus alignment** on
   the interrupted stack before the C dispatcher.
2. `c01557c0..57cc` adds **80 bytes** of C dispatcher saves/locals.
3. `c0155800` calls `c016d600`. It loads words 5/6 at `c0181fb8`; when word 5
   is zero it saves the interrupted SP at `c0181fcc` and switches B15 to the
   word-6 stack pointer. Nested calls with nonzero saved-SP state retain B15.
4. `c016e100` restores the saved SP when passed zero and clears that saved slot.

Thus a separate interrupt stack does **not** justify charging zero interrupt
bytes to a task. This path has 352 bytes plus alignment before the switch.
Combined with the known wait subtotal, the visible components are 672 bytes
plus alignment; **this is not a maximum or a safe-margin calculation**. Deeper
kernel calls can be interrupted, and vector entry, switch placement and later
scheduler work still need their own bounds.

## Remaining proof

- Bound all worker wait, semaphore acquire/release, event-post and drain call
  paths, including indirect calls and diagnostic paths.
- Trace vector registration (entry address reference at `c0168d70`) and every
  interrupt capable of preempting the worker; include pre-switch saves,
  nesting, exception paths and scheduler work after SP restoration.
- Bound the reset caller's stack separately, including its added event post.
- Establish interrupt-stack allocation/nesting capacity as a separate gate.
- Once a reviewed diagnostic path exists, measure the `0xBE` watermark under
  load. Do not approve an image from an unmeasured nominal subtraction.
