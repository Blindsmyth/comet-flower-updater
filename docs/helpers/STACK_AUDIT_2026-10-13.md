# Worker task stack audit — 2026-10-13

Offline instruction audit of `build/fw/map/main.dis` and the generation candidate
ELF. The stack gate remains open. No device operation or updater execution.

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
