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

## 2. Pre-loop handshake message (confirmed bytes; semantics guess)
Just before the stage loop, `0x403b17..0x403b62`: copies 17 bytes from `.rdata 0x43ac74` into a
scratch SysEx buffer (`0x9d9c10`), patches in the model byte at offset 3, then calls the generic
5-byte-number appender (`0x403a50`, section 5) twice into the same buffer before sending all 17
bytes via `0x403df0` (section 6). Template (confirmed, read directly from `.rdata`, indexed byte by
byte to avoid the off-by-one this doc's first draft had):
```
idx: 0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16
     f0 52 00 00 60 30 00 00 00 00 00 00 00 00 00 00 f7
```
Offset 3 is overwritten with the model byte; offsets 6-10 are overwritten with
`num7(0x27FFC, 5)` (`push 0x9d9c16` = buffer base `0x9d9c10` + 6) and offsets 11-15 with
`num7(4, 5)` (`push 0x9d9c1b` = base + 11), both confirmed call-site arguments. Byte-for-byte:
```
F0 52 00 <model> 0x60 0x30 <5B num=0x27FFC> <5B num=4> F7      (17 bytes)
```
**Guess:** purpose not traced further (likely an "enter programming session" / capability-
announce message); the fixed byte `0x30` at offset 5 and the meaning of the two numeric fields
are unconfirmed. Not needed to reproduce stage 0-7 if the pedal does not gate on it, but send it
anyway until proven unnecessary — cheap and matches what the real updater does.

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

## 7. What is still a gap (be explicit, do not guess past this)
- The **reply/ack message format** from the pedal (what sets `this+0x2138`, consumed by the
  write loop in section 4 step 2) was not located. Without it we cannot know how the pedal
  signals "chunk accepted, send the next one" vs "retry" vs "done" vs "error" — needed before any
  standalone tool can safely drive multi-chunk writes without guessing from silence/timeouts.
- Section 2's handshake message's necessity and the meaning of its two numeric fields (`0x27FFC`,
  `4`) are unconfirmed.
- The model byte at `.data 0x44bc0c`: 12 read sites found, zero write sites in `.text` (checked by
  exact-displacement operand match across the whole disassembly) — consistent with a zeroed BSS
  default that is simply never changed (matches this project's existing convention of device id
  `0x00` everywhere else, `docs/helpers/FW_RND_S12_SYSEX_HOOK_2026-10-22.md` Finding 6), but not
  proven; a write via a computed (register-relative) address cannot be ruled out by this check.
- Section 6's transport call chain below `0x401c20` and the MIDI port/device-open sequence before
  the handshake (`0x403ae7` region and earlier) were not traced.
- **Nothing here has been tried against real hardware.** All of it is static analysis of the x86
  host program. Before any live attempt: capture a real update-mode session (this project already
  has the tooling pattern for a passive MIDI listener; USB-MIDI class-compliant ports often allow
  a second app to open the same IN port read-only while Zoom's own exe is using it) to confirm the
  reply format from section 7's first gap, and to confirm bytes match this document exactly,
  *before* ever sending a real erase/write built by new code. Until then treat `tools/
  update_mode.py` (if/when written from this doc) as an unverified candidate only.

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
