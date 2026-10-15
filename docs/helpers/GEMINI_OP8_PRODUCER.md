# Brief (Antigravity / Gemini): who invokes the MIDI port callback, and with which event numbers

Follow `docs/helpers/SAVE_PROTOCOL.md` exactly, including its Token economy section.
- Report: **`docs/helpers/GEMINI_OP8_REPORT.md`**. Create it first with the
  headings below and commit it. After every finding, commit THAT FILE ONLY.
- Scratch folder: `build/gemini_op8/`. This is static analysis only. Never touch
  the pedal, MIDI/USB devices or any .exe, and never push. Do not edit any other file.
- Input: `build/fw/map/main.dis` (TI C6000 disassembly, one instruction per
  line: `address  opcode  [||] mnemonic operands`). `recon/map/chunk_*.md`
  has function names; grep it, do not read it whole.

## Background
The callback `c0144c0c` (the MIDI TX port op dispatcher) is registered by
`c0145154..5160` through `c0152410`, which stores it at `0xc011ac80`
(`c0152436 STW A0,*A6[0]` with A6=`0xc011ac80`). It dispatches op codes 2..8
through the table `0xc01843d8`. Op 8 (`c0144d0c`) resets the MIDI ring.
Producers are already known for ops 2, 3 and 5 (see section 4 of
`docs/helpers/USB_LIFECYCLE_CONTINUATION_2026-10-14.md`). Each of them loads
`*0xc011ac80` and calls it at `c01520cc..20e4`.

## Tasks (one report section each)
1. **All loads of 0xc011ac80.** Find every instruction that forms
   `0xc011ac80` (an `MVK 0xac80` or `MVK 0xffffac80` with `MVKH 0xc0110000`
   within ~16 lines, or an equivalent base plus offset). For each one, give
   the address, whether it is a load or a store, and the enclosing function.
   Write a small Python script in your scratch folder to do the scan; do not
   eyeball the file.
2. **Every call through the loaded pointer.** For each load, follow the
   register to an indirect call (`B .S2 Bx` / `CALL` with a register, or
   `BNOP reg`). Record the value of the event-number argument at that call:
   A4 or B4, whichever one `c0144c0c` reads as A1. Check what the first few
   lines of `c0144c0c` move into A1. List event numbers 2..8 and their call sites.
3. **Op 8.** Which call site, if any, passes 8? If none does, say so plainly.
   Do not guess.
4. **Context.** For each call site, name the enclosing function and its
   direct callers (two levels up at most). Is it reached from the
   handler table `0xc01807a0` (dispatched only at `c01383ea`)?

Every claim needs an address, a short excerpt of at most 8 lines, and a
confidence (confirmed / likely / guess). If you cannot determine
something, write "unknown". Do not fill gaps with plausible guesses.
Pitfalls:
- A `CALLP` to `c016e0XX` is a function epilogue.
- `||` means the instruction runs in the same packet as the one before it.
- Delay-slot instructions after a branch still execute.
