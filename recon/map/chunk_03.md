# chunk_03: c0122924..c0128134 (150 functions)

Summary: this range holds three clearly separated subsystems. (1)
c0122924..c0124fc0 (~100 functions) is the TI ELF/dynamic-loader
machinery that loads a 5-slot effect module image: header/magic
validation (`c0123478` checks `\x7fELF`, `c01234c4` checks
`e_machine==140`=EM_C6000), section/program-header field population
(`c0123848`'s internal dispatch at `c012387c` fed by a ~10-entry
function-pointer table at `0xc0183d04..3c`, one arm per `Elf32_Shdr`
field), module object creation (`c0123ce4`), PT_LOAD segment loading
(`c01242bc`), special-symbol lookup (`c0124584`, `c0124cf8` for
`__TI_STATIC_BASE`), and relocation-handler selection/invocation
(`c01235ec`/`c0123824`/`c0122d50`, all keyed off B14[132]) feeding the
EM_C6000 handler `c0133f28` outside this range -- this matches recon/14
and recon/18's prior ELF-loader tracing almost exactly and most of
those rows cite it directly. A lock/error-flag pair recurring through
this cluster, `locked_subsystem_op_115`/`validate_and_set_error`
(both keyed on B14[115], already named in 00), guards most stages.
(2) c0125000..c0127070 (~35 functions) is a UI/rhythm bitmap-and-draw
cluster rooted in MainApp/RhythmService/UpdateUI: `c01256c4` is
confirmed (read the code) to be a second "set a run of bits" SPLOOP
primitive -- structurally identical to the already-named LCD primitive
`gfx_set_bit_range` (c011c508, see 00) but targeting a different
bitmap base (`0xc0183ae4`), and is called from 13 sibling draw/pattern
functions. `c0126624`/`c01268e0`/`c01269d4` (700/244/700 instructions,
two near-identical) sit under the already-named `orchestrator_c0126624`
(c0126c90, see 00) and use the signed-divide helper, consistent with
rhythm-pattern timing math. (3) c0127440..c0128134 (~25 functions) is a
MIDI message-building cluster: a table-driven checksum/CRC step
(`c0127440`, read the code), per-parameter "jump-table" entry functions
(`c0127daa..c0127f48`) that each call one small worker then return via
the already-named shared epilogue `epilogue_pop_b3_shared2`
(c0127f58, see 00), driven off a function-pointer table at
`0xc0183b74..c0183c3c`, all exercising the already-named
`midi_tx_locked`/`midi_tx_n` senders (c01274cc/c0127500, see 00) and a
cluster of B14 slots (30-38, 112-119) that look like per-CC-parameter
state.

Functions already named in `recon/map/00_library_kernel.md` (listed
here as "see 00", not re-analyzed): `c0123a74` (thin_arg_adapter),
`c0126c90` (orchestrator_c0126624), `c01274cc` (midi_tx_locked),
`c0127500` (midi_tx_n), `c0127f58` (epilogue_pop_b3_shared2).

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| c0122924 | tbl_step_c011297c | steps a 168-byte-stride record table @0xc011297c indexed by arg0: guards on field+2 non-null, reads/transitions state field+3 (1 or 2 -> check field+5, else branch), calls c0120650 or c0120800 | confirmed | read: `MVKH 0xc0110000,B0; MVK 0x297c` base; `MPYLI A0,A3` (A0=168|0x200 via SET.S1 A0,9,9); CMPEQ field+3 vs 1/2; CALLP c0120650/c0120800 |
| c0122988 | tbl_step_c011341c | same shape as c0122924, second record table @0xc011341c, dispatches to c0120904/c0120acc instead | confirmed | read: identical instruction pattern to c0122924 with base 0xc011341c; CALLP c0120904/c0120acc |
| c01229e8 | tbl_step_dispatch | orchestrator entered via c016e020/restored via c016e000; calls c01200f4 then both per-table steppers c0122924 and c0122988 -- a generic "service pending slot" poller, called from 5 unrelated sites | likely | calls=c01200f4,c0122924,c0122988,c016e000,c016e020; 5 callers (c0137fe4,c015b168,c015b290,c015b2b4,c015e9d0); n=228 |
| c0122acc | const_ret0_dup | 1-instruction body (`MVK 0,A4`) immediately followed by the next function's prologue -- a tail-shared "return 0" artifact, single caller c015e880 | likely | size=4 (one instr); callers=1 (c015e880); no calls |
| c0122ad0 | wrapper_c0122ad0 | generic routine calling c0121224 (outside this chunk), not traced further | guess | n=144(approx, size field); callers=1 (c015e9d0); calls=c0121224 |
| c0122b60 | elf_stage_lock_b60 | ELF-loader stage: takes the B14[115] "effect-load" lock via locked_subsystem_op_115, called from both module-create (c0123ce4) and the top-level loader (c0124b2c) | likely | calls=c0163118=locked_subsystem_op_115; callers=c0123ce4,c0124b2c |
| c0122bb4 | elf_stage_check_bb4 | ELF-loader stage: runs the B14[115] error-check validate_and_set_error, called from module-create, c0124974 and the top-level loader | likely | calls=c01630b4=validate_and_set_error; callers=c0123ce4,c0124974,c0124b2c |
| c0122bf8 | elf_stage_check_bf8 | ELF-loader stage: validate_and_set_error wrapper, single caller c0124f8c (the finalize/close stage) | likely | calls=c01630b4=validate_and_set_error; callers=c0124f8c |
| c0122cb0 | elf_stage_lock_cb0 | ELF-loader stage: locked_subsystem_op_115 wrapper, callers c01245f0 and c0124884 | likely | calls=c0163118=locked_subsystem_op_115; callers=c01245f0,c0124884 |
| c0122d04 | elf_stage_check_d04 | ELF-loader stage: validate_and_set_error wrapper, single caller c0124b2c (top-level loader) | likely | calls=c01630b4=validate_and_set_error; callers=c0124b2c |
| c0122d50 | elf_call_reloc_handler | invokes the relocation-handler object stored at B14[132] (set by c0123648 per recon/18): reads the handler struct and calls its word[4] -- the final hop in the load chain c0124b2c->c0124974->c012484c->c0122d50->c0133f28 | confirmed | recon/18_round3.md line 83: "c01235ec selects it, c0123648 stores it at B14[132], and c0122d50 calls its word[4]. Load chain: c0124b2c -> c0124974 -> c012484c -> c0122d50 -> c0133f28"; B14 globals: 132 |
| c0122d70 | elf_stage_d70 | ELF-loader stage calling two out-of-range helpers (c015f66c,c015f70c) then err_set_last_code on failure; single caller c0122f4c | guess | calls=c015f66c,c015f70c,c016be80=err_set_last_code; callers=c0122f4c |
| c0122e04 | elf_stage_e04 | large (292 instr) ELF-loader stage, B14[134], calls four out-of-range helpers (c01510e8,c015f654,c015fe30,c0162f74) plus err_set_last_code; callers c0122f28, c0123664, c0123ce4 (module creation) | likely | n=292; B14 globals: 134; calls=c01510e8,c015f654,c015fe30,c0162f74,c016be80; callers=c0122f28,c0123664,c0123ce4 |
| c0122f28 | elf_stage_f28 | thin wrapper around c0122e04 plus c0168040; single caller c0122f4c | guess | calls=c0122e04,c0168040; callers=c0122f4c |
| c0122f4c | elf_stage_f4c | ELF-loader stage (228 instr) chaining c0122d70+c0122f28, called from both the top-level loader (c0124b2c), c0124f50, and the unload driver c01560c0 -- likely a cleanup/dispatch step shared by load and unload | likely | calls=c0122d70,c0122f28,c01458e0,c0147668,c015f624,c015fe08,c016be80; B14 109,132; callers=c0124b2c,c0124f50,c01560c0; recon:18 |
| c0123030 | elf_stage_030 | ELF-loader stage, single caller c0156304 (an out-of-range driver), calls c015fe08+err_set_last_code | guess | callers=c0156304; calls=c015fe08,c016be80 |
| c01230c8 | elf_stage_0c8 | thin err_set_last_code wrapper, single caller c0123128 | guess | calls=c016be80; callers=c0123128 |
| c0123128 | elf_stage_128 | large (552 instr) ELF-loader stage taking the B14[115] lock (locked_subsystem_op_115) and calling c01230c8/c015f690; callers c0123350, c0123ce4 (module creation) | likely | n=552; calls=c01230c8,c015f690,c0163118=locked_subsystem_op_115; callers=c0123350,c0123ce4 |
| c0123350 | elf_stage_350 | ELF-loader stage, B14[17,18], calls c0123128+c015fe08+err_set_last_code | guess | B14 17,18; calls=c0123128,c015fe08,c016be80 |
| c01233c0 | elf_parse_header | ELF header "parse" stage recon/14 names directly: "Its calls include parse c01233c0/c0123620"; takes the B14[115] lock; called from module-create and the top-level loader | confirmed | recon/14_effect_memory.md line 45: "parse c01233c0/c0123620, module creation c0123ce4, segment loading c01242bc"; calls=c0163118=locked_subsystem_op_115; callers=c0123ce4,c0124b2c |
| c0123478 | elf_check_magic | checks the 4-byte ELF magic at *A4[0..3] against 127,69,76,70 (0x7f,'E','L','F') one byte at a time; records error code 3 via err_set_last_code and returns 0 on any mismatch, 1 on match | confirmed | read: `c012347c LDBU *A4[0]; MVK 127; CMPEQ` ... repeated for bytes 1-3 against 69/76/70; on failure `CALLP c016be80,B3 (code=3)`; returns A4=0/1 |
| c01234c4 | elf_check_machine_c6000 | checks an incoming value against 140 (0x8c = EM_C6000, the machine id recon/18 ties to the handler table at c0183688) and returns the equality flag | confirmed | read: `c01234c4 MVK 140,A0; CMPEQ A4,A0,A0; MV A0,A4; BNOP B3,5` |
| c01234cc | elf_check_header | combines elf_check_magic (c0123478) + elf_check_machine_c6000 (c01234c4) plus two more helpers (c015f6e8, c0163300/c01633ec); the magic/machine checks at the top of this routine's callee are what gate ELF acceptance | confirmed | calls=c0123478=elf_check_magic,c01234c4,c015f6e8,c0163300,c01633ec,c016be80; callers=c0123620 |
| c012354c | elf_parse_header2 | sibling parse-stage helper (160 instr) calling c015f6c4/c015f6d0/c0163450 plus err_set_last_code; single caller c0123620 | guess | calls=c015f6c4,c015f6d0,c0163450,c016be80; callers=c0123620 |
| c01235ec | elf_select_reloc_handler | selects the relocation-handler object for the module's machine type (recon/18: "c01235ec selects it, c0123648 stores it at B14[132]"), feeding c0122d50's later invocation | confirmed | recon/18_round3.md line 83; callers=c0123620 |
| c0123620 | elf_parse_header_dispatch | second named "parse" stage (recon/14: "parse c01233c0/c0123620"): calls elf_check_header (c01234cc), elf_parse_header2 (c012354c) and elf_select_reloc_handler (c01235ec); B14[132]; called from module-create and the top-level loader | confirmed | recon/14 line 45; calls=c01234cc=elf_check_header,c012354c,c01235ec,c016be80; B14 132; callers=c0123ce4,c0124b2c |
| c0123664 | elf_stage_664 | ELF-loader stage calling elf_stage_e04 (c0122e04) plus validate_and_set_error/err_set_last_code; callers c0123ce4, c0124974, c0124b2c | guess | calls=c0122e04,c01630b4=validate_and_set_error,c016be80; callers=c0123ce4,c0124974,c0124b2c |
| c01236b8 | elf_stage_6b8 | thin err_set_last_code wrapper, single caller c0123b4c | guess | calls=c016be80; callers=c0123b4c |
| c0123764 | elf_stage_764 | tiny (20 instr) stage, B14[132], single caller c0123b4c -- likely rechecks/reuses the relocation-handler slot | guess | B14 132; callers=c0123b4c |
| c0123778 | elf_stage_778 | ELF-loader stage calling c015f6c4/c015f6d0/c0163450 plus err_set_last_code; single caller c0123b34 | guess | calls=c015f6c4,c015f6d0,c0163450,c016be80; callers=c0123b34 |
| c0123824 | elf_shdr_reloc_lookup | reads/uses the B14[132] relocation-handler slot; only caller is thin_arg_adapter (c0123a74, see 00), which reorders its return before calling the section-header-field dispatcher c0123b18 | likely | B14 132; callers=c0123a74=thin_arg_adapter |
| c0123848 | elf_shdr_field_dispatch | large (556 instr) section-header field-populate routine: internally contains the label c012387c that the ten field-setting "arms" below (c0123a8c..c0123b12, via shared tail c0123b18) branch back into -- a switch-like loop over Elf32_Shdr fields (10 fields matches the 10 arms), not itself calling c012387c via CALLP since it's an internal label | confirmed | read: c012387c (`LDNW *+B4[0],B0`) sits 14 instr after c0123848's own prologue, inside c0123848's own span -- confirmed internal label, not a separate function; calls=thin_arg_adapter,c015f6c4,c015f6d0,c015f6e8,c0163324=field_extract_u8,c0163374,c016be80; callers=c0123b34 |
| c0123a8c | elf_shdr_field_set_12 | switch-arm: loads a decoded field from *B4[1] and stores it at offset 0x12 (ADDAD-scaled) of the object pointed to by A10, then falls into the shared continuation c0123b18 | likely | read: `LDNW *+B4[1],B0; ADDAD A0,0x12,A4; STW B0,*A4[0]; BNOP 0xc0123b18` |
| c0123aa4 | elf_shdr_field_set_const140 | switch-arm: stores the literal constant 140 (0x8c = EM_C6000) into a field of the object, then falls into c0123b18 -- stamping the machine-id field rather than copying a decoded value | likely | read: `MVK 140,A0; MV A11,B0; ADD A0,A10,A4; STW B0,*+A4[0]; BNOP 0xc0123b18` |
| c0123ab4 | elf_shdr_field_set_156 | switch-arm: loads *B4[1], stores at offset 156 (0x9c) of the object, falls into c0123b18 | likely | read: `LDNW *B4[1],B0; MVK 156,A0; ADD A0,A10,A4; STW B0,*A4[0]; BNOP 0xc0123b18` |
| c0123ac6 | elf_shdr_field_set_13 | switch-arm: stores A11 at offset 0x13 (ADDAD-scaled) of the object, falls into c0123b18 | likely | read: `ADDAD A0,0x13,A4; MV A11,B0; STW B0,*A4[0]; BNOP 0xc0123b18` |
| c0123ad4 | elf_shdr_field_set_b11 | switch-arm: loads *+B4[1] and moves it into register B11/A13 (not a struct store) before falling into c0123b18 -- likely sets up a return/working register rather than a field | likely | read: `LDNW *+B4[1],B0; MV B0,B11; MVK 1,B0; MV B0,A13; BNOP 0xc0123b18` |
| c0123ae6 | elf_shdr_field_set_const148 | switch-arm: stores the literal constant 148 into a field of the object, falls into c0123b18 | likely | read: `MVK 148,A0; ADD A0,A10,A4; MV A11,B0; STW B0,*A4[0]; BNOP 0xc0123b18` |
| c0123af4 | elf_shdr_field_set_18 | switch-arm: loads *+B4[1], stores at offset 18 of the object (*+A4[18]), falls into c0123b18 | likely | read: `LDNW *+B4[1],B0; MV A10,A4; STW B0,*+A4[18]; BNOP 0xc0123b18` |
| c0123b06 | elf_shdr_field_set_a12 | switch-arm: loads *B4[1] into register A12 (not memory), falls into c0123b18 | likely | read: `LDNW *B4[1],B0; MV B0,A12; BNOP 0xc0123b18` |
| c0123b0c | elf_shdr_field_set_b10 | switch-arm: loads *B4[1] into register B10, falls into c0123b18 | likely | read: `LDNW *B4[1],B0; MV B0,B10; BNOP 0xc0123b18` |
| c0123b12 | elf_shdr_field_set_a15 | switch-arm: loads *B4[1] into register A15 (via B0), falls into c0123b18 | likely | read: `LDNW *B4[1],B0; MV B0,A15; BNOP 0xc0123b18` |
| c0123b18 | elf_shdr_field_continue | shared continuation for all ten switch-arms above: unconditionally branches back into c0123848's own body at label c012387c to resume the field-populate loop -- confirms c0123848 is one large dispatching function, not that these arms call out to a separate routine | confirmed | read: `c0123b18 BNOP.S1 0xc012387c,4` -- target is 14 instructions into c0123848's own span; callers= all ten arms above + thin_arg_adapter |
| c0123b34 | elf_stage_b34 | calls elf_stage_778 (c0123778) then elf_shdr_field_dispatch (c0123848); single caller c0123b4c | guess | calls=c0123778,c0123848=elf_shdr_field_dispatch; callers=c0123b4c |
| c0123b4c | elf_stage_b4c | ELF-loader stage chaining c01236b8+c0123764+c0123b34, callers c0123ce4 (module creation) and c0124b2c (top-level loader) | guess | calls=c01236b8,c0123764,c0123b34,c016be80; callers=c0123ce4,c0124b2c |
| c0123ba0 | elf_stage_ba0 | large-ish (288 instr) stage calling c015f6b4/c015f6c4 plus err_set_last_code; callers c0123ce4, c0124b2c | guess | n=288; calls=c015f6b4,c015f6c4,c016be80; callers=c0123ce4,c0124b2c |
| c0123cc0 | elf_stage_cc0 | small (36 instr) stage with no recorded callees, three callers (c0123ce4, c0124974, c0124b2c) -- possibly a flag getter/clearer between load stages | guess | n=36; no calls listed; callers=c0123ce4,c0124974,c0124b2c |
| c0123ce4 | elf_module_create | the "module creation" stage recon/14 names directly: huge (996 instr) dispatcher calling 26+ of the stage functions above (c0122b60, c0122bb4, c0122e04, c0123128, c01233c0, c0123620, c0123664, c0123b4c, c0123ba0, c0123cc0, plus out-of-range c0145970/c0145a0c/c0145d30/c0146cb4/c01510e8/c015f644...); single caller c0124b2c | confirmed | recon/14_effect_memory.md line 45: "module creation c0123ce4"; recon/18; callers=c0124b2c |
| c01240c8 | elf_stage2_0c8 | small (36 instr) stage, B14[132] (relocation-handler slot), single caller c0124178 | guess | B14 132; callers=c0124178 |
| c01240ec | elf_stage_sym_0ec | 140-instr routine called from three different sites including c0164b48 (outside this chunk) as well as c0124234/c0124244 below -- a shared symbol/field helper reused elsewhere in the loader | guess | n=140; callers=c0124234,c0124244,c0164b48 |
| c0124178 | elf_stage_178 | 188-instr stage chaining c01240c8, c0124234, c0124244, c01242a0; single caller c01242bc (segment loading) | guess | calls=c01240c8,c0124234,c0124244,c01242a0,c016e020; callers=c01242bc=elf_load_segments |
| c0124234 | elf_stage_234 | small (16 instr) stage calling c01240ec and c01242a0; is itself a function-pointer-table entry (ptr@ c0184554) as well as being called directly by c0124178 | guess | calls=c01240ec,c01242a0; ptr@ c0184554; callers=c0124178 |
| c0124244 | elf_stage_244 | sibling of c0124234 (72 instr), same two callees, own table slot at c0184558 | guess | calls=c01240ec,c01242a0; ptr@ c0184558; callers=c0124178 |
| c012428c | elf_stage_28c | 20-instr routine reachable only via its function-pointer table slot (ptr@ c0184560), no direct callers recorded -- part of the same dispatch table as c0124234/c0124244/c01242a0 | guess | ptr@ c0184560; no callers recorded directly (table-only) |
| c01242a0 | elf_stage_2a0 | small (28 instr) shared tail called from c0124178, c0124234 and c0124244, also its own table slot (ptr@ c018455c) | guess | calls=c016e000; ptr@ c018455c; callers=c0124178,c0124234,c0124244 |
| c01242bc | elf_load_segments | the "segment loading" stage recon/14/18 name directly (PT_LOAD loop): calls elf_stage_178 (c0124178) plus out-of-range c015f72c; checked by c0124b2c's abort-on-failure logic at c0124bac/c0124bb6 | confirmed | recon/14 line 45 "segment loading c01242bc"; recon/18_round3.md line 230-235 "the PT_LOAD call at c0124bac: CALLP.S2 0xc01242bc,B3"; callers=c0124b2c |
| c0124584 | elf_lookup_special_symbol | the "special symbol" lookup recon/14 names: "c0124584 instead looks up a special symbol"; single caller c0124b2c; string __TI_STACK_SIZE nearby in the same cluster (c0124584 itself calls c0146b14) | confirmed | recon/14_effect_memory.md line 45; calls=c0146b14; callers=c0124b2c; strings nearby: __TI_STACK_SIZE (c0124584's own fact-sheet entry) |
| c01245f0 | elf_stage_5f0 | stage taking the B14[115] lock (elf_stage_lock_cb0 / c0122cb0) under a lock pattern; single caller c0124b2c | guess | calls=c0122cb0,c0163118=locked_subsystem_op_115; callers=c0124b2c |
| c012466c | elf_stage_66c | 236-instr stage calling three out-of-range helpers (c015f6a4,c015fda0,c0162f84); single caller c0124b2c | guess | n=236; calls=c015f6a4,c015fda0,c0162f84; callers=c0124b2c |
| c0124758 | elf_stage_758 | stage calling out-of-range c015f720; single caller c012484c | guess | calls=c015f720; callers=c012484c |
