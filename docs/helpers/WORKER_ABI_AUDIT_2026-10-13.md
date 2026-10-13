# Worker ABI and timeout audit — 2026-10-13

Offline audit complete; candidate remains DO_NOT_FLASH. No updater/device operation.

## Artifact identity

### Confirmed: binary identity against loose firmware
Current raw firmware SHA-256: `f1478153ed179d167a799ba4f94aedd3a1a4550f20ab771cfc38bc84b9d4c021`, differing from candidate document packaged resource `0ecddd...` because commit `6ac9489` hooked the second AD channel at `c01600b0` to `c01a0860`. Current linked ELF SHA-256: `094bbad93f0daf457bb4e56817e1176c8a4081eabcc27826e936329e39414df3`.

### Confirmed: listing matches current raw candidate
Fresh TI `dis6x` disassembly from the current ELF is byte-identical to `build/controller/controller.dis` (SHA-256 `d6bf71b2d56a6274fad55774347430b998daae6f09b934d20a629b7d7c92e707`). `elf_image` extraction and AIS walk show the complete 2656-byte allocated payload at `c01a0000` equals the current raw firmware payload; payload hash `d2b5110279aa141a01910f5edebfe43ff61c6d158519df4cd114a65b768cb822`. Scratch `build/worker_abi_audit/check_payload.py` verifies this payload match without rebuilding or running an updater.

## Stock timeout control flow

### Function contract & register setup (`c014a0cc`)
Stock caller `c0149d40` passes:
- **A4**: Event handle from `B14[90]`
- **B4**: Event bitmask (`3`)
- **A6**: Mode flag (`1` for OR, `0` for AND)
- **B6**: Pointer to output word (`caller SP+4`)
- **A8**: Timeout (`-1` / `0xFFFFFFFF` in stock worker, `100` in controller wrapper)

`c014a0cc` saves registers via helper `c016e020`, evaluates mode in `A6`, normalizes mask into `andMask` (B4) and `orMask` (A6), checks timeout in `A8` against `-1` at `c014a0e8`, and invokes lower wait `c0144580` with timeout in register **B6**.

### Confirmed: timeout leaves output word unchanged
Stock `c014a102` copies lower wait return A4 to A0.
- **Success Path (`A0 != 0`)**: `[A0] BNOP c014a10c, 5` lands at `c014a10c`, stores the returned event bits through preserved output pointer A10 (`c014a10e STW A0, *B4[0]`), sets `A0 = 0` at `c014a110`, and returns 0 in A4.
- **Timeout Path (`A0 == 0`)**: `[A0] BNOP` is not taken. Control falls through to `c014a106 BNOP c014a114, 3`. Its two delay slots execute:
  - `c014a108 MVK 50, A0`
  - `c014a10a NEG A0, A0` (A0 becomes `-50`)
  The branch lands at `c014a114`. **The instructions at `c014a10c..c014a110` are completely skipped**, including the store at `c014a10e`. The output word `*out_bits` is never written on timeout. Callee registers are restored and `c014a118 MV A0, A4` returns `-50` in A4.

The controller wrapper prezeros the output word (`c01a0200 STW 0, *B11[0]`), so a timeout with no append leaves zero. An append defensively normalizes nonpositive output before setting bit 0.

### Lower wait dispatch (`c0144580`)
`c0144580` receives timeout in B6, saves it at `*B15[31]`, packs it into stack record slot 30 (`*B15[30]`), and passes the record through `c016a240` to universal synchronization core `c015a520`. Finite timeouts are armed at `c0144aec` through `c0166580` against the periodic Clock tick counter.

## Compiled wrapper ABI and stack

### Confirmed: wrapper arguments and preserved return
Stock caller `c0149d42..54` sets A4=event from `B14[90]`, B4=3, A6=1, B6=caller SP+4, A8=-1. Wrapper keeps event in B5 and output pointer in B11. In controller mode `c01a0200` clears `*B11`, `c01a0204/206` restore A4/B6, `c01a0208` sets A8=100; B4/A6 remain intact. Branch target in A3 is `c014a0cc`. Mode-off takes predicated branch at `c01a01d4` with original arguments and returns through `c01a01e8`.

At `c01a0210/212`, `CALLP port_ready` runs in parallel with `MV A4, A15`: the wait return code is captured before `port_ready` replaces A4. Every controller exit joins `c01a05a0`; `c01a05a6` copies A15 back to A4 before A15 is restored. The stock worker ignores A4 and loads `*B15[1]` at `c0149d56`, tests bit 0 at `c0149d60`, and invokes drain calls only when bit 0 is set. The wrapper thus preserves the wait return contract while setting output bit 0 to signal controller append.

### Confirmed: wrapper frame balance; stack capacity remains open
Wrapper prologue `c01a01a8..1e0` saves A11, A10 (two 8-byte SP steps), B13:B12, B11:B10, A15:A14, A13:A12 (four 8-byte steps), and B3 with a 24-byte SP step. Total B15 decrement is 72 bytes, preserving 8-byte alignment. Both epilogues `c01a01e8..1fa` and `c01a05a0..5b4` undo exactly these steps. B14 is untouched. Output pointer refers to caller-owned SP+4 word.

Frame breakdown:
- Wrapper frame: 72 bytes
- Stock EVENT_WAIT (`c016e020` save helper): 56 bytes
- Lower wait `c0144580`: 56 bytes callee saves + 128 bytes locals = 184 bytes
Total known depth below wrapper-entry SP: **312 bytes** (72 + 56 + 184), before deeper callees/interrupt/task context. Append helper `c01a0070..90` balances 32 bytes; `port_ready` and `ring_free` are leaf helpers.

## Timeout units

### Kernel architecture & Clock tick definition
The firmware runs on **TI SYS/BIOS** (TI-RTOS Kernel with XDC runtime). In SYS/BIOS (`ti.sysbios.knl.Event`, `ti.sysbios.knl.Clock`), all wait and sleep durations are expressed in **Clock ticks**.

- Clock tick period: Standard SYS/BIOS configuration specifies `Clock.tickPeriod = 1000 µs` (1 ms per tick, 1 kHz).
- Tick servicing: The 32-bit tick counter at `0xc0182054` increments on periodic timer interrupt callback `diag_counter_tick_cb` (`c016a2e0`).
- Argument scaling: Neither `c014a0cc` nor `c0144580` applies scaling or prescaling; timeout argument A8 is passed directly as raw Clock ticks.

### Concrete values
- `A8 = -1` (`0xFFFFFFFF`): `BIOS_WAIT_FOREVER` (blocks indefinitely until event bits arrive).
- `A8 = 0`: `BIOS_NO_WAIT` (polls without yielding).
- `A8 = 100`: **100 Clock ticks** = **100 ms** (0.10 seconds).
With timeout 100, the controller worker wakes up and re-evaluates port readiness, reconnect, and pending edges every ~100 ms even when no hardware event occurs.

## Remaining gates and recommended corrections

1. **Task stack margin**: Confirm worst-case task stack headroom beyond 312 bytes under preemption and interrupt nesting.
2. **USB lifecycle observation gap**: As detailed in `USB_LIFECYCLE_AUDIT_2026-10-13.md`, implement a transport generation token or ring reset hook (`c014a018`) so that disconnect/reconnect cycles between 100 ms wake intervals invalidate obsolete sent-state and replay desired controls.
3. **Packaging reconciliation**: Rebuild and package under an updated candidate identity that includes the second AD channel hook (`6ac9489`) and verify exact SHA-256 hashes prior to hardware tests.
