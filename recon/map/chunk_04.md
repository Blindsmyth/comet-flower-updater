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