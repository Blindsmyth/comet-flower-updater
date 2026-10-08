# Chunk 01 function map: 118072ac..1180b020

Summary: this range is the L2 (0x1180xxxx) task/driver region covering the
switch and knob input subsystems (normal-speed 10-button GPIO sampler and
its debounce/remap path, the two-footswitch sampler, the four-knob relative
encoder/accumulator path), the AD task's external serial converter read
(GPIO-bit-banged handshake plus i2c_write), the McASP/EDMA audio-engine
builder and ISR dispatch, the zero-target gain-ramp family, MIDI compose/
queue helpers shared with MainApp, LooperUI mute-group helpers, UpdateUI
screen-list/scroll helpers, and a block of small MainApp/UI orchestrators
entered through the c016e020/c016e000 save-restore pair. Most routines in
the low 1180axxx addresses are thin leaves or glue with few or no internal
branches; call-graph position and B14 slot reuse are the main evidence for
those, so many rows below are "likely" rather than "confirmed". Three
functions in this range are already named in recon/map/00_library_kernel.md
and are skipped here (see 00): 118093c0, 1180a2a8, 1180ad68.

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| 118072ac | midi_cfg_table_fill | entry via 1180bd10 save helper; scales arg0 by 84 (same stride as c0130d74 fixed_scale_mul_84) to index a table at 0x118115a0, then a 2-iteration loop copies a word per record via veneers 1180b830/1180ba40 | likely | read: `118072c0 MVK 0x0054,A1; 118072c4 MPYLI A1,A11,A7:A6`; base `118072c8/cc MVK 0x15a0/MVKH 0x11810000`; loop CALLP 0x1180ba40 x2, A12=2 |
| 11807310 | param_apply_5slot_ramp | entry 1180bd10; sets flag bits (arg0) into 0x1181312c via 1180a660, loops 5x (slot 0..4) via veneers 1180b810/1180b820 + 1180ae40, writes a config block at 0x11811ca8+105*8 via copy veneer 1180ba70, calls 1180a6a0 (5-slot guarded ramp-apply) always and 1180a50c/1180a4e8 (ramp family) only when arg1==0, then clears the flag via 1180a684 | likely | read: `11807348 CMPGT 5,A10,A0` loop bound; `1180734e MVK 105,A6; SHL A6,0x3,A6`=840; `11807366/11807374` arg1-gated branches around 1180a50c/1180a4e8 |
| 1180738c | midi_param_dispatch | large (~150 instr) dispatcher; calls 118072ac, 11807310, the ramp-flag family 1180a340/1180a350/1180a4a0/1180a4c4, knob accumulator 1180afc0, orchestrator_midi_compose c012ee10; called from 118075e4,c0128d14,c012d2e4,c01437f0 — central MIDI-controllable-parameter apply/send handler | likely | read first ~60 instr: entry 1180bd10, calls 11805f14,118063c8,11806450,11807220,118072ac,11807310,1180a340/50/4a0/4c4; full 150-instr body not exhaustively traced |
| 118075e4 | midi_param_dispatch2 | calls 1180738c, big_subsystem_init, diag_mask_test, wrapper_c016d240; B14[174]; sibling dispatcher gating 1180738c, not traced further | guess | calls=1180738c,c0155ac0,c0169fc0,c016d240; 1 caller c012f878 |
| 118076c0 | task_switch_nrml_spd_read | SwitchNrmlSpdRead task entry (named verbatim in FWMAP.md task list); samples the 10 normal buttons via c0156f00 and dispatches debounce/post through 1180a7ec | confirmed | recon/15: "SwitchNrmlSpdRead name c0172ef2 at c0181cd4, entry 118076c0 at c0181cb8"; `118076c0 CALLP 1180bd10; 118076c8 CALLP 1180b710` |
| 118077e8 | switch_event_remap | remaps the footswitch event id before the non-blocking queue post in 11807a54 (used for the both-feet-held combined gesture) | confirmed | recon/15: "A remapper 118077e8 can substitute the event before the nonblocking queue post at 11807a80" |
| 11807858 | footswitch_debounce_sample | two-footswitch debounce: waits elapsed>19 ticks, assigns event 2*i / 2*i+1 per changed+sampled bit, sampling via c0157034/1180954c (GPIO3/GPIO5) | confirmed | recon/15: `118078e4 MVK 19,A1; 118078ea CMPGTU A0,A1,A0`; `11807968 ADD A10,A10,A0` (event=2*i); both offsets fall inside this function's 396-byte span (11807858..118079e4) |
| 118079e4 | footswitch_coincidence_check | detects a two-switch coincidence within <=100 ticks and overrides the event to 4 (combined footswitch gesture) | confirmed | recon/15: `11807a22 MVK 100,A0; 11807a2e MVK 4,A0`; offsets fall inside this function's 112-byte span (118079e4..11807a54) |
| 11807a54 | footswitch_event_post | applies the remap 118077e8, then posts the (possibly remapped) event non-blocking (timeout 0, A6=0) via the mailbox veneer 1180b6f0 -> c0166780 | confirmed | recon/15: `11807a80` queue post, A6=0; fact sheet calls=(118077e8,c0166780,...) matches |
| 11807ac0 | wrapper_11807ac0 | tiny leaf calling only c0168640; part of a B14[99]-keyed UI/effect-slot dispatch chain | guess | calls=c0168640; 5 callers (11807aec,11807d54,c0148c48,c0148d40,c0157748) |
| 11807aec | orchestrator_11807ac0 | calls 11807ac0, c0148ac0, c0157970; B14[99]; same dispatch-chain family as 11807b48/ba8 | guess | calls=11807ac0,c0148ac0,c0157970; b14=99 |
| 11807b48 | orchestrator_b14_99 | B14[99]-keyed dispatcher calling 11807aec, bridge_status_struct (c0156d68), c0157984 | guess | calls=11807aec,c0156d68,c0157984; b14=99 |
| 11807ba8 | orchestrator_b14_99b | B14[99]-keyed, calls 11807b48 and c0155348 | guess | calls=11807b48,c0155348; b14=99 |
| 11807bec | tiny_dispatch_c0148ff4 | 2-call leaf (c0155304,c0155404), only reached from c0148ff4 | guess | calls=c0155304,c0155404; 1 caller |
| 11807c08 | orchestrator_11809a0c | calls 11805e2c,11807b48,11809a0c,11809aac,c014ace0-family, bridge_status_struct; B14[99] | guess | calls incl. 11809a0c,11809aac,c0156d68; b14=99 |
| 11807c84 | wrapper_11807c84 | calls c0130a00,c01418ec; only reached from 11807d54/c0148c48 | guess | calls=c0130a00,c01418ec; 2 callers |
| 11807d24 | effect_slot_dispatch1 | calls 11807ba8, mainapp_event_dispatch (c01537a8), c0155304, orchestrator_locked_small, effect_slot_lookup — ties into the effect-slot state-query chain | guess | calls=11807ba8,c01537a8,c0155304,c015c0f8,c015c164; 1 caller c0149004 |
| 11807d54 | effect_slot_dispatch2 | large (18-call) B14[99,154] dispatcher chaining 11807ac0/aec/b48/c84, bios_sem_pend, cfg_ptr_11810000_325c, bridge_status_struct, orchestrator_locked_small, effect_slot_lookup, bios_sem_post — top of the effect-slot dispatch chain | guess | b14=99,154; calls incl. c0150b20,c0155328,c0156d68,c015c0f8,c015c164,c01628e0; 1 caller c0149010 |
| 11807ea0 | usbstr_helper1 | 12-byte leaf, calls c013b7e8; 7 callers — part of a usb-descriptor/numeric-formatting cluster inferred from callee names (usb_desc_table_get, fmt_render_wrapper) below, not independently disassembled | guess | calls=c013b7e8; 7 callers |
| 11807eac | usbstr_helper2 | 12-byte leaf, calls c013b828; sibling of 11807ea0, 4 callers | guess | calls=c013b828; 4 callers |
| 11807eb8 | usbstr_builder1 | calls 11807ea0, rts_const_return_1, c012b048, c012f628 — part of the usb-descriptor string-formatting chain | guess | calls=11807ea0,c012af98,c012b048,c012f628; 1 caller 11807f04 |
| 11807f04 | usbstr_builder2 | calls 11807ea0,11807eb8,c012b048, rts_udiv32 — division suggests decimal-digit formatting | guess | calls=11807ea0,11807eb8,c012b048,c0168580; 1 caller 11807f4c |
| 11807f4c | usbstr_builder3 | calls 11807ea0,11807eac,11807f04, rts_const_return_1, c012ee80 | guess | calls incl. 11807f04,c012af98,c012ee80; 1 caller 11808200 |
| 11807fe0 | usbstr_builder4 | calls 11807ea0,11807eac,c012b108,c012ee80,c0132510,c0132560 | guess | 1 caller 118080b4 |
| 118080b4 | usbstr_builder5 | calls 11807ea0,11807eac,11807fe0,c012ad1c,c012ee80 | guess | 1 caller 1180814c |
| 1180814c | usbstr_builder6 | calls 11807ea0,118080b4,c012b108,c0132510,c0132560 | guess | 1 caller 11808200 |
| 118081e0 | usbstr_leaf1 | calls only c012ee80; 1 caller 11808200 | guess | n=12 |
| 118081ec | usbstr_leaf2 | 4-byte stub, no calls recorded; 1 caller 11808200 | guess | n=4 |
| 118081f0 | usbstr_leaf3 | calls only c012f040; 1 caller 11808200 | guess | n=16 |
| 11808200 | usbstr_dispatch | dispatcher calling 11807ea0,11807eac,11807f4c,1180814c,118081e0/ec/f0 — top of the usb-string/descriptor formatting cluster; 2 callers 11808360/11808440 | guess | calls incl. the seven leaves above |
| 11808280 | usbdesc_helper | calls usb_desc_table_get (c012afe0=c012b008 veneer); 2 callers 11808360/11808440 | guess | calls=c012b008 |
| 118082b4 | usbdesc_fmt2 | thin wrapper around fmt_render_wrapper2 (c016a100); 1 caller 11808360 | guess | calls=c016a100 |
| 118082f8 | usbdesc_fmt1 | thin wrapper around fmt_render_wrapper (c016c360); 1 caller 11808360 | guess | calls=c016c360 |
| 11808320 | usbdesc_fmt3 | calls c012b324, fixed_scale_mul_84 (c0130d74), c013b7e8, fmt_render_wrapper; 1 caller 11808360 | guess | calls=c012b324,c0130d74,c013b7e8,c016c360 |
| 11808360 | usbdesc_builder_main | orchestrates 11808200/280/82b4/82f8/8320 plus usb_desc_table_get, orchestrator_midi_compose, c012f068, fixed_scale_mul_84_div; builds a formatted USB-descriptor/MIDI string; 1 caller 1180af60 | likely | 12 calls incl. c012afe0,c012ee10,c0130d28; 1 caller |
| 11808440 | usbdesc_builder_alt | sibling of 11808360 (calls 11808200,11808280,usb_desc_table_get,c012db40,c013b7e8); 1 caller 1180af8c | guess | calls=11808200,11808280,c012afe0,c012db40,c013b7e8 |
| 11808560 | ad_init_stub | tiny (12-byte) leaf, no calls recorded; 1 caller 1180abc0 — part of the AD init sequence | guess | n=12 |
| 1180856c | ad_gpio_setup | AD peripheral setup: pokes 8 MMIO fields via shared helpers c01609f0,c0160a04..c0160a84 (the same helper set 118086e4/MainApp uses), then calls 11808ac0; 1 caller 1180abc0 | likely | calls incl. 11808ac0, 8x c0160a0x, hwi_guarded_divide_update; roots AD |
| 11808654 | ui_buf_clear | clears a buffer via rts_memset; shared by MainApp/UpdateUI redraw sites | likely | calls=c0167b00; 4 callers (118086e4,11808cb0,c013c204,c013c514) |
| 118086a4 | mainapp_helper_86a4 | 64-byte leaf, no calls recorded; 1 caller 118086e4 | guess | n=64 |
| 118086e4 | mainapp_bigsetup | calls 11808654,118086a4, the same 8 MMIO-poke helpers (c01609f0..c0160a84) 1180856c uses, bios_sem_post, rts_memset, wrapper_c016bfa0; B14[183]; 1 caller c015d428 (MainApp init path) | likely | calls incl. 8x c0160a0x, c01628e0, c0167b00; b14=183 |
| 11808838 | i2c_rate_div | computes a divide (rts_udiv32) for the I2C transaction, e.g. a bus-speed/clock-divider value; 1 caller 118088d0 (i2c_write) | likely | calls=c0168580 |
| 118088d0 | i2c_write | i2c_write(buf,len,dev); far stub c016f200; locks B14[182/183] via bios_sem_pend, computes rate via 11808838, transfers, diag_mask_test, releases via bios_sem_post; 1 caller c013dca0 | confirmed | recon/16: "0x118088d0 i2c_write(buf, len, dev) (L2 code; far stub c016f200)" |
| 11808ac0 | ad_gpio_table_init | 212-byte leaf, no further calls recorded; 1 caller 1180856c — likely a bulk GPIO pin-table init for the AD serial handshake lines | guess | n=212, calls=none; roots AD |
| 11808b94 | updateui_leaf_b94 | 12-byte leaf, 1 caller c013c218 | guess | n=12 |
| 11808ba0 | updateui_divhelper | calls hwi_guarded_divide_update; 1 caller 11808bc8 | guess | calls=c016b540 |
| 11808bc8 | updateui_scroll_helper | calls 11808ba0; UpdateUI scroll/position helper, 4 callers incl. c014dbb8,c0160d8c | guess | calls=11808ba0; 4 callers |
| 11808c44 | rhythm_div_helper | calls hwi_guarded_divide_update; 1 caller wrapper_c016c060 — RhythmService timing divide | guess | calls=c016b540; roots RhythmService |
| 11808c68 | updateui_scroll_thunk | thin wrapper calling 11808bc8; 2 callers c0160d58/e30 | guess | calls=11808bc8 |
| 11808ca4 | updateui_leaf_ca4 | 12-byte leaf, no calls; 4 callers incl. 11808cb0,11808d00,c013c218,c0160dd4 | guess | n=12 |
| 11808cb0 | updateui_item_clear | calls 11808654 (buf clear),11808ca4,ptr_const_118130a0; 6 callers across UpdateUI screen handlers | likely | calls=11808654,11808ca4,c016bff0 |
| 11808d00 | updateui_item_clear2 | calls 11808ca4; sibling of 11808cb0, 2 callers 11808ed0/c013c514 | guess | calls=11808ca4 |
| 11808d50 | updateui_scroll_main | calls 11808bc8 three times; B14[129]; 1 caller 11808ed0 — larger UpdateUI scroll routine | guess | calls=11808bc8 x3; b14=129 |
| 11808ed0 | updateui_screen_switch | calls 11808d00,11808d50,c0150830; 2 callers 11808f00/c013c674 | guess | calls incl. 11808d00,11808d50 |
| 11808f00 | updateui_screen_switch2 | calls 11808ed0,ptr_const_118130a0; 2 callers c01507d8/c0150844 | guess | calls=11808ed0,c016bff0 |
| 11808f40 | task_ad_main | AD task body; registered task entry 11809004 (named verbatim in FWMAP.md task list) falls 196 bytes into this 544-byte block; calls the serial-read sequencer 1180abc0, locked_lookup_big, hwi_guarded_divide_update | confirmed | recon/15,18: "Task 11809004 calls read routine 1180abc0"; 11809004-11808f40=0xc4 < size 544 |
| 11809160 | datastore_copy_helper | calls c0136720/744/7f8, bios_sem_post; B14[177]; 1 caller wrapper_c016d300 — DataStore/UpdateUI shared copy helper | guess | b14=177; roots DataStore,UpdateUI |
| 11809224 | midi_lock_wait | calls bios_sem_pend, diag_mask_test; B14[177]; 1 caller wrapper_c016be20 | guess | calls=c0150b20,c0169fc0; b14=177 |
| 118092a0 | midi_param_lock_op | takes/releases a lock (bios_sem_pend/post) around c01454f4; B14[177]; 8 callers across MIDI/MainApp/PreLoad/RhythmService/UpdateUI — generic locked-operation wrapper | likely | calls=c01454f4,c0150b20,c01628e0; b14=177; 8 callers |
| 1180933c | datastore_copy2 | calls rts_memcpy_word_sploop only; 1 caller wrapper_c016d300 | guess | calls=c016d4c0 |
| 118093c0 | sign_test_predicate | see 00_library_kernel.md | — | already named |
| 11809420 | gpio_set_helper1 | thin wrapper around sign_test_predicate (118093c0); 4 callers incl. orchestrator_1180_region2,11805484,1180ab20,c0160b80 | likely | calls=118093c0 |
| 1180942c | gpio_set_helper2 | sibling of 11809420 (calls 118093c0 only); 1 caller 1180ab20 | likely | calls=118093c0 |
| 11809438 | gpio_set_helper3 | sibling of 11809420 (calls 118093c0); 2 callers orchestrator_1180_region2,11805484 | likely | calls=118093c0 |
| 11809458 | batt_gpio_drive | drives/reads a GPIO pin via sign_test_predicate (118093c0), analogous to AD's 11809474 pattern; 1 caller 11809b80 (BatteryManagement) | likely | calls=118093c0; roots BatteryManagement |
| 11809474 | ad_gpio90_drive | drives GPIO 90 low/high via sign_test_predicate (118093c0); part of the AD serial-converter handshake performed inside 1180abc0 | confirmed | recon/15: "drives GPIO 90 low via 11809474 -> 118093c0" |
| 11809484 | gpio_read_bit | reads *(GPIO_base + 40*(pin>>5) + 32) and extracts bit pin&31; GPIO_base=01e26000 | confirmed | recon/15: `118094a2 SHR A4,5,B0; ...; 118094b2 LDW *A5[8],A0; 118094b6 SHRU A0,A1,A0` |
| 118094c4 | gpio_pin_select_idx | indexed pin selector: maps index 0..5 to pins 27,24,26,37,38,86 (default 0 for index 6) then reads via 11809484; reached via veneer c016f1a0 | confirmed | recon/15: "118094c4..9504 selects pins 27,24,26,37,38,86 for indices 0..5 and defaults to 0 for index 6" |
| 1180950c | gpio_read_fixed | thin wrapper calling 11809484 for one fixed pin; callers incl. task 118076c0, 11809d08, wrapper_c016c120 | guess | calls=11809484 |
| 11809524 | gpio_read_direct1 | one of the three direct (non-indexed) normal-button GPIO readers feeding c0156f00's 10-bit sample; veneer c016f1b0 target | confirmed | recon/15: "assembles bits 0..9 from three direct readers and seven indexed readers" |
| 11809530 | gpio_read_direct2 | second direct GPIO reader; veneer c016f1d0 target | confirmed | recon/15 veneer-resolution list |
| 11809540 | gpio_read_direct3 | third direct GPIO reader; veneer c016f1c0 target | confirmed | recon/15 veneer-resolution list |
| 1180954c | gpio_read_footsw | two-footswitch pin selector: index0=GPIO3, index1=GPIO5, via 11809484 | confirmed | recon/15: `11809550/54/56/58`: "index 0 reads GPIO3; index 1 reads GPIO5" (offsets fall inside this 36-byte function) |
| 11809570 | task_popup_time_counter | PopUpTimeCounter task entry 11809580 (named verbatim in FWMAP.md task list) falls 16 bytes inside this 296-byte block; reads a GPIO (11809484), pends/posts B14[159], calls locked_lookup_big; also reached from BatteryManagement | likely | 11809580-11809570=0x10 < size 296; task-table name match; b14=159 |
| 11809698 | looper_mute_lock_op | locked op (bios_sem_pend/post) around B14[159]; 1 caller 1180ad40 — LooperUI/MainApp mute-group helper | likely | calls=c0150b20,c01628e0; b14=159; roots LooperUI,MainApp |
| 11809718 | ui_ad_helper | 104-byte leaf, no calls recorded; 2 callers 1180ad58, orchestrator_1180_region (1180ad68) — roots AD/MainApp/UpdateUI | guess | n=104, calls=none |
| 11809780 | updateui_list_render1 | calls orchestrator_1180_region, c0137708/18/28/38, c015e280/3b8 — UpdateUI list/menu render helper | guess | 2 callers 11809948,c013c5e8 |
| 118097f8 | updateui_render_thunk | thin wrapper around orchestrator_c011c990 (gfx dispatch); 1 caller 11809830 | guess | calls=c011cb64 |
| 11809830 | updateui_list_render2 | calls 118097f8, fixed_point_math_big, tailcall_wrapper_c016ad20_c016acc0 — sibling render routine | guess | calls=118097f8,c0146ee0,c016acc0 |
| 11809948 | updateui_list_render_top | calls 11809780,11809830,c0158f00/38; 1 caller c01697c8 — top of the UpdateUI list-render pair | guess | calls=11809780,11809830 |
| 11809980 | midi_scale_wrap | thin wrapper around fixed_scale_mul_84 (c0130d74); 5 callers across MIDI/MainApp/UpdateUI | likely | calls=c0130d74 |
| 118099a0 | midi_compose_wrap1 | calls 11809980, orchestrator_midi_compose (c012ee10); 3 callers incl. 1180aea0 | likely | calls=11809980,c012ee10 |
| 118099e4 | midi_compose_wrap2 | calls 118099a0; 3 callers 11809a0c/a8c/aac | guess | calls=118099a0 |
| 11809a0c | midi_compose_wrap3 | calls 118099e4; 2 callers 11807c08,1180a734 | guess | calls=118099e4 |
| 11809a34 | midi_ctl_helper1 | calls c01618ac/c0 (outside chunk); 3 callers 11809a58/aac/b34 | guess | calls=c01618ac,c01618c0 |
| 11809a58 | midi_ctl_helper2 | calls 11809a34, c01618b4; 2 callers 11809a8c,c014abd0 | guess | calls=11809a34,c01618b4 |
| 11809a8c | midi_ctl_helper3 | calls 118099e4,11809a58; 4 callers incl. 1180a6a0,c0143470,c0150738 | guess | calls=118099e4,11809a58 |
| 11809aa0 | midi_ctl_thunk | thin wrapper calling 11809a8c; 1 caller c0141684 | guess | calls=11809a8c |
| 11809aac | midi_compose_wrap4 | calls 118099e4,11809a34; 2 callers 11807c08,1180a734 | guess | calls=118099e4,11809a34 |
| 11809aec | midi_queue_post | calls 1180b06c (event-post veneer outside chunk); 1 caller 11809b34 | guess | calls=1180b06c |
| 11809b04 | midi_sdiv_helper | thin wrapper around rts_sdiv32; 1 caller 11809b34 | likely | calls=c01675c0 |
| 11809b34 | midi_expr_apply | calls 118099a0,11809a34,11809aec,11809b04,c01600c8; 1 caller c014aef4 — c014aef4/B14[155] is the stock expression-pedal acquisition site recon/18 flags, so this is plausibly part of the expression-value compose/apply path | likely | calls incl. 118099a0,11809a34,11809aec,11809b04; recon/18 names c014aef4's B14[155] acquisition |
| 11809b80 | batt_gpio_read_step | calls 11809458 (battery GPIO drive/read step); 1 caller 11809bd4 (BatteryManagement task) | likely | calls=11809458; roots BatteryManagement |
| 11809bd4 | task_battery_management | BatteryManagement task entry (named verbatim in FWMAP.md task list); calls 11809570,11809b80,locked_lookup_big; B14[112] | confirmed | FWMAP.md task list: "BatteryManagement ... 11809bd4"; calls=11809570,11809b80,c0158980 |
| 11809d08 | repeat_event_handler_helper | calls 1180950c, knob/event post 1180b000, bios_sem_pend, locked_lookup_big, bios_sem_post, hwi_guarded_divide_update; B14[157]; 1 caller c01635c0 — roots incl. RepeatEventHandler/AD/MIDI/MainApp/UpdateUI | likely | calls incl. 1180950c,1180b000,c0150b20,c0158980,c01628e0; b14=157 |
| 11809f00 | ad_subsystem_init | calls 11805e64, big_subsystem_init; B14[48,50,127,165]; 1 caller 1180abc0 — likely an AD one-time init path (multiple B14 slots touched) | guess | b14=48,50,127,165; calls=11805e64,c0155ac0 |
| 1180a070 | rhythm_leaf1 | 16-byte leaf, no calls recorded; 2 callers 11806eb4,c015402c — RhythmService | guess | n=16; roots RhythmService |
| 1180a080 | rhythm_leaf2 | 32-byte leaf, no calls recorded; same 2 callers as 1180a070 | guess | n=32; roots RhythmService |
| 1180a0a0 | updateui_gfx_dispatch | calls big_subsystem_2 (c011d938), cfg_get_global_c011ad8c, 11804124, 118048fc; B14[184]; 1 caller c013c644 | guess | calls incl. c011d938,c0156e80; b14=184 |
| 1180a130 | ad_init_path | calls orchestrator_1180_region (1180ad68), 1180af34, c01497d0, big_subsystem_init, cfg_get_global_c011ad8c, c0158f00, c01635f8/3640; B14[139]; 1 caller 1180abc0 — a second AD init/config branch alongside 11809f00, not distinguished further | guess | b14=139; calls incl. 1180ad68,1180af34,c0155ac0,c0156e80 |
| 1180a220 | gain_ramp_core | calls locked_lookup_big; 1 caller 1180a2a8 (audio_gain_ramp_div) — the core per-step ramp iteration body | likely | calls=c0158980; 1 caller=1180a2a8; recon/16 |
| 1180a2a8 | audio_gain_ramp_div | see 00_library_kernel.md | — | already named |
| 1180a340 | ramp_flag_clear_1268c | clears flag word 0x1181268c (disables the audio-side ramp-update handshake); 9 callers | confirmed | recon/16: "the second clears 1181268c via 1180a340" |
| 1180a350 | ramp_flag_set_1268c | sets flag word 0x1181268c=1; 9 callers | confirmed | recon/16: "1180a350 (sets 1181268c=1)" |
| 1180a380 | preload_init_step | calls c0127fe0, c0144580, big_subsystem_init; B14[100,174]; 1 caller 1180a3d0 | guess | b14=100,174; calls=c0127fe0,c0144580,c0155ac0; roots PreLoad,RhythmService,UpdateUI |
| 1180a3d0 | preload_init_main | calls 1180626c,1180a380,c0131698,c014c0b0,bios_sem_pend,bios_sem_post; B14[175]; 1 caller 1180a448 | guess | b14=175; calls incl. 1180a380,c0150b20,c01628e0 |
| 1180a448 | preload_init_thunk | calls 1180a3d0, c014bfc8; 1 caller wrapper_c016c090 | guess | calls=1180a3d0,c014bfc8 |
| 1180a4a0 | gain_ramp_up | ramps a parameter up to target, companion of the 1181268c clear path, calls audio_gain_ramp_div 1180a2a8; 6 callers | confirmed | recon/16: "ramps up via 1180a340" lineage; calls=1180a2a8 |
| 1180a4c4 | gain_ramp_to_zero | zero-target gain ramp, companion of the 1181268c set path, calls audio_gain_ramp_div 1180a2a8; 6 callers | confirmed | recon/16: "1180a4c4 (zero-target gain ramp through 1180a2a8/1180a220)" |
