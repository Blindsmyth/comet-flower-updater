# Brief: gpt-6-sol calibration read (2026-10-09)

You are reversing the firmware of a Zoom G1X Four pedal (TI C674x DSP,
little-endian). Read-only task, short. Answer in your report file only.

Rules:
- Do not touch the pedal, MIDI, pedal tools or updater .exe files.
- Do not edit or commit anything. Write only `build/sol_calib/REPORT.md`.
- Follow the token economy in `docs/helpers/SAVE_PROTOCOL.md` (no whole-file
  prints; `sed -n` windows of at most 60 lines; grep with tight patterns).
- Do NOT read `recon/` or `docs/fwmap/` — this is a blind test.

Inputs:
- `build/fw/map/main.dis` — full disassembly, one instruction per line:
  `<addr>   <opcode>   <mnemonic> <operands>`. Use `grep -n '^c0135940'` to
  find a line number, then `sed -n` a window.
- `build/fw/map/refs.txt` — `<insn addr> <reg> <constant>` for every
  MVK/MVKH-built constant.
- C6000 notes: MVK sets the low 16 bits sign-extended, MVKH sets the high 16
  bits. Branches and CALLP have delay slots; BNOP/CALLP execute the next
  packets before the target.

Questions (the code is part of a USB device stack; it is a MUSB-style
controller):
1. Function c0135940: what USB request does it implement? Which setup-packet
   fields does it read (byte offsets), where does it store what (give the
   full absolute address of any array, computed from MVK/MVKH), which
   functions does it call, and what are its error paths? Does it bound-check
   anything?
2. Function c01357c8, called from c0135940: what does it do, step by step?
   What does it match on (field offsets), where does its data come from, and
   which function does the endpoint/FIFO configuration?
3. Who else calls c01357c8?

For every claim give the instruction address and a short excerpt, and a
confidence (confirmed / likely / guess). Keep the report under 80 lines.

## Result (Claude, 2026-10-09)
`gpt-6-sol` is refused on the owner's ChatGPT account ("not supported when
using Codex with a ChatGPT account"). Ran **`gpt-5.6-sol`, low effort**: 2 min,
25k tokens. Graded against recon/21 3.1:
- Right: SET_INTERFACE; wIndex/wValue offsets; 0xc011a1b0 from MVK/MVKH; no
  bounds check; c01357c8 gets descriptors from c0160ec0, matches type 4 /
  +2 / +3, configures endpoints through c01212e0. New: second caller
  c01356fa in SET_CONFIGURATION (verified).
- Wrong: folded the separate leaf c01359b8 into c0135940 (past the c016e000
  epilogue); missed the 0xffff8acc error code loaded in the BNOP delay slot
  at c0135958.
Verdict: good enough for targeted reads with a Claude review. Same pitfalls
as earlier helpers.
