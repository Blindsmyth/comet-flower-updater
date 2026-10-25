# Recon 26: update-mode SysEx wire protocol (host side, from the updater .exe)

Static analysis only, of the HOST program, not the pedal firmware: `build/public_release/
ZOOM G1X FOUR System v2.00 (Official Stock Restore).exe` (every "Comet Flower ... Updater.exe"
build/*.exe in this repo is a byte-identical copy of this same x86 code; only embedded PE
resources differ, per `make_fs_restore_updater.py`). x86, 32-bit, no .NET CLR header. Read with
`pefile` + `capstone` (both already in `.venv`), no disassembler project file. Every address is
a file/image VA in that one exe; confirmed = read directly from the disassembly listing below
(reproducible with the one-liner each section implies), not inferred.

Goal: can we drive the pedal's update mode ourselves, without Zoom's exe at all. Answer so far:
**yes, this is a plain MIDI SysEx protocol** (the exe imports `WINMM.dll`'s `midiOut*`/`midiIn*`,
not any vendor USB driver), using the exact same 7-bit packing and CRC32-complement convention
already implemented in this repo's `zoomzt2.py` (vendored at `C:\Users\z\zoomlab\stomphacks\
zoom-zt2`) for normal-mode patch/file SysEx. No new packing code is needed, only new message
builders.

## 1. Stage table (confirmed, already known from `make_fs_restore_updater.py`; now also seen at the instruction level)
Walker loop at `0x403c66..0x403dbc` (inside the stage-execution function starting `0x403ae7`-ish,
not fully bounded above). Table at VA `0x0043AC88`, 8 entries x 16 bytes, confirmed by:
```
0x00403cb7  mov edx, [ebp-0x2c]      ; loop index 0..7
0x00403cba  shl edx, 4               ; *16
0x00403cbd  mov eax, [edx + 0x43ac88]   ; op
```
then `op==1` branch reads `[idx*16+0x43ac8c]`=addr, `[idx*16+0x43ac90]`=size and calls the erase
function (`0x4037f0`, see section 3); `op==2` branch reads `[+0x43ac8c]`=addr, `[+0x43ac90]`=size,
`[+0x43ac94]`=resource id and calls the write function (`0x4034d0`, section 4). Confirmed table
contents (`.rdata`, read directly, matches `make_fs_restore_updater.py`'s hard-coded `EXPECTED`
exactly):
```
stage 0: erase 0x0bf000 size 0x1000
stage 1: erase 0x028000 size 0xb000
stage 2: write 0x028000 resource 133
stage 3: erase 0x000000 size 0x28000
stage 4: write 0x000000 resource 142
stage 5: erase 0x033000 size 0x8c000
stage 6: write 0x033000 resource 129
stage 7: write 0x0bf000 resource 139
```

## 2. Pre-loop Flash Read (`cmd = 0x60`) and the boot-skip check (confirmed)
Before the stage loop (`0x403ad7..0x403c58`), `0x403aa0` initialises `[ebp-0x18] = 1` (`write_boot = 1`)
and scans the stage table for any entry with `addr == 0` (`0x403b00: cmp dword ptr [ecx+0x43ac8c], 0`).
When present, `0x403b0d..0x403b62` zeroes the read-buffer index `[0x44bc08]`, copies 17 bytes from
`.rdata 0x43ac74` into the scratch SysEx buffer (`0x9d9c10`), patches in the model byte (`0x6E`) at
offset 3, and calls the generic 5-byte-number appender (`0x403a50`, section 5) twice (`addr = 0x27FFC`
at offset 6, `size = 4` at offset 11) before sending all 17 bytes via `0x403df0`:
```
idx: 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16
     f0 52 00 6e 60 30 7c 7f 09 00 00 04 00 00 00 00 f7
```
Byte-for-byte:
```
F0 52 00 <model=0x6E> 0x60 0x30 <addr=0x27FFC:5x7bit-LE> <size=4:5x7bit-LE> F7      (17 bytes)
```
**Confirmed semantics (`0x403bfc..0x403d1c`):**
1. Waits up to 60,000 ms (`0xea60`) on `[this+0x2134]` for the pedal's `0x60 0x04 0x30` read-data
   reply (section 7), which unpacks 4 bytes from flash `0x27FFC..0x28000` into `.data 0x44bc10`.
2. Loads Resource `0x8E` (the `0x28000`-byte boot program; its last 4 bytes at `+0x27FFC` are the
   ASCII boot version `"1.00"`, `31 2e 30 30`) and runs `memcmp(res_0x8e + 0x27ffc, 0x44bc10, 4)`
   at `0x403c43`.
3. **If those 4 bytes are equal (`test eax, eax; jne 0x403c56`), `0x403c4f` sets `[ebp-0x18] = 0`**,
   and the stage loop (`0x403ce1..0x403d1c`) **skips** both the erase (`op==1`) and write (`op==2`)
   stages for `addr == 0x000000`!
   - Consequence 1: Zoom's official updater does *not* rewrite the boot region (`0x000000..0x028000`)
     when the pedal already has `"1.00"` at `0x27FFC`.
   - Consequence 2: Any boot-logo updater (`tools/make_boot_logo_updater.py`) that only edits the
     184 logo bytes at `0x1be60` in Resource `0x8E` while leaving `0x27FFC..0x28000` (`"1.00"`) and
     `0x403c4f` untouched will silently skip its boot stages and exit immediately without writing flash.
     Patching `0x403c4f` (`mov dword ptr [ebp-0x18], 0` -> `1`) forces the boot write while keeping
     the `"1.00"` version tag in flash intact.

## 3. Erase message (confirmed, full byte layout)
`0x4037f0(this, addr, size)` -> `0x4033f0(this, model_byte, addr, size)` builds and sends:
copies a 16-byte template from `.data 0x4490f0` (confirmed bytes: `f0 52 00 00 0a 00 00 00 00 00
00 00 00 00 00 f7`), overwrites offset 3 with the model byte, offsets 5-9 with `addr` and offsets
10-14 with `size`, each as 5 bytes 7-bit little-endian (same bit-shift pattern as section 5), and
sends all 16 bytes via `0x403df0`:
```
F0 52 00 <model> 0x0A <addr:5x7bit-LE> <size:5x7bit-LE> F7      (16 bytes)
```

## 4. Write-chunk message (confirmed, full byte layout) and the write loop
`0x4034d0(this, addr, size_or_0, resource_id)`:
1. `FindResourceA(0, resource_id, "BIN")` -> `LoadResource` -> `LockResource` to get a pointer to
   the resource's raw bytes (confirmed: IAT thunks at `.rdata 0x43a2ac/b0/b4`, resource-type
   string `"BIN\0"` read directly at `0x43ad90`); `SizeofResource` gives the real length when the
   stage's `size` field is 0 (true for every write stage in section 1's table — the exe trusts
   the resource's own size, not a caller-supplied number).
2. Loop, chunk = up to `0x1000` (4096) bytes at a time, while `written < total`:
   calls `0x4032c0(this, model_byte, chunk_ptr, addr+written, chunk_len)` to build+send one
   message, then polls for an ack with up to 30 retries x 100 ms `Sleep` (`[0x43a2cc]`) before
   giving up; a per-reply status field at `this+0x2138` (0 = keep going, 0xFF = a different
   continue case, anything else on the "not 0xFF" branch = stop) gates whether the loop advances
   — **gap:** the reply-parsing code that sets `this+0x2138` was not located in this pass (see
   section 7); only this consumer side is confirmed.
3. `0x4032c0`'s message, byte for byte (confirmed, full trace):
   - 5-byte template from `.data 0x4490c8` (confirmed bytes: `f0 52 00 00 02`) copied to the
     scratch buffer, offset 3 overwritten with the model byte: `F0 52 00 <model> 0x02`.
   - offsets 5-9: `addr`, 5x7bit-LE (same shift pattern as section 5/3).
   - offsets 10-11: the **low 14 bits only** of `chunk_len` as 2x7bit-LE (`and 0x7f` then
     `sar 7; and 0x7f`) — sufficient since chunk_len never exceeds `0x1000` (4096 < 2^14).
   - offset 12 onward: the raw chunk bytes 7-bit-packed by `0x401080` (section 5b) — confirmed
     bit-for-bit identical to `zoomzt2.py`'s `pack()` (same MSB-collector-byte-first-then-7-payload
     -bytes shape, same bit order: byte0's bit7 -> collector bit 6, byte1's bit7 -> bit 5, ...,
     byte6's bit7 -> bit 0). Reuse `zoomzt2.pack()` directly; do not reimplement.
   - immediately after the packed data (at byte offset `12 + packed_len`): a 5-byte 7-bit-LE
     **checksum** of the *raw* (unpacked) chunk bytes, computed by `0x401030` (section 5c) —
     confirmed to be exactly `binascii.crc32(data) ^ 0xFFFFFFFF` (see section 5c); this project's
     own `zoomzt2.patch_upload`/`patch_g1.py` already compute checksums this exact way, so reuse
     that expression directly.
   - final byte: `F7`.
   - total send length = `0x12 (18) + packed_len`, confirmed (`[ebp-8]` holds `packed_len`
     returned by `0x401080`, `edx = that + 0x12` is the pushed send length).
```
F0 52 00 <model> 0x02 <addr:5x7bit-LE> <len:2x7bit-LE, low 14 bits> <packed data> <crc:5x7bit-LE> F7
```

## 5. Shared encodings (confirmed)
- **5a. Generic 5-byte 7-bit-LE number appender**, `0x403a50(value, dst)` (used for the section 2
  handshake numbers): `dst[0]=v&0x7f; dst[1]=(v>>7)&0x7f; dst[2]=(v>>14)&0x7f; dst[3]=(v>>21)&0x7f;
  dst[4]=(v>>28)&0xf`. The erase (section 3) and write-chunk (section 4) address/size/length
  fields use the identical bit pattern inlined rather than calling this helper, confirmed by
  reading `0x403416..0x4034ab` and `0x4032e5..0x40334b` directly (last byte masked `0x7f` there,
  not `0xf`, but the top 3 bits are always 0 for a 32-bit value shifted right 28, so it is the
  same number either way).
- **5b. 7-bit pack**, `0x401080(dst, src, len)`: for each group of up to 7 source bytes, writes
  one collector byte (initial value `0x40`, shifted right by 1 after each of the up to 7 bytes it
  covers — i.e. collector bit 6 <- byte0's bit 7, bit 5 <- byte1's bit 7, ..., bit 0 <- byte6's
  bit 7) followed by each byte's low 7 bits; returns the total packed length written. Confirmed
  identical in shape and bit order to `zoomzt2.py`'s `pack()` (reread side by side: `encode[0] +=
  (byte&0x80)>>len(encode)` with `len(encode)` running 1..7 produces the same bit6..bit0 mapping).
  **Use `zoomzt2.pack()` as-is for this.**
- **5c. Checksum**, `0x401030(data, len)`: accumulator initialised to `0xFFFFFFFF`
  (`mov [ebp-8], 0xffffffff`), updated per byte by `0x401000(acc, byte)` = `table[(acc^byte)&0xff]
  ^ (acc>>8)` reading a 256-entry table at `.rdata 0x43a6a0` (confirmed: standard CRC32 per-byte
  step, table not dumped/verified against the standard polynomial but the per-byte formula is the
  textbook one), no final complement. This is exactly the raw accumulator that Python's
  `binascii.crc32(data) ^ 0xFFFFFFFF` produces (the library call complements twice: once internally
  at the end, once explicitly by the `^ 0xFFFFFFFF`, landing back on the pre-final-complement
  value this loop returns directly). **Use `binascii.crc32(data) ^ 0xFFFFFFFF` as-is for this**
  (same expression `zoomzt2.patch_upload`/`tools/patch_g1.py` already use for normal-mode SysEx).

## 6. Transport (confirmed shape, not fully traced)
`0x403df0(this, buf, len)` calls `this+0x211c`'s object (a vtable-style call through `0x401c20`,
not traced further) and translates its return (nonzero = success) to this function's own
0-success/-1-fail convention, used by every message builder above as the actual send. The deeper
call eventually reaches `midiOutPrepareHeader` -> `midiOutLongMsg` -> `midiOutUnprepareHeader`
(confirmed import call sites at `0x401c41/0x401c60/0x401c94`, inside a different, not yet
pinpointed wrapper — **gap:** the exact call path from `0x401c20` down to those three WINMM calls
was not traced instruction by instruction this pass, only that both ends exist in the same exe).
MIDI port selection ("ZOOM G Series" shown in the updater's own UI, `docs/RECOVERY_G1.md`) is
also not traced; **gap:** whether update mode enumerates under a different USB product string
than normal mode, or the same port just answers differently, is unknown from this pass.

## 7. Session lifecycle (`0x404630`) and incoming SysEx reply parser (`0x403ee0`) (confirmed)
When the user starts the update (`0x4045fb` spawns worker thread `0x404630`):
1. **Universal Device Inquiry (`0x4046ac`):** Sends `F0 7E 00 06 01 F7` (6 bytes at `.data 0x4490a0`)
   and waits up to 30,000 ms (`0x7530`) on `[this+0x2134]`.
   - In `0x403ee0`, when a reply with `msg[1] == 0x7E`, `msg[3] == 0x06`, `msg[4] == 0x02` arrives
     (`0x40410b..0x404175`), it sets `[this+0x2138] = 0`, copies the 4-byte family/member ID at
     `msg[6..9]` into `this+0x213c`, and signals the event (`0x405f10`).
   - `0x4047cc` copies those 4 bytes from `this+0x213c` to `.data 0x44bc0c` via `memcpy(0x44bc0c,
     this+0x213c, 4)` (`0x4234b0`), checks them against the 3 allowed 4-byte entries at `.rdata
     0x43ac68` (`6e 00 0d 00` for G1X FOUR, `6e 00 0b 00` for G1 FOUR; mismatch shows STRINGTABLE
     `0x69` `"Illegal device connected."`), and writes the first byte **`0x6E`** (`byte ptr [0x44bc0c]`)
     into the `.data` templates (`0x404954..0x40499f`). Thus **`<model>` is `0x6E`**.
2. **Enter Update Session (`0x4049a2`):** Sends `F0 52 00 0x6E 0x01 F7` (6 bytes at `.data 0x4490c0`)
   and waits up to 30,000 ms (`0x7530`).
   - Checks `[this+0x2138]` at `0x404a8e`:
     - `0x00`: success -> `Sleep(500)` (`0x404bc8`) -> `call 0x403aa0` (stage runner).
     - `0x0B`: pedal is in normal mode, not firmware update mode -> shows STRINGTABLE `0x6A`
       (`"Please use the firmware update mode."`).
     - `0xFF`: port closed / aborted (`0x404263`).
     - Any other value: shows STRINGTABLE `0x6B` (`"Transfer error occurred."`).
3. **Incoming `F0 52 00 <model> <cmd> ... F7` dispatch (`0x403ee0`, jump table `0x4041b0`, index table `0x4041d0`):**
   - **`cmd == 0x00` (case 0, `0x403f81` — Status / ACK / NACK):**
     `F0 52 00 0x6E 0x00 <status> F7` (7 bytes). Reads `status = msg[5]`, stores `[this+0x2138] = status`
     (`0x00` = ACK/OK, non-zero = error/retry), and signals the event (`0x405f10`).
     - In `0x4037f0` (erase): waits up to 60,000 ms (`0xea60`); `status == 0` completes the erase;
       non-zero (not `0xFF`) sleeps 100 ms (`0x64`) and retries up to 6 times (`cmp ecx, 5; jle`).
     - In `0x4034d0` (write chunk): waits up to 1,000 ms (`0x3e8`); `status == 0` resets the retry
       counter and advances `written += chunk_len`; timeout or non-zero status (not `0xFF`) sleeps
       100 ms (`0x64`) and re-sends the *same* chunk up to 31 times (`cmp edx, 0x1e; jle`).
   - **`cmd == 0x02` (case 2, `0x403fb1`):** Sets `[this+0x2138] = 0` and signals the event.
   - **`cmd == 0x60` (case 6, `0x403ff0` — Flash Read Reply):**
     Format: `F0 52 00 0x6E 0x60 0x04 0x30 <2B> <raw_len:2x7bit-LE at msg[9..10]> <packed_data at msg[11..11+plen]> <crc32:5x7bit-LE> F7`.
     Presets `[this+0x2138] = 1`, unpacks `plen` bytes via `0x401180` into `0x44bc10 + [0x44bc08]`,
     computes `crc32` (`0x401030`) over the `raw_len` unpacked bytes, compares against the 5-byte
     7-bit-LE CRC decoded by `0x403e70`, and if equal advances `[0x44bc08] += raw_len` and sets
     `[this+0x2138] = 0` before signaling the event.
   - **`cmd == 0x01, 0x04, 0x05` (cases 1, 4, 5):** Sends host ACK `F0 52 00 0x6E 0x00 0x00 F7` (`0x404360`).
   - **Unrecognized `cmd > 0x60` (case 7, `0x4040ff`):** Sends host NACK `F0 52 00 0x6E 0x00 0x01 F7` (`0x4043a0(1)`).
4. **Exit Update Session (`0x404c15`):** After `0x403aa0` completes all stages, sends
   `F0 52 00 0x6E 0x04 F7` (6 bytes at `.data 0x4490e0`), waits up to 30,000 ms (`0x7530`) for ACK,
   and displays STRINGTABLE `0x6C` (`"Version update completed."`).

## Method note (for anyone re-deriving this)
`pefile` resolves the PE/IAT; `capstone` (`CS_ARCH_X86`, `CS_MODE_32`) disassembles `.text`.
Anchor point that made this tractable: `make_fs_restore_updater.py` already named the exact
`.rdata` VA of the stage table (`0x43AC88`) from its own resource-patching work; searching
`.text` for instructions containing that literal as a 4-byte LE immediate/displacement found
exactly one hit, `0x403cbd`, which was the stage-walker loop itself. From there, every function
address in this document was reached by following that one function's `call`/`push` operands
outward (erase/write dispatch -> message builders -> shared pack/crc helpers), never by
guessing. The WINMM import thunk table (resolved via `pefile`'s `DIRECTORY_ENTRY_IMPORT`) gave
the independent confirmation that this is plain MIDI SysEx, not a vendor USB protocol.
