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

*Pending analysis.*

## 3. Instance count

*Pending analysis.*

## 4. Mailbox

*Pending analysis.*
