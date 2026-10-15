# Report: MIDI Port Callback (0xc011ac80) and Op 8 Producers

Investigation into who invokes the MIDI port callback registered at `0xc011ac80` (`c0144c0c`) and with which event numbers, specifically whether op 8 (ring reset, `c0144d0c`) is invoked.

## 1. All loads of 0xc011ac80

The static scanner script `build/gemini_op8/scan_ac80_loads.py` tracked constant register generation across the entire disassembly `build/fw/map/main.dis` (153,793 instructions).

There are exactly **two loads**, **two stores**, and **four base-pointer passing formations** involving `0xc011ac80` across the entire firmware binary.

### 1.1 Loads of `0xc011ac80`

1. **`c0151f18` (LOAD)** in function **`c0151ed0`** (`usb_if_request_callback_veneer`)
   - Direct constant formation at `c0151f10..c0151f14` loads pointer into `A0`.
   - Disassembly excerpt:
     ```text
     c0151f10   02564028           MVK.S1        0xffffac80,A4
     c0151f14   026008e8           MVKH.S1       0xc0110000,A4
     c0151f18       000c           LDW.D1T1      *A4[0],A0
     ```
   - **Confidence**: confirmed.

2. **`c01520cc` (LOAD)** in function **`c0151ff4`** (`usb_if_record_field_1384`)
   - Base `0xc011ac84` formed at `c0152008..c015200c` in `B4` and held in callee-saved `A11`.
   - Offset `-4` applied at `c01520ca` (`ADD.L2 B0,-4,B4`) forming `0xc011ac80` in `B4`.
   - Loaded into `B0` at `c01520cc`.
   - Disassembly excerpt:
     ```text
     c01520c8       1587           MV.L2X        A11,B0
     c01520ca       8c41           ADD.L2        B0,-4,B4
     c01520cc       100d           LDW.D2T2      *B4[0],B0
     ```
   - **Confidence**: confirmed.

### 1.2 Stores to `0xc011ac80`

1. **`c0152326` (STORE)** in function **`c0152318`** (`usbmidi_close_state`)
   - Direct constant formation at `c0152318..c0152320` into `A4`.
   - Clears `*0xc011ac80` by storing `0` (`A0 = 0`).
   - Disassembly excerpt:
     ```text
     c0152318   02564028           MVK.S1        0xffffac80,A4
     c0152320   026008e9           MVKH.S1       0xc0110000,A4
     c0152324       0426 ||        MVK.L1        0,A0
     c0152326       0004           STW.D1T1      A0,*A4[0]
     ```
   - **Confidence**: confirmed.

2. **`c0152436` (STORE)** in function **`c0152410`** (`usbmidi_open`)
   - Direct constant formation at `c0152420..c0152424` into `A10`.
   - Clears the 40-byte state via `rts_memset(0xc011ac80, 0, 40)` at `c0152428`, then stores the incoming callback argument `A11` (`A0`) into `*0xc011ac80`.
   - Disassembly excerpt:
     ```text
     c0152420   05564028           MVK.S1        0xffffac80,A10
     c0152424   056008e8           MVKH.S1       0xc0110000,A10
     c0152432       c506           MV.L1         A10,A6
     c0152434       0586           MV.L1         A11,A0
     c0152436       0104           STW.D1T1      A0,*A6[0]
     ```
   - **Confidence**: confirmed.

### 1.3 Other Formations (Struct Base Pointer Passing)

Four functions compute `A6 = 0xc011ac80` by subtracting 4 from `0xc011ac84` to pass the driver struct base `A6` to `c01520f4` (`indexed_oneshot_action_dispatch`):
- `c0152288`: `ADD.L1 A0,-4,A6` in `c0152240` (`usbmidi_api3`)
- `c01522f2`: `ADD.L1 A4,-4,A6` in `c01522d8` (`usbmidi_api5_on_txreset`)
- `c0152374`: `ADD.L1 A0,-4,A6` in `c015232c` (`usbmidi_api4_c`)
- `c01523f0`: `ADD.L1 A4,-4,A6` in `c01523d0` (`usbmidi_api4_on_rxenable`)

Neither `c01520f4` nor any of its action targets reads or writes word 0 (`*A6[0]` / `0xc011ac80`); they access only fields at offsets 8, 12, 24, 28, 32, 36.
- **Confidence**: confirmed.

## 2. Every call through the loaded pointer

*Pending analysis.*

## 3. Op 8

*Pending analysis.*

## 4. Context

*Pending analysis.*
