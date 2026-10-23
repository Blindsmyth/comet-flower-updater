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


## Answers
### Step 1: USB MIDI OUT receive & SysEx assembly
### Step 2: Zoom SysEx dispatcher & command values
### Step 3: Proposed hook for CF Probe
### Step 4: Reply path (c01274cc) signature and limits

## Not checked / open leads
