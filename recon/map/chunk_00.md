# chunk_00: 11800400..118072ac (150 functions)

Scope: the start of the AIS-loaded L2 executable region (recon/16's
`11800400..1180bd40` "AIS executable section; GPIO, drivers,
interrupt/control tasks"). This range holds: two GPIO/peripheral
register init routines run from `c015d428` at boot (`1180044c`,
`11801aa8`, plus a bit-set/bit-clear pair `11800400`/`11800424`); a
locked, low-level serial-transfer driver (`1180673c`, confirmed by
recon/15 and by reading its lock+dispatch code here) built on a small
family of register-poll helpers (`11801498` and siblings) and an
EDMA/PaRAM descriptor builder call-through (`11806700` -> `1180a954`,
confirmed per recon/18); a large 1180-region MIDI command-table
subsystem (`11802a90`..`11803a28`) that reuses the same MIDI lock
B14[161] the c0-region's `c01274cc` (`midi_tx_locked`) uses, dispatched
through a 9-10 entry function-pointer table at `c01840fc..c0184138`
ending in the shared epilogue `118037d6` (already named in 00); a
two-tier rhythm-pattern-table UI renderer family (`11803a60..11804124`
"small" variant, `11804150..118048fc` "large" variant) built on the
already-confirmed `rhythm_get_field117`/`gfx_set_bit_range`; a
TunerService pitch-period measurement core (`11804a44`, reads a
hardware tick counter three times and computes deltas); and the start
of a RhythmService playback/UI dispatcher family (`11806ce0`,
`11806eb4`, `1180710c`) continuing into chunk_01. A dense population of
tiny per-item callback/table-pointer stubs (many `ptr@` references into
`c0185cxx`-`c0186874`) look like settings/menu-item records, consistent
with FWMAP.md's documented settings-menu table.

| addr | name | role | conf | evidence |
|---|---|---|---|---|
| 11800400 | gpio_shadow_set_bit12 | sets bit 12 of the word at offset 0x60 of the struct whose pointer lives at global `0x11813468` (read-modify-write, not a HW SET register) | confirmed | `11800414 LDW *+A3[A4=96]; 1180041a SET A4,12,12,A4; 11800420 STW A4,*+A3[A5=96]` |
| 11800424 | gpio_shadow_clear_bit12 | clears bit 12 of the word at offset 0x180 of the same struct `*0x11813468` | confirmed | `11800440 LDW *B4[0]; 11800444 CLR B4,12,12,B4; 11800448 STW B4,*+A3[0]` with B4=A3+0x180 |
| 1180044c | hw_pinmux_init_block | large (4172 B) peripheral/pinmux init: writes two magic words into fields [14]/[15] of the struct `*0x11813468`, then a long run of CLR+SET passes on 3-4 bit sub-fields all at offset 0x120 of the same struct (bit groups 28,24,20/21-23,16,13,9-11... descending) -- a register-field configuration table, not traced to a specific peripheral name | likely | `11800470 STW A5,*A4[14]`; `11800472 STW A3,*A4[15]`; repeated `CLR.S1 A3,n,m,A3` / `SET.S1 A3,k,k,A3` / `STW *+A4[0x120]` triples from `11800490` to `118004fc` (and beyond, not fully read) |
| 11801498 | serial_cfg_mode_and_poll | sets a 5-bit mode field in reg+0xa28 to 3, sets reg+0 to 1, then busy-polls reg+0x128 bit 0 (via SPLOOP) and reg+0x828 bit 27==3 before returning -- a configure-then-wait-ready step of the shared serial driver | confirmed | `118014c4 CLR B5,0,4,B5; 118014c8 OR 3,B5,B5; 118014cc STW B5,*+B4[0]`; `118014e8 LDW *+A6[0]; 118014ec AND 1,A3,A0` SPLOOP busy-wait; `11801508 LDW; 1180150c EXTU A3,27,27,A3; 11801510 CMPEQ 3,A3,A0` second SPLOOP busy-wait |
| 118015f4 | serial_phase2 | 452 B sibling of `11801498` (same two callers `1180673c`/`c014f5e4`), touches mmio region `01e27000` -- a further configure/poll phase of the serial driver, not read | guess | roots match 11801498 exactly; mmio=01e27000 |
| 118017b8 | serial_phase3 | 512 B sibling, touches mmio `01c10000` and `01e27000` -- likely the data-transfer phase (two peripheral regions at once) | guess | mmio=01c10000,01e27000; same caller pair |
| 118019b8 | serial_phase4 | 240 B sibling, touches mmio `01c10000` only -- likely a GPIO-only (chip-select?) phase | guess | mmio=01c10000; same caller pair |
| 11801aa8 | hw_init_block2 | 3896 B, callers `c015d428` (same as `1180044c`), touches mmio `01c10000`+`01e27000` -- a second large peripheral-register init block run at boot, not traced in detail | guess | n=3896; mmio=01c10000,01e27000; callers=c015d428 |
| 118029e0 | shared_init_helper1 | 48 B, roots DataStore/MIDI/MainApp/PreLoad/RhythmService/UpdateUI, called from the per-task init-table entries `c01453b4`/`c01454f4`/`c0145568` | guess | callers=c01453b4,c01454f4,c0145568 |
| 11802a10 | shared_init_helper2 | 48 B, same roots, single caller `1180b040` | guess | callers=1180b040 |
| 11802a40 | div_wrapper_a | thin wrapper around the integer-divide helper `rts_div32_variant`, caller `11802fcc` | likely | calls=c0169980; n=40 |
| 11802a68 | div_wrapper_b | sibling of `11802a40`, same shape, caller `1180382c` | likely | calls=c0169980; n=40 |
| 11802a90 | midi_tx_forward_1180 | reorders args (A4->B4, B4->A6, A4=0) and tail-calls the veneer `0x1180bd20`, which resolves (MVK 0x4dc8/MVKH 0xc0140000) to `c0144dc8`, the shared UART/MIDI transport also used by `c01274cc`/`c0128580` | confirmed | `11802a98 CALLP 0x1180bd20,B3`; `1180bd20 MVK 0x4dc8,B31` (-> c0144dc8); 9 callers, all in the 1180-region MIDI sender family below |
| 11802aa4 | table9_index_118133cc | indexes a 9-byte-stride table at `0x11810720` using a counter read from global `0x118133cc` (A1 = A0*8+A0) | likely | `11802ab0 LDW *A4[0],A0` (A4=0x118133cc); `11802ab2 SHL A0,3,A1; 11802ab4 ADDAW A1,A0,A1`; B7=0x11810720 |
| 11802b50 | unk_1180_2b50 | 20 B, roots MIDI/MainApp, single caller `c01289ec` | guess | callers=c01289ec |
| 11802b64 | unk_1180_2b64 | 12 B, roots MIDI/MainApp/UpdateUI, callers `c0128788`/`c0134d04`/`c013c54c` | guess | callers=3 |
| 11802b70 | midi_stage_copy_1180 | copies a word+byte pair from global `0x118133d0`/`+4` to `0x11810320`/`+4` -- stages an outgoing byte+flag before the transport call; same 9-caller set as `11802a90` | confirmed | `11802b78 LDW *A4[0],A1` (A4=0x118133d0); `11802b7a LDB *A4[4],A0`; `11802b8a STW A1,*B4[0]`; `11802b8c STB A0,*B4[4]` (B4=0x11810320) |
| 11802b90 | midi_tx_locked_1180 | sem_pend(B14[161]) -> calls `11802a90` (tx forward) and `11802b70` (stage copy) and `c013b8a8` -> sem_post(B14[161]) -- the 1180-region analogue of the c0-region's `midi_tx_locked`, same lock slot B14[161] | likely | b14=138,161; calls=11802a90,11802b70,c013b8a8,bios_sem_pend,bios_sem_post; B14[161] matches c01274cc's confirmed MIDI lock |
| 11802c44 | midi_send_variant1_1180 | locked-sender case: calls `11802b90` then `11805dc0` -- one of ~9 "send MIDI message variant N" cases fed by the table at c0184100-138 | likely | callers=c0168144; calls=11802b90,11805dc0 |
| 11802c58 | midi_send_variant2_1180 | sibling of variant1, calls `11802b90` then `11805dd8` | likely | callers=c0168418; calls=11802b90,11805dd8 |
| 11802c70 | midi_send_variant3_1180 | sibling, calls `11802b90` then `11805de8` | likely | callers=c0168434; calls=11802b90,11805de8 |
| 11802c88 | midi_send_variant4_1180 | sibling, calls `11802b90` then the table-index helper `c0140240` (not the usual `1180xxxx` slot helper) | likely | callers=c012ec80; calls=11802b90,c0140240 |
| 11802ca0 | midi_send_variant5_1180 | sibling, calls `11802b90` then `11805f14` | likely | callers=c0168434; calls=11802b90,11805f14 |
| 11802cb8 | midi_send_variant6_1180 | sibling, calls `11802b90`, `c013b8a8`, and the known table[index] getter `cfg_table_index_1181191c` (c0140320) | likely | callers=c0134650,c013498c; calls=11802b90,c013b8a8,c0140320 |
| 11802cd4 | midi_send_variant7_1180 | sibling, calls `11802b90` then `11805e64` | likely | callers=c016846c; calls=11802b90,11805e64 |
| 11802cec | midi_send_variant8_1180 | sibling, calls `11802b90` then `11805ec4` | likely | callers=c0168488; calls=11802b90,11805ec4 |
| 11802d08 | midi_send_full1_1180 | full locked send (own sem_pend/post on B14[161], not via `11802b90`) calling `11802a90`+`11802b70` directly | likely | callers=c0150738; calls=11802a90,11802b70,bios_sem_pend,bios_sem_post; b14=161 |
| 11802d44 | midi_send_full2_1180 | sibling of `11802d08`, same shape, caller `c01507d8` | likely | b14=161; calls=11802a90,11802b70,bios_sem_pend,bios_sem_post |
| 11802d80 | midi_send_build_1180 | 352 B builder: calls `c0127440`, `rts_memset`, under save/restore -- likely clears/prepares a message buffer before a send, single caller `11802ee0` | guess | n=352; calls=c0127440,rts_memset,rts_regs_restore,rts_regs_save |
| 11802ee0 | midi_send_diag_gated_1180 | 192 B locked op (sem_pend/post B14[161]) gated by `diag_mask_test`, also touches B14[99]; calls `11802a90`,`11802b70`,`11802d80`,`11806258`,`c0130e04`,`c013bc8c` -- a diagnostics/log-gated MIDI send | likely | b14=99,161; calls include c0169fc0=diag_mask_test,bios_sem_pend,bios_sem_post |
| 11802fa0 | unk_1180_2fa0 | 12 B tiny forwarder to `11802ee0`, caller `11803778` | guess | calls=11802ee0 |
| 11802fac | unk_1180_2fac | 12 B tiny forwarder to `11802ee0`, 6 callers across c012/c013/c015 message-type handlers | guess | calls=11802ee0; callers=6 |
| 11802fb8 | unk_1180_2fb8 | 20 B, single caller `c0134650` | guess | callers=c0134650 |
| 11802fcc | div_then_post_1180 | 68 B: calls the divide wrapper `11802a40` then `1180b000` (near the known event-post helper `1180b020`) -- likely divides a value then posts an event | guess | calls=11802a40,1180b000; 4 callers |
| 11803010 | unk_1180_3010 | 32 B, single caller `c0127cf4` | guess | callers=c0127cf4 |
| 11803030 | unk_1180_3030 | 20 B, single caller `c01349ec` (thin_orchestrator_veneers, named in 00) | guess | callers=c01349ec |
| 11803044 | midi_send_full3_1180 | locked sender (sem_pend/post B14[161]) calling `11802a90`+`11802b70` plus `1180b060`, caller `11803780` (a dispatch-table veneer) | likely | b14=161; calls=11802a90,11802b70,1180b060,bios_sem_pend,bios_sem_post |
| 118030a0 | status_struct_rmw_c011ad8c | reads/updates the small status struct at `0xc011ad8c` via the known getter `cfg_get_global_c011ad8c` plus sibling `c0156e8c`, single caller `118030d0` | likely | calls=c0156e80=cfg_get_global_c011ad8c,c0156e8c |
| 118030d0 | locked_dispatch_154 | 96 B locked dispatcher (sem_pend/post), B14[154], calls 10 callees including `118030a0` | guess | b14=154; n=96; callers=11803794 |
| 11803130 | unk_1180_3130 | 124 B, calls `11802fcc`,`c0127fe0`,`c01395dc` under save/restore, single caller `118037a4` | guess | n=124; calls=11802fcc,c0127fe0,c01395dc |
| 118031ac | midi_send_batch_1180 | 168 B locked sender (B14[161]) that calls SIX of the "variant" helpers (`11805dc0`,`11805dd8`,`11805de8`,`11805e64`,`11805ec4`,`11805f14`) in one locked section -- a composite/batch send of several message fields at once | likely | b14=161; calls=11805dc0,11805dd8,11805de8,11805e64,11805ec4,11805f14,bios_sem_pend,bios_sem_post |
| 11803254 | midi_send_full4_1180 | 440 B locked sender variant, B14[161], single caller `1180344c` (paired with `1180340c`) | guess | n=440; b14=161; callers=1180344c |
| 1180340c | midi_send_full5_1180 | 64 B locked sender variant, B14[161], sibling called alongside `11803254` from `1180344c` | guess | b14=161; callers=1180344c |
| 1180344c | midi_send_dispatch1_1180 | dispatches to both `11803254` and `1180340c` then calls `c0156860`, caller `118037b6` (table veneer) | guess | calls=11803254,1180340c,c0156860 |
| 11803474 | midi_send_via_txn_1180 | 64 B locked sender (sem_pend/post) that calls the c0-region `midi_tx_n` (c0127500) directly, plus `c0127fe0`/`c0156938`; B14[180] -- a different lock slot from the B14[161] family above | likely | b14=180; calls=c0127500=midi_tx_n,c0127fe0,c0156938,bios_sem_pend,bios_sem_post |
| 118034b4 | unk_1180_34b4 | 96 B, calls `11802fcc`,`c013b7e8` under save/restore, caller `118037c2` (table veneer) | guess | n=96; calls=11802fcc,c013b7e8 |
| 11803514 | midi_send_full6_1180 | 508 B locked sender, B14[155] and B14[161] -- B14[155] is the same slot flagged for `effect_slot_lookup` (c015c164, string 'OFF') in 00, so this send may report effect on/off state over MIDI | likely | b14=155,161; calls=11802a90,11802b70,1180af60,1180af8c,c0127fe0,rts_memset,bios_sem_pend,bios_sem_post |
| 11803710 | midi_case_body1_1180 | 104 B case body feeding into the shared epilogue `118037d6` (see 00), single caller `c0128e54` | guess | roots=MIDI; calls=118037d6 |
| 11803778 | midi_table_veneer1 | dispatch-table entry #1 (ptr@ c0184138): calls `11802fa0` then the shared epilogue `118037d6` | likely | ptr@=c0184138; calls=11802fa0,118037d6 |
| 11803780 | midi_table_veneer2 | dispatch-table entry #2 (ptr@ c0184130): calls `11803044` then the shared epilogue | likely | ptr@=c0184130; calls=11803044,118037d6 |
| 11803784 | midi_table_veneer3 | dispatch-table entry #3 (ptr@ c0184128): calls `midi_tx_n` (c0127500) and `c01289ec` then the shared epilogue | likely | ptr@=c0184128; calls=c0127500=midi_tx_n,c01289ec,118037d6 |
| 11803794 | midi_table_veneer4 | dispatch-table entry #4 (ptr@ c0184124): calls `118030d0` and `midi_tx_n` then the shared epilogue | likely | ptr@=c0184124; calls=118030d0,c0127500=midi_tx_n,118037d6 |
| 118037a4 | midi_table_veneer5 | dispatch-table entry #5 (ptr@ c0184120): calls `11802fcc`+`11803130` then the shared epilogue | likely | ptr@=c0184120; calls=11802fcc,11803130,118037d6 |
| 118037b2 | midi_table_veneer6 | dispatch-table entry #6 (ptr@ c018411c): calls `118031ac` then the shared epilogue | likely | ptr@=c018411c; calls=118031ac,118037d6 |
| 118037b6 | midi_table_veneer7 | dispatch-table entry #7 (ptr@ c0184108): calls `1180344c` then the shared epilogue | likely | ptr@=c0184108; calls=1180344c,118037d6 |
| 118037ba | midi_table_veneer8 | dispatch-table entry #8 (ptr@ c0184104): calls `11803474` then the shared epilogue | likely | ptr@=c0184104; calls=11803474,118037d6 |
| 118037c2 | midi_table_veneer9 | dispatch-table entry #9 (ptr@ c0184100): calls `118034b4` then the shared epilogue | likely | ptr@=c0184100; calls=118034b4,118037d6 |
| 118037c6 | midi_table_veneer10 | dispatch-table entry #10 (ptr@ c01840fc): calls `11803514` directly | likely | ptr@=c01840fc; calls=11803514 |
| 118037d6 | epilogue_pop_b3_shared3 | see 00 | likely | recon/map/00_library_kernel.md |
| 118037e0 | buf_clear_1180 | 24 B, roots MainApp, calls `rts_memset` -- a small buffer-clear helper, 4 callers | guess | calls=rts_memset |
| 118037f8 | buf_clear_wrap1_1180 | 12 B wrapper around `118037e0`, caller `c0129614` | guess | calls=118037e0 |
| 11803804 | buf_clear_wrap2_1180 | 40 B wrapper around `118037e0`, caller `1180382c` | guess | calls=118037e0 |
| 1180382c | unk_1180_382c | 20 B, calls the divide wrapper `11802a68` and `11803804`, caller `118038f8` | guess | calls=11802a68,11803804 |
| 11803840 | buf_clear_wrap3_1180 | 184 B wrapper around `118037e0` under save/restore, caller `118038f8` | guess | calls=118037e0,rts_regs_restore,rts_regs_save |
| 118038f8 | init_orchestrator_1180 | 304 B: orchestrates `11802aa4` (table9 index), `118037e0`, `1180382c`, `11803840` under save/restore; single caller `c0134bec` | guess | calls=11802aa4,118037e0,1180382c,11803840 |
| 11803a28 | unk_1180_3a28 | 56 B, roots MIDI/MainApp, single caller `c01289ec` | guess | callers=c01289ec |
| 11803a60 | rhythm_calc_small_a | roots UpdateUI; uses the confirmed rhythm-table getter `rhythm_get_field117` plus `rts_sdiv32` -- a layout/geometry calc for the "small" rhythm-pattern render variant | likely | calls=c0166194=rhythm_get_field117,c01675c0=rts_sdiv32 |
| 11803bec | rhythm_draw_small_a | roots UpdateUI; uses `gfx_set_bit_range`, `rhythm_get_field117`, `rts_div32_variant` -- draws rhythm-pattern bits into the LCD bitmap (small variant) | likely | calls=c011c508=gfx_set_bit_range,c0166194=rhythm_get_field117,c0169980=rts_div32_variant |
| 11803d50 | rhythm_draw_small_b | roots UpdateUI; 596 B sibling of `11803bec`, also calls unresolved `c0153f00`/`c0153f0c` plus `c0168640` | likely | calls=c011c508=gfx_set_bit_range,c0153f00,c0153f0c,c0166194=rhythm_get_field117,c0168640,c0169980=rts_div32_variant |
| 11803fa4 | rhythm_render_small | roots UpdateUI; B14[184]; orchestrates `11803a60`+`11803bec`+`11803d50` -- top of the "small" rhythm-pattern render path | likely | b14=184; calls=11803a60,11803bec,11803d50 |
| 11803ff8 | rhythm_render_small_alt | roots UpdateUI; B14[184]; 300 B sibling path calling `11803a60` plus gfx/rhythm helpers and `c0166258` | likely | b14=184; calls=11803a60,c011c508=gfx_set_bit_range,c0153f00,c0153f0c,c0166194=rhythm_get_field117,c0166258,c0168640 |
| 11804124 | rhythm_render_small_dispatch | roots UpdateUI; calls `11803fa4`+`11803ff8`+`11805e10`; callers `1180a0a0`/`c016d2c0` | likely | calls=11803fa4,11803ff8,11805e10 |
| 11804150 | rhythm_calc_large_a | roots UpdateUI; sibling of `11803a60` (same `rhythm_get_field117`+`rts_sdiv32` pair) for the "large" render variant | likely | calls=c0166194=rhythm_get_field117,c01675c0=rts_sdiv32 |
| 118042f0 | rhythm_draw_large_a | roots UpdateUI; sibling of `11803bec`/`11803d50` for the large variant | likely | calls=c011c508=gfx_set_bit_range,c0153f00,c0153f0c,c0166194=rhythm_get_field117,c0168640,c0169980=rts_div32_variant |
| 118044a4 | rhythm_draw_large_b | roots UpdateUI; near-identical sibling of `118042f0` | likely | same callee set as 118042f0 |
| 11804664 | rhythm_draw_large_c | roots UpdateUI; 232 B sibling, no c0153f00/c0153f0c calls | likely | calls=c011c508=gfx_set_bit_range,c0166194=rhythm_get_field117,c0169980=rts_div32_variant |
| 1180474c | rhythm_render_large | roots UpdateUI; B14[184]; orchestrates `11804150`+`118042f0`+`118044a4`+`11804664` -- top of the "large" rhythm-pattern render path | likely | b14=184; calls=11804150,118042f0,118044a4,11804664,c0153f0c,c0166258,c01675c0=rts_sdiv32 |
| 118047cc | rhythm_render_large_alt | roots UpdateUI; B14[184]; sibling dispatch path calling `11804150` plus gfx/rhythm helpers | likely | b14=184; calls=11804150,c011c508=gfx_set_bit_range,c0153f00,c0153f0c,c0166194=rhythm_get_field117,c0166258,c0168640 |
| 118048fc | rhythm_render_large_dispatch | roots UpdateUI; calls `1180474c`+`118047cc`+`11805e10`; same caller pair (`1180a0a0`/`c01697c8`-family) as `11804124` -- likely a top-level "draw rhythm screen" invoking both small- and large-variant renderers | likely | calls=1180474c,118047cc,11805e10; callers=1180a0a0,c01697c8 |
| 1180494c | tuner_helper_a | roots TunerService; 40 B shared helper called from the tuner entry wrapper, the period-measure core, and two other TunerService sites | guess | callers=11804974,11804a44,c014b044,c014b37c |
| 11804974 | tuner_entry_wrapper | roots TunerService; caller `c01674e0` (the TunerService task entry per recon/15's task-anchor table); calls `1180494c` | likely | callers=c01674e0 (TunerService task entry); calls=1180494c |
| 118049ec | unk_1180_49ec | 68 B, roots UpdateUI, single caller `c0129398` | guess | callers=c0129398 |
| 11804a30 | unk_1180_4a30 | 20 B, roots TunerService, single caller `11804a44` | guess | callers=11804a44 |
| 11804a44 | tuner_period_measure | 1524 B TunerService core: reads a hardware tick counter via `1180bae0` three times, computing elapsed-tick deltas into globals `0x118131e4`/`31b0`/`31bc`/`31c0`, compares against a reference count at `0xc011a398`, and calls `rts_udiv32`/`hwi_guarded_divide_update` -- pitch-period measurement (time between zero-crossings) feeding the tuner's frequency computation | likely | `11804a48/70/a8 CALLP 0x1180bae0,B3` (tick read) x3; `11804a6c SUB A1,A0,A0; STW A0,*B4[...]` deltas; `11804aa0 CMPEQ A0,B0,A0` vs c011a398; calls=c0168580=rts_udiv32,c016b540=hwi_guarded_divide_update; b14=108 |
| 11805038 | unk_1180_5038 | 176 B, roots UpdateUI, calls `rts_sdiv32`; mmio `01818000`; single caller `118050e8` | guess | calls=c01675c0=rts_sdiv32; mmio=01818000 |
| 118050e8 | unk_1180_50e8 | 824 B, roots UpdateUI, calls `11805038` plus `11805dc0`/`11805dd8`/`1180b060`; single caller `c013c674` | guess | n=824; calls=11805038,11805dc0,11805dd8,1180b060 |
| 11805420 | orchestrator_1180_region2 | see 00 | guess | recon/map/00_library_kernel.md |
| 11805484 | serial_xfer_caller2_1180 | 212 B; calls `11805420` (see 00) and the confirmed serial-transfer orchestrator `1180673c`, plus `11809420`/`11809438`/`diag_mask_test` -- another entry point into the serial-transfer family | likely | calls=11805420,1180673c=serial_xfer_entry,11809420,11809438,c0169fc0=diag_mask_test |
| 11805558 | unk_1180_5558 | 80 B, roots MainApp, single caller `c0160b80` | guess | callers=c0160b80 |
| 118055a8 | unk_1180_55a8 | 12 B forwarder to `11805420`, caller `1180ab20` | guess | calls=11805420 |
| 118055b4 | unk_1180_55b4 | 96 B, roots MainApp; calls `11805420`,`11805484`,`rts_memset`; caller `c0160b80` | guess | calls=11805420,11805484,rts_memset |
| 11805614 | unk_1180_5614 | 28 B, roots MIDI/MainApp; calls `11805420`; callers `c0160b80`/`c0169700` | guess | calls=11805420 |
| 11805630 | hwi_guarded_update_1180 | 584 B, roots MIDI/MainApp/UpdateUI; calls `hwi_guarded_divide_update` under save/restore; single caller `11805878` (the audio_or_ui_handler named in 00) | likely | calls=c016b540=hwi_guarded_divide_update; callers=11805878 |
| 11805878 | audio_or_ui_handler_1180 | see 00 | guess | recon/map/00_library_kernel.md |
| 11805b00 | unk_1180_5b00 | 32 B forwarder to `11805420`, caller `c0160b80` | guess | calls=11805420 |
| 11805b20 | unk_1180_5b20 | 16 B, single caller `c0168144` | guess | callers=c0168144 |
| 11805b30 | menu_item_record1 | 20 B, ptr@ c0185e4c -- a settings/menu-item record entry (FWMAP's documented settings table family); caller `c01508f0` | guess | ptr@=c0185e4c |
| 11805b44 | unk_1180_5b44 | 16 B, single caller `c0168418` | guess | callers=c0168418 |
| 11805b54 | unk_1180_5b54 | 112 B, single caller `c0168434` | guess | callers=c0168434 |
| 11805bc4 | menu_item_record2 | 52 B, ptr@ c0185ca8 -- settings/menu-item record entry | guess | ptr@=c0185ca8 |
| 11805bf8 | unk_1180_5bf8 | 76 B, single caller `c016846c` | guess | callers=c016846c |
| 11805c44 | menu_item_record3 | 16 B, ptr@ c0186160 -- settings/menu-item record entry | guess | ptr@=c0186160 |
| 11805c54 | unk_1180_5c54 | 36 B, roots MIDI/MainApp; single caller `c0163118` (locked_subsystem_op_115, named in 00) | guess | callers=c0163118=locked_subsystem_op_115 |
| 11805c78 | unk_1180_5c78 | 76 B, single caller `c0168488` | guess | callers=c0168488 |
| 11805cc4 | menu_item_record4 | 16 B, ptr@ c0185cec -- settings/menu-item record entry | guess | ptr@=c0185cec |
| 11805cd4 | menu_item_record5 | 20 B, ptr@ c0185e00 -- settings/menu-item record entry | guess | ptr@=c0185e00 |
| 11805ce8 | unk_1180_5ce8 | 56 B, single caller `c0168434` | guess | callers=c0168434 |
| 11805d20 | orchestrator_1180_region3 | see 00 | guess | recon/map/00_library_kernel.md |
