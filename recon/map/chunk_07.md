# chunk_07: c0136674..c013b1f4 (150 functions)

Summary: mapping in progress; this range begins with MainApp screen helpers and configuration persistence routines.

| addr | name | role | conf | evidence |
|---|---|---|---|---|

| c0136674 | mainapp_rhythm_screen_draw_35 | Draw rhythm screen with selector 35. | confirmed | c0136676 CALLP c0136590; c0136678 MVK 35,A4 |
| c0136684 | mainapp_screen_draw_5aec | Draw common screen using callback c0135aec and selector 50. | confirmed | c0136688 MVK 0x5aec,B6; c0136694 CALLP c01361ac |
| c01366a0 | mainapp_screen_draw_5afa | Draw common screen using callback c0135afa; fact range also includes a subsequent numeric lookup routine. | likely | c01366a4 MVK 0x5afa,B6; c01366b0 CALLP c01361ac; new save at c01366b8 |
| c0136720 | cfg_round_up_multiple | Round a value upward to a divisor boundary using remainder. | likely | c0136728 CALLP c0169980; c0136732 SUB A3,A0,A0; c0136734 ADD A2,A0,A0 |
| c0136744 | cfg_write_metadata_words | Persist a sequence of four-byte metadata fields from 11819cf0 onward. | likely | c0136758/c0136764 form 11819cf0; c0136760 CALLP c01453b4; A6=4 |
| c01367f8 | cfg_datastore_write_sections | Write configuration sections and metadata from the DataStore copy path. | likely | c0136804 MVK 0x3448,A3; c0136824/c0136828 form c0183a50; c01369b8 CALLP c01453b4 |
| c01369d0 | cfg_wait_write_barrier | Acquire then release the semaphore in B14 slot 177. | confirmed | c01369d4 LDW *+B14[177],A4; c01369d8 CALLP c0150b20; c01369e0 CALLP c01628e0 |
| c01369f0 | cfg_count_nonzero_words | Count nonzero words in an array of B4 elements. | confirmed | c0136a00 LDW *B4++[1],B0; c0136a04 conditional branch skips c0136a08 ADD A1,1,A1 |
| c0136a18 | cfg_mainapp_write_sections | Persist selected configuration sections and report progress/status. | likely | c0136a24/c0136a28 form 1181344c; c0136a54 CALLP c0136720; writer calls and B14[178] in fact sheet |
| c0137204 | cfg_mainapp_write_finalize | Write remaining configuration metadata and mark completion. | likely | c0137224 CALLP c0145568; c0137318 CALLP c01529c0; c0137332 STW 1 to 1181344c |
| c0137340 | ui_update_popup_frame | Draw the shared frame/content used by update success and failure popups. | likely | c0137354 CALLP c011d938; c013736c CALLP c0142ec4; c0137378 CALLP c013a2d8 |
| c0137388 | ui_settings_draw_backdrop | Draw fixed 128-wide graphics using asset c017a8d8. | likely | c0137390 MVK 0x80,B6; c0137398 CALLP c011c508; c01373a4 MVK 20,A8 |
| c01373ac | ui_output_draw_scaled_indicator | Select and draw an indicator from a scaled value. | likely | c0137400 CALLP c016ad40; c01374a0 SHL A4,5,A0; c01374b8 CALLP c011c508 |
| c01374c8 | ui_settings_draw_output | Render the OUTPUT settings panel and its scaled indicator. | likely | fact string OUTPUT; c01374d4 CALLP c011d938; c0137700 CALLP c01373ac |
| c013770c | ui_settings_field_10 | Invoke shared field renderer with parameter 10. | confirmed | c013770e MVK 10,B4; c0137710 CALLP c015e3b8 |

| c0137718 | ui_settings_field_11 | Invoke shared field renderer with parameter 11. | confirmed | c013771a MVK 11,B4; c0137720 CALLP c015e3b8 |
| c0137728 | ui_settings_field_7 | Invoke shared field renderer with parameter 7. | confirmed | c013772a MVK 7,B4; c013772c CALLP c015e3b8 |
| c0137738 | ui_settings_field_6 | Invoke shared field renderer with parameter 6. | confirmed | c013773a MVK 6,B4; c0137740 CALLP c015e3b8 |
| c0137748 | ui_assignment_panel_draw_primary | Render the primary descriptor/assignment panel. | likely | c013776c CALLP c0141aa8; c0137784 CALLP c016c360; c0137a80 CALLP c011c508 |
| c0137a98 | ui_assignment_panel_draw_alternate | Render the alternate descriptor/assignment panel with boxed fields. | likely | c0137ab4 CALLP c0141aa8; c0137acc CALLP c016c360; c0137e18 CALLP c015c4c4 |
| c0137e30 | ui_assignment_panel_dispatch | Select between the two assignment panel renderers after lookup/scaling. | likely | c0137e64 CALLP c0130d28; c0137e8c CALLP c0137748; c0137e9a CALLP c0137a98 |
| c0137eac | ui_assignment_alias_draw | Look up an assignment alias and draw its formatted row. | likely | c0137ec4 CALLP c013d320; c0137f00 CALLP c013d7f8; c0137f08 CALLP c011ebc8 |
| c0137f20 | ui_settings_mode_dispatch | Dispatch settings rendering for global modes 5 and 6. | confirmed | c0137f38 CALLP c0156e80; c0137f40 CMPEQ 5,A4; c0137f46 CMPEQ 6,A1 |
| c0137f60 | usb_callback_unsupported | Return signed status 0xffff8acc. | confirmed | c0137f60 MVK 0xffff8acc,A4; c0137f64 BNOP B3,5; ptr c0180d40 |
| c0137f66 | usb_callback_csr_enable | Apply USB endpoint CSR operation 1 and return zero. | confirmed | c0137f68 CALLP c0120ef8; c0137f6c MVK 1,B4; c0137f6e MVK 0,A4 |
| c0137f74 | usb_endpoint_index_lookup | Validate/normalize endpoint identifier and return its mapped table index through a byte pointer. | likely | c0137f84 MVK 128,B0; c0137fca AND B2,15; c0137fd8 LDB from c011a620; c0137fda STB |
| c0137fe4 | usb_endpoint_prepare_one | Prepare one endpoint record and issue endpoint operation 5. | likely | c0137ff0 CALLP c01229e8; c0138008 CALLP c0137f74; c0138054 CALLP c0138400 with B4=5 |
| c0138070 | usb_endpoint_prepare_all_or_one | Prepare one endpoint, or walk six 52-byte records for identifier -1. | confirmed | c0138074 CMPEQ -1,A4; c0138082 MVK 6,B0; c0138090 LDW *A10++[13]; c013809a CALLP c0137fe4 |
| c01380b4 | usb_endpoint_transfer_service | Resolve endpoint record, drain/service its transfer and issue operation 3. | likely | c01380c4 CALLP c0137f74; c013810a LDW *A4[4]; c0138178 CALLP c0122824; c01381ae CALLP c0138400 |
| c01381c4 | usb_endpoint_operation_2 | Resolve endpoint record and invoke operation 2 with null payload. | confirmed | c01381c8 CALLP c0137f74; c01381f8 MVK 2,B4; c0138204 MVK 0,A6; c0138208 CALLP c0138400 |

| c0138214 | usb_endpoint_operation_1 | Resolve endpoint record and invoke operation 1 with null payload. | confirmed | c0138218 CALLP c0137f74; c0138250 MVK 1,B4; c0138260 CALLP c0138400 |
| c013826c | usb_worker_shutdown | Shut down USB endpoints and release/reset worker resources. | likely | c0138274 CALLP c011ff28; c01382b4/c01382cc/c01382ec STW zero to B14[94..96]; recon/15 |
| c0138300 | usb_worker_reset | Shut down worker resources, reinitialize controller subsystem, return zero. | confirmed | c0138302 CALLP c013826c; c0138304 CALLP c01200c0; c0138308 MVK 0,A4 |
| c0138310 | usb_worker_task | Receive USB commands, dispatch the callback table and signal completion. | likely | c0138318 CALLP c014a214 with B14[95]; c0138330/c0138334 form c0180d40; recon/17 worker descriptor |
| c0138370 | usb_worker_decode_event | Decode controller events, enable IRQ sequence and route endpoint events. | likely | c0138378 CALLP c0121d80; c0138390 CALLP c012154c; c01383e6 LDW event table c01807a0 |
| c0138400 | usb_endpoint_complete | Complete endpoint work by semaphore notification or indirect callback, with transfer bookkeeping. | confirmed | c0138424 STW payload at record+36; c0138428 CALLP c014a080; c0138448 LDW callback at +44; c0138450 B A0 |
| c01384ac | usb_endpoint_io_service | Resolve endpoint, dispatch endpoint I/O and finish through operation 4. | likely | c01384b8 CALLP c0137f74; c0138580 CALLP c0122824; c01385b2 CALLP c0138400 with B4=4 |
| c01385c8 | usb_endpoint_record_bind | Find an available endpoint record and install endpoint-to-record mapping. | likely | c01385ec LDB map c011a620; c0138628 CMPEQ -2,B5; c013864e STW endpoint; c0138652 STB index |
| c0138660 | usb_endpoint_records_reset | Reset one endpoint mapping or reinitialize mappings including endpoints 0 and 128. | likely | c0138664 CMPEQ -1,A2; c0138708 STB through c011a620; c013870c/c0138710 CALLP c01385c8 |
| c0138720 | usb_worker_start | Allocate USB worker resources, handle initialization failures and resume controller. | likely | c0138730 CALLP c014a4d0; c01387cc STW B14[94]; c01387e8 CALLP c0120dd0; recon/17 |
| c01387f0 | usb_command_dispatch | Validate and dispatch USB commands via worker synchronization or callback table. | likely | c0138810/c0138814 compare commands 5/6; c0138a20 CALLP c014a1d8; c0138a48 LDW c0180d40[A4] |
| c0138a6c | usb_helper_c015c6b4 | Forward USB-related caller to c015c6b4. | confirmed | c0138a70 CALLP c015c6b4; caller c015afa0 |
| c0138a78 | usb_endpoint_layer_init | Initialize endpoint records/maps, bind control endpoints and initialize USB controller. | likely | c0138a88/c0138a8c form c011a4e8; c0138b04/c0138b08 CALLP c01385c8; c0138b0c CALLP c0122260 |
| c0138b40 | ui_state_8b60_finish | Set shared flag 1 and clear state word at c0118b78. | confirmed | c0138b42 MVK 1,A4; c0138b44 CALLP c01552d4; c0138b52 STW zero to c0118b78 |
| c0138b58 | ui_state_8b60_reset | Clear 28-byte UI state, initialize it and run a semaphore-guarded refresh. | likely | c0138b70 CALLP memset with A6=28; c0138ba0/c0138bb0 pend/post B14[155]; c0138bac CALLP c014abd0 |

| c0138bc0 | ui_save_state_reset_mode7 | Clear save-screen state, select mode 7 and refresh under semaphore. | likely | c0138bd4 CALLP memset size 28; c0138be2 MVK 7,A0; c0138c08 CALLP c014abd0 under B14[155] |
| c0138c1c | ui_save_state_apply_selection | Pass stored selection at c0118b68 to c0160d2c. | confirmed | c0138c20/c0138c24 form c0118b68; c0138c28 CALLP c0160d2c with LDW value |
| c0138c34 | ui_save_select_active_mode | Inspect selected item and switch active UI item to mode 7 or 8. | likely | c0138c38 LDW *A4[2]; c0138c4c CALLP c01317c4; c0138c6e/c0138c70 load 8/7; c0138c74 CALLP c0149664 |
| c0138c84 | ui_save_mark_pending | Set c0118b78 to 1 and return 1. | confirmed | c0138c88/c0138c8c form c0118b78; c0138c92 STW 1; c0138c94 MVK 1,A4 |
| c0138ca4 | ui_save_commit_selection | Apply the current selection through MIDI/assignment paths according to save-screen mode. | likely | c0138cb8/c0138cc0/c0138cc8 compare 7/8/14; c0138d68 CALLP c0131138; c0138d78 CALLP c012f878 |
| c0138d8c | ui_save_conditional_draw | Invoke common UI drawing only when input bit 0 is set. | confirmed | c0138d8e EXTU A4,31,31,A0; c0138d90 conditional skip; c0138d94 CALLP c011f8d8 with (0,1) |
| c0138da4 | ui_save_draw_mode_icon | Select save-screen icon according to state mode. | likely | c0138db8 CMPEQ 14,A0; c0138dc4 asset c01802b0; c0138e04 asset c01802e8; CALLP c011c508 |
| c0138e28 | ui_save_draw_selection_icon | Draw one of two selection glyphs using assets c0180898/c01808c0. | likely | c0138e30/c0138e50 select asset; c0138e40/c0138e60 CALLP c011c508 |
| c0138e74 | ui_save_draw_marker | Draw fixed marker at vertical position 7 or 20 depending on input. | confirmed | c0138e78 tests input; c0138e80/c0138e82 load 7/20; c0138e90 CALLP c011c508 with asset c0181a68 |
| c0138ea8 | ui_save_draw_slot_label | Format slot/bank digits and render a save selection label. | likely | c0138eb4/c0138ec0 CALLP c0130a00/c0130a30; c0138ee0 CALLP c016a100; fact string %d%d |
| c0138f2c | ui_save_fetch_and_draw_slot | Fetch selected record into stack buffer and render slot label. | likely | c0138f34 CALLP c013142c with B4=SP+8; c0138f40 CALLP c0138ea8 |
| c0138f50 | ui_save_draw_destination_label | Fetch/format the alternate save destination label. | likely | c0138f60 CALLP c013142c; c0138f74 CALLP c0130a30; c0138fe0 CALLP c011d4d8; %d%d |
| c0138ff4 | ui_save_draw_selection_fields | Draw mode/selection icons and both slot labels. | confirmed | c0139002/c0139004 CALLP c0138da4/c0138e28; c0139008/c013900c CALLP c0138f2c/c0138f50 |
| c0139018 | ui_save_draw_footswitch_prompt | Draw the BOTH FSW : SAVE prompt and indexed text variant. | likely | fact string BOTH FSW : SAVE; c0139030 CALLP c011c508; c0139058 CALLP c013a2d8 |
| c0139068 | ui_save_draw_footswitch_prompt_3 | Draw save footswitch prompt with selector 3. | confirmed | c013906a CALLP c0139018; c013906c MVK 3,A4 |

## Data

## Open questions

- Mapping in progress.
