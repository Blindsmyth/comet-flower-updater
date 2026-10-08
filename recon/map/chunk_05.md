# chunk_05: c012dab0..c0132430 (150 functions)

Summary: this range is almost entirely MIDI/MainApp/UpdateUI logic layered on
top of the graphics and USB-descriptor primitives from earlier chunks, with
five sub-clusters: (1) `c012dab0..c012e5a8` a generic scrollable-list
row-render dispatcher (`ui_row_render_dispatch` c012e5a8) that picks among
type-specific renderers for names, quoted strings, table values, a
"page N/M" counter, a 5-glyph icon family (`ui_glyph_dispatch` c012e3a8,
confirmed computed-jump dispatcher at table 0xc0184494) and a per-item
custom-numeric-formatter table at 0x11811ca8 (same x*84 stride as recon/01's
0x118115a0 table); (2) `c012ec80..c012fb28` a cascade of "try each setter
type in turn" MIDI-value-apply helpers built on tag-dispatch leaves
(midi_apply_type11/30/31_setter) feeding the already-named
orchestrator_midi_compose, plus the USB-descriptor-table accessor family
(usb_desc_table_entry_get and friends); (3) `c012fb9c..c01309da` a
MIDI-controllable-parameter "assignment record" subsystem: search/apply
cascades over the recon/01 value*84 table at 0x118115a0
(cfg_record_find_by_id c012fd28, midi_assign_record_apply c012ff14,
midi_assign_apply_variant1/1_locked/3 c01300a4/c0130138/c01303b8), all
selected by a settings-menu action switch whose real body is
`midi_settings_action_dispatch` (c01308e4) -- the ten addresses
c0130950,c013098a..c01309da are confirmed NOT independent functions but
switch case-arms reached only through the 24-entry pointer table at
0xc0183e4c, per the FWMAP shared-epilogue pitfall; (4) `c0130a00..c0131800`
a MIDI diagnostic-trace subsystem tagged by ROM strings EDTB/PPRM/PTCF/
TXE1/TXJ1 (diag_record_build_edtb c0130ab4, midi_diag_trace_emit c0130e04 --
the c0-region counterpart of the already-named 1180-region
midi_send_diag_gated_1180 -- and midi_param_change_trace c013150c, called
from midi_param_dispatch and PreLoad init), interleaved with more small
cfg/custom-formatter-table accessors and a pair of near-identical SysEx
senders (c0131138/c0131188); (5) `c0131800..c0132430` a USB MIDI
descriptor/string "rebuild all slots" subsystem
(usb_desc_rebuild_all_slots c01320e8, called from
midi_assign_apply_and_rebuild_desc c01302d8 whenever a MIDI assignment
changes) built from a large family of near-identical slot-get accessors
and lock-guarded "write only if changed" slot setters over the USB
descriptor table. Three functions in this range were already named by
00_library_kernel.md (orchestrator_midi_compose c012ee10,
fixed_scale_mul_84_div c0130d28, fixed_scale_mul_84 c0130d74) -- see that
file; this report gives them "see" rows only.

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| c012dab0 | midi_pack_7bit_block | packs A4:A5 into 10 bytes at *B4[0..9], each byte an EXTU 7-bit field of the combined 35-bit value (last byte gets the top single bit via SHRU 0x1f) -- a MIDI 7-bit-safe byte-stream encode of a binary value, called from midi_compose_and_send (c0128070) | likely | c012dab4 EXTU.S1 A3,25,25,A0; c012db30 SHRU.S2 B0,0x1f,B0; STB *+B4[0..9]; callers=midi_compose_and_send,c0128134 |
| c012db40 | name_matches_builtin1 | SPLOOPW 10 byte-compare loop (classic strncmp10 shape: EXTU+CMPEQ+SUB+OR per byte) between the buffer at caller stack+8 and a fixed 10-byte string at ~0xc016ff28, then CALLP c0141a68 with len 0x20 -- looks like "does this 10-char name equal built-in string #1" | likely | c012db68 SPLOOPW 10; c012db70/74 LDBU/LDB *++[1]; c012db7a CMPEQ.L2 0,B0,B0; c012db82 SUB.L2X; calls c0141a68 |
| c012dbb4 | name_matches_builtin2 | sibling of c012db40: same 10-byte strncmp loop against a different fixed/looked-up string (LDW *A5[0] then compare), B2=65 constant, calls c0141a68 | likely | identical SPLOOPW 10 compare body at c012dbe0; MVK 65,B2; calls c0141a68 |
| c012dc2c | name_matches_builtin3 | third sibling of c012db40/dbb4, same 10-byte strncmp shape, called only from c012dca4 | likely | same SPLOOPW 10 body pattern (not re-read byte-for-byte, structurally identical entry/exit to siblings) |
| c012dca4 | ui_row_render_name | row renderer for a 10-char name field: calls the 3 name_matches_builtin* checks, gfx_set_bit_range, ui_render_item_a_wrap2, fmt_render_wrapper, fixed_point_math_big; string "Dummy" (placeholder shown when name unset/matches a built-in default) | likely | string Dummy; calls=c012db40,c012dbb4,c012dc2c,c011c508=gfx_set_bit_range,c011e4b4=ui_render_item_a_wrap2,c016c360=fmt_render_wrapper; 1 caller c012e5a8 |
| c012df54 | ui_row_render_sub1 | row-renderer helper: calls gfx_set_bit_range and big_subsystem_2 (c011d938); not traced instruction-by-instruction | guess | calls=c011c508=gfx_set_bit_range,c011d938=big_subsystem_2; 1 caller c012e010 |
| c012e010 | ui_row_render_type2 | sibling row renderer to c012dca4 (same gfx_set_bit_range/ui_render_item_a_logged/fmt_render_wrapper call set, delegates part of the work to c012df54); selected by c012e5a8 for a different field type | guess | calls=c011c508=gfx_set_bit_range,c011e3ac=ui_render_item_a_logged,c012df54,c016c360=fmt_render_wrapper; 1 caller c012e5a8 |
| c012e164 | ui_row_render_table_value | row renderer that fetches a table entry via usb_desc_table_get/c012ad58/c012ee80 then draws it (gfx_set_bit_range, ui_render_item_a_wrap2) -- shows a value pulled from an indexed table | guess | calls=11805fb0=validated_table_lookup,c012afe0=usb_desc_table_get,c012ad58,c012ee80,c011e4b4=ui_render_item_a_wrap2; 1 caller c012e5a8 |
| c012e330 | ui_row_render_page_counter | renders a "page N/M" style counter; string "%1d/%1d" fits a two-number ratio display | likely | string %1d/%1d; calls=c011d014=ui_render_item_a_wrap,c015ad98,c016c360=fmt_render_wrapper; 1 caller c012e5a8 |
| c012e3a8 | ui_glyph_dispatch | bounds-checks arg (B1) against 4 (CMPLTU 0x4,B1 -> out of range goes to default c012e450), else loads a 5-entry function-pointer table at 0xc0184494+index*4 and branches into it -- dispatcher for 5 small glyph-draw variants | confirmed | c012e3ac CMPLTU.L2 0x4,B1,B0; c012e3b4/b8 table base 0xc0180000+0x4494; c012e3c0 LDW *B5[B4],B0; c012e3c2 BNOP B0,5 |
| c012e3c4 | ui_glyph_draw_0 | glyph-draw leaf 0/5: CALLP gfx_set_bit_range with fixed source bitmap at 0xc0181258, width 11 -- draws one fixed small icon | confirmed | MVK 0x1258,B8; MVKH 0xc0180000,B8; CALLP 0xc011c508,B3; tail-branches to shared c012e44a |
| c012e3e0 | ui_glyph_draw_1 | glyph-draw leaf 1/5, same shape as c012e3c4 with source bitmap 0xc0181240 | confirmed | MVK 0x1240,B8; MVKH 0xc0180000,B8; CALLP 0xc011c508,B3 |
| c012e3f8 | ui_glyph_draw_2 | glyph-draw leaf 2/5, source bitmap 0xc0181228 | confirmed | MVK 0x1228,B8; MVKH 0xc0180000,B8; CALLP 0xc011c508,B3 |
| c012e414 | ui_glyph_draw_3 | glyph-draw leaf 3/5, source bitmap 0xc0181210 | confirmed | MVK 0x1210,B8; MVKH 0xc0180000,B8; CALLP 0xc011c508,B3 |
| c012e430 | ui_glyph_draw_4 | glyph-draw leaf 4/5, source bitmap 0xc01811f8 | confirmed | MVK 0x11f8,B8; MVKH 0xc0180000,B8; CALLP 0xc011c508,B3 |
| c012e450 | ui_glyph_draw_default | out-of-range/default case for ui_glyph_dispatch: draws a blank/empty bitmap at ~0xc017b4a8, width 128 | confirmed | MVK 0xffffb4a8/MVKH 0xc0170000,B8; MVK 0x80,B6; CALLP 0xc011c508,B3 |
| c012e474 | ui_row_render_numeric_custom | numeric-value row renderer: indexes a per-item custom-formatter table at 0x11811ca8 by value*84 (same x*84 stride as recon/01's 0x118115a0 table); if a formatter is registered it tail-jumps to it, else falls back to fixed_scale_mul_84_div (c0130d28) + c011f06c for default decimal formatting | likely | MVK 84,B0; MPYLI B0,B4,B1:B0; base 0x11811ca8; LDW *A4[0],A0; [A0] BNOP A0,5 (indirect call); fallback calls c0130d28,c011f06c |
| c012e4b8 | ui_row_render_quoted_string | row renderer for a quoted-string field (e.g. a name/label shown in quotes); string "\"%s\"" | likely | string "%s"; calls=c011d938=big_subsystem_2,c011e4b4=ui_render_item_a_wrap2,c012b324,c0130d74=fixed_scale_mul_84,c016c360=fmt_render_wrapper |
| c012e584 | ui_row_render_blank | simple row renderer: one gfx_set_bit_range call against a fixed bitmap at ~0xc01790e0, width 128 -- likely the "empty row" / separator renderer | likely | MVK 0xffff90e0/MVKH 0xc0170000,B8; MVK 0x80,B6; single CALLP 0xc011c508,B3 |
| c012e5a8 | ui_row_render_dispatch | the master per-row renderer for a generic list screen: validates/looks up the row's type via validated_table_lookup, then dispatches to the type-specific renderers above (c012dca4 name, c012e010/e164 table-value, c012e330 page-counter, c012e474 numeric, c012e4b8 quoted-string) plus ui_text_render/gfx_set_bit_range directly for simple cases; only callers c01359e4,c013c044 (likely UpdateUI-task screen draw call sites) | likely | calls (42) incl. 1180aea0=ui_text_render,11805fb0=validated_table_lookup,c012dca4,c012e010,c012e164,c012e330,c012e450,c012e474,c012e4b8,c012e584; 2 callers |
| c012ec80 | midi_apply_value_if_changed | gets a value (c0140240) and applies it (c01418ec); if the applied result differs from the pre-apply value, takes bios_sem_pend, reloads/invalidates the cached state at B14[155] (via c013fee0 with -1, then c016f610, and conditionally c016f600 when cfg_get_b14_26 is set), then bios_sem_post -- a locked "apply + invalidate cache on change" pattern | likely | c012eca4 CMPEQ.L1 A1,A0,A0 (pre vs post); [A0]==skip path; calls=c0140240,c01418ec,c0150b20=bios_sem_pend,c013fee0,c0129630=cfg_get_b14_26,c01628e0=bios_sem_post; B14 global 155 |
| c012ece0 | midi_apply_type30_setter | reads a type/kind tag for the item via c013db58; if tag==30 calls the type-30 setter c014038c and returns whether it accepted the value (bool in A4), else returns 0 | confirmed | c012ecec MVK 30,A0; c012ecee CMPEQ.L1 A4,A0,A0; c012ecf4 CALLP 0xc014038c,B3; result boolean in A4 |
| c012ed0c | midi_apply_type11_setter | same tag-dispatch shape as c012ece0 but for tag==11: tries setter c01403d8 first, and if it fails (returns 0) falls back to a second setter c016f5f0 before returning success/fail | confirmed | c012ed18 CMPEQ.L1 11,A4,A0; calls c01403d8 then (if !result) c016f5f0 |
| c012ed44 | midi_apply_type31_setter | sibling of c012ece0 for tag==31, single setter c0140428 | confirmed | c012ed50 MVK 31,A0; CMPEQ.L1 A4,A0,A0; calls c0140428 |
| c012ed70 | midi_apply_value_cascade_a | cascading "try each setter in turn" dispatcher: scales the value (fixed_scale_mul_84 c0130d74), tries midi_apply_type30_setter; on failure rescales and tries midi_apply_type31_setter; on failure tries c01404c4, then c01404ec, then falls back to c0140268, returning 1/0 for overall success | confirmed | sequential `MV A4,A0; [A0] BNOP ...edc0` success-short-circuit chain through c012ece0,c0130d74,c012ed44,c01404c4,c01404ec,c0140268 |
| c012edcc | midi_apply_value_cascade_b | second cascade variant: tries midi_apply_type11_setter (c012ed0c) first, then fixed_scale_mul_84, then c01404ec, then c0140268 -- used by a different caller set (c0141ac8) than cascade_a | confirmed | same short-circuit-chain shape as c012ed70 but through c012ed0c,c0130d74=fixed_scale_mul_84,c01404ec,c0140268 |
| c012ee10 | orchestrator_midi_compose | see 00_library_kernel.md | likely | already named, recon/map/00_library_kernel.md |
| c012ee80 | usb_desc_or_table_fetch | fetches an entry from the indexed table via usb_desc_table_get (c012afe0) plus helpers c012b008/c012b108; called from the usbstr_builder/usbstr_leaf family and from the row-render dispatch -- a shared "get table entry N" accessor, not traced instruction-by-instruction | guess | calls=c012afe0=usb_desc_table_get,c012b008,c012b108; 11 callers incl. usbstr_builder3/4/5,usbstr_leaf1 |
| c012ef24 | ui_row_render_table_value2 | sibling of c012e164: validated_table_lookup + usb_desc_or_table_fetch (c012ee80) then a draw call c015acec -- another table-value row-render variant | guess | calls=11805d20=orchestrator_1180_region3,11805fb0=validated_table_lookup,c012ee80,c015acec; 2 callers incl. c012e5a8 |
| c012efb0 | usb_desc_table_entry_get | thin wrapper: usb_desc_table_get (c012afe0) then c012b008/c012b108 -- same accessor shape as c012ee80 but with a different, larger caller set (c0131870, c0131ab0, c0131d04, ... the c0132xxx USB-string builder family below) | guess | calls=c012afe0=usb_desc_table_get,c012b008,c012b108; 9 callers |
| c012f040 | usb_desc_entry_get_wrap | tiny wrapper around usb_desc_table_entry_get (c012efb0); 11 callers across the usbstr_leaf3 and c0131xxx/c0132xxx families | guess | calls=c012efb0; 11 callers incl. usbstr_leaf3 |
| c012f068 | usb_desc_entry_get_checked | wraps usb_desc_entry_get_wrap (c012f040) with an rts_const_return_1 (c012af98) guard; called from usbdesc_builder_main and c0141684/c0141784 | guess | calls=c012af98=rts_const_return_1,c012f040; 3 callers |
| c012f0b4 | usb_desc_table_entry_get2 | sibling accessor: usb_desc_table_get + c012b008 (no c012b108 this time); single caller c012f148 | guess | calls=c012afe0=usb_desc_table_get,c012b008; 1 caller |
| c012f148 | midi_compose_from_table1 | composes/sends a MIDI value from a table entry: fetches via c012f0b4, formats via c013d998, then calls orchestrator_midi_compose | guess | calls=c012ee10=orchestrator_midi_compose,c012f0b4,c013d998; 1 caller c012f5d4 |
| c012f1a0 | midi_compose_from_table2 | sibling of c012f148 for a different table/field (c013d9b0 instead of c013d998); single caller c0143418 | guess | calls=c012ee10=orchestrator_midi_compose,c013d9b0; 1 caller |
| c012f1e4 | cfg_index_bound_check | bound-checks an index (bound_check_lt4) then resolves it via the table-index helper c0140320; shared by 4 callers in the c012ffxx/c0130xxx apply-cascade family | guess | calls=11805d20=orchestrator_1180_region3,11805d84=bound_check_lt4,c0140320=cfg_table_index_1181191c; 4 callers |
| c012f238 | rhythm_bound_check | same bound_check_lt4 (clamp-to-4) shape as c012f1e4 but with RhythmService/UpdateUI roots and no table-index call -- likely a knob/param-index guard for the rhythm-pattern UI | guess | roots=RhythmService,UpdateUI; calls=11805d84=bound_check_lt4; 2 callers (c01344e8,c01565b8) |
| c012f284 | ui_row_render_table_value3 | third table-value row-render variant (validated_table_lookup + usb_desc_or_table_fetch c012ee80 + c0132510/c0132560 + c015aca0/c015ad98); single caller c012f378 | guess | calls=11805fb0=validated_table_lookup,c012ee80,c0132510,c0132560,c015aca0,c015ad98; 1 caller |
| c012f378 | ui_row_render_table_value4 | wraps ui_row_render_table_value3 (c012f284) with an extra c012ad1c lookup; called from the master dispatch c012e5a8 and from c012f440 | guess | calls=11805fb0=validated_table_lookup,c012ad1c,c012f284,c015aca0,c015ad98; 2 callers |
| c012f440 | ui_row_render_table_value5 | wraps ui_row_render_table_value4 (c012f378) plus c0132510/c0132560; single caller c01303b8 | guess | calls=c012b108,c012f378,c0132510,c0132560,c015acec; 1 caller |
| c012f4ec | cfg_table_index_wrap | thin wrapper around the table-index helper c0140320; 6 callers across the c012fdxx/c0130xxx apply family | guess | calls=c0140320=cfg_table_index_1181191c; 6 callers |
| c012f510 | ui_row_render_region3_leaf1 | tiny leaf calling only orchestrator_1180_region3; roots UpdateUI; 2 callers (c012e5a8, c0137a98) | guess | calls=11805d20=orchestrator_1180_region3; 2 callers |
| c012f530 | usb_desc_table_entry_get3 | sibling accessor: usb_desc_table_get + c012b108 (no c012b008); single caller c0132430 | guess | calls=c012afe0=usb_desc_table_get,c012b108; 1 caller |
| c012f5d4 | midi_compose_from_table1_wrap | thin wrapper calling midi_compose_from_table1 (c012f148); single caller c0143418 | guess | calls=c012f148; 1 caller |
| c012f604 | ui_row_render_region3_leaf2 | sibling of c012f510 (orchestrator_1180_region3 only), roots UpdateUI, called from c012e5a8 and c0137e30 | guess | calls=11805d20=orchestrator_1180_region3; 2 callers |
| c012f628 | usb_desc_or_table_fetch_wrap | wraps usb_desc_or_table_fetch (c012ee80) with an rts_const_return_1 guard; callers usbstr_builder1, c015aca0 | guess | calls=c012af98=rts_const_return_1,c012ee80; 2 callers |
| c012f674 | midi_apply_scaled_from_cfg | scales a config value (fixed_scale_mul_84_div c0130d28) against cfg_get_global_1181191c (c0140258); single caller c01297a0 | guess | calls=c0130d28=fixed_scale_mul_84_div,c0140258=cfg_get_global_1181191c; 1 caller |
| c012f6d8 | midi_leaf_shared | small shared leaf with no calls listed; called by both c012f74c and c012f7e4 (likely returns/reads a fixed field) | guess | roots=MIDI,MainApp; 0 calls listed; 2 callers |
| c012f74c | midi_apply_from_b14_27 | reads cfg via cfg_get_global_c011ad8c (c0156e80) and c012f6d8, applies through midi_leaf_ace8 and c0131188; one of the MIDI-param-dispatch call targets | guess | calls=1180ace8=midi_leaf_ace8,c012f6d8,c0131188,c0156e80=cfg_get_global_c011ad8c; 3 callers incl. midi_param_dispatch |
| c012f7a4 | midi_apply_from_b14_27_wrap | wraps midi_apply_from_b14_27 (c012f74c) after fetching cfg_get_b14_27 (c0127fe0) and copying via rts_memcpy_word_sploop; B14 slot 99 | guess | calls=c0127fe0=cfg_get_b14_27,c012f74c,c016d4c0=rts_memcpy_word_sploop; B14 global 99; 2 callers |
| c012f7e4 | midi_apply_from_b14_27_variant | sibling of c012f74c for a different target (c0131138 instead of c0131188); single caller c01395dc | guess | calls=1180ace8=midi_leaf_ace8,c012f6d8,c0131138,c0156e80=cfg_get_global_c011ad8c; 1 caller |
| c012f840 | switch_speed_gate_wrapper | calls the switch-speed gate (1180add8=switch_speed_gate2) plus c0155290/c0163648/c01636cc; roots include Swi:USB,SwitchNrmlSpdRead -- likely applies a MIDI-driven switch-speed/debounce setting | guess | roots=MIDI,MainApp,Swi:USB,SwitchNrmlSpdRead; calls=11805eb4=unk_1180_5eb4,1180add8=switch_speed_gate2,c0155290,c0163648,c01636cc; recon:15 |
| c012f878 | midi_param_apply_leaf | applies a MIDI-controllable parameter via midi_param_dispatch2 (118075e4) and midi_leaf_ad14, then c01490cc; 10 callers across MainApp/MIDI call sites (orchestrator_b14_99 etc.) | guess | calls=118075e4=midi_param_dispatch2,1180ad14=midi_leaf_ad14,c01490cc; 10 callers |
| c012f898 | cfg_table_value_fetch | validated_table_lookup then c0130a00/c015c0b8/c015c118 -- fetches and bound-checks a configuration-table value; 2 callers | guess | calls=11805d20=orchestrator_1180_region3,11805fb0=validated_table_lookup,c0130a00,c015c0b8,c015c118; 2 callers |
| c012f900 | mainapp_sem_leaf | tiny leaf, roots MainApp, only call is rts_regs_save (c016e020) -- essentially a no-op/stub wrapped in the save/restore pair, called by c012faa4 and c012fb00 | guess | roots=MainApp; calls=c016e020=rts_regs_save only; 2 callers |
| c012f960 | ptr_table_entry_1 | no calls, ptr@ c0184510 -- a data-pointer-table entry (callback slot), not traced | guess | ptr@ c0184510; 0 calls, 0 callers listed |
| c012f98c | ptr_table_entry_2 | sibling of c012f960, ptr@ c018450c | guess | ptr@ c018450c |
| c012f9b8 | ptr_table_entry_3 | sibling of c012f960, ptr@ c0184508 | guess | ptr@ c0184508 |
| c012f9e8 | midi_apply_locked | bios_sem_pend/post-guarded apply: calls c01418ec and c0153428; ptr@ c0184504 slots it into the same callback table as c012f960/98c/9b8; B14 global 155 | guess | calls=c01418ec,c0150b20=bios_sem_pend,c0153428,c01628e0=bios_sem_post; ptr@ c0184504; B14 global 155 |
| c012faa4 | mainapp_sem_apply | locked apply: bios_sem_pend, calls orchestrator_1180_region (1180ad68), mainapp_sem_leaf (c012f900), c015bfc0/c015c094, bios_sem_post; roots MainApp; B14 global 154 | guess | roots=MainApp; calls=1180ad68=orchestrator_1180_region,c012f900,c0150b20=bios_sem_pend,c015bfc0,c015c094,c01628e0=bios_sem_post; B14 global 154; 3 callers |
| c012fb00 | mainapp_sem_leaf_wrap | thin wrapper around mainapp_sem_leaf (c012f900); single caller wrapper_c016a94c | guess | calls=c012f900; 1 caller |
| c012fb28 | midi_apply_locked2 | sibling of c012f9e8: bios_sem_pend/post-guarded, calls shared_accessor5_1180 (11805e64), c01418ec, c0153428/c0153464, c015e6d8; single caller c0164840 | guess | calls=11805e64=shared_accessor5_1180,c01418ec,c0153428,c0153464,c015e6d8; 1 caller |
| c012fb9c | midi_apply_or_fallback | tries midi_apply_value_cascade_a (c012ed70); on success calls c01297a0(value,0), on failure calls c01297a0(value,orig_arg) instead; both paths then call the shared finalizer c016f570 | confirmed | c012fba4 CALLP 0xc012ed70; c012fbaa [A0] branch splits success/fail paths into two different c01297a0 call-arg shapes, converge at c012fbc8 CALLP 0xc016f570 |
| c012fbe0 | midi_item_status_tag | probes two cfg-pointer slots (cfg_ptr_11810000_325c index 0 then 1); if both empty, picks status tag 6 if the item id (A10) is zero else tag 5, via bridge_status_struct (c0156d68) -- looks like an "assigned/unassigned" status classifier | likely | c012fbe8/f0 CALLP 0xc0155328 (index 0,1); c012fbfa test A10; CALLP 0xc0156d68 with A4=6 or 5; recon:15 |
| c012fc18 | state_buf_clear | rts_memset's a fixed 24-byte buffer at ~0xc011abe4 to 0; roots MainApp | confirmed | MVK 0xffffabe4/MVKH 0xc0110000,A4; MVK 24,A6; MVK 0,B4; CALLP 0xc0167b00=rts_memset |
| c012fc34 | state_buf_clear_wrap | thin wrapper calling state_buf_clear (c012fc18) only; roots MainApp | confirmed | single CALLP 0xc012fc18 |
| c012fc40 | state_reset_and_elapsed | clears the state buffer (state_buf_clear c012fc18), loads a start/latest timestamp pair from a fixed table at ~0xc011abf4, computes elapsed (subtract), applies it via c014002c, and flags via c0155414 -- consistent with resetting a popup/elapsed-time counter | likely | LDW from 0xc011abf4 table; CALLP 0xc012fc18,0xc015adc8,0xc016f650,0xc014002c,0xc0155414; final STW 1 into struct+4 |
| c012fc98 | cfg_table_index_search | linear-search loop over a config range (bounds from cfg_get_global_1181191c c0140258) to find the index matching a target, then resolves via cfg_table_index_1181191c (c0140320) and c016f560/c014002c | likely | loop CMPLT/CMPEQ/ADD A10 incrementing against cfg_get_global_1181191c bound; CALLP 0xc0140320,0xc016f560,0xc014002c |
| c012fd08 | status_flag_check_6_7 | queries status codes 6 and 7 via c015bf6c (same family as midi_item_status_tag's bridge_status_struct codes) | guess | two CALLP 0xc015bf6c with B4=6 then B4=7, A4=A6=0 both times |
| c012fd28 | cfg_record_find_by_id | searches the value*84-strided config table at ~0x118115a0 (recon/01's table, written by midi_cfg_table_fill 118072ac) for a record whose first word equals the target id, with fallbacks through cfg_get_b14_26, orchestrator_midi_compose and several cfg_table_index helpers; large (240B) multi-path function, core search loop confirmed | likely | c012fd38 MVK 0x54,A0; MPYLI A0,A13,A7:A6; c012fd44/48 base 0x118115a0-ish; c012fd50 LDW *B4[0],B0; CMPEQ B0,B1,B0 -> branch c012fe04 on match |
| c012fe18 | cfg_type_classify | classifies a type code from *A10 into a status: 1 or 3 -> writes a shared status word; 39/40 -> writes 0; anything else -> writes 1; writes results to two output pointers (*A11,*A12) | confirmed | c012fe30/32 CMPEQ 1; c012fe36 CMPEQ 3; c012fe3a/40 SUB A1,39,A0; CMPLTU 1,A0 (range 39-40); STW to *A11/*A12 |
| c012fe68 | cfg_type_classify_scan | scans a code list (terminated by value 42) at the caller's buffer, classifying each entry via cfg_type_classify (c012fe18) and marking bit/byte flags into the 24-byte state buffer (same ~0xc011abe4 buffer as state_buf_clear); single caller c012ff14 | likely | loop CMPEQ B0,42,B0 terminator test; CALLP 0xc012fe18 per entry; STB flags into 0xc011abe4-based buffer |
| c012ff14 | midi_assign_record_apply | large (400B) record-apply handler: validates/bounds an index (c012f1e4), scans/classifies the record's type codes (cfg_type_classify_scan c012fe68), reads several sub-fields via c013d3xx/c013d8xx/c013d9xx accessors, resolves via cfg_table_index helpers (c012fc98,c012fd08,c012fe68) and scales via fixed_scale_mul_84(_div) -- the apply-a-MIDI-assignment-record counterpart to cfg_record_find_by_id; single caller c0130950 | likely | calls (24) incl. c012f1e4,c012f4ec,c012fc98,c012fd08,c012fe68,c0130d28=fixed_scale_mul_84_div,c0130d74=fixed_scale_mul_84,c013d320,c013d3e8,c013d814,c013d8d0,c013d9c8; not traced instruction-by-instruction given size |
| c01300a4 | midi_assign_apply_variant1 | sibling apply-handler to midi_assign_record_apply, calling orchestrator_1180_region (1180ad68), cfg_index_bound_check (c012f1e4), midi_assign_record_apply (c012fd28 search) and c013d658/c015c0b8; callers c0130138,c01307d4 | guess | calls=1180ad68=orchestrator_1180_region,c012f1e4,c012fd28,c013d658,c015c0b8; 2 callers |
| c0130138 | midi_assign_apply_variant1_locked | locked wrapper around midi_assign_apply_variant1 (c01300a4): bios_sem_pend, orchestrator_1180_region, c012f1e4, c01300a4, c015c0b8, bios_sem_post; B14 global 154; single caller c0130950 | likely | calls=1180ad68=orchestrator_1180_region,c012f1e4,c01300a4,c0150b20=bios_sem_pend,c015c0b8,c01628e0=bios_sem_post; B14 global 154 |
| c01301cc | region3_tiny_leaf | single-call leaf to unk_1180_5ed0 (11805ed0), shared by c01301e4 and c0130378 | guess | calls=11805ed0=unk_1180_5ed0; 2 callers |
| c01301e4 | midi_compose_scaled_send | composes and sends a scaled MIDI value: midi_scale_wrap (11809980), orchestrator_1180_region, orchestrator_midi_compose, region3_tiny_leaf (c01301cc), fixed_scale_mul_84_div, c0158fb0; single caller c01303b8 | likely | calls=11809980=midi_scale_wrap,1180ad68=orchestrator_1180_region,c012ee10=orchestrator_midi_compose,c01301cc,c0130d28=fixed_scale_mul_84_div,c0158fb0 |
| c0130244 | midi_apply_variant_noSend | sibling of midi_compose_scaled_send without the compose/send step (only orchestrator_1180_region + c0158fb0); single caller c01303b8 | guess | calls=1180ad68=orchestrator_1180_region,c0158fb0 |
| c0130280 | usb_desc_apply_target | fetches a usb-desc-table entry (usb_desc_table_get) then applies via c0153428; single caller c01303b8 | guess | calls=c012afe0=usb_desc_table_get,c0153428 |
| c01302d8 | midi_assign_apply_and_rebuild_desc | locked apply that also rebuilds the USB-descriptor/MIDI string: calls into the usbstr-builder family (c0131d64,c01320e8,c01322d8,c0141784) under bios_sem_pend/post; B14 global 155; callers c01303b8,c0134650 | likely | calls=c0131d64,c01320e8,c01322d8,c0141784,c0150b20=bios_sem_pend,c01628e0=bios_sem_post; B14 global 155 |
| c0130378 | midi_assign_apply_variant2 | sibling helper used alongside midi_assign_apply_and_rebuild_desc: orchestrator_1180_region3, cfg_table_index_wrap (c012f4ec), region3_tiny_leaf (c01301cc), c015c070; callers c01303b8,c0134650 | guess | calls=11805d20=orchestrator_1180_region3,c012f4ec,c01301cc,c015c070 |
| c01303b8 | midi_assign_apply_variant3 | the largest (512B) of the three settings-action handlers selected by midi_settings_action_dispatch (c0130950): combines usb-desc lookups, midi_scale_wrap, orchestrator_midi_compose, the table-value row-render helpers (c012ee80,c012ef24,c012f440), cfg_table_index_wrap and the midi_compose_scaled_send/midi_apply_variant_noSend/usb_desc_apply_target/midi_assign_apply_and_rebuild_desc/midi_assign_apply_variant2 siblings above; single caller c0130950, not traced instruction-by-instruction given size | likely | calls (24) incl. 11805fb0=validated_table_lookup,11809980=midi_scale_wrap,c012ee10=orchestrator_midi_compose,c012ee80,c012ef24,c012f440,c012f4ec,c01301e4,c0130244,c0130280,c01302d8,c0130378,c0130d28=fixed_scale_mul_84_div,c0155328=cfg_ptr_11810000_325c |
| c01305b8 | settings_action_set_flag_a | settings-action case handler: calls midi_item_status_tag (c012fbe0) passing through the caller's item descriptor, ignores its result, always returns 1 (success); recon/15 already covers this item | likely | CALLP 0xc012fbe0; unconditional MVK 1,A4 return; recon:15 |
| c01305d0 | settings_action_set_flag_b | sibling of settings_action_set_flag_a with the same call+unconditional-success-return shape, reached from a different switch case; recon/15 | likely | CALLP 0xc012fbe0; unconditional MVK 1,A4 return; recon:15 |
| c01305e8 | settings_flag_consume_notify | copies a 16-byte item descriptor to the stack, then probes a flag byte at state-buffer+2 (0xc011abe4+2): if set, clears it and notifies c0157668 with the old value, else notifies c0157668 with 0 -- a "consume pending flag" case handler | likely | LDBU *B4[2] probe/clear at 0xc011abe4+2; CALLP 0xc0157668 with the probed value |
| c0130638 | elapsed_delta_apply | computes an elapsed delta (c016f560 then c014002c then SUB A2,A1) between two values -- shared helper for case handlers that need a before/after duration; single direct caller in this cluster (settings_action_cfgptr_changed c0130654) plus c012fc98 | likely | CALLP 0xc016f560,0xc014002c; SUB.L1 A2,A1,A4 |
| c0130654 | settings_action_cfgptr_changed | copies a 16-byte item descriptor, resolves two values via c016f650/c016f640, probes cfg_ptr_11810000_325c at two indices, and if the before/after values differ calls elapsed_delta_apply (c0130638), sets a flag byte at state-buffer+2, and notifies c0157510 -- else calls orchestrator_locked_small (c015c0f8) directly | confirmed | CALLP 0xc0155328 x2; CMPEQ A10,A11; on mismatch CALLP 0xc0130638 then STB 1 at 0xc011abe6 then CALLP 0xc0157510 |
| c01306ec | settings_action_reinit_cache | probes cfg_ptr_11810000_325c at indices 0/1; if neither set, calls bridge_status_struct(1); else re-inits via big_subsystem_init (c0155ac0, size 64) using B14[139], then locks (bios_sem_pend), invalidates B14[154]'s cache via c0136684(-1), unlocks (bios_sem_post) | likely | CALLP 0xc0155328 x2; CALLP 0xc0156d68 A4=1; CALLP 0xc0155ac0=big_subsystem_init; B14 globals 139,154; CALLP 0xc0150b20=bios_sem_pend / 0xc01628e0=bios_sem_post |
| c0130748 | settings_action_toggle_status4 | probes cfg_ptr_11810000_325c at indices 0/1; if neither set, clears a fixed scratch word at ~0xc011abf8 (returning its old value), else calls bridge_status_struct(4) | likely | CALLP 0xc0155328 x2; scratch word at 0xffffabf8/0xc0110000; CALLP 0xc0156d68 A4=4 |
| c0130790 | settings_action_scratch_probe | probes c01552a0 then clears the same fixed scratch word (~0xc011abf8) used by settings_action_toggle_status4, returning its old value | guess | CALLP 0xc01552a0; scratch word at 0xffffabf8/0xc0110000 |
| c01307b8 | settings_action_dual_probe | calls c0155404 then c0155304 (two small accessors), returns a fixed 0 -- looks like a "commit two settings fields" case with no real decision logic traced | guess | CALLP 0xc0155404,0xc0155304; returns MVK 0,A4 |
| c01307d4 | settings_action_dispatch_event | bound-checks the item (c012f1e4), consumes a state-buffer flag, calls c016f540/c016f590/c015c0b8, then applies midi_assign_apply_variant1 (c01300a4) under bios_sem_pend/post (B14 154), and finally dispatches through mainapp_event_dispatch (c01537a8) -- the most consequential case handler in this family | confirmed | CALLP 0xc012f1e4,0xc016f540,0xc016f590,0xc015c0b8,0xc0150b20=bios_sem_pend,0xc01300a4,0xc01628e0=bios_sem_post,0xc01537a8=mainapp_event_dispatch; B14 global 154 |
| c01308a8 | settings_action_scale_notify | bound-checks the item (c012f1e4), computes a rounded/signed-shift scaling of the value (SHRU 0x1f + ADD + EXTU 23,24 -- sign-correct divide-by-2^8-ish rounding), then notifies via c0155348/c0155278 | likely | CALLP 0xc012f1e4; SHRU.S1 A1,0x1f,A0; ADD A0,A1,A0; EXTU.S1 A0,23,24,A4; CALLP 0xc0155348,0xc0155278 |
| c01308e4 | midi_settings_action_dispatch | the master settings-action switch (confirmed, 108B header + body through the shared tail at c01309e4): copies a 16-byte item/event descriptor, reads its type code, and for code<=23 jumps through a 24-entry function-pointer table at 0xc0183e4c (holding the case-arm addresses below); for code in {25..28} calls midi_assign_apply_variant3 (c01303b8); {31,32} calls midi_assign_apply_variant1_locked (c0130138); {33} calls an out-of-range helper c016f530; {39,40} calls midi_assign_record_apply (c012ff14) with arg 0; otherwise falls through with no action. Single caller c0134b94; recon/15 | confirmed | c0130904 CMPGTU B4,23,B0; [!B0] BNOP 0xc0130944 (table dispatch at 0xc0183e4c+B4*4); explicit SUB/CMPLTU/CMPEQ chains for 25-28,31-32,33,39-40; recon:15 |
| c0130950 | settings_action_case_default_0 | NOTE per FWMAP pitfalls: this is a switch case-ARM inside midi_settings_action_dispatch (c01308e4), not an independent function -- reached only via the 0xc0183e4c table (.word ref, 0 real CALLP), falls straight through to a plain return with no call (the "code with no handler registered" arm) | likely | body is exactly `BNOP 0xc01309e4,4` (jump to shared tail), no CALLP; ptr@ c0183e6c,c0183e70,c0183e74,c0183ea4 (multiple table slots alias this same no-op arm) |
| c013098a | settings_action_case_1 | switch case-arm of midi_settings_action_dispatch (c01308e4): CALLP settings_action_set_flag_a (c01305b8) then join shared tail -- not an independent function | likely | CALLP 0xc01305b8; BNOP 0xc01309e4,5; ptr@ c0183ea8 |
| c0130992 | settings_action_case_2 | switch case-arm: CALLP settings_action_set_flag_b (c01305d0); not an independent function | likely | CALLP 0xc01305d0; ptr@ c0183ea0 |
| c013099a | settings_action_case_3 | switch case-arm: CALLP settings_flag_consume_notify (c01305e8); not an independent function | likely | CALLP 0xc01305e8; ptr@ c0183e7c,84,8c,94,9c (5 table slots alias this arm) |
| c01309a6 | settings_action_case_4 | switch case-arm: CALLP settings_action_cfgptr_changed (c0130654); not an independent function | likely | CALLP 0xc0130654; ptr@ c0183e78,80,88,90,98 (5 table slots) |
| c01309ae | settings_action_case_5 | switch case-arm: CALLP settings_action_reinit_cache (c01306ec); not an independent function | likely | CALLP 0xc01306ec; ptr@ c0183e68 |
| c01309b6 | settings_action_case_6 | switch case-arm: CALLP settings_action_toggle_status4 (c0130748); not an independent function | likely | CALLP 0xc0130748; ptr@ c0183e64 |
| c01309c2 | settings_action_case_7 | switch case-arm: CALLP settings_action_scratch_probe (c0130790); not an independent function | likely | CALLP 0xc0130790; ptr@ c0183e60 |
| c01309ca | settings_action_case_8 | switch case-arm: CALLP settings_action_dual_probe (c01307b8); not an independent function | likely | CALLP 0xc01307b8; ptr@ c0183e5c |
| c01309d2 | settings_action_case_9 | switch case-arm: CALLP settings_action_dispatch_event (c01307d4); not an independent function | likely | CALLP 0xc01307d4; ptr@ c0183e50,58 (2 table slots) |
| c01309da | settings_action_case_10 | switch case-arm: CALLP settings_action_scale_notify (c01308a8); not an independent function | likely | CALLP 0xc01308a8; ptr@ c0183e4c,54 (2 table slots) |
| c0130a00 | bound_check_0_50_lookup1 | clamps A4 to [0,50); if out of range returns -1, else calls c0168640 with (value+offset, 10) | confirmed | c0130a0c CMPGT 0,A4,A0; c0130a12 CMPLT A4,50,A0; out-of-range path sets A0=-1; in-range CALLP 0xc0168640 B4=10 |
| c0130a30 | bound_check_0_50_div10 | sibling of bound_check_0_50_lookup1: same [0,50) clamp, then calls rts_sdiv32 (c01675c0) with divisor B4=10 (or -1 on out-of-range) -- a value/10 conversion with range guard | confirmed | same CMPGT/CMPLT clamp; CALLP 0xc01675c0=rts_sdiv32,B4=10 |
| c0130a70 | custom_formatter_table_base_get | returns the fixed constant address 0x11811910 -- the base of a small table adjacent to the value*84 custom-formatter table at 0x11811ca8 | confirmed | MVK 0x1910,A4; MVKH 0x11810000,A4; BNOP B3,5 (plain constant-return leaf) |
| c0130a80 | param_id_notify_51 | if A4 < 50 (unsigned), stores it to the stack and notifies c016f520 with code 51 and a pointer to the stored value; otherwise no-op | confirmed | CMPLTU A4,50,A0; [!A0] skip; STW A4,*B15[1]; MVK 51,A4; CALLP 0xc016f520,B3 |
| c0130a98 | custom_formatter_table_get | looks up the per-item custom-formatter function pointer at 0x11811ca8+(value*84) and returns it (the same table c012e474 and cfg_record_find_by_id-style code index into, but here just a plain getter) | confirmed | MVK 0x54,A0; MPYLI A0,A4,A7:A6; base 0x118111ca8; LDW *A4[0],A4; return |
| c0130ab4 | diag_record_build_edtb | builds a large (~1288B stack) diagnostic trace record for the EDTB/PPRM/PTCF/TXE1/TXJ1 tag set: memsets several sub-buffers, writes a fixed header struct from ROM (0xc0180018f0) plus field defaults, then gates emission on diag_mask_test (c0169fc0) via c016f740/c016f730; single caller c013150c; strings EDTB/PPRM/PTCF/TXE1/TXJ1/empty | likely | ADDK -1288,B15; CALLP 0xc0167b00=rts_memset x5 (sizes 224,248,208,20,48,12); header LDW 0xc0180018f0; CALLP 0xc016f740,0xc016f730; CALLP 0xc0169fc0=diag_mask_test (per fact-sheet call list); not traced to the end given size |
| c0130d28 | fixed_scale_mul_84_div | see 00_library_kernel.md | likely | already named, recon/map/00_library_kernel.md |
| c0130d50 | cfg_record_type_is_1 | indexes the value*84-strided table at ~0x1181159c (same table family as fixed_scale_mul_84/_div) and returns whether the loaded word equals 1 -- a "is this record type 1" predicate | confirmed | MVK 0x54,A0; MPYLI A0,A4,A7:A6; base 0x1181159c; LDW *B4[0],B0; CMPEQ.L1X 1,B0,A0 |
| c0130d74 | fixed_scale_mul_84 | see 00_library_kernel.md | likely | already named, recon/map/00_library_kernel.md |
| c0130d90 | cfg_record_notify_conditional | notifies via c016f520 (same call as param_id_notify_51) and, if it returns nonzero, additionally calls c01369d0; else returns 0 | likely | CALLP 0xc016f520; [A10] CALLP 0xc01369d0; else MVK 0,A4 |
| c0130db0 | midi_diag_trace_emit_leaf | helper for midi_diag_trace_emit (c0130e04): calls c015f34c only; roots MIDI,MainApp; single caller c0130e04 | guess | calls=c015f34c; 1 caller |
| c0130e04 | midi_diag_trace_emit | the c0-region diagnostic-trace emitter for MIDI sends (counterpart to the already-named 1180-region midi_send_diag_gated_1180): gates on diag_mask_test (c0169fc0) using cfg_get_global_11813488/8c and c0140680, then emits via midi_diag_trace_emit_leaf (c0130db0); called from 10 MIDI-compose/send sites (c0128474,c0128788,c0128c88,c0128d14,c0129490,c012d2e4,c0131138,c0131188,c01437f0) plus midi_send_diag_gated_1180; strings EDTB/PPRM/PTCF/TXE1/TXJ1 | likely | calls=1180b060=cfg_get_global_11813488,1180b06c=cfg_get_global_1181348c,c0130db0,c0140680,c0169fc0=diag_mask_test; 10 callers; not traced to the end given size (804B) |
| c0131128 | midi_send_byte_wrap | thin wrapper around wrapper_c016be58 (c016be58), then returns 0; shared tail used by both midi_sysex_send variants below | likely | CALLP 0xc016be58=wrapper_c016be58; MVK 0,A4; roots MIDI,MainApp |
| c0131138 | midi_sysex_send_a | fills a ~248-byte local buffer (rts_memset with a flag bit set via SET.S1 ...,9,9), logs via midi_diag_trace_emit (c0130e04), then sends via midi_send_byte_wrap (c0131128) -- one of two near-identical SysEx-block senders | confirmed | CALLP 0xc0167b00=rts_memset (len 0xf8/248, SET bit9); CALLP 0xc0130e04=midi_diag_trace_emit; CALLP 0xc0131128 |
| c0131188 | midi_sysex_send_b | sibling of midi_sysex_send_a with the same memset/trace/send shape, reached from a different caller (c0138ca4) | confirmed | identical structure to c0131138: CALLP 0xc0167b00,0xc0130e04,0xc0131128 |
| c01311cc | fmt_buffer_render | memsets a local buffer then calls fmt_render_wrapper (c016c360); unrelated to the MIDI cluster above (callers c015942c,c01594f0 are a different, not-yet-mapped subsystem) | guess | calls=c0167b00=rts_memset,c016c360=fmt_render_wrapper; 2 callers |
| c0131294 | mainapp_param_lock_wrap | thin wrapper calling midi_param_lock_op (118092a0) only; roots MainApp; single caller c01341e4 | likely | calls=118092a0=midi_param_lock_op; roots=MainApp |
| c01312c4 | diag_tag_field_extract | inline tag-dispatch (no subroutine calls): compares the input's leading bytes against the ROM tag strings "EDTB" (0xc01810f2) and "PPRM" (0xc01810f7) byte-by-byte, and on a match copies an 8-byte sub-field from a computed struct offset into a local buffer -- part of the diag-trace-record parsing family; single caller c0128788; strings EDTB/PPRM/PTCF | likely | c01312e4/e6 LDBU-loop CMPEQ against 0xc01810f2; c0131328/34 LDNDW/STNDW 8-byte field copy; repeats against 0xc01810f7; roots MIDI |
| c01313e8 | midi_apply_from_table_leaf | thin apply leaf calling c01405e4; roots MIDI,MainApp; callers midi_usb_orchestrator_1180,c013142c | guess | calls=c01405e4; 2 callers |
| c013142c | midi_locked_apply_leaf | locks via midi_param_lock_op (118092a0) then applies via midi_apply_from_table_leaf (c01313e8); callers c0138f2c,c0138f50,c015942c,c01594f0 | likely | calls=118092a0=midi_param_lock_op,c01313e8 |
| c0131468 | midi_param_trace_leaf1 | sub-helper of midi_param_change_trace (c013150c), single call to c015f260 | guess | calls=c015f260; 1 caller c013150c |
| c0131484 | midi_param_trace_leaf2 | sibling sub-helper of midi_param_change_trace: calls c015f260 then rts_memset | guess | calls=c015f260,c0167b00=rts_memset; 1 caller c013150c |
| c013150c | midi_param_change_trace | the parameter-change diagnostic-trace entry point: builds the EDTB/PPRM record (diag_record_build_edtb c0130ab4), fills it via midi_param_trace_leaf1/2 (c0131468,c0131484), and gates on diag_mask_test (c0169fc0); called from midi_param_dispatch and 5 other MIDI/PreLoad sites; strings EDTB/PPRM | likely | calls=c0130ab4=diag_record_build_edtb,c0131468,c0131484,c0169fc0=diag_mask_test; 6 callers incl. midi_param_dispatch |
| c0131698 | preload_param_init_trace | PreLoad-time initializer that locks via midi_param_lock_op, calls c01296b4 and c012b180, then logs via midi_param_change_trace (c013150c); single caller preload_init_main (1180a3d0) | likely | calls=118092a0=midi_param_lock_op,c01296b4,c012b180,c013150c; roots=PreLoad,RhythmService,UpdateUI |
| c0131740 | mainapp_struct_copy | thin wrapper around rts_memcpy_word_sploop (c016d4c0) only; roots MainApp; single caller c0134a80 | guess | calls=c016d4c0=rts_memcpy_word_sploop; roots=MainApp |
| c01317c4 | midi_field_accessor | leaf with no calls listed, shared by 5 callers across midi_param_dispatch and MainApp/MIDI sites -- likely a fixed-field getter/setter | guess | roots=MIDI,MainApp; 0 calls; 5 callers |
| c0131800 | usb_desc_slot_set_if_changed_a | fetches a USB-descriptor table entry (usb_desc_entry_get_wrap c012f040), scales it (fixed_scale_mul_84_div c0130d28), compares it against the current entry in the custom-formatter table at 0x11811ca8, and only if different takes bios_sem_pend (B14 155), installs the new value via c0141684, then bios_sem_post -- a "write slot handler only if it changed" setter | confirmed | CALLP 0xc012f040,0xc0130d28; CMPEQ.L1X against 0x118111ca8[idx]; [match] skip; else CALLP 0xc0150b20=bios_sem_pend,0xc0141684,0xc01628e0=bios_sem_post; B14 global 155 |
| c0131870 | usb_desc_slot_get_a | fetches a USB-descriptor table entry via usb_desc_table_get + usb_desc_table_entry_get (c012efb0); called from the slot-get/rebuild family below | guess | calls=c012afe0=usb_desc_table_get,c012efb0=usb_desc_table_entry_get; 4 callers |
| c0131918 | usb_desc_slot_get_b | sibling accessor: usb_desc_table_get + c012b008 (no c012efb0); 2 callers (c01319a4,c0156680) | guess | calls=c012afe0=usb_desc_table_get,c012b008; 2 callers |
| c01319a4 | usb_desc_slot_resolve | combines rts_const_return_1 guard with usb_desc_slot_get_a/b (c0131870,c0131918) and c012afa0 -- resolves one descriptor slot's value, used throughout the rebuild family | likely | calls=c012af98=rts_const_return_1,c012afa0,c0131870,c0131918; 5 callers |
| c0131ab0 | usb_desc_slot_get_c | wraps usb_desc_slot_resolve (c01319a4) with an extra usb_desc_table_entry_get (c012efb0) fetch; 5 callers incl. c01320e8 | guess | calls=c012afe0=usb_desc_table_get,c012efb0=usb_desc_table_entry_get,c01319a4; 5 callers |
| c0131b44 | usb_desc_slot_set_if_changed_b | larger (320B) sibling of usb_desc_slot_set_if_changed_a: same get/scale/compare/lock-install shape (c012f040,fixed_scale_mul_84_div,c0131ab0,c0141784,bios_sem_pend/post), single caller c01320e8; B14 global 155 | likely | calls=c012af98=rts_const_return_1,c012f040,c0130d28=fixed_scale_mul_84_div,c0131ab0,c0141784,c0150b20=bios_sem_pend,c01628e0=bios_sem_post; B14 global 155 |
| c0131c84 | usb_desc_slot_set_if_changed_c | third sibling of usb_desc_slot_set_if_changed_a, same shape, single caller c015756c; B14 global 155 | likely | calls=c012f040,c0130d28=fixed_scale_mul_84_div,c0141684,c0150b20=bios_sem_pend,c01628e0=bios_sem_post; B14 global 155 |
| c0131d04 | usb_desc_slot_get_d | sibling of usb_desc_slot_get_c (usb_desc_table_get+usb_desc_table_entry_get+usb_desc_slot_resolve); 5 callers incl. the rebuild orchestrator's neighbors | guess | calls=c012afe0=usb_desc_table_get,c012efb0=usb_desc_table_entry_get,c01319a4; 5 callers |
| c0131d64 | usb_desc_slot_set_if_changed_d | fourth sibling of usb_desc_slot_set_if_changed_a using usb_desc_slot_get_d (c0131d04); callers c01302d8,c0132498; B14 global 155 | likely | calls=c012af98=rts_const_return_1,c012f040,c0131d04,c0141684,c0150b20=bios_sem_pend,c01628e0=bios_sem_post; B14 global 155 |
| c0131dd4 | usb_desc_slot_get_e | sibling accessor combining usb_desc_table_get+usb_desc_table_entry_get+usb_desc_slot_resolve; 5 callers | guess | calls=c012afe0=usb_desc_table_get,c012efb0=usb_desc_table_entry_get,c01319a4; 5 callers |
| c0131e34 | usb_desc_slot_get_f | combines usb_desc_slot_get_d and usb_desc_slot_get_e (c0131d04,c0131dd4) plus c0141684; single caller c0143470 | guess | calls=c012af98=rts_const_return_1,c012f040,c0131d04,c0131dd4,c0141684; 1 caller |
| c0131ea0 | usb_desc_slot_get_g | combines rts_const_return_1, c012afa0, usb_desc_slot_get_a (c0131870); single caller c01320e8 | guess | calls=c012af98=rts_const_return_1,c012afa0,c0131870; 1 caller |
| c0131f84 | usb_desc_slot_get_h | thin wrapper around usb_desc_slot_get_c (c0131ab0) with an rts_const_return_1 guard; single caller c01320e8 | guess | calls=c012af98=rts_const_return_1,c0131ab0; 1 caller |
| c0131fd4 | usb_desc_slot_get_i | sibling accessor (usb_desc_table_get+usb_desc_table_entry_get) with no further delegation; 2 callers (c01320e8,c015756c) | guess | calls=c012afe0=usb_desc_table_get,c012efb0=usb_desc_table_entry_get; 2 callers |
| c0132080 | usb_desc_slot_set_combined | combines usb_desc_slot_get_d/e (c0131d04,c0131dd4) with c0141684/c0141784 writes; 2 callers (c01320e8,c015756c) | guess | calls=c012f040,c0131d04,c0131dd4,c0141684,c0141784; 2 callers |
| c01320e8 | usb_desc_rebuild_all_slots | the master rebuild orchestrator (496B): calls the gain-ramp-clamped helpers (1180a9e0,1180aa28) plus every slot-get/slot-set sibling above (c0131870,c01319a4,c0131ab0,c0131b44,c0131ea0,c0131f84,c0131fd4,c0132080) and the config-table pointer c014ff44=cfg_table_ptr_11f03ad0, under bios_sem_pend/post (B14 155) -- rebuilds the whole USB MIDI descriptor/string table after an assignment change; single caller c01302d8 (midi_assign_apply_and_rebuild_desc) | likely | calls (19) incl. 1180a9e0=gain_ramp_slot_clamped,1180aa28=gain_ramp_slot_clamped2,c0131870,c01319a4,c0131ab0,c0131b44,c0131ea0,c0131f84,c0131fd4,c0132080,c014ff44=cfg_table_ptr_11f03ad0,c0150b20=bios_sem_pend,c01628e0=bios_sem_post; B14 global 155; not traced instruction-by-instruction given size |
| c01322d8 | usb_desc_slot_get_plain | plain single-call wrapper around usb_desc_table_get only; single caller c01302d8 | guess | calls=c012afe0=usb_desc_table_get; 1 caller |
| c0132364 | usb_desc_slot_get_j | sibling accessor (usb_desc_table_get+usb_desc_table_entry_get); single caller c015756c | guess | calls=c012afe0=usb_desc_table_get,c012efb0=usb_desc_table_entry_get; 1 caller |
| c01323d8 | usb_desc_slot_get_k | sibling accessor (usb_desc_table_get+usb_desc_table_entry_get); 2 callers (c015756c,c01576c0) | guess | calls=c012afe0=usb_desc_table_get,c012efb0=usb_desc_table_entry_get; 2 callers |

## Data

- `0x118115a0` (recon/01's table, write side `midi_cfg_table_fill` 118072ac):
  read side confirmed here by `cfg_record_find_by_id` (c012fd28, base
  0x118115a0ish), `fixed_scale_mul_84`/`fixed_scale_mul_84_div`
  (c0130d74/c0130d28) and `cfg_record_type_is_1` (c0130d50), all indexing
  by `value*84`, base offset 0x159c -> records are (at least) read as a
  first word compared/classified by small integer type codes (1, 30, 31,
  39, 40 seen as distinct tag values dispatched differently).
- `0x11811ca8` (+0x11811910 base per `custom_formatter_table_base_get`
  c0130a70): a second value*84-strided table of per-item custom-numeric
  formatter function pointers, read by `ui_row_render_numeric_custom`
  (c012e474) and `custom_formatter_table_get` (c0130a98), written (lock-
  guarded, only-if-changed) by the `usb_desc_slot_set_if_changed_*` family
  (c0131800, c0131b44, c0131c84, c0131d64).
- `0xc0184494..c01844a4` (5 words): glyph-draw jump table for
  `ui_glyph_dispatch` (c012e3a8), entries point at c0181258/1240/1228/
  1210/11f8 (fixed small bitmaps).
- `0xc0183e4c..c0183eac` (24 words): settings-menu action-code jump table
  for `midi_settings_action_dispatch` (c01308e4); several codes alias the
  same case-arm (see Data below and the per-arm `ptr@` lists).
- `0xc011abe4` (24-byte scratch buffer, "state buffer"): cleared by
  `state_buf_clear` (c012fc18), read/written as flag bytes at offsets 0,
  2(+variants) by `state_reset_and_elapsed` (c012fc40),
  `settings_flag_consume_notify` (c01305e8) and
  `settings_action_cfgptr_changed` (c0130654); also reused by
  `cfg_type_classify_scan` (c012fe68) to mark per-entry type-classification
  flags.
- B14[155]: a semaphore-guarded "current MIDI-assign/USB-descriptor"
  cache/handle, invalidated by `midi_apply_value_if_changed` (c012ec80) and
  locked around every `usb_desc_slot_set_if_changed_*` write and the whole
  `usb_desc_rebuild_all_slots` (c01320e8) pass.
- B14[154]: a second semaphore-guarded handle used by the
  `midi_assign_apply_variant1*` / `settings_action_dispatch_event`
  (c01307d4) path (mainapp_event_dispatch c01537a8 sits behind the same
  lock).
- ROM tag strings `EDTB`,`PPRM`,`PTCF`,`TXE1`,`TXJ1`,`empty` at
  0xc01810f2 area: read directly (inline byte compares, no strcmp call)
  by `diag_tag_field_extract` (c01312c4); same tag set built into the
  larger diagnostic record by `diag_record_build_edtb` (c0130ab4).

## Open questions

- Exact semantics of the type-tag values dispatched by
  `midi_apply_type11/30/31_setter` (c012ed0c/ece0/ed44) and by
  `cfg_type_classify` (c012fe18, codes 1/3 vs 39/40 vs other) are not
  established -- likely map to MIDI-assignable parameter storage classes
  (knob/switch/LED vs on/off) but no corroborating string evidence found
  in this range.
- `midi_settings_action_dispatch`'s (c01308e4) explicit non-table cases
  (25-28 -> c01303b8, 31-32 -> c0130138, 33 -> c016f530, 39-40 -> c012ff14)
  were decoded from the compare chain but the actual menu-item meaning of
  each numeric code is unknown; a future pass over the settings-menu data
  table near c0182b38 (per FWMAP.md) might cross-reference these codes to
  on-screen menu labels.
- `c016f520`/`c016f530`/`c016f540`/`c016f560`/`c016f570`/`c016f590`/
  `c016f600`/`c016f610`/`c016f640`/`c016f650`/`c016f720`/`c016f730`/
  `c016f740` are called repeatedly throughout this chunk's MIDI-apply and
  diag-trace clusters but lie just outside this chunk's range (c016e020..)
  and were not traced -- a worthwhile target for whoever maps that range,
  since pinning them would sharpen several "likely"/"guess" rows here.
- `c01311cc` (fmt_buffer_render) and its callers c015942c/c01594f0 look
  unrelated to the rest of this chunk's MIDI focus; not investigated
  further since they belong to a different, not-yet-mapped subsystem.
