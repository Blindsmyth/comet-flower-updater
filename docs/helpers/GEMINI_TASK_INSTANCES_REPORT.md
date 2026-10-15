# Task Instances Report: USB Event Loop `0xc0138310`

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

*Pending analysis.*

## 4. Mailbox

*Pending analysis.*
