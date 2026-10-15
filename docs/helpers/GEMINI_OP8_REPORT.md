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

### 2.1 Argument Register Read by `c0144c0c`

The callback dispatcher routine at `c0144c0c` begins:
```text
c0144c0c   10528410           CALLP.S1      0xc016e020,A3
c0144c10       2246           MV.L1         A4,A1
c0144c12       834e ||        MV.S1         A6,A4
c0144c14   0007c058           SUB.L1        A1,0x2,A0
c0144c18   0000cbd8           CMPLTU.L1     0x6,A0,A0
c0144c20   c086a120    [ A0]  BNOP.S1       0xc0144d2c,5
c0144c2c       448a ||        SHL.S1        A1,0x2,A0
c0144c2e       0c00           ADD.L1        A0,-8,A0
```
- Instruction `c0144c10 MV.L1 A4, A1` moves **`A4`** into `A1`.
- `A1` is tested for range 2..8 (`SUB 2`, `CMPLTU 6`) and used as index into table `0xc01843d8` via `(A1 - 2) * 4`.
- **Conclusion**: The event-number argument passed by callers is in **`A4`**.
- **Confidence**: confirmed.

### 2.2 Indirect Calls Following Load 1 (`c0151ed0`)

In `c0151ed0`, the callback pointer loaded into `A0` at `c0151f18` is called indirectly at two distinct sites:

1. **Call Site 1 (`c0151f48`)**: passes `A4 = 7` (Event 7)
   ```text
   c0151f48   00001362           B.S2X         A0
   c0151f4c   01866162           ADDKPC.S2     0xc0151f58,B3,3
   c0151f50       e626           MVK.L1        7,A4
   c0151f52       0627 ||        MVK.L2        0,B4
   c0151f54   03000028 ||        MVK.S1        0x0000,A6
   ```
   - Reached when `wIndex == 3` (MIDI OUT Endpoint 3).
   - **Confidence**: confirmed.

2. **Call Site 2 (`c0151f30`)**: passes `A4 = 8` (Event 8)
   ```text
   c0151f30   00001362           B.S2X         A0
   c0151f34   01896162           ADDKPC.S2     0xc0151f44,B3,3
   c0151f38       0e26           MVK.L1        8,A4
   c0151f3a       0627 ||        MVK.L2        0,B4
   c0151f40   03000028 ||        MVK.S1        0x0000,A6
   ```
   - Reached when `wIndex == 132` (`0x84`, MIDI IN Endpoint 4).
   - **Confidence**: confirmed.

### 2.3 Indirect Calls Following Load 2 (`c0151ff4`)

In `c0151ff4`, the callback pointer loaded into `B0` at `c01520cc` is called indirectly at a single call site (`c01520d4`), with four incoming branches setting `A4`:

```text
c01520d4   00000362           B.S2          B0
c01520d8   018a6162           ADDKPC.S2     0xc01520e8,B3,3
c01520e0   0200a35b           MVK.L2        0,B4
c01520e4   033c9058 ||        ADD.L1X       4,B15,A6
```

The value of `A4` reaching `c01520d4` depends on the incoming record event (0..3):
- **Record event 0** branches to `c0152058`, setting `c0152094 MVK.L1 2, A4` -> passes **`A4 = 2`** (Event 2).
- **Record event 1** branches to `c0152034`, setting `c0152054 MVK.L1 4, A4` -> passes **`A4 = 4`** (Event 4).
- **Record event 2** branches to `c01520b4`, setting `c01520c0 MVK.L1 3, A4` -> passes **`A4 = 3`** (Event 3).
- **Record event 3** branches to `c01520a4`, setting `c01520ae MVK.L1 5, A4` -> passes **`A4 = 5`** (Event 5).
- **Confidence**: confirmed.

### 2.4 Complete Summary of Event Numbers 2..8 and Call Sites

| Event # | Call Site Address | Enclosing Function | Trigger Condition |
|:---:|:---:|:---|:---|
| **2** | `c01520d4` | `c0151ff4` | Record event 0 dispatched (via `c015e880` at `c015e8f4`) |
| **3** | `c01520d4` | `c0151ff4` | Record event 2 dispatched (via `c015e9d0` at `c015ea38`) |
| **4** | `c01520d4` | `c0151ff4` | Record event 1 dispatched (via `c015e924` at `c015e990`) |
| **5** | `c01520d4` | `c0151ff4` | Record event 3 dispatched (via `c0135660` at `c0135798`) |
| **6** | *None* | *None* | Unreferenced. Table entry 6 (`0xc01843e8`) points to `c0144d2c` (no-op return 0). |
| **7** | `c0151f48` | `c0151ed0` | USB standard request `CLEAR_FEATURE(ENDPOINT_HALT)` on EP 3 (OUT) |
| **8** | `c0151f30` | `c0151ed0` | USB standard request `CLEAR_FEATURE(ENDPOINT_HALT)` on EP 0x84 (IN) |

## 3. Op 8

*Pending analysis.*

## 4. Context

*Pending analysis.*
