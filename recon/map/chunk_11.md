# chunk_11: c0149648..c014d124 (150 functions)

Summary: (in progress)

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| c0149648 | tbl_veneer_c0164950 | 2-instr trampoline: CALLP 0xc0164950,B3 then join shared return at c014965c; one of 3 adjacent table slots sharing that tail | likely | read c0149648..c014965c in full; ptr@ c0184144 |
| c0149650 | tbl_veneer_c0157c44 | same trampoline shape calling c0157c44, joins the c014965c tail | likely | read in full; ptr@ c0184140 |
| c0149658 | tbl_veneer_c0157c50 | same trampoline shape calling c0157c50, joins the c014965c tail | likely | read in full; ptr@ c018413c |
| c0149664 | ui_active_item_switch | resolves a new id via c01495c0(A4); compares the result against the pointer stored at B14[120] (current active UI item); if unchanged, returns; else calls the old item's field+20(word5) callback if set, stores the new pointer into B14[120], then calls the new item's field+16(word4) callback if set -- an activate/deactivate switch for "the current active item/popup" | confirmed | read c0149664..c01496b0 in full: `LDW *+B14[120],B1; CMPEQ B1,A0,B0` skip-if-same; `LDW *B4[5],B0;[B0] B.S2 B0` old->cb; `STW A0,*+B14[120]`; `LDW *A4[4],A0;[A0] B.S2X A0` new->cb |
| c01496b4 | ui_active_item_select_2 | thin wrapper: calls c0149664 with argument 2 | confirmed | read in full: `CALLP 0xc0149664,B3 \|\| MVK 2,A4`; 1 caller c0156e08 |
| c01496c4 | ui_active_item_clear_all | thin wrapper: calls updateui_item_clear(-1) via veneer c016f2a0 | confirmed | read in full: `MVK -1,A4 \|\| CALLP 0xc016f2a0,B3`; fact sheet resolves c016f2a0 to 11808cb0=updateui_item_clear; 1 caller c0156d04 |
| c01496d0 | ui_active_item_reset_and_redraw | deactivates id 0xfff then selects id 0 via two calls to c0149664; then, gated by checks through c016f6d0 / midi_field_accessor(c01317c4) / midi_apply_from_b14_27_wrap(c012f7a4), takes the B14[154] lock and calls mainapp_screen_draw_common_wrap_a(c01363ac), finally clearing B14[23] | confirmed structure, guess purpose | read c01496d0..c0149720 in full; exact triggering condition not established |
| c0149724 | ui_active_item_update | if B14[120] (active item) is set and its field+28(word7) callback is non-null, calls c0160dd4 then tail-calls that callback -- per-frame "update the active item" hook, matches UpdateUI root | confirmed | read c0149724..c014974c in full |
| c0149750 | ui_item9_dispatch_arg_self | resolves fixed id 9 via c01495c0, loads its field+32(word8) callback and tail-calls it passing the resolved record itself as argument | confirmed | read c0149750..c0149770 in full |
| c0149774 | ui_item9_field16_call1 | resolves fixed id 9, loads its field+16(word4) callback, tail-calls it with A4=1 | confirmed | read c0149774..c0149790 in full |
| c0149794 | ui_item9_field24_call1 | resolves fixed id 9, loads its field+24(word6) callback, tail-calls it with A4=1 | confirmed | read c0149794..c01497ac in full |
| c01497b0 | ui_active_item_type6_render | if B14[120] (active item) exists and its type/field0 == 6, calls c014c84c (the char/level-edit popup renderer) | confirmed | read c01497b0..c01497cc in full |
| c01497d0 | ui_active_item_type6_value | if active item exists and type/field0 == 6, returns c014c838()'s result, else returns 0 -- getter paired with c01497b0 | confirmed | read c01497d0..c01497f0 in full |
| c01497f4 | ui_active_item_get_type_or_none | getter: returns the active item's type/field0 word, or sentinel 0xfff if no active item | confirmed | read c01497f4..c014980c in full |
| c014980c | ui_type_not_6_or_7 | predicate: true unless the record's field0 is 6 or 7 (`ADD A0,-6,A0; CMPLTU 1,A0,A0`) | confirmed | read c014980c..c014981c in full |
| c0149820 | ui_active_item_type_gate | predicate on the current active item's type (via c01497f4): returns 0 if type<=1, 0 if type==9, else 1 | confirmed | read c0149820..c014983c in full |
| c0149840 | ui_popup_type_dispatch_11_20 | if the current screen id (c0156e80=cfg_get_global_c011ad8c) == 7 and the input record's type/field0 is in [11..20], tail-calls a handler from a 10-entry table at c018427c indexed by (type-11)*4; outside that range or screen, falls into the shared tail at c01498b8 (inside c01498a2) | likely | read c0149840..c0149884 in full |
| c0149888 | ui_popup_flag_check | checks byte flag array c01152e0[record->field+2]; if set, jumps directly into c01498a2's body at its +0x22 label (c01498c4); if clear, jumps into its +0x3e label (c01498e0) -- a gated entry point into the function below, not an independent return | likely | read c0149888..c01498a2 in full |
| c01498a2 | ui_popup_activate_dispatch | sets byte flag c01152e0[record->field+2]=1 (entry also reachable via c0149888's gate), then: if type==5 sets B14[23]=1; else if type==6 or B14[23] already set, keeps the caller's arg; otherwise checks c014980c (not 6/7) and c0149820 (type gate) and, if both pass, calls the record's field+32(word8) callback directly with the record; on the fallback paths calls effect_slot_lookup(c015c164), orchestrator_locked_small(c015c0f8), c0156e8c and mainapp_rhythm_menu_popup_open(c0135b70) before restoring/returning | likely | read c01498a2..c0149948 (166 instr) in full; business meaning of types 5/6 not established |

| c0149948 | ui_record44_field_dispatch | entered with (idx A4, record A6->A12, extra B4->A11); computes idx2=record->field0-25 and bounds-checks the caller's idx against it; out of range just returns a flag; in range calls c0158f84(record->field+12=word3), then indexes a 44-byte-stride array at A12+44*idx2 and, depending on sub-checks, tail-calls through that entry's word8/word9/word10 callbacks or calls c0153464 plus c01418ec using its word6 field | likely | read c0149948..c0149a08 (166 instr) in full; the array's identity/class is not established |
| c0149a0c | ui_active_item_reset_default13 | gets current type (c01497f4), calls c0157944, zeroes a 28-byte struct at c01152e0 (rts_memset), clears B14[23], deactivates id 0xfff then selects id 13 via c0149664 | confirmed | read c0149a0c..c0149a40 in full |
| c0149a44 | wrapper_c0152eb0_00 | thin forwarder: tail-calls c0152eb0(0,0) | confirmed | read in full: `MVK 0,A4 \|\| CALLP 0xc0152eb0,B3 \|\| MVK 0,B4` |
| c0149a54 | wrapper_c0145eac_00 | thin forwarder: tail-calls c0145eac(0,0) | confirmed | read in full |
| c0149a68 | ui_active_item_field24_call_gated | if A4 (caller flag) and B14[120] (active item) and its field+24(word6) callback are all non-null, tail-calls that callback | confirmed | read c0149a68..c0149a90 in full |
| c0149a90 | ui_active_item_cycle | if current type (c01497f4) is the 0xfff sentinel, returns 0; else steps the type by +1 or -1 (sign of caller's arg), clamps to [2,12], selects the result via c0149664, returns 1 | confirmed | read c0149a90..c0149ad4 in full |
| c0149ad4 | ui_record_field_select | resolves id via c01495c0(A4), then by selector B4: 0 returns the record pointer itself, 1 returns its field+4(word1), 2 returns field+8(word2), anything else returns 0 | likely | read c0149ad4..c0149b1c in full; staggered-delay-slot branch encoding, switch intent clear but not re-derived cycle-by-cycle |

## Data
- B14[120]: pointer to the current active UI item/popup descriptor. Callback layout observed: word4(+16)=activate, word5(+20)=deactivate, word6(+24)=misc(called with arg 1), word7(+28)=per-frame update, word8(+32)=activate-dispatch callback. word0 = type/id (0xfff sentinel = none).
- B14[23], B14[154]: flags/lock touched by the c0149664/c01496d0/c01498a2 family; B14[154] guards mainapp_screen_draw_common_wrap_a.
- c01152e0: byte flag array indexed by record->field+2(offset8), read/set by c0149888/c01498a2.
- c018427c..c01842a4: 10-word function-pointer table for popup types 11..20, alternating between the c0149888-style and c01498a2-style entry points.

## Open questions

## Open questions
