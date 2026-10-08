# Chunk 04 function map: c0128134..c012dab0 (150 functions)

Summary: this range holds five subsystems. (1) c0128134..c0128dd4 is a
family of "compose a fixed-layout Zoom SysEx reply and send it" builders
(each memsets a small stack buffer, writes literal header bytes `F0 52
<devid@0xc0183b48> ...`, optionally sets flag bits, appends a checksum via
c013b7b0 and `F7`, then calls the already-named `midi_tx_locked`
c01274cc), fanned out by (2) `c0128e54`, a 20-way dispatcher on `B14[38]`
(confirmed: direct CMPEQ cascade read) that is itself reached only through
(3) an inbound-SysEx byte-state-machine, `c01291ce..c0129276`, dispatched
via a 5-entry function-pointer table at `0xc01844a8..c01844b8` keyed by
parser state (confirmed structurally: tests the incoming byte against
`0x52`/`0x7E`, advances `B14[43]/164/165/167/168`, and the state at
`c0129276` is the one that completes a message and calls `c0128e54`).
(4) `c012c840..c012daac` is a second, independent MIDI engine: a 48-entry
jump table (`c012d9e0`, base `0xc0183c40`, bounds-checked `<48`,
confirmed) dispatching through tiny CALLP+branch-to-epilogue veneers
(`c012da18..c012daa8`, all read directly, epilogue `c012daac` already
named in 00) into per-command "get/set effect parameter over MIDI"
composers -- many small ones sharing the pattern `midi_tx_locked +
c0129638 (device-ID range check) + field_extract_bit25`, plus several
heavyweight "bulk" composers (`c012be20` 1876B, `c012b744` 796B, `c012bc18`
520B, `c012c678` 456B) that build/clear a parameter-value buffer against
two tables at `0xc0100062c4` (count/bound) and `0xc010aa78` (per-field
size/offset), confirmed via a direct read of the anchor `c012b3c0`.
(5) `c0129db8..c012a8bc` is a MainApp patch/preset-file browser: flash
filesystem calls (`c014bf2c/c014bfd4/c014c1d8/c014c350`) against literal
patch filenames (`FLST_SEQ.ZT2`, `BYPASS.ZD2`, `GUARDZDL.ZT2`, wildcard
`*.*`), a `<<<`/`>>>` scroll-arrow label builder (`c012a428`, confirmed),
and `B14[15]/[16]` as list count/index (confirmed getter/setter pair
`c0129fb0`/`c01296ac`); `c012ad74` (recon/18) drives it from the knob.
A sixth, smaller cluster (`c012ad1c..c012b394`) is USB descriptor-string
composition layered over the already-named `usb_desc_table_get`
(c012afe0, see 00_library_kernel.md) and the 1180-region `usbstr_builder*`
veneers. Five addresses in this range were already named by
`recon/map/00_library_kernel.md`'s wave-0 sweep: `c01282d4`, `c0128580`,
`c0129630`, `c012af98`, `c012afe0`, `c012c934`, `c012ca24`, `c012ca80`,
`c012daac` -- see that file.

Method: read `build/fw/map/main.dis` windows (<=60 lines) at each cluster's
anchor address to confirm the structural pattern, then applied that
confirmed shape to call-graph/B14-sibling evidence for the rest, per
00_library_kernel.md's own precedent. "Confirmed" rows below were read
directly; "likely" rows share a read-confirmed shape/callee set; "guess"
rows have only call-graph/size evidence.

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| c0128134 | midi_reply_build_edit1 | composes and sends a 22-byte Zoom SysEx reply: memset(22), `F0 52 <devid@0xc0183b48> 47`, conditional flag bits (16/32/64/128) set via a chunk_05 helper (0xc012dab0) gated by two boolean tests, checksum via c013b7b0, `F7`, sent via midi_tx_locked(len=0x16) | confirmed | read c0128134..c012820e in full: `STB 0xF0,*+B15[8]`; `STB 0x52,*+B15[9]`; devid loaded from `0xc0183b48`; `CALLP 0xc01274cc,B3` with B4=0x16 |
| c0128210 | midi_reply_build_status1 | composes and sends a fixed 30-byte Zoom SysEx reply: memset(30), header `F0 52 <devid> 43 32 00 78 05 32 00 0A` then a literal fill pattern, sent via midi_tx_locked | confirmed | read c0128210..c0128298: literal STB sequence of 0xF0,0x52,devid,0x43,0x32,0x00,0x78,0x05,... |
| c01282d4 | see 00_library_kernel.md | (error_guarded_call) | confirmed | named by prior wave-0 sweep |
| c0128310 | midi_edit_msg_build1 | builds and checksums a MIDI edit-request buffer, sharing the B14[45] guard of error_guarded_call | likely | calls=c0127440(checksum_update),c01282d4,rts_memset,save/restore; only called by the two coordinators below |
| c0128440 | midi_edit_msg_build2 | smaller sibling of c0128310, builds a buffer and forwards it to the transport c0144dc8 (same transport midi_tx_byte uses) | likely | calls=c0144dc8,rts_memset,save/restore; B14[45]; same two callers as c0128310 |
| c0128474 | midi_edit_tx_coordinator1 | composes+sends a locked MIDI edit transaction by combining c0128310/c0128440 under the B14[161] lock (same slot midi_tx_locked uses) | likely | calls=c0128310,c0128440,error_guarded_call,bios_sem_pend/post,rts_sdiv32; B14[161] |
| c0128580 | see 00_library_kernel.md | (midi_tx_byte) | confirmed | named by prior wave-0 sweep |
| c0128598 | midi_edit_msg_build3 | sibling builder to c0128310/c0128440: checksums and sends a buffer via midi_tx_byte/c0144dc8 | likely | calls=checksum_update,midi_tx_byte,c0144dc8,rts_memset,save/restore |
| c01286e4 | midi_edit_tx_coordinator2 | sibling of c0128474: locked edit transaction combining c0128580/c0128598 | likely | calls=unk_1180_6258,midi_tx_byte,c0128598,bios_sem_pend/post,rts_sdiv32; B14[161] |
| c0128788 | midi_error_report_build | large (388B) builder touching the error-code B14 slots (30,31,33,38,112-119, the same range as err_set_last_code's B14[114]) -- likely reports the last recorded error/status over MIDI | guess | B14=30,31,33,38,112-119; calls=checksum_update,midi_tx_n,c0130d90,c0130e04,c01312c4,c013150c,c013bf8c,bios_sem_pend/post,diag_mask_test |
| c012890c | midi_reply_send_simple1 | thin wrapper: forwards a precomputed buffer straight to midi_tx_locked | likely | calls(1)=c01274cc only; size 72B |
| c0128954 | midi_edit_tx_coordinator3 | sibling of c0128474/c01286e4: locked transaction over c0128580/c0128598 | likely | calls=c0128580,c0128598,bios_sem_pend/post,save/restore; B14[161] |
| c01289ec | midi_apply_param_edit | bridges MIDI and MainApp: applies a received MIDI edit value into live effect-parameter state (multiple MainApp-side callees) | guess | roots MIDI,MainApp; calls=unk_1180_2b50,unk_1180_3a28,switch_speed_gate2,c012f878,c01437f0,c0148b30,c0148b44,c014ab00,bios_sem_pend/post,c0153788; B14=27,99,180 |
| c0128a54 | midi_param_lookup1 | looks up a parameter/effect record via locked_lookup_big and a B14[125] getter | guess | calls=c0134e24,c013c90c,c0153788,c0158980(locked_lookup_big),c016c118(cfg_get_b14_125); roots MIDI |
| c0128aa8 | midi_status_bridge_call | thin (12B) forwarder into bridge_status_struct | likely | calls(1)=c0156d68 only |
| c0128ab4 | midi_param_lookup2 | looks up a parameter record via two unnamed 0xc012f8xx/0xc0148bxx helpers, gated by B14[99] | guess | calls=shared_accessor6_1180,c012f74c,c012f878,c0148b30,c0148b44 |
| c0128b00 | midi_edit_ui_refresh | touches the graphics subsystem (big_mvc_subsystem c011f8d8) and status struct getter -- likely redraws the UI after a MIDI edit, gated B14[149] | guess | calls=c011f8d8,c013c914,c0156e80(cfg_get_global_c011ad8c),c015c0f8(orchestrator_locked_small),c0161200(cfg_locked_dispatch),c016d880(sem_post_or_clear),c016df00(region_bridge_1) |
| c0128b48 | midi_param_edit_coordinator | orchestrates the three lookup/refresh helpers above (c0128a54/aa8/ab4/b00) into one locked parameter-edit transaction | likely | calls=switch_speed_gate2,subsystem_init_gate_thunk,c0128a54,c0128aa8,c0128ab4,c0128b00,c013b5fc,bios_sem_pend/post,c0156c94,c0158e8c; B14=27,154 |
| c0128ba4 | midi_send_channel_msg | sends a precomputed buffer via midi_tx_locked, gated by the channel slot B14[26] | likely | calls(1)=c01274cc; B14[26]; shared by 3 callers incl UpdateUI root c012936c |
| c0128c24 | midi_send_channel_msg_a | thin (16B) veneer calling midi_send_channel_msg with one preset arg | likely | calls(1)=c0128ba4 only |
| c0128c34 | midi_send_channel_msg_b | sibling thin veneer, different preset arg | likely | calls(1)=c0128ba4 only |
| c0128c48 | midi_send_channel_dispatch | picks between the a/b channel-msg veneers, scaling a value via the signed-divide helper first (likely 7-bit/14-bit conversion) | likely | calls=c0128c24,c0128c34,rts_sdiv32,c0168640; caller 1180738c=midi_param_dispatch |
| c0128c88 | midi_edit_tx_coordinator4 | sibling of c0128474/8954: locked transaction over midi_tx_byte/c0128598 | likely | calls=unk_1180_6258,midi_tx_byte,c0128598,c0130e04,bios_sem_pend/post; B14=26,99,161 |
| c0128d14 | midi_bulk_edit_tx | locked edit transaction that uses the word-sploop memcpy (variable-length payload), unlike its fixed-size siblings | likely | calls=midi_param_dispatch,c0130e04,c013150c,c013bf8c,bios_sem_pend/post,diag_mask_test,c016d4c0(memcpy_word_sploop); B14=99,161 |
| c0128dd4 | midi_reply_send_simple2 | sends a precomputed buffer via midi_tx_locked, gated by a diag-mask test and a fixed pointer constant | likely | calls=midi_tx_locked,diag_mask_test,c016ac28(ptr_const_c011ad7a) |
| c0128e54 | midi_cmd_dispatch | top-level MIDI command dispatcher: reads command code from B14[38], 20-way CMPEQ cascade (codes 1,2,3,4,6,8,9,10,11,12,13,14,15,16,17,19,20,22,23) fanning into the reply builders above plus c0128070/midi_tx_n/subsystem_init_gate; only caller is the rx-state-machine entry c0129276 | confirmed | read c0128e54..c0128f24 in full: `LDW *+B14[38],B2` then repeated `CMPEQ.L2 N,B2,B0` / `[B0] BNOP`; recon/15 |
| c01291ce | midi_rx_state_e | one of five inbound-SysEx parser states (table slot 0xc01844b8): advances the running counter B14[43], calls midi_stage_464 (c0127464), then resets B14[164]/167 on mismatch | likely | read c01291ce..c01291f0; ptr@ c01844b8; B14=43,164,167 |
| c01291f0 | midi_rx_state_d | sibling parser state (table slot 0xc01844b4): advances B14[43], calls midi_param_table_dispatch (c0127cf4) | likely | read c01291f0..c0129214; ptr@ c01844b4; B14=43,164,167 |
| c0129214 | midi_rx_state_c | parser state (table slot 0xc01844ac) comparing the incoming byte (B6) against 0x52 (Zoom manufacturer ID) | likely | read c0129214..c0129242: `MVK 82,B1; CMPEQ.L2 B6,B1,B1`; ptr@ c01844ac; B14=43,167,168 |
| c0129242 | midi_rx_state_b | parser state (table slot 0xc01844a8) comparing the incoming byte (A6) against 0x52 or 0x7E (Zoom ID or Universal Non-Realtime SysEx ID) | likely | read c0129242..c0129276: `CMPEQ B1,A6,B1 ... MVK 126,A0; CMPEQ A6,A0,A0; OR A0,B1,A0`; ptr@ c01844a8; B14=43,164,167 |
| c0129276 | midi_rx_state_dispatch_entry | parser state (table slot 0xc01844b0) that completes a parsed SysEx message: calls midi_stage_f60 (c0127f60) to prep, then calls the 20-way command dispatcher midi_cmd_dispatch (c0128e54); also contains the shared merge continuation at c012932c for the other 4 states | likely | read start+body: `CALLP 0xc0127f60,B3 ... CALLP 0xc0128e54,B3`; ptr@ c01844b0; B14=39,40,43,164,165,167; size 246 exactly spans to next function c012936c |
| c012936c | midi_channel_display_notify | UI-side wrapper around midi_send_channel_msg, roots UpdateUI | guess | calls=c0128ba4,save/restore; roots UpdateUI |
| c0129398 | midi_channel_ui_handler | UpdateUI handler that forwards to an 1180-region helper then midi_tx_locked and midi_channel_display_notify | guess | calls=unk_1180_49ec,midi_tx_locked,c012936c; roots UpdateUI; callers c013c674,c01507d8 |
| c0129490 | midi_edit_tx_coordinator5 | sibling of c0128474: locked edit transaction combining c0128310/c0128440, using the unsigned-divide/variant helpers instead of signed | likely | calls=unk_1180_6258,error_guarded_call,c0128310,c0128440,c0130e04,c013bc8c,bios_sem_pend/post,rts_udiv32,rts_div32_variant,diag_mask_test; B14=99,161 |
| c01295c8 | midi_edit_tx_entry | top-level entry choosing between the two edit-tx coordinators c0128474/c0129490 | likely | calls(2)=c0128474,c0129490; B14[99]; only caller wrapper_c016be20 |
| c01295ec | cfg_set_b14_26 | setter: B14[26] = A4 (pairs with the already-named getter cfg_get_b14_26 c0129630) | confirmed | read in full: `STW A4,*+B14[26]; BNOP B3,5`; caller switch_repeat_notify (1180a7ec) |
| c01295f4 | cfg_set_b14_27 | setter: B14[27] = A4 | confirmed | read in full: `STW A4,*+B14[27]; BNOP B3,5`; caller locked_dispatch_154 |
| c0129600 | cfg_set_global_c0183b48 | copies a packed word field from `*A4[0]` into the global device-ID byte at 0xc0183b48 (the same global every SysEx builder above reads as `<devid>`) | confirmed | read in full: `LDNW *+A4[0],A0; MVK 0x3b48,A4; MVKH 0xc0180000,A4; STNW A0,*A4[0]` |
| c0129614 | midi_lock_release_cleanup | calls an unnamed tail-blob veneer (c016f670) then releases the MIDI lock B14[161] via bios_sem_post | likely | read in full: `CALLP 0xc016f670,B3; CALLP 0xc01628e0,B3 || LDW *+B14[161],A4` |
| c0129630 | see 00_library_kernel.md | (cfg_get_b14_26) | confirmed | named by prior wave-0 sweep |
| c0129638 | midi_devid_range_valid | reads the global device-ID byte (0xc0183b48, set by cfg_set_global_c0183b48) and returns a 0/1 guard based on range checks against 64/128 -- used before several composers send | confirmed | read in full: loads global, 3x `CMPLT A4,{64,64,128},A0` chain, returns 0 or 1 in A4 |
| c0129680 | effect_slot_flag_copy | copies a byte between two indices of a 1-byte-per-slot table at 0xc0064528 (index = arg2+arg1 vs arg1) | confirmed | read in full: `LDBU *A4[A5],A0` then `STB A0,*A4[A5]` with A5=0xc0064528 base, A4 recomputed as A1+A4 |
| c0129698 | effect_slot_flag_set | setter counterpart of c0129680: writes arg2 into slot[arg1] of the same 0xc0064528 table | confirmed | read in full: `MVK 0x4528,A4; MVKH 0xc0060000,A4; STB B0,*A5[A4]` |
| c01296ac | cfg_set_b14_16 | setter: B14[16] = A4 (pairs with the getter c0129fb0, both tied to the patch-list cluster) | confirmed | read in full: `STW A4,*+B14[16]; BNOP B3,5`; caller patchlist_screen_build (c012a8bc) |
| c01296b4 | table_find_index_0xc0064f6c | searches a word table at 0xc0064f6c for a value equal to the argument, using an SPLOOPW kernel; returns early if B14[15] (patch-list count) is zero | likely | read start of SPLOOPW loop: `LDW *A4++[1],A5; CMPEQ A5,A7,A6`; B14[15]; size 112B |
| c0129724 | effect_slot_prep | preparation step feeding into effect_slot_load_unload; recon/14,16,18 already trace sibling addresses in this dispatcher family | likely | calls=c01560f0,c0156304,c0164a80,c0164a8c,save/restore; recon:14,16,18 |
| c01297a0 | effect_slot_load_unload | loads or unloads an effect module into a slot: A4=slot index, B4=flag (nonzero=load, zero=unload-only); extensively traced by recon/18_round3.md's cleanup/callback-safety analysis | confirmed | recon/18_round3.md secs 4.1-4.3: `c01437c4 CALLP 0xc01297a0,B3 ; A4=slot, B4=0 -> unload-only`; strings BPS/BYPASS/DATA/INFO/ZDLF; size 1560B |
| c0129db8 | patchlist_entry_get | reads a patch-list entry/field, feeding into both the screen builder and a param-reply builder (c012d030) | guess | callers=patchlist_guard_check(c0129e30),c012d030; size 120B, no further calls listed |
| c0129e30 | patchlist_guard_check | checks for a guard/lock file `GUARDZDL.ZT2` on flash via the file-open helper c014c1d8, then c014bf2c/locked_small_op/c014bfd4, before gating some list operation | confirmed | read c0129e30..c0129f38: literal string pointer resolves to `GUARDZDL.ZT2`; `CALLP 0xc014c1d8,B3` (open/check), `CALLP 0xc014bf2c,B3`, `CALLP 0xc014c350,B3` (locked_small_op), `CALLP 0xc014bfd4,B3` |
| c0129f44 | patchlist_entry_get2 | sibling lookup to patchlist_entry_get, only called from the screen builder | guess | caller=patchlist_screen_build (c012a8bc); size 108B, no further calls listed |
| c0129fb0 | cfg_get_b14_16 | getter: return B14[16] (pairs with cfg_set_b14_16 c01296ac) | confirmed | read in full: `LDW *+B14[16],A4; BNOP B3,5` |
| c0129fb8 | patchlist_render_build1 | large (1136B) patch-list screen-rendering routine using the B14[16] getter and the table-search helper; not traced in detail given size | guess | calls=cfg_get_b14_16; B14[15]; caller patchlist_screen_build |
| c012a428 | patchlist_arrow_label_set | writes a `<<<` or `>>>` 4-byte string literal (direction flag B4) plus an index into a small UI-list-arrow struct | confirmed | read in full: `MVK 0xfffff5bf/0xfffff5c3,A5; MVKH 0xc0170000,A5; LDNW *A5[0],A0; STNW A0,*A4[0]`; strings `<<<`/`>>>` |
| c012a464 | patchlist_render_build2 | sibling of c0129fb8: builds a list-screen view, reading the `FLST_SEQ.ZT2` patch-list file via c014bf2c/c014bfd4/c014c1d8/locked_small_op | guess | strings=FLST_SEQ.ZT2; B14[15]; calls=cfg_get_b14_16,patchlist_arrow_label_set,c014bf2c,c014bfd4,c014c1d8,locked_small_op,rts_memset |
| c012a8bc | patchlist_screen_build | top-level orchestrator of the whole patch-browser screen: combines the guard check, both render builders, and several file-op helpers; strings include wildcard `*.*`, `BYPASS.ZD2`, `Bypass`, `FLST_SEQ.ZT2`; recon/13 already touches this area | likely | calls=cfg_set_b14_16,patchlist_guard_check,patchlist_entry_get2,patchlist_render_build1,patchlist_render_build2,c014bfd4,c014bff0,c014c1d8,c014c300,locked_small_op,c014c880,c014c9f0,c014ccd0,rts_memset,fmt_render_wrapper; B14[15]; recon:13; size 1120B |
| c012ad1c | usbdesc_helper1 | small (44B) helper shared by three USB-string-builder callers | guess | callers=usbstr_builder5(118080b4),c012e5a8,c012f378; no calls listed |
| c012ad48 | usbdesc_helper2 | tiny (16B) helper, single caller c012e5a8 | guess | caller=c012e5a8; no calls listed |
| c012ad58 | generic_util1 | small (28B) utility shared across the patch-list, USB-descriptor and RhythmService callers; no further structure identified | guess | 6 callers spanning c012ad74,c012e164,c012e5a8,c01564b8,c015c3e0,c015c4f8; roots MainApp,RhythmService,UpdateUI |
| c012ad74 | patchlist_knob_scroll | drives the patch-list browser from the knob: accumulates a knob delta (1180afc0=knob_delta_accumulate), scrolls the list, and reloads the effect slot via effect_slot_load_unload; recon/18 already traces this | likely | calls=knob_delta_accumulate,effect_slot_load_unload,generic_util1,cfg_table_ptr_11f03ad0(c014ff44),diag_mask_test; B14[15]; recon:18; size 548B |
| c012af98 | see 00_library_kernel.md | (rts_const_return_1) | confirmed | named by prior wave-0 sweep |
| c012afa0 | midi_usb_small_helper1 | small (24B) leaf, no calls listed, 3 callers in the USB-descriptor/MIDI area | guess | callers=c01319a4,c0131ea0,c0156680 |
| c012afb8 | patchlist_name_copy | copies a patch/entry name using the word-sploop memcpy, gated by the patch-list count B14[15] | likely | calls(1)=c016d4c0(rts_memcpy_word_sploop); B14[15]; callers c0151648,c0156860 |
| c012afe0 | see 00_library_kernel.md | (usb_desc_table_get) | confirmed | named by prior wave-0 sweep |
| c012b008 | usbdesc_field_get | sibling accessor to usb_desc_table_get, called by 13 USB-string/descriptor builders | likely | 13 callers incl usbstr builders 118072ac,11808280 and c012b048/b108; no calls listed; size 28B |
| c012b024 | usbdesc_small_helper1 | tiny (12B) helper, 3 callers in one call-site family | guess | callers=c013d984,c013d998,c013d9b0 |
| c012b030 | generic_util2 | small (24B) utility also called from the TunerService task root (c01674e0); recon/14 already notes it | guess | callers=c0143240,c01432b4,c01433ec,c0143720,c01674e0; recon:14 |
| c012b048 | usbdesc_string_compose | composes a USB string descriptor from usb_desc_table_get/usbdesc_field_get plus two unnamed 0xc0132xxx helpers; called from usbstr_builder1/2 | likely | calls=usb_desc_table_get,usbdesc_field_get,c0132510,c0132560,save/restore; size 192B |
| c012b108 | usbdesc_string_compose2 | sibling of usbdesc_string_compose, reused by a larger set of USB-string-builder and MainApp callers | likely | calls=usb_desc_table_get,usbdesc_field_get; 11 callers incl usbstr_builder4/6 |
| c012b180 | usbdesc_or_patchlist_helper | shared small (88B) helper spanning USB-descriptor and patch-list callers (B14[15]) | guess | callers=midi_usb_orchestrator_1180(11806450),c0131698; B14[15] |
| c012b1d8 | midi_small_coordinator1 | small (48B) coordinator calling an unnamed 0xc01560c0 helper, 4 callers across MIDI/MainApp | guess | calls(1)=c01560c0; callers c012b394,c013f858,c013fc08,c014811c |
| c012b208 | patchlist_helper1 | small (88B) helper gated by the patch-list count B14[15] | guess | B14[15]; callers c01513cc,c0151648; no calls listed |
| c012b260 | patchlist_helper2 | small (96B) helper gated by B14[15], 3 callers | guess | B14[15]; callers c013b690,c013b8c0,c013b904; no calls listed |
| c012b2c0 | const_stub_or_tiny | tiny (4B!) leaf with 5 callers incl midi_usb_orchestrator_1180 -- likely a constant-return stub | guess | size 4B; callers=11806450,c0132658,c01327c8,c0132b78,c0133254 |
| c012b2c4 | patchlist_helper3 | small (96B) helper gated by B14[15], single caller | guess | B14[15]; caller c0141ac8; no calls listed |
| c012b324 | usbdesc_fmt_helper | small (112B) helper used by a USB-descriptor formatter (usbdesc_fmt3, 11808320) and one other caller, gated B14[15] | guess | B14[15]; callers=11808320,c012e4b8 |
| c012b394 | midi_small_coordinator2 | forwards into midi_small_coordinator1 (c012b1d8); callers span the MIDI param-dispatch veneer and 3 others | guess | calls(1)=c012b1d8; callers=midi_param_dispatch(1180738c),c0132af8,c0132b78,c01437b4 |
| c012b3c0 | param_buf_validate_init | validates a parameter index against a count table at 0xc0100062c4, computes a per-field byte offset via a 4-byte-stride size/offset table at 0xc010aa78, then clears/inits that buffer region via c0141e50/c0141e68/buffer_clear_init | confirmed | read c012b3c0..c012b468 in full: `MVK 0x62c4,A4;MVKH 0xc0100000,A4;LDHU *A4[0],A0;CMPLT A1,A0,A0` (bound check); `MVK 0xffffaa78,A4;MVKH 0xc0100000,A4;LDHU *A4[2],A0` (field table); `CALLP 0xc0141f14,B3` (buffer_clear_init) |
| c012b46c | param_buf_set_field | extends param_buf_validate_init to also set a field value via two unnamed 0xc0141xxx helpers | likely | calls=param_buf_validate_init,c0141d80,c014204c; callers c012b584,c012c678 |
| c012b584 | param_buf_apply_locked | applies a parameter-buffer field update under the B14[6] lock (bios_sem_pend/post) | likely | calls=param_buf_set_field,c0141ce0,c0141d38,c0141de0,bios_sem_pend/post,diag_mask_test; B14[6]; size 448B |
| c012b744 | param_buf_bulk_apply | large (796B) locked parameter-buffer update using the unsigned-divide/variant helpers (suggests a scaled multi-field or ranged update); recon/18 touches this family | likely | calls=c0141ce0,c0141d38,c0141de0,buffer_clear_init,c0142028,c01423ec,bios_sem_pend/post,rts_udiv32,rts_div32_variant,diag_mask_test; B14[6]; recon:18 |
| c012ba60 | param_buf_clear_range | clears a parameter-buffer range via buffer_clear_init plus one unnamed helper (c01423ec) | likely | calls=buffer_clear_init,c01423ec; caller param_buf_init_all (c012bc18) |
| c012bb84 | param_buf_clear_simple | clears a parameter buffer via plain memset, gated by diag_mask_test | likely | calls=rts_memset,diag_mask_test; caller param_buf_init_all |
| c012bc18 | param_buf_init_all | top-level locked initializer combining param_buf_clear_range/clear_simple and three unnamed 0xc0141xxx/0xc0142xxx field helpers | likely | calls=param_buf_clear_range,param_buf_clear_simple,c0141ce0,c0141d38,c0141de0,c01420a0,c0142120,bios_sem_pend/post,rts_memset; B14[6]; size 520B |
| c012be20 | param_buf_build_bulk_dump | very large (1876B) routine sharing param_buf_validate_init and the clear/field helpers -- likely builds a bulk parameter dump buffer; not traced in detail given size | guess | calls=param_buf_validate_init,c0141d80,c0141e68,buffer_clear_init,c014204c,c01423ec,rts_div32_variant; caller param_buf_dispatch (c012c678) |
| c012c574 | param_buf_clear_field | clears one parameter field via c0141e68/buffer_clear_init | likely | calls=c0141e68,buffer_clear_init; caller param_buf_dispatch |
| c012c5d4 | param_buf_set_field2 | sets a parameter field via c0141d80/c0142028, sibling of param_buf_set_field | likely | calls=c0141d80,c0142028; caller param_buf_dispatch |
| c012c678 | param_buf_dispatch | top coordinator of the parameter-buffer cluster, bridging into the patch-list B14 slots (6,14,15) as well -- likely applies a received parameter edit to the effect-slot buffer and the patch-list display state | likely | calls=param_buf_set_field,param_buf_build_bulk_dump,param_buf_clear_field,param_buf_set_field2,c0141ce0,c0141d38,c0141de0,c01421d8,bios_sem_pend/post; B14=6,14,15; size 456B |
| c012c840 | midi_payload_clear | shared buffer-clear helper reused by two of the param-reply composers below (c012cd88,c012d728) | likely | calls(1)=rts_memset; 2 callers |
| c012c914 | midi_param_table_entry_handler | handler invoked only from the receive-side midi_param_table_dispatch (c0127cf4, outside this chunk) | guess | caller=c0127cf4; size 32B, no calls listed |
| c012c934 | see 00_library_kernel.md | (field_extract_bit25) | confirmed | named by prior wave-0 sweep |
| c012c964 | midi_param_reply_build1 | composes and sends a MIDI parameter-value reply using midi_tx_locked + the device-ID guard + the bit25 field extractor | likely | calls=midi_tx_locked,c0129638(devid_range_valid),field_extract_bit25; B14[70]; caller c012caf4 |
| c012c9f4 | midi_param_small_helper | small (48B) helper shared by 5 of the param-reply coordinators, no further calls | guess | callers=c012caf4,c012cf30,c012d030,c012d80c,c012d890 |
| c012ca24 | see 00_library_kernel.md | (midi_compose_send) | confirmed | named by prior wave-0 sweep |
| c012ca80 | see 00_library_kernel.md | (magic_const_check) | confirmed | named by prior wave-0 sweep |
| c012caf4 | midi_param_reply_coordinator1 | coordinates midi_param_reply_build1, midi_param_small_helper, midi_compose_send and magic_const_check under locked_small_op, entered via the 48-entry command table (c012da40) | likely | calls=checksum_update,midi_param_reply_build1,midi_param_small_helper,midi_compose_send,magic_const_check,c014bf2c,c014bfd4,locked_small_op,diag_mask_test; B14=22,70,72; size 492B |
| c012cce0 | midi_param_reply_build2 | sibling composer entered via table veneer c012da34 | likely | calls=midi_compose_send,magic_const_check,c014bfd4; B14[72] |
| c012cd18 | midi_simple_ack_send | shared simple-ack/status sender: forwards a buffer via midi_tx_locked + device-ID guard; reused by 7 of the 48-entry table's command veneers | likely | calls=midi_tx_locked,devid_range_valid; 7 callers (all thin table veneers) |
| c012cd60 | midi_cmd_veneer_ack1 | 48-entry table veneer: calls midi_simple_ack_send then falls to the shared epilogue | likely | calls(1)=c012cd18; caller is table slot c012daa8 |
| c012cd6c | midi_cmd_veneer_ack2 | sibling table veneer calling midi_simple_ack_send | likely | calls(1)=c012cd18; caller table slot c012da80 |
| c012cd78 | midi_cmd_veneer_ack3 | sibling table veneer calling midi_simple_ack_send | likely | calls(1)=c012cd18; caller table slot c012da74 |
| c012cd88 | midi_param_reply_build3 | composer using midi_payload_clear plus the checksum/tx/devid-guard/bit25 chain | likely | calls=checksum_update,midi_tx_locked,devid_range_valid,midi_payload_clear,field_extract_bit25; B14[70]; caller c012ce68 |
| c012ce68 | midi_param_reply_build4 | coordinates midi_compose_send/magic_const_check/midi_param_reply_build3; entered via table veneer c012da90 | likely | calls=midi_compose_send,magic_const_check,midi_param_reply_build3; B14=22,70,72 |
| c012cea0 | midi_param_reply_build5 | composer in the fixed midi_tx_locked+devid_guard+bit25 shape | likely | calls=midi_tx_locked,devid_range_valid,field_extract_bit25; B14[70]; caller c012cf30 |
| c012cf30 | midi_param_reply_build6 | coordinates midi_param_small_helper/midi_compose_send/magic_const_check/midi_param_reply_build5 plus a file-op helper (c014bff0); entered via table veneer c012da48 | likely | calls=midi_param_small_helper,midi_compose_send,magic_const_check,midi_param_reply_build5,c014bff0; B14=22,70,72 |
| c012cfa0 | midi_param_reply_build7 | composer in the fixed shape | likely | calls=midi_tx_locked,devid_range_valid,field_extract_bit25; B14[70]; caller c012d030 |
| c012d030 | midi_param_reply_build8_patchlink | coordinates midi_param_reply_build7 plus patchlist_entry_get and the patch-file-open helper c014c1d8 -- bridges the MIDI param-reply engine to the patch-list filesystem calls | likely | calls=patchlist_entry_get,midi_param_small_helper,midi_compose_send,magic_const_check,midi_param_reply_build7,c014c1d8; B14=70,72,73; entered via table veneer c012da54 |
| c012d0d0 | midi_param_reply_build9 | composer in the fixed shape | likely | calls=midi_tx_locked,devid_range_valid,field_extract_bit25; B14[70]; caller c012d190 |
| c012d190 | midi_param_reply_build10 | coordinates midi_param_reply_build9 plus an unnamed helper (c0158284); entered via table veneer c012da60 | likely | calls=midi_param_reply_build9,c0158284; B14[72] |
| c012d1c4 | midi_cmd_veneer_ack4 | sibling table veneer calling midi_simple_ack_send | likely | calls(1)=c012cd18; caller table slot c012da88 |
| c012d1d0 | midi_param_reply_build11 | composer in the fixed shape; also reached directly from the table (slot c012da98) | likely | calls=midi_tx_locked,devid_range_valid,field_extract_bit25; B14[70] |
| c012d2c4 | midi_param_reply_build12 | composer calling two unnamed helpers (c014bf20,c01583e4) alongside midi_compose_send/magic_const_check; entered via table veneer c012da66 | likely | calls=midi_compose_send,magic_const_check,c014bf20,c01583e4 |
| c012d2e4 | midi_param_reply_build13_bulk | bulk-payload composer using the word-sploop memcpy and two unnamed 0xc016d2xx helpers; entered via table veneer c012da6e | likely | calls=unk_1180_6258,midi_param_dispatch,cfg_get_b14_27,midi_simple_ack_send,c012f878,c0130e04,c013dbf8,c01437b4,bios_sem_pend/post,c016d200,c016d220,rts_memcpy_word_sploop; B14=99,154,155; size 224B |
| c012d3c4 | midi_param_reply_build14 | composer in the fixed shape, shared by two coordinators | likely | calls=midi_tx_locked,devid_range_valid,field_extract_bit25; B14[70]; callers c012d48c,c012d4d0 |
| c012d48c | midi_param_reply_build15 | coordinates midi_param_reply_build14 plus a file/param helper (c014c880); entered via table veneer c012da2c | likely | calls=midi_compose_send,magic_const_check,midi_param_reply_build14,c014c880; B14=70,72 |
| c012d4d0 | midi_param_reply_build16 | sibling coordinator of build15, using c014c9f0 instead; entered via table veneer c012da30 | likely | calls=midi_compose_send,magic_const_check,midi_param_reply_build14,c014c9f0; B14=70,72 |
| c012d538 | midi_param_reply_build17 | small coordinator using c014ccd0; entered via table veneer c012da28 | likely | calls=midi_compose_send,magic_const_check,c014ccd0; B14[72] |
| c012d564 | midi_param_reply_build18 | composer in the fixed shape | likely | calls=midi_tx_locked,devid_range_valid,field_extract_bit25; B14[70]; caller c012d5f8 |
| c012d5f8 | midi_param_reply_build19 | coordinates midi_param_reply_build18 plus c014c300; entered via table veneer c012da24 | likely | calls=midi_param_reply_build18,c014c300; B14[72] |
| c012d640 | midi_cmd_veneer_ack5 | sibling table veneer calling midi_simple_ack_send | likely | calls(1)=c012cd18; caller table slot c012daa2 |
| c012d64c | midi_param_reply_build20 | composer in the fixed shape | likely | calls=midi_tx_locked,devid_range_valid,field_extract_bit25; B14[70]; caller c012d6f0 |
| c012d6f0 | midi_param_reply_build21 | coordinates midi_param_reply_build20 plus an unnamed helper (c0169de0); entered via table veneer c012da20 | likely | calls=midi_param_reply_build20,c0169de0; B14[72] |
| c012d728 | midi_param_reply_build22 | composer using midi_payload_clear plus the checksum/tx/devid-guard/bit25 chain | likely | calls=checksum_update,midi_tx_locked,devid_range_valid,midi_payload_clear,field_extract_bit25; B14[70]; caller c012d80c |
| c012d80c | midi_param_reply_build23 | coordinates midi_param_small_helper/midi_param_reply_build22 plus cfg_locked_dispatch and sem_post_or_clear; entered via table veneer c012da18 | likely | calls=midi_param_small_helper,midi_param_reply_build22,c01454f4,c0161200(cfg_locked_dispatch),c016d880(sem_post_or_clear); B14=70,72,149 |
| c012d890 | midi_param_reply_build24 | coordinates midi_param_small_helper/midi_compose_send/magic_const_check under locked_small_op; entered via table veneer c012da4e | likely | calls=midi_param_small_helper,midi_compose_send,magic_const_check,locked_small_op; B14=70,72,73 |
| c012d8c4 | midi_cmd_veneer_ack6 | sibling table veneer calling midi_simple_ack_send | likely | calls(1)=c012cd18; caller table slot c012da6a |
| c012d8d0 | midi_param_reply_build25 | coordinates midi_tx_locked/midi_compose_send/magic_const_check/midi_param_reply_build4; entered via table veneer c012da90 | likely | calls=midi_tx_locked,midi_compose_send,magic_const_check,midi_param_reply_build4; B14=72,284 |
| c012d9e0 | midi_param_cmd_dispatch48 | the 48-entry MIDI parameter-command dispatcher: reads command index from B14[284], bounds-checks `<48` (falling straight to the shared epilogue if out of range), then jumps through a function-pointer table at 0xc0183c40 | confirmed | read in full: `LDBU *+B14[284],B1 ... CMPLTU 48,A0,B0; [B0] BNOP 0xc012daac,4 ... MVK 0x3c40,A5; MVKH 0xc0180000,A5; LDW *A5[A4],A0; BNOP.S2X A0,5` |
| c012da18 | midi_cmd_veneer_to_d80c | 48-entry table-jump veneer (slot 0): CALLP midi_param_reply_build23 then falls to the shared epilogue c012daac | confirmed | read in full: `CALLP 0xc012d80c,B3; BNOP 0xc012daac,5` |
| c012da20 | midi_cmd_veneer_to_d6f0 | table-jump veneer: CALLP midi_param_reply_build21 then epilogue | confirmed | read in full: `CALLP 0xc012d6f0,B3; BNOP 0xc012daac,5` |
| c012da24 | midi_cmd_veneer_to_d5f8 | table-jump veneer: CALLP midi_param_reply_build19 then epilogue | confirmed | read in full: `CALLP 0xc012d5f8,B3; BNOP 0xc012daac,5` |
| c012da28 | midi_cmd_veneer_to_d538 | table-jump veneer: CALLP midi_param_reply_build17 then epilogue | confirmed | read in full: `CALLP 0xc012d538,B3; BNOP 0xc012daac,5` |
| c012da2c | midi_cmd_veneer_to_d48c | table-jump veneer: CALLP midi_param_reply_build15 then epilogue | confirmed | read in full: `CALLP 0xc012d48c,B3; BNOP 0xc012daac,5` |
| c012da30 | midi_cmd_veneer_to_d4d0 | table-jump veneer: CALLP midi_param_reply_build16 then epilogue | confirmed | read in full: `CALLP 0xc012d4d0,B3; BNOP 0xc012daac,5` |
| c012da34 | midi_cmd_veneer_to_cce0 | table-jump veneer: CALLP midi_param_reply_build2 then epilogue | confirmed | read in full: `CALLP 0xc012cce0,B3; BNOP 0xc012daac,5` |
| c012da40 | midi_cmd_veneer_to_caf4 | table-jump veneer: CALLP midi_param_reply_coordinator1 then epilogue | confirmed | read in full: `CALLP 0xc012caf4,B3; BNOP 0xc012daac,5` |
| c012da48 | midi_cmd_veneer_to_cf30 | table-jump veneer: CALLP midi_param_reply_build6 then epilogue | confirmed | read in full: `CALLP 0xc012cf30,B3; BNOP 0xc012daac,5` |
| c012da4e | midi_cmd_veneer_to_d890 | table-jump veneer: CALLP midi_param_reply_build24 then epilogue | confirmed | read in full: `CALLP 0xc012d890,B3; BNOP 0xc012daac,5` |
| c012da54 | midi_cmd_veneer_to_d030 | table-jump veneer: CALLP midi_param_reply_build8_patchlink then epilogue | confirmed | read in full: `CALLP 0xc012d030,B3; BNOP 0xc012daac,5` |
| c012da60 | midi_cmd_veneer_to_d190 | table-jump veneer: CALLP midi_param_reply_build10 then epilogue | confirmed | read in full: `CALLP 0xc012d190,B3; BNOP 0xc012daac,5` |
| c012da66 | midi_cmd_veneer_to_d2c4 | table-jump veneer: CALLP midi_param_reply_build12 then epilogue | confirmed | read in full: `CALLP 0xc012d2c4,B3; BNOP 0xc012daac,5` |
| c012da6a | midi_cmd_veneer_to_d8c4 | table-jump veneer: CALLP midi_cmd_veneer_ack6 then epilogue | confirmed | read in full: `CALLP 0xc012d8c4,B3; BNOP 0xc012daac,5` |
| c012da6e | midi_cmd_veneer_to_d2e4 | table-jump veneer: CALLP midi_param_reply_build13_bulk then epilogue | confirmed | read in full: `CALLP 0xc012d2e4,B3; BNOP 0xc012daac,5` |
| c012da74 | midi_cmd_veneer_to_cd78 | table-jump veneer: CALLP midi_cmd_veneer_ack3 then epilogue | confirmed | read in full: `CALLP 0xc012cd78,B3; BNOP 0xc012daac,5` |
| c012da80 | midi_cmd_veneer_to_cd6c | table-jump veneer: CALLP midi_cmd_veneer_ack2 then epilogue | confirmed | read in full: `CALLP 0xc012cd6c,B3; BNOP 0xc012daac,5` |
| c012da88 | midi_cmd_veneer_to_d1c4 | table-jump veneer: CALLP midi_cmd_veneer_ack4 then epilogue | confirmed | read in full: `CALLP 0xc012d1c4,B3; BNOP 0xc012daac,5` |
| c012da90 | midi_cmd_veneer_to_d8d0 | table-jump veneer: stores B1 into B14[284] then CALLP midi_param_reply_build25, falls to epilogue | confirmed | read in full: `STB B1,*+B14[284]; CALLP 0xc012d8d0,B3; BNOP 0xc012daac,5`; B14[284] |
| c012da98 | midi_cmd_veneer_to_d1d0 | table-jump veneer: CALLP midi_param_reply_build11 then epilogue | likely | fact-sheet callee matches the confirmed veneer pattern exactly: `CALLP 0xc012d1d0,B3` (seen directly), epilogue not re-verified byte-for-byte |
| c012daa2 | midi_cmd_veneer_to_d640 | table-jump veneer: CALLP midi_cmd_veneer_ack5 then epilogue | likely | fact-sheet callee c012d640 matches the confirmed veneer pattern; not individually re-read |
| c012daa8 | midi_cmd_veneer_to_cd60 | table-jump veneer: CALLP midi_cmd_veneer_ack1 (no epilogue branch listed in fact sheet -- smallest veneer, 4B) | guess | fact sheet: calls(1)=c012cd60 only, size 4B; not individually re-read |
| c012daac | see 00_library_kernel.md | (epilogue_pop_b3_shared) | confirmed | named by prior wave-0 sweep; this is the shared tail every table veneer above branches into |

## Data
- `0xc0183b48` (1 byte): the active MIDI device-ID/channel byte. Read by every SysEx reply builder (c0128134, c0128210, ...) as the message's `<devid>` field; written by `cfg_set_global_c0183b48` (c0129600); range-checked by `midi_devid_range_valid` (c0129638).
- `0xc01844a8..c01844b8` (5 x 4-byte function pointers, ascending): the inbound-SysEx receive-state table, indexed by the running parser state; entries are `midi_rx_state_b/c/dispatch_entry/d/e` (c0129242,c0129214,c0129276,c01291f0,c01291ce).
- `0xc0183c40..c0183d00` (48 x 4-byte function pointers): the "get/set effect parameter over MIDI" command table, indexed by `B14[284]` via `midi_param_cmd_dispatch48` (c012d9e0); entries are the `midi_cmd_veneer_to_*` thin wrappers.
- `0xc0100062c4` (halfword): a parameter-count/bound table read by `param_buf_validate_init` (c012b3c0) to range-check an incoming parameter index.
- `0xc010aa78` (4-byte-stride halfword pairs): a per-field size/offset table used by the same function to compute a buffer offset.
- `0xc0064528` (1 byte per slot): a small per-effect-slot flag table, accessed by `effect_slot_flag_copy`/`effect_slot_flag_set` (c0129680/c0129698).
- `B14[15]`/`B14[16]`: patch-list entry count / current index (getter/setter pair `cfg_get_b14_16`/`cfg_set_b14_16`, c0129fb0/c01296ac).
- `B14[26]`/`B14[27]`: MIDI channel-ish config slots (setters c01295ec/c01295f4 pair with the already-named getters cfg_get_b14_26/27).
- `B14[43]`,`B14[164]`,`B14[165]`,`B14[167]`,`B14[168]`: inbound-SysEx parser running state (byte counter, last-byte values, state/status byte) touched throughout the rx-state-machine cluster.
- `B14[70]`,`B14[72]`,`B14[73]`: fields threaded through nearly every `midi_param_reply_build*` composer/coordinator pair -- likely the current parameter's slot/index/value triple.
- `B14[284]`: the command index into the 48-entry table, also independently stored by two of the table veneers (c012d9e0's own test, and c012da90's `STB B1,*+B14[284]`).
- Patch/preset filenames found as literals in this range: `FLST_SEQ.ZT2`, `BYPASS.ZD2`, `GUARDZDL.ZT2`, `*.*`, and UI scroll-arrow labels `<<<`/`>>>`.

## Open questions
- Exact semantics of the 20 command codes dispatched by `midi_cmd_dispatch` (c0128e54) and the 48 commands dispatched by `midi_param_cmd_dispatch48` (c012d9e0) are not decoded to specific MIDI/SysEx operation names (e.g. which code is "identity request", "bulk dump", "parameter set") -- only the dispatch mechanism and the generic "compose+checksum+send" shape of the targets is confirmed.
- The precise state-number-to-table-slot mapping for the 5-entry rx-state-machine (0xc01844a8..b8) was read structurally (byte comparisons against 0x52/0x7E, B14 state advances) but not pinned to named protocol states (e.g. "waiting for manufacturer ID" vs "waiting for device ID").
- `c012b2c0` (4 bytes, 5 callers) was not read directly; flagged as a likely constant-return stub by size alone.
- Several "generic_util"/"usbdesc_helper" leaves (c012ad1c, c012ad48, c012ad58, c012afa0, c012b024, c012b030) have no callees in the fact sheet and were not read; their exact role is unresolved beyond "small shared utility".
- `param_buf_build_bulk_dump` (c012be20, 1876B, the largest function in this chunk) and its siblings `param_buf_bulk_apply`/`param_buf_init_all` were only read via their anchor `c012b3c0`'s shape, not instruction-by-instruction; whether they build a bulk SysEx dump, a flash-save record, or both is not established.