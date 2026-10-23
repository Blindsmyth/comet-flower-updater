# F8: Incoming SysEx path and a free command

## Status
running

## Findings

### 1. USB MIDI OUT Endpoint Receive and Circular Ring Buffer (confirmed)
Host bytes sent to the pedal over USB MIDI OUT are received by the USB endpoint worker routine at `c0159620`, which drains the USB hardware FIFO via `c0144ee4` into a 4096-byte circular ring buffer in L2 SRAM at `0xc010f288`.
- **Ring buffer base**: `0xc010f288` (4096 bytes = 0x1000 bytes, modulus mask `0x0fff`).
- **Index pointers**: Write index is stored at global `*+B14[40]`. Read index is stored at global `*+B14[39]`.
- **Task signaling**: After committing the write pointer at `c015974c STW.D2T2 B1,*+B14[40]`, routine `c01596e8` signals the MIDI task by posting event bit 1 to event handle `*+B14[147]` via `c0155ac0(handle, 1)` (SYS/BIOS `Event_post`).
- **Disassembly evidence**:
  - `c0159668 MVK.S1 0xfffff288, A10; c015966c MVKH.S1 0xc0100000, A10` -> base `0xc010f288`.
  - `c015970c CALLP.S2 0xc0144ee4, B3` with `B4 = A0 + A10` (buffer target `0xc010f288 + write_index`).
  - `c015974c STW.D2T2 B1, *+B14[40]` (commits updated write index mod 4096).
  - `c01596e8 CALLP.S2 0xc0155ac0, B3; c01596ec LDW *+B14[147], A4; c01596f0 MVK 1, B4` (`Event_post(B14[147], 1)`).
- **Consumer**: MIDI task `c0129118` blocks on `c0129130 CALLP 0xc0144580, B3` (`Event_pend(B14[147], 1, 0, -1)`). On wakeup, it compares `B14[39]` against `B14[40]` (`c0129146 CMPEQ A4, B0, A0`) and loads incoming bytes from `*A4[A5]` (`0xc010f288 + read_index`) at `c0129152 LDBU *A4[A5], A0`. Read index is committed at `c012934c STW B0, *+B14[39]`.

### 2. SysEx Parser State Machine and Assembly Buffer (confirmed)
The MIDI task (`c0129118`) parses incoming bytes with a 5-state machine driven by table `0xc01844a8`, collecting Zoom SysEx messages into global metadata and a 1024-byte payload buffer at `0x1180ff20`.
- **Status Byte Detection**:
  - `c0129160 MVK 128, A0; CMPLT A6, A0, A0; [!A0] BNOP 0xc01292f6, 5` branches on status bytes (MSB=1).
  - Realtime bytes (`>= 0xf8` / 248) are ignored at `c01292f6..c01292fa`.
  - Non-realtime status bytes reset state `*+B14[167] = 0` at `c0129304`.
  - On `0xf0` (SysEx start): stores status byte in `*+B14[164]` at `c0129318`.
  - On `0xf7` (EOX): clears `*+B14[164] = 0` at `c0129320` and invokes the command dispatcher via `c0129324 CALLP.S2 0xc0128e54, B3`.
- **State Machine Table (`0xc01844a8`)**:
  - **State 0 (`c0129242`) - Manufacturer ID**: checks incoming byte against `0x52` (Zoom) or `0x7e` (Universal SysEx). Stores byte in `*+B14[165]`. On `0x52`, advances state `B14[167] = 1`, zeroes `B14[43] = 0`.
  - **State 1 (`c0129214`) - Device ID**: stores device ID (`0x00`) in `*+B14[168]`. For Zoom ID (`B6 == 82`), advances state `B14[167] = 2`.
  - **State 2 (`c0129276`) - Model ID**: receives model byte (e.g. `0x6e` for G1/G1X Four) in `*+B14[166]`. Advances state `B14[167] = 3`, zeroes byte counter `B14[43] = 0`.
  - **State 3 (`c01291f0`) - Payload Data**: increments `B14[43] = B14[43] + 1`, calls `c0127cf4(A4=byte, B4=count)`.
- **Payload Assembly Buffer at `0x1180ff20` (max 1024 B)**:
  - When `B14[43] == 1` (first payload byte): `c0127df0` stores the command byte as halfword at `0xc0183b60` (`STH A1, *+A7[0]`). If recognized, it sets internal command ID `*+B14[38]`.
  - When `B14[43] > 1` (subsequent payload bytes): bulk commands (cmd `>= 9`, routed through default branch `c0127d78 CALLP 0xc016f760`) jump to `11803010`.
  - Disassembly at `11803010`:
    ```text
    11803010 MV.L1    A4,A0
    11803012 MVK.S2   0,B0
    11803014 SET.S2   B0,10,10,B0        ; B0 = 1024 (0x400)
    11803016 CMPLT.L2 B4,B0,B0           ; check payload byte offset < 1024
    11803018 [!B0] BNOP.S1 0x1180302a,5  ; drop if overflow
    11803020 MVK.S2   0xffffff20,B5
    11803024 MVKH.S2  0x11800000,B5      ; B5 = 0x1180ff20
    11803028 STB.D2T1 A0,*B4[B5]         ; store data byte
    1180302a MVK.L1   1,A4
    1180302c BNOP.S2  B3,5
    ```
  - This proves the SysEx payload is assembled in L2 SRAM at `0x1180ff20`, bounded strictly at **1024 bytes** (1 KiB).

### 3. Zoom SysEx Command Dispatcher, Command Map, and Unknown Command Behavior (confirmed)
When a complete Zoom SysEx message terminates with `0xf7`, the MIDI task executes `c0129324 CALLP.S2 0xc0128e54, B3` to invoke the top-level command dispatcher `c0128e54` (`midi_cmd_dispatch`).
- **Internal Command Code Loading**:
  - `c0128e58 LDW.D2T2 *+B14[38], B2` loads the internal command ID assigned during inbound parsing by `c0127df0..c0127f58` (which inspects the command byte stored at `0xc0183b60`).
- **20-Way CMPEQ Cascade**:
  - `c0128e54..c0128f74` evaluates `B2` against 20 distinct internal codes:
    - `B2 == 1`  -> `c0128dd4` (Device Inquiry / Identity reply builder)
    - `B2 == 2`  -> `c01290ec` (no-op)
    - `B2 == 3`  -> `c012906c` -> `c0127500(0)` (status reply 0)
    - `B2 == 4` or `23` -> `c0128788` (error report builder)
    - `B2 == 6`  -> `c012890c` (simple reply forwarder)
    - `B2 == 8` or `22` -> `c0128474` (edit transaction coordinator 1)
    - `B2 == 9`  -> `c01290b8`: `STW 1, *+B14[26]`, `c0127500(0)` (PC mode / editor ON)
    - `B2 == 10` -> `c01290a8`: `STW 0, *+B14[26]`, `c0127500(0)` (PC mode / editor OFF)
    - `B2 == 11` -> `c0128b48` (parameter edit coordinator)
    - `B2 == 12` -> `c01289ec` (apply parameter edit into live effect state)
    - `B2 == 13` -> `c0128c88` (edit transaction coordinator 4)
    - `B2 == 14` -> `c0128d14` (bulk edit transaction)
    - `B2 == 15` -> `c0128c48` (send channel message dispatch)
    - `B2 == 16` or `17` -> `c0129084` -> `c0127500(11)` (error code 11 reply)
    - `B2 == 19` -> `c0128954` (edit transaction coordinator 3)
    - `B2 == 20` -> `c012906c` -> `c0127500(0)` (status reply 0)
    - `B2 == 21` -> `c0128210` (status reply builder 1)
    - `B2 == 24` -> `c0128134` (reply template builder 1898)
    - `B2 == 26` -> `c0128070` (subsystem init gate)
    - `B2 == 27` -> `c01438b0` / `c0127500(0)`
    - `B2 == 28` -> `c01437f0` / `c0127500(0)`
    - `B2 == 29` -> `c012d9e0`
    - `B2 == 30` -> `c016f6a0`
- **External Command Bytes Handled**:
  - The external command bytes mapping to these handlers are: `0x01`, `0x03`, `0x04`, `0x05`, `0x06`, `0x08`, `0x09`, `0x0e`, `0x28` (40), `0x29` (41), `0x2d` (45), `0x2e` (46), `0x33` (51), `0x44` (68), `0x45` (69), `0x46` (70), `0x48` (72), `0x50` (80), `0x51` (81), `0x52` (82), `0x53` (83), `0x55` (85), `0x56` (86), `0x57` (87), `0x60` (96), and `0x64` (100).
- **Unknown Command Behavior (confirmed silent drop)**:
  - If a command byte is not recognized (e.g. `0x70`), `c0127df0` leaves `*+B14[38] = 0`.
  - In `c0128e54`, `B2 == 0` fails all 20 `CMPEQ` checks and lands at `c0128f74 [!B0] BNOP.S1 0xc01290ec, 5`.
  - Common exit `c01290ec`:
    - Clears internal command ID: `c012910c STW.D2T2 B0, *+B14[38]` (`B0 = 0`).
    - Posts event 64 to `*+B14[139]`: `c0129100 CALLP 0xc0155ac0, B3; MVK 64, B4`.
    - Returns via `c0129114 BNOP.S2 B3, 5`.
  - **No error reply is sent**. The unrecognized message is dropped completely silently without affecting firmware state.
- **Model Byte for G1X Four**:
  - Model ID is `0x6e` (110 decimal).
  - Confirmed by `tools/midi_listen_g1.py:21` (`HDR = [0x52, 0x00, 0x6e]`), `tools/ua_bench.py:277`, and `mainapp_model_detect` (`c015d7e0`) which matches flash string "G1X IV" and initializes the global model ID at `0xc0183b48` to `0x6e` via `c0129600`.

### 4. Proposed Hook for CF Probe SysEx (confirmed & likely implementation options)
To allow a TEST-only CF Probe feature to intercept incoming host requests (`peek`, `watch`, LCD screenshot) before stock processing, the hook should be placed at the point of complete SysEx arrival.
- **Hook Location A (Recommended Call Hook)**:
  - Instruction address: `0xc0129324` in `midi_task_entry` (`c0129118`).
  - Current 32-bit word: `0xa18ab35b` (file offset `0x0001d2a0` in `res1_493412.bin`).
    - Lower 16 bits: `0xb35b` = `CALLP.S2 0xc0128e54, B3`.
    - Upper 16 bits: `0xa18a` = `BNOP.S1 0xc012932c, 5`.
  - Task/Context: **MIDI task** (`c0129118`), running at SYS/BIOS Task level.
  - Calling convention / Data locations:
    - Registers do not carry buffer arguments at `c0129324`. All SysEx fields reside in known global memory:
      - Command byte: halfword at `0xc0183b60` (`*(volatile uint16_t *)0xc0183b60`).
      - Model ID: byte at `*+B14[166]` (`0x6e`).
      - Manufacturer ID: byte at `*+B14[165]` (`0x52`).
      - Device ID: byte at `*+B14[168]` (`0x00`).
      - Payload buffer pointer: `0x1180ff20` (in L2 SRAM).
      - Payload length: `*+B14[43] - 1` (where `B14[43]` is the count of bytes in state 3: 1 command byte + payload).
      - Stock internal command ID: `*+B14[38]` (0 for unrecognized commands).
  - Hook handler protocol:
    ```c
    void cf_probe_sysex_hook(void) {
        uint16_t cmd = *(volatile uint16_t *)0xc0183b60;
        if (cmd == CF_PROBE_CMD) {  /* e.g. 0x70 */
            uint8_t *payload = (uint8_t *)0x1180ff20;
            uint32_t len = *(volatile uint32_t *)(B14_BASE + 43*4) - 1;
            cf_probe_handle_command(payload, len);
            /* consumed: return directly to caller without calling c0128e54 */
            return;
        }
        /* not mine: invoke stock dispatcher */
        stock_midi_cmd_dispatch();
    }
    ```
- **Hook Location B (Dispatcher Entry Replacement)**:
  - Instruction address: `0xc0128e54` (`midi_cmd_dispatch`).
  - Current 32-bit word: `0x01bc54f6` (`STW.D2T2 B3, *B15--[2]`, file offset `0x0001cdd4` in `res1`).
  - Next word: `0x0100266e` (`LDW.D2T2 *+B14[38], B2`, file offset `0x0001cdd8`).
  - Because `c0129324` is the SOLE caller of `c0128e54` in the whole firmware, replacing the opening instructions of `c0128e54` with a 32-bit branch/veneer avoids touching the compact fetch packet at `c0129324`.
- **Free Command Byte Choice**:
  - `0x70` (112 decimal):
    - Completely unused by stock firmware.
    - Command parser `c0127df0` leaves `*+B14[38] = 0`.
    - Subsequent payload bytes automatically route through `c0127d78` into buffer `0x1180ff20` up to 1024 bytes.
    - If CF Probe is inactive, stock firmware safely and silently drops it at `c01290ec`.

### 5. Reply Transmission Path via c01274cc (confirmed)
The reply path `c01274cc` is the standard raw MIDI/SysEx transmission entry used by stock reply builders.
- **Signature & Calling Convention**:
  ```c
  void c01274cc(const uint8_t *buf /* A4 */, uint32_t len /* B4 */);
  ```
  - `A4` holds the source byte buffer pointer.
  - `B4` holds the byte length.
  - Calling convention: Standard TI C6000 EABI register assignment.
  - Return value: Discarded (the routine restores callee-saved registers across the final semaphore release and does not return a status code to the caller).
- **Synchronization and Mutex**:
  - Takes semaphore `*+B14[161]` (`0xc0185084`) with timeout `-1` (`0xffffffff`, `BIOS_WAIT_FOREVER`):
    - `c01274d4 CALLP 0xc0150b20, B3; c01274d8 LDW *+B14[161], A4; c01274e0 MVK -1, B4`.
  - Calls internal transport: `c01274e4 CALLP.S2 0xc0144dc8, B3` with `A4=0` (port 0), `B4=buf`, `A6=len`.
  - Releases semaphore: `c01274f0 CALLP 0xc01628e0, B3; c01274f4 LDW *+B14[161], A4`.
- **Limits (Max Bytes & Backpressure)**:
  - Transport `c0144dc8` copies caller bytes into a **1025-byte circular ring** at `0xc0117b28` via `c0149de4`.
  - Because 1 byte is reserved for full detection (`c0149d84 SET A0,10,10,A0; c0149d8e CMPEQ B1,B0,B0`), the maximum capacity in one call is **1024 bytes**.
  - If the ring is full, `c0149de4` appends what fits and drops the remainder.
  - Blocking behavior: `c01274cc` blocks on the mutex `B14[161]` if another task is transmitting, but it does **not** block on USB wire completion. It queues bytes into the TX ring and signals worker `c0149d40` via event bit 1 on `B14[90]`.
- **Allowed Calling Context**:
  - **SYS/BIOS Task context ONLY**.
  - It must **never** be called from Hwi or Swi context, because `Semaphore_pend` with an unbounded timeout is illegal at interrupt level.
  - Stock callers are all Task-level: MIDI task (`c0129118`), UpdateUI task (`c013c754`), and MainApp task (`c0134e10`).
  - Calling `c01274cc` directly from the proposed CF Probe hook inside the MIDI task context (`c0129118`) is completely valid, thread-safe, and matches stock behavior.






## Answers
### Step 1: USB MIDI OUT receive & SysEx assembly
### Step 2: Zoom SysEx dispatcher & command values
### Step 3: Proposed hook for CF Probe
### Step 4: Reply path (c01274cc) signature and limits

## Not checked / open leads
