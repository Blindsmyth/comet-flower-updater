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

## Data

## Open questions

- Mapping in progress.
