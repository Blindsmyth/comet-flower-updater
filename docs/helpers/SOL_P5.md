# Brief (Codex gpt-5.6-sol, medium): how USB handler records bind to interfaces (patch item P5)

Follow `docs/helpers/SAVE_PROTOCOL.md` (including Token economy) exactly.
- Report: **`recon/24_if_record_binding.md`**. Create it with the headings
  below, commit it, then commit THAT FILE ONLY after every finding.
- Scratch: `build/sol_p5/`. Static only; never touch the pedal, USB/MIDI
  devices or any .exe; never push.
- Inputs: `build/fw/map/main.dis`, `build/fw/map/refs.txt` (constants: use it),
  names in `recon/map/chunk_*.md` (grep). Context (grep, don't print whole):
  `recon/20_usb_audio_proto.md` 2.2 and 2.6, `recon/21_usb_audio_needs.md` 3.1.

## Background
MIDI registers its handler record with `c015afa0(A4=6, B4=0xc018137c)` at
c01521a8..b4 (slot 1, c0152198, calls it with B4=0, probably unregister).
The record is 5 function words: +0 c0151ecc, +4 c0151e80, +8 c0151ff4,
+12 c0151ed0 (request callback), +16 c0151e84. c015afa0 -> c0138a6c ->
c015c6b4 -> c015c66c (table c011aac0, `CMPEQ 6`). The SETUP decoder
c01359e4 finds a record with c015c804 then c015c788(A4=&out, B4=recipient,
A6=wIndex) and calls its +12 callback (c0135a18..c0135a6c).

USB audio must add records for interface 2 (AudioControl) and 3
(AudioStreaming) whose callbacks see their own requests.

## Questions (report sections)
1. **What A4=6 means** in c015afa0/c015c66c (record type? class code?
   count?), and the full argument list of c015afa0 (A6, B6, A8, B8, B10 are
   also read at c015afb4..c015afc8).
2. **The table(s).** c011aac0 and neighbours (c011aa4c, c011aa18): layout,
   entry size, how many entries, what fills them.
3. **The lookup.** c015c804 and c015c788: how (recipient, wIndex) selects a
   record. Is the key the bInterfaceNumber, taken from the configuration
   descriptor, or a fixed slot? Truth table for recipient 1/2/3.
4. **The other record words.** What +0/+4/+8/+16 are called for (grep
   callers / indirect calls through the record), so an IF2/IF3 record can
   supply safe stubs.
5. **Recipe for USB audio.** Exactly what to call (and from where: task
   context, before POWER.SOFTCONN per recon/21 3.2) to register IF2 and IF3
   records so that requests with wIndex 2 / 3 reach their callbacks; any
   table capacity limit that must be raised; any place that hard-codes
   interfaces 0/1.

Every claim: instruction address, short excerpt (≤ 8 lines), confidence
(confirmed / likely / guess). Predicated code: `[!B0] B X` / `[B0] B Y`
pairs take exactly one; an ADDKPC in delay slots makes a call; parallel
`[A0] .. || [!A0] ..` both read the OLD A0. A CALLP to c016e000 ends a
function. SPLOOPD ii=1 runs ILC+4 times.
