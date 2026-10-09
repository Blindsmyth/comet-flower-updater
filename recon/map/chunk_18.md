# chunk_18: c016e020..c016ec40 (68 functions)

Summary: Mapping in progress.

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| c016e020 | rts_regs_save | save ABI-preserved registers on the stack and return through A3 | confirmed | c016e020 `STW B14,*B15--[2]`; c016e024 `B A3` with delay slots storing A15:A10, B13:B10, and B3:B2 |
| c016e0c0 | runtime_global_3aec_set | store A4 to runtime global c0183aec | confirmed | c016e0c4-c016e0cc form c0183aec and `STW A4,*A3` in the return delay slots |
| c016e100 | stack_pointer_init_if_zero | conditionally initialize B15 from runtime global c0181fcc | confirmed | c016e100 copies A4 to B0; A4!=0 -> return/no writes; A4==0 -> c016e110 loads B15 from c0181fcc and c016e114 clears that global |
| c016e120 | runtime_halt | spin forever | confirmed | c016e124 `BNOP 0xc016e124,5` |
| c016e140 | callback_broadcast_null | broadcast a null event/value tuple | confirmed | c016e140 saves B3; c016e144 calls `callback_broadcast_tailcall` with B4=0, A6=0, then returns A4=0 |
| c016e160 | codec_init_default_device | initialize codec using descriptor at ffffac44 | confirmed | c016e164/c016e16c load A4=ffffac44; c016e168 calls `codec_init_and_mute` |
| c016e180 | variant_record_copy_adapter | rearrange an encoded record and tail-call variant-record copy | likely | c016e180/c016e188 load A6 from original A4+3; c016e18c-c016e194 pass A4=old B4 and B4=old A4+7; c016e184 branches to `variant_record_copy` |
| c016e1a0 | audio_ramp_table_apply_mode1 | apply the audio ramp table with mode 1 | confirmed | c016e1a0 preserves B3 in A2; c016e1a4 calls `audio_ramp_table_apply` with A6=1; c016e1ac returns through A2 |
| c016e1c0 | int32_to_float | convert signed integer A4 to single-precision float | confirmed | c016e1c0 `INTSP A4,A4`; c016e1c4 returns |
| c016e1e0 | audio_ramp_callback_invoke_zero | invoke the installed audio-ramp callback with A4=0 | confirmed | hidden start; c016e1e4 calls c016e2c0 with c016e1e8 `MVK 0,A4` |
| c016e220 | pair_init | initialize a two-word record from B4 and zero | confirmed | c016e220-c016e226 stores B4 at A4+0 and zero at A4+4 |
| c016e22c | locked_subsystem_op_8 | run locked subsystem operation 8 | confirmed | c016e22e sets A4=8; c016e230 calls `locked_subsystem_op_115` |
| c016e240 | cfg_locked_dispatch_tailcall | tail-call the locked configuration dispatcher | confirmed | c016e240 branches directly to `cfg_locked_dispatch`; later c016e260 code is not part of this entry |
| c016e280 | runtime_pair_1f60_copy | copy the eight-byte runtime pair at c0181f60 to A4 | confirmed | c016e280-c016e288 form c0181f60 and `LDNDW`; c016e290 stores the pair to A4 |
| c016e2a0 | runtime_slot_1f74_swap | replace c0181f74 with A4 and return its old value | confirmed | c016e2ac loads c0181f60+20 (scaled `[5]`); c016e2b0 stores the input there while A4 retains the old word |
| c016e2c0 | audio_ramp_callback_invoke | call the function pointer stored at c0181f78 | confirmed | c016e2c4-c016e2cc load pointer from c0181f78; c016e2d0 branch plus c016e2d4 `ADDKPC` makes the indirect call |
| c016e2e0 | return_true | return 1 | confirmed | c016e2e0 `BNOP B3,4`; c016e2e4 delay slot sets A4=1 |
| c016e340 | l2_cache_writeback_invalidate | write back and invalidate an L2 address range | confirmed | c016e342 moves input B6 to A6; c016e344-c016e34c pass operation registers at 01844018 to `l2_cache_wbinv_or_wb` |
| c016e360 | l2_cache_invalidate | invalidate an L2 address range | confirmed | c016e362 moves input B6 to A6; c016e364-c016e36c pass operation registers at 01844010 to `l2_cache_wbinv_or_wb` |
| c016e380 | l2_cache_writeback | write back an L2 address range | confirmed | c016e382 moves input B6 to A6; c016e384-c016e38c pass operation registers at 01844000 to `l2_cache_wbinv_or_wb`; used before USB TX submission |
| c016e3a0 | arena_copy_default_descriptor | tail-call the arena/ring copy body, supplying descriptor c0180600 when B4 is null | confirmed | c016e3a0 branches to `arena_copy_body`; B4!=0 -> preserve caller B4; B4==0 -> c016e3b0 selects c0180600 into B4 |
| c016e3e0 | interrupts_enable | set the global-interrupt-enable bit in CSR | confirmed | c016e3e0 reads CSR; c016e3e4 ORs bit 0; c016e3e8 writes CSR |
| c016e440 | timestamp_counter_start | clear TSCL and return -1 | confirmed | c016e440-c016e444 write zero to TSCL; c016e448 returns -1 |
| c016e460 | timestamp_counter_low_get | return the low 32 bits of the timestamp counter | confirmed | c016e460 reads TSCL into B4; c016e468 moves it to A4 |
| c016e4c0 | interrupts_disable_save_csr | disable interrupts and return the previous CSR | confirmed | c016e4c0 reads CSR; c016e4c8 returns it in A4 in parallel with c016e4cc `DINT` |
| c016e4e0 | csr_restore | restore CSR from B4 | confirmed | c016e4e0 `MVC B4,CSR`; c016e4e8 returns |
| c016e500 | return_false | return 0 | confirmed | c016e500 sets A4=0 and c016e504 returns |
| c016e520 | menu_commit_0ee0_global_offset | add the base from c017d36c to A4 and commit through the 0ee0 menu descriptor | likely | hidden start; c016e524-c016e52c load `*c017d36c`; c016e530 calls `menu_commit_0ee0` with c016e534 `ADD A3,A4,A4` |
| c016e540 | return_true_540 | return 1 | confirmed | c016e540 sets A4=1 and c016e544 returns |
| c016e560 | global_object_invalid_get | return whether global object c01821ec is absent or has a negative field 4 | confirmed | c016e564 calls `global_object_field4_negative_or_missing`; c016e568 returns its result unchanged |
| c016e580 | global_object_field4_status | convert the field-4 validity test to a 0/-1 status | confirmed | c016e584 calls c016e560; result==0 -> c016e58e returns 0; result!=0 -> c016e58c returns -1 |
| c016e5a0 | global_object_field9_status | convert the field-9 validity test to a 0/-1 status | confirmed | c016e5a4 calls c016e5c0; result==0 -> c016e5ae returns 0; result!=0 -> c016e5ac returns -1 |
| c016e5c0 | global_object_field9_invalid_get | return whether global object c01821ec is absent or has a negative field 9 | confirmed | c016e5c4 calls `global_object_field9_negative_or_missing`; c016e5c8 returns its result unchanged |
| c016e640 | cfg_locked_dispatch_tailcall_640 | tail-call the locked configuration dispatcher | confirmed | c016e640 branches directly to `cfg_locked_dispatch` |
| c016e660 | sem_post_or_clear_tailcall | tail-call the conditional semaphore-post/local-clear helper | confirmed | c016e660 branches directly to `sem_post_or_clear` |
| c016e680 | arena_copy_default_0e40 | tail-call the arena/ring copy body, defaulting B4 to c0180e40 | confirmed | c016e680 branches to `arena_copy_body`; B4!=0 -> preserve B4; B4==0 -> c016e690 selects c0180e40 |
| c016e6a0 | return_true_thunk | call the return-true callback and return its value | confirmed | c016e6a4 calls c016e540 with A4=1; c016e6ac-c016e6b4 return the resulting A4 |
| c016e6e0 | arena_copy_default_1180 | tail-call the arena/ring copy body, defaulting B4 to c0181180 | confirmed | c016e6e0 branches to `arena_copy_body`; B4!=0 -> preserve B4; B4==0 -> c016e6f0 selects c0181180 |
| c016e700 | struct_word0_get | return word 0 of the object at A4 | confirmed | c016e700 `LDW *+A4[0],A4`; c016e704 returns |
| c016e720 | arena_copy_default_027c | tail-call the arena/ring copy body, defaulting B4 to c018027c | confirmed | c016e720 branches to `arena_copy_body`; B4!=0 -> preserve B4; B4==0 -> c016e730 selects c018027c |
| c016e740 | event_table_halfword_get | return the halfword at offset 12 in an event-table entry selected by byte offset A4 | likely | c016e740-c016e748 load table base from c0180714; c016e750 adds A4; c016e754 `LDHU *+A3[6]` uses scaled 12-byte offset |
| c016e780 | menu_commit_0ec0 | tail-call the shared menu-item commit helper using descriptor c0180ec0 | likely | c016e780 branches to `menu_item_commit_shared`; delay slots set B4=input A4, A4=c0180ec0, A6=0, B6=-1 |
| c016e7c0 | self_pointer_test | return whether object word 0 points to the object itself | confirmed | c016e7c0 loads `*A4`; equal -> c016e7d0 returns 1; unequal -> c016e7cc returns 0; host row excludes hidden c016e7e0 |
| c016e7e0 | menu_commit_0ec0_global_offset | add the base from c0180a24 to A4 and commit through descriptor 0ec0 | likely | hidden start; c016e7e4-c016e7ec load `*c0180a24`; c016e7f0 calls c016e780 with c016e7f4 `ADD A3,A4,A4` |
| c016e800 | arena_copy_default_0b7c | tail-call the arena/ring copy body, defaulting B4 to c0180b7c | confirmed | c016e800 branches to `arena_copy_body`; B4!=0 -> preserve B4; B4==0 -> c016e810 selects c0180b7c |
| c016e820 | struct_halfword12_get | return the unsigned halfword at object byte offset 12 | confirmed | c016e820 `LDHU *+A4[6],A4`; LDHU index 6 is scaled to 12 bytes |
| c016e840 | runtime_flag_20b4_test_and_set | return halfword c01820b4 and replace it with 1 | confirmed | c016e840-c016e84c load the old halfword from c01820b4; c016e850 stores 1 there |
| c016e8a0 | arena_copy_default_00f4 | tail-call the arena/ring copy body, defaulting B4 to c01800f4 | confirmed | c016e8a0 branches to `arena_copy_body`; B4!=0 -> preserve B4; B4==0 -> c016e8b0 selects c01800f4 |
| c016e8c0 | return_true_call_thunk | call `return_true` and return its result | confirmed | c016e8c0 preserves B3 in A0; c016e8c4 calls c016e2e0; c016e8c8 returns through A0 |
| c016e8e0 | runtime_flag_20dc_test_and_set | return halfword c01820dc and replace it with 1 | confirmed | c016e8e0-c016e8ec load the old halfword from c01820dc; c016e8f0 stores 1 there |
| c016e900 | struct_word52_get | return object word 13 at byte offset 52 | confirmed | c016e900 `LDW *+A4[13],A4`; word index 13 is scaled to 52 bytes |
| c016e920 | runtime_word_20ec_get | return the word stored at c01820ec | confirmed | c016e920-c016e928 form c01820ec and load A4 from it |
| c016e960 | runtime_word_2130_set | store A4 at c0182130 | confirmed | c016e960-c016e968 form c0182130 and `STW A4,*A3` |
| c016e980 | gate_hwi_enter | enter the global Hwi gate and return the prior CSR key | confirmed | c016e984-c016e990 load the gate handle from c0181a44 and call c016eb60, which tail-calls `interrupts_disable_save_csr` |
| c016e9a0 | gate_hwi_leave | leave the global Hwi gate by restoring the CSR key in A4 | confirmed | c016e9a4-c016e9b4 load handle c0181a44, copy caller A4 to B4, and call c016eb80 -> `csr_restore` |
| c016ea20 | csr_restore_tailcall | tail-call CSR restore | confirmed | c016ea20 branches directly to c016e4e0 `csr_restore` |
| c016ea40 | struct_halfword32_clear | return the halfword at byte offset 32 and clear it | confirmed | c016ea48 loads `LDHU *+A3[16]` (scaled 32-byte offset); c016ea4c stores zero there |
| c016ea60 | struct_halfword32_set | return the halfword at byte offset 32 and replace it with 1 | confirmed | c016ea68 loads `LDHU *+A3[16]` (scaled 32-byte offset); c016ea6c stores 1 there |
| c016ea80 | multi_dispatch_zero_optional_args | call the multi-dispatch routine with optional A8, B8, and A10 arguments zero | confirmed | c016ea84 calls c0161540; parallel c016ea88-c016ea90 set A10=0, A8=0, and B8=0 |
| c016eaa0 | multi_dispatch_zero_tail_args | call the multi-dispatch routine with B8 and A10 zero while preserving A8 | confirmed | c016eaa4 calls c0161540; parallel c016eaa8/c016eaac set A10=0 and B8=0, with no A8 write |
| c016eac0 | virtual_method2_tailcall | tail-call object virtual method slot 2 | confirmed | c016eac0 branches to c016e9c0, whose c016e9c0/c016e9c8 load the vtable from object word 0 and target from vtable word 2 before branching indirectly |
| c016eae0 | virtual_method3_tailcall | tail-call object virtual method slot 3 | confirmed | c016eae0 branches to c016e9e0, whose c016e9e0/c016e9e8 load the vtable from object word 0 and target from vtable word 3 before branching indirectly |
| c016eb00 | runtime_word_21e0_get | return the word stored at c01821e0 | confirmed | c016eb00-c016eb08 form c01821e0 and load A4 from it |
| c016eb20 | xdc_startup_exec_15 | execute XDC/BIOS startup with a 15-word local work buffer | likely | c016eb20 allocates 72 stack bytes; c016eb24-c016eb2c call `xdc_runtime_startup_exec` with B4=15 and A4=B15+8 |
| c016eb40 | runtime_flag_1a3c_is_set | return whether word c0181a3c is nonzero | confirmed | c016eb40-c016eb48 load the word; value==0 -> c016eb50/c016eb54 return 0; value!=0 -> return 1 |
| c016eb60 | interrupts_disable_save_csr_tailcall | tail-call interrupt disable and return the previous CSR | confirmed | c016eb60 branches directly to c016e4c0 `interrupts_disable_save_csr` |

## Data


## Open questions
