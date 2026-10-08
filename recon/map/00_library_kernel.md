# 00: runtime-library and kernel functions (wave 0)

Scope: the 80 most-called functions named in the wave-0 brief, plus every
function coverage.py detected in c0169f20..c016f780 (fact sheets chunk_17
and chunk_18: the tail of the code section, c016f7a0 being the last
detected function start in the whole firmware). Union: 285 distinct
addresses, listed below in address order per FWMAP.md's table format.

Summary: this range is **not** purely compiler-runtime/kernel code as the
brief's own wording hinted it might be -- it is a mix of:
- the TI C6000 runtime-support primitives it's named for: integer divide
  (`c0168580` unsigned, `c01675c0` signed), float divide (`c016c240`),
  word-granularity memcpy (`c016d4c0`), memset (`c0167b00`, outside the
  range but a top target), and the universal register save/restore
  helpers `c016e020`/`c016e000` (865/853 callers -- by far the most-called
  functions in the whole firmware);
- a small number of genuine SYS/BIOS-style kernel primitives: a
  semaphore pend/post pair (`c0150b20`/`c01628e0`, confirmed this wave by
  reading `c01628e0`'s DINT-guarded count increment) and a raw CSR
  get/set pair (`c016e4c0`/`c016e4e0`) that looks like the mechanic behind
  Hwi_disable/Hwi_restore;
- a large population of tiny, mechanically unambiguous **accessors**:
  getters/setters for single B14 global slots, getters for fixed global
  words/pointers, and struct-field getters off an argument pointer;
- a large population of **tail-call veneers and "preload a constant then
  jump to a shared handler" trampolines** -- in particular, families that
  all jump into `c016ba40` (inside `c016b9c0`), `c0166a80` and `c015a520`
  with a different preloaded pointer each time. These look like
  per-item wrappers for a settings/menu table (FWMAP.md documents a
  settings-menu table around c0182b38) or similar per-slot UI records,
  **not** kernel code -- flagged here so later helpers don't mistake the
  bulk of chunk_17/18 for RTOS internals;
- `c016ec20`, the last detected function start in the firmware (2912
  bytes, running to c016f7a0, just past our range), is itself **not one
  routine**: it is a run of small long-branch veneers that coverage.py's
  stub-folding did not separate into individual functions (recon/15,16,18
  had already traced several of the addresses inside it: c016ef60 ->
  1180a954, c016f1a0/b0/d0 -> 118094xx, c016f450/460/4c0/4d0, c016f740).
  Treat addresses inside it as veneers, not as one meaningful function.
- coverage.py's caller counts mix real CALLP call sites, plain-branch
  tail-calls, and (for a handful of addresses) internal shared-epilogue
  fan-in; `c012daac`, `c0127f58`, `c0139490` and `118037d6` have large
  "caller" counts but are shared tails/epilogues reached only by branch
  or by appearing as filler entries in function-pointer tables, not real
  independently-called library routines. Checked via a refkind pass
  (CALLP vs branch vs `.word` reference counts) before trusting any
  caller count in this report.

Method: a scripted pass (`build/fwmap0/*.py`) pulled per-function size,
callers, callees, strings, B14 slots and roots from the existing fact
sheets, then classified each address by structural shape (B14
getter/setter, constant-return leaf, address-constant getter, tail-call
veneer, MVC/CSR pair, double-word multiply, SPLOOP copy, divide shape).
Every "confirmed" row below was checked by reading the actual
disassembly; "likely" rows combine a clear structural shape with
supporting call-graph/string evidence but were not traced instruction by
instruction; "guess" rows are honest placeholders (mostly small
application-level wrappers in the chunk_17/18 sweep) with whatever
callee/string/B14 evidence was available, per SAVE_PROTOCOL's "a short
honest guess beats a wrong confirmed."

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| 118037d6 | epilogue_pop_b3_shared3 | same shared-tail pattern as c012daac/c0127f58: pop B3 and return, reached by 11 branches + 6 table refs, 0 CALLP | likely | refkind: callp=0,branch=11,word=6; LDW *++B15[2],B3; BNOP B3,5 |
| 11805420 | orchestrator_1180_region2 | 1180-region orchestrator, same 1180bd10 save-helper entry, calls 1180673c,11809420,11809438 plus c016e000 | guess | calls=1180673c,11809420,11809438,c016e000; entry CALLP 0x1180bd10,A3; 7 callers |
| 11805878 | audio_or_ui_handler_1180 | large (228 instr) 1180-region routine calling 11805420, 11805484, 11805630 and the Hwi-guarded divide wrapper c016b540 -- likely an audio or UI event handler; not traced in detail | guess | n=228; calls=11805420,11805484,11805630,c016b540; 15 callers |
| 11805d20 | orchestrator_1180_region3 | 1180-region orchestrator (1180bd10 save-helper entry) calling the table-index helper c0140320 plus c016e000/c016e020 -- not traced further | guess | calls=c0140320,c016e000,c016e020; entry CALLP 0x1180bd10,A3; 37 callers |
| 11805d84 | bound_check_lt4 | predicate: tests whether A4 < 4 and branches accordingly -- an index/range validation (clamp to 4 items, e.g. 4 knobs) | likely | 11805d84 CMPLT.L1 4,A4,A0; [A0] BNOP 0x11805d98,5; 15 callers |
| 11805fb0 | validated_table_lookup | orchestrator: calls the bound-check predicate 11805d84, the 1180-region routine 11805d20, and the table-index helper c0140320 -- a validated table lookup (clamp index, then fetch) | likely | calls=11805d20,11805d84,c0140320,c016e000; 12 callers |
| 118093c0 | sign_test_predicate | predicate comparing A4/B4 (MV then CMPGT 0,A1,A0) -- a positivity/sign test on an argument pair | guess | 118093c0 MV.L2 B4,B0; MV.L1 A4,A1; CMPGT.L1 0,A1,A0; 18 callers |
| 1180a2a8 | audio_gain_ramp_div | part of the zero-target gain-ramp path recon/16 already identified (via 1180a220); calls the fp32-divide helper c016c240, consistent with a ramp-rate = delta/steps computation | likely | recon/16: '1180a4c4 (zero-target gain ramp through 1180a2a8/1180a220)'; calls=1180a220,c016c240,c016e000,c016e020; 20 callers |
| 1180ad68 | orchestrator_1180_region | 1180-region orchestrator entered via the L2 save helper 1180bd10 (the 1180-region analogue of c016e020), calls 11809718 then c016e000/c016e020 (c0-region helpers) -- bridges regions like c016df00 | guess | calls=11809718,c016e000,c016e020; entry CALLP 0x1180bd10,A3; 18 callers |
| 1180b020 | ui_event_post_byte | posts a UI event: stores A4 as a byte on the stack, reads the handle from B14[172], tail-calls the Mailbox veneer 1180b6f0 which resolves to c0166780 (Mailbox_post) -- matches recon/15's rotary-knob event-posting trace exactly | confirmed | recon/15: 'posts event 25+i through c016ef70 -> 1180b000 -> c0166780'; c0166780 already identified as Mailbox_post; b14=172; calls=c0166780; 18 callers |
| c011c508 | gfx_set_bit_range | sets/ORs a run of bits into a bitmap row: computes row base A21<<9 then CALLP 0xc011adc0, does round-to-byte arithmetic (SHR/SHRU by 3) and an SPLOOP that ORs a shifted bit mask into successive bytes via STB | likely | c011c522 SHL A0,0x9,A0 (row*512); c011c524 CALLP 0xc011adc0,B3; c011c572 MVK 1,A3; c011c574 SPLOOP 2; c011c57a OR A2,A0,A0; c011c582 STB A0,*A4[0]; 77 callers, highest of any non-kernel target -- a shared UI/LCD draw primitive, not a kernel routine |
| c011cb64 | orchestrator_c011c990 | orchestrator: enters via c016e020, calls c011c990 then does cleanup via c016e000 -- not traced into c011c990 itself this wave | guess | calls=c011c990,c016e000,c016e020; 17 callers |
| c011d4d8 | unk_d4d8 | 68-instruction MVC-flagged routine, only direct call c011d390; not traced in detail this wave | guess | n=68; calls=c011d390; 13 callers |
| c011d84c | orchestrator_c011b848 | orchestrator entered via c016e020, calls c011b848, c011bbc4, c011c22c plus c016e000 -- a multi-step subsystem routine, not traced in detail | guess | calls=c011b848,c011bbc4,c011c22c,c016e000; 6 callers |
| c011d938 | big_subsystem_2 | very large (335 instr) MVC-flagged routine whose only direct call is c011d8f0 -- a major subsystem routine, not traced in detail given size | guess | n=335; calls=c011d8f0; 16 callers |
| c011f87c | wrapper_c011f7f4 | wrapper computing an index into the 0x11800000 region (SHL A4,0x9) before calling c011f7f4 | guess | c011f87c MVK 0x0000,B0; MVKH 0x11800000,B0; SHL A4,0x9,A0; calls c011f7f4; 7 callers |
| c011f8d8 | big_mvc_subsystem | 114-instruction MVC-flagged routine calling c011c704, c011c788 and c011eef0 -- a sizeable subsystem routine, not traced in detail | guess | n=114; calls=c011c704,c011c788,c011eef0; 26 callers |
| c0123a74 | thin_arg_adapter | thin adapter: CALLP's c0123824 then shuffles return/argument registers (A10->A4, A11->B4) before calling c0123b18 -- reorders arguments between two calls | likely | c0123a74 CALLP 0xc0123824,B3; MV A10,A4; MV.L2X A11,B4; calls c0123824,c0123b18; 1 caller |
| c0126c90 | orchestrator_c0126624 | orchestrator entered via c016e020, calls c0126624, c01268e0, c01269d4 plus c016e000 | guess | calls=c0126624,c01268e0,c01269d4,c016e000; 3 callers |
| c01274cc | midi_tx_locked | already-confirmed MIDI/serial send wrapper (recon/15,17-19): saves args, takes the outer lock B14[161] via c0150b20 (timeout -1), calls the transport c0144dc8, releases via c01628e0 | confirmed | recon/15,17,18,19: c01274d4 CALLP c0150b20 with B14[161]; c01274e4 CALLP c0144dc8; c01274f0 CALLP c01628e0 |
