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
| c0127500 | midi_tx_n | wraps c01274cc, adding a byte-count/length argument (MVK 0x1880,B4 is a buffer base, not the count) -- a send-N-bytes layer over the single locked sender | likely | c0127500 MV A4,A1; MVK 0x1880,B4; calls c01274cc; 9 callers |
| c0127f58 | epilogue_pop_b3_shared2 | same pattern as c012daac: pop B3, return; reached by 32 branches + 29 table-pointer refs, 0 CALLP. Confirmed in context as the shared tail of a switch-like block at c0127f40-c0127f54 whose case arms all branch into it | confirmed | c0127f46 and c0127f50 BNOP.S1 0xc0127f58,5 (two case arms observed directly in the preceding 24 bytes); refkind callp=0, branch=32, word=29 |
| c01282d4 | error_guarded_call | reads B14[45] then calls c016bf50 -- a flag-guarded call, same family as the other b14-keyed error/status wrappers (c01630b4, c0163118) | guess | b14=45; calls=c016bf50; 3 callers |
| c0128580 | midi_tx_byte | thin single-byte wrapper: stores A4 as a byte on the stack and forwards it to the UART/MIDI transport c0144dc8 (the same transport used by the locked sender c01274cc) | likely | c0128580 STB A4,*+B15[4]; CALLP 0xc0144dc8,B3; 4 callers |
| c0129630 | cfg_get_b14_26 | getter: return B14[26] | confirmed | c0129630 LDW *+B14[26],A4; BNOP B3,5; refkind callp=23 (real calls, not epilogue-fold) |
| c012af98 | rts_const_return_1 | leaf stub, unconditionally returns constant 1 (A4=1); 35 real CALLP callers, confirmed not a shared-epilogue artifact | confirmed | c012af98 MVK.L1 1,A4; BNOP B3,5 -- refkind: callp=35, branch=0, word=0 (genuinely called, not a tail-merge target) |
| c012afe0 | usb_desc_table_get | indexes a 36-byte-record table at 0xc0064404 by A1 (arg1), reads field 0 (a base pointer), then adds B0*56 (arg2 scaled) -- the same 0xc0064xxx region recon/20 already ties to USB class-descriptor/alt-setting response buffers | likely | c012afe4 MVK 0x4404,A2; c012aff0 MVKH 0xc0060000,A2 -> base 0xc0064404; c012aff8/c012affa SHL B0,3 / SHL B0,6 -> effectively B0*56; recon/20 notes A4=0xc00643fc is the response buffer, 8 bytes from this base |
| c012c934 | field_extract_bit25 | extracts a packed bit/byte field: EXTU.S1 A0,25,25,A1 on the incoming A4 -- single-bit or short-field accessor from a packed status/event word | likely | c012c934 MV.L1 A4,A0; EXTU.S1 A0,25,25,A1; 13 callers |
| c012ca24 | midi_compose_send | composer: calls c01274cc (MIDI tx), c0129638, and the bit-extract helper c012c934 -- builds and sends a MIDI-like message from a packed field | likely | calls=c01274cc,c0129638,c012c934,c016e000; 11 callers |
| c012ca80 | magic_const_check | compares an incoming value against the fixed constant 0xffffd759 (-10151) -- a sentinel/magic-number validation; exact meaning of the constant not established | guess | c012ca80 MVK.S1 0xffffd759,A0; CMPEQ.L1 A1,A0,A0; 11 callers |
| c012daac | epilogue_pop_b3_shared | shared tail: pops B3 off the stack and returns; reached only by BNOP branch (22x) and as a function-pointer table filler (27x .word refs), never by CALLP -- an internal exit point of enclosing function(s), not an independently called routine | likely | refkind: callp=0, branch=22, word=27; body is only LDW *++B15[2],B3; BNOP B3,5 |
| c012ee10 | orchestrator_midi_compose | orchestrator entered via c016e020; calls c012ece0,c012ed0c,c012ed44 plus the fixed-multiply helper c0130d74 and c01274cc (MIDI tx) -- likely composes and sends a scaled MIDI value | likely | calls=c012ece0,c012ed0c,c012ed44,c0130d74 (+c01274cc per earlier overview); 23 callers |
| c0130d28 | fixed_scale_mul_84_div | sibling of c0130d74: same 0x54 multiply plus an extra constant 0x159c, consistent with a combined multiply-then-scale (e.g. percent-to-gain-then-clamp) helper | likely | c0130d28 MVK.S1 0x0054,A0; MPYLI.M1 A0,A4,A7:A6; MVK.S2 0x159c,B0; 17 callers |
| c0130d74 | fixed_scale_mul_84 | 32x32->64 fixed-point multiply by the constant 0x54 (84 decimal): MVK 0x54,A0; MPYLI A0,A4,A7:A6 -- a scale/convert helper, exact use (e.g. percent-to-internal-gain) not established | likely | c0130d74 MVK.S1 0x0054,A0; MPYLI.M1 A0,A4,A7:A6; 14 callers |
| c01349ec | thin_orchestrator_veneers | tiny (6 instr) orchestrator calling two of the trailing veneer-blob targets (c016f3f0, c016f3e0) plus c0156c94 and c016e000 -- a thin dispatcher, not traced further | guess | calls=c016f3f0,c016f3e0,c0156c94,c016e000; 6 callers |
| c0139490 | epilogue_return_a3 | epilogue variant: copies A3 into the return register A4, then pops B3 and returns -- i.e. 'return whatever the caller already computed into A3', a shared-tail with a value in flight | likely | c0139490 MV.L1 A3,A4; LDW *++B15[2],B3; BNOP B3,5; 5 callers |
| c013a2d8 | wrapper_c011d4d8 | wrapper that forwards into the large routine c011d4d8 -- not traced further | guess | calls=c011d4d8; 17 callers |
| c013b590 | event_dispatch_108_109 | dispatcher reading B14[108]/[109] (the same slots c016a770's event-record copier uses per recon/15) plus B14[139]; calls 1180af34, c013b2a0, c013b2e8 and the big init routine c0155ac0 | likely | b14=108,109,139; calls=1180af34,c013b2a0,c013b2e8,c0155ac0; recon/15 ties b14=108/109 to the event-record dispatch area; 17 callers |
| c013dd2c | orchestrator_dca0_dce0 | orchestrator entered via c016e020, calls c013dca0 and c013dce0 plus c016e000 -- not traced further | guess | n=89; calls=c013dca0,c013dce0,c016e000,c016e020; 20 callers |
| c0140258 | cfg_get_global_1181191c | getter for a fixed global word at 0x1181191c, returns it directly | confirmed | c0140258 MVK 0x191c,A4; MVKH 0x11810000,A4 -> 0x1181191c; LDHU *A4[0],A4; 23 callers |
| c0140320 | cfg_table_index_1181191c | computes an index into a word table based at 0x11811900 (A4<<2) and calls the getter c0140258 -- a generic table[index] accessor | likely | c0140320 MVK 0x1900,A5; SHL A4,0x2,A4; MVKH 0x11810000,A5; calls c0140258; 21 callers |
| c0141f14 | buffer_clear_init | calls the memset primitive c0167b00 inside a c016e020/CALLP-entered frame -- a buffer-init/clear routine | likely | calls=c0167b00,c016e020; 10 callers |
| c01453b4 | unk_453b4 | 107-instruction routine calling 118029e0, 1180b040, c01451a0 and c0145220; b14=149 -- not traced in detail this wave | guess | n=107; b14=149; calls=118029e0,1180b040,c01451a0,c0145220; 5 callers |
| c0146ee0 | fixed_point_math_big | very large (391 instr) double-register-pair ('DP') math routine using the 32x32->64 multiply helper c016d3c0 and c016d480 -- likely a filter-coefficient or gain computation; not traced in detail given size | guess | n=391; calls=c016d3c0,c016d480; 11 callers |
| c014c350 | locked_small_op | entered via c016e020, reads B14[78] then calls c012c678 and releases via the post primitive c01628e0 -- a short do-X-under-lock wrapper, same shape as other lock/release pairs found this wave | likely | b14=78,138,175; calls=c012c678,c01628e0,c016e000,c016e020; 8 callers |
| c014ff44 | cfg_table_ptr_11f03ad0 | computes a pointer into a 16-byte-stride table based at 0x11f03ad0, indexed by A4 (SHL A4,0x4) -- likely a per-slot (5 effect slots?) record accessor | likely | c014ff44 MVK 0x3ad0,B0; MVKH 0x11f00000,B0; SHL A4,0x4,A0; ADDAW A0,A4,A0 -- note: recon/16 flagged a nearby constant 11f039b0 as unrelated audio-buffer address; 28 callers |
| c01502cc | cfg_get_ptr_11f03b48 | returns the fixed pointer constant 0x11f03b48 (no load, just the address) -- a base-pointer getter into the 0x11f0xxxx data/sample region | confirmed | c01502cc MVK 0x3b48,A4; MVKH 0x11f00000,A4; BNOP B3,5; 15 callers |
| c0150b20 | bios_sem_pend | Semaphore_pend-equivalent: blocking wait on a handle taken from a B14 slot, with a timeout last-arg (-1 = forever); extensively confirmed by recon/17-19 lock-order traces | confirmed | recon/17-19: c01274d4 CALLP c0150b20 with B14[161], timeout -1; c014a096 MVK -1,B4; CALLP c0150b20 with B14[89]; 163 CALLP refs |
| c01529c0 | big_dispatcher | very large (262 instr) MVC-flagged routine saving many registers; its only direct call is c016b7c0 -- a sizeable switch/dispatch-like routine, not traced in detail | guess | n=262; calls=c016b7c0; 11 callers |
| c01537a8 | mainapp_event_dispatch | dispatcher keyed off B14[138], calling 1180b000, c01324b4, c01534a0 and c0155360 -- ties into the MainApp event-queue machinery recon/19 already traced (c0153554/c01535ce area); likely posts/dispatches one MainApp event | likely | b14=138; calls=1180b000,c01324b4,c01534a0,c0155360; recon/19 traces sibling addresses c0153554,c01535ce in the same dispatcher family; 20 callers |
| c0155328 | cfg_ptr_11810000_325c | computes a pointer into the 0x1181325c area offset by an incoming index A1 -- a table/record accessor into the same 1181xxxx region used by c0140258/c0140320 | guess | c0155328 MV A4,A1; MVK 0x325c,A4; MVKH 0x11810000,A4; 13 callers |
| c0155ac0 | big_subsystem_init | very large (439 instr) routine saving many callee-saved registers, MVC-flagged; calls c0162be0, the memset helper c0167f60(sic, close to c0167b00), c016a380 and c016b640 -- likely a major subsystem setup/init routine; not traced in detail given size | guess | n=439; calls=c0162be0,c0167f60,c016a380,c016b640; 21 callers |
| c0156d68 | bridge_status_struct | bridges regions: entered via the c0 save helper c016e020 but calls the 1180-region routine 1180ace8 as well as c014002c, and also touches the 0xc011ad70-ad8c status struct group (same family as c0156e80/c016ac1c/c016ac28) | guess | calls=11805d20,1180ace8,c014002c,c016e020; touches 0xffffad8c constant; 22 callers |
| c0156e80 | cfg_get_global_c011ad8c | getter: returns the word at fixed global 0xc011ad8c (part of a small status struct also touched by c016ac1c/c016ac28/c0156d68 at nearby offsets ad70/ad75/ad7a/ad8c) | confirmed | c0156e80 MVK 0xffffad8c,A4; MVKH 0xc0110000,A4 -> 0xc011ad8c; LDW *A4[0],A4; BNOP B3,5; 30 callers |
| c0158980 | locked_lookup_big | very large (191 instr) MVC-flagged routine calling c0164380, c0166580, c016a240 and c016b7c0 -- shares 3 of its 4 callees with c0150b20's own body, suggesting a related lock/lookup operation; not traced in detail | guess | n=191; calls=c0164380,c0166580,c016a240,c016b7c0; 34 callers |
| c015c0f8 | orchestrator_locked_small | small (9 instr visible) orchestrator entered via c016e020, calling 1180af34 and c0161c30 plus the restore helper c016e000 | guess | calls=1180af34,c0161c30,c016e000,c016e020; 29 callers |
| c015c164 | effect_slot_lookup | calls 1180ad68, the pend primitive c0150b20, c01541cc and c0158cf4; references the string 'OFF' and B14[155] -- likely an effect-slot state query/toggle | guess | b14=155; strings=OFF; calls=1180ad68,c0150b20,c01541cc,c0158cf4; 22 callers |
| c0161200 | cfg_locked_dispatch | reads several fixed global pointers/flags (approx 0xc017d8f4, 0xc017d3f4, 0xc017d974, 0xc0181f74) and eventually calls the semaphore-pend primitive c0150b20 and a CSR/DINT-guarded routine c016d840 -- a state/mode check combined with a locked operation; not traced past the opening dispatch | guess | c0161200 reads 3 distinct 0xc017xxxx globals and an A10/A11 handle before any call; fact sheet calls=c0150b20,c016d840; 42 callers |
| c01628e0 | bios_sem_post | Semaphore_post-equivalent: resolves object via B14 handle+table, disables interrupts (MVC CSR,B11; DINT) around incrementing the count field *A3[0], restores CSR, returns | confirmed | c01629b8 MVC CSR,B11; c01629c0 DINT; c01629bc ADD A3,A10,A3; c01629c4 LDW *+A3[0],A4 -- mirrors c0150b20 object resolution; 170 CALLP refs; prior recon/17-19 note said likely post/unlock |
| c01630b4 | validate_and_set_error | reads B14[115] then, on failure, calls err_set_last_code (c016be80) and c0143900 -- a condition check that records an error code | likely | b14=115; calls=c0143900,c016be80; 19 callers |
| c0163118 | locked_subsystem_op_115 | large-frame (57 instr, ADDK -48,B15) routine sharing B14[115] with c01630b4 above; calls 11805c54, c0143f60, c0155290, c0169700 -- likely the operation that c01630b4's error path guards | guess | b14=115; calls=11805c54,c0143f60,c0155290,c0169700; entry via c016e020; 17 callers |
| c0163324 | field_extract_u8 | reads a non-word-aligned word (LDNW) at *A4[0] then extracts an 8-bit field at bit offset 16 (EXTU A0,16,24,A1) -- a packed-struct byte-field accessor | likely | c0163324 LDNW.D1T1 *A4[0],A0; EXTU.S1 A0,16,24,A1; 9 callers |
| c0166194 | rhythm_get_field117 | reads table[A4] from base 0xc0182730 (FWMAP.md's documented rhythm-patterns table) then returns byte field +117 of that record; a second entry at c01661ac (same base, pointer-only) and a third at c01661b8 (field +118, with further dispatch) are folded into the same span | confirmed | c0166194 MVK 0x2730,A5; MVKH 0xc0180000,A5 -> 0xc0182730; c01661a0 LDW *A5[A4],A4; c01661a2 MVK 117,A5; c01661a6 LDBU *A4[A5],A4 -- matches FWMAP.md's documented table address exactly |
| c01675c0 | rts_sdiv32 | signed 32-bit integer divide/remainder helper: negates operands per sign (NEG.S2/NEG.L1), NORM+SUBC restoring-division loop (shared label c016764c), re-applies sign at the end -- the signed sibling of c0168580 | confirmed | c01675c0 NEG.S2 B4,B5; c01675f8/c0167600 conditional NEG.L1/NEG.S2 on sign bits; c016764c SUBC.L1X A4,B4,A4 loop; 23 CALLP callers, 0 branch/word refs (always called at a distance via a veneer) |
| c0167b00 | rts_memset | fill A6 bytes at A4 with byte B4 (loop variant, not SPLOOP) | confirmed | recon/16,20 already confirmed: callers pass (ptr,0,size); entry MV A4,A18; 127 CALLP refs |
| c0168580 | rts_udiv32 | unsigned 32-bit integer divide/remainder helper: LMBD normalization of both operands, then an iterative SUBC restoring-division loop (label c0168600), returns via B B3 -- matches the brief's __c6xabi_divu/remi shape | confirmed | c0168580 LMBD.L2X 1,A4,B1; c0168584 LMBD.L1X 1,B4,A1; c01685ec..c0168610 SUBC.L1X A4,B4,A4 loop then B B3; 43 CALLP callers including c016b540 |
| c0169980 | rts_div32_variant | see entry above (duplicate address appears in both the target list and the kernel-range sweep) | likely | see c0169980 above |
| c0169f20 | wrapper_c0169f20 | generic routine (calls c0167f60,c016db80) | guess | c0169f20: n=40; 2 callers; first op STW.D2T1 A11,*B15--[14] |
| c0169fc0 | diag_mask_test | tests bits 0 and 1 of a flags word (A6) at entry; called from every task/ISR root in coverage.tsv (AD, BatteryManagement, DataStore, Hwi:EDMA-RX, LooperUI, MIDI, MainApp, PopUpTimeCounter, PreLoad, QFuncService, RepeatEventHandler, RhythmService, Swi:USB, SwitchNrmlSpdRead, TunerService, UpdateUI, UsbTask-worker) -- that universality plus the Log_*/Diags strings found nearby in rodata (c0172a8f Diags, c0172a2b LM_begin...) suggests this gates an instrumented Log_write-style call (an XDC Diags-mask test), not application logic | likely | c0169fc0 AND.D1 1,A6,A0 // AND.S1 2,A6,A1; 65 CALLP callers spanning literally every root in coverage.tsv |
| c016a060 | wrapper_c016a060 | generic leaf routine, no further structure identified | guess | c016a060: n=49; 4 callers; first op MVK.S1 0x03fe,A6 |
| c016a100 | fmt_render_wrapper2 | same shape and callee as c016c360 (forwards to c014fa40); a sibling formatter wrapper used from a different call site/UI context | likely | first ops: MV.L1X B15,A15; STW A15,*B15--[8]; calls c014fa40; 12 callers |
| c016a1a0 | wrapper_c016a1a0 | generic leaf routine, no further structure identified | guess | c016a1a0: n=48; 0 callers; first op STW.D2T2 B10,*B15--[2] |
| c016a240 | wrapper_c016a240 | generic routine (calls c015a520) | guess | c016a240: n=40; 3 callers; first op STW.D2T2 B13,*B15--[2] |
| c016a2e0 | wrapper_c016a2e0 | generic routine (calls c0164240,c0168e80,c016e7c0) | guess | c016a2e0: n=40; 0 callers; first op STW.D2T2 B13,*B15--[2] |
| c016a380 | wrapper_c016a380 | generic routine (calls c015a520,c015a7a0) | guess | c016a380: n=91; 5 callers; first op STW.D2T2 B13,*B15--[2] |
| c016a4c0 | wrapper_c016a4c0 | generic routine (calls c0167b00) | guess | c016a4c0: n=47; 0 callers; first op STW.D2T2 B10,*B15--[2] |
| c016a560 | wrapper_c016a560 | generic routine (calls c016e980,c016e9a0) | guess | c016a560: n=141; 1 callers; first op STW.D2T1 A10,*B15--[2] |
| c016a740 | wrapper_c016a740 | generic routine (calls c0158ea0,c0158ea8) | guess | c016a740: n=7; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016a758 | wrapper_c016a758 | generic routine (calls 1180b020,c015908c) | guess | c016a758: n=8; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016a770 | wrapper_c016a770 | generic routine (calls c0139738,c0139a70,c0139b88; B14[108 109 ]) | guess | c016a770: n=20; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016a7c0 | wrapper_c016a7c0 | generic routine (calls 11800400,11800424) | guess | c016a7c0: n=52; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016a840 | wrapper_c016a840 | generic routine (calls 1180a954,c016e000,c016e020) | guess | c016a840: n=18; 1 callers; first op CALLP.S1 0xc016e020,A3 |
| c016a87c | wrapper_c016a87c | generic routine (calls c015c94c,c015c9a0) | guess | c016a87c: n=17; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016a8c0 | wrapper_c016a8c0 | generic routine (calls 11805e8c) | guess | c016a8c0: n=12; 2 callers; first op STW.D2T2 B3,*B15--[2] |
| c016a8e0 | wrapper_c016a8e0 | generic leaf routine, no further structure identified | guess | c016a8e0: n=17; 2 callers; first op MV.L1 A4,A5 |
| c016a914 | wrapper_c016a914 | generic routine (calls c0150b20,c0160e74,c01628e0; B14[155 ]) | guess | c016a914: n=17; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016a94c | wrapper_c016a94c | generic routine (calls c012fb00,c0154564; string 'OUTPUT ') | guess | c016a94c: n=32; 0 callers; first op STW.D2T2 B3,*B15--[2] |
| c016a9ac | ptr_const_c0183740 | returns the fixed pointer constant 0xc0183740 (no load) | confirmed | c016a9ac: MVK/MVKH -> 0xc0183740; BNOP; 1 callers |
| c016a9c0 | wrapper_c016a9c0 | generic routine (calls c0152240) | guess | c016a9c0: n=17; 1 callers; first op STW.D2T2 B3,*B15--[4] |
| c016a9f0 | wrapper_c016a9f0 | generic routine (calls c015232c) | guess | c016a9f0: n=25; 1 callers; first op STW.D2T2 B3,*B15--[4] |
| c016aa40 | wrapper_c016aa40 | generic routine (calls c011cb64,c0140320,c01563a0) | guess | c016aa40: n=21; 1 callers; first op CALLP.S1 0xc016e020,A3 |
| c016aa88 | wrapper_c016aa88 | generic routine (calls 1180710c,c0126ff8,c0144580; B14[165 ]) | guess | c016aa88: n=56; 2 callers; first op STW.D2T2 B3,*B15--[2] |
| c016ab40 | wrapper_c016ab40 | generic routine (calls c0159620,c015af0c,c016e000) | guess | c016ab40: n=7; 1 callers; first op CALLP.S1 0xc016e020,A3 |
| c016ab58 | wrapper_c016ab58 | generic routine (calls c015af00,c016ab40; B14[24 ]) | guess | c016ab58: n=8; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016ab70 | wrapper_c016ab70 | generic routine (calls c0159758,c015af18) | guess | c016ab70: n=9; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016ab8c | wrapper_c016ab8c | generic routine (calls c015b114,c016ab70; B14[24 ]) | guess | c016ab8c: n=14; 2 callers; first op STW.D2T2 B3,*B15--[2] |
| c016abc0 | wrapper_c016abc0 | generic routine (calls c01454f4,c0167b00,c016e000) | guess | c016abc0: n=26; 1 callers; first op CALLP.S1 0xc016e020,A3 |
| c016ac1c | ptr_const_c011ad75 | returns the fixed pointer constant 0xc011ad75 (no load) | confirmed | c016ac1c: MVK/MVKH -> 0xc011ad75; BNOP; 2 callers |
| c016ac28 | ptr_const_c011ad7a | returns the fixed pointer constant 0xc011ad7a (no load) | confirmed | c016ac28: MVK/MVKH -> 0xc011ad7a; BNOP; 4 callers |
| c016ac34 | wrapper_c016ac34 | generic routine (calls c0169f20) | guess | c016ac34: n=43; 2 callers; first op MVK.S1 0xffffad70,A4 |
| c016acc0 | tailcall_wrapper_c016ad20_c016acc0 | small wrapper that tail-calls c016ad20 after a short setup | likely | c016acc0: ...; B 0xc016ad20; 4 callers |
| c016ad40 | wrapper_c016ad40 | generic leaf routine, no further structure identified | guess | c016ad40: n=36; 1 callers; first op MV.L1 A4,A3 |
| c016adc0 | wrapper_c016adc0 | generic routine (calls c0169fc0) | guess | c016adc0: n=76; 2 callers; first op MVK.L1 0,A3 |
| c016aec0 | wrapper_c016aec0 | generic leaf routine, no further structure identified | guess | c016aec0: n=34; 1 callers; first op STW.D2T2 B3,*B15--[12] |
| c016af40 | wrapper_c016af40 | generic routine (calls 1180b060,c0167b00,c0169fc0) | guess | c016af40: n=68; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016b040 | wrapper_c016b040 | generic routine (calls c016e0c0,c016e2a0,c016e840) | guess | c016b040: n=74; 5 callers; first op MVK.S2 0x5140,B4 |
| c016b140 | wrapper_c016b140 | generic routine (calls c016d5c0) | guess | c016b140: n=40; 2 callers; first op STW.D2T2 B3,*B15--[2] |
| c016b1c0 | wrapper_c016b1c0 | generic routine (calls c0169ca0) | guess | c016b1c0: n=106; 1 callers; first op MVC.S2 CSR,B4 |
| c016b340 | wrapper_c016b340 | generic routine (calls c015a520) | guess | c016b340: n=32; 0 callers; first op MV.L1X B4,A6 |
| c016b3c0 | wrapper_c016b3c0 | generic routine (calls c015a520) | guess | c016b3c0: n=32; 0 callers; first op MV.L1X B4,A6 |
| c016b440 | wrapper_c016b440 | generic routine (calls c015a520) | guess | c016b440: n=32; 1 callers; first op MV.L1X B4,A6 |
| c016b4c0 | wrapper_c016b4c0 | generic routine (calls c016d8c0) | guess | c016b4c0: n=35; 0 callers; first op STW.D2T1 A10,*B15--[2] |
| c016b540 | hwi_guarded_divide_update | Hwi-protected (MVC CSR,B11; DINT ... MVC B11,CSR) update: reads struct fields at handle+6/+2/+0/+5, calls the unsigned-divide helper c0168580 on two of them -- likely a running-rate/average update guarded against preemption | likely | c016b56c MVC CSR,B11; c016b570 DINT; c016b598 CALLP 0xc0168580,B3; c016b5a8 MVC B11,CSR; 28 callers |
| c016b5c0 | wrapper_c016b5c0 | generic routine (calls c015a520) | guess | c016b5c0: n=32; 2 callers; first op MV.L1X B4,A6 |
| c016b640 | wrapper_c016b640 | generic routine (calls c015a520) | guess | c016b640: n=32; 3 callers; first op MV.L1X B4,A6 |
| c016b6c0 | wrapper_c016b6c0 | generic routine (calls c016b7c0) | guess | c016b6c0: n=33; 3 callers; first op STW.D2T2 B3,*B15--[2] |
| c016b740 | wrapper_c016b740 | generic routine (calls c016b7c0) | guess | c016b740: n=33; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016b7c0 | unk_b7c0 | 140-instruction routine, prologue 'STW A10,*B15--[2]; STW B3,*B15[1]', only external call c0163c00 -- not traced in detail this wave despite 11 callers and being called by both c016b540's sibling wrappers (c016b6c0/c016b740) and c01529c0 | guess | n=140; calls=c0163c00; 11 callers; called by c016b6c0,c016b740,c01529c0,c016b9c0 |
| c016b9c0 | wrapper_c016b9c0 | generic routine (calls c0169fc0) | guess | c016b9c0: n=111; 4 callers; first op STW.D2T1 A10,*B15--[2] |
| c016bb40 | wrapper_c016bb40 | generic leaf routine, no further structure identified | guess | c016bb40: n=32; 0 callers; first op MV.L1X B4,A0 |
| c016bbc0 | wrapper_c016bbc0 | generic routine (calls c016bd40,c016cf00,c016e980; string '%.*s ') | guess | c016bbc0: n=113; 1 callers; first op STW.D2T1 A11,*B15--[2] |
| c016bd40 | wrapper_c016bd40 | generic routine (calls c016ec00) | guess | c016bd40: n=35; 4 callers; first op MV.L1X B15,A15 |
| c016bdc0 | wrapper_c016bdc0 | generic routine (calls c0167b00) | guess | c016bdc0: n=25; 1 callers; first op MVK.S1 0x0cfc,A3 |
| c016be20 | wrapper_c016be20 | generic routine (calls 11809224,c01295c8,c0129630) | guess | c016be20: n=20; 2 callers; first op CALLP.S1 0xc016e020,A3 |
| c016be58 | wrapper_c016be58 | generic routine (calls c016be20) | guess | c016be58: n=11; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016be80 | err_set_last_code | setter: B14[114] = A4 (records a small last status/error code); 48 CALLP callers including the heap allocator's out-of-block path | confirmed | c016be80 STW A4,*+B14[114]; BNOP B3,5 -- already identified in recon/18_round3.md |
| c016be88 | err_get_and_format | getter for B14[114] (pairs with c016be80) that goes on to build an error message, default string literal 'Unknown (Error ...)'; calls c016c360 (format helper) and uses c016e000/c016e020 save-restore, so it is a real 24-instruction function, not a 2-instruction leaf, despite sharing the getter's opening instruction | likely | fact sheet: b14=114, strings=Unknown (Error, calls c016c360,c016e000,c016e020; n=24 |
| c016bee0 | wrapper_c016bee0 | generic routine (calls 1180a350,c014fea0,c014ff58) | guess | c016bee0: n=24; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016bf40 | ptr_const_c018326c | returns the fixed pointer constant 0xc018326c (no load) | confirmed | c016bf40: MVK/MVKH -> 0xc018326c; BNOP; 2 callers |
| c016bf50 | wrapper_c016bf50 | generic routine (calls c0155ac0,c01628e0,c016bf40; B14[139 154 ]) | guess | c016bf50: n=11; 5 callers; first op STW.D2T2 B3,*B15--[2] |
| c016bf74 | struct_get_field_0_c016bf74 | getter: returns field +0 of the struct pointed to by arg A4 | confirmed | c016bf74: LDW.D1T1 *+A4[0],A4; 1 callers |
| c016bfa0 | wrapper_c016bfa0 | generic routine (calls c0167b00,c016e000,c016e020) | guess | c016bfa0: n=32; 1 callers; first op CALLP.S1 0xc016e020,A3 |
| c016bff0 | ptr_const_118130a0 | returns the fixed pointer constant 0x118130a0 (no load) | confirmed | c016bff0: MVK/MVKH -> 0x118130a0; BNOP; 9 callers |
| c016c000 | rts_const_return_0_c016c000 | leaf stub, returns constant 0 | confirmed | c016c000 MVK.L1 0,A4; BNOP; 1 callers |
| c016c004 | cfg_get_global_c0180d61 | getter: returns the word/field at fixed global 0xc0180d61 | likely | c016c004: MVK/MVKH -> 0xc0180d61; LDBU.D1T1 *A4[A5],A4; 1 callers |
| c016c024 | wrapper_c016c024 | generic routine (calls c016c004,c016df64,c016e000) | guess | c016c024: n=19; 1 callers; first op CALLP.S1 0xc016e020,A3 |
| c016c060 | wrapper_c016c060 | generic routine (calls 11805e64,11808c44,c0168580) | guess | c016c060: n=14; 1 callers; first op STW.D2T2 B3,*B15--[4] |
| c016c090 | wrapper_c016c090 | generic routine (calls 1180a448,c0127fe0,c0129630; B14[99 125 174 ]) | guess | c016c090: n=43; 2 callers; first op STW.D2T2 B3,*B15--[2] |
| c016c118 | cfg_get_b14_125 | getter: return B14[125] | confirmed | c016c118 LDW.D2T1 *+B14[125],A4; returns; 1 callers |
| c016c120 | wrapper_c016c120 | generic routine (calls 1180950c,c0155290,c015576c) | guess | c016c120: n=56; 1 callers; first op CALLP.S1 0xc016e020,A3 |
| c016c1e0 | wrapper_c016c1e0 | generic routine (calls c0167b00,c016d4c0) | guess | c016c1e0: n=26; 1 callers; first op MVK.S2 0x0004,B4 |
| c016c240 | rts_fp32_div_plus_strcopy | two unrelated routines merged into one coverage-detected span: (1) c016c240-c016c2fc is the single-precision float DIVIDE helper -- RCPSP reciprocal estimate plus two Newton-Raphson refinement passes (MPYSP/SUBSP), with a B-side entry at c016c240 and an A-side entry at c016c2a0; (2) c016c300 onward is an unrelated byte-copy-with-sentinel loop (LDB/STB loop comparing against A5). Only the divide half has the real external callers | confirmed | c016c240 RCPSP.S2 B4,B5; c016c248 MPYSP.M2 B4,B5,B6; c016c254/c016c270 SUBSP (Newton-Raphson refinement); matches the TI C6000 compiler fp32-divide shape exactly; c016c300 CMPLT 0,B6,B0 begins the unrelated copy loop |
| c016c360 | fmt_render_wrapper | sets up an A15 frame pointer, forwards to c014fa40 with fixed pointer constants (approx 0xc015d580, 0xc015e080) plus a stack-passed record/string pointer -- a thin formatter wrapper; used by the error-message builder c016be88 and by c016a100 | likely | c016c360 MV B15,A15; c016c368 LDW *+A15[1],A3; c016c38c CALLP 0xc014fa40,B3; 29 callers |
| c016c3c0 | wrapper_c016c3c0 | generic routine (calls c016e0c0) | guess | c016c3c0: n=52; 1 callers; first op STW.D2T2 B10,*B15--[2] |
| c016c480 | wrapper_c016c480 | generic leaf routine, no further structure identified | guess | c016c480: n=30; 1 callers; first op MVC.S2 CSR,B6 |
| c016c4e0 | wrapper_c016c4e0 | generic routine (calls c016d7c0) | guess | c016c4e0: n=27; 0 callers; first op STW.D2T2 B3,*B15--[2] |
| c016c540 | wrapper_c016c540 | generic routine (calls c0166a80) | guess | c016c540: n=24; 1 callers; first op MVK.S2 0x0dc0,B4 |
| c016c5a0 | wrapper_c016c5a0 | generic leaf routine, no further structure identified | guess | c016c5a0: n=27; 1 callers; first op MVK.S1 0x201c,A3 |
| c016c600 | wrapper_c016c600 | generic routine (calls c016b9c0) | guess | c016c600: n=24; 0 callers; first op STW.D2T1 A11,*B15--[2] |
| c016c660 | wrapper_c016c660 | generic routine (calls c0166a80) | guess | c016c660: n=24; 0 callers; first op STW.D2T1 A11,*B15--[2] |
| c016c6c0 | wrapper_c016c6c0 | generic routine (calls c016a380,c016b9c0) | guess | c016c6c0: n=51; 0 callers; first op STW.D2T1 A11,*B15--[2] |
| c016c780 | wrapper_c016c780 | generic routine (calls c0166a80) | guess | c016c780: n=24; 0 callers; first op MVK.S2 0x0e00,B4 |
| c016c7e0 | wrapper_c016c7e0 | generic routine (calls c015a7a0) | guess | c016c7e0: n=29; 0 callers; first op STW.D2T1 A10,*B15--[2] |
| c016c840 | wrapper_c016c840 | generic leaf routine, no further structure identified | guess | c016c840: n=30; 0 callers; first op SUB.L2 B15,0x8,B15 |
| c016c8a0 | wrapper_c016c8a0 | generic routine (calls c016b9c0) | guess | c016c8a0: n=24; 0 callers; first op STW.D2T1 A11,*B15--[2] |
| c016c900 | wrapper_c016c900 | generic routine (calls c0166a80) | guess | c016c900: n=24; 1 callers; first op STW.D2T1 A11,*B15--[2] |
| c016c960 | wrapper_c016c960 | generic routine (calls c0162be0,c0166a80) | guess | c016c960: n=55; 2 callers; first op STW.D2T1 A11,*B15--[2] |
| c016ca20 | wrapper_c016ca20 | generic routine (calls c0166a80) | guess | c016ca20: n=24; 1 callers; first op MVK.S2 0x0ea0,B4 |
| c016ca80 | wrapper_c016ca80 | generic routine (calls c0162be0,c0166a80) | guess | c016ca80: n=55; 2 callers; first op MVK.S2 0x0ee0,B4 |
| c016cb40 | wrapper_c016cb40 | generic leaf routine, no further structure identified | guess | c016cb40: n=31; 0 callers; first op STW.D2T2 B10,*B15--[2] |
| c016cba0 | wrapper_c016cba0 | generic routine (calls c0166a80) | guess | c016cba0: n=24; 2 callers; first op MVK.S2 0x0f00,B4 |
| c016cc00 | wrapper_c016cc00 | generic leaf routine, no further structure identified | guess | c016cc00: n=55; 0 callers; first op SUB.L2 B15,0x8,B15 |
| c016ccc0 | wrapper_c016ccc0 | generic leaf routine, no further structure identified | guess | c016ccc0: n=27; 3 callers; first op MV.L1 A4,A3 |
| c016cd20 | wrapper_c016cd20 | generic leaf routine, no further structure identified | guess | c016cd20: n=35; 5 callers; first op MVK.S2 0x5140,B5 |
| c016cd80 | wrapper_c016cd80 | generic routine (calls c016b9c0) | guess | c016cd80: n=24; 0 callers; first op STW.D2T1 A11,*B15--[2] |
| c016cde0 | wrapper_c016cde0 | generic routine (calls c0166a80) | guess | c016cde0: n=24; 0 callers; first op MVK.S2 0x0f20,B4 |
| c016ce40 | wrapper_c016ce40 | generic routine (calls c0167b00,c0167f60) | guess | c016ce40: n=29; 3 callers; first op STW.D2T1 A11,*B15--[2] |
| c016cea0 | wrapper_c016cea0 | generic routine (calls c0167b00) | guess | c016cea0: n=25; 0 callers; first op STW.D2T2 B3,*B15--[2] |
| c016cf00 | wrapper_c016cf00 | generic leaf routine, no further structure identified | guess | c016cf00: n=25; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016cf60 | wrapper_c016cf60 | generic routine (calls c013c980,c016eb40) | guess | c016cf60: n=30; 1 callers; first op STW.D2T1 A10,*B15--[4] |
| c016cfc0 | wrapper_c016cfc0 | generic routine (calls c013c980,c016c480,c016eb40) | guess | c016cfc0: n=74; 1 callers; first op STW.D2T1 A10,*B15--[4] |
| c016d0c0 | wrapper_c016d0c0 | generic routine (calls c0155ac0; B14[179 ]) | guess | c016d0c0: n=7; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016d0d4 | wrapper_c016d0d4 | generic routine (calls c0144580; B14[179 ]) | guess | c016d0d4: n=12; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016d100 | wrapper_c016d100 | generic routine (string 'OnOff ') | guess | c016d100: n=18; 0 callers; first op SUB.L2 B15,0x8,B15 |
| c016d140 | wrapper_c016d140 | generic leaf routine, no further structure identified | guess | c016d140: n=5; 0 callers; first op SUB.L2 B15,0x8,B15 |
| c016d150 | wrapper_c016d150 | generic routine (string 'OnOff') | guess | c016d150: n=31; 2 callers; first op MVK.L1 2,A0 |
| c016d1c0 | wrapper_c016d1c0 | generic routine (calls c0167b00) | guess | c016d1c0: n=20; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016d200 | wrapper_c016d200 | generic routine (calls c0164684) | guess | c016d200: n=10; 4 callers; first op STW.D2T2 B3,*B15--[2] |
| c016d220 | wrapper_c016d220 | generic routine (calls c0164684) | guess | c016d220: n=10; 4 callers; first op STW.D2T2 B3,*B15--[2] |
| c016d240 | wrapper_c016d240 | generic leaf routine, no further structure identified | guess | c016d240: n=20; 2 callers; first op MVK.S1 50,A0 |
| c016d280 | wrapper_c016d280 | generic leaf routine, no further structure identified | guess | c016d280: n=18; 1 callers; first op MVK.S1 65,A0 |
| c016d2c0 | wrapper_c016d2c0 | generic routine (calls 11804124,c01502e0,c01505f4) | guess | c016d2c0: n=17; 2 callers; first op CALLP.S1 0xc016e020,A3 |
| c016d300 | wrapper_c016d300 | generic routine (calls 11809160,1180933c,c011c508) | guess | c016d300: n=40; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016d380 | wrapper_c016d380 | generic leaf routine, no further structure identified | guess | c016d380: n=19; 1 callers; first op MVK.L2 0,B5 |
| c016d3c0 | fixed_mul64_c016d3c0 | 32x32->64 fixed-point multiply helper (MPY32U), operands from A4/B4/B5 | likely | c016d3c0: MPY32U.M2X B4,A4,B7:B6; 1 callers |
| c016d440 | wrapper_c016d440 | generic leaf routine, no further structure identified | guess | c016d440: n=17; 1 callers; first op SUB.D2 B15,0x10,B15 |
| c016d480 | wrapper_c016d480 | generic leaf routine, no further structure identified | guess | c016d480: n=21; 3 callers; first op MVK.S2 0x0020,B5 |
| c016d4c0 | rts_memcpy_word_sploop | software-pipelined word-granularity memcpy: SPLOOPD loop copying (A6>>2) words from B4 to A4 via LDW/STW; a second, unrelated bounded ring-buffer-append routine (LDW *B4[1]/[2] length/capacity compare, STB) starts immediately after at c016d540 and was folded into the same coverage-detected span | confirmed | c016d4c0 MV A4,A30 // SHR A6,0x2,B31; c016d4d0 SPLOOPD 1; c016d4d8 LDW *B30++[1],B31; c016d4e8 STW A31,*A30++[1]; 20 CALLP callers |
| c016d5c0 | wrapper_c016d5c0 | generic leaf routine, no further structure identified | guess | c016d5c0: n=19; 1 callers; first op STW.D1T1 A6,*A4--[1] |
| c016d600 | wrapper_c016d600 | generic leaf routine, no further structure identified | guess | c016d600: n=17; 2 callers; first op MVK.S1 0x1fb8,A0 |
| c016d640 | wrapper_c016d640 | generic routine (calls c0167b00) | guess | c016d640: n=16; 1 callers; first op MVK.S1 0x1538,A3 |
| c016d680 | wrapper_c016d680 | generic leaf routine, no further structure identified | guess | c016d680: n=19; 1 callers; first op MVK.L2 0,B4 |
| c016d6c0 | tailcall_wrapper_c016d6ec_c016d6c0 | small wrapper that tail-calls c016d6ec after a short setup | likely | c016d6c0: ...; B 0xc016d6ec; 3 callers |
| c016d780 | wrapper_c016d780 | generic routine (calls c0167da0,c016b740,c016bbc0) | guess | c016d780: n=16; 0 callers; first op MVK.S1 0xffffb0c0,A4 |
| c016d7c0 | wrapper_c016d7c0 | generic leaf routine, no further structure identified | guess | c016d7c0: n=16; 2 callers; first op MVK.S1 0x21ec,A3 |
| c016d800 | wrapper_c016d800 | generic leaf routine, no further structure identified | guess | c016d800: n=17; 3 callers; first op MVC.S2 CSR,B5 |
| c016d840 | wrapper_c016d840 | generic leaf routine, no further structure identified | guess | c016d840: n=17; 2 callers; first op MVC.S2 CSR,B5 |
| c016d880 | sem_post_or_clear | conditional wrapper around c01628e0: if arg2(B4) != 0, writes 0 to *A4[1] and returns; if arg2 == 0, tail-branches into c01628e0 (bios_sem_post) with B4 loaded from a fixed global at approx 0xc017d36c -- i.e. complete an operation, optionally releasing a default lock | confirmed | c016d888 [A0] B 0xc016d8b0 (store-0 path); c016d890 [!A0] B 0xc01628e0 // c016d894 LDW *+B4[0],B4 loads the lock handle then tail-calls the post primitive; 38 callers |
| c016d8c0 | wrapper_c016d8c0 | generic leaf routine, no further structure identified | guess | c016d8c0: n=32; 1 callers; first op MVK.S1 0x21ec,A3 |
| c016d940 | tailcall_wrapper_c0166a80_c016d940 | small wrapper that tail-calls c0166a80 after a short setup | likely | c016d940: ...; B 0xc0166a80; 4 callers |
| c016da00 | tailcall_wrapper_c0166a80_c016da00 | small wrapper that tail-calls c0166a80 after a short setup | likely | c016da00: ...; B 0xc0166a80; 2 callers |
| c016db00 | wrapper_c016db00 | generic leaf routine, no further structure identified | guess | c016db00: n=16; 1 callers; first op MVK.S1 0x21ec,A3 |
| c016db40 | wrapper_c016db40 | generic leaf routine, no further structure identified | guess | c016db40: n=18; 9 callers; first op MVK.S1 0x19f4,A3 |
| c016db80 | tailcall_wrapper_c016dba8_c016db80 | small wrapper that tail-calls c016dba8 after a short setup | likely | c016db80: ...; B 0xc016dba8; 5 callers |
| c016dc00 | wrapper_c016dc00 | generic leaf routine, no further structure identified | guess | c016dc00: n=32; 1 callers; first op MVK.S1 0x21ec,A3 |
| c016dc80 | wrapper_c016dc80 | generic routine (calls c0161540) | guess | c016dc80: n=19; 0 callers; first op STW.D2T1 A10,*B15--[2] |
| c016dcc0 | wrapper_c016dcc0 | generic routine (calls c016a560,c016cf60,c016e120) | guess | c016dcc0: n=68; 6 callers; first op STW.D2T2 B3,*B15--[2] |
| c016ddc0 | unk_ddc0 | large (81 instr) routine, prologue uses A15 frame pointer, only external call is c016cfc0; fact sheet B14-global list for this address looked anomalous (very large slot numbers) and was not trusted -- not traced further this wave | guess | callers=3; calls=c016cfc0; MV.L1X B15,A15 prologue |
| c016df00 | region_bridge_1 | bridges the c0 and 1180 address spaces: enters via c016e020 (c0-region save helper) but calls 11805878 (1180-region) and c01636a0, c016e000; small (8 instr visible) but called 18 times | guess | calls=11805878,c01636a0,c016e000; entered via CALLP 0xc016e020,A3; 18 callers |
| c016df20 | wrapper_c016df20 | generic routine (calls c01529c0; B14[184 ]) | guess | c016df20: n=8; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016df40 | wrapper_c016df40 | generic routine (calls c0168144) | guess | c016df40: n=5; 0 callers; first op STW.D2T2 B3,*B15--[2] |
| c016df54 | wrapper_c016df54 | generic leaf routine, no further structure identified | guess | c016df54: n=3; 0 callers; first op BNOP.S2 B3,5 |
| c016df60 | rts_const_return_0_c016df60 | leaf stub, returns constant 0 | confirmed | c016df60 MVK.L1 0,A4; BNOP; 2 callers |
| c016df64 | wrapper_c016df64 | generic routine (calls c0169fc0) | guess | c016df64: n=5; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016df74 | wrapper_c016df74 | generic routine (calls c016a060) | guess | c016df74: n=20; 1 callers; first op MVK.L1 0,A4 |
| c016dfc0 | tailcall_wrapper_c016ac40_c016dfc0 | small wrapper that tail-calls c016ac40 after a short setup | likely | c016dfc0: ...; B 0xc016ac40; 1 callers |
| c016e000 | rts_regs_restore | epilogue helper: pop B3:B2,A11:A10,B11:B10,A13:A12,B13:B12,A15:A14,B14 then BNOP B3,0 (return) | confirmed | c016e000 LDDW *++B15[1],B3:B2 ... BNOP B3,0; 853 refs; pairs with c016e020 |
| c016e020 | rts_regs_save | prologue helper: push B14,A15:A14,B13:B12,A13:A12,B11:B10,A11:A10,B3:B2 then branch to A3 (entered via CALLP X,A3, not B3, so B3 stays free) | confirmed | c016e020 STW B14,*B15--[2]; B.S2X A3, then parallel/sequential STDW of A15:A14,B13:B12,A13:A12,B11:B10,A11:A10,B3:B2; 865 CALLP/branch refs, matches brief's CALLP ...,A3 save/restore shape |
| c016e0c0 | wrapper_c016e0c0 | generic leaf routine, no further structure identified | guess | c016e0c0: n=16; 3 callers; first op BNOP.S2 B3,2 |
| c016e100 | wrapper_c016e100 | generic leaf routine, no further structure identified | guess | c016e100: n=8; 2 callers; first op MV.D2X A4,B0 |
| c016e120 | wrapper_c016e120 | generic leaf routine, no further structure identified | guess | c016e120: n=8; 2 callers; first op NOP  |
| c016e140 | wrapper_c016e140 | generic routine (calls c016dfc0) | guess | c016e140: n=11; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016e160 | wrapper_c016e160 | generic routine (calls c013e4f4) | guess | c016e160: n=8; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016e180 | tailcall_wrapper_c0169fc0_c016e180 | small wrapper that tail-calls c0169fc0 after a short setup | likely | c016e180: ...; B 0xc0169fc0; 0 callers |
| c016e1a0 | wrapper_c016e1a0 | generic routine (calls c0161e60) | guess | c016e1a0: n=8; 0 callers; first op MV.L1X B3,A2 |
| c016e1c0 | wrapper_c016e1c0 | generic routine (calls c016e2c0) | guess | c016e1c0: n=24; 2 callers; first op INTSP.L1 A4,A4 |
| c016e220 | wrapper_c016e220 | generic leaf routine, no further structure identified | guess | c016e220: n=5; 1 callers; first op MV.L2 B4,B0 |
| c016e22c | wrapper_c016e22c | generic routine (calls c0163118) | guess | c016e22c: n=7; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016e240 | tailcall_wrapper_c0161200_c016e240 | small wrapper that tail-calls c0161200 after a short setup | likely | c016e240: ...; B 0xc0161200; 1 callers |
| c016e280 | wrapper_c016e280 | generic leaf routine, no further structure identified | guess | c016e280: n=8; 2 callers; first op MVK.S1 0x1f60,A3 |
| c016e2a0 | wrapper_c016e2a0 | generic leaf routine, no further structure identified | guess | c016e2a0: n=8; 1 callers; first op MVK.S1 0x1f60,A5 |
| c016e2c0 | wrapper_c016e2c0 | generic leaf routine, no further structure identified | guess | c016e2c0: n=9; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016e2e0 | wrapper_c016e2e0 | generic leaf routine, no further structure identified | guess | c016e2e0: n=24; 1 callers; first op BNOP.S2 B3,4 |
| c016e340 | wrapper_c016e340 | generic routine (calls c015ee80) | guess | c016e340: n=10; 1 callers; first op STW.D2T2 B3,*B15--[2] |
| c016e360 | wrapper_c016e360 | generic routine (calls c015ee80) | guess | c016e360: n=10; 3 callers; first op STW.D2T2 B3,*B15--[2] |
| c016e380 | wrapper_c016e380 | generic routine (calls c015ee80) | guess | c016e380: n=10; 3 callers; first op STW.D2T2 B3,*B15--[2] |
| c016e3a0 | tailcall_wrapper_c016ba40_c016e3a0 | small wrapper that tail-calls c016ba40 after a short setup | likely | c016e3a0: ...; B 0xc016ba40; 1 callers |
| c016e3e0 | wrapper_c016e3e0 | generic leaf routine, no further structure identified | guess | c016e3e0: n=24; 1 callers; first op MVC.S2 CSR,B4 |
| c016e440 | wrapper_c016e440 | generic leaf routine, no further structure identified | guess | c016e440: n=8; 0 callers; first op MVK.L2 0,B4 |
| c016e460 | wrapper_c016e460 | generic leaf routine, no further structure identified | guess | c016e460: n=26; 4 callers; first op MVC.S2 TSCL,B4 |
| c016e4c0 | csr_get | reads CSR into B4 and returns; the raw mechanic behind an Hwi_disable-style get-old-interrupt-state helper, but it does not itself issue DINT, so any real interrupt-disable happens inline at the call site, not inside this helper | likely | c016e4c0 opens MVC.S2 CSR,B4 (per range overview); pairs with the c016e4e0 setter below |
| c016e4e0 | csr_set | writes a caller-supplied value (B4) back into CSR and returns -- mechanically identical to Hwi_restore(key): restores a previously saved interrupt-enable state | likely | c016e4e0 opens MVC.S2 B4,CSR (per range overview); pairs with c016e4c0 |
| c016e500 | wrapper_c016e500 | generic routine (calls c016da00) | guess | c016e500: n=17; 0 callers; first op MVK.L1 0,A4 |
| c016e540 | wrapper_c016e540 | generic leaf routine, no further structure identified | guess | c016e540: n=8; 1 callers; first op MVK.L1 1,A4 |
| c016e560 | wrapper_c016e560 | generic routine (calls c016d7c0) | guess | c016e560: n=8; 1 callers; first op MV.L1X B3,A2 |
| c016e580 | wrapper_c016e580 | generic routine (calls c016e560) | guess | c016e580: n=11; 0 callers; first op STW.D2T2 B3,*B15--[2] |
| c016e5a0 | wrapper_c016e5a0 | generic routine (calls c016e5c0) | guess | c016e5a0: n=11; 0 callers; first op STW.D2T2 B3,*B15--[2] |
| c016e5c0 | wrapper_c016e5c0 | generic routine (calls c016db00) | guess | c016e5c0: n=32; 1 callers; first op MV.L1X B3,A2 |
| c016e640 | tailcall_wrapper_c0161200_c016e640 | small wrapper that tail-calls c0161200 after a short setup | likely | c016e640: ...; B 0xc0161200; 3 callers |
| c016e660 | tailcall_wrapper_c016d880_c016e660 | small wrapper that tail-calls c016d880 after a short setup | likely | c016e660: ...; B 0xc016d880; 3 callers |
| c016e680 | tailcall_wrapper_c016ba40_c016e680 | small wrapper that tail-calls c016ba40 after a short setup | likely | c016e680: ...; B 0xc016ba40; 1 callers |
| c016e6a0 | wrapper_c016e6a0 | generic routine (calls c016e540) | guess | c016e6a0: n=16; 0 callers; first op STW.D2T2 B3,*B15--[2] |
| c016e6e0 | tailcall_wrapper_c016ba40_c016e6e0 | small wrapper that tail-calls c016ba40 after a short setup | likely | c016e6e0: ...; B 0xc016ba40; 2 callers |
| c016e700 | struct_get_field_0_c016e700 | getter: returns field +0 of the struct pointed to by arg A4 | confirmed | c016e700: LDW.D1T1 *+A4[0],A4; 1 callers |
| c016e720 | tailcall_wrapper_c016ba40_c016e720 | small wrapper that tail-calls c016ba40 after a short setup | likely | c016e720: ...; B 0xc016ba40; 1 callers |
| c016e740 | wrapper_c016e740 | generic leaf routine, no further structure identified | guess | c016e740: n=16; 1 callers; first op MVK.S1 0x0714,A3 |
| c016e780 | tailcall_wrapper_c0166a80_c016e780 | small wrapper that tail-calls c0166a80 after a short setup | likely | c016e780: ...; B 0xc0166a80; 2 callers |
| c016e7c0 | wrapper_c016e7c0 | generic routine (calls c016e780) | guess | c016e7c0: n=17; 1 callers; first op LDW.D1T1 *+A4[0],A3 |
| c016e800 | tailcall_wrapper_c016ba40_c016e800 | small wrapper that tail-calls c016ba40 after a short setup | likely | c016e800: ...; B 0xc016ba40; 4 callers |
| c016e820 | struct_get_field_6_c016e820 | getter: returns field +6 of the struct pointed to by arg A4 | confirmed | c016e820: LDHU.D1T1 *+A4[6],A4; 1 callers |
