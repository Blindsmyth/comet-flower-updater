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