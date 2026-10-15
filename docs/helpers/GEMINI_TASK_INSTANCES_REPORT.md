# Task Instances Report: USB Event Loop `0xc0138310`

> **Claude review (2026-10-15): verified.**
> - **Guard.** The `LDW *+B14[94],B0` at `c0138778` is in the delay slots of `c0138776 [A0] BNOP`, so it
>   executes on both paths. On the mailbox-created path, `c0138798 [!B0] BNOP 0xc01387a8` reaches the
>   create (`c01387ac`, descriptor `0xc01800bc`) only when the handle is 0.
> - **Descriptor.** The words at `c01800c4/c8/cc` match (entry `c0138310`, priority 30, stack 0x800).
> - **Callers.** `c0138720` has exactly one direct caller.
> - **Result.** At most one `UsbTask` instance exists. This closes the last assumption of
>   `USB_Q25_ASSOCIATION_2026-10-15.md` §2.

Static analysis report on task instances and lifecycle of the USB event loop `0xc0138310` in `build/fw/map/main.dis`.

## 1. Every reference to `0xc0138310`

- **Confidence**: confirmed
- **Scan methodology**: An automated Python scan (`build/gemini_tasks/find_refs.py`, `build/gemini_tasks/deep_scan.py`) searched all 153,793 lines of `build/fw/map/main.dis` for:
  1. Any `MVK` / `MVK.Sx` loading `0x8310`, `0xffff8310`, `-31984`, or `33552`, paired with `MVKH` `0xc0130000` within 16 instructions. (Result: **0** occurrences).
  2. Any direct call or branch (`CALLP`, `B`, `BNOP`) targeting `0xc0138310`. (Result: **0** occurrences).
  3. Any `.word` literal or text match for `c0138310`. (Result: **2** occurrences: the function definition itself and one data word).
- **Hits identified**:
  1. **Address `0xc0138310`** (own function entry in `TEXT`):
     ```
     c0138310   106ba410           CALLP.S1      0xc016e020,A3
     c0138314   07be09c2           SUB.D2        B15,0x10,B15
     c0138318   1023e293           CALLP.S2      0xc014a214,B3
     ```
  2. **Address `0xc01800c4`** (in `DATA` section `sc016f780`, offset `+0x08` of static descriptor `0xc01800bc`):
     ```
     c01800bc   00000000           .word 0x00000000
     c01800c0   00000000           .word 0x00000000
     c01800c4   c0138310           .word 0xc0138310
     c01800c8   0000001e           .word 0x0000001e
     c01800cc   00000800           .word 0x00000800
     c01800d0   00000000           .word 0x00000000
     c01800d4   c01817d0           .word 0xc01817d0
     ```
  - **Enclosing scope**: DATA section `sc016f780`. There is no enclosing C function; `0xc01800c4` is a statically initialized `.word` in read-only global data, specifically field `+0x08` (entry function pointer) of the `UsbTask` descriptor table entry `0xc01800bc`.

## 2. Task creation

- **Confidence**: confirmed
- **Descriptor table**: `0xc0138310` is stored at offset `+0x08` of static descriptor `0xc01800bc` in DATA section `sc016f780`.
  - Descriptor fields at `0xc01800bc`:
    - `+0x08` (`0xc01800c4`): `0xc0138310` — Entry function pointer (`usb_worker_task`)
    - `+0x0c` (`0xc01800c8`): `0x0000001e` — Priority: **30** (`0x1e`)
    - `+0x10` (`0xc01800cc`): `0x00000800` — Stack size: **2048 bytes** (`0x800` = 2 KiB)
    - `+0x18` (`0xc01800d4`): `0xc01817d0` — Name pointer -> `"UsbTask"` (`c01817d0: .word 0x54627355, 0x006b7361`)
- **Creation routine (`c014a400`)**:
  - The descriptor `0xc01800bc` is passed in `A4` to `c014a400` at `c01387ac` in `usb_worker_start` (`c0138720`):
    ```
    c01387a8   02005e28           MVK.S1        0x00bc,A4
    c01387ac   10238c13           CALLP.S2      0xc014a400,B3
    c01387b0   02600c68 ||        MVKH.S1       0xc0180000,A4
    c01387b4       0246           MV.L1         A4,A0
    c01387b6       a5aa    [ A0]  BNOP.S1       0xc01387cc,5
    ...
    c01387cc   00005e7c           STW.D2T1      A0,*+B14[94]
    ```
  - Routine `c014a400` (`TASK_CREATE` in `controller.c`) initializes a 56-byte SYS/BIOS `Task_Params` structure via `c016e8a0` from default template `0xc01800f4`, unpacks the fields (`*A4[2]` -> fxn, `*A4[3]` -> priority, `*A4[4]` -> stackSize, `*A4[6]` -> name), and calls the SYS/BIOS task creator `c0165920` (`Task_create`).
  - The returned non-zero task handle is saved into `*+B14[94]`.

## 3. Instance count

- **Confidence**: confirmed
- **Count of distinct creation sites**: **1** distinct creation site (`c01387ac` in `c0138720` `usb_worker_start`).
  - *Note*: While `c014a400` is called from 3 locations in the firmware (`c01387ac`, `c0149fa8`, `c014be08`), only `c01387ac` passes descriptor `0xc01800bc` pointing to `0xc0138310`. The other two sites instantiate different tasks (`c0149d40` and `c014bb48`).
- **Reachability and re-execution**:
  - The single call chain reaching `c0138720` in the static disassembly is:
    `c01341e4` (`mainapp_frame_update` @ `c0134354`) -> `c016c120` (`preload_ready_flag_init` @ `c016c150`) -> `c016ab8c` (@ `c016ab98`) -> `c016ab70` (@ `c016ab80`) -> `c015af18` (API wrapper @ `c015af20`) -> `c0138720` (`usb_worker_start`).
  - Because `c015af18` is an exposed subsystem start veneer (paired with `c015af0c` shutdown and `c015af00` reset), the creating code is capable of being called more than once during firmware lifecycle (e.g. system re-init or restart).
- **Instance guards**:
  - **Confirmed YES**, guarded by two layers:
    1. *Prior instance teardown*: `usb_worker_start` (`c0138720`) unconditionally begins by invoking `usb_worker_shutdown` (`c013826c`), which pend-drains and deletes any active worker handle in `B14[94]` (`c014a260`, `c014a160`, `c014a2b0`) and clears `*+B14[94] = 0`:
       ```
       c0138720       31f7           STW.D2T2      B3,*B15--[2]
       c0138722       b4db           CALLP.S2      0xc013826c,B3
       ```
    2. *Handle non-zero guard*: `usb_worker_start` explicitly loads `B14[94]` into `B0` and tests if it is zero before calling `c014a400`:
       ```
       c0138778   00005e6e           LDW.D2T2      *+B14[94],B0
       ...
       c0138798   3014a120    [!B0]  BNOP.S1       0xc01387a8,5
       c013879c   e0808000           .fphead       n, l, W, BU, br, nosat, 0000100b
       c01387a0       b61b           CALLP.S2      0xc0138300,B3
       c01387a4   024566a8           MVK.S1        0xffff8acd,A4
       c01387a8   02005e28           MVK.S1        0x00bc,A4
       ```
       If `B14[94]` is already non-zero (teardown failed to release it), the code does *not* jump to `c01387a8`; it aborts through `c01387a0` and returns error `0xffff8acd`.
- **Conclusion**: Exactly **1** task instance exists at any time. The instance count is strictly **0 or 1**; multiple concurrent instances can never exist.

## 4. Mailbox

- **Confidence**: confirmed
- **Mailbox handle**: `c0138318` receives from **B14 slot 95** (`*+B14[95]`), which holds the handle created at `c013876c` (via `c014a4d4` Mailbox creator) and stored at `c0138790`.
  - Disassembly of the receive call (`c0138318`):
    ```
    c0138310   106ba410           CALLP.S1      0xc016e020,A3
    c0138314   07be09c2           SUB.D2        B15,0x10,B15
    c0138318   1023e293           CALLP.S2      0xc014a214,B3
    c013831c   e1a08000           .fphead       n, l, W, BU, br, nosat, 0001101b
    c0138320   02005f6d ||        LDW.D2T1      *+B14[95],A4
    c0138324   023c805a ||        ADD.L2        4,B15,B4
    ```
  - Routine `c014a214` is a direct wrapper around SYS/BIOS `Mailbox_pend`:
    ```
    c014a214       31f7           STW.D2T2      B3,*B15--[2]
    c014a216       ff26           MVK.L1        -1,A6
    c014a218   10389012 ||        CALLP.S2      0xc0166680,B3
    c014a220       0626           MVK.L1        0,A4
    c014a222       71f7           LDW.D2T2      *++B15[2],B3
    c014a226       a1ef           BNOP.S2       B3,5
    ```
    It calls `c0166680` (`Mailbox_pend`) with timeout `A6 = -1` (`BIOS_WAIT_FOREVER`), message buffer in `B4 = B15 + 4`, and mailbox handle in `A4 = B14[95]`.
- **Exclusivity (does any other task receive from this handle?)**:
  - **Confirmed NO**.
  - A complete scan of all instructions referencing `B14[95]` across `main.dis` reveals exactly 8 instructions:
    1. `c01382b8`: `LDW *+B14[95], B0` in `usb_worker_shutdown` (`c013826c`) — check handle prior to teardown.
    2. `c01382cc`: `STW B0, *+B14[95]` in `usb_worker_shutdown` — clear handle to 0 on teardown.
    3. `c0138320`: `LDW *+B14[95], A4` in `usb_worker_task` (`c0138310`) — pass handle to receive helper `c014a214`.
    4. `c0138740`: `LDW *+B14[95], B0` in `usb_worker_start` (`c0138720`) — error check.
    5. `c0138784`: `STW B0, *+B14[95]` in `usb_worker_start` — error clear.
    6. `c0138790`: `STW A0, *+B14[95]` in `usb_worker_start` — store newly created mailbox handle.
    7. `c0138918`: `LDW *+B14[95], A4` in `usb_command_dispatch` (`c01387f0`) — pass handle to `c014a174` (`Mailbox_post`).
    8. `c0138a08`: `LDW *+B14[95], A4` in `usb_command_dispatch` (`c01387f0`) — pass handle to `c014a174` (`Mailbox_post`).
  - Receiver helper `c014a214` has exactly **1 caller** in the entire firmware: `c0138318`.
  - Direct callers to SYS/BIOS `Mailbox_pend` (`c0166680`) were also verified: 5 total call sites exist (`c013abc8`, `c013b108`, `c014a218`, `c01534a4`, `c01534c8`); all other sites service different mailboxes (`B14[172]`, `B14[162]`, or passed arguments).
  - Therefore, `c0138310` (`usb_worker_task`) is the exclusive receiver for `B14[95]`. `B14[95]` is populated exclusively by `usb_command_dispatch` (`c01387f0`).
