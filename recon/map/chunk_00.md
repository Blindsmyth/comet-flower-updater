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
| 118015f4 | serial_phase2 | same configure+poll shape as `11801498`: `CLR`+`OR` sets a mode field to 3, writes a ready flag, then two SPLOOP busy-waits (one on a RAM status word, one on MMIO `01e27128` via shift+AND) before an EXTU+CMPEQ-3 status check -- next configure/poll phase of the shared serial driver | likely | `11801620 CLR B5,0,4,B5; 11801624 OR 3,B5,B5`; SPLOOPW busy-waits at `11801630`/`11801674`; `118016a8 MVK 0x7128,B5`+`MVKH 0x1e20000,B5` = mmio 01e27128 |
| 118017b8 | serial_phase3 | polls MMIO `01e27128` bit0 via SPLOOP, then `CLR`+`OR` sets a mode field at `01e27a28` to 2 and writes a ready flag, then polls MMIO `01e27828` bit0 via a second SPLOOP -- a third configure/poll phase touching two adjacent `01e27xxx` registers | likely | `118017c4 LDW *B4[0]` (mmio 01e27128); `11801814 CLR A5,0,4,A5; 11801818 OR 2,A5,A5; STW *A4[0]` (mmio 01e27a28); second SPLOOP polls mmio 01e27828 |
| 118019b8 | serial_phase4 | same shape confined to MMIO bank `01c10000` only: polls `01c10128` bit0 via SPLOOP, then `CLR`+`OR` sets a mode field at `01c10a10` to 2 and writes a ready flag -- a configure/poll phase on that bank alone (which peripheral is not confirmed) | likely | `118019c4 LDW *B4[0]` (mmio 01c10128); `11801a14 CLR A5,0,4,A5; 11801a18 OR 2,A5,A5; STW *A4[0]` (mmio 01c10a10) |
| 11801aa8 | hw_init_block2 | opens with the identical configure(mode=3)+two-stage-SPLOOP-poll sequence used by `11801498`/`118015f4` (same MMIO offsets 0x0a00/0x128/0x800/0x0a04, `CLR`+`OR`=3, `EXTU 27,27`+`CMPEQ 3` check), then continues into further register writes not traced to the end (3896 B total) -- likely brings up the same serial/UART peripheral block rather than generic pinmux, run at boot from the same caller as `1180044c` | likely | `11801ad0 CLR B4,0,4,B5; 11801ad4 OR 3,B5,B4; STW *A5[0]`; SPLOOPW at `11801ae4`/`11801b34`; `11801b18 EXTU A4,27,27,A4; 11801b20 CMPEQ 3,A4,A0` |
| 118029e0 | shared_init_helper1 | read-modify-write on field +0x13c of the struct `*0x11813468`: extracts bit 4 of the old value into bit 0, forces bit 28 on, and stores that back -- discards the rest of the old field, so this reinitializes the status word (carrying one flag forward) rather than patching it | confirmed | `11802a04 EXTU B4,4,4,B4; 11802a08 SET B4,28,28,B4; 11802a0c STW B4,*+A3[0]` (same 0x13c offset just loaded) |
| 11802a10 | shared_init_helper2 | identical to `118029e0` but forces bit 31 instead of bit 28: reinitializes field +0x13c of `*0x11813468`, carrying old bit 4 into bit 0 | confirmed | `11802a30 EXTU B4,4,4,B4; 11802a34 SET B4,31,31,B4; 11802a38 STW B4,*+A3[0]` |
| 11802a40 | div_wrapper_a | thin wrapper around the integer-divide helper `rts_div32_variant`, caller `11802fcc` | likely | calls=c0169980; n=40 |
| 11802a68 | div_wrapper_b | sibling of `11802a40`, same shape, caller `1180382c` | likely | calls=c0169980; n=40 |
| 11802a90 | midi_tx_forward_1180 | reorders args (A4->B4, B4->A6, A4=0) and tail-calls the veneer `0x1180bd20`, which resolves (MVK 0x4dc8/MVKH 0xc0140000) to `c0144dc8`, the shared UART/MIDI transport also used by `c01274cc`/`c0128580` | confirmed | `11802a98 CALLP 0x1180bd20,B3`; `1180bd20 MVK 0x4dc8,B31` (-> c0144dc8); 9 callers, all in the 1180-region MIDI sender family below |
| 11802aa4 | table9_index_118133cc | indexes a 9-byte-stride table at `0x11810720` using a counter read from global `0x118133cc` (A1 = A0*8+A0) | likely | `11802ab0 LDW *A4[0],A0` (A4=0x118133cc); `11802ab2 SHL A0,3,A1; 11802ab4 ADDAW A1,A0,A1`; B7=0x11810720 |
| 11802b50 | midi_edit_value_set_1180 | setter: stores arg A4 into global word `0x118133d8` and returns -- paired getter is `11802b64`; single caller `c01289ec` (midi_apply_param_edit) | confirmed | `11802b5c STW A0,*A4[0]` at 0x118133d8 |
| 11802b64 | midi_edit_value_get_1180 | getter: returns global word `0x118133d8` (written by `11802b50`); read by error-report build, mode-event dispatch and the settings screen builder | confirmed | `11802b6c LDW *A4[0],A4` at 0x118133d8 |
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
| 11805d84 | bound_check_lt4 | see 00 | likely | recon/map/00_library_kernel.md |
| 11805dc0 | shared_accessor1_1180 | 12 B, roots UpdateUI; 7 callers spanning both the rhythm-render family (`11802c44`,`118031ac`,`118050e8`) and settings-menu sites (`c0154654`,`c0159160`,`c01591ac`,`c0159216`) -- a generic small B14/global accessor | guess | callers=7 |
| 11805dcc | unk_1180_5dcc | 12 B, ptr@ c0185e48; 4 callers | guess | ptr@=c0185e48 |
| 11805dd8 | shared_accessor2_1180 | 16 B, roots UpdateUI; ptr@ c0185ebc; callers `11802c58`,`118031ac`,`118050e8` | guess | ptr@=c0185ebc |
| 11805de8 | shared_accessor3_1180 | 28 B, roots MainApp/TunerService; 6 callers incl `11802c70`,`118031ac`,`11804a44` | guess | callers=6 |
| 11805e04 | unk_1180_5e04 | 12 B, single caller `c013ac04` | guess | callers=c013ac04 |
| 11805e10 | shared_accessor4_1180 | 16 B, roots MIDI/MainApp/RhythmService/UpdateUI; 7 callers spanning both rhythm-render dispatchers (`11804124`,`118048fc`) and RhythmService (`11806ce0`,`11806eb4`) -- likely a "get current rhythm pattern/slot" accessor shared by UI render and playback | guess | callers=11804124,118048fc,11806ce0,11806eb4,c0150588,c015408c,c0158c58 |
| 11805e20 | unk_1180_5e20 | 12 B, roots MIDI/MainApp/RhythmService; single caller `c0158cf4` | guess | callers=c0158cf4 |
| 11805e2c | unk_1180_5e2c | 12 B, 8 callers (c0148xxx family) | guess | callers=8 |
| 11805e38 | menu_item_record6 | 16 B, roots UpdateUI; ptr@ c0185ca4,c0186870 -- settings/menu-item record entry | guess | ptr@=c0185ca4,c0186870 |
| 11805e48 | menu_item_record7 | 12 B, roots UpdateUI; ptr@ c018686c | guess | ptr@=c018686c |
| 11805e54 | menu_item_record8 | 16 B, roots UpdateUI; ptr@ c0186874 | guess | ptr@=c0186874 |
| 11805e64 | shared_accessor5_1180 | 12 B, roots AD/MIDI/MainApp/RhythmService; 11 callers | guess | callers=11 |
| 11805e70 | unk_1180_5e70 | 16 B, roots MIDI/MainApp; 3 callers | guess | callers=3 |
| 11805e80 | unk_1180_5e80 | 12 B, roots MIDI; single caller `c013af08` | guess | callers=c013af08 |
| 11805e8c | unk_1180_5e8c | 12 B, roots MainApp; single caller `c016a8c0` | guess | callers=c016a8c0 |
| 11805e98 | menu_item_record9 | 16 B, roots MIDI/MainApp; ptr@ c018615c; caller `c0139a70` | guess | ptr@=c018615c |
| 11805ea8 | unk_1180_5ea8 | 12 B, roots MainApp; callers `c01631d4`,`c016976c` | guess | callers=2 |
| 11805eb4 | unk_1180_5eb4 | 16 B, roots MIDI/MainApp/Swi:USB/SwitchNrmlSpdRead; 3 callers | guess | callers=3 |
| 11805ec4 | shared_accessor6_1180 | 12 B, roots MIDI/MainApp; ptr@ c0185d34; 10 callers | guess | ptr@=c0185d34; callers=10 |
| 11805ed0 | unk_1180_5ed0 | 40 B, callers `c01301cc`,`c01307d4` | guess | callers=2 |
| 11805ef8 | menu_item_record10 | 16 B, roots MainApp/UpdateUI; ptr@ c0185ce8; callers `c01374c8`,`c01694a0` | guess | ptr@=c0185ce8 |
| 11805f08 | menu_item_record11 | 12 B, roots MIDI/MainApp/Swi:USB/SwitchNrmlSpdRead; ptr@ c0185dfc; caller `1180add8` | guess | ptr@=c0185dfc |
| 11805f14 | shared_accessor7_1180 | 16 B, roots MIDI/MainApp/RhythmService/UpdateUI; 6 callers | guess | callers=6 |
| 11805f24 | unk_1180_5f24 | 12 B, roots AD/MIDI/MainApp/UpdateUI; single caller `c01635c0` | guess | callers=c01635c0 |
| 11805f30 | unk_1180_5f30 | 16 B, callers `11807d54`,`c0148c48` | guess | callers=2 |
| 11805f40 | table_lookup_1180 | 112 B, calls the known table[index] getter `cfg_table_index_1181191c` (c0140320) under save/restore -- sibling of `validated_table_lookup` (11805fb0, named in 00) but without the bound-check | likely | calls=c0140320=cfg_table_index_1181191c; callers=c015ade0,c015ae50 |
| 11805fb0 | validated_table_lookup | see 00 | likely | recon/map/00_library_kernel.md |
| 1180604c | const1_wrapper1_1180 | 152 B, roots MIDI/MainApp; calls `rts_const_return_1` under save/restore; 2 callers | guess | calls=c012af98=rts_const_return_1 |
| 118060e4 | unk_1180_60e4 | 60 B, roots MIDI/MainApp; 4 callers | guess | callers=4 |
| 11806120 | unk_1180_6120 | 312 B, roots MIDI/MainApp; calls `c0140220`,`c0141ac8`,`c0141b74`; callers `11806450`,`c013fef0` | guess | n=312; calls=3 |
| 11806258 | unk_1180_6258 | 20 B, roots MIDI/MainApp; calls out-of-range `118092a0`; 11 callers | guess | calls=118092a0 |
| 1180626c | unk_1180_626c | 72 B, roots PreLoad/RhythmService/UpdateUI; calls out-of-range `118092a0`; caller `1180a3d0` | guess | calls=118092a0 |
| 118062b4 | buf_copy_const1_1180 | 276 B: calls `rts_const_return_1`, `c012efb0`, and the SPLOOP word-memcpy `rts_memcpy_word_sploop` -- copies a fixed-size buffer/table and may return a fixed status; single caller `c0157984` | guess | calls=c012af98=rts_const_return_1,c012efb0,c016d4c0=rts_memcpy_word_sploop |
| 118063c8 | midi_compose_usb_desc1 | 136 B: calls `usb_desc_table_get` and `orchestrator_midi_compose` -- builds/sends a MIDI-like message incorporating a field from the USB class-descriptor table, ties the MIDI and USB subsystems together | likely | calls=c012afe0=usb_desc_table_get,c012ee10=orchestrator_midi_compose |
| 11806450 | midi_usb_orchestrator_1180 | 688 B: combines `11806120` and `118063c8` plus several c012/c013/c014 callees; single caller `1180738c` (out of range, chunk_01) | guess | n=688; calls=11806120,118063c8,c012b180,c012b2c0,c01313e8,c013ba64,c013ffd0,c01400d4,c01404ec,c0141ac8 |
| 11806700 | edma_param_build_serial | builds an EDMA PaRAM descriptor as part of the serial-transfer setup: enters via the L2 save-helper `1180bd10` and calls `1180a954` (recon/16's confirmed PaRAM builder) directly, matching recon/18's cited call site `11806724` exactly | confirmed | `11806724 CALLP.S2 0x1180a954,B3` read directly; caller `1180673c` |
| 1180673c | serial_xfer_entry | locked low-level serial-transfer orchestrator; its own body ends at 11806c8c, pends B14[163], selects the 11801498/118015f4 transfer path, repeatedly builds EDMA descriptors, runs the 118017b8/118019b8 phases, then posts B14[170] | confirmed | own span 1180673c..11806c8b; caller 11805450/118054b0/1180abf0 plus veneer c016f170; calls 11801498,118015f4,118017b8,118019b8,11806700,1180b9b0,1180b9c0,1180bad0,1180bc70,1180bcc0,1180bcd0,1180bcf0,1180bd10,1180bd30 |
| 11806c8c | serial_sem_post_171 | (hidden start) post the semaphore/event handle in B14[171] and return 0 | confirmed | address ref c014f8cc; `11806c90 CALLP 1180bcd0` with `11806c94 LDW *+B14[171],A4`; return at 11806ca2 |
| 11806ca4 | serial_sem_post_151 | (hidden start) post the semaphore/event handle in B14[151] and return 0 | confirmed | address ref c014f694; `11806ca8 CALLP 1180bcd0` with `11806cac LDW *+B14[151],A4`; return at 11806cb6 |
| 11806cb8 | serial_sem_post_152 | (hidden start) post the semaphore/event handle in B14[152] and return 0 | confirmed | address ref c014f6b0; `11806cc0 CALLP 1180bcd0` with `11806cc4 LDW *+B14[152],A4`; return at 11806cd4 |
| 11806ce0 | rhythm_ui_update_dispatch | 468 B RhythmService/MIDI/MainApp dispatcher: calls `ui_event_post_byte` (1180b020) and `big_subsystem_init` (c0155ac0), touches B14 slots 48,49,50,53,108,165,184-189 -- overlaps heavily with the rhythm-render (B14[184]) and tuner (B14[108]) B14 slots seen above, consistent with a RhythmService state/UI update step | likely | b14=48,49,50,53,108,165,184,185,186,187,188,189; calls include 1180b020=ui_event_post_byte,c0155ac0=big_subsystem_init |
| 11806eb4 | rhythm_playback_step | 600 B RhythmService routine: calls `ui_event_post_byte`,`big_subsystem_init`, and the rhythm-table field getter family near `c0166180`/`c0166194`; B14 50,51,108,139,184,187,189,208,209; single caller `1180710c` | likely | b14=50,51,108,139,184,187,189,208,209; calls=1180a070,1180a080,1180b020=ui_event_post_byte,c0155ac0=big_subsystem_init,c0166180,c0167400,c0167410,c0167478 |
| 1180710c | rhythm_playback_dispatch | 276 B wrapper around `11806eb4`; B14 48,49,184,188; single caller `c016aa88` | likely | b14=48,49,184,188; calls=11806eb4 |
| 11807220 | midi_compose_usb_desc2 | 140 B sibling of `118063c8`: calls `usb_desc_table_get` and `orchestrator_midi_compose`; single caller `1180738c` | likely | calls=c012afe0=usb_desc_table_get,c012ee10=orchestrator_midi_compose |

## Data

- Global peripheral-base pointer `0x11813468` (read via `MVK 0x3468,A3; MVKH 0x11810000,A3; LDW *A3[0],A3`): a struct whose fields include word offsets `0x60` (bit-set target of `11800400`), `0x180` (bit-clear target of `11800424`), `0x120` (the repeated 3-4 bit pinmux-style field edits in `1180044c`), and words `[14]`/`[15]` (two magic constants `0x83e70b13`-ish and `0x95a4f1e0`-ish written by `1180044c`). Likely a peripheral/pinmux controller register block mapped through a driver-context pointer; exact peripheral identity not established.
- `0x118133cc`/`0x118133d0`: a small MIDI-send staging area read by `11802aa4` (9-byte-stride table index at `0x11810720`) and `11802b70` (word+byte copy to `0x11810320`). Together with the dispatch table at `c01840fc..c0184138` (9-10 function-pointer entries, each a "send MIDI message variant N" case ending in the shared epilogue `118037d6`), this is the 1180-region's MIDI command-table subsystem. It shares the MIDI lock slot **B14[161]** with the c0-region's confirmed `midi_tx_locked` (`c01274cc`), and one variant (`11803474`) calls the c0-region `midi_tx_n` (`c0127500`) directly -- the two regions are not independent MIDI paths but layers of the same transport. One variant (`11803514`) additionally touches B14[155], the same slot flagged for the effect on/off query `effect_slot_lookup` (c015c164, 'OFF' string) in 00 -- open question whether this variant reports effect state over MIDI.
- `0x1180bd10`/`0x1180bd20`/`0x1180bae0`/`0x1180bcf0`/`0x1180bcc0` (just past this chunk, in chunk_01's range): the 1180-region's own save/restore prologue-epilogue pair and lock/tick helpers. `0x1180bd20` is confirmed (by reading it) to be a veneer to `c0144dc8` (`MVK 0x4dc8,B31; MVKH 0xc0140000,B31; B B31`); `0x1180bcf0` behaves as the 1180-region's `Semaphore_pend` analogue (handle from B14[163], timeout -1, called from `1180673c`); `0x1180bae0` returns a free-running hardware tick/counter value (called 3x by `tuner_period_measure`, 11804a44). These deserve a confirmed row from whichever chunk covers 1180b020..1180bd40.
- The rhythm-pattern UI render family splits into two near-identical trees sharing the confirmed table `0xc0182730`/`rhythm_get_field117`: a "small" variant (`11803a60`,`11803bec`,`11803d50` -> `11803fa4`/`11803ff8` -> `11804124`) and a "large" variant (`11804150`,`118042f0`,`118044a4`,`11804664` -> `1180474c`/`118047cc` -> `118048fc`), both gated by B14[184] and both called from the same two sites (`1180a0a0` and a `c01697c8`/`c016d2c0` pair) -- consistent with one screen drawing both a small icon and a full pattern grid.
- `0xc011ad8c` status struct (named in 00's Data section) is also touched here by `118030a0` via the confirmed getter `cfg_get_global_c011ad8c`.
- Many 12-20 byte leaves in `11805bxx`-`11805fxx` carry `ptr@` references into `c0185cxx`..`c0186874` -- consistent with FWMAP.md's documented settings-menu table around `c0182b38`; named `menu_item_recordN` here as honest placeholders, not traced to specific menu entries.

## Open questions

- Hidden-start pass 2026-10-09: 3 rows added, 1 host rows rewritten, 0 false positives.

- The exact peripheral behind the struct at `0x11813468` (bit 12 set/clear in `11800400`/`11800424`, pinmux-style field edits at offset `0x120` in `1180044c`) is unidentified; a future pass with a TI DaVinci/OMAP-L1 peripheral register map could likely name it precisely (GPIO bank vs. PINMUX controller vs. something else).
- `11801498`/`118015f4`/`118017b8`/`118019b8` are almost certainly four phases of one serial-transfer protocol (config+poll / mmio 01e27000 / mmio 01c10000+01e27000 / mmio 01c10000), but only `11801498` was actually read; the other three are guesses from caller-set matching alone.
- The 1180-region MIDI send-variant family (`11802a90`..`11803a28`, ~30 functions) was classified mostly by call-graph shape (which helper(s) each "variant" calls) rather than by reading each variant's body; a future pass could read a few variants directly to pin down which MIDI message type (note/CC/PC/SysEx) each dispatch-table slot actually sends, and whether the table is indexed by UI event code or by MIDI message ID.
- `11805e10` is shared between the rhythm-render dispatchers (UpdateUI, B14[184]) and the RhythmService playback routines (`11806ce0`,`11806eb4`) -- worth confirming whether it is a single "current rhythm pattern pointer" accessor used by both drawing and playback, which would tie this chunk's two rhythm sub-families together.
- `11806450`'s and `1180710c`'s single caller (`1180738c`, `c016aa88`) are both outside this chunk (chunk_01 territory); whoever maps that range should cross-check the B14 slots and callee sets noted here.
- `11806258`/`1180626c` both call `118092a0`, also outside this chunk -- worth checking what that shared target does once chunk_01/chunk_02 names it.

## Review by Claude (2026-10-08)
11800400/11800424: `LDW *+A3[A4]` with A4 = 96 (11800414) is scaled, giving **byte offset 0x180** for both functions, not 0x60 for the set. Both act on the same word (+0x180) of the struct at *0x11813468: set bit 12 / clear bit 12. The role is otherwise as stated.
